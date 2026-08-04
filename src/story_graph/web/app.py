from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from story_graph.ingest.loader import SUPPORTED_EXTENSIONS
from story_graph.web.jobs import (
    JobDeleteError,
    JobManager,
    JobNotFoundError,
    JobPauseError,
    JobRetryError,
)
from story_graph.web.models import JobState, JobStatus
from story_graph.web.session import get_or_create_session_id
from story_graph.web.ui import STATIC_DIR, render_index_page


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JOBS_ROOT = PROJECT_ROOT / "data" / "jobs"
DEFAULT_RETENTION_DAYS = int(os.getenv("STORY_GRAPH_JOB_RETENTION_DAYS", "30"))


manager = JobManager(
    DEFAULT_JOBS_ROOT,
    retention_days=DEFAULT_RETENTION_DAYS,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.start()
    app.state.job_manager = manager
    try:
        yield
    finally:
        manager.stop()


app = FastAPI(
    debug=False,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    response = HTMLResponse(
        render_index_page(
            show_api_key_field=not _server_api_key_configured()
        )
    )
    get_or_create_session_id(request, response)
    return response


@app.get("/jobs")
async def list_jobs(request: Request):
    session_id = get_or_create_session_id(request)
    statuses = request.app.state.job_manager.list_statuses_for_session(session_id)
    return {"jobs": [_serialize_status(s) for s in statuses]}


@app.post("/jobs", status_code=202)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    apply_nlp_filter: bool = Form(False),
    api_key: str = Form(""),
    max_chunks: str | None = Form(None),
    max_chunk_tokens: str | None = Form(None),
    max_paragraphs_per_chunk: str | None = Form(None),
    batch_size: str | None = Form(None),
    max_batch_tokens: str | None = Form(None),
):
    filename = Path(file.filename or "").name

    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        return JSONResponse(
            {
                "error": (
                    "Unsupported file type. "
                    f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
                )
            },
            status_code=400,
        )

    raw_bytes = await file.read()

    if not raw_bytes:
        return JSONResponse(
            {"error": "The uploaded file is empty."},
            status_code=400,
        )

    provider_api_key = (
        None
        if _server_api_key_configured()
        else api_key.strip()
    )

    try:
        if not _server_api_key_configured() and not provider_api_key:
            raise ValueError("An API key is required.")

        session_id = get_or_create_session_id(request)

        status = request.app.state.job_manager.create_job(
            session_id=session_id,
            upload_name=filename,
            file_bytes=raw_bytes,
            provider_api_key=provider_api_key,
            apply_nlp_filter=apply_nlp_filter,
            max_chunks=_parse_max_chunks(max_chunks),
            max_chunk_tokens=_parse_non_negative_int(
                max_chunk_tokens,
                field_name="max_chunk_tokens",
                default=3000,
            ),
            max_paragraphs_per_chunk=_parse_non_negative_int(
                max_paragraphs_per_chunk,
                field_name="max_paragraphs_per_chunk",
                default=80,
            ),
            batch_size=_parse_positive_int(
                batch_size,
                field_name="batch_size",
                default=4,
            ),
            max_batch_tokens=_parse_positive_int(
                max_batch_tokens,
                field_name="max_batch_tokens",
                default=9000,
            ),
        )

    except UnicodeDecodeError:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            return JSONResponse(
                {
                    "error": (
                        "Unsupported file type. "
                        f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
                    )
                },
                status_code=400,
            )

    except ValueError as exc:
        return JSONResponse(
            {"error": str(exc)},
            status_code=400,
        )

    return _serialize_status(status)


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    try:
        session_id = get_or_create_session_id(request)
        status = request.app.state.job_manager.get_status_for_session(
            job_id,
            session_id,
        )
    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)

    return _serialize_status(status)


@app.post("/jobs/{job_id}/retry", status_code=202)
async def retry_job(job_id: str, request: Request):
    try:
        session_id = get_or_create_session_id(request)

        request.app.state.job_manager.get_status_for_session(
            job_id,
            session_id,
        )

        status = request.app.state.job_manager.retry_job(job_id)

    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    except JobRetryError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return _serialize_status(status)


@app.post("/jobs/{job_id}/pause", status_code=202)
async def pause_job(job_id: str, request: Request):
    try:
        session_id = get_or_create_session_id(request)

        request.app.state.job_manager.get_status_for_session(
            job_id,
            session_id,
        )

        status = request.app.state.job_manager.pause_job(job_id)

    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    except JobPauseError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return _serialize_status(status)


@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request):
    try:
        session_id = get_or_create_session_id(request)

        request.app.state.job_manager.get_status_for_session(
            job_id,
            session_id,
        )

        request.app.state.job_manager.delete_job(job_id)

    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    except JobDeleteError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return Response(status_code=204)


@app.get("/jobs/{job_id}/graph")
async def get_job_graph(job_id: str, request: Request):
    manager: JobManager = request.app.state.job_manager

    try:
        session_id = get_or_create_session_id(request)

        status = manager.get_status_for_session(
            job_id,
            session_id,
        )

    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)

    if status.state != JobState.completed:
        return JSONResponse(
            {"error": "Graph output is not ready yet."},
            status_code=409,
        )

    graph_bytes = manager.graph_bytes(job_id)

    if graph_bytes is None:
        return JSONResponse(
            {"error": "Graph output artifact is missing."},
            status_code=404,
        )

    return Response(
        graph_bytes,
        media_type="text/html; charset=utf-8",
    )


@app.get("/jobs/{job_id}/graph/download")
async def download_job_graph(request: Request, job_id: str):
    manager = request.app.state.job_manager

    try:
        session_id = get_or_create_session_id(request)
        status = manager.get_status_for_session(job_id, session_id)
    except JobNotFoundError:
        return JSONResponse(
            {"error": "Job not found."},
            status_code=404,
        )

    if status.state != JobState.completed:
        return JSONResponse(
            {"error": "Graph output is not ready yet."},
            status_code=409,
        )

    graph_bytes = manager.graph_bytes(job_id)

    if graph_bytes is None:
        return JSONResponse(
            {"error": "Graph output artifact is missing."},
            status_code=404,
        )

    filename = Path(status.original_filename).stem + "_story_graph.html"

    return Response(
        graph_bytes,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )

def _serialize_status(status: JobStatus) -> dict:
    payload = status.model_dump(
        mode="json",
        exclude={
            "session_id",
            "workspace",
        },
    )

    payload["graph_url"] = (
        f"/jobs/{status.job_id}/graph"
        if status.state == JobState.completed
        else None
    )

    payload["graph_download_url"] = (
        f"/jobs/{status.job_id}/graph/download"
        if status.state == JobState.completed
        else None
    )

    return payload


def _parse_max_chunks(raw_value) -> int:
    if raw_value in (None, ""):
        return 0

    value = int(raw_value)

    if value < 0:
        raise ValueError("max_chunks must be zero or a positive integer.")

    return value


def _parse_non_negative_int(raw_value, *, field_name: str, default: int = 0) -> int:
    if raw_value in (None, ""):
        return default

    value = int(raw_value)

    if value < 0:
        raise ValueError(f"{field_name} must be zero or a positive integer.")

    return value


def _parse_positive_int(raw_value, *, field_name: str, default: int) -> int:
    if raw_value in (None, ""):
        return default

    value = int(raw_value)

    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def _server_api_key_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )