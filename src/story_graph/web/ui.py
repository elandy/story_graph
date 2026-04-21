def render_index_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Story Graph Studio</title>
  <style>
    :root {
      --bg: #f6efe4;
      --bg-accent: #dfe9d7;
      --panel: rgba(255, 251, 245, 0.9);
      --ink: #1f1d1b;
      --muted: #665f58;
      --line: rgba(31, 29, 27, 0.12);
      --primary: #14532d;
      --primary-strong: #0f3f22;
      --warm: #bf5b31;
      --shadow: 0 22px 50px rgba(53, 44, 33, 0.12);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Aptos", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(191, 91, 49, 0.15), transparent 28%),
        radial-gradient(circle at bottom right, rgba(20, 83, 45, 0.18), transparent 32%),
        linear-gradient(145deg, var(--bg) 0%, var(--bg-accent) 100%);
    }

    .shell {
      width: min(1180px, calc(100% - 2rem));
      margin: 0 auto;
      padding: 2rem 0 2.5rem;
      display: grid;
      gap: 1.25rem;
    }

    .hero,
    .panel,
    .viewer {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }

    .hero {
      padding: 1.5rem 1.6rem;
      display: grid;
      gap: 0.75rem;
    }

    .eyebrow {
      display: inline-flex;
      width: fit-content;
      padding: 0.35rem 0.7rem;
      border-radius: 999px;
      background: rgba(20, 83, 45, 0.1);
      color: var(--primary);
      font-size: 0.8rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      font-family: "Iowan Old Style", Georgia, serif;
      font-size: clamp(2.1rem, 5vw, 3.6rem);
      line-height: 0.95;
      max-width: 12ch;
    }

    .hero p {
      margin: 0;
      max-width: 62ch;
      color: var(--muted);
      line-height: 1.6;
    }

    .panel {
      padding: 1.2rem;
      display: grid;
      gap: 1rem;
    }

    form {
      display: grid;
      gap: 1rem;
    }

    .dropzone {
      display: grid;
      gap: 0.45rem;
      padding: 1.25rem;
      border: 1.5px dashed rgba(20, 83, 45, 0.25);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.55);
      cursor: pointer;
    }

    .dropzone strong {
      font-size: 1rem;
    }

    .dropzone span {
      color: var(--muted);
      font-size: 0.95rem;
    }

    input[type="file"] {
      width: 100%;
    }

    .options {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }

    .field {
      display: grid;
      gap: 0.35rem;
      padding: 0.9rem 1rem;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.65);
    }

    .field input[type="number"] {
      width: 100%;
      border: 1px solid rgba(31, 29, 27, 0.12);
      border-radius: 12px;
      padding: 0.65rem 0.8rem;
      font: inherit;
      background: rgba(255, 255, 255, 0.9);
    }

    .checkbox {
      display: flex;
      gap: 0.75rem;
      align-items: start;
      color: var(--muted);
      line-height: 1.4;
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 0.9rem 1.2rem;
      width: fit-content;
      font: inherit;
      font-weight: 600;
      color: white;
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-strong) 100%);
      cursor: pointer;
      box-shadow: 0 12px 24px rgba(20, 83, 45, 0.2);
    }

    button[disabled] {
      opacity: 0.65;
      cursor: wait;
    }

    .status-card {
      display: grid;
      gap: 0.85rem;
      padding: 1.1rem 1.15rem;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.75);
    }

    .status-head {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.35rem 0.7rem;
      border-radius: 999px;
      font-size: 0.85rem;
      background: rgba(191, 91, 49, 0.12);
      color: var(--warm);
    }

    .meta {
      display: flex;
      gap: 0.8rem;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .meta a {
      color: var(--primary);
      text-decoration: none;
      font-weight: 600;
    }

    progress {
      width: 100%;
      height: 14px;
      border: 0;
      border-radius: 999px;
      overflow: hidden;
    }

    progress::-webkit-progress-bar {
      background: rgba(31, 29, 27, 0.08);
    }

    progress::-webkit-progress-value {
      background: linear-gradient(90deg, var(--warm), var(--primary));
    }

    .progress-meta {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 0.92rem;
    }

    .viewer {
      padding: 0.8rem;
      min-height: 72vh;
      position: relative;
      overflow: hidden;
    }

    .viewer-empty {
      min-height: calc(72vh - 1.6rem);
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
      padding: 1.5rem;
      border-radius: 18px;
      background:
        linear-gradient(160deg, rgba(20, 83, 45, 0.08), rgba(191, 91, 49, 0.1)),
        rgba(255, 255, 255, 0.65);
      border: 1px dashed rgba(20, 83, 45, 0.16);
    }

    iframe {
      width: 100%;
      min-height: calc(72vh - 1.6rem);
      border: 0;
      border-radius: 18px;
      background: white;
    }

    @media (max-width: 700px) {
      .shell {
        width: min(100% - 1rem, 1180px);
        padding-top: 1rem;
      }

      .hero,
      .panel,
      .viewer {
        border-radius: 20px;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="eyebrow">Story Graph Studio</span>
      <h1>Upload a plain-text story. Get the graph back in the browser.</h1>
      <p>
        Each upload becomes an isolated job workspace with its own source file, checkpoint,
        graph HTML, debug JSON, and status metadata. The UI polls chunk-by-chunk progress while
        the backend keeps request handling free.
      </p>
    </section>

    <section class="panel">
      <form id="upload-form">
        <label class="dropzone" for="file-input">
          <strong id="selected-file">Choose a UTF-8 .txt file</strong>
          <span>The first pass reuses the existing generated HTML graph directly.</span>
          <input id="file-input" name="file" type="file" accept=".txt,text/plain" required>
        </label>

        <div class="options">
          <label class="field">
            <span>Max chunks</span>
            <input name="max_chunks" type="number" min="0" step="1" placeholder="0 means full text">
          </label>

          <label class="field checkbox">
            <input name="apply_nlp_filter" type="checkbox" value="true">
            <span>Apply the optional NLP pre-filter before extraction.</span>
          </label>
        </div>

        <button id="submit-button" type="submit">Start Processing</button>
      </form>

      <section class="status-card">
        <div class="status-head">
          <div class="meta">
            <span id="job-id">No job yet.</span>
            <a id="graph-link" href="#" target="_blank" hidden>Open graph</a>
          </div>
          <span class="pill" id="state-pill">idle</span>
        </div>
        <div id="status-message">Upload a text file to create a processing job.</div>
        <progress id="progress-bar" max="100" value="0"></progress>
        <div class="progress-meta">
          <span id="chunk-stats">0 / 0 chunks</span>
          <span id="stage-stats">waiting</span>
        </div>
      </section>
    </section>

    <section class="viewer">
      <div class="viewer-empty" id="viewer-empty">
        The generated graph will appear here once the job reaches <strong>completed</strong>.
      </div>
      <iframe id="graph-frame" title="Story graph output" hidden></iframe>
    </section>
  </main>

  <script>
    const form = document.getElementById("upload-form");
    const fileInput = document.getElementById("file-input");
    const selectedFile = document.getElementById("selected-file");
    const submitButton = document.getElementById("submit-button");
    const jobIdNode = document.getElementById("job-id");
    const graphLink = document.getElementById("graph-link");
    const statePill = document.getElementById("state-pill");
    const statusMessage = document.getElementById("status-message");
    const progressBar = document.getElementById("progress-bar");
    const chunkStats = document.getElementById("chunk-stats");
    const stageStats = document.getElementById("stage-stats");
    const viewerEmpty = document.getElementById("viewer-empty");
    const graphFrame = document.getElementById("graph-frame");

    let activeJobId = null;

    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      selectedFile.textContent = file ? file.name : "Choose a UTF-8 .txt file";
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      if (!fileInput.files || !fileInput.files[0]) {
        updateStatus({
          state: "idle",
          stage: "validation",
          message: "Choose a .txt file first.",
          completed_chunks: 0,
          total_chunks_to_process: 0
        });
        return;
      }

      submitButton.disabled = true;
      updateStatus({
        state: "queued",
        stage: "uploading",
        message: "Uploading file and creating job workspace.",
        completed_chunks: 0,
        total_chunks_to_process: 0
      });

      try {
        const response = await fetch("/jobs", {
          method: "POST",
          body: new FormData(form)
        });
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.error || "Upload failed.");
        }

        activeJobId = payload.job_id;
        updateStatus(payload);
        graphFrame.hidden = true;
        viewerEmpty.hidden = false;
        graphLink.hidden = true;
        await pollStatus(activeJobId);
      } catch (error) {
        updateStatus({
          state: "failed",
          stage: "error",
          message: error.message,
          completed_chunks: 0,
          total_chunks_to_process: 0
        });
      } finally {
        submitButton.disabled = false;
      }
    });

    async function pollStatus(jobId) {
      while (activeJobId === jobId) {
        const response = await fetch(`/jobs/${jobId}`);
        const payload = await response.json();

        if (!response.ok) {
          updateStatus({
            state: "failed",
            stage: "error",
            message: payload.error || "Failed to fetch job status.",
            completed_chunks: 0,
            total_chunks_to_process: 0
          });
          return;
        }

        updateStatus(payload);

        if (payload.state === "completed") {
          const graphUrl = `${payload.graph_url}?t=${Date.now()}`;
          graphFrame.src = graphUrl;
          graphFrame.hidden = false;
          viewerEmpty.hidden = true;
          graphLink.href = payload.graph_url;
          graphLink.hidden = false;
          return;
        }

        if (payload.state === "failed") {
          graphFrame.hidden = true;
          viewerEmpty.hidden = false;
          graphLink.hidden = true;
          return;
        }

        await new Promise((resolve) => window.setTimeout(resolve, 1500));
      }
    }

    function updateStatus(status) {
      const completed = Number(status.completed_chunks || 0);
      const total = Number(status.total_chunks_to_process || 0);
      const percent = total > 0
        ? Math.min(100, Math.round((completed / total) * 100))
        : (status.state === "completed" ? 100 : 0);

      jobIdNode.textContent = status.job_id ? `Job ${status.job_id}` : "No job yet.";
      statePill.textContent = status.state || "idle";
      statusMessage.textContent = status.message || "";
      chunkStats.textContent = `${completed} / ${total} chunks`;
      stageStats.textContent = status.stage || "waiting";
      progressBar.value = percent;
    }
  </script>
</body>
</html>
"""
