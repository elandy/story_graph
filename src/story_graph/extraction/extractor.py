from pydantic_ai import Agent
from .models import ExtractionResult


relationship_agent = Agent(
    "google-gla:gemini-3.1-flash-lite-preview",
    output_type=ExtractionResult,
    system_prompt=(
        "Extract characters, relationships, and sentiments from the text."
        "Rules:"
        "- Include relationships explicitly stated or clearly implied, including roles and hierarchy."
        "- For roles: If a character is described as a professor/teacher, create 'teacher' relationships to student characters mentioned in the text."
        "- For appointments: If a character is appointed to a teaching position, create 'teacher' relationships to student characters in the text, and consider the previous holder no longer in that role if 'former' is used."
        "- For employers/leaders: If a character holds a position of authority (e.g., director), infer 'employer' or 'leader' to subordinates if stated."
        "- Do NOT infer speculative relationships beyond what's clearly implied."
        "- Evidence must be an exact quote from the text."
        "- If the text implies a social or role relationship (classmate, colleague, neighbor, mentor, etc.), treat it as a relationship and classify to the best matching type."
        "- You may infer a relationship when it is clearly implied by the text, not only when spelled out as X is Y."
    ),
)


async def extract_relationships(text: str) -> ExtractionResult:
    result = await relationship_agent.run(text)
    return result.output