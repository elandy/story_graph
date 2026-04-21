from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, Field

from story_graph.extraction.models import ExtractionResult


CHECKPOINT_VERSION = 1


class CheckpointEntry(BaseModel):
    chunk_index: int
    chunk_start_index: int
    chunk_fingerprint: str
    result: ExtractionResult


class ExtractionCheckpoint(BaseModel):
    version: int = CHECKPOINT_VERSION
    completed: list[CheckpointEntry] = Field(default_factory=list)


def default_checkpoint_path(book_path: str, apply_nlp_filter: bool) -> Path:
    source_path = Path(book_path).resolve()
    filter_suffix = "filtered" if apply_nlp_filter else "raw"
    book_hash = sha256(str(source_path).encode("utf-8")).hexdigest()[:12]
    safe_stem = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in source_path.stem
    ).strip("_") or "book"

    return Path("data") / "checkpoints" / f"{safe_stem}.{filter_suffix}.{book_hash}.json"


def chunk_fingerprint(chunk: dict) -> str:
    payload = f"{chunk['start_index']}\n{chunk['text']}".encode("utf-8")
    return sha256(payload).hexdigest()


def load_checkpoint(path: Path, chunks: list[dict]) -> list[ExtractionResult]:
    if not path.exists():
        return []

    try:
        checkpoint = ExtractionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Checkpoint file {path} is invalid: {exc}") from exc

    if checkpoint.version != CHECKPOINT_VERSION:
        raise ValueError(
            f"Checkpoint file {path} has version {checkpoint.version}, "
            f"expected {CHECKPOINT_VERSION}."
        )

    results = []
    max_entries = min(len(checkpoint.completed), len(chunks))

    for expected_index in range(max_entries):
        entry = checkpoint.completed[expected_index]
        current_chunk = chunks[expected_index]

        if entry.chunk_index != expected_index:
            raise ValueError(
                f"Checkpoint file {path} is not contiguous at chunk {expected_index}."
            )

        if entry.chunk_start_index != current_chunk["start_index"]:
            raise ValueError(
                f"Checkpoint file {path} does not match the current chunk start indices."
            )

        if entry.chunk_fingerprint != chunk_fingerprint(current_chunk):
            raise ValueError(
                f"Checkpoint file {path} does not match the current chunk content."
            )

        results.append(entry.result)

    return results


def write_checkpoint(path: Path, chunks: list[dict], results: list[ExtractionResult]) -> None:
    if len(results) > len(chunks):
        raise ValueError("Cannot write more checkpointed results than chunks.")

    entries = []
    for chunk_index, result in enumerate(results):
        chunk = chunks[chunk_index]
        entries.append(
            CheckpointEntry(
                chunk_index=chunk_index,
                chunk_start_index=chunk["start_index"],
                chunk_fingerprint=chunk_fingerprint(chunk),
                result=result,
            )
        )

    checkpoint = ExtractionCheckpoint(completed=entries)

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")
    temp_path.replace(path)
