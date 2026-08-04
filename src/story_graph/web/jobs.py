import asyncio
import tempfile
import threading
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue

from sqlalchemy import delete, select

from story_graph.extraction.pipeline import ExtractionPaused
from story_graph.pipeline import StoryGraphRunConfig, run_story_graph_pipeline_from_file
from story_graph.progress import PipelineProgressUpdate
from story_graph.web.compression import COMPRESSION_ALGORITHM, compress_bytes, decompress_bytes
from story_graph.web.database import SessionLocal
from story_graph.web.db_models import JobArtifactRecord, JobRecord
from story_graph.web.models import JobArtifacts, JobState, JobStatus


class JobNotFoundError(FileNotFoundError):
    pass


class JobRetryError(ValueError):
    pass


class JobPauseError(ValueError):
    pass


class JobDeleteError(ValueError):
    pass


class JobManager:
    def __init__(self, jobs_root: Path | None = None, retention_days: int = 30):
        self.jobs_root = Path(jobs_root or tempfile.gettempdir()).resolve()
        self.retention_days = retention_days
        self._queue: Queue[str | None] = Queue()
        self._stop_event = threading.Event()
        self._write_lock = threading.RLock()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        if self._worker is not None and self._worker.is_alive():
            return

        self._stop_event.clear()
        self._cleanup_expired_jobs()
        self._requeue_incomplete_jobs()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="story-graph-worker",
            daemon=True,
        )
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=1)
        if self._worker is not None and not self._worker.is_alive():
            self._worker = None

    def create_job(
        self,
        upload_name: str,
        file_bytes: bytes,
        session_id: str,
        provider_api_key: str | None = None,
        apply_nlp_filter: bool = False,
        max_chunks: int = 0,
        max_chunk_tokens: int = 3000,
        max_paragraphs_per_chunk: int = 80,
        batch_size: int = 4,
        max_batch_tokens: int = 9000,
    ) -> JobStatus:
        if max_chunks < 0:
            raise ValueError("max_chunks must be zero or a positive integer.")
        if max_chunk_tokens < 0:
            raise ValueError("max_chunk_tokens must be zero or a positive integer.")
        if max_paragraphs_per_chunk < 0:
            raise ValueError("max_paragraphs_per_chunk must be zero or a positive integer.")
        if batch_size <= 0:
            raise ValueError("batch_size must be a positive integer.")
        if max_batch_tokens <= 0:
            raise ValueError("max_batch_tokens must be a positive integer.")

        text = file_bytes.decode("utf-8")
        if not text.strip():
            raise ValueError("Uploaded file is empty.")

        job_id = uuid.uuid4().hex
        now = _utc_now()
        status = JobStatus(
            job_id=job_id,
            session_id=session_id,
            state=JobState.queued,
            stage="queued",
            message="Job queued.",
            created_at=now,
            updated_at=now,
            original_filename=Path(upload_name).name or "upload.txt",
            workspace="db",
            apply_nlp_filter=apply_nlp_filter,
            max_chunks=max_chunks,
            max_chunk_tokens=max_chunk_tokens,
            max_paragraphs_per_chunk=max_paragraphs_per_chunk,
            batch_size=batch_size,
            max_batch_tokens=max_batch_tokens,
        )

        with self._write_lock, SessionLocal() as session:
            session.add(self._record_from_status(status))
            self._upsert_artifact(
                session,
                job_id,
                status.artifacts.input_file,
                file_bytes,
                content_type="text/plain; charset=utf-8",
            )
            if provider_api_key:
                self._upsert_artifact(
                    session,
                    job_id,
                    ".provider_api_key",
                    provider_api_key.encode("utf-8"),
                    content_type="text/plain; charset=utf-8",
                )
            session.commit()

        self._queue.put(job_id)
        return status

    def list_statuses(self) -> list[JobStatus]:
        with SessionLocal() as session:
            records = session.scalars(
                select(JobRecord).order_by(JobRecord.updated_at.desc())
            ).all()
            return [self._status_from_record(record) for record in records]

    def list_statuses_for_session(self, session_id: str) -> list[JobStatus]:
        with SessionLocal() as session:
            records = session.scalars(
                select(JobRecord)
                .where(JobRecord.session_id == session_id)
                .order_by(JobRecord.updated_at.desc())
            ).all()
            return [self._status_from_record(record) for record in records]

    def retry_job(self, job_id: str) -> JobStatus:
        with self._write_lock:
            status = self.get_status(job_id)
            if status.state not in {JobState.failed, JobState.paused}:
                raise JobRetryError("Only failed or paused jobs can be resumed.")

            if self.get_artifact_bytes(job_id, status.artifacts.input_file) is None:
                raise JobRetryError("Job input file is missing.")

            status.state = JobState.queued
            status.stage = "queued"
            status.message = "Job queued to resume from checkpoint."
            status.pause_requested = False
            status.error = None
            status.traceback = None
            status.updated_at = _utc_now()
            self._write_status(status)

        self._queue.put(job_id)
        return status

    def pause_job(self, job_id: str) -> JobStatus:
        with self._write_lock:
            status = self.get_status(job_id)
            if status.state == JobState.queued:
                status.state = JobState.paused
                status.stage = "paused"
                status.message = "Job paused."
                status.pause_requested = False
            elif status.state == JobState.running:
                status.pause_requested = True
                status.stage = "pausing"
                status.message = "Pause requested. Waiting for the current batch to finish."
            elif status.state == JobState.paused:
                raise JobPauseError("Job is already paused.")
            else:
                raise JobPauseError("Only queued or running jobs can be paused.")

            status.updated_at = _utc_now()
            self._write_status(status)
            return status

    def delete_job(self, job_id: str) -> None:
        with self._write_lock, SessionLocal() as session:
            status = self.get_status(job_id)
            if status.state not in {JobState.completed, JobState.failed, JobState.paused}:
                raise JobDeleteError("Only completed, failed, or paused jobs can be deleted.")

            result = session.execute(delete(JobRecord).where(JobRecord.job_id == job_id))
            if result.rowcount == 0:
                raise JobNotFoundError(job_id)
            session.commit()

    def get_status(self, job_id: str) -> JobStatus:
        with SessionLocal() as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                raise JobNotFoundError(job_id)
            return self._status_from_record(record)

    def get_status_for_session(self, job_id: str, session_id: str) -> JobStatus:
        status = self.get_status(job_id)
        if status.session_id != session_id:
            raise JobNotFoundError(job_id)

        return status

    def graph_bytes(self, job_id: str) -> bytes | None:
        status = self.get_status(job_id)
        return self.get_artifact_bytes(job_id, status.artifacts.graph_file)

    def get_artifact_bytes(self, job_id: str, name: str) -> bytes | None:
        with SessionLocal() as session:
            artifact = session.scalar(
                select(JobArtifactRecord).where(
                    JobArtifactRecord.job_id == job_id,
                    JobArtifactRecord.name == name,
                )
            )
            if artifact is None:
                return None
            return decompress_bytes(artifact.data)

    def graph_path(self, job_id: str) -> Path:
        raise RuntimeError("Graph artifacts are stored in Postgres. Use graph_bytes().")

    def checkpoint_path(self, job_id: str) -> Path:
        raise RuntimeError("Checkpoint artifacts are stored in Postgres.")

    def debug_json_path(self, job_id: str) -> Path:
        raise RuntimeError("Debug artifacts are stored in Postgres.")

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=0.25)
            except Empty:
                continue

            if job_id is None:
                self._queue.task_done()
                break

            try:
                self._run_job(job_id)
            finally:
                self._queue.task_done()

    def _run_job(self, job_id: str) -> None:
        try:
            status = self.get_status(job_id)
        except JobNotFoundError:
            return

        if status.state in {JobState.completed, JobState.failed, JobState.paused}:
            return

        self._update_status(
            job_id,
            state=JobState.running,
            stage="running",
            message="Worker started processing.",
            pause_requested=False,
            error=None,
            traceback=None,
        )

        with tempfile.TemporaryDirectory(prefix=f"story-graph-{job_id}-") as tmp_dir:
            workspace = Path(tmp_dir)
            input_path = workspace / status.artifacts.input_file
            checkpoint_path = workspace / status.artifacts.checkpoint_file
            graph_path = workspace / status.artifacts.graph_file
            debug_json_path = workspace / status.artifacts.debug_relationships_file

            input_bytes = self.get_artifact_bytes(job_id, status.artifacts.input_file)
            if input_bytes is None:
                self._update_status(
                    job_id,
                    state=JobState.failed,
                    stage="failed",
                    message="Job failed: input artifact is missing.",
                    pause_requested=False,
                    error="Input artifact is missing.",
                    traceback=None,
                )
                return
            input_path.write_bytes(input_bytes)

            checkpoint_bytes = self.get_artifact_bytes(job_id, status.artifacts.checkpoint_file)
            if checkpoint_bytes is not None:
                checkpoint_path.write_bytes(checkpoint_bytes)

            provider_api_key = self._read_provider_api_key(job_id)

            def persist_checkpoint_if_present() -> None:
                if checkpoint_path.exists():
                    self._save_file_artifact(
                        job_id,
                        checkpoint_path,
                        status.artifacts.checkpoint_file,
                        content_type="application/json",
                    )

            def progress_callback(update: PipelineProgressUpdate) -> None:
                try:
                    current_status = self.get_status(job_id)
                except JobNotFoundError:
                    return

                fields = {
                    "stage": update.stage,
                    "message": update.message,
                }
                for field_name in (
                    "total_paragraphs",
                    "total_chunks_raw",
                    "filtered_out_chunks",
                    "total_chunks_available",
                    "total_chunks_to_process",
                    "completed_chunks",
                    "current_chunk",
                ):
                    value = getattr(update, field_name)
                    if value is not None:
                        fields[field_name] = value

                if current_status.pause_requested:
                    fields["stage"] = "pausing"
                    fields["message"] = "Pause requested. Waiting for the current batch to finish."

                self._update_status(job_id, **fields)
                persist_checkpoint_if_present()

            try:
                result = asyncio.run(
                    run_story_graph_pipeline_from_file(
                        input_path,
                        StoryGraphRunConfig(
                            apply_nlp_filter=status.apply_nlp_filter,
                            max_chunks=status.max_chunks,
                            max_chunk_tokens=status.max_chunk_tokens,
                            max_paragraphs_per_chunk=status.max_paragraphs_per_chunk,
                            batch_size=status.batch_size,
                            max_batch_tokens=status.max_batch_tokens,
                            provider_api_key=provider_api_key,
                            debug_json=True,
                            checkpoint_path=checkpoint_path,
                            reset_checkpoint=False,
                            output_html_path=graph_path,
                            debug_json_path=debug_json_path,
                            confirm_extraction=lambda _remaining: True,
                            should_pause=lambda: self._should_pause(job_id),
                            progress_callback=progress_callback,
                        ),
                    )
                )
            except ExtractionPaused:
                persist_checkpoint_if_present()
                self._update_status(
                    job_id,
                    state=JobState.paused,
                    stage="paused",
                    message="Job paused.",
                    current_chunk=None,
                    pause_requested=False,
                    error=None,
                    traceback=None,
                )
                return
            except Exception as exc:
                persist_checkpoint_if_present()
                self._update_status(
                    job_id,
                    state=JobState.failed,
                    stage="failed",
                    message=f"Job failed: {exc}",
                    pause_requested=False,
                    error=str(exc),
                    traceback=traceback.format_exc(),
                )
                return

            if checkpoint_path.exists():
                self._save_file_artifact(
                    job_id,
                    checkpoint_path,
                    status.artifacts.checkpoint_file,
                    content_type="application/json",
                )
            if graph_path.exists():
                self._save_file_artifact(
                    job_id,
                    graph_path,
                    status.artifacts.graph_file,
                    content_type="text/html; charset=utf-8",
                )
            if debug_json_path.exists():
                self._save_file_artifact(
                    job_id,
                    debug_json_path,
                    status.artifacts.debug_relationships_file,
                    content_type="application/json",
                )

            self._update_status(
                job_id,
                state=JobState.completed,
                stage="completed",
                message="Graph ready.",
                total_paragraphs=result.total_paragraphs,
                total_chunks_raw=result.total_chunks_raw,
                filtered_out_chunks=result.filtered_out_chunks,
                total_chunks_available=result.total_chunks_available,
                total_chunks_to_process=result.total_chunks_to_process,
                completed_chunks=len(result.extraction_results),
                current_chunk=None,
                estimated_time_seconds=result.estimated_time_seconds,
                total_characters=result.total_characters,
                total_relationships=result.total_relationships,
                total_sentiments=result.total_sentiments,
                pause_requested=False,
                error=None,
                traceback=None,
            )

    def _requeue_incomplete_jobs(self) -> None:
        with self._write_lock, SessionLocal() as session:
            records = session.scalars(
                select(JobRecord).where(JobRecord.state.in_([JobState.queued.value, JobState.running.value]))
            ).all()

            for record in records:
                record.state = JobState.queued.value
                record.stage = "queued"
                record.message = "Job queued."
                record.pause_requested = False
                record.error = None
                record.traceback = None
                record.updated_at = _utc_now()
                self._queue.put(record.job_id)

            session.commit()

    def _update_status(self, job_id: str, **fields) -> JobStatus:
        with self._write_lock:
            status = self.get_status(job_id)
            for field_name, value in fields.items():
                setattr(status, field_name, value)
            status.updated_at = _utc_now()
            self._write_status(status)
            return status

    def _write_status(self, status: JobStatus) -> None:
        with self._write_lock, SessionLocal() as session:
            record = session.get(JobRecord, status.job_id)
            if record is None:
                raise JobNotFoundError(status.job_id)

            self._apply_status_to_record(status, record)
            session.commit()

    def _should_pause(self, job_id: str) -> bool:
        try:
            return self.get_status(job_id).pause_requested
        except JobNotFoundError:
            return False

    def _cleanup_expired_jobs(self) -> None:
        if self.retention_days <= 0:
            return

        cutoff = _utc_now().timestamp() - (self.retention_days * 86400)
        removable_states = {JobState.completed.value, JobState.failed.value, JobState.paused.value}

        with self._write_lock, SessionLocal() as session:
            records = session.scalars(
                select(JobRecord).where(JobRecord.state.in_(removable_states))
            ).all()

            for record in records:
                if record.updated_at.timestamp() <= cutoff:
                    session.delete(record)

            session.commit()

    def _read_provider_api_key(self, job_id: str) -> str | None:
        data = self.get_artifact_bytes(job_id, ".provider_api_key")
        if data is None:
            return None

        value = data.decode("utf-8").strip()
        return value or None

    def _save_file_artifact(
        self,
        job_id: str,
        path: Path,
        name: str,
        *,
        content_type: str,
    ) -> None:
        self._save_artifact_bytes(
            job_id,
            name,
            path.read_bytes(),
            content_type=content_type,
        )

    def _save_artifact_bytes(
        self,
        job_id: str,
        name: str,
        data: bytes,
        *,
        content_type: str,
    ) -> None:
        with self._write_lock, SessionLocal() as session:
            self._upsert_artifact(session, job_id, name, data, content_type=content_type)
            session.commit()

    def _upsert_artifact(
        self,
        session,
        job_id: str,
        name: str,
        data: bytes,
        *,
        content_type: str,
    ) -> None:
        now = _utc_now()
        compressed = compress_bytes(data)

        artifact = session.scalar(
            select(JobArtifactRecord).where(
                JobArtifactRecord.job_id == job_id,
                JobArtifactRecord.name == name,
            )
        )

        if artifact is None:
            artifact = JobArtifactRecord(
                job_id=job_id,
                name=name,
                content_type=content_type,
                compression=COMPRESSION_ALGORITHM,
                data=compressed,
                size_bytes=len(data),
                compressed_size_bytes=len(compressed),
                created_at=now,
                updated_at=now,
            )
            session.add(artifact)
            return

        artifact.content_type = content_type
        artifact.compression = COMPRESSION_ALGORITHM
        artifact.data = compressed
        artifact.size_bytes = len(data)
        artifact.compressed_size_bytes = len(compressed)
        artifact.updated_at = now

    def _record_from_status(self, status: JobStatus) -> JobRecord:
        return JobRecord(
            job_id=status.job_id,
            session_id=status.session_id,
            state=status.state.value,
            stage=status.stage,
            message=status.message,
            created_at=status.created_at,
            updated_at=status.updated_at,
            original_filename=status.original_filename,
            workspace=status.workspace,
            apply_nlp_filter=status.apply_nlp_filter,
            max_chunks=status.max_chunks,
            max_chunk_tokens=status.max_chunk_tokens,
            max_paragraphs_per_chunk=status.max_paragraphs_per_chunk,
            batch_size=status.batch_size,
            max_batch_tokens=status.max_batch_tokens,
            total_paragraphs=status.total_paragraphs,
            total_chunks_raw=status.total_chunks_raw,
            filtered_out_chunks=status.filtered_out_chunks,
            total_chunks_available=status.total_chunks_available,
            total_chunks_to_process=status.total_chunks_to_process,
            completed_chunks=status.completed_chunks,
            current_chunk=status.current_chunk,
            estimated_time_seconds=status.estimated_time_seconds,
            total_characters=status.total_characters,
            total_relationships=status.total_relationships,
            total_sentiments=status.total_sentiments,
            pause_requested=status.pause_requested,
            error=status.error,
            traceback=status.traceback,
            artifacts_meta=status.artifacts.model_dump(mode="json"),
        )

    def _apply_status_to_record(self, status: JobStatus, record: JobRecord) -> None:
        record.session_id = status.session_id
        record.state = status.state.value
        record.stage = status.stage
        record.message = status.message
        record.created_at = status.created_at
        record.updated_at = status.updated_at
        record.original_filename = status.original_filename
        record.workspace = status.workspace
        record.apply_nlp_filter = status.apply_nlp_filter
        record.max_chunks = status.max_chunks
        record.max_chunk_tokens = status.max_chunk_tokens
        record.max_paragraphs_per_chunk = status.max_paragraphs_per_chunk
        record.batch_size = status.batch_size
        record.max_batch_tokens = status.max_batch_tokens
        record.total_paragraphs = status.total_paragraphs
        record.total_chunks_raw = status.total_chunks_raw
        record.filtered_out_chunks = status.filtered_out_chunks
        record.total_chunks_available = status.total_chunks_available
        record.total_chunks_to_process = status.total_chunks_to_process
        record.completed_chunks = status.completed_chunks
        record.current_chunk = status.current_chunk
        record.estimated_time_seconds = status.estimated_time_seconds
        record.total_characters = status.total_characters
        record.total_relationships = status.total_relationships
        record.total_sentiments = status.total_sentiments
        record.pause_requested = status.pause_requested
        record.error = status.error
        record.traceback = status.traceback
        record.artifacts_meta = status.artifacts.model_dump(mode="json")

    def _status_from_record(self, record: JobRecord) -> JobStatus:
        return JobStatus(
            job_id=record.job_id,
            session_id=record.session_id,
            state=JobState(record.state),
            stage=record.stage,
            message=record.message,
            created_at=record.created_at,
            updated_at=record.updated_at,
            original_filename=record.original_filename,
            workspace=record.workspace,
            apply_nlp_filter=record.apply_nlp_filter,
            max_chunks=record.max_chunks,
            max_chunk_tokens=record.max_chunk_tokens,
            max_paragraphs_per_chunk=record.max_paragraphs_per_chunk,
            batch_size=record.batch_size,
            max_batch_tokens=record.max_batch_tokens,
            total_paragraphs=record.total_paragraphs,
            total_chunks_raw=record.total_chunks_raw,
            filtered_out_chunks=record.filtered_out_chunks,
            total_chunks_available=record.total_chunks_available,
            total_chunks_to_process=record.total_chunks_to_process,
            completed_chunks=record.completed_chunks,
            current_chunk=record.current_chunk,
            estimated_time_seconds=record.estimated_time_seconds,
            total_characters=record.total_characters,
            total_relationships=record.total_relationships,
            total_sentiments=record.total_sentiments,
            pause_requested=record.pause_requested,
            error=record.error,
            traceback=record.traceback,
            artifacts=JobArtifacts.model_validate(record.artifacts_meta or {}),
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)