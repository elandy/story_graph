import json

from dotenv import load_dotenv
from pydantic_ai import Agent

from .models import BatchExtractionResult, ExtractionResult


load_dotenv()


MODEL_NAME = "google-gla:gemini-3.1-flash-lite"
EXTRACTION_RULES = (
    "Rules:\n"
    "- Include relationships that are explicitly stated or clearly implied by the text.\n"
    "- Use common-sense inference: e.g., classmate, new classmate, coworker, teammate, roommate, boss, "
    "student, neighbor, enemy, or friend all imply a relationship even if not written as "
    "'X is Y'.\n"
    "- If the text establishes a social or role connection, create a relationship edge.\n"
    "- Prefer the most specific kinship label supported by the text. For example, use aunt, uncle, "
    "niece, nephew, cousin, grandparent, or grandchild when that is what the text indicates.\n"
    "- Do not collapse specific family relationships into parent/child. An aunt or uncle is not a parent. "
    "A guardian or caretaker is not automatically a parent unless the text supports that parental relation.\n"
    "- For role changes: when someone is appointed or replaces another in a role (e.g., teacher), "
    "create relationship edges based on that role to relevant characters in the text.\n"
    "- Set ends_here=true only when the quoted evidence itself shows that a relationship or "
    "sentiment ends in this passage (e.g., fired, retired, died, quit, left, broke up, graduated).\n"
    "- Do not invent relationships, sentiments, or endings that are not supported by the text.\n"
    "- Evidence must be an exact quote from the text.\n"
    "- Leave position and end_position null; the pipeline will fill temporal positions."
)


relationship_agent = Agent(
    MODEL_NAME,
    output_type=ExtractionResult,
    system_prompt=(
        "Extract characters, relationships, and sentiments from the text.\n"
        f"{EXTRACTION_RULES}"
    ),
)


batch_relationship_agent = Agent(
    MODEL_NAME,
    output_type=BatchExtractionResult,
    system_prompt=(
        "Extract characters, relationships, and sentiments for each chunk in the JSON payload.\n"
        "Return one item for every chunk.\n"
        "- Each item must preserve its input chunk_index.\n"
        "- Treat each chunk independently.\n"
        "- If a chunk has no findings, return empty lists for that chunk.\n"
        f"{EXTRACTION_RULES}"
    ),
)


async def extract_relationships(text: str) -> ExtractionResult:
    result = await relationship_agent.run(text)
    return result.output


async def extract_relationships_batch(texts: list[str]) -> list[ExtractionResult]:
    if not texts:
        return []

    if len(texts) == 1:
        return [await extract_relationships(texts[0])]

    payload = {
        "chunks": [
            {
                "chunk_index": chunk_index,
                "text": text,
            }
            for chunk_index, text in enumerate(texts)
        ]
    }
    result = await batch_relationship_agent.run(
        json.dumps(payload, ensure_ascii=False, indent=2)
    )

    expected_indices = set(range(len(texts)))
    items_by_index = {}
    for item in result.output.items:
        if item.chunk_index in items_by_index:
            raise ValueError(f"Duplicate chunk_index in batch response: {item.chunk_index}")
        items_by_index[item.chunk_index] = item.result

    if set(items_by_index) != expected_indices:
        raise ValueError("Batch extraction response did not return exactly one result per chunk.")

    return [items_by_index[index] for index in range(len(texts))]
