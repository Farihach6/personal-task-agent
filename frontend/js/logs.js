/**
 * Execution Logs panel.
 *
 * Displays agent execution-log entries with workflow ID and
 * log-level filters. All backend communication goes through
 * the centralized Api wrapper from api.js.
 *
 * The panel never reloads the page when filtering or refreshing.
 */
(() => {
  const FILTER_DEBOUNCE_MS = 300;
  const LOG_LIMIT = 200;

  const state = {
    workflowId: "",
    level: "",
    initialized: false,
    loading: false,
  };

  const tableBody = document.getElementById("logs-table-body");
  const stateEl = document.getElementById("logs-state");
  const refreshBtn = document.getElementById("logs-refresh-btn");
  const workflowIdInput = document.getElementById("logs-workflow-id-input");
  const levelSelect = document.getElementById("logs-level-select");
  const logsTabButton = document.querySelector('[data-tab="logs"]');

  const LEVEL_LABELS = {
    INFO: "Info",
    WARNING: "Warning",
    ERROR: "Error",
  };

  const LEVEL_CLASSES = {
    INFO: "info",
    WARNING: "warning",
    ERROR: "error",
  };

  let filterDebounceTimer = null;

  /**
   * Escape dynamic values before inserting them into HTML.
   *
   * @param {*} value
   * @returns {string}
   */
  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  /**
   * Format an ISO timestamp for display.
   *
   * @param {string|null|undefined} isoString
   * @returns {string}
   */
  function formatTimestamp(isoString) {
    if (!isoString) {
      return "—";
    }

    const date = new Date(isoString);

    if (Number.isNaN(date.getTime())) {
      return "—";
    }

    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  /**
   * Render a visual badge for a log level.
   *
   * @param {string} level
   * @returns {string}
   */
  function renderLevelBadge(level) {
    const normalizedLevel = String(level || "").toUpperCase();

    const cssClass =
      LEVEL_CLASSES[normalizedLevel] || "info";

    const label =
      LEVEL_LABELS[normalizedLevel] || normalizedLevel || "Unknown";

    return `
      <span class="log-level-badge log-level-badge-${cssClass}">
        ${escapeHtml(label)}
      </span>
    `;
  }

  /**
   * Display a loading, empty, or error state.
   *
   * @param {string} message
   * @param {boolean} isError
   */
  function renderState(message, isError = false) {
    if (!stateEl) {
      return;
    }

    stateEl.textContent = message;
    stateEl.className = `logs-state${isError ? " error" : ""}`;
    stateEl.style.display = message ? "block" : "none";
  }

  /**
   * Clear all rendered log rows.
   */
  function clearRows() {
    if (tableBody) {
      tableBody.innerHTML = "";
    }
  }

  /**
   * Render log rows into the logs table.
   *
   * @param {Array} logs
   */
  function renderRows(logs) {
    if (!tableBody) {
      return;
    }

    tableBody.innerHTML = "";

    logs.forEach((log) => {
      const row = document.createElement("tr");

      const workflowId =
        log.workflow_id == null ? "" : String(log.workflow_id);

      const message =
        log.message == null ? "" : String(log.message);

      const level =
        log.level == null ? "" : String(log.level).toUpperCase();

      const shortWorkflowId =
        workflowId.length > 8
          ? `${workflowId.slice(0, 8)}…`
          : workflowId;

      row.innerHTML = `
        <td class="history-cell-meta">
          ${escapeHtml(formatTimestamp(log.timestamp))}
        </td>

        <td>
          ${renderLevelBadge(level)}
        </td>

        <td
          class="history-cell-id"
          title="${escapeHtml(workflowId)}"
        >
          ${workflowId ? escapeHtml(shortWorkflowId) : "—"}
        </td>

        <td class="logs-cell-message">
          ${escapeHtml(message) || "—"}
        </td>
      `;

      tableBody.appendChild(row);
    });
  }

  /**
   * Check whether any filters are currently active.
   *
   * @returns {boolean}
   */
  function hasActiveFilters() {
    return Boolean(state.workflowId || state.level);
  }

  /**
   * Build the appropriate empty-state message.
   *
   * @returns {string}
   */
  function buildEmptyStateMessage() {
    if (hasActiveFilters()) {
      return "No execution logs match the current filters.";
    }

    return "No execution logs found.";
  }

  /**
   * Extract log items safely from the API response.
   *
   * Supports the expected paginated response shape:
   * { items: [...] }
   *
   * Also tolerates a plain array for frontend compatibility.
   *
   * @param {*} response
   * @returns {Array}
   */
  function getLogItems(response) {
    if (Array.isArray(response)) {
      return response;
    }

    if (response && Array.isArray(response.items)) {
      return response.items;
    }

    return [];
  }

  /**
   * Set the loading state of the refresh button.
   *
   * @param {boolean} loading
   */
  function setLoading(loading) {
    state.loading = loading;

    if (!refreshBtn) {
      return;
    }

    refreshBtn.disabled = loading;
    refreshBtn.textContent = loading ? "Refreshing..." : "Refresh";
  }

  /**
   * Load execution logs from the backend.
   *
   * @returns {Promise<void>}
   */
  async function loadLogs() {
    if (state.loading) {
      return;
    }

    setLoading(true);
    renderState("Loading execution logs...");
    clearRows();

    try {
      const response = await Api.listLogs({
        workflow_id: state.workflowId || undefined,
        level: state.level || undefined,
        limit: LOG_LIMIT,
      });

      const logs = getLogItems(response);

      if (logs.length === 0) {
        renderState(buildEmptyStateMessage());
        return;
      }

      renderState("");
      renderRows(logs);
    } catch (error) {
      const message =
        error && error.message
          ? error.message
          : "Unable to load execution logs.";

      renderState(
        `Failed to load execution logs: ${message}`,
        true
      );
    } finally {
      setLoading(false);
    }
  }

  /**
   * Schedule a log reload after the user stops typing.
   */
  function scheduleReload() {
    clearTimeout(filterDebounceTimer);

    filterDebounceTimer = setTimeout(() => {
      loadLogs();
    }, FILTER_DEBOUNCE_MS);
  }

  /**
   * Handle workflow ID filter changes.
   *
   * @param {Event} event
   */
  function handleWorkflowFilter(event) {
    state.workflowId = event.target.value.trim();
    scheduleReload();
  }

  /**
   * Handle log-level filter changes.
   *
   * @param {Event} event
   */
  function handleLevelFilter(event) {
    state.level = event.target.value;
    loadLogs();
  }

  /**
   * Handle refresh button clicks.
   */
  function handleRefresh() {
    loadLogs();
  }

  /**
   * Initialize event listeners for the Logs panel.
   */
  function initialize() {
    if (state.initialized) {
      return;
    }

    if (!tableBody || !stateEl || !refreshBtn) {
      return;
    }

    state.initialized = true;

    if (workflowIdInput) {
      workflowIdInput.addEventListener(
        "input",
        handleWorkflowFilter
      );
    }

    if (levelSelect) {
      levelSelect.addEventListener(
        "change",
        handleLevelFilter
      );
    }

    refreshBtn.addEventListener(
      "click",
      handleRefresh
    );

    if (logsTabButton) {
      logsTabButton.addEventListener("click", () => {
        loadLogs();
      });
    }
  }

  initialize();
})();