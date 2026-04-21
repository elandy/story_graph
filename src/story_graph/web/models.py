from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobArtifacts(BaseModel):
    input_file: str = "input.txt"
    checkpoint_file: str = "checkpoint.json"
    graph_file: str = "story_graph.html"
    debug_relationships_file: str = "debug_relationships.json"
    status_file: str = "status.json"


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    stage: str
    message: str
    created_at: datetime
    updated_at: datetime
    original_filename: str
    workspace: str
    apply_nlp_filter: bool = False
    max_chunks: int = 0
    total_paragraphs: int = 0
    total_chunks_raw: int = 0
    filtered_out_chunks: int = 0
    total_chunks_available: int = 0
    total_chunks_to_process: int = 0
    completed_chunks: int = 0
    current_chunk: int | None = None
    estimated_time_seconds: int = 0
    total_characters: int = 0
    total_relationships: int = 0
    total_sentiments: int = 0
    error: str | None = None
    traceback: str | None = None
    artifacts: JobArtifacts = Field(default_factory=JobArtifacts)
