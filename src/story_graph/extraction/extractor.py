from dotenv import load_dotenv
from pydantic_ai import Agent
from .models import ExtractionResult


load_dotenv()


relationship_agent = Agent(
    "google-gla:gemini-3.1-flash-lite-preview",
    output_type=ExtractionResult,
    system_prompt=(
        "Extract characters, relationships, and sentiments from the text.\n"
        "Rules:\n"
        "- Include relationships that are explicitly stated or clearly implied by the text.\n"
        "- Use common-sense inference: e.g., classmate, new classmate, coworker, teammate, boss, "
        "student, neighbor, enemy, or friend all imply a relationship even if not written as "
        "'X is Y'.\n"
        "- If the text establishes a social or role connection, create a relationship edge.\n"
        "- For role changes: when someone is appointed or replaces another in a role (e.g., teacher), "
        "create relationship edges based on that role to relevant characters in the text.\n"
        "- Set ends_here=true only when the quoted evidence itself shows that a relationship or "
        "sentiment ends in this passage (e.g., fired, retired, died, quit, left, broke up, graduated).\n"
        "- Do not invent relationships, sentiments, or endings that are not supported by the text.\n"
        "- Evidence must be an exact quote from the text.\n"
        "- Leave position and end_position null; the pipeline will fill temporal positions."
    ),
)


async def extract_relationships(text: str) -> ExtractionResult:
    result = await relationship_agent.run(text)
    return result.output
