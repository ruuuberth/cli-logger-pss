from __future__ import annotations

import json
import pkgutil
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata


@dataclass(frozen=True)
class BuildInfo:
    version: str
    git_sha: str
    build_time: str
    source: str

    @property
    def display_label(self) -> str:
        version = self.version or "dev"
        sha = (self.git_sha or "unknown")[:7]
        return f"{version} ({sha})"


def _default_version() -> str:
    try:
        return metadata.version("pss-logger-native")
    except Exception:
        return "0.1.0"


@lru_cache(maxsize=1)
def get_build_info() -> BuildInfo:
    try:
        raw = pkgutil.get_data("app", "resources/build_metadata.json")
    except (FileNotFoundError, OSError):
        raw = None
    if not raw:
        return BuildInfo(
            version=_default_version(),
            git_sha="dev",
            build_time="unknown",
            source="fallback",
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return BuildInfo(
            version=_default_version(),
            git_sha="invalid",
            build_time="unknown",
            source="invalid",
        )

    return BuildInfo(
        version=str(payload.get("version") or _default_version()),
        git_sha=str(payload.get("git_sha") or "unknown"),
        build_time=str(payload.get("build_time") or "unknown"),
        source=str(payload.get("source") or "embedded"),
    )
