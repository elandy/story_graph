# Story Graph

Story Graph extracts character relationships and sentiments from a book, aggregates them into a graph, and produces an interactive HTML visualization.

The project supports two entry points:

* **CLI** for running the pipeline directly against a local text file.
* **FastAPI web application** that executes the same pipeline asynchronously while persisting jobs and artifacts in PostgreSQL.

---

# Requirements

* Python 3.12+
* PostgreSQL 17+
* Docker & Docker Compose (recommended for the web application)
* Environment variables loaded from `.env`

If you use the local virtual environment:

```powershell
.\.venv\Scripts\python.exe
```

---

# Running the CLI Pipeline

Basic run:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt
```

Process only the first 10 chunks:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10
```

Enable the NLP pre-filter:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --apply-nlp-filter
```

## Useful CLI Options

- `--max-chunks 10`: limit the run to the first N chunks
- `--apply-nlp-filter`: drop chunks with no detected character interaction before extraction
- `--debug-prints`: print extracted relationships per chunk
- `--debug-json`: dump aggregated relationships to `debug_relationships.json`
- `--checkpoint-file <path>`: explicitly choose the resume/checkpoint file
- `--reset-checkpoint`: delete any existing checkpoint file before starting

Before extraction begins, the CLI asks for confirmation:

```text
Proceed with extraction for N remaining chunk(s)? (y/n):
```

---

# Running the Web Application

The recommended approach is Docker Compose:

```bash
docker compose up --build
```

This starts:

* PostgreSQL
* FastAPI
* automatic database migrations via Alembic

The application is then available at:

```text
http://localhost:8000
```

On startup the container automatically executes:

```text
alembic upgrade head
```

ensuring the database schema is up to date.

---

# Database Migrations

This project uses Alembic for schema management.

Generate a migration:

```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:

```bash
alembic upgrade head
```

Show the current database revision:

```bash
alembic current
```

Rollback one revision:

```bash
alembic downgrade -1
```

---

# Web Application

The web application is implemented with **FastAPI**.

Current functionality:

* upload books in UTF-8 `.txt`, `.epub`, `.pdf` or `.docx` format 
* background job processing
* browser polling for progress
* retry failed jobs
* pause running jobs
* delete jobs
* render the generated graph directly in the browser

Unlike earlier versions, the web application **does not rely on per-job filesystem state**.

Job metadata, status, checkpoints and generated artifacts are persisted in PostgreSQL, allowing jobs to survive application restarts without depending on `data/jobs/`.

---

# Outputs

## CLI

The generated graph is written to:

```text
story_graph.html
```

When `--debug-json` is enabled:

```text
debug_relationships.json
```

## Web

The generated graph is stored as a database artifact and served directly by the API through the graph endpoint.

---

# Resume After Interruption

The extraction engine is checkpointed.

After every completed chunk it stores:

* completed chunk index
* chunk fingerprint
* extracted structured result

If the CLI process is interrupted (Ctrl+C, terminal close, crash), rerunning with the same checkpoint continues from the next unfinished chunk.

The web application uses the same checkpointing mechanism internally. Running or queued jobs resume correctly after the application restarts.

Failed jobs are **not** retried automatically. They can be retried through the web interface.

---

# Resume Example

Choose an explicit checkpoint:

```powershell
$ckpt = "data\checkpoints\blindsight.test.json"
```

Run:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10 --checkpoint-file $ckpt --reset-checkpoint
```

Interrupt after several completed chunks.

Resume:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10 --checkpoint-file $ckpt
```

Expected behavior:

* previously completed chunks are loaded
* processing resumes at the first unfinished chunk

---

# Default Checkpoint Location

When `--checkpoint-file` is omitted, checkpoints are written under:

```text
data/checkpoints/
```

Pattern:

```text
data/checkpoints/<book-stem>.<raw|filtered>.<book-path-hash>.json
```

For example:

```text
data/blindsight.txt
```

generates something similar to:

```text
data/checkpoints/blindsight.raw.852d354748c2.json
```

Filtered runs generate a separate checkpoint filename.

---

# Restart From Scratch

Ignore any existing checkpoint:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --reset-checkpoint
```

Or with an explicit checkpoint:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --checkpoint-file data\checkpoints\blindsight.test.json --reset-checkpoint
```

---

# Project Architecture

```
                +----------------+
                |   FastAPI API  |
                +-------+--------+
                        |
                        |
                Job Manager
                        |
         Shared Pipeline Core
                        |
      Relationship Extraction
                        |
                Graph Generation
                        |
                  PostgreSQL
```

The CLI and web application both execute the same extraction pipeline. The web application adds asynchronous job execution, persistence, and an HTTP API on top of the shared processing core.

---

# Notes

* CLI checkpoint compatibility depends on the chunk sequence remaining unchanged.
* Filtered and unfiltered runs should use separate checkpoints.
* Checkpoints are written after every completed chunk.
* Database schema changes are managed exclusively through Alembic migrations.
* The web application stores persistent job state in PostgreSQL rather than the local filesystem.
