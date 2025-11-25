

from dataclasses import dataclass, field
from typing import Optional

from livekit.agents import RunContext, function_tool


CONTENT_FILE = "shared-data/day4_tutor_content.json"

@dataclass
class MasteryLoops:
    last_score: float = 0.0
    avg_score: float = 0.0
    topic: Optional[str] = None
    summary: Optional[str] = None
    sample_question: Optional[str] = None

    @function_tool()
    async def record_topic(
        self,
        context: RunContext["MySessionInfo"],
        topic: str,
        summary: str | None = None,
        sample_question: str | None = None,
    ):
        """
        Use this tool to record the user's current topic and mastery info.
        """

        session = context.session.userdata  # ✅ this IS MySessionInfo

        # Ensure topic object exists
        mastery = session.topic

        mastery.topic = topic
        mastery.summary = summary or mastery.summary
        mastery.sample_question = sample_question or mastery.sample_question
        mastery.times_explained += 1

        # Save back
        session.topic = mastery

        return {
            "message": f"Recorded topic '{topic}'",
            "times_explained": mastery.times_explained
        }


@dataclass
class MySessionInfo:
    data: MasteryLoops = field(default_factory=MasteryLoops)