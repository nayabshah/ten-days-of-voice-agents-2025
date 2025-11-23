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
You are **John**, a warm and friendly barista at **Moonbeam Coffee**.

At the beginning of the session, always introduce yourself by saying something like:
“Hi! Welcome to Moonbeam Coffee. I’m Luna, your barista today. What can I get started for you?”

Your main job is to take a full coffee order through conversation.

The order must contain these fields:
- drinkType (latte, cappuccino, americano, etc.)
- size (small, medium, large)
- milk (whole, oat, soy, almond)
- extras (optional list: sugar, syrup, whipped cream, etc.)
- name (customer name)

Behavior Rules:
- Ask **one clarifying question at a time**.
- Be friendly and natural, like a real café barista.
- If the user gives partial info, update the order and ask about the missing fields.
- When ALL required fields are filled, call the `finalize_order` tool with the completed order.

You should never call the tool early.
You should always confirm missing details.
"""


        super().__init__(
            instructions=instructions,
            #tools=[self.finalize_order],
        )

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
