import json

from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable

from .models import BatchExtractionResult, ExtractionResult
from .model_factory import _get_chat_llm

# Keep your extraction rules text so the model gets the same instructions.
EXTRACTION_RULES = (
    "Rules:\n"
    "- Extract all meaningful character-to-character connections.\n"
    "- A connection does not need to be friendship, family, or a social bond. "
    "Characters who meet, speak, observe, help, command, teach, follow, visit, "
    "or otherwise directly interact should receive an edge.\n"
    "- When the exact relationship is unclear, use relationship type 'unknown'. "
    "Do not omit the edge just because the social nature of the relationship is uncertain.\n"
    "- Use specific relationship labels when supported by evidence "
    "(friend, teacher, student, servant, leader, protector, etc.).\n"
    "- Use unknown when the text only establishes interaction without a clear relationship.\n"
    "- Do not create edges between characters who only appear in separate unrelated scenes "
    "unless the text establishes a connection.\n"
    "- Evidence must be an exact quote from the text.\n"
    "- Leave position and end_position null; the pipeline will fill temporal positions."
)

@traceable(
    run_type="llm",
    name="Relationship Extraction",
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
    template = (
        "You are given a JSON payload containing multiple independent text chunks.\n"
        "Process each chunk independently.\n\n"
        f"{EXTRACTION_RULES}\n\n"
        "Payload:\n"
        "{payload}\n"
    )

    prompt = ChatPromptTemplate.from_template(template)

    chain = prompt | structured_model
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