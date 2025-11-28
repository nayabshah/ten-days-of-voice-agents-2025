#!/usr/bin/env python3
"""
LiveKit agent with integrated Day-7 Grocery Agent (combined general + grocery tools).

Features:
- Original LiveKit voice pipeline (Deepgram STT, Google LLM, Murf TTS, Multilingual turn detector)
- Assistant remains general-purpose but gains grocery tools:
  - add_item, remove_item, list_cart, show_catalog, ingredients_for, place_order, track_order, history
- Persistence for catalog, recipes, orders stored under ./data/
- Orders saved as JSON files under ./data/orders/
- Simple heuristic in on_message to directly handle common voice commands
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from dotenv import load_dotenv

# LiveKit imports
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

# --- Data paths and sample data ---
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
ORDERS_DIR = DATA_DIR / "orders"
CATALOG_FILE = DATA_DIR / "catalog.json"
RECIPES_FILE = DATA_DIR / "recipes.json"
INDEX_FILE = ORDERS_DIR / "orders_index.json"

SAMPLE_CATALOG = {
    "items": [
        {"name": "Whole Wheat Bread", "category": "Groceries", "price": 45, "brand": "Harvest Gold", "tags": ["bread", "vegan"]},
        {"name": "White Bread", "category": "Groceries", "price": 40, "brand": "Britannia", "tags": ["bread"]},
        {"name": "Eggs - 12 Pack", "category": "Groceries", "price": 75, "tags": ["protein", "breakfast"]},
        {"name": "Milk - 1L", "category": "Groceries", "price": 62, "brand": "Amul", "tags": ["dairy"]},
        {"name": "Peanut Butter - 500g", "category": "Groceries", "price": 199, "brand": "Pintola", "tags": ["vegan", "spread"]},
        {"name": "Pasta - 500g", "category": "Groceries", "price": 120, "brand": "Barilla", "tags": ["pasta"]},
        {"name": "Tomato Pasta Sauce", "category": "Groceries", "price": 149, "brand": "Del Monte", "tags": ["sauce"]},
        {"name": "Onion - 1kg", "category": "Groceries", "price": 40, "tags": ["vegetable"]},
        {"name": "Tomato - 1kg", "category": "Groceries", "price": 50, "tags": ["vegetable"]},
        {"name": "Bananas - 6 pcs", "category": "Groceries", "price": 45, "tags": ["fruit"]},
        {"name": "Potato Chips", "category": "Snacks", "price": 35, "brand": "Lays"},
        {"name": "Chocolate Bar", "category": "Snacks", "price": 60, "brand": "Cadbury"},
        {"name": "Veg Sandwich", "category": "Prepared Food", "price": 70},
        {"name": "Chicken Sandwich", "category": "Prepared Food", "price": 85},
        {"name": "Margherita Pizza", "category": "Prepared Food", "price": 199},
        {"name": "Cold Coffee", "category": "Drinks", "price": 99},
        {"name": "Apple Juice", "category": "Drinks", "price": 120},
        {"name": "Noodles - 2 Pack", "category": "Snacks", "price": 30},
    ]
}

SAMPLE_RECIPES = {
    "peanut butter sandwich": ["Whole Wheat Bread", "Peanut Butter - 500g"],
    "pasta for two": ["Pasta - 500g", "Tomato Pasta Sauce"],
    "simple salad": ["Tomato - 1kg", "Onion - 1kg"],
    "breakfast pack": ["Milk - 1L", "Eggs - 12 Pack", "Bananas - 6 pcs"]
}


# --- Grocery backend logic (reused by tools) ---
class GroceryBackend:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ORDERS_DIR.mkdir(parents=True, exist_ok=True)
        self.catalog = self._ensure_and_load(CATALOG_FILE, SAMPLE_CATALOG)
        self.recipes = self._ensure_and_load(RECIPES_FILE, SAMPLE_RECIPES)
        self.orders_index = self._load_index()
        # cart keyed by normalized item name -> {name, qty, unit_price}
        self.cart: Dict[str, Dict[str, Any]] = {}

    def _ensure_and_load(self, path: Path, sample: Dict) -> Dict:
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sample, f, indent=2)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_index(self) -> List[Dict[str, Any]]:
        if not INDEX_FILE.exists():
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            return []
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []

    # Catalog lookup
    def find_item(self, query: str) -> Optional[Dict[str, Any]]:
        q = query.strip().lower()
        for it in self.catalog.get("items", []):
            if it["name"].strip().lower() == q:
                return it
        candidates = [it for it in self.catalog.get("items", []) if q in it["name"].strip().lower()]
        if candidates:
            return candidates[0]
        for it in self.catalog.get("items", []):
            tags = [t.lower() for t in it.get("tags", [])]
            if q in tags:
                return it
        return None

    def list_catalog(self) -> List[str]:
        out = []
        for it in self.catalog.get("items", []):
            line = f"{it['name']} — ₹{it['price']} ({it.get('category','')})"
            if it.get("brand"):
                line += f" — {it['brand']}"
            out.append(line)
        return out

    # Cart operations
    def add_item(self, name_or_query: str, quantity: int = 1) -> Tuple[bool, str]:
        item = self.find_item(name_or_query)
        if not item:
            return False, f"Item '{name_or_query}' not found in catalog."
        key = item["name"].lower()
        if key in self.cart:
            self.cart[key]["qty"] += quantity
        else:
            self.cart[key] = {"name": item["name"], "qty": quantity, "unit_price": item["price"]}
        return True, f"Added {quantity} x {item['name']} to your cart."

    def remove_item(self, name_or_query: str) -> Tuple[bool, str]:
        item = self.find_item(name_or_query)
        if not item:
            return False, f"Item '{name_or_query}' not found in catalog."
        key = item["name"].lower()
        if key in self.cart:
            del self.cart[key]
            return True, f"Removed {item['name']} from your cart."
        return False, f"{item['name']} is not in your cart."

    def update_quantity(self, name_or_query: str, quantity: int) -> Tuple[bool, str]:
        item = self.find_item(name_or_query)
        if not item:
            return False, f"Item '{name_or_query}' not found in catalog."
        key = item["name"].lower()
        if quantity <= 0:
            return self.remove_item(item["name"])
        if key in self.cart:
            self.cart[key]["qty"] = quantity
            return True, f"Updated {item['name']} quantity to {quantity}."
        else:
            self.cart[key] = {"name": item["name"], "qty": quantity, "unit_price": item["price"]}
            return True, f"Added {quantity} x {item['name']} to your cart."

    def show_cart(self) -> str:
        if not self.cart:
            return "Your cart is empty."
        lines = []
        total = 0
        for ent in self.cart.values():
            lines.append(f"{ent['qty']} × {ent['name']} — ₹{ent['qty'] * ent['unit_price']}")
            total += ent["qty"] * ent["unit_price"]
        lines.append(f"Total: ₹{total}")
        return " ; ".join(lines)

    def ingredients_for(self, recipe_name: str) -> Tuple[bool, str]:
        rkey = recipe_name.strip().lower()
        mapped = None
        for k in self.recipes.keys():
            if k.strip().lower() == rkey:
                mapped = self.recipes[k]
                break
        if not mapped:
            for k in self.recipes.keys():
                if rkey in k.strip().lower():
                    mapped = self.recipes[k]
                    break
        if not mapped:
            return False, f"No recipe found for '{recipe_name}'."
        added = []
        for item_name in mapped:
            found = self.find_item(item_name)
            if found:
                key = found["name"].lower()
                if key in self.cart:
                    self.cart[key]["qty"] += 1
                else:
                    self.cart[key] = {"name": found["name"], "qty": 1, "unit_price": found["price"]}
                added.append(found["name"])
        if not added:
            return False, "Could not add any items for that recipe (items not in catalog)."
        return True, f"I've added {', '.join(added)} to your cart for '{recipe_name}'."

    # Orders
    def cart_total(self) -> int:
        return sum(ent["qty"] * ent["unit_price"] for ent in self.cart.values())

    def place_order(self, customer_info: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        if not self.cart:
            return False, "Your cart is empty — nothing to place."
        now = datetime.now(timezone.utc)
        order_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
        order = {
            "orderId": order_id,
            "timestamp": now.isoformat(),
            "items": [
                {"name": ent["name"], "qty": ent["qty"], "unit_price": ent["unit_price"], "line_total": ent["qty"] * ent["unit_price"]}
                for ent in self.cart.values()
            ],
            "total": self.cart_total(),
            "status": "Preparing",
            "customer": customer_info or {}
        }
        filename = ORDERS_DIR / f"order_{order_id}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(order, f, indent=2)
        self.orders_index.append({"orderId": order_id, "timestamp": now.isoformat(), "file": str(filename)})
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self.orders_index, f, indent=2)
        self.cart = {}
        return True, f"Order placed! Your order id is {order_id}."

    def list_history(self) -> List[Dict[str, Any]]:
        return list(self.orders_index)

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.orders_index:
            if entry["orderId"] == order_id:
                try:
                    with open(entry["file"], "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return None
        return None

    def compute_status(self, order: Dict[str, Any]) -> str:
        try:
            t = datetime.fromisoformat(order["timestamp"])
        except Exception:
            return order.get("status", "Preparing")
        elapsed = (datetime.now(timezone.utc) - t).total_seconds()
        if elapsed < 60:
            return "Preparing"
        if elapsed < 180:
            return "Out for delivery"
        if elapsed < 300:
            return "Arriving Soon"
        return "Delivered"

    def track_order(self, order_id: str) -> Tuple[bool, str]:
        order = self.get_order(order_id)
        if not order:
            return False, f"Order {order_id} not found."
        status = self.compute_status(order)
        order["status"] = status
        # Save status
        for entry in self.orders_index:
            if entry["orderId"] == order_id:
                try:
                    with open(entry["file"], "w", encoding="utf-8") as f:
                        json.dump(order, f, indent=2)
                except Exception:
                    pass
                break
        return True, f"Order {order_id} status: {status}"

    def clear_cart(self):
        self.cart = {}

# --- Assistant class with function tools for grocery operations ---
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a helpful voice AI assistant. The user is interacting with you via voice.
You can answer general questions, and you also provide GroceryBuddy features when asked.
Be concise, friendly, and voice-friendly. Do not use emojis or strange formatting.
"""
        )
        # Backend that stores catalog, recipes, cart, orders
        self.backend = GroceryBackend()

    # -----------------------
    # Grocery function tools
    # -----------------------

    @function_tool
    async def add_item(self, ctx: RunContext, item: str, quantity: int = 1):
        """Add a grocery item to the cart.
        Args:
            item: Item name or search query (voice)
            quantity: integer quantity (default 1)
        """
        ok, msg = self.backend.add_item(item, quantity)
        logger.info(f"add_item: {item=} {quantity=} -> {ok}")
        return msg

    @function_tool
    async def remove_item(self, ctx: RunContext, item: str):
        """Remove item from cart."""
        ok, msg = self.backend.remove_item(item)
        logger.info(f"remove_item: {item=} -> {ok}")
        return msg

    @function_tool
    async def update_quantity(self, ctx: RunContext, item: str, quantity: int):
        """Update quantity for an item in the cart."""
        ok, msg = self.backend.update_quantity(item, quantity)
        logger.info(f"update_quantity: {item=} {quantity=} -> {ok}")
        return msg

    @function_tool
    async def list_cart(self, ctx: RunContext):
        """List current cart/groceries in a voice-friendly form."""
        summary = self.backend.show_cart()
        logger.info("list_cart called")
        return summary

    @function_tool
    async def show_catalog(self, ctx: RunContext):
        """Return short catalog listing (voice-friendly)."""
        items = self.backend.list_catalog()
        # For voice, send a compact string
        spoken = "; ".join(items[:30])
        logger.info("show_catalog called")
        return f"Catalog items: {spoken}"

    @function_tool
    async def ingredients_for(self, ctx: RunContext, recipe_name: str):
        """Add ingredients for a named recipe to the cart."""
        ok, msg = self.backend.ingredients_for(recipe_name)
        logger.info(f"ingredients_for: {recipe_name=} -> {ok}")
        return msg

    @function_tool
    async def place_order(self, ctx: RunContext, name: Optional[str] = None, address: Optional[str] = None):
        """Place the current cart as an order."""
        customer = {}
        if name:
            customer["name"] = name
        if address:
            customer["address"] = address
        ok, msg = self.backend.place_order(customer_info=customer)
        logger.info(f"place_order -> {ok}")
        return msg

    @function_tool
    async def history(self, ctx: RunContext):
        """List previous orders' ids and timestamps."""
        hist = self.backend.list_history()
        if not hist:
            return "No previous orders found."
        lines = [f"{e['orderId']} at {e['timestamp']}" for e in hist]
        return " ; ".join(lines)

    @function_tool
    async def track_order(self, ctx: RunContext, order_id: str):
        """Track an existing order id."""
        ok, msg = self.backend.track_order(order_id)
        logger.info(f"track_order: {order_id=} -> {ok}")
        return msg
    
    @function_tool
    async def clear_grocery_list(self, context: RunContext):
        """Clears the entire grocery list."""
        self.backend.clear_cart()
        return "Your grocery list has been cleared."

    # -----------------------
    # Heuristic on_message to help with direct voice commands
    # -----------------------
    async def on_message(self, msg, ctx: RunContext):
        """Simple heuristics: if user says 'add milk' or 'remove eggs' call the tools directly.
        Return the tool result string to have the agent respond immediately, otherwise return None to let the LLM handle it.
        """
        text = (msg.text or "").strip().lower()
        if not text:
            return None

        # Common patterns: add <qty?> <item>, remove <item>, list cart, show catalog, place order, track <id>, ingredients for <recipe>
        if text.startswith("add "):
            tokens = text.split()
            # e.g., "add 2 milk" or "add milk"
            if len(tokens) >= 3 and tokens[1].isdigit():
                qty = int(tokens[1])
                item = " ".join(tokens[2:])
                return await self.add_item(ctx, item=item, quantity=qty)
            else:
                item = " ".join(tokens[1:])
                return await self.add_item(ctx, item=item, quantity=1)

        if text.startswith("remove "):
            item = text[len("remove "):].strip()
            return await self.remove_item(ctx, item=item)

        if "list cart" in text or "what's in my cart" in text or "what is in my cart" in text or text == "show cart":
            return await self.list_cart(ctx)

        if "catalog" in text or "list items" in text or text.startswith("show catalog"):
            return await self.show_catalog(ctx)

        if text.startswith("ingredients for"):
            recipe = text[len("ingredients for"):].strip()
            if recipe:
                return await self.ingredients_for(ctx, recipe_name=recipe)

        if text.startswith("place order") or text in ("i'm done", "im done", "place my order", "that's all", "thats all"):
            # We can't reliably ask follow-ups in this heuristic; let the LLM ask for name/address if needed.
            return await self.place_order(ctx)

        if text.startswith("track ") or text.startswith("where is my order"):
            # "track <orderid>" or "where is my order <id>"
            tokens = text.split()
            if len(tokens) >= 2:
                # last token assumed to be id
                order_id = tokens[-1]
                return await self.track_order(ctx, order_id=order_id)

        # if none matched, return None to let the LLM handle general conversation
        return None


# --- prewarm & entrypoint and pipeline setup (mostly unchanged) ---
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.0-flash"),
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
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    # Optional: basic logging config
    logging.basicConfig(level=logging.INFO)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
