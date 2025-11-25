import json
import os

from livekit.agents import Agent, ChatContext,function_tool,Agent, RunContext
from livekit.plugins import murf


CONTENT_FILE = "shared-data/day4_tutor_content.json"

class LearnAgent(Agent):
    
    def __init__(self,chat_ctx: ChatContext = None):
        
        
        super().__init__(
            tts = murf.TTS(voice="en-US-Matthew",style="Conversation"),
            instructions="""
You are LearnAgent.

Your purpose:
Help the learner understand ONE topic clearly, then save what they learned.

Your responsibilities:

- Ask the user what topic or skill they want to learn
- Generate a simple, beginner-friendly explanation
- Ask ONE short understanding question
- Evaluate the user's answer briefly (0–100%) and remember this as accuracy
- If understanding is good (accuracy >= 70%), provide a short summary
- After providing the summary,
    YOU MUST CALL:

    save_topic_content(topic, summary, short_question, accuracy)

    so the topic can be stored.

What to save:

- topic (the name the user gave)
- summary (2–4 sentences)
- short_question (the understanding check question)
- accuracy (0–100 score)

Style:
- Keep tone friendly and encouraging
- Explanations must be 3–5 sentences maximum
- Avoid heavy jargon unless explained simply

Flow:

1. Ask: "What topic would you like to learn?"
2. Receive topic
3. Explain the topic simply
4. Ask ONE short understanding question
5. Evaluate the user's answer (0–100)
6. If accuracy >= 70:
    - Give short positive feedback
    - Provide a short summary
    - CALL save_topic_content(...)
7. If accuracy < 70:
    - Give helpful feedback
    - Re-explain briefly and ask ONE new question

Rules:

- Do NOT ask multiple questions at once
- Do NOT turn this into a quiz session
- Do NOT lecture for too long
- Do NOT invent a new topic unless the user requests it
- ALWAYS call save_topic_content(...) after explaining and summarizing successfully

Your goal:
Help the learner understand the concept with one short explanation,
one follow-up question, and properly SAVE the learning result.
"""
        )
        
   
    async def on_enter(self)-> None:
        # self.session.tts = murf.TTS(voice="Matthew")
        await self.session.generate_reply(instructions="Greet Welcome to Learn Mode! What topic or skill would you like to learn today?")

    @function_tool()
    async def save_topic_content(
        self,
        topic: str,
        summary: str,
        sample_question: str,
        accuracy: float = None,
    ):
        """Save learned topic immediately after summary is generated"""

        entry = {
            "id": topic.lower().replace(" ", "_"),
            "title": topic,
            "summary": summary,
            "sample_question": sample_question,
            "accuracy": accuracy
        }

        path = "shared-data/day4_tutor_content.json"
        directory = os.path.dirname(path)

        # ✅ ensure directory exists
        os.makedirs(directory, exist_ok=True)

        # ✅ load existing content
        try:
            with open(path, "r") as f:
                content = json.load(f)
                if not isinstance(content, list):
                    content = []
        except FileNotFoundError:
            content = []
        except json.JSONDecodeError:
            content = []

        # ✅ avoid duplicates by id
        if not any(e.get("id") == entry["id"] for e in content):
            content.append(entry)

            # ✅ write back
            with open(path, "w") as f:
                json.dump(content, f, indent=2)

            print(f"✅ Saved: {entry['id']}")

        return "✅ Topic saved!"
