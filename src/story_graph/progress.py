from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(slots=True)
class PipelineProgressUpdate:
    stage: str
    message: str
    total_paragraphs: int | None = None
    total_chunks_raw: int | None = None
    filtered_out_chunks: int | None = None
    total_chunks_available: int | None = None
    total_chunks_to_process: int | None = None
    completed_chunks: int | None = None
    current_chunk: int | None = None
    checkpoint_path: Path | None = None
    output_path: Path | None = None


ProgressCallback = Callable[[PipelineProgressUpdate], None]


def emit_progress(
    callback: ProgressCallback | None,
    update: PipelineProgressUpdate,
) -> None:
    if callback is not None:
        callback(update)
