/**
 * Single wrapper around fetch() for all backend calls.
 * Centralizing this avoids duplicated base-URL / error-handling logic
 * across chat.js, history.js, notes.js, and logs.js.
 */
const Api = (() => {
  const BASE_URL = "/api/v1";

  async function request(path, options = {}) {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const error = new Error(body.message || `Request failed with status ${response.status}`);
      error.status = response.status;
      throw error;
    }

    return response.status === 204 ? null : response.json();
  }

  return {
    health: () => request("/health"),
    chat: (message) => request("/chat", { method: "POST", body: JSON.stringify({ message }) }),
    createNote: (data) => request("/notes", { method: "POST", body: JSON.stringify(data) }),
    listNotes: (params = {}) => {
      const query = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
      ).toString();
      return request(`/notes${query ? `?${query}` : ""}`);
    },
    getNote: (id) => request(`/notes/${id}`),
    updateNote: (id, data) => request(`/notes/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    deleteNote: (id) => request(`/notes/${id}`, { method: "DELETE" }),
    listPendingApprovals: () => request("/approvals"),
    approveWorkflow: (workflowId) => request(`/approvals/${workflowId}/approve`, { method: "POST" }),
    rejectWorkflow: (workflowId) => request(`/approvals/${workflowId}/reject`, { method: "POST" }),
    listWorkflows: (params = {}) => {
      const query = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
      ).toString();
      return request(`/workflows${query ? `?${query}` : ""}`);
    },
    getWorkflow: (workflowId) => request(`/workflows/${workflowId}`),
    getWorkflowSteps: (workflowId) => request(`/workflows/${workflowId}/steps`),
    listLogs: (params = {}) => {
      const query = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""))
      ).toString();
      return request(`/logs${query ? `?${query}` : ""}`);
    },
  };
})();