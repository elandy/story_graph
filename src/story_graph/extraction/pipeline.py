import asyncio
from pathlib import Path

from story_graph.extraction.checkpoint import load_checkpoint, write_checkpoint
from story_graph.extraction.extractor import extract_relationships
from story_graph.extraction.models import ExtractionResult


def _match_evidence_position(evidence: str, paragraphs: list[str], start_index: int) -> int:
    for offset, paragraph in enumerate(paragraphs):
        if evidence in paragraph:
            return start_index + offset

    return start_index


def annotate_temporal_positions(result: ExtractionResult, chunk: dict) -> ExtractionResult:
    paragraphs = chunk["text"].split("\n\n")
    start_index = chunk["start_index"]

    for relationship in result.relationships:
        position = _match_evidence_position(relationship.evidence, paragraphs, start_index)
        relationship.position = position
        # end_position is exclusive so an ending chunk remains visible on the slider.
        relationship.end_position = position + 1 if relationship.ends_here else None

    for sentiment in result.sentiments:
        position = _match_evidence_position(sentiment.evidence, paragraphs, start_index)
        sentiment.position = position
        sentiment.end_position = position + 1 if sentiment.ends_here else None

    return result


async def process_chunks(
    chunks: list[dict],
    checkpoint_path: Path | None = None,
    reset_checkpoint: bool = False,
):
    if not chunks:
        return []

    results = []
    checkpoint_file = Path(checkpoint_path) if checkpoint_path is not None else None

    if checkpoint_file is not None:
        if reset_checkpoint and checkpoint_file.exists():
            checkpoint_file.unlink()
            print(f"Reset checkpoint: {checkpoint_file}")

        results = load_checkpoint(checkpoint_file, chunks)

        if results:
            print(
                f"Loaded {len(results)}/{len(chunks)} chunks from checkpoint: "
                f"{checkpoint_file}"
            )
        else:
            print(f"Using checkpoint file: {checkpoint_file}")

    if len(results) >= len(chunks):
        print("All requested chunks are already available in the checkpoint.")
        return results[:len(chunks)]

    remaining_chunks = len(chunks) - len(results)
    proceed = input(f"Proceed with extraction for {remaining_chunks} remaining chunk(s)? (y/n): ")
    if proceed.strip().lower() != "y":
        print("Extraction cancelled.")
        return results

    requests_in_run = 0

    for i in range(len(results), len(chunks)):
        chunk = chunks[i]
        print(f"Processing chunk {i + 1}/{len(chunks)}")

        try:
            result = await extract_relationships(text=chunk["text"])
        except Exception as exc:
            print(f"Extraction failed on chunk {i + 1}/{len(chunks)}: {exc}")
            if checkpoint_file is not None:
                print(f"Partial progress is saved in: {checkpoint_file}")
            raise

        result = annotate_temporal_positions(result, chunk)
        results.append(result)

        if checkpoint_file is not None:
            write_checkpoint(checkpoint_file, chunks, results)

        requests_in_run += 1

        # Rate limiting: sleep after every 5 requests in the current run.
        if requests_in_run % 5 == 0 and i + 1 < len(chunks):
            print("Rate limit: sleeping 60 seconds after 5 requests")
            await asyncio.sleep(60)

    return results
