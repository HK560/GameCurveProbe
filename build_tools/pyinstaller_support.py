from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path


def _resolve_package_root(package_name: str) -> Path:
    spec = find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        raise ModuleNotFoundError(f"Could not resolve package root for {package_name!r}.")
    return Path(next(iter(spec.submodule_search_locations))).resolve()


def collect_package_files(package_name: str, patterns: list[str]) -> list[tuple[str, str]]:
    """Collect package files while preserving the package-relative directory layout."""
    package_root = _resolve_package_root(package_name)
    package_parent = package_root.parent
    collected: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for pattern in patterns:
        for path in sorted(package_root.glob(pattern)):
            if not path.is_file():
                continue
            source = str(path)
            target = path.relative_to(package_parent).parent.as_posix()
            item = (source, target)
            if item not in seen:
                collected.append(item)
                seen.add(item)

    return collected
