import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from story_graph.extraction.checkpoint import load_checkpoint, write_checkpoint
from story_graph.extraction.extractor import extract_relationships, extract_relationships_batch
from story_graph.extraction.models import ExtractionResult
from story_graph.progress import PipelineProgressUpdate, ProgressCallback, emit_progress


class ExtractionPaused(Exception):
    pass


class RequestPacer:
    def __init__(
        self,
        rate_limit_every: int,
        rate_limit_seconds: float,
        *,
        now_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._now_fn = now_fn or time.monotonic
        self._sleep_fn = sleep_fn or asyncio.sleep
        if rate_limit_every <= 0 or rate_limit_seconds <= 0:
            self._min_interval_seconds = 0.0
        else:
            self._min_interval_seconds = rate_limit_seconds / rate_limit_every
        self._last_request_started_at: float | None = None

    async def wait_for_slot(
        self,
        *,
        progress_callback: ProgressCallback | None = None,
        total_chunks_to_process: int | None = None,
        completed_chunks: int | None = None,
        current_chunk: int | None = None,
        checkpoint_path: Path | None = None,
    ) -> None:
        if self._min_interval_seconds <= 0:
            self._last_request_started_at = self._now_fn()
            return

        if self._last_request_started_at is not None:
            elapsed = self._now_fn() - self._last_request_started_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                emit_progress(
                    progress_callback,
                    PipelineProgressUpdate(
                        stage="extraction",
                        message=f"Rate limit: waiting {remaining:.1f} seconds before next request",
                        total_chunks_to_process=total_chunks_to_process,
                        completed_chunks=completed_chunks,
                        current_chunk=current_chunk,
                        checkpoint_path=checkpoint_path,
                    ),
                )
                await self._sleep_fn(remaining)

        self._last_request_started_at = self._now_fn()


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return True

    if isinstance(exc, (ValueError, TypeError, AssertionError)):
        return False

    message = str(exc).lower()
    retry_markers = (
        "429",
        "rate limit",
        "rate-limit",
        "timeout",
        "timed out",
        "temporar",
        "connection reset",
        "connection aborted",
        "connection refused",
        "service unavailable",
        "server error",
        "overloaded",
        "try again",
        "temporary outage",
    )
    return any(marker in message for marker in retry_markers)


def _retry_delay_seconds(
    attempt: int,
    *,
    base_seconds: float,
    max_seconds: float,
) -> float:
    if attempt <= 0:
        raise ValueError("attempt must be positive.")
    delay = base_seconds * (2 ** (attempt - 1))
    return min(delay, max_seconds)


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
    should_pause: Callable[[], bool] | None = None,
    progress_callback: ProgressCallback | None = None,
    rate_limit_every: int = 5,
    rate_limit_seconds: float = 60.0,
    max_retries: int = 3,
    retry_backoff_base_seconds: float = 2.0,
    retry_backoff_max_seconds: float = 60.0,
    batch_size: int = 4,
    max_batch_tokens: int = 9000,
    extractor: Callable[..., Awaitable[ExtractionResult]] | None = None,
    batch_extractor: Callable[[list[str]], Awaitable[list[ExtractionResult]]] | None = None,
    now_fn: Callable[[], float] | None = None,
    sleep_fn: Callable[[float], Awaitable[None]] | None = None,
):
    if not chunks:
        return []
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer.")
    if max_batch_tokens <= 0:
        raise ValueError("max_batch_tokens must be a positive integer.")

    extractor_fn = extractor or extract_relationships
    batch_extractor_fn = batch_extractor or extract_relationships_batch
    results = []
    checkpoint_file = Path(checkpoint_path) if checkpoint_path is not None else None
    effective_sleep_fn = sleep_fn or asyncio.sleep
    pacer = RequestPacer(
        rate_limit_every,
        rate_limit_seconds,
        now_fn=now_fn,
        sleep_fn=effective_sleep_fn,
    )

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
    chunk_index = len(results)

    while chunk_index < len(chunks):
        if should_pause is not None and should_pause():
            emit_progress(
                progress_callback,
                PipelineProgressUpdate(
                    stage="extraction",
                    message="Extraction paused.",
                    total_chunks_to_process=len(chunks),
                    completed_chunks=len(results),
                    current_chunk=chunk_index + 1 if chunk_index < len(chunks) else None,
                    checkpoint_path=checkpoint_file,
                ),
            )
            raise ExtractionPaused("Extraction paused.")

        batch_chunks = _select_batch_chunks(
            chunks,
            start_index=chunk_index,
            batch_size=batch_size,
            max_batch_tokens=max_batch_tokens,
        )
        batch_start = chunk_index + 1
        batch_end = batch_start + len(batch_chunks) - 1
        emit_progress(
            progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message=(
                    f"Processing chunk {batch_start}/{len(chunks)}"
                    if len(batch_chunks) == 1
                    else f"Processing chunks {batch_start}-{batch_end}/{len(chunks)}"
                ),
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                current_chunk=batch_start,
                checkpoint_path=checkpoint_file,
            ),
        )

        attempt = 0
        batch_results: list[ExtractionResult]
        while True:
            attempt += 1
            await pacer.wait_for_slot(
                progress_callback=progress_callback,
                total_chunks_to_process=len(chunks),
                completed_chunks=len(results),
                current_chunk=batch_start,
                checkpoint_path=checkpoint_file,
            )
            try:
                if len(batch_chunks) == 1:
                    batch_results = [await extractor_fn(text=batch_chunks[0]["text"])]
                else:
                    batch_results = await batch_extractor_fn(
                        [chunk["text"] for chunk in batch_chunks]
                    )
                _validate_batch_results(batch_results, len(batch_chunks))
                break
            except Exception as exc:
                retryable = _is_retryable_error(exc)
                if attempt <= max_retries and retryable:
                    delay = _retry_delay_seconds(
                        attempt,
                        base_seconds=retry_backoff_base_seconds,
                        max_seconds=retry_backoff_max_seconds,
                    )
                    emit_progress(
                        progress_callback,
                        PipelineProgressUpdate(
                            stage="extraction",
                            message=(
                                f"Retrying chunks {batch_start}-{batch_end}/{len(chunks)} after error: {exc} "
                                f"(attempt {attempt}/{max_retries}, waiting {delay:.1f}s)"
                            ),
                            total_chunks_to_process=len(chunks),
                            completed_chunks=len(results),
                            current_chunk=batch_start,
                            checkpoint_path=checkpoint_file,
                        ),
                    )
                    await effective_sleep_fn(delay)
                    continue

                emit_progress(
                    progress_callback,
                    PipelineProgressUpdate(
                        stage="extraction",
                        message=(
                            f"Extraction failed on chunks {batch_start}-{batch_end}/{len(chunks)}: {exc}"
                        ),
                        total_chunks_to_process=len(chunks),
                        completed_chunks=len(results),
                        current_chunk=batch_start,
                        checkpoint_path=checkpoint_file,
                    ),
                )
                raise

        for offset, result in enumerate(batch_results):
            chunk = batch_chunks[offset]
            normalized = annotate_temporal_positions(result, chunk)
            results.append(normalized)

            if checkpoint_file is not None:
                write_checkpoint(checkpoint_file, chunks, results)

            completed_index = chunk_index + offset + 1
            emit_progress(
                progress_callback,
                PipelineProgressUpdate(
                    stage="extraction",
                    message=f"Completed chunk {completed_index}/{len(chunks)}",
                    total_chunks_to_process=len(chunks),
                    completed_chunks=len(results),
                    current_chunk=completed_index,
                    checkpoint_path=checkpoint_file,
                ),
            )

        chunk_index = len(results)

    return results


def _prompt_for_confirmation(remaining_chunks: int) -> bool:
    proceed = input(
        f"Proceed with extraction for {remaining_chunks} remaining chunk(s)? (y/n): "
    )
    return proceed.strip().lower() == "y"


def _validate_batch_results(results: list[ExtractionResult], expected_count: int) -> None:
    if len(results) != expected_count:
        raise ValueError(
            f"Expected {expected_count} extraction result(s) from the batch, got {len(results)}."
        )


def _select_batch_chunks(
    chunks: list[dict],
    *,
    start_index: int,
    batch_size: int,
    max_batch_tokens: int,
) -> list[dict]:
    selected = []
    token_total = 0

    for chunk in chunks[start_index:]:
        if len(selected) >= batch_size:
            break

        chunk_tokens = int(chunk.get("token_estimate", 0) or 0)
        separator_tokens = 8 if selected else 0
        proposed_total = token_total + separator_tokens + chunk_tokens

        if selected and proposed_total > max_batch_tokens:
            break

        selected.append(chunk)
        token_total = proposed_total

    if not selected and start_index < len(chunks):
        return [chunks[start_index]]

    return selected
