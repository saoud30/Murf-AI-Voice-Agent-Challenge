import logging
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
    tokenize
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel


logger = logging.getLogger("agent")
load_dotenv(".env.local")


# -----------------------------------------------------
# Game Master Agent (Day 8 — Primary Goal Version)
# -----------------------------------------------------
class GameMasterAgent(Agent):
    def __init__(self):
        # This prompt alone handles the entire Day-8 primary goal
        instructions = (
            "You are a Game Master running a voice-only interactive fantasy adventure.\n"
            "Tone: dramatic, immersive, descriptive.\n"
            "Universe: classic medieval fantasy—dragons, magic, ancient ruins, dark forests.\n\n"

            "RULES:\n"
            "1. You ALWAYS describe the current scene in vivid detail.\n"
            "2. You ALWAYS end every message with: 'What do you do?'\n"
            "3. You maintain continuity ONLY using chat history.\n"
            "4. You remember:\n"
            "   - the player's decisions\n"
            "   - world events you previously described\n"
            "   - named characters and locations\n"
            "5. You NEVER rush the story. Let it unfold slowly.\n"
            "6. Do NOT reveal that you are an AI model.\n"
            "7. Keep responses short enough to be spoken aloud.\n\n"

            "SESSION START:\n"
            "Begin the adventure immediately when the session starts. Introduce the player as waking up at the edge of an ancient forest as a mysterious force stirs in the distance.\n"
            "Then ask: 'What do you do?'"
        )
        super().__init__(instructions=instructions)


# -----------------------------------------------------
# LiveKit Agent Entry
# -----------------------------------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Narration",
            tokenizer=tokenize.basic.SentenceTokenizer(),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on(ev: MetricsCollectedEvent):
        usage.collect(ev.metrics)

    async def log_usage():
        logger.info(usage.get_summary())

    ctx.add_shutdown_callback(log_usage)

    # Start Game Master Agent
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm)
    )
