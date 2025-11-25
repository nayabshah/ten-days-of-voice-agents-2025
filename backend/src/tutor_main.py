import json
import logging
from dataclasses import dataclass, field


from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli,RoomInputOptions, Agent, ChatContext,MetricsCollectedEvent,metrics,tokenize,JobProcess,function_tool,Agent, AgentSession, RunContext

from livekit.plugins import murf, deepgram,  silero,noise_cancellation,google


from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agents.orchestrator import Orchestrator
from agents.content_loader import MasteryLoops, MySessionInfo

logger = logging.getLogger("day4-multiagent")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# -------------------------------------------------------
# UserData
# -------------------------------------------------------
@dataclass
class UserData:
    """Stores data and agents to be shared across the session"""
    data=MasteryLoops() 






CONTENT_FILE = "shared-data/day4_tutor_content.json"




async def new_userdata():
    return MySessionInfo(data=MasteryLoops())
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
# -------------------------------------------------------
# ENTRYPOINT
# -------------------------------------------------------
async def entrypoint(ctx: JobContext):

    userdata = await new_userdata()
   
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession[MySessionInfo](
        userdata=userdata,
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-2.5-flash",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="en-US-Ronnie", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
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
        agent=Orchestrator(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint,prewarm_fnc=prewarm))
