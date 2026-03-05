#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.database import ensure_sqlite_indexes, ensure_sqlite_schema
from app.services.api_flow_storage import ApiFlowRepository


def main() -> int:
    ensure_sqlite_schema()
    ensure_sqlite_indexes()

    repo = ApiFlowRepository()

    cleaned_total = 0
    while True:
        updated = repo.backfill_response_body_cleaned(batch_size=200)
        if updated <= 0:
            break
        cleaned_total += updated

    normalized_total = 0
    while True:
        inserted = repo.sync_battle_replays_from_api_flow(batch_size=500)
        if inserted <= 0:
            break
        normalized_total += inserted

    children_total = 0
    while True:
        inserted = repo.sync_battle_replay_children(batch_size=200)
        if inserted <= 0:
            break
        children_total += inserted

    print(f"cleaned_backfill={cleaned_total}")
    print(f"normalized_inserted={normalized_total}")
    print(f"normalized_children_inserted={children_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
