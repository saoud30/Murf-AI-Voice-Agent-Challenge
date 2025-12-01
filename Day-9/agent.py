import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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
# FILE PATHS
# -----------------------------------------------------------
CATALOG_PATH = Path("../shared-data/day9_catalog.json")
ORDERS_PATH = Path("day9_orders.json")

# -----------------------------------------------------------
# LOAD/SAVE HELPERS
# -----------------------------------------------------------
def load_catalog() -> List[Dict[str, Any]]:
    try:
        with CATALOG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Could not load catalog")
        return []


def load_orders() -> List[Dict[str, Any]]:
    if not ORDERS_PATH.exists():
        return []
    try:
        with ORDERS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_orders(orders: List[Dict[str, Any]]):
    with ORDERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


CATALOG = load_catalog()

# -----------------------------------------------------------
# PRODUCT FILTERS
# -----------------------------------------------------------
def filter_products(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = CATALOG

    if "category" in filters:
        results = [p for p in results if p["category"].lower() == filters["category"].lower()]

    if "max_price" in filters:
        results = [p for p in results if p["price"] <= filters["max_price"]]

    if "color" in filters:
        results = [p for p in results if p["color"].lower() == filters["color"].lower()]

    if "keyword" in filters:
        kw = filters["keyword"].lower()
        results = [
            p for p in results
            if (kw in p["name"].lower() or kw in p["description"].lower())
        ]

    return results


# -----------------------------------------------------------
# Pydantic Schemas for Tools
# -----------------------------------------------------------
class ListProductsArgs(BaseModel):
    category: Optional[str] = None
    max_price: Optional[int] = None
    color: Optional[str] = None
    keyword: Optional[str] = None


class CreateOrderArgs(BaseModel):
    product_id: str
    quantity: int = 1


# -----------------------------------------------------------
# SHOPPING AGENT (ACP-Style)
# -----------------------------------------------------------
class ShoppingAgent(Agent):

    def __init__(self):
        instructions = (
            "You are a voice-based shopping assistant inspired by the Agentic Commerce Protocol.\n"
            "Rules:\n"
            "- NEVER invent products. ALWAYS call list_products first.\n"
            "- Understand user intent from speech.\n"
            "- Use list_products() to browse catalog.\n"
            "- When user decides to buy something, call create_order().\n"
            "- When user asks what they bought, call get_last_order().\n"
            "- Be conversational and concise. No emojis.\n"
        )
        super().__init__(instructions=instructions)

    # -------------------------------------------------------
    # TOOL 1 — list_products (patched with Pydantic args)
    # -------------------------------------------------------
    @function_tool
    async def list_products(
        self,
        ctx: RunContext,
        args: ListProductsArgs
    ) -> List[Dict[str, Any]]:
        filters = {}

        if args.category:
            filters["category"] = args.category

        if args.max_price is not None:
            filters["max_price"] = args.max_price

        if args.color:
            filters["color"] = args.color

        if args.keyword:
            filters["keyword"] = args.keyword

        return filter_products(filters)

    # -------------------------------------------------------
    # TOOL 2 — create_order
    # -------------------------------------------------------
    @function_tool
    async def create_order(
        self,
        ctx: RunContext,
        args: CreateOrderArgs
    ) -> Dict[str, Any]:

        orders = load_orders()
        product = next((p for p in CATALOG if p["id"] == args.product_id), None)

        if not product:
            return {"error": "Invalid product_id"}

        total = product["price"] * args.quantity

        order_obj = {
            "id": f"ORD-{len(orders) + 1}",
            "created_at": datetime.now().isoformat(),
            "items": [
                {
                    "product_id": args.product_id,
                    "name": product["name"],
                    "quantity": args.quantity,
                    "unit_price": product["price"],
                    "currency": product["currency"],
                    "subtotal": total
                }
            ],
            "total": total,
            "currency": product["currency"]
        }

        orders.append(order_obj)
        save_orders(orders)
        return order_obj

    # -------------------------------------------------------
    # TOOL 3 — get_last_order
    # -------------------------------------------------------
    @function_tool
    async def get_last_order(self, ctx: RunContext) -> Dict[str, Any]:
        orders = load_orders()
        if not orders:
            return {"message": "No orders yet."}
        return orders[-1]


# -----------------------------------------------------------
# LIVEKIT INITIALIZATION (patched)
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
        agent=ShoppingAgent(),
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
