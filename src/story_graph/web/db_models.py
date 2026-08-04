from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from story_graph.web.database import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    workspace: Mapped[str] = mapped_column(Text, nullable=False, default="db")

    apply_nlp_filter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_chunk_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=3000)
    max_paragraphs_per_chunk: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    max_batch_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=9000)

    total_paragraphs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks_raw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filtered_out_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks_to_process: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_chunk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_relationships: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sentiments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    pause_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    artifacts_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    artifacts: Mapped[list["JobArtifactRecord"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class JobArtifactRecord(Base):
    __tablename__ = "job_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "name", name="uq_job_artifacts_job_id_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/octet-stream")
    compression: Mapped[str] = mapped_column(String(32), nullable=False, default="gzip")
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    compressed_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[JobRecord] = relationship(back_populates="artifacts")