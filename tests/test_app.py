from __future__ import annotations

from gamecurveprobe.app import build_browser_url, build_context, build_parser
import pytest
from gamecurveprobe.backends.capture.dxcam_monitor_backend import DxcamMonitorCaptureBackend


def test_build_parser_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.token is None
    assert args.no_browser is False


def test_build_context_returns_ready_app_context() -> None:
    context = build_context("test-token", "127.0.0.1", 8765)
    assert context.token == "test-token"
    assert "http://127.0.0.1:8765" in context.allowed_origins
    context.close()


def test_parser_rejects_non_loopback_host() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--host", "0.0.0.0"])


def test_browser_url_keeps_token_out_of_query_string() -> None:
    url = build_browser_url("127.0.0.1", 8765, "secret")

    assert url == "http://127.0.0.1:8765/#token=secret"


def test_production_context_uses_dxgi_capture_backend() -> None:
    context = build_context("test-token", "127.0.0.1", 8765)
    try:
        assert isinstance(context.capture._backends["dxcam"], DxcamMonitorCaptureBackend)
    finally:
        context.close()
