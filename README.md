# Story Graph

Extracts character relationships and sentiments from a book, aggregates them into a graph, and writes an interactive HTML visualization.

## Requirements

- Python 3.12+
- Project dependencies installed
- Environment variables loaded through `.env`

If you use the local virtualenv in this repo, commands below assume:

```powershell
.\.venv\Scripts\python.exe
```

## Run The Pipeline

Basic run:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt
```

Process only the first 10 chunks:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10
```

Run with the NLP pre-filter enabled:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --apply-nlp-filter
```

Useful optional flags:

- `--max-chunks 10`: limit the run to the first N chunks
- `--apply-nlp-filter`: drop chunks with no detected character interaction before extraction
- `--debug-prints`: print extracted relationships per chunk
- `--debug-json`: dump aggregated relationships to `debug_relationships.json`
- `--checkpoint-file <path>`: explicitly choose the resume/checkpoint file
- `--reset-checkpoint`: delete any existing checkpoint file before starting

The script asks for confirmation before extraction starts:

```text
Proceed with extraction for N remaining chunk(s)? (y/n):
```

Type `y` to continue.

## Outputs

The main output HTML is written to:

```text
story_graph.html
```

If `--debug-json` is enabled, this file is also written:

```text
debug_relationships.json
```

## Resume After Interruption Or Error

The extraction stage is resumable. After each completed chunk, the pipeline saves a checkpoint file containing:

- the completed chunk index
- the chunk fingerprint
- the extracted structured result

If the process stops because of `Ctrl+C`, a terminal close, or an extraction error, rerun the command with the same book and checkpoint file. The pipeline reloads completed chunks and continues from the next unfinished chunk.

### Example: stop after 5 chunks, resume to 10

Use a fixed checkpoint file so the test is explicit:

```powershell
$ckpt = "data\checkpoints\blindsight.test.json"
```

Start a clean run:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10 --checkpoint-file $ckpt --reset-checkpoint
```

When prompted, type:

```text
y
```

If you want to interrupt after chunk 5, wait until chunk 5 has finished saving and the program prints:

```text
Processing chunk 6/10
```

Then press `Ctrl+C`.

Resume with the same checkpoint file:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10 --checkpoint-file $ckpt
```

When prompted, type:

```text
y
```

Expected resume behavior:

- it prints `Loaded 5/10 chunks from checkpoint: ...`
- it starts again at `Processing chunk 6/10`

You can inspect how many chunks are already saved:

```powershell
((Get-Content $ckpt -Raw | ConvertFrom-Json).completed).Count
```

## Default Checkpoint Location

If you do not pass `--checkpoint-file`, the pipeline generates one automatically under:

```text
data/checkpoints/
```

Pattern:

```text
data/checkpoints/<book-stem>.<raw|filtered>.<book-path-hash>.json
```

Details:

- `<book-stem>` comes from the input filename
- `raw` is used for normal runs
- `filtered` is used when `--apply-nlp-filter` is enabled
- `<book-path-hash>` is derived from the absolute input path

For this repo, the default checkpoint file for:

```text
data\blindsight.txt
```

is:

```text
data\checkpoints\blindsight.raw.852d354748c2.json
```

If you run with `--apply-nlp-filter`, the generated filename changes to the `filtered` variant.

## Restart From Scratch

If you want to ignore previous progress and re-extract from chunk 1, use:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10 --reset-checkpoint
```

Or, if you are using a custom checkpoint path:

```powershell
.\.venv\Scripts\python.exe -m story_graph.main data\blindsight.txt --max-chunks 10 --checkpoint-file data\checkpoints\blindsight.test.json --reset-checkpoint
```

## Notes

- Resume works only when the checkpoint still matches the same chunk sequence. If the book content changes, the checkpoint is rejected.
- Switching between filtered and unfiltered runs changes the chunk list, so those runs should use separate checkpoint files.
- Checkpoints are written after each completed chunk, not before a chunk starts.
