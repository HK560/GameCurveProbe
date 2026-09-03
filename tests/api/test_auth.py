from __future__ import annotations


def test_session_requires_bearer_token(client, auth_headers) -> None:
    assert client.get("/api/session").status_code == 401
    assert client.get("/api/session", headers={"Authorization": "Bearer bad-token", "Origin": "http://127.0.0.1"}).status_code == 401
    assert client.get("/api/session", headers=auth_headers).status_code == 200


def test_origin_validation(client, token) -> None:
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://evil.com"}
    response = client.get("/api/session", headers=headers)
    assert response.status_code == 403


def test_health_endpoint_is_unauthenticated(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
