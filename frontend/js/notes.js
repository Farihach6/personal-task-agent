

/**

 * Notes panel: list, search, paginate, create, edit, and delete notes.

 * Talks to the backend exclusively through the Api wrapper (api.js).

 */

(() => {

  const PAGE_SIZE = 9;



  const state = {

    search: "",

    offset: 0,

    total: 0,

    editingNoteId: null,

  };



  let searchDebounceTimer = null;



  const grid = document.getElementById("notes-grid");

  const stateEl = document.getElementById("notes-state");

  const paginationEl = document.getElementById("notes-pagination");

  const searchInput = document.getElementById("notes-search-input");

  const newBtn = document.getElementById("notes-new-btn");



  const modal = document.getElementById("note-modal");

  const modalTitle = document.getElementById("note-modal-title");

  const titleInput = document.getElementById("note-title-input");

  const contentInput = document.getElementById("note-content-input");

  const saveBtn = document.getElementById("note-save-btn");

  const cancelBtn = document.getElementById("note-cancel-btn");



  function showToast(message, type = "success") {

    const container = document.getElementById("toast-container");

    const toast = document.createElement("div");

    toast.className = `toast ${type}`;

    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => toast.remove(), 3500);

  }



  function escapeHtml(str) {

    const div = document.createElement("div");

    div.textContent = str;

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



  function renderNotes(notes) {

    grid.innerHTML = "";

    notes.forEach((note) => {

      const card = document.createElement("div");

      card.className = "card note-card";

      card.innerHTML = `

        <h4 class="note-card-title">${escapeHtml(note.title)}</h4>

        <p class="note-card-content">${escapeHtml(note.content)}</p>

        <span class="note-card-meta">Updated ${formatDate(note.updated_at)}</span>

        <div class="note-card-actions">

          <button class="btn btn-secondary" data-action="edit" data-id="${note.id}">Edit</button>

          <button class="btn btn-danger" data-action="delete" data-id="${note.id}">Delete</button>

        </div>

      `;

      grid.appendChild(card);

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

      loadNotes();

    });



    const label = document.createElement("span");

    label.textContent = `Page ${currentPage} of ${totalPages}`;



    const nextBtn = document.createElement("button");

    nextBtn.className = "btn btn-secondary";

    nextBtn.textContent = "Next →";

    nextBtn.disabled = state.offset + PAGE_SIZE >= state.total;

    nextBtn.addEventListener("click", () => {

      state.offset += PAGE_SIZE;

      loadNotes();

    });



    paginationEl.append(prevBtn, label, nextBtn);

  }



  async function loadNotes() {

    renderState("Loading notes...");

    grid.innerHTML = "";

    paginationEl.innerHTML = "";



    try {

      const response = await Api.listNotes({

        search: state.search || undefined,

        limit: PAGE_SIZE,

        offset: state.offset,

      });

      state.total = response.total;



      if (response.items.length === 0) {

        renderState(

          state.search

            ? `No notes match "${state.search}".`

            : "No notes yet. Click \u201c+ New Note\u201d to create your first one."

        );

        return;

      }



      renderState("");

      renderNotes(response.items);

      renderPagination();

    } catch (err) {

      renderState(`Failed to load notes: ${err.message}`, true);

      showToast(`Failed to load notes: ${err.message}`, "error");

    }

  }



  function openModal(note = null) {

    state.editingNoteId = note ? note.id : null;

    modalTitle.textContent = note ? "Edit Note" : "New Note";

    titleInput.value = note ? note.title : "";

    contentInput.value = note ? note.content : "";

    modal.classList.remove("hidden");

    titleInput.focus();

  }



  function closeModal() {

    modal.classList.add("hidden");

    state.editingNoteId = null;

  }



  async function saveNote() {

    const title = titleInput.value.trim();

    const content = contentInput.value.trim();



    if (!title || !content) {

      showToast("Title and content are both required.", "error");

      return;

    }



    saveBtn.disabled = true;

    saveBtn.textContent = "Saving...";



    try {

      if (state.editingNoteId) {

        await Api.updateNote(state.editingNoteId, { title, content });

        showToast("Note updated.");

      } else {

        await Api.createNote({ title, content });

        showToast("Note created.");

      }

      closeModal();

      state.offset = 0;

      await loadNotes();

    } catch (err) {

      showToast(`Failed to save note: ${err.message}`, "error");

    } finally {

      saveBtn.disabled = false;

      saveBtn.textContent = "Save";

    }

  }



  async function deleteNote(noteId) {

    if (!confirm("Delete this note? This cannot be undone.")) return;



    try {

      await Api.deleteNote(noteId);

      showToast("Note deleted.");

      await loadNotes();

    } catch (err) {

      showToast(`Failed to delete note: ${err.message}`, "error");

    }

  }



  grid.addEventListener("click", async (event) => {

    const button = event.target.closest("button[data-action]");

    if (!button) return;



    const noteId = Number(button.dataset.id);

    if (button.dataset.action === "delete") {

      await deleteNote(noteId);

    } else if (button.dataset.action === "edit") {

      try {

        const note = await Api.getNote(noteId);

        openModal(note);

      } catch (err) {

        showToast(`Failed to load note: ${err.message}`, "error");

      }

    }

  });



  newBtn.addEventListener("click", () => openModal());

  cancelBtn.addEventListener("click", closeModal);

  saveBtn.addEventListener("click", saveNote);

  modal.addEventListener("click", (event) => {

    if (event.target === modal) closeModal();

  });



  searchInput.addEventListener("input", (event) => {

    clearTimeout(searchDebounceTimer);

    searchDebounceTimer = setTimeout(() => {

      state.search = event.target.value.trim();

      state.offset = 0;

      loadNotes();

    }, 300);

  });



  document.querySelector('[data-tab="notes"]').addEventListener("click", () => {

    loadNotes();

  }, { once: true });

})();




