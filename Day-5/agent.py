import logging
import json
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

FAQ_PATH = Path("shared-data/day5_zerodha_faq.json")
LEADS_PATH = Path("zerodha_leads.json")


# ------------------------
# FAQ loading & search
# ------------------------
def load_faq_data() -> List[Dict[str, Any]]:
    if not FAQ_PATH.exists():
        logger.warning(f"FAQ file not found at {FAQ_PATH.resolve()}")
        return []
    try:
        with FAQ_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        logger.exception("Failed to read FAQ file")
        return []


FAQ_DATA: List[Dict[str, Any]] = load_faq_data()


def keyword_score(query: str, item: Dict[str, Any]) -> int:
    """Very simple keyword matching score."""
    q_words = {w.lower() for w in query.split() if len(w) > 2}
    haystack = " ".join(
        [item.get("question", ""), item.get("answer", ""), " ".join(item.get("tags", []))]
    ).lower()
    return sum(1 for w in q_words if w in haystack)


def find_best_faq(query: str) -> str:
    if not FAQ_DATA:
        return "I do not have company FAQ data loaded right now."

    best_item = None
    best_score = 0
    for item in FAQ_DATA:
        score = keyword_score(query, item)
        if score > best_score:
            best_score = score
            best_item = item

    if not best_item or best_score == 0:
        return "I am not sure about that specific detail. You may need to check the Zerodha website for the latest information."

    return best_item.get("answer", "I have an answer, but it seems incomplete.")


# ------------------------
# Lead storage helpers
# ------------------------
def load_leads() -> List[Dict[str, Any]]:
    if not LEADS_PATH.exists():
        return []
    try:
        with LEADS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        logger.exception("Failed to read leads file")
        return []


def append_lead(lead: Dict[str, Any]) -> None:
    leads = load_leads()
    leads.append(lead)
    try:
        with LEADS_PATH.open("w", encoding="utf-8") as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved lead: {lead}")
    except Exception:
        logger.exception("Failed to write leads file")


# ------------------------
# SDR Agent
# ------------------------
class ZerodhaSDRAssistant(Agent):
    def __init__(self) -> None:
        instructions = (
            "You are a friendly Sales Development Representative (SDR) for Zerodha, "
            "an Indian online discount brokerage platform.\n"
            "You are talking to potential customers via voice.\n\n"
            "Your goals:\n"
            "1) Greet the visitor warmly and introduce yourself as part of Zerodha.\n"
            "2) Ask what brought them here and what they are working on.\n"
            "3) Understand their needs: are they investors, traders, beginners, or advanced?\n"
            "4) Answer questions about Zerodha ONLY using the FAQ and company info available "
            "through the tool `search_faq`. Do not make up exact numbers or promises.\n"
            "5) Politely collect lead details during the conversation:\n"
            "   - name\n"
            "   - company (or 'individual')\n"
            "   - email\n"
            "   - role\n"
            "   - use case (what they want Zerodha for)\n"
            "   - team size\n"
            "   - timeline (now / soon / later)\n"
            "6) When the user indicates they are done (for example: 'that is all', 'I am done', 'thanks') "
            "and you have most of the lead fields, do the following:\n"
            "   - Give a short spoken summary of who they are, what they want, and the rough timeline.\n"
            "   - Then call the tool `save_lead` EXACTLY ONCE with the final lead details and a summary.\n"
            "7) If you are uncertain about any detail, say so honestly.\n"
            "8) Keep responses short, clear, and conversational. No emojis or markdown.\n"
        )

        super().__init__(instructions=instructions)

    # FAQ tool
    @function_tool
    async def search_faq(self, ctx: RunContext, question: str) -> str:
        """
        Search Zerodha FAQ/company info and return a concise answer.

        Use this whenever the user asks about:
        - what Zerodha does
        - who it is for
        - pricing and brokerage
        - platforms, account opening, etc.
        """
        answer = find_best_faq(question)
        return answer

    # Lead saving tool
    @function_tool
    async def save_lead(
        self,
        ctx: RunContext,
        name: str,
        company: str,
        email: str,
        role: str,
        use_case: str,
        team_size: str,
        timeline: str,
        summary: str,
    ) -> str:
        """
        Save lead information at the end of the call.

        Call this ONLY ONCE when:
        - The user has indicated they are done, AND
        - You have collected most of the fields.

        Fields:
        - name: Lead's name
        - company: Company name or 'individual'
        - email: Contact email
        - role: What they do (e.g. founder, student, trader)
        - use_case: What they want Zerodha for
        - team_size: Size of their team/user group
        - timeline: Rough timeline (now / soon / later)
        - summary: 1–2 sentence SDR-style summary
        """
        lead = {
            "name": name,
            "company": company,
            "email": email,
            "role": role,
            "use_case": use_case,
            "team_size": team_size,
            "timeline": timeline,
            "summary": summary,
        }

        append_lead(lead)
        return "I have saved this lead to the system."


# ------------------------
# LiveKit plumbing
# ------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=ZerodhaSDRAssistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
