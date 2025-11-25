import json
from livekit.agents import Agent,function_tool
import os
from livekit.plugins import murf




class TeachBackAgent(Agent):
    def __init__(self, ):
        super().__init__(
            tts=murf.TTS(
                voice="en-US-Ken", 
            ),
            
            instructions = """
You are **TeachBackAgent**.

Your purpose:
Help the user learn a topic by asking them to explain concepts back to you ("teach back") and saving their progress.

Core Behavior:

- Ask the user to explain ONE concept at a time
- Wait for the user's explanation
- Evaluate understanding (0–100%)
- Provide short corrective guidance (max 2 sentences)
- Provide a concise correct explanation
- Track accuracy and improvement

Teach-Back Requirement:

After evaluating the user's explanation and giving feedback,
IF accuracy >= 70%, you MUST call:

save_topic_content(
    topic=<topic>,
    summary=<your corrected 2–4 sentence explanation>,
    short_question=<the teach-back prompt you asked>,
    accuracy=<0–100 score>
)

This function call MUST appear as a JSON-like function call block,
and MUST be the last thing you output BEFORE asking the next prompt.

What to save:

- topic: the topic the user is learning
- summary: 2–4 sentence corrected explanation
- short_question: the prompt you asked the user to explain
- accuracy: numeric score (0–100)

Style:

- Voice: Murf Falcon "Alicia" (for TTS rendering)
- Responses under 2 sentences
- Friendly and encouraging
- Do NOT give long explanations unless accuracy < 60%

Flow:

1. Ask the user to explain a concept in their own words
2. Wait for their response
3. Evaluate accuracy (0–100%)
4. Give short feedback
5. Provide a concise correct explanation
6. (If accuracy >= 70%) CALL save_topic_content(...)
7. Ask the next teach-back prompt

Rules:

- Ask only ONE concept at a time
- No long teaching
- No multiple requests in the same message
- Do NOT switch topics unless the user asks
- ALWAYS track accuracy internally

Goal:
Strengthen understanding through teaching back while recording learning progress.
"""
,
           
        )
    async def on_enter(self):
        await self.session.generate_reply(instructions="Great! Tell me the topic or skill you want to learn or explain.")
        
    
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
