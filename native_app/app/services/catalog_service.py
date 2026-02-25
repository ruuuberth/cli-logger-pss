from __future__ import annotations

import asyncio
from typing import Any

from app.models.database import SessionLocal
from app.services.pss_service import PSSService


class CatalogService:
    def get_items(
        self,
        force_refresh: bool = False,
        item_type: str | None = None,
        source: str = "db",
    ) -> list[dict[str, Any]]:
        return self._run("items", force_refresh, item_type=item_type, source=source)

    def get_ships(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        return self._run("ships", force_refresh)

    def get_crews(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        return self._run("crews", force_refresh)

    def _run(
        self,
        entity: str,
        force_refresh: bool,
        item_type: str | None = None,
        source: str = "db",
    ) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            service = PSSService(db)
            if entity == "items":
                if source == "api":
                    return asyncio.run(service.get_item_designs_api(item_type=item_type))
                if source == "local":
                    return asyncio.run(service.get_item_designs_from_local_files(item_type))
                return asyncio.run(service.get_item_designs_db(item_type))
            if entity == "ships":
                return asyncio.run(service.get_ship_designs(force_refresh=force_refresh))
            if entity == "crews":
                return asyncio.run(service.get_crew_designs(force_refresh=force_refresh))
            return []
        finally:
            db.close()
