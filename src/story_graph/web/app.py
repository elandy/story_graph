from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from story_graph.web.jobs import JobDeleteError, JobManager, JobNotFoundError, JobPauseError, JobRetryError
from story_graph.web.models import JobState, JobStatus
from story_graph.web.ui import STATIC_DIR, render_index_page


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JOBS_ROOT = PROJECT_ROOT / "data" / "jobs"


def create_app(jobs_root: Path | None = None) -> Starlette:
    manager = JobManager(jobs_root or DEFAULT_JOBS_ROOT)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        manager.start()
        app.state.job_manager = manager
        try:
            yield
        finally:
            manager.stop()

    app = Starlette(
        debug=False,
        lifespan=lifespan,
        routes=[
            Route("/", endpoint=index_page),
            Route("/jobs", endpoint=list_jobs, methods=["GET"]),
            Route("/jobs", endpoint=create_job, methods=["POST"]),
            Route("/jobs/{job_id:str}", endpoint=get_job_status, methods=["GET"]),
            Route("/jobs/{job_id:str}", endpoint=delete_job, methods=["DELETE"]),
            Route("/jobs/{job_id:str}/pause", endpoint=pause_job, methods=["POST"]),
            Route("/jobs/{job_id:str}/retry", endpoint=retry_job, methods=["POST"]),
            Route("/jobs/{job_id:str}/graph", endpoint=get_job_graph, methods=["GET"]),
        ],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app

async def index_page(_request: Request) -> HTMLResponse:
    return HTMLResponse(render_index_page())


async def list_jobs(request: Request) -> JSONResponse:
    statuses = request.app.state.job_manager.list_statuses()
    return JSONResponse({"jobs": [_serialize_status(status) for status in statuses]})


async def create_job(request: Request) -> JSONResponse:
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        return JSONResponse({"error": "A .txt file upload is required."}, status_code=400)

    filename = Path(upload.filename or "").name
    if not filename.lower().endswith(".txt"):
        return JSONResponse({"error": "Only .txt uploads are supported."}, status_code=400)

    raw_bytes = await upload.read()
    await upload.close()
    if not raw_bytes:
        return JSONResponse({"error": "The uploaded file is empty."}, status_code=400)

    apply_nlp_filter = str(form.get("apply_nlp_filter", "")).lower() in {
        "1",
        "true",
        "on",
        "yes",
    }

    try:
        max_chunks = _parse_max_chunks(form.get("max_chunks"))
        max_chunk_tokens = _parse_non_negative_int(
            form.get("max_chunk_tokens"),
            field_name="max_chunk_tokens",
            default=3000,
        )
        max_paragraphs_per_chunk = _parse_non_negative_int(
            form.get("max_paragraphs_per_chunk"),
            field_name="max_paragraphs_per_chunk",
            default=80,
        )
        batch_size = _parse_positive_int(
            form.get("batch_size"),
            field_name="batch_size",
            default=4,
        )
        status = request.app.state.job_manager.create_job(
            upload_name=filename,
            file_bytes=raw_bytes,
            apply_nlp_filter=apply_nlp_filter,
            max_chunks=max_chunks,
            max_chunk_tokens=max_chunk_tokens,
            max_paragraphs_per_chunk=max_paragraphs_per_chunk,
            batch_size=batch_size,
        )
    except UnicodeDecodeError:
        return JSONResponse(
            {"error": "Only UTF-8 encoded .txt uploads are supported."},
            status_code=400,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return JSONResponse(_serialize_status(status), status_code=202)


async def get_job_status(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    try:
        status = request.app.state.job_manager.get_status(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)

    return JSONResponse(_serialize_status(status))


async def retry_job(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    try:
        status = request.app.state.job_manager.retry_job(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    except JobRetryError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return JSONResponse(_serialize_status(status), status_code=202)


async def pause_job(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    try:
        status = request.app.state.job_manager.pause_job(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    except JobPauseError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return JSONResponse(_serialize_status(status), status_code=202)


async def delete_job(request: Request) -> Response:
    job_id = request.path_params["job_id"]
    try:
        request.app.state.job_manager.delete_job(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    except JobDeleteError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)

    return Response(status_code=204)


async def get_job_graph(request: Request):
    job_id = request.path_params["job_id"]
    manager: JobManager = request.app.state.job_manager

    try:
        status = manager.get_status(job_id)
    except JobNotFoundError:
        return JSONResponse({"error": "Job not found."}, status_code=404)

    if status.state != JobState.completed:
        return JSONResponse({"error": "Graph output is not ready yet."}, status_code=409)

    graph_path = manager.graph_path(job_id)
    if not graph_path.exists():
        return JSONResponse({"error": "Graph output file is missing."}, status_code=404)

    return FileResponse(graph_path, media_type="text/html")


def _serialize_status(status: JobStatus) -> dict:
    payload = status.model_dump(mode="json")
    payload["graph_url"] = (
        f"/jobs/{status.job_id}/graph"
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


app = create_app()
