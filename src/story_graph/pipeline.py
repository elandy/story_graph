from dataclasses import dataclass, field
from collections.abc import Callable
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
    output_html_path: Path = field(default_factory=lambda: Path("story_graph.html"))
    debug_json_path: Path | None = None
    confirm_extraction: Callable[[int], bool] | None = None
    progress_callback: ProgressCallback | None = None
    rate_limit_every: int = 5
    rate_limit_seconds: float = 60.0


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

    paragraphs = split_paragraphs(text)
    emit_progress(
        config.progress_callback,
        PipelineProgressUpdate(
            stage="chunking",
            message=f"Paragraphs: {len(paragraphs)}",
            total_paragraphs=len(paragraphs),
        ),
    )

    chunks = chunk_paragraphs(paragraphs)
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
            message=f"Chunks to process: {total_chunks_to_process}",
            total_paragraphs=len(paragraphs),
            total_chunks_raw=total_chunks_raw,
            filtered_out_chunks=filtered_out_chunks,
            total_chunks_available=total_chunks_available,
            total_chunks_to_process=total_chunks_to_process,
        ),
    )

    sleeps = (total_chunks_to_process - 1) // config.rate_limit_every if (
        total_chunks_to_process > 0 and config.rate_limit_every > 0
    ) else 0
    estimated_time_seconds = sleeps * int(config.rate_limit_seconds) + total_chunks_to_process * 10
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
        progress_callback=config.progress_callback,
        rate_limit_every=config.rate_limit_every,
        rate_limit_seconds=config.rate_limit_seconds,
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
