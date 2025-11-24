import logging
import json
from pathlib import Path
from datetime import datetime

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

WELLNESS_LOG_PATH = Path("wellness_log.json")


def load_wellness_history() -> list:
    """Load past wellness entries from wellness_log.json."""
    if not WELLNESS_LOG_PATH.exists():
        return []
    try:
        with WELLNESS_LOG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        logger.exception("Failed to read wellness_log.json")
        return []


def append_wellness_entry(entry: dict) -> None:
    """Append a new entry to the wellness log."""
    history = load_wellness_history()
    history.append(entry)
    try:
        with WELLNESS_LOG_PATH.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved wellness entry to {WELLNESS_LOG_PATH.resolve()}: {entry}")
    except Exception:
        logger.exception("Failed to write wellness_log.json")


class Assistant(Agent):
    def __init__(self) -> None:
        # Build dynamic context from previous check-ins
        history = load_wellness_history()
        last_entry_context = ""

        if history:
            last = history[-1]
            last_mood = last.get("mood", "unknown")
            last_goals = last.get("goals", [])
            last_goals_str = ", ".join(last_goals) if last_goals else "no specific goals"
            last_entry_context = (
                "\n\nContext from our last check-in:\n"
                f"- You said you felt: '{last_mood}'.\n"
                f"- Your goals were: {last_goals_str}.\n"
                "Gently reference this if it helps the conversation, "
                "for example by asking how today compares."
            )

        base_instructions = (
            "You are a daily Health & Wellness Voice Companion.\n"
            "You are NOT a doctor or therapist.\n"
            "You are a warm, realistic, supportive check-in partner.\n\n"
            "Your job in each session:\n"
            "1) Ask how the user is feeling today (mood + energy).\n"
            "   - Examples: 'How are you feeling today?', 'What is your energy like?'\n"
            "2) Ask about 1–3 simple, realistic goals or intentions for today.\n"
            "   - Work, study, self-care, rest, exercise, hobbies, etc.\n"
            "3) Offer small, grounded suggestions.\n"
            "   - Break big goals into small steps.\n"
            "   - Suggest short breaks, walks, or simple actions.\n"
            "   - Never give medical advice or diagnoses.\n"
            "4) Finish with a short recap:\n"
            "   - Summarize today's mood and the main 1–3 goals.\n"
            "   - Confirm: 'Does this sound right?'\n"
            "5) Then call the tool `save_wellness_log` EXACTLY ONE TIME per check-in\n"
            "   once you know:\n"
            "   - mood (short text description)\n"
            "   - goals (a list of 1–3 short goals/intentions)\n"
            "   - summary (one sentence summary of the check-in)\n"
            "6) Keep responses short, natural, and conversational.\n"
            "   No emojis, markdown, or special formatting.\n"
        )

        super().__init__(
            instructions=base_instructions + last_entry_context,
        )

    @function_tool
    async def save_wellness_log(
        self,
        context: RunContext,
        mood: str,
        goals: list[str],
        summary: str,
    ) -> str:
        """
        Save today's wellness check-in to a local JSON file named wellness_log.json.

        Only call this tool AFTER you:
        - Asked about mood and energy.
        - Collected 1–3 goals or intentions.
        - Gave a brief recap.

        Parameters:
        - mood: short text describing how the user feels today.
        - goals: list of 1–3 short goals or intentions for today.
        - summary: single-sentence recap of the check-in.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "mood": mood,
            "goals": goals,
            "summary": summary,
        }

        append_wellness_entry(entry)
        return "I have saved today's wellness check-in so we can refer back to it next time."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Voice AI pipeline: Deepgram STT, Gemini LLM, Murf Falcon TTS, turn detector
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

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session with our Health & Wellness Companion
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
