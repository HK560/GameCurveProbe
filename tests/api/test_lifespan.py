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
