import pytest


AI_SAMPLE = (
    "In today's fast-paced digital landscape, leveraging cutting-edge technologies "
    "is essential for organizations seeking to remain competitive. By embracing "
    "innovative solutions and fostering a culture of continuous improvement, "
    "businesses can unlock new opportunities for growth and drive meaningful "
    "outcomes. Furthermore, the integration of advanced analytics and AI-driven "
    "insights enables decision-makers to navigate complexity with confidence. "
    "Ultimately, success hinges on the ability to adapt, evolve, and deliver "
    "value across diverse stakeholder ecosystems. It is therefore imperative "
    "that leaders prioritize strategic alignment, operational excellence, and "
    "transformative thinking in equal measure."
)


HUMAN_SAMPLE = (
    "I went down to the river yesterday and the water was so low you could "
    "see the rocks the kids used to jump off, the ones we always told them "
    "not to jump off. Funny how that works. The heron was back, anyway, "
    "standing in the shallows like she'd never left. She probably hadn't. "
    "I sat on the bank for maybe an hour, didn't catch anything, didn't "
    "really try. My knee is bothering me again. Mom called twice while I "
    "was out, both about the same thing. I'll call her back tonight, "
    "probably, or tomorrow."
)


@pytest.fixture
def ai_text() -> str:
    return AI_SAMPLE


@pytest.fixture
def human_text() -> str:
    return HUMAN_SAMPLE
