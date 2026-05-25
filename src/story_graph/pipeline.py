from dataclasses import dataclass, field
from collections.abc import Callable
from math import ceil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from story_graph.aggregation.pipeline import aggregate
from story_graph.chunking.splitter import chunk_paragraphs, split_paragraphs
from story_graph.extraction.checkpoint import default_checkpoint_path
from story_graph.extraction.models import ExtractionResult
from story_graph.extraction.pipeline import process_chunks
from story_graph.graph.builder import build_graph
from story_graph.graph.visualize import visualize_graph
from story_graph.ingest.loader import load_book
from story_graph.progress import PipelineProgressUpdate, ProgressCallback, emit_progress


@dataclass(slots=True)
class StoryGraphRunConfig:
    apply_nlp_filter: bool = False
    max_chunks: int = 0
    debug_json: bool = False
    checkpoint_path: Path | None = None
    reset_checkpoint: bool = False
    max_chunk_tokens: int = 3000
    max_paragraphs_per_chunk: int = 80
    chunk_overlap: int = 0
    batch_size: int = 4
    max_batch_tokens: int = 9000
    output_html_path: Path = field(default_factory=lambda: Path("story_graph.html"))
    debug_json_path: Path | None = None
    confirm_extraction: Callable[[int], bool] | None = None
    should_pause: Callable[[], bool] | None = None
    progress_callback: ProgressCallback | None = None
    rate_limit_every: int = 5
    rate_limit_seconds: float = 60.0
    max_retries: int = 3
    retry_backoff_base_seconds: float = 2.0
    retry_backoff_max_seconds: float = 60.0


@dataclass(slots=True)
class StoryGraphRunResult:
    source_path: Path | None
    checkpoint_path: Path | None
    output_html_path: Path
    debug_json_path: Path | None
    total_paragraphs: int
    total_chunks_raw: int
    filtered_out_chunks: int
    total_chunks_available: int
    total_chunks_to_process: int
    estimated_time_seconds: int
    total_characters: int
    total_relationships: int
    total_sentiments: int
    extraction_results: list[ExtractionResult]
    graph: object


async def run_story_graph_pipeline_from_file(
    source_path: str | Path,
    config: StoryGraphRunConfig,
) -> StoryGraphRunResult:
    input_path = Path(source_path)
    text = load_book(str(input_path))
    return await run_story_graph_pipeline(
        text=text,
        config=config,
        source_path=input_path,
    )


async def run_story_graph_pipeline(
    text: str,
    config: StoryGraphRunConfig,
    source_path: Path | None = None,
) -> StoryGraphRunResult:
    if config.max_chunks < 0:
        raise ValueError("max_chunks must be zero or a positive integer.")
    if config.max_retries < 0:
        raise ValueError("max_retries must be zero or a positive integer.")
    if config.max_chunk_tokens < 0:
        raise ValueError("max_chunk_tokens must be zero or a positive integer.")
    if config.max_paragraphs_per_chunk < 0:
        raise ValueError("max_paragraphs_per_chunk must be zero or a positive integer.")
    if config.chunk_overlap < 0:
        raise ValueError("chunk_overlap must be zero or a positive integer.")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be a positive integer.")
    if config.max_batch_tokens <= 0:
        raise ValueError("max_batch_tokens must be a positive integer.")

    paragraphs = split_paragraphs(text)
    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="chunking",
            message=f"Paragraphs: {len(paragraphs)}",
            total_paragraphs=len(paragraphs),
        ),
    )

    chunks = chunk_paragraphs(
        paragraphs,
        max_tokens=config.max_chunk_tokens,
        max_paragraphs=config.max_paragraphs_per_chunk,
        overlap=config.chunk_overlap,
    )
    total_chunks_raw = len(chunks)
    filtered_out_chunks = 0

    if config.apply_nlp_filter:
        from story_graph.filtering.character_filter import has_character_interaction

        filtered_chunks = [chunk for chunk in chunks if has_character_interaction(chunk["text"])]
        filtered_out_chunks = total_chunks_raw - len(filtered_chunks)
        chunks = filtered_chunks
        emit_progress(
            config.progress_callback,
            PipelineProgressUpdate(
                stage="filtering",
                message=f"Filtered chunks without interaction: {filtered_out_chunks}",
                total_chunks_raw=total_chunks_raw,
                filtered_out_chunks=filtered_out_chunks,
            ),
        )

    total_chunks_available = len(chunks)
    total_chunks_to_process = (
        min(config.max_chunks, total_chunks_available)
        if config.max_chunks
        else total_chunks_available
    )

    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="chunking",
            message=f"Total chunks available: {total_chunks_available}",
            total_paragraphs=len(paragraphs),
            total_chunks_raw=total_chunks_raw,
            filtered_out_chunks=filtered_out_chunks,
            total_chunks_available=total_chunks_available,
            total_chunks_to_process=total_chunks_to_process,
        ),
    )
    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="chunking",
            message=(
                "Chunking config: "
                f"max_tokens={config.max_chunk_tokens or 'off'}, "
                f"max_paragraphs={config.max_paragraphs_per_chunk or 'off'}, "
                f"batch_size={config.batch_size}, "
                f"max_batch_tokens={config.max_batch_tokens}"
            ),
            total_paragraphs=len(paragraphs),
            total_chunks_raw=total_chunks_raw,
            filtered_out_chunks=filtered_out_chunks,
            total_chunks_available=total_chunks_available,
            total_chunks_to_process=total_chunks_to_process,
        ),
    )
    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="chunking",
            message=f"Chunks to process: {total_chunks_to_process}",
            total_paragraphs=len(paragraphs),
            total_chunks_raw=total_chunks_raw,
            filtered_out_chunks=filtered_out_chunks,
            total_chunks_available=total_chunks_available,
            total_chunks_to_process=total_chunks_to_process,
        ),
    )

    estimated_time_seconds = _estimate_runtime_seconds(
        total_chunks=total_chunks_to_process,
        batch_size=config.batch_size,
        rate_limit_every=config.rate_limit_every,
        rate_limit_seconds=config.rate_limit_seconds,
    )
    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="chunking",
            message=f"E.T.A.: {estimated_time_seconds / 60:.1f} minutes.",
            total_chunks_available=total_chunks_available,
            total_chunks_to_process=total_chunks_to_process,
        ),
    )

    checkpoint_path = _resolve_checkpoint_path(
        source_path=source_path,
        config=config,
    )
    if checkpoint_path is not None:
        emit_progress(
            config.progress_callback,
            PipelineProgressUpdate(
                stage="extraction",
                message=f"Extraction checkpoint: {checkpoint_path}",
                total_chunks_available=total_chunks_available,
                total_chunks_to_process=total_chunks_to_process,
                checkpoint_path=checkpoint_path,
            ),
        )

    results = await process_chunks(
        chunks[:total_chunks_to_process],
        checkpoint_path=checkpoint_path,
        reset_checkpoint=config.reset_checkpoint,
        confirm_continue=config.confirm_extraction,
        should_pause=config.should_pause,
        progress_callback=config.progress_callback,
        rate_limit_every=config.rate_limit_every,
        rate_limit_seconds=config.rate_limit_seconds,
        max_retries=config.max_retries,
        retry_backoff_base_seconds=config.retry_backoff_base_seconds,
        retry_backoff_max_seconds=config.retry_backoff_max_seconds,
        batch_size=config.batch_size,
        max_batch_tokens=config.max_batch_tokens,
    )

    total_characters = sum(len(result.characters) for result in results)
    total_relationships = sum(len(result.relationships) for result in results)
    total_sentiments = sum(len(result.sentiments) for result in results)

    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="aggregation",
            message="Aggregating extraction results.",
            total_chunks_to_process=total_chunks_to_process,
            completed_chunks=len(results),
        ),
    )

    registry, relationships, sentiments = aggregate(results)

    debug_json_path = None
    if config.debug_json:
        import json

        debug_json_path = config.debug_json_path or Path("debug_relationships.json")
        debug_json_path.parent.mkdir(parents=True, exist_ok=True)
        debug_json_path.write_text(
            json.dumps(relationships, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        emit_progress(
            config.progress_callback,
            PipelineProgressUpdate(
                stage="aggregation",
                message=f"Wrote debug relationships JSON: {debug_json_path}",
                total_chunks_to_process=total_chunks_to_process,
                completed_chunks=len(results),
            ),
        )

    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="graph",
            message="Building graph.",
            total_chunks_to_process=total_chunks_to_process,
            completed_chunks=len(results),
        ),
    )
    graph = build_graph(registry, relationships, sentiments)

    visualize_graph(
        graph,
        output_file=str(config.output_html_path),
        total_chunks=total_chunks_to_process,
    )
    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="graph",
            message=f"Graph HTML written to {config.output_html_path}",
            total_chunks_to_process=total_chunks_to_process,
            completed_chunks=len(results),
            output_path=config.output_html_path,
        ),
    )

    return StoryGraphRunResult(
        source_path=source_path,
        checkpoint_path=checkpoint_path,
        output_html_path=config.output_html_path,
        debug_json_path=debug_json_path,
        total_paragraphs=len(paragraphs),
        total_chunks_raw=total_chunks_raw,
        filtered_out_chunks=filtered_out_chunks,
        total_chunks_available=total_chunks_available,
        total_chunks_to_process=total_chunks_to_process,
        estimated_time_seconds=estimated_time_seconds,
        total_characters=total_characters,
        total_relationships=total_relationships,
        total_sentiments=total_sentiments,
        extraction_results=results,
        graph=graph,
    )


def _resolve_checkpoint_path(
    source_path: Path | None,
    config: StoryGraphRunConfig,
) -> Path | None:
    if config.checkpoint_path is not None:
        return config.checkpoint_path

    if source_path is None:
        return None

    return default_checkpoint_path(str(source_path), config.apply_nlp_filter)


def _estimate_runtime_seconds(
    total_chunks: int,
    batch_size: int,
    rate_limit_every: int,
    rate_limit_seconds: float,
) -> int:
    if total_chunks <= 0:
        return 0
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer.")

    total_requests = ceil(total_chunks / batch_size)
    processing_seconds = total_requests * 10
    if rate_limit_every <= 0 or rate_limit_seconds <= 0:
        return processing_seconds

    requests_per_second = rate_limit_every / rate_limit_seconds
    if requests_per_second <= 0:
        return processing_seconds

    pacing_seconds = ceil((total_requests - 1) / requests_per_second) if total_requests > 1 else 0
    return processing_seconds + pacing_seconds
