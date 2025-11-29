import logging
import json
import os
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
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

with open("travel_faq.json") as f:
    FAQ = json.load(f)

QUESTIONS = [
    ("name", "Great! May I know your name?"),
    ("email", "Nice to meet you! What's your email?"),
    ("destination", "Where would you like to travel?"),
    ("dates", "When are you planning to travel?"),
    ("travelers", "How many travelers will be going?"),
    ("budget", "Do you have a rough budget in mind?"),
    ("purpose", "What's the purpose of your trip? Holiday, business, honeymoon?")
]


class TravelSDR(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
You are a friendly Travel Agency Assistant for Explore Travels.

Goals:
- Greet warmly
- Understand the user's travel plan
- Answer travel questions ONLY using provided FAQ
- Collect lead details naturally
- Ask ONLY ONE question at a time
- Keep responses short
- Never ask multiple questions
- Never invent information

When user says "done", "thanks", "that's all":
- Give a short summary
- Save lead to travel_lead.json
- Say goodbye
"""
        )

    async def on_start(self, ctx: JobContext):
        ctx.proc.userdata["lead"] = {k: None for k, _ in QUESTIONS}
        await ctx.say("Hello! Welcome to Explore Travels. How can I assist you today?")

    async def on_message(self, ctx: JobContext, message: str):
        text = message.lower().strip()
        lead = ctx.proc.userdata["lead"]

        # END DETECTION
        if text in ["done", "thanks", "thank you", "that's all", "bye", "stop"]:
            summary = (
                f"Thank you! Here's what I have:\n"
                f"- Name: {lead.get('name')}\n"
                f"- Destination: {lead.get('destination')}\n"
                f"- Dates: {lead.get('dates')}\n"
                f"- Travelers: {lead.get('travelers')}\n"
                f"- Budget: {lead.get('budget')}\n"
                f"- Purpose: {lead.get('purpose')}"
            )

            await ctx.say(summary)

            path = os.path.join(os.getcwd(), "travel_lead.json")
            with open(path, "w") as f:
                json.dump(lead, f, indent=2)

            print("✅ Lead saved at:", path)
            await ctx.say("We'll contact you soon. Have a great day!")
            return

        # FAQ MATCHING
        for item in FAQ["faq"]:
            if item["q"].lower() in text:
                await ctx.say(item["a"])
                return

        # STORE ANSWER
        for key, question in QUESTIONS:
            if lead[key] is None:
                lead[key] = message.strip()
                break

        # ASK NEXT
        for key, question in QUESTIONS:
            if lead[key] is None:
                await ctx.say(question)
                return

        await ctx.say("Great, tell me more!")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=TravelSDR(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
