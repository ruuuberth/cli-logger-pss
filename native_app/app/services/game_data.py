from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TEXT_EXTENSIONS = {".xml", ".json", ".txt", ".log", ".csv", ".ini", ".cfg", ".yaml", ".yml"}
MAX_FILES = 300
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024


@dataclass
class GameFile:
    name: str
    relative_path: str
    size: int
    content: str


def candidate_directories() -> list[Path]:
    home = Path.home()
    if Path.home().drive:
        return [
            home / "AppData" / "LocalLow" / "SavySoda" / "Pixel Starships",
            home / "AppData" / "Local" / "SavySoda" / "Pixel Starships",
            home / "Documents" / "SavySoda" / "Pixel Starships",
        ]

    # macOS
    mac_a = home / "Library" / "Application Support" / "SavySoda" / "Pixel Starships"
    if mac_a.exists() or (home / "Library").exists():
        return [
            mac_a,
            home / "Library" / "Caches" / "SavySoda" / "Pixel Starships",
        ]

    # Linux
    return [
        home / ".config" / "unity3d" / "SavySoda" / "Pixel Starships",
        home / ".local" / "share" / "SavySoda" / "Pixel Starships",
        home / "SavySoda" / "Pixel Starships",
    ]


def detect_game_directory() -> Path | None:
    for candidate in candidate_directories():
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _is_exportable(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    return 0 < size <= MAX_FILE_SIZE_BYTES


def scan_game_files(base_dir: Path) -> list[GameFile]:
    files: list[GameFile] = []
    if not base_dir.exists() or not base_dir.is_dir():
        return files

    for path in _iter_files(base_dir):
        if len(files) >= MAX_FILES:
            break
        if not _is_exportable(path):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            files.append(
                GameFile(
                    name=path.name,
                    relative_path=str(path.relative_to(base_dir)),
                    size=path.stat().st_size,
                    content=content,
                )
            )
        except OSError:
            continue

    return files


def _iter_files(base_dir: Path) -> Iterable[Path]:
    for path in base_dir.rglob("*"):
        if path.is_file():
            yield path
