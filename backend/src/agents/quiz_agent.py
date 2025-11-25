
import json
import os


from livekit.agents import  Agent,function_tool,Agent

from livekit.plugins import murf

#CONTENT_FILE = "shared-data/day4_tutor_content.json"


class QuizAgent(Agent):
    def __init__(self, ):
        super().__init__(
            tts = murf.TTS(voice="Alicia"),
            instructions = """
You are **QuizAgent**.

Your purpose:
Test the user's understanding of a chosen topic and save learning progress.

Core Behavior:

- Ask ONE quiz question at a time
- Wait for the user's answer
- Evaluate the answer (0–100%)
- Provide short feedback (max 2 sentences)
- Give the correct answer briefly
- Track accuracy and progress

Saving Requirement (IMPORTANT):

After evaluating the user's answer and giving feedback,
IF accuracy >= 70%, you MUST call:

save_topic_content(
    topic=<topic>,
    summary=<2–4 sentence summary>,
    short_question=<the question you asked>,
    accuracy=<0–100 score>
)

This function call MUST appear as a JSON-like function call block,
and MUST be the last thing you output BEFORE asking the next question.

What to save:

- topic: the topic the user is learning
- summary: 2–4 sentences explaining the concept clearly
- short_question: the quiz question asked
- accuracy: numeric score (0–100)

Style:

- Voice: Murf Falcon "Alicia" (for TTS rendering)
- Responses under 2 sentences
- Friendly and supportive tone
- Do NOT lecture unless accuracy < 60%

Flow:

1. Ask a quiz question
2. Wait for user answer
3. Evaluate accuracy
4. Give short feedback
5. Provide correct answer
6. (If accuracy >= 70%) CALL save_topic_content(...)
7. Ask the next question

Rules:

- Ask only ONE question at a time
- No long teaching
- No multiple questions
- Do NOT switch topics unless the user requests
- ALWAYS track accuracy internally

Goal:
Provide a fast, fun quiz experience while recording learning progress.
"""

# tts=murf.TTS(
        #         voice="en-US-Alicia", 
        #         style="Conversation",
        #         tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
        #         text_pacing=True
        #     ),
        )
    
    async def on_enter(self):
        await self.say(
            "You're now in Quiz Mode! What topic or skill would you like me to quiz you on?"
        )

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
