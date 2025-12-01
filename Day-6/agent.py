import logging
import json
from pathlib import Path
from typing import Dict, Any, List

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

FRAUD_DB_PATH = Path("shared-data/day6_fraud_cases.json")


# -----------------------------
# Database Helpers
# -----------------------------
def load_fraud_cases() -> List[Dict[str, Any]]:
    if not FRAUD_DB_PATH.exists():
        logger.error("Fraud DB not found.")
        return []
    try:
        with FRAUD_DB_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        logger.exception("Failed to read fraud DB.")
        return []


def save_fraud_cases(cases: List[Dict[str, Any]]) -> None:
    try:
        with FRAUD_DB_PATH.open("w", encoding="utf-8") as f:
            json.dump(cases, f, indent=2, ensure_ascii=False)
    except:
        logger.exception("Failed to write fraud DB.")


# -----------------------------
# Fraud Agent
# -----------------------------
class FraudAlertAgent(Agent):
    def __init__(self):
        instructions = (
            "You are a fraud alert representative for a fictional Indian bank called Horizon Bank.\n"
            "You are contacting a customer about a suspicious card transaction.\n\n"

            "CALL FLOW:\n"
            "1) Greet professionally: ‘This is the fraud monitoring desk at Horizon Bank.’\n"
            "2) Ask for the customer's first name to load their fraud case.\n"
            "3) Load the fraud case using the tool `load_case`.\n"
            "4) Ask ONE non-sensitive verification question from the case.\n"
            "5) If user answers incorrectly → politely end with verification_failed.\n"
            "6) If verification passes → read the suspicious transaction:\n"
            "   - merchant\n"
            "   - amount\n"
            "   - location\n"
            "   - time\n"
            "   - masked card ending\n"
            "7) Ask: ‘Did you make this transaction?’\n"
            "8) If yes → mark safe.\n"
            "9) If no → mark fraudulent (mock card block, mock dispute).\n"
            "10) Use tool `update_case_status` EXACTLY ONCE at end.\n\n"

            "RULES:\n"
            "- Never ask for PIN, full card number, password, OTP, or anything sensitive.\n"
            "- Stay calm, professional, and reassuring.\n"
            "- Keep responses short.\n"
        )
        super().__init__(instructions=instructions)
        self.current_case = None  # store case for call


    # -----------------------------
    # TOOL: Load Case by Name
    # -----------------------------
    @function_tool
    async def load_case(self, ctx: RunContext, user_name: str) -> str:
        """
        Load a fraud case from DB for the given username.
        """
        cases = load_fraud_cases()
        for c in cases:
            if c.get("userName", "").lower() == user_name.lower():
                self.current_case = c
                return (
                    f"I have located your case for {user_name}. "
                    "Please answer a simple verification question next."
                )
        return "I could not find a case for that name. Please try again."


    # -----------------------------
    # TOOL: Update Case Status
    # -----------------------------
    @function_tool
    async def update_case_status(
        self,
        ctx: RunContext,
        user_name: str,
        status: str,
        outcomeNote: str
    ) -> str:
        """
        Update fraud case in DB exactly once.
        """
        cases = load_fraud_cases()
        updated = False
        for c in cases:
            if c.get("userName", "").lower() == user_name.lower():
                c["status"] = status
                c["outcomeNote"] = outcomeNote
                updated = True
                break

        if updated:
            save_fraud_cases(cases)
            return "The fraud case has been updated."
        else:
            return "I could not update the case because the user was not found."


# -----------------------------
# LiveKit Plumbing
# -----------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Calm",
            tokenizer=tokenize.basic.SentenceTokenizer(),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()
    @session.on("metrics_collected")
    def _on(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(usage_collector.get_summary())

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=FraudAlertAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
