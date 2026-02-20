from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .game_data import GameFile


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS imported_game_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_dir TEXT,
                    relative_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_ext TEXT,
                    file_size INTEGER NOT NULL,
                    content_hash TEXT UNIQUE NOT NULL,
                    content_text TEXT NOT NULL,
                    imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
                """
            )

    def import_files(self, source_dir: str, files: list[GameFile]) -> dict[str, int]:
        imported = 0
        updated = 0

        with self._connect() as conn:
            for game_file in files:
                content_hash = hashlib.sha256(game_file.content.encode("utf-8", errors="replace")).hexdigest()
                existing = conn.execute(
                    "SELECT id FROM imported_game_files WHERE content_hash = ?",
                    (content_hash,),
                ).fetchone()

                if existing:
                    conn.execute(
                        """
                        UPDATE imported_game_files
                        SET source_dir = ?, relative_path = ?, file_name = ?, file_size = ?, content_text = ?, imported_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            source_dir,
                            game_file.relative_path,
                            game_file.name,
                            game_file.size,
                            game_file.content,
                            existing[0],
                        ),
                    )
                    updated += 1
                    continue

                conn.execute(
                    """
                    INSERT INTO imported_game_files (source_dir, relative_path, file_name, file_size, content_hash, content_text)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_dir,
                        game_file.relative_path,
                        game_file.name,
                        game_file.size,
                        content_hash,
                        game_file.content,
                    ),
                )
                imported += 1

        return {"imported": imported, "updated": updated, "total": len(files)}
