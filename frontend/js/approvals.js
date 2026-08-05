/**
 * Approvals panel: lists workflows paused awaiting human approval, and lets
 * the user approve or reject each one. Talks to the backend exclusively
 * through the Api wrapper (api.js).
 */
(() => {
  const listEl = document.getElementById("approvals-list");
  const stateEl = document.getElementById("approvals-state");
  const refreshBtn = document.getElementById("approvals-refresh-btn");

  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function renderState(message, isError = false) {
    stateEl.textContent = message;
    stateEl.className = `notes-state${isError ? " error" : ""}`;
    stateEl.style.display = message ? "block" : "none";
  }

  function renderToolInputDetails(toolInput) {
    const entries = Object.entries(toolInput || {});
    if (entries.length === 0) {
      return '<p class="approval-card-detail-row approval-card-detail-empty">No additional details.</p>';
    }
    return entries
      .map(
        ([key, value]) =>
          `<p class="approval-card-detail-row"><strong>${escapeHtml(key)}:</strong> ${escapeHtml(value)}</p>`
      )
      .join("");
  }

  function renderApprovals(items) {
    listEl.innerHTML = "";
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = "card approval-card";
      card.innerHTML = `
        <div class="approval-card-header">
          <span class="approval-tool-badge">${escapeHtml((item.tool_name || "unknown").toUpperCase())}</span>
          <span class="approval-card-meta">Requested ${formatDate(item.created_at)}</span>
        </div>
        <p class="approval-card-prompt">"${escapeHtml(item.user_prompt)}"</p>
        <div class="approval-card-details">${renderToolInputDetails(item.tool_input)}</div>
        <div class="approval-card-actions">
          <button class="btn btn-primary" data-action="approve" data-id="${escapeHtml(item.workflow_id)}">Approve</button>
          <button class="btn btn-danger" data-action="reject" data-id="${escapeHtml(item.workflow_id)}">Reject</button>
        </div>
      `;
      listEl.appendChild(card);
    });
  }

  async function loadApprovals() {
    renderState("Loading pending approvals...");
    listEl.innerHTML = "";

    try {
      const response = await Api.listPendingApprovals();

      if (response.items.length === 0) {
        renderState("No approvals waiting right now.");
        return;
      }

      renderState("");
      renderApprovals(response.items);
    } catch (err) {
      renderState(`Failed to load approvals: ${err.message}`, true);
      showToast(`Failed to load approvals: ${err.message}`, "error");
    }
  }

  async function decide(workflowId, approve, button) {
    button.disabled = true;
    const originalText = button.textContent;
    button.textContent = approve ? "Approving..." : "Rejecting...";

    try {
      const result = approve
        ? await Api.approveWorkflow(workflowId)
        : await Api.rejectWorkflow(workflowId);
      const message = (result && result.final_response) || (approve ? "Action approved." : "Action rejected.");
      showToast(message, approve ? "success" : "success");
      await loadApprovals();
    } catch (err) {
      showToast(`Failed to ${approve ? "approve" : "reject"}: ${err.message}`, "error");
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  listEl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const workflowId = button.dataset.id;
    if (button.dataset.action === "approve") {
      decide(workflowId, true, button);
    } else if (button.dataset.action === "reject") {
      decide(workflowId, false, button);
    }
  });

  refreshBtn.addEventListener("click", loadApprovals);

  document.querySelector('[data-tab="approvals"]').addEventListener(
    "click",
    () => {
      loadApprovals();
    },
    { once: true }
  );
})();