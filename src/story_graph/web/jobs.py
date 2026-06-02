import asyncio
import shutil
import threading
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue

from story_graph.extraction.pipeline import ExtractionPaused
from story_graph.pipeline import StoryGraphRunConfig, run_story_graph_pipeline_from_file
from story_graph.progress import PipelineProgressUpdate
from story_graph.web.models import JobState, JobStatus


class JobNotFoundError(FileNotFoundError):
    pass


class JobRetryError(ValueError):
    pass


class JobPauseError(ValueError):
    pass


class JobDeleteError(ValueError):
    pass


class JobManager:
    def __init__(self, jobs_root: Path, retention_days: int = 30):
        self.jobs_root = Path(jobs_root).resolve()
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

        self.jobs_root.mkdir(parents=True, exist_ok=True)

        text = file_bytes.decode("utf-8")
        if not text.strip():
            raise ValueError("Uploaded file is empty.")

        job_id = uuid.uuid4().hex
        workspace = self.jobs_root / job_id
        workspace.mkdir(parents=True, exist_ok=False)

        status = JobStatus(
            job_id=job_id,
            state=JobState.queued,
            stage="queued",
            message="Job queued.",
            created_at=_utc_now(),
            updated_at=_utc_now(),
            original_filename=Path(upload_name).name or "upload.txt",
            workspace=str(workspace),
            apply_nlp_filter=apply_nlp_filter,
            max_chunks=max_chunks,
            max_chunk_tokens=max_chunk_tokens,
            max_paragraphs_per_chunk=max_paragraphs_per_chunk,
            batch_size=batch_size,
            max_batch_tokens=max_batch_tokens,
        )

        self._input_path(job_id).write_text(text, encoding="utf-8")
        if provider_api_key:
            self._api_key_path(job_id).write_text(provider_api_key, encoding="utf-8")
        self._write_status(status)
        self._queue.put(job_id)
        return status

    def list_statuses(self) -> list[JobStatus]:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        statuses = []

        with self._write_lock:
            for status_path in self.jobs_root.glob("*/status.json"):
                try:
                    statuses.append(
                        JobStatus.model_validate_json(
                            status_path.read_text(encoding="utf-8")
                        )
                    )
                except Exception:
                    continue

        return sorted(statuses, key=lambda status: status.updated_at, reverse=True)

    def retry_job(self, job_id: str) -> JobStatus:
        with self._write_lock:
            status = self.get_status(job_id)
            if status.state not in {JobState.failed, JobState.paused}:
                raise JobRetryError("Only failed or paused jobs can be resumed.")

            if not self._input_path(job_id).exists():
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
        workspace = self._workspace(job_id)
        with self._write_lock:
            status = self.get_status(job_id)
            if status.state not in {JobState.completed, JobState.failed, JobState.paused}:
                raise JobDeleteError("Only completed, failed, or paused jobs can be deleted.")

            if not workspace.exists():
                raise JobNotFoundError(job_id)

            shutil.rmtree(workspace)

    def get_status(self, job_id: str) -> JobStatus:
        status_path = self._status_path(job_id)
        with self._write_lock:
            if not status_path.exists():
                raise JobNotFoundError(job_id)
            return JobStatus.model_validate_json(status_path.read_text(encoding="utf-8"))

    def graph_path(self, job_id: str) -> Path:
        status = self.get_status(job_id)
        return self._workspace(job_id) / status.artifacts.graph_file

    def checkpoint_path(self, job_id: str) -> Path:
        status = self.get_status(job_id)
        return self._workspace(job_id) / status.artifacts.checkpoint_file

    def debug_json_path(self, job_id: str) -> Path:
        status = self.get_status(job_id)
        return self._workspace(job_id) / status.artifacts.debug_relationships_file

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

        input_path = self._input_path(job_id)
        provider_api_key = self._read_provider_api_key(job_id)
        checkpoint_path = self._workspace(job_id) / status.artifacts.checkpoint_file
        graph_path = self._workspace(job_id) / status.artifacts.graph_file
        debug_json_path = self._workspace(job_id) / status.artifacts.debug_relationships_file

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
        for status_path in self.jobs_root.glob("*/status.json"):
            try:
                status = JobStatus.model_validate_json(status_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if status.state not in {JobState.queued, JobState.running}:
                continue

            status.state = JobState.queued
            status.stage = "queued"
            status.message = "Job queued."
            status.pause_requested = False
            status.error = None
            status.traceback = None
            status.updated_at = _utc_now()
            self._write_status(status)
            self._queue.put(status.job_id)

    def _update_status(self, job_id: str, **fields) -> JobStatus:
        with self._write_lock:
            status = self.get_status(job_id)
            for field_name, value in fields.items():
                setattr(status, field_name, value)
            status.updated_at = _utc_now()
            self._write_status(status)
            return status

    def _write_status(self, status: JobStatus) -> None:
        with self._write_lock:
            status_path = self._status_path(status.job_id)
            status_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = status_path.with_suffix(status_path.suffix + ".tmp")
            temp_path.write_text(
                status.model_dump_json(indent=2),
                encoding="utf-8",
            )
            temp_path.replace(status_path)

    def _workspace(self, job_id: str) -> Path:
        return self.jobs_root / job_id

    def _status_path(self, job_id: str) -> Path:
        return self._workspace(job_id) / "status.json"

    def _input_path(self, job_id: str) -> Path:
        return self._workspace(job_id) / "input.txt"

    def _api_key_path(self, job_id: str) -> Path:
        return self._workspace(job_id) / ".provider_api_key"

    def _should_pause(self, job_id: str) -> bool:
        try:
            return self.get_status(job_id).pause_requested
        except JobNotFoundError:
            return False

    def _cleanup_expired_jobs(self) -> None:
        if self.retention_days <= 0:
            return

        cutoff = _utc_now().timestamp() - (self.retention_days * 86400)
        for status_path in self.jobs_root.glob("*/status.json"):
            try:
                status = JobStatus.model_validate_json(status_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if status.state not in {JobState.completed, JobState.failed, JobState.paused}:
                continue

            if status.updated_at.timestamp() > cutoff:
                continue

            workspace = self._workspace(status.job_id)
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

    def _read_provider_api_key(self, job_id: str) -> str | None:
        api_key_path = self._api_key_path(job_id)
        if not api_key_path.exists():
            return None

        value = api_key_path.read_text(encoding="utf-8").strip()
        return value or None


def _utc_now() -> datetime:
    return datetime.now(UTC)
