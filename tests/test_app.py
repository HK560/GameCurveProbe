from __future__ import annotations

from gamecurveprobe.app import build_context, build_parser


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
