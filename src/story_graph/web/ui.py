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

    [hidden] {
      display: none !important;
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

    .button-secondary {
      color: var(--primary);
      background: rgba(20, 83, 45, 0.1);
      box-shadow: none;
    }

    .button-small {
      padding: 0.55rem 0.8rem;
      font-size: 0.9rem;
    }

    .actions {
      display: flex;
      gap: 0.6rem;
      flex-wrap: wrap;
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

    .history {
      display: grid;
      gap: 0.75rem;
      padding: 1.1rem 1.15rem;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.75);
    }

    .history-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }

    .history h2 {
      margin: 0;
      font-size: 1rem;
    }

    .job-list {
      display: grid;
      gap: 0.6rem;
    }

    .job-row {
      display: grid;
      gap: 0.65rem;
      padding: 0.85rem;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.72);
    }

    .job-row.active {
      border-color: rgba(20, 83, 45, 0.45);
      box-shadow: inset 3px 0 0 var(--primary);
    }

    .job-main {
      display: grid;
      gap: 0.25rem;
      min-width: 0;
    }

    .job-title {
      overflow-wrap: anywhere;
      font-weight: 700;
    }

    .job-meta {
      display: flex;
      gap: 0.65rem;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .job-actions {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
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

          <label class="field">
            <span>Max chunk tokens</span>
            <input name="max_chunk_tokens" type="number" min="0" step="1" value="3000">
          </label>

          <label class="field">
            <span>Max paragraphs per chunk</span>
            <input name="max_paragraphs_per_chunk" type="number" min="0" step="1" value="80">
          </label>

          <label class="field">
            <span>Batch size</span>
            <input name="batch_size" type="number" min="1" step="1" value="4">
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

      <section class="history">
        <div class="history-head">
          <h2>Jobs</h2>
          <button class="button-secondary button-small" id="refresh-jobs-button" type="button">Refresh</button>
        </div>
        <div class="job-list" id="job-list"></div>
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
    const refreshJobsButton = document.getElementById("refresh-jobs-button");
    const jobList = document.getElementById("job-list");

    const activeJobStorageKey = "storyGraphActiveJobId";
    let activeJobId = window.localStorage.getItem(activeJobStorageKey);
    let pollTimer = null;

    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      selectedFile.textContent = file ? file.name : "Choose a UTF-8 .txt file";
    });

    refreshJobsButton.addEventListener("click", () => {
      loadJobs();
    });

    jobList.addEventListener("click", async (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }

      const button = event.target.closest("button[data-action]");
      if (!button) {
        return;
      }

      const jobId = button.dataset.jobId;
      if (!jobId) {
        return;
      }

      if (button.dataset.action === "watch") {
        activateJob(jobId);
        const status = await fetchJobStatus(jobId);
        if (status) {
          updateStatus(status);
          handleTerminalStatus(status);
          if (["queued", "running"].includes(status.state)) {
            schedulePoll(jobId);
          }
        }
      }

      if (button.dataset.action === "resume") {
        await resumeJob(jobId);
      }
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

        activateJob(payload.job_id);
        updateStatus(payload);
        graphFrame.hidden = true;
        viewerEmpty.hidden = false;
        graphLink.hidden = true;
        loadJobs();
        schedulePoll(activeJobId);
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

    initialize();

    async function initialize() {
      await loadJobs();
      if (!activeJobId) {
        return;
      }

      const status = await fetchJobStatus(activeJobId);
      if (!status) {
        clearActiveJob();
        return;
      }

      updateStatus(status);
      handleTerminalStatus(status);
      if (["queued", "running"].includes(status.state)) {
        schedulePoll(activeJobId);
      }
    }

    function activateJob(jobId) {
      activeJobId = jobId;
      window.localStorage.setItem(activeJobStorageKey, jobId);
      renderActiveJobMarker();
    }

    function clearActiveJob() {
      activeJobId = null;
      window.localStorage.removeItem(activeJobStorageKey);
      if (pollTimer) {
        window.clearTimeout(pollTimer);
        pollTimer = null;
      }
      renderActiveJobMarker();
    }

    async function loadJobs() {
      try {
        const response = await fetch("/jobs");
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Failed to load jobs.");
        }
        renderJobs(payload.jobs || []);
      } catch (error) {
        jobList.innerHTML = `<div class="job-row">${escapeHtml(error.message)}</div>`;
      }
    }

    function renderJobs(jobs) {
      if (!jobs.length) {
        jobList.innerHTML = '<div class="job-row">No jobs yet.</div>';
        return;
      }

      jobList.innerHTML = jobs.map((job) => {
        const completed = Number(job.completed_chunks || 0);
        const total = Number(job.total_chunks_to_process || 0);
        const progress = total > 0 ? `${completed} / ${total} chunks` : "No chunks yet";
        const updated = job.updated_at ? new Date(job.updated_at).toLocaleString() : "unknown time";
        const isActive = job.job_id === activeJobId ? " active" : "";
        const openButton = job.state === "completed" && job.graph_url
          ? `<a href="${job.graph_url}" target="_blank"><button class="button-secondary button-small" type="button">Open</button></a>`
          : "";
        const resumeButton = job.state === "failed"
          ? `<button class="button-secondary button-small" type="button" data-action="resume" data-job-id="${job.job_id}">Resume</button>`
          : "";
        const watchButton = ["queued", "running", "failed", "completed"].includes(job.state)
          ? `<button class="button-secondary button-small" type="button" data-action="watch" data-job-id="${job.job_id}">Watch</button>`
          : "";

        return `
          <article class="job-row${isActive}" data-job-row="${job.job_id}">
            <div class="job-main">
              <div class="job-title">${escapeHtml(job.original_filename || "upload.txt")}</div>
              <div class="job-meta">
                <span>${escapeHtml(job.state || "unknown")}</span>
                <span>${escapeHtml(progress)}</span>
                <span>${escapeHtml(updated)}</span>
              </div>
            </div>
            <div class="job-actions">${watchButton}${resumeButton}${openButton}</div>
          </article>
        `;
      }).join("");
    }

    function renderActiveJobMarker() {
      document.querySelectorAll("[data-job-row]").forEach((row) => {
        row.classList.toggle("active", row.dataset.jobRow === activeJobId);
      });
    }

    async function fetchJobStatus(jobId) {
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
        return null;
      }

      return payload;
    }

    async function resumeJob(jobId) {
      try {
        const response = await fetch(`/jobs/${jobId}/retry`, { method: "POST" });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Failed to resume job.");
        }

        activateJob(jobId);
        updateStatus(payload);
        graphFrame.hidden = true;
        viewerEmpty.hidden = false;
        graphLink.hidden = true;
        await loadJobs();
        schedulePoll(jobId);
      } catch (error) {
        updateStatus({
          state: "failed",
          stage: "error",
          message: error.message,
          completed_chunks: 0,
          total_chunks_to_process: 0
        });
      }
    }

    function schedulePoll(jobId) {
      if (pollTimer) {
        window.clearTimeout(pollTimer);
      }

      pollTimer = window.setTimeout(() => pollStatus(jobId), 1500);
    }

    async function pollStatus(jobId) {
      if (activeJobId !== jobId) {
        return;
      }

      const payload = await fetchJobStatus(jobId);
      if (!payload) {
        return;
      }

      updateStatus(payload);
      await loadJobs();

      if (handleTerminalStatus(payload)) {
        return;
      }

      schedulePoll(jobId);
    }

    function handleTerminalStatus(status) {
      if (status.state === "completed") {
        const graphUrl = `${status.graph_url}?t=${Date.now()}`;
        graphFrame.src = graphUrl;
        graphFrame.hidden = false;
        viewerEmpty.hidden = true;
        graphLink.href = status.graph_url;
        graphLink.hidden = false;
        return true;
      }

      if (status.state === "failed") {
        graphFrame.hidden = true;
        viewerEmpty.hidden = false;
        graphLink.hidden = true;
        return true;
      }

      return false;
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

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
  </script>
</body>
</html>
"""
