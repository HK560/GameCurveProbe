from __future__ import annotations

from starlette.testclient import TestClient

from gamecurveprobe.api.server import create_app
from gamecurveprobe.context import AppContext


def test_lifespan_closes_resources_on_shutdown(monkeypatch, context) -> None:
    closed = []
    original_close = AppContext.close

    def tracking_close(self):
        closed.append(True)
        original_close(self)

    monkeypatch.setattr(AppContext, "close", tracking_close)

    app = create_app(context_factory=lambda: context)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").status_code == 200

    assert len(closed) == 1


def test_spa_fallback_cannot_escape_static_directory(tmp_path, context) -> None:
    static_dir = tmp_path / "web"
    static_dir.mkdir()
    (static_dir / "assets").mkdir()
    (static_dir / "index.html").write_text("<div id='app'></div>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("do-not-expose", encoding="utf-8")
    app = create_app(context_factory=lambda: context, static_dir=static_dir)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/%2e%2e/secret.txt")

    assert "do-not-expose" not in response.text


def test_cors_never_allows_arbitrary_origins(context) -> None:
    app = create_app(context_factory=lambda: context)
    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")

    assert "*" not in cors.kwargs.get("allow_origins", [])
    assert cors.kwargs.get("allow_origin_regex") != ".*"
