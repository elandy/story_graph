import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from story_graph.extraction.checkpoint import load_checkpoint, write_checkpoint
from story_graph.extraction.extractor import extract_relationships
from story_graph.extraction.models import ExtractionResult
from story_graph.progress import PipelineProgressUpdate, ProgressCallback, emit_progress


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
    confirm_continue: Callable[[int], bool] | None = None,
    progress_callback: ProgressCallback | None = None,
    rate_limit_every: int = 5,
    rate_limit_seconds: float = 60.0,
    extractor: Callable[..., Awaitable[ExtractionResult]] | None = None,
):
    if not chunks:
        return []

    extractor_fn = extractor or extract_relationships
    results = []
    checkpoint_file = Path(checkpoint_path) if checkpoint_path is not None else None

    if checkpoint_file is not None:
        if reset_checkpoint and checkpoint_file.exists():
            checkpoint_file.unlink()
            emit_progress(
                progress_callback,
                PipelineProgressUpdate(
                    stage="extraction",
                    message=f"Reset checkpoint: {checkpoint_file}",
                    total_chunks_to_process=len(chunks),
                    completed_chunks=0,
                    checkpoint_path=checkpoint_file,
                ),
            )

        results = load_checkpoint(checkpoint_file, chunks)

        if results:
            message = (
                f"Loaded {len(results)}/{len(chunks)} chunks from checkpoint: "
                f"{checkpoint_file}"
            )
        else:
            message = f"Using checkpoint file: {checkpoint_file}"

        emit_progress(
            progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message=message,
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                checkpoint_path=checkpoint_file,
            ),
        )

    if len(results) >= len(chunks):
        emit_progress(
            progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message="All requested chunks are already available in the checkpoint.",
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                checkpoint_path=checkpoint_file,
            ),
        )
        return results[:len(chunks)]

    remaining_chunks = len(chunks) - len(results)
    should_continue = (
        confirm_continue(remaining_chunks)
        if confirm_continue is not None
        else _prompt_for_confirmation(remaining_chunks)
    )
    if not should_continue:
        emit_progress(
            progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message="Extraction cancelled.",
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                checkpoint_path=checkpoint_file,
            ),
        )
        return results

    requests_in_run = 0

    for i in range(len(results), len(chunks)):
        chunk = chunks[i]
        emit_progress(
            progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message=f"Processing chunk {i + 1}/{len(chunks)}",
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                current_chunk=i + 1,
                checkpoint_path=checkpoint_file,
            ),
        )

        try:
            result = await extractor_fn(text=chunk["text"])
        except Exception as exc:
            emit_progress(
                progress_callback,
                PipelineProgressUpdate(
                    stage="extraction",
                    message=f"Extraction failed on chunk {i + 1}/{len(chunks)}: {exc}",
                    total_chunks_to_process=len(chunks),
                    completed_chunks=len(results),
                    current_chunk=i + 1,
                    checkpoint_path=checkpoint_file,
                ),
            )
            raise

        result = annotate_temporal_positions(result, chunk)
        results.append(result)

        if checkpoint_file is not None:
            write_checkpoint(checkpoint_file, chunks, results)

        emit_progress(
            progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message=f"Completed chunk {i + 1}/{len(chunks)}",
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                current_chunk=i + 1,
                checkpoint_path=checkpoint_file,
            ),
        )

        requests_in_run += 1

        # Rate limiting: sleep after every 5 requests in the current run.
        if (
            rate_limit_every > 0
            and requests_in_run % rate_limit_every == 0
            and i + 1 < len(chunks)
        ):
            emit_progress(
                progress_callback,
                PipelineProgressUpdate(
                    stage="extraction",
                    message=(
                        "Rate limit: sleeping "
                        f"{rate_limit_seconds:.0f} seconds after {rate_limit_every} requests"
                    ),
                    total_chunks_to_process=len(chunks),
                    completed_chunks=len(results),
                    current_chunk=i + 1,
                    checkpoint_path=checkpoint_file,
                ),
            )
            await asyncio.sleep(rate_limit_seconds)

    return results


def _prompt_for_confirmation(remaining_chunks: int) -> bool:
    proceed = input(
        f"Proceed with extraction for {remaining_chunks} remaining chunk(s)? (y/n): "
    )
    return proceed.strip().lower() == "y"
