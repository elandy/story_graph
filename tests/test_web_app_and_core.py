import asyncio
import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from story_graph.extraction.models import (
    Character,
    ExtractionResult,
    Relationship,
    RelationshipType,
    Sentiment,
    SentimentType,
)
from story_graph.pipeline import StoryGraphRunConfig, run_story_graph_pipeline_from_file
from story_graph.web.app import DEFAULT_JOBS_ROOT, create_app
from story_graph.web.jobs import JobManager
from story_graph.web.models import JobState, JobStatus
from story_graph.web.ui import render_index_page


def _build_extraction_result(evidence: str) -> ExtractionResult:
    return ExtractionResult(
        characters=[
            Character(name="Alice", aliases=["A."]),
            Character(name="Bob", aliases=["B."]),
        ],
        relationships=[
            Relationship(
                source="Alice",
                target="Bob",
                relation=RelationshipType.friend,
                evidence=evidence,
            )
        ],
        sentiments=[
            Sentiment(
                source="Alice",
                target="Bob",
                sentiment=SentimentType.trust,
                evidence=evidence,
            )
        ],
    )


def _wait_for(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class SharedPipelineCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_story_graph_pipeline_from_file_writes_outputs(self):
        progress_messages = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "story.txt"
            input_path.write_text("Alice meets Bob.", encoding="utf-8")

            with patch(
                "story_graph.extraction.pipeline.extract_relationships",
                new=AsyncMock(return_value=_build_extraction_result("Alice meets Bob.")),
            ):
                result = await run_story_graph_pipeline_from_file(
                    input_path,
                    StoryGraphRunConfig(
                        checkpoint_path=temp_path / "checkpoint.json",
                        output_html_path=temp_path / "graph.html",
                        debug_json=True,
                        debug_json_path=temp_path / "debug_relationships.json",
                        confirm_extraction=lambda _remaining: True,
                        progress_callback=lambda update: progress_messages.append(update.message),
                    ),
                )

            self.assertEqual(result.total_chunks_to_process, 1)
            self.assertEqual(result.total_relationships, 1)
            self.assertEqual(result.total_sentiments, 1)
            self.assertTrue((temp_path / "checkpoint.json").exists())
            self.assertTrue((temp_path / "graph.html").exists())
            self.assertTrue((temp_path / "debug_relationships.json").exists())
            self.assertTrue(
                any(message.startswith("Extraction checkpoint:") for message in progress_messages)
            )
            self.assertTrue(
                any(message.startswith("Graph HTML written to") for message in progress_messages)
            )


class UiMarkupTests(unittest.TestCase):
    def test_rendered_page_uses_external_assets(self):
        html = render_index_page()

        self.assertIn('/static/app.css', html)
        self.assertIn('/static/app.js', html)
        self.assertIn('job-search-input', html)
        self.assertIn('job-state-filter', html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn('name="api_key"', html)

    def test_rendered_page_can_include_api_key_field(self):
        html = render_index_page(show_api_key_field=True)

        self.assertIn('name="api_key"', html)
        self.assertIn('type="password"', html)


class WebAppTests(unittest.TestCase):
    def test_default_jobs_root_is_repo_data_jobs(self):
        self.assertTrue(DEFAULT_JOBS_ROOT.is_absolute())
        self.assertEqual(DEFAULT_JOBS_ROOT, ROOT / "data" / "jobs")

    def test_upload_job_completes_and_serves_graph(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True), patch(
                "story_graph.extraction.pipeline.extract_relationships",
                new=AsyncMock(return_value=_build_extraction_result("Alice meets Bob.")),
            ):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.post(
                        "/jobs",
                        data={"api_key": "test-api-key"},
                        files={"file": ("story.txt", b"Alice meets Bob.", "text/plain")},
                    )
                    self.assertEqual(response.status_code, 202)
                    payload = response.json()
                    job_id = payload["job_id"]

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "completed"
                        )
                    )

                    status = client.get(f"/jobs/{job_id}").json()
                    self.assertEqual(status["state"], "completed")
                    self.assertEqual(status["completed_chunks"], 1)
                    self.assertEqual(status["total_relationships"], 1)

                    jobs_response = client.get("/jobs")
                    self.assertEqual(jobs_response.status_code, 200)
                    jobs_payload = jobs_response.json()
                    self.assertEqual(len(jobs_payload["jobs"]), 1)
                    self.assertEqual(jobs_payload["jobs"][0]["job_id"], job_id)

                    retry_response = client.post(f"/jobs/{job_id}/retry")
                    self.assertEqual(retry_response.status_code, 409)

                    graph_response = client.get(f"/jobs/{job_id}/graph")
                    self.assertEqual(graph_response.status_code, 200)
                    self.assertIn("Alice", graph_response.text)

                    workspace = jobs_root / job_id
                    self.assertTrue((workspace / "input.txt").exists())
                    self.assertTrue((workspace / ".provider_api_key").exists())
                    self.assertTrue((workspace / "checkpoint.json").exists())
                    self.assertTrue((workspace / "story_graph.html").exists())
                    self.assertTrue((workspace / "debug_relationships.json").exists())
                    self.assertTrue((workspace / "status.json").exists())

    def test_upload_requires_api_key_when_server_key_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.post(
                        "/jobs",
                        files={"file": ("story.txt", b"Alice meets Bob.", "text/plain")},
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["error"], "An API key is required.")

    def test_index_hides_api_key_field_when_server_key_is_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {"GOOGLE_API_KEY": "server-key"}, clear=True):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.get("/")
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn('name="api_key"', response.text)

    def test_index_shows_api_key_field_when_server_key_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.get("/")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('name="api_key"', response.text)

    def test_completed_job_can_be_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True), patch(
                "story_graph.extraction.pipeline.extract_relationships",
                new=AsyncMock(return_value=_build_extraction_result("Alice meets Bob.")),
            ):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.post(
                        "/jobs",
                        data={"api_key": "test-api-key"},
                        files={"file": ("story.txt", b"Alice meets Bob.", "text/plain")},
                    )
                    self.assertEqual(response.status_code, 202)
                    job_id = response.json()["job_id"]

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "completed"
                        )
                    )

                    delete_response = client.delete(f"/jobs/{job_id}")
                    self.assertEqual(delete_response.status_code, 204)
                    self.assertFalse((jobs_root / job_id).exists())

                    status_response = client.get(f"/jobs/{job_id}")
                    self.assertEqual(status_response.status_code, 404)

                    jobs_response = client.get("/jobs")
                    self.assertEqual(jobs_response.status_code, 200)
                    self.assertEqual(jobs_response.json()["jobs"], [])

    def test_static_assets_are_served(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with TestClient(create_app(jobs_root=jobs_root)) as client:
                css_response = client.get("/static/app.css")
                self.assertEqual(css_response.status_code, 200)
                self.assertIn(":root", css_response.text)

                js_response = client.get("/static/app.js")
                self.assertEqual(js_response.status_code, 200)
                self.assertIn("const form = document.getElementById", js_response.text)
                self.assertIn("window.confirm", js_response.text)

    def test_second_job_stays_queued_while_first_job_is_running(self):
        first_started = threading.Event()
        release_first = threading.Event()

        async def fake_extract(text: str):
            if text.startswith("First"):
                first_started.set()
                await asyncio.to_thread(release_first.wait, 2)
            return _build_extraction_result(text)

        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True), patch("story_graph.extraction.pipeline.extract_relationships", new=fake_extract):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    first_response = client.post(
                        "/jobs",
                        data={"api_key": "test-api-key"},
                        files={"file": ("first.txt", b"First story paragraph.", "text/plain")},
                    )
                    self.assertEqual(first_response.status_code, 202)
                    first_job_id = first_response.json()["job_id"]

                    self.assertTrue(first_started.wait(timeout=2))
                    first_status = client.get(f"/jobs/{first_job_id}").json()
                    self.assertEqual(first_status["state"], "running")

                    second_response = client.post(
                        "/jobs",
                        data={"api_key": "test-api-key"},
                        files={"file": ("second.txt", b"Second story paragraph.", "text/plain")},
                    )
                    self.assertEqual(second_response.status_code, 202)
                    second_job_id = second_response.json()["job_id"]

                    second_status = client.get(f"/jobs/{second_job_id}").json()
                    self.assertEqual(second_status["state"], "queued")

                    release_first.set()

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{first_job_id}").json()["state"] == "completed"
                        )
                    )
                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{second_job_id}").json()["state"] == "completed"
                        )
                    )

    def test_failed_job_can_resume_from_checkpoint(self):
        calls = []
        failed_once = False

        async def flaky_extract(text: str):
            nonlocal failed_once
            calls.append(text)
            if "Paragraph 40." in text and not failed_once:
                failed_once = True
                raise ValueError("invalid extraction payload")
            return _build_extraction_result(text.split("\n\n")[0])

        paragraphs = [f"Paragraph {index}." for index in range(41)]
        book = "\n\n".join(paragraphs).encode("utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True), patch("story_graph.extraction.pipeline.extract_relationships", new=flaky_extract), patch(
                "story_graph.extraction.pipeline.asyncio.sleep",
                new=AsyncMock(),
            ):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.post(
                        "/jobs",
                        data={
                            "api_key": "test-api-key",
                            "max_chunks": "2",
                            "max_paragraphs_per_chunk": "40",
                            "batch_size": "1",
                        },
                        files={"file": ("story.txt", book, "text/plain")},
                    )
                    self.assertEqual(response.status_code, 202)
                    job_id = response.json()["job_id"]

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "failed"
                        )
                    )

                    failed_status = client.get(f"/jobs/{job_id}").json()
                    self.assertEqual(failed_status["completed_chunks"], 1)
                    self.assertTrue((jobs_root / job_id / "checkpoint.json").exists())

                    retry_response = client.post(f"/jobs/{job_id}/retry")
                    self.assertEqual(retry_response.status_code, 202)
                    self.assertEqual(retry_response.json()["state"], "queued")

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "completed"
                        )
                    )

                    completed_status = client.get(f"/jobs/{job_id}").json()
                    self.assertEqual(completed_status["completed_chunks"], 2)
                    self.assertEqual(
                        sum("Paragraph 0." in call for call in calls),
                        1,
                    )
                    self.assertEqual(
                        sum("Paragraph 40." in call for call in calls),
                        2,
                    )

    def test_running_job_can_pause_and_resume_after_current_batch(self):
        first_started = threading.Event()
        release_first = threading.Event()
        calls = []

        async def fake_extract(text: str):
            calls.append(text)
            if text == "First paragraph.":
                first_started.set()
                await asyncio.to_thread(release_first.wait, 2)
            return _build_extraction_result(text)

        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True), patch("story_graph.extraction.pipeline.extract_relationships", new=fake_extract):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.post(
                        "/jobs",
                        data={
                            "api_key": "test-api-key",
                            "max_paragraphs_per_chunk": "1",
                            "batch_size": "1",
                        },
                        files={
                            "file": (
                                "story.txt",
                                b"First paragraph.\n\nSecond paragraph.",
                                "text/plain",
                            )
                        },
                    )
                    self.assertEqual(response.status_code, 202)
                    job_id = response.json()["job_id"]

                    self.assertTrue(first_started.wait(timeout=2))

                    pause_response = client.post(f"/jobs/{job_id}/pause")
                    self.assertEqual(pause_response.status_code, 202)
                    self.assertTrue(pause_response.json()["pause_requested"])

                    release_first.set()

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "paused"
                        )
                    )

                    paused_status = client.get(f"/jobs/{job_id}").json()
                    self.assertEqual(paused_status["completed_chunks"], 1)
                    self.assertFalse(paused_status["pause_requested"])

                    retry_response = client.post(f"/jobs/{job_id}/retry")
                    self.assertEqual(retry_response.status_code, 202)
                    self.assertEqual(retry_response.json()["state"], "queued")

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "completed"
                        )
                    )

                    completed_status = client.get(f"/jobs/{job_id}").json()
                    self.assertEqual(completed_status["completed_chunks"], 2)
                    self.assertEqual(calls, ["First paragraph.", "Second paragraph."])

    def test_manager_cleans_up_expired_terminal_jobs_on_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"
            expired_job_id = "expiredjob"
            fresh_job_id = "freshjob"

            for job_id, state, age_days in (
                (expired_job_id, JobState.completed, 45),
                (fresh_job_id, JobState.completed, 1),
            ):
                workspace = jobs_root / job_id
                workspace.mkdir(parents=True, exist_ok=True)
                updated_at = datetime.now(UTC) - timedelta(days=age_days)
                status = JobStatus(
                    job_id=job_id,
                    state=state,
                    stage=state.value,
                    message="stored job",
                    created_at=updated_at,
                    updated_at=updated_at,
                    original_filename=f"{job_id}.txt",
                    workspace=str(workspace),
                )
                (workspace / "status.json").write_text(
                    status.model_dump_json(indent=2),
                    encoding="utf-8",
                )

            manager = JobManager(jobs_root, retention_days=30)
            manager.start()
            manager.stop()

            self.assertFalse((jobs_root / expired_job_id).exists())
            self.assertTrue((jobs_root / fresh_job_id).exists())

    def test_transient_extraction_error_is_retried_without_manual_resume(self):
        attempts = 0

        async def flaky_extract(text: str, api_key: str | None = None):
            nonlocal attempts
            attempts += 1
            self.assertEqual(api_key, "user-api-key")
            if attempts == 1:
                raise RuntimeError("temporary outage")
            return _build_extraction_result(text)

        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_root = Path(temp_dir) / "jobs"

            with patch.dict("os.environ", {}, clear=True), patch(
                "story_graph.extraction.pipeline.extract_relationships",
                new=flaky_extract,
            ), patch(
                "story_graph.extraction.pipeline.asyncio.sleep",
                new=AsyncMock(),
            ):
                with TestClient(create_app(jobs_root=jobs_root)) as client:
                    response = client.post(
                        "/jobs",
                        data={"api_key": "user-api-key"},
                        files={"file": ("story.txt", b"Alice meets Bob.", "text/plain")},
                    )
                    self.assertEqual(response.status_code, 202)
                    job_id = response.json()["job_id"]

                    self.assertTrue(
                        _wait_for(
                            lambda: client.get(f"/jobs/{job_id}").json()["state"] == "completed"
                        )
                    )

                    status = client.get(f"/jobs/{job_id}").json()
                    self.assertEqual(status["state"], "completed")
                    self.assertEqual(status["completed_chunks"], 1)
                    self.assertEqual(attempts, 2)
