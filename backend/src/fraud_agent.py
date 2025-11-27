import logging
import sqlite3
import json
import os
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import tokenize

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ✅ SQLite Setup
conn = sqlite3.connect("fraud.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS fraud_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userName TEXT,
    securityIdentifier TEXT,
    caseStatus TEXT,
    transactionName TEXT,
    transactionTime TEXT,
    transactionCategory TEXT,
    transactionSource TEXT
)
""")

# ✅ Insert sample row if table empty
cursor.execute("SELECT COUNT(*) FROM fraud_cases")
CASES_FILE = os.path.join(os.getcwd(), "db_dump.json")
def load_cases():
    with open(CASES_FILE, "r") as f:
        return json.load(f)
if cursor.fetchone()[0] == 0:
    cases = load_cases()
    for case in cases:
        cursor.execute("""
        INSERT INTO fraud_cases (
            userName, securityIdentifier,
            transactionName, transactionTime, transactionCategory,
            transactionSource, caseStatus
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            case["userName"], case["securityIdentifier"], case["transactionName"], case["transactionTime"], case["transactionCategory"],
            case["transactionSource"], case["caseStatus"]
        ))
    conn.commit()
# ✅ Global state variables




class FraudAgent(Agent):
    def __init__(self):
        super().__init__(instructions="""
You are a calm, professional fraud representative for a fictional bank.
- Introduce yourself, verify the user using non-sensitive data (first name + security identifier).
- Read suspicious transaction details from DB.
- Ask if user authorized the transaction (yes/no).
- Update DB status to 'confirmed_safe', 'confirmed_fraud', or 'verification_failed'.
- Never ask for PINs, CVV, full card numbers or passwords.
                         # Tools

- Use available tools as needed, or upon user request.
- Collect required inputs first. Perform actions silently if the runtime expects it.
""")
        # session state
        self.current_case = None
        self.asked_verification = False
        self.verified = False
        self.asked_confirmation = False

    # on_enter will run when the session starts
    async def on_enter(self):
        # use send_text to make the agent speak / reply
        await self.session.generate_reply(instructions="Hello — this is SecureBank Fraud Team. May I have your first name as on the account?")

   
    # ---- function tools ----
    @function_tool()
    async def lookup_user_by_username(self, ctx: RunContext, message: str) -> dict:
        """
        Tool: Find a pending fraud case for provided first name (case-insensitive).
        Returns a dict with case data (or empty dict if not found).
        """
        name = (message or "").strip().lower()
        if not name:
            
            return {}
        # find pending cases for name
        cursor.execute("SELECT * FROM fraud_cases WHERE LOWER(userName)=? AND caseStatus='pending_review'", (name,))
        row = cursor.fetchone()
        if not row:
            
            return {}

        # map row
        case = {
            "id": row[0],
            "userName": row[1],
             "caseStatus": row[3],
            "securityIdentifier": row[2],
            "transactionName": row[4],
            "transactionTime": row[5],
            "transactionCategory": row[6],
            "transactionSource": row[7],
           
        }

        self.current_case = case
        self.asked_verification = True
        
        return case

    @function_tool()
    async def verify_identity_by_securityIdentifier(self, ctx: RunContext, message: str) -> bool:
        """
        Tool: check provided text against stored securityIdentifier.
        Returns True if verified, False otherwise.
        """
        print("Verifying identity..." + message)

        if not self.current_case:
            return False

        # Normalize text
        answer = (message or "").strip().replace(" ", "").lower()
        expected = (self.current_case.get("securityIdentifier") or "").strip().replace(" ", "").lower()

        if answer == expected:
            self.verified = True
            await self.session.generate_reply(
                instructions="Identity verified. Thank you."
            )
            return True

        await self.session.generate_reply(
            instructions="That doesn't match our records. Could you repeat the security identifier?"
        )
        return False


    @function_tool()
    async def get_transaction_details_from_database(self, ctx: RunContext) -> dict:
        """Tool: read the suspicious transaction to the user and ask yes/no."""
        if not self.current_case:
            return {}

        c = self.current_case
        self.asked_confirmation = True

        return c

    @function_tool()
    async def update_db_status(self, ctx: RunContext, message: str) -> dict:
        """Tool: process user's yes/no and update DB accordingly."""
        if "yes" in message:
                self.update_case("confirmed_safe")
                await self.session.generate_reply(
                    instructions="Thank you. We will mark this transaction as safe."
                )
        elif "no" in message:
                self.update_case("confirmed_fraud")
                await self.session.generate_reply(
                    instructions="Thank you. We have flagged this transaction as fraud and blocked the card."
                )
        else:
                await self.session.generate_reply(
                    instructions="Please answer yes or no."
                )
                return

        await self.session.generate_reply(instructions="Your case has been updated. Goodbye.")
        return

    # ---- DB helper (not a function_tool) ----
    def update_case(self, status: str):
        if not self.current_case:
            return
        cursor.execute(
            "UPDATE fraud_cases SET caseStatus = ? WHERE id = ?",
            (status, self.current_case["id"])
        )
        conn.commit()
        logger.info("Updated case %s -> %s", self.current_case["id"], status)
        

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=FraudAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        )
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
