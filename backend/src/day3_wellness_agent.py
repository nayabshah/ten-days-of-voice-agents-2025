"""
Improved Day-3: Health & Wellness Voice Companion ("Ken")

Enhancements:
- Stronger grounding + anti-medicalization constraints
- Smarter warm-start referencing last check-in
- Required-field enforcement (mood + ≥1 objective)
- More stable JSON read/write handling
- Consistent check-in record schema
- Improved streaming format for UI
- Better tool instructions for LLM compliance

Modified: agent now streams a brief goodbye and attempts to end the call after saving a check-in.
"""
import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Annotated

from dotenv import load_dotenv
load_dotenv(".env.local")

from pydantic import Field

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    RoomInputOptions,
    function_tool,
    metrics,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("wellness")
logger.setLevel(logging.INFO)

LOG_FILENAME = "wellness_log.json"


# ------------------------------------------------------
#   Data Models
# ------------------------------------------------------
@dataclass
class CheckIn:
    timestamp: str
    mood: str
    energy: Optional[str] = None
    objectives: list[str] = field(default_factory=list)
    agent_summary: Optional[str] = None


@dataclass
class Userdata:
    current: Optional[CheckIn] = None
    history: list[CheckIn] = field(default_factory=list)


# ------------------------------------------------------
#   JSON Persistence Utils
# ------------------------------------------------------
def read_history() -> list[dict]:
    """Safely read history; auto-correct corrupted files."""
    if not os.path.exists(LOG_FILENAME):
        return []

    try:
        with open(LOG_FILENAME, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        logger.warning(f"Invalid JSON in {LOG_FILENAME} — resetting file: {e}")
        return []


def append_history(entry: dict) -> None:
    """Append safely with overwrite protection."""
    try:
        existing = read_history()
        existing.append(entry)

        with open(LOG_FILENAME, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Failed to write history file: {e}")


# ------------------------------------------------------
#   Agent
# ------------------------------------------------------
class WellnessAgent(Agent):
    def __init__(self):
        instructions = """
You are a supportive, upbeat, **non-clinical wellness companion** named **Ken**.
You are NOT a political figure, NOT a public persona — just a friendly digital
character who happens to have this name.

--- SESSION OPENING ---

At the start of every new session, you MUST say a short, clear,
voice-friendly introduction:

  “Hey there, I’m Trump, your daily wellness companion. Let’s do a quick check-in.”

If there is previous check-in history, lightly reference the most recent entry:
  Example: “Last time on 2025-11-20 you mentioned low energy. How’s today looking?”

--- PURPOSE ---

Your goal is to guide the user through a **simple, practical wellbeing check-in**.
You should ask about:
1. Current mood  
2. energy level  1 to 10
3. One to three small, realistic intentions for the day


Keep it conversational and ask **one question at a time**.

--- STYLE GUIDELINES ---

- Warm and encouraging  
- Short, simple, natural (optimized for voice)  
- No clinical advice  
- No diagnostics  
- No crisis management  
- Absolutely no political commentary  
- Avoid heavy analysis — keep it light and practical  

--- COMPLETION LOGIC ---

Once the user has:
✔ stated their **mood**, and  
✔ given **at least one intention** (objective)  

You MUST call the `save_checkin` tool with this structure:

{
  "timestamp": "...",
  "mood": "...",
  "energy": "...",          // may be null or empty if not provided
  "objectives": ["..."],    // 1–3 short items
  "agent_summary": "one warm, friendly sentence."
}

--- SUMMARY RULES ---

The `agent_summary` must:
- Be **one single sentence**
- Warm, friendly, and neutral
- Reflect what the user shared in a simple way
- You should also gently encourage simple healthy habits when appropriate (for example: a short walk, staying hydrated, or choosing a balanced meal). Keep these suggestions light, optional, and non-prescriptive — do NOT give medical advice or clinical recommendations.
- No political content
- No judgment, no labels, no clinical/philosophical depth

--- AFTER SAVING ---

After calling the tool:
1. Read back the summary to the user in one short line  
2. Ask a quick confirmation question:  
   “Does that look right?” or “Sound okay?”  

If the user confirms (or the session ends):
- Say a short friendly goodbye:  
  “Great — have a good one! Goodbye!”

Then end the call.
"""

        super().__init__(instructions=instructions)

    # --------------------------------------------------
    # Stream Saved Entry
    # --------------------------------------------------
    async def _stream_saved_entry(self, ctx: RunContext[Userdata], entry: dict):
        """Push the saved check-in record to the UI."""
        if not ctx.room:
            return

        try:
            writer = await ctx.room.local_participant.stream_text("wellness_final")

            await writer.write(json.dumps({
                "type": "final_checkin",
                "index": len(ctx.userdata.history),
                "timestamp": entry["timestamp"],
                "entry": entry,
            }).encode("utf-8"))

            await writer.close()
        except Exception as e:
            logger.warning(f"[stream] Could not stream final entry: {e}")

    # --------------------------------------------------
    # Stream Goodbye
    # --------------------------------------------------
    async def _stream_goodbye(self, ctx: RunContext[Userdata], message: str = "Great — have a good one! Goodbye."):
        """Send a small goodbye message to the UI so the client and TTS can play it."""
        if not ctx.room:
            return

        try:
            writer = await ctx.room.local_participant.stream_text("wellness_final")
            await writer.write(json.dumps({
                "type": "goodbye",
                "message": message,
            }).encode("utf-8"))
            await writer.close()
        except Exception as e:
            logger.warning(f"[stream] Could not stream goodbye: {e}")

    # --------------------------------------------------
    # Attempt to end the call gracefully
    # --------------------------------------------------
    async def _attempt_end_call(self, ctx: RunContext[Userdata]):
        """
        Attempt multiple known ways to close/disconnect the room.
        This is defensive: the exact API may vary depending on LiveKit bindings.
        """
        if not getattr(ctx, "room", None):
            return

        room = ctx.room
        local = getattr(room, "local_participant", None)

        # Try a few possible methods in order; swallow exceptions
        candidates = [
            ("disconnect", getattr(room, "disconnect", None)),
            ("close", getattr(room, "close", None)),
            ("leave", getattr(local, "leave", None)),
            ("close_local_participant", getattr(local, "close", None)),
            ("force_disconnect", getattr(room, "disconnect_participant", None)),
        ]

        for name, fn in candidates:
            if not fn:
                continue
            try:
                if asyncio.iscoroutinefunction(fn):
                    await fn()
                else:
                    res = fn()
                    # If the call returned a coroutine, await it
                    if asyncio.iscoroutine(res):
                        await res
                logger.info(f"[end_call] Successfully called {name}()")
                # break after successful attempt
                break
            except Exception as e:
                logger.debug(f"[end_call] {name}() failed: {e}")
                continue

    # --------------------------------------------------
    # Tool: save_checkin
    # --------------------------------------------------
    @function_tool
    async def save_checkin(
        self,
        ctx: RunContext[Userdata],
        payload: Annotated[
            dict,
            Field(description="A complete check-in record: timestamp, mood, energy, objectives, agent_summary")
        ]
    ) -> str:

        # Validate required fields
        mood = (payload.get("mood") or "").strip()
        objectives = payload.get("objectives") or []
        if not mood or not objectives:
            return "Error: mood and at least one objective are required."

        entry = {
            "timestamp": payload.get("timestamp") or datetime.utcnow().isoformat(),
            "mood": mood,
            "energy": (payload.get("energy") or "").strip() or None,
            "objectives": objectives,
            "agent_summary": (payload.get("agent_summary") or "").strip() or None,
        }

        # Persist
        append_history(entry)

        # Update session memory
        try:
            ctx.userdata.history.append(CheckIn(**entry))
        except Exception:
            ctx.userdata.history.append(entry)

        # Stream to UI
        await self._stream_saved_entry(ctx, entry)

        # Say a brief goodbye to the UI and attempt to end the call gracefully.
        # The agent's LLM will still be able to follow-up with a read-back if configured,
        # but this ensures the client receives a goodbye message and the server tries to close.
        try:
            goodbye_text = entry.get("agent_summary") or "Thanks for checking in — take care!"
            # Keep goodbye short and non-clinical
            goodbye_message = f"{goodbye_text} Goodbye!"
            await self._stream_goodbye(ctx, goodbye_message)
        except Exception as e:
            logger.warning(f"Failed to stream goodbye: {e}")

        # Attempt to end the call (best-effort)
        try:
            await self._attempt_end_call(ctx)
        except Exception as e:
            logger.warning(f"Failed to end call: {e}")

        return f"Saved check-in for {entry['timestamp']}."


# ------------------------------------------------------
#   Server Wiring
# ------------------------------------------------------
server = AgentServer()


@server.rtc_session()
async def wellness_session(ctx: JobContext):

    # Load history
    userdata = Userdata()
    raw = read_history()

    try:
        userdata.history = [CheckIn(**i) for i in raw]
    except Exception:
        userdata.history = raw

    # Session
    session = AgentSession[Userdata](
        userdata=userdata,
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
        max_tool_steps=6,
        preemptive_generation=True,
    )

    ctx.session = session

    # Attach usage logging
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev):
        usage_collector.collect(ev.metrics)

    ctx.add_shutdown_callback(lambda: logger.info(
        f"usage: {usage_collector.get_summary()}"
    ))

    # Start LLM agent
    await session.start(
        agent=WellnessAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # -------------------------
    # Warm Start Hint
    # -------------------------
    if userdata.history:
        last = userdata.history[-1]
        hint = (
            f"NOTE TO LUNA: Most recent check-in was on {last.timestamp}. "
            f"The user described mood='{last.mood}'. "
            f"Use a light callback when greeting."
        )
        # Safe way to provide system-side context
        session.add_system_message(hint)

    # Connect
    await ctx.connect()


if __name__ == "__main__":
    from livekit.agents.cli import run_app
    run_app(server)