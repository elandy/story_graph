import json

from langchain_core.prompts import ChatPromptTemplate

from .models import BatchExtractionResult, ExtractionResult
from .model_factory import _get_chat_llm

# Keep your extraction rules text so the model gets the same instructions.
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

async def extract_relationships(text: str, api_key: str | None = None) -> ExtractionResult:
    """
    Extract relationships for a single text chunk and return an ExtractionResult instance.
    """
    model = _get_chat_llm(provider="google", api_key=api_key)
    structured_model = model.with_structured_output(ExtractionResult)
    template = (
        "You are given a fragment of book text. Extract characters, relationships, "
        "and sentiments from the text according to the rules below.\n\n"
        f"{EXTRACTION_RULES}\n\n"
        "Text:\n"
        "{text}\n"
    )
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | structured_model

    return await chain.ainvoke({"text": text})


async def extract_relationships_batch(texts: list[str],api_key: str | None = None) -> list[ExtractionResult]:
    """
    Extract relationships for multiple chunks in a single LLM call.
    Returns one ExtractionResult for each input chunk in the same order.
    """
    if not texts: return []
    if len(texts) == 1: return [await extract_relationships(texts[0], api_key=api_key)]

    payload = {
        "chunks": [
            {
                "chunk_index": i,
                "text": text,
            }
            for i, text in enumerate(texts)
        ]
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    model = _get_chat_llm(provider="google", api_key=api_key)

    structured_model = model.with_structured_output(BatchExtractionResult)
    print(model.__class__)
    print(structured_model.__class__)
    template = (
        "You are given a JSON payload containing multiple independent text chunks.\n"
        "Process each chunk independently.\n\n"
        f"{EXTRACTION_RULES}\n\n"
        "Payload:\n"
        "{payload}\n"
    )

    prompt = ChatPromptTemplate.from_template(template)

    chain = prompt | structured_model
    print(len(payload_json))
    print(sum(len(t) for t in texts))
    parsed_batch = await chain.ainvoke(
        {"payload": payload_json}
    )
    results = [None] * len(texts)

    for item in parsed_batch.items:
        if not (0 <= item.chunk_index < len(texts)):
            raise ValueError(f"Invalid chunk_index {item.chunk_index}")

        results[item.chunk_index] = item.result

    if any(r is None for r in results):
        raise ValueError("Model did not return one result for every chunk.")

    return results