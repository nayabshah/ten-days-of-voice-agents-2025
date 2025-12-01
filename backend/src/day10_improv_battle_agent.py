# improv_battle_agent.py
import logging
import json
import random
from datetime import datetime

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

# ----------------------------
# Predefined improv scenarios
# ----------------------------
PRESET_SCENARIOS = [
    "You are a time-travelling tour guide explaining modern smartphones to someone from the 1800s. Show them how to 'swipe'.",
    "You are a barista who has to tell a customer that their latte is actually a portal to another dimension.",
    "You are a restaurant waiter who must calmly tell a customer that their order has escaped the kitchen and is now a free agent.",
    "You are a hotel concierge in a hotel where rooms rearrange themselves every night. Help a confused guest find their bed.",
    "You are a customer trying to return an obviously cursed object to a very skeptical shop owner.",
    "You are an astronaut trying to explain Earth slang to a robot co-pilot mid-flight.",
    "You are a farmer selling 'mystery vegetables' at a market — be convincing and creative about what they do.",
    "You are a detective interrogating a suspect who insists the criminal act was committed by a very persuasive pigeon."
]

# ----------------------------
# Assistant Agent (Host)
# ----------------------------
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are the host of a TV improv show called "Improv Battle".
Persona:
- High-energy, witty, clear about rules.
- Reactions should be realistic: sometimes amused, sometimes unimpressed, sometimes pleasantly surprised.
- Keep feedback constructive: supportive, neutral, or mildly critical (never abusive or insulting).
Structure:
- Introduce the show and explain the rules.
- Run N improv rounds per session.
- For each round: announce a scenario, invite the player to improvise, listen, react, and store the reaction.
Behavior notes:
- Use start_game to initialize and get the first scenario.
- Use submit_performance when the player finishes a scene (or says 'End scene' / 'End show' to stop).
- Use end_game for early exit.
- Keep spoken responses short and conversational when speaking aloud.
""",
        )
        # per-instance session state (one Assistant instance -> one session in this pattern)
        self.improv_state = None

    # ----------------------------
    # Helpers
    # ----------------------------
    def _make_initial_state(self, player_name: str | None, max_rounds: int):
        return {
            "player_name": player_name or "Contestant",
            "current_round": 0,
            "max_rounds": max_rounds,
            "rounds": [],  # each: {"scenario": str, "performance": str, "host_reaction": str}
            "phase": "intro",  # intro | awaiting_improv | reacting | done
            "started_at": datetime.now().isoformat(),
        }

    def _choose_scenario(self):
        # choose a scenario not already used if possible
        used = {r["scenario"] for r in self.improv_state["rounds"]}
        available = [s for s in PRESET_SCENARIOS if s not in used]
        if not available:
            available = PRESET_SCENARIOS[:]
        return random.choice(available)

    def _choose_tone(self):
        # randomly pick supportive, neutral, mildly_critical with weighted prob
        return random.choices(["supportive", "neutral", "mildly_critical"], weights=[0.45, 0.35, 0.2])[0]

    def _make_reaction_text(self, scenario, performance, tone):
        """
        Simple heuristics to craft a reaction:
        - mention a specific moment if performance is long enough or contains keywords
        - vary language by tone
        """
        highlight = None
        perf_lower = (performance or "").lower()
        # look for inherently improv-friendly markers
        for marker in ["joke", "funny", "laugh", "weird", "surreal", "absurd", "dramatic", "cry", "shout"]:
            if marker in perf_lower:
                highlight = marker
                break

        # pick phrase fragments
        if tone == "supportive":
            opener = random.choice([
                "Fantastic! That was a lovely scene —",
                "Brilliant! I loved that —",
                "Nice work! You leaned into the premise really well —"
            ])
            if highlight:
                return f"{opener} especially the bit about \"{highlight}\" — that landed for me. Let's move on."
            if len(performance or "") > 60:
                return f"{opener} you gave that plenty of detail and it paid off. Great energy!"
            return f"{opener} clean choices, clear character. Well done."

        if tone == "neutral":
            opener = random.choice([
                "Okay — that was interesting.",
                "Noted. You explored the idea.",
                "Good attempt."
            ])
            if highlight:
                return f"{opener} The \"{highlight}\" moment caught my attention, though you could've expanded it."
            return f"{opener} I want to see you push the choices a bit further next time."

        # mildly_critical
        opener = random.choice([
            "Hmm, not bad, but it felt a bit safe.",
            "I think you had an idea but didn't commit to it fully.",
            "Close — I wanted a stronger choice."
        ])
        if highlight:
            return f"{opener} The \"{highlight}\" moment showed promise; lean in more on that next time."
        if len(performance or "") < 25:
            return f"{opener} Try to give a little more detail — a sentence or two more can make the scene breathe."
        return f"{opener} Try more specificity in the stakes or the character's need."

    def _make_summary(self):
        """Create a short closing summary describing player's style and highlights."""
        rounds = self.improv_state["rounds"]
        if not rounds:
            return "You didn't get to perform. Come back when you're ready for the spotlight!"

        # gather signals
        total_text = " ".join((r.get("performance") or "") for r in rounds)
        len_total = len(total_text)
        energy = "energetic" if len_total > 200 else "measured"
        mentions = []
        for r in rounds:
            perf = (r.get("performance") or "").lower()
            for marker in ["funny", "absurd", "dramatic", "emotional", "romantic", "sardonic", "weird", "surreal"]:
                if marker in perf and marker not in mentions:
                    mentions.append(marker)

        standout = []
        for r in rounds:
            if r.get("host_reaction"):
                # if host reaction mentioned something specific, surface it
                standout.append(r["host_reaction"].split(".")[0])

        summary_lines = [
            f"Alright {self.improv_state['player_name']}, that's a wrap on Improv Battle!",
            f"You came across as an {energy} improviser."
        ]
        if mentions:
            summary_lines.append("You showed strengths around: " + ", ".join(mentions) + ".")
        if standout:
            summary_lines.append("Standout moments: " + " | ".join(standout[:3]) + ".")
        summary_lines.append("Thanks for playing — keep practicing those bold choices!")
        return " ".join(summary_lines)

    # ----------------------------
    # Tools exposed to the LLM / session
    # ----------------------------
    @function_tool
    async def start_game(self, ctx: RunContext, player_name: str | None = None, max_rounds: int = 3):
        """
        Initialize game state and return the first scenario object:
        {
            "scenario": str,
            "round_number": int,
            "phase": "awaiting_improv"
        }
        """
        max_rounds = int(max_rounds or 3)
        self.improv_state = self._make_initial_state(player_name, max_rounds)
        # prepare first scenario
        scenario = self._choose_scenario()
        self.improv_state["phase"] = "awaiting_improv"
        self.improv_state["current_round"] = 1
        self.improv_state["rounds"].append({"scenario": scenario, "performance": None, "host_reaction": None})
        return {
            "scenario": scenario,
            "round_number": 1,
            "phase": self.improv_state["phase"],
            "player_name": self.improv_state["player_name"]
        }

    @function_tool
    async def submit_performance(self, ctx: RunContext, text: str):
        """
        Record the player's performance text for the current round, produce a host reaction,
        and either prepare the next scenario or finalize the game.
        Returns a dict:
        {
            "host_reaction": str,
            "next_scenario": str | None,
            "round_number": int,
            "phase": "reacting" | "awaiting_improv" | "done",
            "summary": str | None
        }
        """
        if not self.improv_state:
            return {"error": "Game not started. Call start_game first."}

        # defensive normalization
        text = (text or "").strip()
        # store performance
        idx = self.improv_state["current_round"] - 1
        if idx < 0 or idx >= self.improv_state["max_rounds"]:
            # out of bounds - finalize
            self.improv_state["phase"] = "done"
            summary = self._make_summary()
            return {"host_reaction": "No active round.", "next_scenario": None, "phase": "done", "summary": summary}

        self.improv_state["rounds"][idx]["performance"] = text
        # pick a tone and make reaction
        tone = self._choose_tone()
        reaction = self._make_reaction_text(self.improv_state["rounds"][idx]["scenario"], text, tone)
        self.improv_state["rounds"][idx]["host_reaction"] = reaction
        self.improv_state["phase"] = "reacting"

        # decide whether to continue or finish
        if self.improv_state["current_round"] >= self.improv_state["max_rounds"]:
            # finalize
            self.improv_state["phase"] = "done"
            summary = self._make_summary()
            return {
                "host_reaction": reaction,
                "next_scenario": None,
                "round_number": self.improv_state["current_round"],
                "phase": "done",
                "summary": summary
            }
        else:
            # prepare next round
            self.improv_state["current_round"] += 1
            next_scn = self._choose_scenario()
            self.improv_state["rounds"].append({"scenario": next_scn, "performance": None, "host_reaction": None})
            self.improv_state["phase"] = "awaiting_improv"
            return {
                "host_reaction": reaction,
                "next_scenario": next_scn,
                "round_number": self.improv_state["current_round"],
                "phase": "awaiting_improv",
                "summary": None
            }

    @function_tool
    async def end_game(self, ctx: RunContext):
        """
        End the game early and return a closing summary.
        """
        if not self.improv_state:
            return {"message": "No active game."}
        self.improv_state["phase"] = "done"
        summary = self._make_summary()
        return {"message": "Game ended", "summary": summary}

# ----------------------------
# Bootstrapping: session and runner
# ----------------------------

def prewarm(proc: JobProcess):
    # load VAD once for each process
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    # attach some logging context
    ctx.log_context_fields = {"room": ctx.room.name}

    # create an AgentSession similar to your Day-9 setup
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
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
    def _metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage summary: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session with an instance of Assistant (one per session)
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    # connect to LiveKit room
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
