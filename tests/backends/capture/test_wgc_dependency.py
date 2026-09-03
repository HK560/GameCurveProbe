import importlib.util


def test_windows_capture_dependency_is_importable() -> None:
    assert importlib.util.find_spec("windows_capture") is not None
