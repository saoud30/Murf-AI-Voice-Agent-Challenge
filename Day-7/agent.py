import logging
import json
from pathlib import Path
from datetime import datetime
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
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

CATALOG_PATH = Path("../shared-data/day7_catalog.json")
RECIPES_PATH = Path("../shared-data/day7_recipe_map.json")
ORDER_SAVE_PATH = Path("day7_order.json")

# -----------------------------
# Helpers: load JSON files
# -----------------------------
def load_catalog() -> List[Dict[str, Any]]:
    try:
        with CATALOG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except:
        logger.exception("Catalog load failed")
        return []


def load_recipes() -> Dict[str, List[str]]:
    try:
        with RECIPES_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except:
        logger.exception("Recipe map load failed")
        return {}


CATALOG = load_catalog()
RECIPES = load_recipes()


# Simple keyword-based search in catalog
def search_catalog(query: str):
    q = query.lower()
    matches = []

    for item in CATALOG:
        if q in item["name"].lower() or any(q in tag for tag in item["tags"]):
            matches.append(item)

    return matches


# -----------------------------
# Ordering Agent
# -----------------------------
class GroceryOrderingAgent(Agent):
    def __init__(self):
        instructions = (
            "You are a friendly grocery and food ordering assistant for a fictional service called QuickCart.\n"
            "You help users order groceries, snacks and simple prepared meals.\n\n"
            "You can:\n"
            "- Add items to a cart\n"
            "- Update and remove items\n"
            "- Show the cart\n"
            "- Add multiple ingredients for recipes (like 'ingredients for pasta for two')\n\n"
            "CART RULES:\n"
            "- Always confirm after adding or removing items.\n"
            "- If user asks for ingredients for a dish, use the recipe tool.\n"
            "- When the user is done ('place order', 'that's all'), call save_order EXACTLY ONCE.\n"
            "- No emojis or markdown.\n"
        )
        super().__init__(instructions=instructions)
        self.cart: Dict[str, int] = {}  # item_id -> quantity


    # ------------------------------------------
    # TOOL 1 – Add Item to Cart
    # ------------------------------------------
    @function_tool
    async def add_item(self, ctx: RunContext, item_id: str, quantity: int) -> str:
        if item_id not in [i["id"] for i in CATALOG]:
            return "I could not find that item."

        self.cart[item_id] = self.cart.get(item_id, 0) + quantity
        item = next(i for i in CATALOG if i["id"] == item_id)
        return f"Added {quantity} of {item['name']} to your cart."


    # ------------------------------------------
    # TOOL 2 – Remove Item
    # ------------------------------------------
    @function_tool
    async def remove_item(self, ctx: RunContext, item_id: str) -> str:
        if item_id in self.cart:
            del self.cart[item_id]
            return "I removed that item from your cart."
        return "That item is not in your cart."


    # ------------------------------------------
    # TOOL 3 – Add recipe ingredients
    # ------------------------------------------
    @function_tool
    async def add_recipe(self, ctx: RunContext, recipe_name: str) -> str:
        recipe_name_l = recipe_name.lower()
        matched_recipe = None

        for name in RECIPES:
            if recipe_name_l in name:
                matched_recipe = name
                break

        if not matched_recipe:
            return "I do not have a recipe for that."

        added_items = []
        for item_id in RECIPES[matched_recipe]:
            self.cart[item_id] = self.cart.get(item_id, 0) + 1
            item = next(i for i in CATALOG if i["id"] == item_id)
            added_items.append(item["name"])

        return f"I have added {', '.join(added_items)} for {matched_recipe}."


    # ------------------------------------------
    # TOOL 4 – Show Cart
    # ------------------------------------------
    @function_tool
    async def show_cart(self, ctx: RunContext) -> str:
        if not self.cart:
            return "Your cart is empty."

        text = "Your cart currently has: "
        parts = []

        for item_id, quantity in self.cart.items():
            item = next(i for i in CATALOG if i["id"] == item_id)
            parts.append(f"{quantity} x {item['name']}")

        return text + ", ".join(parts)


    # ------------------------------------------
    # TOOL 5 – Save Order
    # ------------------------------------------
    @function_tool
    async def save_order(self, ctx: RunContext, user_name: str) -> str:
        if not self.cart:
            return "Your cart is empty. Nothing to save."

        order_items = []
        total = 0

        for item_id, quantity in self.cart.items():
            item = next(i for i in CATALOG if i["id"] == item_id)
            subtotal = item["price"] * quantity
            total += subtotal

            order_items.append({
                "item_id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "unit_price": item["price"],
                "subtotal": subtotal
            })

        order = {
            "customer_name": user_name,
            "timestamp": datetime.now().isoformat(),
            "items": order_items,
            "total": total
        }

        with ORDER_SAVE_PATH.open("w", encoding="utf-8") as f:
            json.dump(order, f, indent=2)

        return f"Your order has been placed. Total is {total}."


# -----------------------------
# LiveKit plumbing
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
            style="Friendly",
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

    # Start Grocery Agent
    await session.start(
        agent=GroceryOrderingAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
