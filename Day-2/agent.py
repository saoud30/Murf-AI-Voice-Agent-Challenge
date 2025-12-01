import logging
import json
from pathlib import Path

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


class Assistant(Agent):
    def __init__(self) -> None:
        # Persona + behavior instructions for Day 2
        super().__init__(
            instructions=(
                "You are a friendly coffee shop barista for a modern specialty coffee brand called Falcon Brew.\n"
                "The user is talking to you via voice. Keep your replies short, natural and conversational.\n"
                "Your primary job is to take a coffee order and fill this order object:\n"
                "{\n"
                '  \"drinkType\": \"string\",\n'
                '  \"size\": \"string\",\n'
                '  \"milk\": \"string\",\n'
                '  \"extras\": [\"string\"],\n'
                '  \"name\": \"string\"\n'
                "}\n"
                "Behavior rules:\n"
                "1. Ask clarifying questions until ALL fields are known.\n"
                "   - drinkType: e.g. latte, cappuccino, americano, mocha, cold brew.\n"
                "   - size: e.g. small, medium, large.\n"
                "   - milk: e.g. whole, skim, oat, almond, soy.\n"
                "   - extras: comma-separated list (whipped cream, caramel, extra shot, vanilla, etc.). "
                "      If the user wants no extras, set an empty list.\n"
                "   - name: the name to write on the cup.\n"
                "2. Confirm each choice briefly as you go.\n"
                "3. Once the order is fully known, call the tool `save_order` EXACTLY ONE TIME with the final values.\n"
                "4. AFTER the tool responds, clearly confirm the full order and tell the user it has been saved.\n"
                "5. Do NOT call `save_order` before all fields are filled.\n"
                "6. Do not use emojis, markdown, asterisks or special formatting in your replies.\n"
            ),
        )

    @function_tool
    async def save_order(
        self,
        context: RunContext,
        drinkType: str,
        size: str,
        milk: str,
        extras: list[str],
        name: str,
    ) -> str:
        """
        Save the finalized coffee order to a local JSON file named coffee_order.json.

        Only call this tool AFTER you know all fields:
        - drinkType
        - size
        - milk
        - extras (can be empty list)
        - name
        """
        order = {
            "drinkType": drinkType,
            "size": size,
            "milk": milk,
            "extras": extras,
            "name": name,
        }

        # Save coffee_order.json in the working directory (backend/)
        save_path = Path("coffee_order.json")
        try:
            with save_path.open("w", encoding="utf-8") as f:
                json.dump(order, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved coffee order to {save_path.resolve()}: {order}")
            return "The order has been saved to the system."
        except Exception as e:
            logger.exception("Failed to save coffee order")
            return (
                "I had an issue saving the order. "
                "Please tell the human operator that there was an error writing the order file."
            )


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

    # Start the session with our barista Assistant
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
