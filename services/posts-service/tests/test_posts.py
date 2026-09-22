def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_create_post(client):
    resp = client.post(
        "/posts", json={"user_id": 1, "title": "Hello", "content": "World"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == 1
    assert body["title"] == "Hello"
    assert body["content"] == "World"
    assert "id" in body
    assert "created_at" in body


def test_get_post_by_id(client):
    created = client.post(
        "/posts", json={"user_id": 2, "title": "Post A", "content": "Body A"}
    ).json()

    resp = client.get(f"/posts/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["title"] == "Post A"


def test_get_missing_post_404(client):
    resp = client.get("/posts/99999")
    assert resp.status_code == 404


def test_list_posts_filtered_by_user_id(client):
    client.post("/posts", json={"user_id": 10, "title": "A", "content": "a"})
    client.post("/posts", json={"user_id": 10, "title": "B", "content": "b"})
    client.post("/posts", json={"user_id": 20, "title": "C", "content": "c"})

    resp = client.get("/posts", params={"user_id": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(item["user_id"] == 10 for item in body["items"])


def test_list_posts_pagination(client):
    for i in range(5):
        client.post("/posts", json={"user_id": 30, "title": f"T{i}", "content": "c"})

    resp = client.get("/posts", params={"user_id": 30, "limit": 2, "offset": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2
    assert body["total"] == 5


def test_delete_post(client):
    created = client.post(
        "/posts", json={"user_id": 3, "title": "Delete me", "content": "bye"}
    ).json()

    resp = client.delete(f"/posts/{created['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/posts/{created['id']}")
    assert resp.status_code == 404


def test_delete_missing_post_404(client):
    resp = client.delete("/posts/99999")
    assert resp.status_code == 404
