from pydantic_ai import Agent
from .models import ExtractionResult


relationship_agent = Agent(
    "google-gla:gemini-3.1-flash-lite-preview",
    output_type=ExtractionResult,
    system_prompt=(
        "Extract characters, relationships, and sentiments from the text."
        "Rules:"
        "- Include relationships that are explicitly stated OR clearly implied by the text."
        "- Use common-sense inference: e.g., 'classmate', 'new classmate', 'coworker', 'teammate', "
        "  'boss', 'student', 'neighbor', 'enemy', 'friend' all imply a relationship even if not "
        "  written as 'X is Y'."
        "- If the text establishes a social/role connection, create a relationship edge. "
        "- For role changes: When someone is appointed or replaces another in a role (e.g., teacher), create relationship edges based on that role to relevant characters in the text (e.g., teacher to students)."
        "- For relationship endings: If the text implies a relationship ends (e.g., 'graduated', 'fired', 'retired', 'died', 'quit', 'left'), "
        "  set end_position to the current position for the relevant relationship."
        "- Do NOT invent relationships or endings that are not supported by any text."
        "- Evidence must be an exact quote from the text."
    ),
)


async def extract_relationships(text: str) -> ExtractionResult:
    result = await relationship_agent.run(text)
    return result.output