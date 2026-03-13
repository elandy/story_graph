from pydantic_ai import Agent
from .models import ExtractionResult


relationship_agent = Agent(
    "google-gla:gemini-3.1-flash-lite-preview",
    output_type=ExtractionResult,
    system_prompt=(
        "Extract characters, relationships, and sentiments from the text."
        "Rules:"
        "- Only include relationships explicitly stated or clearly implied."
        "- Do NOT infer speculative relationships."
        "- If two characters do not interact, do not create a relationship."
        "- Evidence must be an exact quote from the text."
    ),
)


async def extract_relationships(text: str) -> ExtractionResult:
    result = await relationship_agent.run(text)
    return result.output