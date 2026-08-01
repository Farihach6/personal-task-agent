"""API-level tests for the Notes endpoints."""


def test_create_note_returns_201(client):
    response = client.post("/api/v1/notes", json={"title": "Groceries", "content": "Milk and eggs"})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Groceries"
    assert body["content"] == "Milk and eggs"
    assert "id" in body


def test_create_note_rejects_blank_title(client):
    response = client.post("/api/v1/notes", json={"title": "   ", "content": "content"})
    assert response.status_code == 422


def test_create_note_rejects_missing_fields(client):
    response = client.post("/api/v1/notes", json={"title": "Only title"})
    assert response.status_code == 422


def test_get_note_returns_note(client):
    created = client.post("/api/v1/notes", json={"title": "Note A", "content": "Content A"}).json()

    response = client.get(f"/api/v1/notes/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Note A"


def test_get_note_not_found_returns_404(client):
    response = client.get("/api/v1/notes/999999")
    assert response.status_code == 404


def test_list_notes_empty_returns_empty_list(client):
    response = client.get("/api/v1/notes")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_notes_pagination(client):
    for i in range(3):
        client.post("/api/v1/notes", json={"title": f"Note {i}", "content": "content"})

    response = client.get("/api/v1/notes?limit=2&offset=0")
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_search_notes_filters_by_title_and_content(client):
    client.post("/api/v1/notes", json={"title": "Meeting notes", "content": "roadmap discussion"})
    client.post("/api/v1/notes", json={"title": "Unrelated", "content": "nothing to see"})

    response = client.get("/api/v1/notes?search=meeting")
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Meeting notes"


def test_update_note_changes_fields(client):
    created = client.post("/api/v1/notes", json={"title": "Old", "content": "Old content"}).json()

    response = client.put(f"/api/v1/notes/{created['id']}", json={"title": "New"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New"
    assert body["content"] == "Old content"


def test_update_note_requires_at_least_one_field(client):
    created = client.post("/api/v1/notes", json={"title": "Old", "content": "Old content"}).json()

    response = client.put(f"/api/v1/notes/{created['id']}", json={})
    assert response.status_code == 422


def test_update_note_not_found_returns_404(client):
    response = client.put("/api/v1/notes/999999", json={"title": "Doesn't matter"})
    assert response.status_code == 404


def test_delete_note_removes_it(client):
    created = client.post("/api/v1/notes", json={"title": "Temp", "content": "Delete me"}).json()

    delete_response = client.delete(f"/api/v1/notes/{created['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/notes/{created['id']}")
    assert get_response.status_code == 404


def test_delete_note_not_found_returns_404(client):
    response = client.delete("/api/v1/notes/999999")
    assert response.status_code == 404