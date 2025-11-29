import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Annotated

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from pydantic import Field

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    MetricsCollectedEvent,
     RoomInputOptions,
     metrics,
     JobProcess,
    JobContext,
    RunContext,
    cli,
    function_tool,
    tokenize,
)
from livekit.plugins import  deepgram, google, murf,silero,noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# load_dotenv()
load_dotenv(".env.local")
logger = logging.getLogger("barista")

# ------------------------------------------------------------
# ORDER STATE
# ------------------------------------------------------------

@dataclass
class OrderState:
    drinkType: str | None = None
    size: str | None = None
    milk: str | None = None
    extras: list[str] = field(default_factory=list)
    name: str | None = None

    def is_complete(self):
        return all([
            self.drinkType,
            self.size,
            self.milk,
            self.name,
        ])

# ------------------------------------------------------------
# USERDATA (stored for each session)
# ------------------------------------------------------------

@dataclass
class Userdata:
    order: OrderState

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
# ------------------------------------------------------------
# BARISTA AGENT
# ------------------------------------------------------------

class BaristaAgent(Agent):
    def __init__(self):
        instructions = """
You are **Ethan**, a warm, friendly, and attentive barista at **Moonbeam Coffee**.

At the beginning of every session, ALWAYS introduce yourself naturally:
“Hey there! Welcome to Moonbeam Coffee. I’m Ethan, your barista today. What can I get started for you?”

Your single goal is to take a complete and accurate coffee order.

An order MUST include the following fields:
- drinkType  (latte, cappuccino, americano, espresso, mocha, etc.)
- size        (small, medium, large)
- milk        (whole, oat, soy, almond)
- extras      (optional list: sugar, syrup flavors, whipped cream, extra shots, etc.)
- name        (customer’s name)

### Conversational Behavior

- Ask **one and only one** clarifying question at a time.
- Keep responses short, friendly, and conversational—like a real barista talking to a customer.
- When the user gives ANY detail, you should:
  - update the order,
  - restate what’s filled,
  - and ask about the next missing detail.
- If the user gives multiple details at once (example: “A medium oat latte, no sugar”), extract everything they gave.
- If multiple fields are still missing, ask about them **one at a time** in a natural order:
  1. drinkType  
  2. size  
  3. milk  
  4. extras  
  5. name  

### Important Rules

- **Never call the `finalize_order` tool until ALL required fields are complete.**
- **Never assume missing details. Always ask.**
- If something is unclear or contradictory, politely confirm again.
- Maintain a positive, easygoing tone—light jokes and barista-like enthusiasm are fine.
- Keep the ordering experience smooth and welcoming.

### When the order is complete:

Once drinkType, size, milk, name, and (optional) extras are known:
- Confirm the full order in a single friendly sentence.
- Then call the `finalize_order` tool with the fully assembled order dictionary.
"""

        super().__init__(
            instructions=instructions,
            #tools=[self.finalize_order],
        )

    async def stream_order_update(self, ctx: RunContext[Userdata]):
        """Send incremental state to React via text stream."""
        if not ctx.room:
            return

        writer = await ctx.room.local_participant.stream_text(
            topic="order_update"
        )
        await writer.write(json.dumps({
            "order": ctx.userdata.order.__dict__
        }).encode("utf-8"))
        await writer.close()
    # -------------------- FINALIZE ORDER --------------------

    @function_tool
    async def finalize_order(
        self,
        ctx: RunContext[Userdata],
        order: Annotated[
            dict,
            Field(description="The completed order object that will be saved to JSON."),
        ],
    ) -> str:
        """
        Save the final coffee order to a JSON file.
        Called ONLY after all order fields are complete.
        """

        filename = f"order_{order['name'].lower()}.json"
        path = os.path.join(os.getcwd(), filename)

        with open(path, "w") as f:
            json.dump(order, f, indent=2)
         # send final order via text stream
        if ctx.room:
            writer = await ctx.room.local_participant.stream_text(
                topic="final_order"
            )
            await writer.write(json.dumps({
                "final_order": order
            }).encode("utf-8"))
            await writer.close()

        return f"Your order is complete, {order['name']}! I’ve saved it as {filename}."

# ------------------------------------------------------------
# CREATE NEW USERDATA
# ------------------------------------------------------------

async def new_userdata():
    return Userdata(order=OrderState())

# ------------------------------------------------------------
# SERVER + LIVEKIT AGENT SESSION
# ------------------------------------------------------------

server = AgentServer()

async def on_session_end(ctx: JobContext):
    report = ctx.make_session_report()
    _ = json.dumps(report.to_dict(), indent=2)

@server.rtc_session(on_session_end=on_session_end)
async def barista_agent(ctx: JobContext):
    userdata = await new_userdata()

    session = AgentSession[Userdata](
        userdata=userdata,
        stt=deepgram.STT(model="nova-3"),
       llm=google.LLM(
                model="gemini-2.5-flash",
            ),
         tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        max_tool_steps=5,
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
        agent=BaristaAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(server)