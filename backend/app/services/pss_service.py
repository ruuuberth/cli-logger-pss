import logging
from datetime import date, datetime, timezone
from importlib.util import find_spec
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pss_models import CrewDesign, ItemDesign, ShipDesign

if find_spec("pssapi") is not None:
    from pssapi import PssApiClient  # type: ignore
else:
    PssApiClient = None  # type: ignore

logger = logging.getLogger(__name__)


class PSSService:
    def __init__(self, db: Session):
        self.db = db
        self._client: Any = None
        self._client_initialized = False

    async def get_item_designs(
        self, force_refresh: bool = False, ttl_seconds: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            ttl = self._resolve_ttl(ttl_seconds)
            cached_items = self.db.query(ItemDesign).all()
            if cached_items and not force_refresh and self._is_cache_fresh(cached_items, ttl):
                logger.info(
                    "event=item_designs source=cache count=%s ttl_seconds=%s",
                    len(cached_items),
                    ttl,
                )
                return [self._serialize_item_design(item) for item in cached_items]

            if self._ensure_client() is None:
                return [self._serialize_item_design(item) for item in cached_items]

            item_service = self._get_service("item_service")
            if item_service is None:
                return [self._serialize_item_design(item) for item in cached_items]

            item_designs = await self._call_async_first(
                item_service, ["list_item_designs", "list_items_designs"]
            )
            if item_designs is None:
                return [self._serialize_item_design(item) for item in cached_items]

            rows = [self._item_row(design) for design in item_designs]
            rows = [row for row in rows if row["item_design_id"] is not None]
            self._upsert_rows(ItemDesign, rows, "item_design_id")
            self.db.commit()

            refreshed = self.db.query(ItemDesign).all()
            logger.info("event=item_designs source=api count=%s", len(refreshed))
            return [self._serialize_item_design(item) for item in refreshed]
        except Exception:
            self.db.rollback()
            logger.exception("event=item_designs_error")
            return []

    async def get_item_design(self, item_id: int) -> Optional[Dict[str, Any]]:
        try:
            cached_item = self.db.query(ItemDesign).filter(ItemDesign.item_design_id == item_id).first()
            if cached_item:
                return self._serialize_item_design(cached_item)

            if self._ensure_client() is None:
                return None
            item_service = self._get_service("item_service")
            if item_service is None:
                return None

            item_design = await self._call_async_first(
                item_service, ["get_item_design", "get_items_design"], item_id
            )
            if item_design is None:
                item_designs = await self._call_async_first(item_service, ["list_item_designs"])
                item_design = self._find_design_by_id(item_designs, item_id, ("item_design_id", "id"))
            if item_design is None:
                return None

            row = self._item_row(item_design)
            if row["item_design_id"] is None:
                return None
            self._upsert_rows(ItemDesign, [row], "item_design_id")
            self.db.commit()

            db_item = self.db.query(ItemDesign).filter(ItemDesign.item_design_id == item_id).first()
            return self._serialize_item_design(db_item) if db_item else None
        except Exception:
            self.db.rollback()
            logger.exception("event=item_design_error item_id=%s", item_id)
            return None

    async def get_ship_designs(
        self, force_refresh: bool = False, ttl_seconds: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            ttl = self._resolve_ttl(ttl_seconds)
            cached_ships = self.db.query(ShipDesign).all()
            if cached_ships and not force_refresh and self._is_cache_fresh(cached_ships, ttl):
                logger.info(
                    "event=ship_designs source=cache count=%s ttl_seconds=%s",
                    len(cached_ships),
                    ttl,
                )
                return [self._serialize_ship_design(ship) for ship in cached_ships]

            if self._ensure_client() is None:
                return [self._serialize_ship_design(ship) for ship in cached_ships]

            ship_service = self._get_service("ship_service")
            if ship_service is None:
                return [self._serialize_ship_design(ship) for ship in cached_ships]

            ship_designs = await self._call_async_first(
                ship_service,
                ["list_ship_designs", "list_all_ship_designs", "list_ships_designs", "list_ships"],
            )
            if ship_designs is None:
                return [self._serialize_ship_design(ship) for ship in cached_ships]

            rows = [self._ship_row(design) for design in ship_designs]
            rows = [row for row in rows if row["ship_design_id"] is not None]
            self._upsert_rows(ShipDesign, rows, "ship_design_id")
            self.db.commit()

            refreshed = self.db.query(ShipDesign).all()
            logger.info("event=ship_designs source=api count=%s", len(refreshed))
            return [self._serialize_ship_design(ship) for ship in refreshed]
        except Exception:
            self.db.rollback()
            logger.exception("event=ship_designs_error")
            return []

    async def get_ship_design(self, ship_id: int) -> Optional[Dict[str, Any]]:
        try:
            cached_ship = self.db.query(ShipDesign).filter(ShipDesign.ship_design_id == ship_id).first()
            if cached_ship:
                return self._serialize_ship_design(cached_ship)

            if self._ensure_client() is None:
                return None
            ship_service = self._get_service("ship_service")
            if ship_service is None:
                return None

            ship_design = await self._call_async_first(ship_service, ["get_ship_design", "get_ship"], ship_id)
            if ship_design is None:
                all_ship_designs = await self._call_async_first(
                    ship_service, ["list_all_ship_designs", "list_ship_designs"]
                )
                ship_design = self._find_design_by_id(
                    all_ship_designs, ship_id, ("ship_design_id", "id")
                )
            if ship_design is None:
                return None

            row = self._ship_row(ship_design)
            if row["ship_design_id"] is None:
                return None
            self._upsert_rows(ShipDesign, [row], "ship_design_id")
            self.db.commit()

            db_ship = self.db.query(ShipDesign).filter(ShipDesign.ship_design_id == ship_id).first()
            return self._serialize_ship_design(db_ship) if db_ship else None
        except Exception:
            self.db.rollback()
            logger.exception("event=ship_design_error ship_id=%s", ship_id)
            return None

    async def get_crew_designs(
        self, force_refresh: bool = False, ttl_seconds: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        try:
            ttl = self._resolve_ttl(ttl_seconds)
            cached_crews = self.db.query(CrewDesign).all()
            if cached_crews and not force_refresh and self._is_cache_fresh(cached_crews, ttl):
                logger.info(
                    "event=crew_designs source=cache count=%s ttl_seconds=%s",
                    len(cached_crews),
                    ttl,
                )
                return [self._serialize_crew_design(crew) for crew in cached_crews]

            if self._ensure_client() is None:
                return [self._serialize_crew_design(crew) for crew in cached_crews]

            crew_service = self._get_service("crew_service", "character_service")
            if crew_service is None:
                return [self._serialize_crew_design(crew) for crew in cached_crews]

            crew_designs = await self._call_async_first(
                crew_service, ["list_crew_designs", "list_all_character_designs", "list_character_designs"]
            )
            if crew_designs is None:
                return [self._serialize_crew_design(crew) for crew in cached_crews]

            rows = [self._crew_row(design) for design in crew_designs]
            rows = [row for row in rows if row["crew_design_id"] is not None]
            self._upsert_rows(CrewDesign, rows, "crew_design_id")
            self.db.commit()

            refreshed = self.db.query(CrewDesign).all()
            logger.info("event=crew_designs source=api count=%s", len(refreshed))
            return [self._serialize_crew_design(crew) for crew in refreshed]
        except Exception:
            self.db.rollback()
            logger.exception("event=crew_designs_error")
            return []

    async def get_crew_design(self, crew_id: int) -> Optional[Dict[str, Any]]:
        try:
            cached_crew = self.db.query(CrewDesign).filter(CrewDesign.crew_design_id == crew_id).first()
            if cached_crew:
                return self._serialize_crew_design(cached_crew)

            if self._ensure_client() is None:
                return None
            crew_service = self._get_service("crew_service", "character_service")
            if crew_service is None:
                return None

            crew_design = await self._call_async_first(
                crew_service, ["get_crew_design", "get_character_design"], crew_id
            )
            if crew_design is None:
                all_crew_designs = await self._call_async_first(
                    crew_service, ["list_all_character_designs", "list_crew_designs"]
                )
                crew_design = self._find_design_by_id(
                    all_crew_designs, crew_id, ("crew_design_id", "character_design_id", "id")
                )
            if crew_design is None:
                return None

            row = self._crew_row(crew_design)
            if row["crew_design_id"] is None:
                return None
            self._upsert_rows(CrewDesign, [row], "crew_design_id")
            self.db.commit()

            db_crew = self.db.query(CrewDesign).filter(CrewDesign.crew_design_id == crew_id).first()
            return self._serialize_crew_design(db_crew) if db_crew else None
        except Exception:
            self.db.rollback()
            logger.exception("event=crew_design_error crew_id=%s", crew_id)
            return None

    def _serialize_item_design(self, item: ItemDesign) -> Dict[str, Any]:
        return {
            "id": item.item_design_id,
            "name": item.name,
            "description": item.description,
            "rarity": item.rarity,
            "item_type": item.item_type,
            "stats": item.stats,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_ship_design(self, ship: ShipDesign) -> Dict[str, Any]:
        return {
            "id": ship.ship_design_id,
            "name": ship.name,
            "description": ship.description,
            "class_type": ship.class_type,
            "stats": ship.stats,
            "created_at": ship.created_at.isoformat() if ship.created_at else None,
        }

    def _serialize_crew_design(self, crew: CrewDesign) -> Dict[str, Any]:
        return {
            "id": crew.crew_design_id,
            "name": crew.name,
            "description": crew.description,
            "race": crew.race,
            "role": crew.role,
            "stats": crew.stats,
            "created_at": crew.created_at.isoformat() if crew.created_at else None,
        }

    def _extract_stats(self, obj: Any) -> Dict[str, Any]:
        stats: Dict[str, Any] = {}
        stat_attributes = ["attack", "defense", "health", "speed", "critical", "dodge"]

        for attr in stat_attributes:
            if hasattr(obj, attr):
                stats[attr] = getattr(obj, attr)
        return stats

    def _extract_raw_data(self, obj: Any) -> Dict[str, Any]:
        obj_dict = getattr(obj, "__dict__", None)
        if callable(obj_dict):
            try:
                return self._to_jsonable(obj_dict())
            except Exception:
                pass
        elif isinstance(obj_dict, dict):
            return self._to_jsonable(obj_dict)

        try:
            return self._to_jsonable(vars(obj))
        except TypeError:
            return self._to_jsonable(obj)

    def _to_jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): self._to_jsonable(v) for k, v in value.items() if not callable(v)}
        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable(v) for v in value]
        if callable(value):
            return str(value)

        nested_dict = getattr(value, "__dict__", None)
        if callable(nested_dict):
            try:
                return self._to_jsonable(nested_dict())
            except Exception:
                return str(value)
        if isinstance(nested_dict, dict):
            return self._to_jsonable(nested_dict)
        return str(value)

    def _get_service(self, *names: str) -> Any:
        client = self._ensure_client()
        if client is None:
            return None
        for name in names:
            service = getattr(client, name, None)
            if service is not None:
                return service
        logger.warning("event=pss_service_missing names=%s", ",".join(names))
        return None

    def _ensure_client(self) -> Any:
        if self._client_initialized:
            return self._client

        self._client_initialized = True
        if PssApiClient is None:
            self._client = None
            return None

        try:
            self._client = PssApiClient()
        except Exception:
            logger.exception("event=pss_client_init_error")
            self._client = None
        return self._client

    async def _call_async_first(self, service: Any, method_names: List[str], *args: Any) -> Any:
        for method_name in method_names:
            method = getattr(service, method_name, None)
            if method is None:
                continue
            result = method(*args)
            if hasattr(result, "__await__"):
                return await result
            return result
        logger.warning(
            "event=pss_method_missing service=%s methods=%s",
            service.__class__.__name__,
            ",".join(method_names),
        )
        return None

    def _find_design_by_id(self, designs: Any, target_id: int, id_attrs: tuple[str, ...]) -> Any:
        if not designs:
            return None
        for design in designs:
            for attr in id_attrs:
                if getattr(design, attr, None) == target_id:
                    return design
        return None

    def _first_attr(self, obj: Any, *attrs: str) -> Any:
        for attr in attrs:
            value = getattr(obj, attr, None)
            if value is not None:
                return value
        return None

    def _item_row(self, design: Any) -> Dict[str, Any]:
        return {
            "item_design_id": self._first_attr(design, "item_design_id", "id"),
            "name": self._first_attr(design, "item_design_name", "name") or "",
            "description": self._first_attr(design, "description") or "",
            "rarity": self._first_attr(design, "rarity") or "",
            "item_type": self._first_attr(design, "item_type") or "",
            "stats": self._extract_stats(design),
            "raw_data": self._extract_raw_data(design),
        }

    def _ship_row(self, design: Any) -> Dict[str, Any]:
        return {
            "ship_design_id": self._first_attr(design, "ship_design_id", "id"),
            "name": self._first_attr(design, "ship_design_name", "name") or "",
            "description": self._first_attr(design, "description") or "",
            "class_type": self._first_attr(design, "class_type") or "",
            "stats": self._extract_stats(design),
            "raw_data": self._extract_raw_data(design),
        }

    def _crew_row(self, design: Any) -> Dict[str, Any]:
        return {
            "crew_design_id": self._first_attr(design, "crew_design_id", "character_design_id", "id"),
            "name": self._first_attr(design, "crew_design_name", "character_design_name", "name") or "",
            "description": self._first_attr(design, "description", "character_design_description") or "",
            "race": self._first_attr(design, "race") or "",
            "role": self._first_attr(design, "role") or "",
            "stats": self._extract_stats(design),
            "raw_data": self._extract_raw_data(design),
        }

    def _upsert_rows(self, model: Any, rows: List[Dict[str, Any]], key_column: str) -> None:
        if not rows:
            return
        bind = self.db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        table = model.__table__

        update_dict = {k: table.c[k] for k in rows[0].keys() if k not in {"id", "created_at", key_column}}
        if "updated_at" in table.c:
            update_dict["updated_at"] = datetime.now(timezone.utc)

        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(table).values(rows)
            stmt = stmt.on_conflict_do_update(index_elements=[key_column], set_=update_dict)
            self.db.execute(stmt)
            return
        if dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(table).values(rows)
            stmt = stmt.on_conflict_do_update(index_elements=[key_column], set_=update_dict)
            self.db.execute(stmt)
            return

        for row in rows:
            key_value = row.get(key_column)
            existing = self.db.execute(
                select(model).where(getattr(model, key_column) == key_value)
            ).scalar_one_or_none()
            if existing is None:
                self.db.add(model(**row))
            else:
                for key, value in row.items():
                    setattr(existing, key, value)

    def _resolve_ttl(self, ttl_seconds: Optional[int]) -> int:
        if ttl_seconds is not None:
            return max(0, ttl_seconds)
        return max(0, settings.DESIGNS_CACHE_TTL_SECONDS)

    def _is_cache_fresh(self, records: List[Any], ttl_seconds: int) -> bool:
        if ttl_seconds <= 0 or not records:
            return False
        timestamps = [r.updated_at or r.created_at for r in records if (r.updated_at or r.created_at)]
        if not timestamps:
            return True
        latest = max(timestamps)
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - latest).total_seconds()
        return age <= ttl_seconds
