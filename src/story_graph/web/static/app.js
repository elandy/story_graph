const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const submitButton = document.getElementById("submit-button");
const refreshJobsButton = document.getElementById("refresh-jobs-button");
const jobSearchInput = document.getElementById("job-search-input");
const jobStateFilter = document.getElementById("job-state-filter");
const jobList = document.getElementById("job-list");

const activeJobStorageKey = "storyGraphActiveJobId";
let activeJobId = window.localStorage.getItem(activeJobStorageKey);
let pollTimer = null;
let allJobs = [];

fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  selectedFile.textContent = file ? file.name : "Choose a UTF-8 .txt file";
});

refreshJobsButton.addEventListener("click", () => {
  loadJobs();
});

jobSearchInput.addEventListener("input", () => {
  renderVisibleJobs();
});

jobStateFilter.addEventListener("change", () => {
  renderVisibleJobs();
});

jobList.addEventListener("click", async (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }

  const button = event.target.closest("button[data-action]");
  if (button) {
    const jobId = button.dataset.jobId;
    if (!jobId) {
      return;
    }

    if (button.dataset.action === "resume") {
      await resumeJob(jobId);
    }
    if (button.dataset.action === "pause") {
      await pauseJob(jobId);
    }
    if (button.dataset.action === "delete") {
      await deleteJob(jobId);
    }
    return;
  }

  if (event.target.closest("a, button")) {
    return;
  }

  const row = event.target.closest("[data-job-row]");
  if (row) {
    await selectJob(row.dataset.jobRow);
  }
});

jobList.addEventListener("keydown", async (event) => {
  if (!(event.target instanceof HTMLElement)) {
    return;
  }
  if (!["Enter", " "].includes(event.key)) {
    return;
  }

  const row = event.target.closest("[data-job-row]");
  if (!row) {
    return;
  }

  event.preventDefault();
  await selectJob(row.dataset.jobRow);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!fileInput.files || !fileInput.files[0]) {
    renderInlineMessage("Choose a .txt file first.");
    return;
  }

  submitButton.disabled = true;
  renderInlineMessage("Uploading file and creating job workspace.");

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
    await loadJobs();
    schedulePoll(activeJobId);
  } catch (error) {
    renderInlineMessage(error.message);
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
    allJobs = payload.jobs || [];
    renderVisibleJobs();
  } catch (error) {
    jobList.innerHTML = `<div class="job-row">${escapeHtml(error.message)}</div>`;
  }
}

function renderVisibleJobs() {
  const jobs = filterJobs(allJobs);
  renderJobs(jobs);
}

function renderJobs(jobs) {
  if (!jobs.length) {
    jobList.innerHTML = allJobs.length
      ? '<div class="job-row">No jobs match the current filters.</div>'
      : '<div class="job-row">No jobs yet.</div>';
    return;
  }

  jobList.innerHTML = jobs.map((job) => renderJobRow(job)).join("");
}

function filterJobs(jobs) {
  const query = (jobSearchInput.value || "").trim().toLowerCase();
  const state = jobStateFilter.value || "all";

  return jobs.filter((job) => {
    const matchesState = state === "all" || job.state === state;
    const haystack = `${job.original_filename || ""} ${job.job_id || ""}`.toLowerCase();
    const matchesQuery = !query || haystack.includes(query);
    return matchesState && matchesQuery;
  });
}

function renderJobRow(job) {
  const completed = Number(job.completed_chunks || 0);
  const total = Number(job.total_chunks_to_process || 0);
  const progress = total > 0 ? `${completed} / ${total} chunks` : "No chunks yet";
  const updated = job.updated_at ? new Date(job.updated_at).toLocaleString() : "unknown time";
  const isActive = job.job_id === activeJobId;
  const isExpanded = isActive || ["queued", "running", "paused", "failed"].includes(job.state);
  const rowClasses = [
    "job-row",
    "selectable",
    isActive ? "active" : "",
    isExpanded ? "is-expanded" : "",
  ].filter(Boolean).join(" ");
  const percent = total > 0
    ? Math.min(100, Math.round((completed / total) * 100))
    : (job.state === "completed" ? 100 : 0);

  const openButton = job.state === "completed" && job.graph_url
    ? `<a href="${job.graph_url}" target="_blank"><button class="button-secondary button-small" type="button">Open</button></a>`
    : "";
  const resumeButton = ["failed", "paused"].includes(job.state)
    ? `<button class="button-secondary button-small" type="button" data-action="resume" data-job-id="${job.job_id}">Resume</button>`
    : "";
  const pauseButton = ["queued", "running"].includes(job.state)
    ? `<button class="button-secondary button-small" type="button" data-action="pause" data-job-id="${job.job_id}">Pause</button>`
    : "";
  const deleteButton = ["completed", "failed"].includes(job.state)
    ? `<button class="button-secondary button-small" type="button" data-action="delete" data-job-id="${job.job_id}">Delete</button>`
    : "";
  const graphMeta = job.state === "completed" && job.graph_url
    ? `<a href="${job.graph_url}" target="_blank">Open graph</a>`
    : "";

  const messageBlock = isExpanded
    ? `<div class="job-message">${escapeHtml(job.message || "")}</div>`
    : "";

  const progressBlock = isExpanded
    ? `
      <div class="job-progress">
        <progress max="100" value="${percent}"></progress>
        <div class="progress-meta">
          <span>${escapeHtml(progress)}</span>
          <span>${escapeHtml(job.stage || "waiting")}</span>
        </div>
      </div>
    `
    : "";

  return `
    <article class="${rowClasses}" data-job-row="${job.job_id}" tabindex="0">
      <div class="job-head">
        <div class="job-main">
          <div class="job-title">${escapeHtml(job.original_filename || "upload.txt")}</div>
          <div class="job-meta">
            <span>Job ${escapeHtml(job.job_id || "")}</span>
            <span>${escapeHtml(progress)}</span>
            <span>${escapeHtml(updated)}</span>
            ${graphMeta}
          </div>
        </div>
        <span class="pill">${escapeHtml(job.state || "unknown")}</span>
      </div>
      <div class="job-status">
        ${messageBlock}
        ${progressBlock}
      </div>
      <div class="job-actions">${pauseButton}${resumeButton}${deleteButton}${openButton}</div>
    </article>
  `;
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
    renderInlineMessage(payload.error || "Failed to fetch job status.");
    return null;
  }

  return payload;
}

async function selectJob(jobId) {
  if (!jobId) {
    return;
  }

  activateJob(jobId);
  const status = await fetchJobStatus(jobId);
  if (!status) {
    clearActiveJob();
    await loadJobs();
    return;
  }

  if (["queued", "running"].includes(status.state)) {
    schedulePoll(jobId);
  } else if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
  await loadJobs();
}

async function resumeJob(jobId) {
  try {
    const response = await fetch(`/jobs/${jobId}/retry`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to resume job.");
    }

    activateJob(jobId);
    await loadJobs();
    schedulePoll(jobId);
  } catch (error) {
    renderInlineMessage(error.message);
  }
}

async function pauseJob(jobId) {
  try {
    const response = await fetch(`/jobs/${jobId}/pause`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to pause job.");
    }

    if (activeJobId === jobId && ["queued", "running"].includes(payload.state)) {
      schedulePoll(jobId);
    }
    await loadJobs();
  } catch (error) {
    renderInlineMessage(error.message);
  }
}

async function deleteJob(jobId) {
  try {
    if (!window.confirm("Delete this job and all of its saved artifacts?")) {
      return;
    }

    const response = await fetch(`/jobs/${jobId}`, { method: "DELETE" });
    let payload = {};
    if (response.status !== 204) {
      payload = await response.json();
    }
    if (!response.ok) {
      throw new Error(payload.error || "Failed to delete job.");
    }

    if (activeJobId === jobId) {
      clearActiveJob();
    }
    await loadJobs();
  } catch (error) {
    renderInlineMessage(error.message);
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

  await loadJobs();
  if (!["queued", "running"].includes(payload.state)) {
    pollTimer = null;
    return;
  }

  schedulePoll(jobId);
}

function renderInlineMessage(message) {
  jobList.innerHTML = `<div class="job-row">${escapeHtml(message)}</div>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
