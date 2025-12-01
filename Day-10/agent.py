import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    MetricsCollectedEvent,
    WorkerOptions,
    RoomInputOptions,
    tokenize,
    metrics,
    function_tool,
    cli,
)

from livekit.plugins import google, murf, deepgram, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# -----------------------------------------------------------
# IMPROV GAME STATE
# -----------------------------------------------------------
class GamePhase(str, Enum):
    INTRO = "intro"
    AWAITING_IMPROV = "awaiting_improv"
    REACTING = "reacting"
    DONE = "done"

class ImprovState(BaseModel):
    player_name: Optional[str] = None
    current_round: int = 0
    max_rounds: int = 3
    rounds: List[Dict[str, Any]] = []
    phase: GamePhase = GamePhase.INTRO

# -----------------------------------------------------------
# IMPROV SCENARIOS
# -----------------------------------------------------------
IMPROV_SCENARIOS = [
    {
        "id": "barista_portal",
        "scenario": "You are a barista who must calmly explain to a customer that their latte is actually a portal to another dimension."
    },
    {
        "id": "time_travel_guide",
        "scenario": "You are a time-traveling tour guide explaining modern smartphones to someone from the 1800s."
    },
    {
        "id": "escaped_order",
        "scenario": "You are a restaurant waiter who must politely inform a customer that their order has escaped the kitchen and is now loose in the dining room."
    },
    {
        "id": "cursed_return",
        "scenario": "You are a customer trying to return an obviously cursed object to a very skeptical shop owner."
    },
    {
        "id": "alien_job_interview",
        "scenario": "You are a human resources manager interviewing an alien who has never had a job before."
    }
]

# -----------------------------------------------------------
# TOOL ARGUMENTS
# -----------------------------------------------------------
class StartGameArgs(BaseModel):
    player_name: str

class RecordRoundArgs(BaseModel):
    scenario_id: str
    host_reaction: str
    player_performance_notes: str

class EndGameArgs(BaseModel):
    reason: Optional[str] = None

# -----------------------------------------------------------
# IMPROV BATTLE AGENT
# -----------------------------------------------------------
class ImprovBattleAgent(Agent):
    def __init__(self):
        instructions = (
            "You are the host of a TV improv show called 'Improv Battle'.\n\n"
            "PERSONA:\n"
            "- High-energy, witty, and clear about rules.\n"
            "- Reactions are REALISTIC and VARIED: sometimes amused, sometimes unimpressed, sometimes pleasantly surprised.\n"
            "- Not always supportive; light teasing and honest critique are allowed.\n"
            "- Stay respectful, constructive, and non-abusive.\n\n"
            "GAME FLOW:\n"
            "1. Introduce the show and explain the basic rules.\n"
            "2. Run EXACTLY 3 rounds (max_rounds = 3).\n"
            "3. For each round:\n"
            "   - Set a clear scenario from the prepared list.\n"
            "   - Tell the player to start improvising (use 'awaiting_improv' phase).\n"
            "   - When player indicates they're done (pause + 'done', 'end scene', or natural conclusion), give your reaction.\n"
            "   - Reaction should comment on what worked, what was weird, or what fell flat.\n"
            "   - Vary your tone: supportive, neutral, or mildly critical but always constructive.\n"
            "   - After reaction, explicitly move to next round or end show.\n"
            "4. After final round, provide a 2-3 sentence summary of their improv style.\n"
            "5. If player says 'stop game' or 'end show', call end_game() immediately.\n\n"
            "STATE MANAGEMENT:\n"
            "- Call start_game() when you learn the player's name.\n"
            "- Call record_round() after each round with your reaction.\n"
            "- Track current_round and stop after max_rounds.\n"
            "- Call get_next_scenario() to fetch the next scenario.\n"
        )
        super().__init__(instructions=instructions)
        self.state = ImprovState()

    @function_tool
    async def start_game(self, ctx: RunContext, args: StartGameArgs) -> Dict[str, Any]:
        """Initialize the game with player's name."""
        self.state.player_name = args.player_name
        self.state.phase = GamePhase.AWAITING_IMPROV
        return {
            "status": "started",
            "player_name": self.state.player_name,
            "max_rounds": self.state.max_rounds
        }

    @function_tool
    async def get_next_scenario(self, ctx: RunContext) -> Dict[str, Any]:
        """Get the next improv scenario for the current round."""
        if self.state.current_round >= self.state.max_rounds:
            return {"status": "complete", "message": "Game finished"}
        
        scenario = IMPROV_SCENARIOS[self.state.current_round]
        self.state.current_round += 1
        
        return {
            "round": self.state.current_round,
            "scenario": scenario["scenario"],
            "scenario_id": scenario["id"]
        }

    @function_tool
    async def record_round(self, ctx: RunContext, args: RecordRoundArgs) -> Dict[str, Any]:
        """Record a completed round with host reaction."""
        round_data = {
            "round_number": self.state.current_round,
            "scenario_id": args.scenario_id,
            "host_reaction": args.host_reaction,
            "player_performance_notes": args.player_performance_notes,
            "completed_at": datetime.now().isoformat()
        }
        self.state.rounds.append(round_data)
        
        # Check if game is complete
        if self.state.current_round >= self.state.max_rounds:
            self.state.phase = GamePhase.DONE
        
        return {
            "status": "recorded",
            "round": self.state.current_round,
            "game_complete": self.state.phase == GamePhase.DONE
        }

    @function_tool
    async def end_game(self, ctx: RunContext, args: EndGameArgs) -> Dict[str, Any]:
        """End the game early if requested by player."""
        self.state.phase = GamePhase.DONE
        return {
            "status": "ended",
            "reason": args.reason or "Player requested exit",
            "rounds_completed": len(self.state.rounds)
        }

# -----------------------------------------------------------
# LIVEKIT INITIALIZATION
# -----------------------------------------------------------
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Friendly",
            tokenizer=tokenize.basic.SentenceTokenizer(),
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

    await session.start(
        agent=ImprovBattleAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )