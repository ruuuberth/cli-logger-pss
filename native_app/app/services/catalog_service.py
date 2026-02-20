from __future__ import annotations

import asyncio
from typing import Any

from app.models.database import SessionLocal
from app.services.pss_service import PSSService


class CatalogService:
    def get_items(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        return self._run("items", force_refresh)

    def get_ships(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        return self._run("ships", force_refresh)

    def get_crews(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        return self._run("crews", force_refresh)

    def _run(self, entity: str, force_refresh: bool) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            service = PSSService(db)
            if entity == "items":
                return asyncio.run(service.get_item_designs(force_refresh=force_refresh))
            if entity == "ships":
                return asyncio.run(service.get_ship_designs(force_refresh=force_refresh))
            if entity == "crews":
                return asyncio.run(service.get_crew_designs(force_refresh=force_refresh))
            return []
        finally:
            db.close()
