/**
 * Workflow History panel: lists all agent workflow runs, and shows a full
 * chronological step-by-step timeline for a selected one. Talks to the
 * backend exclusively through the Api wrapper (api.js).
 */
(() => {
  const PAGE_SIZE = 10;

  const state = {
    offset: 0,
    total: 0,
  };

  const tableBody = document.getElementById("history-table-body");
  const stateEl = document.getElementById("history-state");
  const paginationEl = document.getElementById("history-pagination");
  const refreshBtn = document.getElementById("history-refresh-btn");

  const detailOverlay = document.getElementById("history-detail-overlay");
  const detailMetaEl = document.getElementById("history-detail-meta");
  const detailStateEl = document.getElementById("history-detail-state");
  const timelineEl = document.getElementById("history-timeline");
  const detailCloseBtn = document.getElementById("history-detail-close-btn");

  const STATUS_LABELS = {
    RUNNING: "Running",
    WAITING_APPROVAL: "Waiting Approval",
    COMPLETED: "Completed",
    FAILED: "Failed",
  };

  const STATUS_CLASSES = {
    RUNNING: "running",
    WAITING_APPROVAL: "waiting-approval",
    COMPLETED: "completed",
    FAILED: "failed",
  };

  const NODE_LABELS = {
    REASON: "Reason",
    PLAN: "Plan",
    ACT: "Act",
    OBSERVE: "Observe",
    APPROVAL: "Approval",
  };

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function formatDate(isoString) {
    if (!isoString) return "—";
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function formatDuration(startedAt, finishedAt) {
    if (!finishedAt) return "In progress";
    const ms = new Date(finishedAt) - new Date(startedAt);
    if (Number.isNaN(ms) || ms < 0) return "—";
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  }

  function renderStatusBadge(status) {
    const cssClass = STATUS_CLASSES[status] || "unknown";
    const label = STATUS_LABELS[status] || status;
    return `<span class="status-badge status-badge-${cssClass}">${escapeHtml(label)}</span>`;
  }

  function renderState(message, isError = false) {
    stateEl.textContent = message;
    stateEl.className = `notes-state${isError ? " error" : ""}`;
    stateEl.style.display = message ? "block" : "none";
  }

  function renderRows(workflows) {
    tableBody.innerHTML = "";
    workflows.forEach((wf) => {
      const row = document.createElement("tr");
      row.className = "history-row";
      row.dataset.workflowId = wf.workflow_id;
      row.innerHTML = `
        <td class="history-cell-id" title="${escapeHtml(wf.workflow_id)}">${escapeHtml(wf.workflow_id.slice(0, 8))}…</td>
        <td class="history-cell-request">${escapeHtml(wf.user_input)}</td>
        <td>${renderStatusBadge(wf.status)}</td>
        <td class="history-cell-meta">${formatDate(wf.started_at)}</td>
        <td class="history-cell-meta">${formatDuration(wf.started_at, wf.finished_at)}</td>
      `;
      row.addEventListener("click", () => openDetail(wf.workflow_id));
      tableBody.appendChild(row);
    });
  }

  function renderPagination() {
    paginationEl.innerHTML = "";
    if (state.total <= PAGE_SIZE) return;

    const currentPage = Math.floor(state.offset / PAGE_SIZE) + 1;
    const totalPages = Math.ceil(state.total / PAGE_SIZE);

    const prevBtn = document.createElement("button");
    prevBtn.className = "btn btn-secondary";
    prevBtn.textContent = "← Prev";
    prevBtn.disabled = state.offset === 0;
    prevBtn.addEventListener("click", () => {
      state.offset = Math.max(0, state.offset - PAGE_SIZE);
      loadHistory();
    });

    const label = document.createElement("span");
    label.textContent = `Page ${currentPage} of ${totalPages}`;

    const nextBtn = document.createElement("button");
    nextBtn.className = "btn btn-secondary";
    nextBtn.textContent = "Next →";
    nextBtn.disabled = state.offset + PAGE_SIZE >= state.total;
    nextBtn.addEventListener("click", () => {
      state.offset += PAGE_SIZE;
      loadHistory();
    });

    paginationEl.append(prevBtn, label, nextBtn);
  }

  async function loadHistory() {
    renderState("Loading workflow history...");
    tableBody.innerHTML = "";
    paginationEl.innerHTML = "";

    try {
      const response = await Api.listWorkflows({ limit: PAGE_SIZE, offset: state.offset });
      state.total = response.total;

      if (response.items.length === 0) {
        renderState("No workflows have run yet. Send a message from the Chat tab to get started.");
        return;
      }

      renderState("");
      renderRows(response.items);
      renderPagination();
    } catch (err) {
      renderState(`Failed to load workflow history: ${err.message}`, true);
    }
  }

  function renderToolBlock(label, value) {
    if (value === null || value === undefined) return "";
    const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
    return `
      <div class="timeline-tool-block">
        <span class="timeline-tool-label">${escapeHtml(label)}</span>
        <pre class="timeline-tool-value">${escapeHtml(text)}</pre>
      </div>
    `;
  }

  function renderTimeline(steps) {
    timelineEl.innerHTML = "";
    steps.forEach((step, index) => {
      const item = document.createElement("div");
      item.className = "timeline-item";
      item.innerHTML = `
        <div class="timeline-marker">
          <span class="timeline-node-badge">${escapeHtml(NODE_LABELS[step.node_name] || step.node_name)}</span>
          ${index < steps.length - 1 ? '<span class="timeline-connector"></span>' : ""}
        </div>
        <div class="timeline-content card">
          <div class="timeline-header">
            <span class="timeline-sequence">Step ${step.sequence_number}</span>
            <span class="timeline-timestamp">${formatDate(step.timestamp)}</span>
          </div>
          <p class="timeline-summary">${escapeHtml(step.action_summary)}</p>
          ${
            step.tool_name
              ? `<div class="timeline-tool-block"><span class="timeline-tool-label">Tool</span> ${escapeHtml(step.tool_name)}</div>`
              : ""
          }
          ${renderToolBlock("Input", step.tool_input)}
          ${renderToolBlock("Output", step.tool_output)}
        </div>
      `;
      timelineEl.appendChild(item);
    });
  }

  async function openDetail(workflowId) {
    detailOverlay.classList.remove("hidden");
    detailMetaEl.innerHTML = "";
    timelineEl.innerHTML = "";
    detailStateEl.textContent = "Loading steps...";
    detailStateEl.className = "notes-state";
    detailStateEl.style.display = "block";

    try {
      const [workflow, stepsResponse] = await Promise.all([
        Api.getWorkflow(workflowId),
        Api.getWorkflowSteps(workflowId),
      ]);

      detailMetaEl.innerHTML = `
        <div class="history-detail-meta-row"><strong>Workflow:</strong> ${escapeHtml(workflowId)}</div>
        <div class="history-detail-meta-row"><strong>Request:</strong> ${escapeHtml(workflow.user_input)}</div>
        <div class="history-detail-meta-row"><strong>Status:</strong> ${renderStatusBadge(workflow.status)}</div>
        ${
          workflow.final_response
            ? `<div class="history-detail-meta-row"><strong>Final response:</strong> ${escapeHtml(workflow.final_response)}</div>`
            : ""
        }
      `;

      if (stepsResponse.items.length === 0) {
        detailStateEl.textContent = "No steps recorded for this workflow.";
        detailStateEl.style.display = "block";
        return;
      }

      detailStateEl.style.display = "none";
      renderTimeline(stepsResponse.items);
    } catch (err) {
      detailStateEl.textContent = `Failed to load workflow detail: ${err.message}`;
      detailStateEl.className = "notes-state error";
      detailStateEl.style.display = "block";
    }
  }

  function closeDetail() {
    detailOverlay.classList.add("hidden");
  }

  detailCloseBtn.addEventListener("click", closeDetail);
  detailOverlay.addEventListener("click", (event) => {
    if (event.target === detailOverlay) closeDetail();
  });

  refreshBtn.addEventListener("click", () => {
    state.offset = 0;
    loadHistory();
  });

  document.querySelector('[data-tab="history"]').addEventListener(
    "click",
    () => {
      loadHistory();
    },
    { once: true }
  );
})();// Workflow history panel logic will be implemented once the /workflows endpoints exist.
