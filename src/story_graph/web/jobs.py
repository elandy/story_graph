import asyncio
import threading
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue

from story_graph.pipeline import StoryGraphRunConfig, run_story_graph_pipeline_from_file
from story_graph.progress import PipelineProgressUpdate
from story_graph.web.models import JobState, JobStatus


class JobNotFoundError(FileNotFoundError):
    pass


class JobManager:
    def __init__(self, jobs_root: Path):
        self.jobs_root = Path(jobs_root)
        self._queue: Queue[str | None] = Queue()
        self._stop_event = threading.Event()
        self._write_lock = threading.RLock()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        if self._worker is not None and self._worker.is_alive():
            return
        self._stop_event.clear()
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
        apply_nlp_filter: bool = False,
        max_chunks: int = 0,
    ) -> JobStatus:
        if max_chunks < 0:
            raise ValueError("max_chunks must be zero or a positive integer.")

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
        )

        self._input_path(job_id).write_text(text, encoding="utf-8")
        self._write_status(status)
        self._queue.put(job_id)
        return status

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

        if status.state == JobState.completed:
            return

        self._update_status(
            job_id,
            state=JobState.running,
            stage="running",
            message="Worker started processing.",
            error=None,
            traceback=None,
        )

        input_path = self._input_path(job_id)
        checkpoint_path = self._workspace(job_id) / status.artifacts.checkpoint_file
        graph_path = self._workspace(job_id) / status.artifacts.graph_file
        debug_json_path = self._workspace(job_id) / status.artifacts.debug_relationships_file

        def progress_callback(update: PipelineProgressUpdate) -> None:
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

            self._update_status(job_id, **fields)

        try:
            result = asyncio.run(
                run_story_graph_pipeline_from_file(
                    input_path,
                    StoryGraphRunConfig(
                        apply_nlp_filter=status.apply_nlp_filter,
                        max_chunks=status.max_chunks,
                        debug_json=True,
                        checkpoint_path=checkpoint_path,
                        reset_checkpoint=False,
                        output_html_path=graph_path,
                        debug_json_path=debug_json_path,
                        confirm_extraction=lambda _remaining: True,
                        progress_callback=progress_callback,
                    ),
                )
            )
        except Exception as exc:
            self._update_status(
                job_id,
                state=JobState.failed,
                stage="failed",
                message=f"Job failed: {exc}",
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


def _utc_now() -> datetime:
    return datetime.now(UTC)
