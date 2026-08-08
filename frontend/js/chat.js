/**
 * Chat panel: send tasks to the agent and render the conversation.
 * Talks to the backend exclusively through the Api wrapper (api.js).
 * Messages are kept in memory only — persisted history lives in the
 * Workflow History tab, backed by the database.
 */
(() => {
  // Matches app/schemas/chat.py ChatRequest.message (Field max_length=4000).
  const MAX_MESSAGE_LENGTH = 4000;
  const CHAR_WARNING_THRESHOLD = 0.9; // start warning at 90% of the limit

  const messagesEl = document.getElementById("chat-messages");
  const emptyStateEl = document.getElementById("chat-empty");
  const statusEl = document.getElementById("chat-status");
  const formEl = document.getElementById("chat-form");
  const inputEl = document.getElementById("chat-input");
  const charCountEl = document.getElementById("chat-char-count");
  const sendBtn = document.getElementById("chat-send-btn");
  const clearBtn = document.getElementById("chat-clear-btn");

  let isSending = false;

  // --- Small DOM helpers (safe: text is always set via textContent, never innerHTML) ---

  function createBubbleMessage(role, text, { meta } = {}) {
    const wrapper = document.createElement("div");
    wrapper.className = `chat-message chat-message-${role}`;

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    bubble.textContent = text;
    wrapper.appendChild(bubble);

    if (meta) {
      const metaEl = document.createElement("div");
      metaEl.className = "chat-message-meta";
      metaEl.textContent = meta;
      wrapper.appendChild(metaEl);
    }

    return wrapper;
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideEmptyState() {
    emptyStateEl.classList.add("hidden");
  }

  function showEmptyStateIfNoMessages() {
    const hasMessages = messagesEl.querySelector(".chat-message") !== null;
    emptyStateEl.classList.toggle("hidden", hasMessages);
  }

  function appendUserMessage(text) {
    hideEmptyState();
    messagesEl.appendChild(createBubbleMessage("user", text));
    scrollToBottom();
  }

  function appendAssistantMessage(text, meta) {
    hideEmptyState();
    messagesEl.appendChild(createBubbleMessage("assistant", text, { meta }));
    scrollToBottom();
  }

  function appendSystemMessage(text) {
    hideEmptyState();
    messagesEl.appendChild(createBubbleMessage("system", text));
    scrollToBottom();
  }

  function appendErrorMessage(text) {
    hideEmptyState();
    messagesEl.appendChild(createBubbleMessage("error", text));
    scrollToBottom();
  }

  function appendLoadingBubble() {
    hideEmptyState();
    const wrapper = document.createElement("div");
    wrapper.className = "chat-message chat-message-assistant chat-message-loading";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";

    const label = document.createElement("span");
    label.textContent = "Agent is working";
    bubble.appendChild(label);

    const dots = document.createElement("span");
    dots.className = "chat-loading-dots";
    dots.setAttribute("aria-hidden", "true");
    for (let i = 0; i < 3; i += 1) {
      dots.appendChild(document.createElement("span"));
    }
    bubble.appendChild(dots);

    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    scrollToBottom();
    return wrapper;
  }

  function removeNode(node) {
    if (node && node.parentNode) {
      node.parentNode.removeChild(node);
    }
  }

  function setStatus(message, isError = false) {
    statusEl.textContent = message;
    statusEl.className = `chat-status${isError ? " error" : ""}`;
  }

  // --- Validation ---

  function validateMessage(rawValue) {
    if (!rawValue.trim()) {
      return "Please enter a task.";
    }
    if (rawValue.length > MAX_MESSAGE_LENGTH) {
      return "Your message is too long. Please shorten it.";
    }
    return null;
  }

  function updateCharCount() {
    const length = inputEl.value.length;
    charCountEl.textContent = `${length} / ${MAX_MESSAGE_LENGTH}`;

    const isExceeded = length > MAX_MESSAGE_LENGTH;
    const isNearLimit = length >= MAX_MESSAGE_LENGTH * CHAR_WARNING_THRESHOLD;

    charCountEl.classList.toggle("chat-char-count-exceeded", isExceeded);
    charCountEl.classList.toggle("chat-char-count-warning", !isExceeded && isNearLimit);

    sendBtn.disabled = isExceeded || isSending;
  }

  // --- Error handling ---

  function getFriendlyErrorMessage(err) {
    if (!err || typeof err.status !== "number") {
      return "Network error: couldn't reach the agent. Please check your connection and try again.";
    }
    if (err.status === 400) {
      return "The agent couldn't process that request. Please try rephrasing it.";
    }
    if (err.status === 422) {
      return "Please double-check your message and try again.";
    }
    if (err.status === 429) {
      return "You're sending messages too quickly. Please wait a moment and try again.";
    }
    if (err.status >= 500) {
      return "Something went wrong on our end. Please try again in a moment.";
    }
    return "Something went wrong. Please try again.";
  }

  // --- Response rendering ---

  function renderAgentResult(result) {
    if (!result || typeof result.final_response !== "string" || typeof result.status !== "string") {
      appendErrorMessage("The agent returned an unexpected response. Please try again.");
      return;
    }

    if (result.status === "WAITING_APPROVAL") {
      appendAssistantMessage(result.final_response || "This action requires your approval.");
      appendSystemMessage(
        "Approval required before this action can continue. Open the Approvals tab to review it."
      );
      return;
    }

    if (result.status === "FAILED") {
      appendErrorMessage(result.final_response || "The agent couldn't complete that request.");
      return;
    }

    appendAssistantMessage(result.final_response || "Done.");
  }

  // --- Submit flow ---

  async function handleSubmit(event) {
    event.preventDefault();

    if (isSending) {
      return; // guards against rapid repeated submissions
    }

    const rawValue = inputEl.value;
    const validationError = validateMessage(rawValue);
    if (validationError) {
      setStatus(validationError, true);
      return;
    }

    const message = rawValue.trim();
    isSending = true;
    sendBtn.disabled = true;
    clearBtn.disabled = true;
    setStatus("");

    appendUserMessage(message);
    inputEl.value = "";
    updateCharCount();

    const loadingBubble = appendLoadingBubble();

    try {
      const result = await Api.chat(message);
      removeNode(loadingBubble);
      renderAgentResult(result);
    } catch (err) {
      removeNode(loadingBubble);
      appendErrorMessage(getFriendlyErrorMessage(err));
    } finally {
      isSending = false;
      clearBtn.disabled = false;
      updateCharCount(); // also restores sendBtn.disabled based on current input
      inputEl.focus();
    }
  }

  function handleClearChat() {
    messagesEl.querySelectorAll(".chat-message").forEach((node) => node.remove());
    showEmptyStateIfNoMessages();
    setStatus("");
  }

  // Enter sends the message; Shift+Enter inserts a newline (default textarea behavior).
  function handleTextareaKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      formEl.requestSubmit();
    }
  }

  formEl.addEventListener("submit", handleSubmit);
  inputEl.addEventListener("input", updateCharCount);
  inputEl.addEventListener("keydown", handleTextareaKeydown);
  clearBtn.addEventListener("click", handleClearChat);

  updateCharCount();
})();// Chat panel logic will be implemented once the /chat endpoint exists.
