import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pss_models import (
    BattleIndex,
    BattleReport,
    CrewDesign,
    ImportedGameFile,
    ItemDesign,
    ItemIngredient,
    ItemTag,
    ShipDesign,
)

if find_spec("pssapi") is not None:
    from pssapi import PssApiClient  # type: ignore
else:
    PssApiClient = None  # type: ignore

logger = logging.getLogger(__name__)


class PSSFeatureNotSupportedError(Exception):
    pass


class PSSAuthenticationError(Exception):
    pass


class PSSService:
    _battle_report_cache: Dict[int, Dict[str, Any]] = {}
    _unknown_item_keys: set[str] = set()
    _local_item_rows_cache: Dict[str, List[Dict[str, Any]]] = {}
    _api_item_rows_cache: Dict[str, Any] = {}

    def __init__(self, db: Session):
        self.db = db
        self._client: Any = None
        self._client_initialized = False

    async def get_item_designs(
        self, force_refresh: bool = False, ttl_seconds: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        cached_items: List[ItemDesign] = []
        try:
            ttl = self._resolve_ttl(ttl_seconds)
            cached_items = self.db.query(ItemDesign).all()
            if cached_items and not force_refresh:
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
            self._sync_item_relations(rows)
            self.db.commit()

            refreshed = self.db.query(ItemDesign).all()
            logger.info("event=item_designs source=api count=%s", len(refreshed))
            return [self._serialize_item_design(item) for item in refreshed]
        except Exception as exc:
            self.db.rollback()
            raw_reason = ""
            if getattr(exc, "orig", None) is not None:
                raw_reason = str(exc.orig)
            if not raw_reason:
                raw_reason = str(exc)
            reason = " ".join(raw_reason.split())[:240]
            logger.error(
                "event=item_designs_error type=%s reason=%s",
                exc.__class__.__name__,
                reason or "n/a",
            )
            if cached_items:
                return [self._serialize_item_design(item) for item in cached_items]
            return []

    async def get_item_designs_by_type(
        self,
        item_type: str,
        force_refresh: bool = False,
        ttl_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if force_refresh:
                await self.get_item_designs(force_refresh=True, ttl_seconds=ttl_seconds)
            cached_items = (
                self.db.query(ItemDesign)
                .filter(ItemDesign.item_type == item_type)
                .all()
            )
            return [self._serialize_item_design(item) for item in cached_items]
        except Exception:
            self.db.rollback()
            logger.exception("event=item_designs_by_type_error item_type=%s", item_type)
            return []

    async def get_item_designs_api(
        self,
        item_type: str | None = None,
        refresh: bool = False,
        ttl_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        ttl = max(0, settings.ITEMS_API_CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds)
        now = datetime.now(timezone.utc)
        cached_at = self._api_item_rows_cache.get("cached_at")
        cached_rows = self._api_item_rows_cache.get("rows")
        if (
            not refresh
            and cached_at is not None
            and isinstance(cached_rows, list)
            and (now - cached_at).total_seconds() <= ttl
        ):
            rows = cached_rows
        else:
            rows = await self.get_item_designs(force_refresh=True)
            self._api_item_rows_cache["cached_at"] = now
            self._api_item_rows_cache["rows"] = rows

        if item_type:
            if item_type == "Resources":
                return [r for r in rows if r.get("item_type") in {"Gas", "Mineral"}]
            return [r for r in rows if r.get("item_type") == item_type]
        return rows

    async def get_item_designs_db(self, item_type: str | None = None) -> List[Dict[str, Any]]:
        try:
            query = self.db.query(ItemDesign)
            if item_type:
                query = query.filter(ItemDesign.item_type == item_type)
            rows = query.all()
            return [self._serialize_item_design(item) for item in rows]
        except Exception:
            self.db.rollback()
            logger.exception("event=item_designs_db_error item_type=%s", item_type)
            return []

    async def get_item_designs_from_local_files(self, item_type: str | None = None) -> List[Dict[str, Any]]:
        try:
            files = (
                self.db.query(ImportedGameFile)
                .filter(
                    ImportedGameFile.file_name == "ItemDesigns.txt"
                )
                .all()
            )
            available = {f.file_name for f in files}
            if "ItemDesigns.txt" not in available:
                logger.warning(
                    "event=item_designs_local_missing_file file=ItemDesigns.txt note=import_scan_limit_or_missing_export"
                )
                return []
            rows: List[Dict[str, Any]] = []
            for file in files:
                cache_key = file.content_hash or ""
                if cache_key and cache_key in self._local_item_rows_cache:
                    parsed_rows = self._local_item_rows_cache[cache_key]
                else:
                    parsed_rows = self._parse_local_item_file(file.file_name or "", file.content_text or "")
                    if cache_key:
                        self._local_item_rows_cache[cache_key] = parsed_rows
                rows.extend(parsed_rows)

            if item_type:
                if item_type == "Resources":
                    rows = [r for r in rows if r.get("item_type") in {"Gas", "Mineral"}]
                else:
                    rows = [r for r in rows if r.get("item_type") == item_type]
            return rows
        except Exception:
            self.db.rollback()
            logger.exception("event=item_designs_local_files_error item_type=%s", item_type)
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
            self._sync_item_relations([row])
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
        cached_ships: List[ShipDesign] = []
        try:
            ttl = self._resolve_ttl(ttl_seconds)
            cached_ships = self.db.query(ShipDesign).all()
            if cached_ships and not force_refresh:
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
            if cached_ships:
                return [self._serialize_ship_design(ship) for ship in cached_ships]
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
        cached_crews: List[CrewDesign] = []
        try:
            ttl = self._resolve_ttl(ttl_seconds)
            cached_crews = self.db.query(CrewDesign).all()
            if cached_crews and not force_refresh:
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
            if cached_crews:
                return [self._serialize_crew_design(crew) for crew in cached_crews]
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

    async def login_with_email_password(
        self, email: str, password: str, device_key: Optional[str] = None
    ) -> Dict[str, Any]:
        normalized_email = email.strip()
        if not normalized_email or not password:
            raise PSSAuthenticationError("Email y password son obligatorios.")

        checksum_key = settings.PSS_CHECKSUM_KEY.strip()
        if not checksum_key:
            raise PSSFeatureNotSupportedError(
                "Falta configurar PSS_CHECKSUM_KEY en el backend para habilitar login por email/password."
            )

        client = self._ensure_client()
        if client is None:
            raise PSSFeatureNotSupportedError("No se pudo inicializar el cliente de pssapi.")

        user_service = self._get_service("user_service")
        if user_service is None:
            raise PSSFeatureNotSupportedError("No se encontro user_service en pssapi.")

        chosen_device_key = (device_key or "").strip() or str(uuid4())

        try:
            now = datetime.now(timezone.utc)
            checksum = user_service.utils.create_device_login_checksum(
                chosen_device_key,
                client.device_type,
                now,
                checksum_key,
            )
            authorization = await user_service.user_email_password_authorize(
                access_token="00000000-0000-0000-0000-000000000000",
                checksum=checksum,
                client_date_time=now,
                device_key=chosen_device_key,
                email=normalized_email,
                is_web=True,
                language_key=str(client.language_key),
                password=password,
            )
        except Exception as e:
            raise PSSAuthenticationError(f"No fue posible autorizar el usuario: {e}") from e

        refresh_token = getattr(authorization, "refresh_token", None)
        auth_error = getattr(authorization, "error_message", None)
        if auth_error:
            raise PSSAuthenticationError(auth_error)
        if not refresh_token:
            raise PSSAuthenticationError("La autorizacion no devolvio refresh_token.")

        try:
            login_now = datetime.now(timezone.utc)
            login_checksum = user_service.utils.create_device_login_checksum(
                chosen_device_key,
                client.device_type,
                login_now,
                checksum_key,
            )
            user_login = await user_service.device_login(
                checksum=login_checksum,
                client_date_time=login_now,
                device_key=chosen_device_key,
                device_type=client.device_type,
                refresh_token=refresh_token,
            )
        except Exception as e:
            raise PSSAuthenticationError(f"No fue posible obtener access_token: {e}") from e

        access_token = getattr(user_login, "access_token", None)
        user = getattr(user_login, "user", None) or getattr(authorization, "user", None)
        if not access_token:
            raise PSSAuthenticationError("El login no devolvio access_token.")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "device_key": chosen_device_key,
            "user_id": self._first_attr(user, "id", "user_id"),
            "username": self._first_attr(user, "name", "username"),
        }

    async def login_with_refresh_token(
        self,
        refresh_token: str,
        device_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_refresh_token = refresh_token.strip()
        if not normalized_refresh_token:
            raise PSSAuthenticationError("refresh_token es obligatorio.")

        checksum_key = settings.PSS_CHECKSUM_KEY.strip()
        if not checksum_key:
            raise PSSFeatureNotSupportedError(
                "Falta configurar PSS_CHECKSUM_KEY en el backend para convertir refresh_token en access_token."
            )

        client = self._ensure_client()
        if client is None:
            raise PSSFeatureNotSupportedError("No se pudo inicializar el cliente de pssapi.")

        user_service = self._get_service("user_service")
        if user_service is None:
            raise PSSFeatureNotSupportedError("No se encontro user_service en pssapi.")

        chosen_device_key = (device_key or "").strip() or str(uuid4())

        try:
            login_now = datetime.now(timezone.utc)
            login_checksum = user_service.utils.create_device_login_checksum(
                chosen_device_key,
                client.device_type,
                login_now,
                checksum_key,
            )
            user_login = await user_service.device_login(
                checksum=login_checksum,
                client_date_time=login_now,
                device_key=chosen_device_key,
                device_type=client.device_type,
                refresh_token=normalized_refresh_token,
            )
        except Exception as e:
            raise PSSAuthenticationError(f"No fue posible obtener access_token: {e}") from e

        access_token = getattr(user_login, "access_token", None)
        user = getattr(user_login, "user", None)
        if not access_token:
            raise PSSAuthenticationError("El login con refresh_token no devolvio access_token.")

        return {
            "access_token": access_token,
            "refresh_token": normalized_refresh_token,
            "device_key": chosen_device_key,
            "user_id": self._first_attr(user, "id", "user_id"),
            "username": self._first_attr(user, "name", "username"),
        }

    async def get_battle_report(
        self,
        battle_id: int,
        access_token: Optional[str] = None,
        force_refresh: bool = False,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        if battle_id <= 0:
            raise ValueError("battle_id debe ser mayor que 0.")

        ttl = self._resolve_battle_report_ttl(ttl_seconds)
        cached_db = self.db.query(BattleReport).filter(BattleReport.battle_id == battle_id).first()

        if not force_refresh:
            memory_hit = self._get_cached_battle_report(battle_id, ttl)
            if memory_hit is not None:
                return memory_hit
            if cached_db is not None:
                payload = self._serialize_battle_report(cached_db, source="database")
                self._set_cached_battle_report(battle_id, payload)
                return payload

        token_for_http = (access_token or "").strip() or None

        if token_for_http is None:
            if cached_db is not None:
                payload = self._serialize_battle_report(cached_db, source="database")
                self._set_cached_battle_report(battle_id, payload)
                return payload
            raise PSSAuthenticationError(
                "Se requiere access_token para descargar BattleService/GetBattle3."
            )

        xml_report, source_endpoint, remote_error = await self._fetch_battle_report_xml_via_http(
            battle_id=battle_id,
            access_token=token_for_http,
        )
        if not xml_report:
            if remote_error:
                if "authorize access token" in remote_error.lower():
                    raise PSSAuthenticationError(remote_error)
                raise PSSFeatureNotSupportedError(remote_error)
            if cached_db is not None:
                payload = self._serialize_battle_report(cached_db, source="database")
                self._set_cached_battle_report(battle_id, payload)
                return payload
            raise PSSFeatureNotSupportedError(
                "No fue posible obtener el reporte de batalla desde la API remota."
            )

        summary = self._parse_battle_report_summary(xml_report, battle_id)
        row = {
            "battle_id": battle_id,
            "player_name": summary.get("player_name"),
            "opponent_name": summary.get("opponent_name"),
            "battle_type": summary.get("battle_type"),
            "result": summary.get("result"),
            "battle_start_date": summary.get("battle_start_date"),
            "battle_end_date": summary.get("battle_end_date"),
            "xml_report": xml_report,
            "summary_data": summary.get("raw_data"),
            "source_endpoint": source_endpoint,
            "fetched_at": datetime.now(timezone.utc),
        }

        try:
            self._upsert_rows(BattleReport, [row], "battle_id")
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("event=battle_report_upsert_error battle_id=%s", battle_id)
            raise

        saved = self.db.query(BattleReport).filter(BattleReport.battle_id == battle_id).first()
        if saved is None:
            raise PSSFeatureNotSupportedError("No fue posible persistir el reporte de batalla.")

        payload = self._serialize_battle_report(saved, source="api")
        self._persist_battle_index_rows(
            [
                {
                    "id": payload.get("battle_id"),
                    "player_name": payload.get("player_name"),
                    "opponent_name": payload.get("opponent_name"),
                    "battle_type": payload.get("battle_type"),
                    "result": payload.get("result"),
                    "created_at": payload.get("battle_end_date") or payload.get("battle_start_date"),
                    "raw_data": payload.get("summary_data") or {},
                }
            ]
        )
        self._set_cached_battle_report(battle_id, payload)
        return payload

    def list_stored_battle_ids(
        self,
        limit: int = 200,
        offset: int = 0,
        search: Optional[str] = None,
        has_report: Optional[bool] = None,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)
        normalized_search = (search or "").strip()

        query = self.db.query(BattleIndex, BattleReport.battle_id, BattleReport.xml_report).outerjoin(
            BattleReport, BattleReport.battle_id == BattleIndex.battle_id
        )

        if normalized_search:
            token = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    cast(BattleIndex.battle_id, String).ilike(token),
                    BattleIndex.player_name.ilike(token),
                    BattleIndex.opponent_name.ilike(token),
                    BattleIndex.result.ilike(token),
                    BattleIndex.battle_type.ilike(token),
                )
            )
        if has_report is True:
            query = query.filter(BattleReport.battle_id.isnot(None))
        elif has_report is False:
            query = query.filter(BattleReport.battle_id.is_(None))

        total = query.count()
        rows = (
            query.order_by(BattleIndex.last_seen_at.desc(), BattleIndex.battle_id.desc())
            .offset(safe_offset)
            .limit(safe_limit)
            .all()
        )

        payload: List[Dict[str, Any]] = []
        updated_index = False
        for index_row, report_battle_id, report_xml in rows:
            row_has_report = report_battle_id is not None
            if row_has_report and report_xml and (not index_row.player_name or not index_row.opponent_name):
                summary = self._parse_battle_report_summary(report_xml, index_row.battle_id)
                parsed_player = str(summary.get("player_name") or "").strip()
                parsed_opponent = str(summary.get("opponent_name") or "").strip()
                if parsed_player and not index_row.player_name:
                    index_row.player_name = parsed_player[:255]
                    updated_index = True
                if parsed_opponent and not index_row.opponent_name:
                    index_row.opponent_name = parsed_opponent[:255]
                    updated_index = True

            payload.append(
                {
                    "battle_id": index_row.battle_id,
                    "player_name": index_row.player_name,
                    "opponent_name": index_row.opponent_name,
                    "battle_type": index_row.battle_type,
                    "result": index_row.result,
                    "trophy_change": index_row.trophy_change,
                    "created_at": index_row.created_at_value,
                    "first_seen_at": index_row.first_seen_at.isoformat() if index_row.first_seen_at else None,
                    "last_seen_at": index_row.last_seen_at.isoformat() if index_row.last_seen_at else None,
                    "has_report": row_has_report,
                }
            )
        if updated_index:
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("event=battle_index_enrich_commit_error")

        return {
            "data": payload,
            "count": len(payload),
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    async def _fetch_battle_report_xml_via_http(
        self,
        battle_id: int,
        access_token: str,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        base_url = str(settings.PSS_API_BASE_URL).rstrip("/")
        params = {"battleId": battle_id, "accessToken": access_token}
        headers = {
            "Accept": "*/*",
            "User-Agent": "UnityPlayer/6000.0.66f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)",
            "X-Unity-Version": "6000.0.66f2",
        }
        endpoints = [
            "BattleService/GetBattle3",
            "BattleService/GetBattle2",
            "BattleService/GetBattle",
        ]

        last_error: Optional[str] = None
        async with httpx.AsyncClient(timeout=15.0) as client:
            for endpoint in endpoints:
                url = f"{base_url}/{endpoint}"
                try:
                    response = await client.get(url, params=params, headers=headers)
                except Exception:
                    continue
                if response.status_code != 200:
                    continue

                xml_text = (response.text or "").strip()
                if not xml_text:
                    continue
                if "errorMessage=" in xml_text:
                    parsed_error = self._extract_xml_error_message(xml_text)
                    if parsed_error:
                        last_error = parsed_error
                    else:
                        last_error = "La API devolvio un error al solicitar el reporte de batalla."
                    continue
                if not xml_text.startswith("<"):
                    continue
                return xml_text, endpoint, None
        return None, None, last_error

    def _extract_xml_error_message(self, xml_text: str) -> Optional[str]:
        if not xml_text:
            return None
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None

        for key in ("errorMessage", "error", "message"):
            value = root.attrib.get(key)
            if value:
                return str(value)
        return None

    def _parse_battle_report_summary(self, xml_text: str, battle_id: int) -> Dict[str, Any]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return {
                "battle_id": battle_id,
                "player_name": None,
                "opponent_name": None,
                "battle_type": None,
                "result": None,
                "battle_start_date": None,
                "battle_end_date": None,
                "raw_data": {},
            }

        battle_nodes = [node for node in root.iter() if node.tag.lower().endswith("battle")]
        node = battle_nodes[0] if battle_nodes else root
        raw_data = {str(key): value for key, value in node.attrib.items()}
        aggregated = self._collect_xml_attribute_values(root)

        player_name = self._first_xml_value(
            aggregated,
            "playername",
            "captainname",
            "username",
            "attackername",
            "attackerusername",
            "attackercaptainname",
            "attackingcaptainname",
            "user1name",
        )
        opponent_name = self._first_xml_value(
            aggregated,
            "opponentname",
            "enemyname",
            "defendername",
            "defenderusername",
            "defendercaptainname",
            "defendingcaptainname",
            "targetname",
            "user2name",
        )
        if not player_name or not opponent_name:
            candidates = self._collect_name_candidates(aggregated)
            if candidates:
                if not player_name:
                    player_name = candidates[0]
                if not opponent_name and len(candidates) > 1:
                    for candidate in candidates[1:]:
                        if candidate != player_name:
                            opponent_name = candidate
                            break
                if not opponent_name and len(candidates) == 1:
                    opponent_name = candidates[0]

        return {
            "battle_id": self._first_raw_value(raw_data, "battleid", "battle_id", "id") or battle_id,
            "player_name": player_name or self._first_raw_value(raw_data, "playername", "username", "captainname"),
            "opponent_name": opponent_name
            or self._first_raw_value(
                raw_data,
                "opponentname",
                "defendername",
                "attackername",
                "enemyname",
            ),
            "battle_type": self._first_raw_value(raw_data, "battletype", "type", "battlemode"),
            "result": self._first_raw_value(raw_data, "result", "outcome", "winner", "iswin"),
            "battle_start_date": self._first_raw_value(raw_data, "battlestartdate", "startdate"),
            "battle_end_date": self._first_raw_value(raw_data, "battleenddate", "enddate"),
            "raw_data": {**raw_data, "_xml_keys": sorted(list(aggregated.keys()))[:200]},
        }

    def _serialize_item_design(self, item: ItemDesign) -> Dict[str, Any]:
        return {
            "id": item.item_design_id,
            "item_design_id": item.item_design_id,
            "name": item.name,
            "description": item.description,
            "rarity": item.rarity,
            "item_type": item.item_type,
            "item_design_key": item.item_design_key,
            "item_design_name_en": item.item_design_name_en,
            "item_design_description_raw": item.item_design_description_raw,
            "level": item.level,
            "item_sub_type": item.item_sub_type,
            "min_ship_level": item.min_ship_level,
            "min_room_level": item.min_room_level,
            "market_price": item.market_price,
            "fair_price": item.fair_price,
            "build_time": item.build_time,
            "build_price": item.build_price,
            "mineral_cost": item.mineral_cost,
            "gas_cost": item.gas_cost,
            "manufacture_cost": item.manufacture_cost,
            "starbase_manufacture_cost": item.starbase_manufacture_cost,
            "our_price": item.our_price,
            "active_animation_id": item.active_animation_id,
            "animation_id": item.animation_id,
            "border_sprite_id": item.border_sprite_id,
            "character_design_id": item.character_design_id,
            "character_part_id": item.character_part_id,
            "character_part": item.character_part,
            "circulation": item.circulation,
            "content": item.content,
            "craft_design_id": item.craft_design_id,
            "equip_sound_file_id": item.equip_sound_file_id,
            "flags": item.flags,
            "image_sprite_id": item.image_sprite_id,
            "logo_sprite_id": item.logo_sprite_id,
            "missile_design_id": item.missile_design_id,
            "parent_item_design_id": item.parent_item_design_id,
            "particle_sprite_id": item.particle_sprite_id,
            "priority": item.priority,
            "race_id": item.race_id,
            "rank": item.rank,
            "reload_modifier": item.reload_modifier,
            "reload_time": item.reload_time,
            "requirement_string": item.requirement_string,
            "room_design_id": item.room_design_id,
            "root_item_design_id": item.root_item_design_id,
            "situation_design_id": item.situation_design_id,
            "sound_file_id": item.sound_file_id,
            "training_design_id": item.training_design_id,
            "transaction_volume": item.transaction_volume,
            "module_type": item.module_type,
            "module_argument": item.module_argument,
            "enhancement_type": item.enhancement_type,
            "enhancement_value": item.enhancement_value,
            "drop_chance": item.drop_chance,
            "max_count": item.max_count,
            "item_space": item.item_space,
            "required_research_design_id": item.required_research_design_id,
            "tags": item.tags,
            "ingredients": item.ingredients,
            "metadata_json": item.metadata_json,
            "stats": item.stats,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _empty_item_payload(self) -> Dict[str, Any]:
        return {
            "id": None,
            "item_design_id": None,
            "name": "",
            "description": "",
            "rarity": "",
            "item_type": "",
            "item_design_key": None,
            "item_design_name_en": None,
            "item_design_description_raw": None,
            "level": None,
            "item_sub_type": None,
            "min_ship_level": None,
            "min_room_level": None,
            "market_price": None,
            "fair_price": None,
            "build_time": None,
            "build_price": None,
            "mineral_cost": None,
            "gas_cost": None,
            "manufacture_cost": None,
            "starbase_manufacture_cost": None,
            "our_price": None,
            "active_animation_id": None,
            "animation_id": None,
            "border_sprite_id": None,
            "character_design_id": None,
            "character_part_id": None,
            "character_part": None,
            "circulation": None,
            "content": None,
            "craft_design_id": None,
            "equip_sound_file_id": None,
            "flags": None,
            "image_sprite_id": None,
            "logo_sprite_id": None,
            "missile_design_id": None,
            "parent_item_design_id": None,
            "particle_sprite_id": None,
            "priority": None,
            "race_id": None,
            "rank": None,
            "reload_modifier": None,
            "reload_time": None,
            "requirement_string": None,
            "room_design_id": None,
            "root_item_design_id": None,
            "situation_design_id": None,
            "sound_file_id": None,
            "training_design_id": None,
            "transaction_volume": None,
            "module_type": None,
            "module_argument": None,
            "enhancement_type": None,
            "enhancement_value": None,
            "drop_chance": None,
            "max_count": None,
            "item_space": None,
            "required_research_design_id": None,
            "tags": None,
            "ingredients": None,
            "metadata_json": None,
            "stats": {},
            "created_at": None,
        }

    def _parse_local_item_file(self, file_name: str, content_text: str) -> List[Dict[str, Any]]:
        if not content_text.strip().startswith("<"):
            return []
        try:
            root = ET.fromstring(content_text)
        except Exception:
            logger.warning("event=local_item_file_parse_error file=%s", file_name)
            return []

        rows: List[Dict[str, Any]] = []
        for node in list(root):
            attrs = {str(k): v for k, v in node.attrib.items()}
            n = self._normalize_key(node.tag)
            if n == "craftdesign":
                rows.append(self._local_craft_row(attrs))
            elif n == "missiledesign":
                rows.append(self._local_missile_row(attrs))
            elif n == "itemdesign":
                rows.append(self._local_itemdesign_row(attrs))
        return rows

    def _local_craft_row(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        row = self._empty_item_payload()
        craft_id = self._first_raw_value(attrs, "craft_design_id")
        row.update(
            {
                "id": craft_id,
                "item_design_id": craft_id,
                "name": self._first_raw_value(attrs, "craft_name") or "",
                "description": "Fuente local: CraftDesigns",
                "item_type": "Craft",
                "item_sub_type": "CraftDesign",
                "craft_design_id": craft_id,
                "missile_design_id": self._first_raw_value(attrs, "missile_design_id"),
                "reload_time": self._value_as_float(attrs, attrs, "reload"),
                "stats": {
                    "hp": self._value_as_int(attrs, attrs, "hp"),
                    "speed": self._value_as_int(attrs, attrs, "flight_speed"),
                },
            }
        )
        return row

    def _local_missile_row(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        row = self._empty_item_payload()
        missile_id = self._first_raw_value(attrs, "missile_design_id")
        row.update(
            {
                "id": missile_id,
                "item_design_id": missile_id,
                "name": self._first_raw_value(attrs, "missile_design_name") or "",
                "description": "Fuente local: MissileDesigns",
                "item_type": "Missile",
                "item_sub_type": "MissileDesign",
                "missile_design_id": missile_id,
                "damage": None,
                "stats": {
                    "attack": self._value_as_float(attrs, attrs, "system_damage"),
                    "hull_damage": self._value_as_float(attrs, attrs, "hull_damage"),
                    "shield_damage": self._value_as_float(attrs, attrs, "shield_damage"),
                },
            }
        )
        return row

    def _local_itemdesign_row(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        row = self._empty_item_payload()
        item_id = self._value_as_int(attrs, attrs, "item_design_id")
        row.update(
            {
                "id": item_id,
                "item_design_id": item_id,
                "name": self._first_raw_value(attrs, "item_design_name", "name") or "",
                "description": self._first_raw_value(attrs, "item_design_description", "description") or "",
                "rarity": self._first_raw_value(attrs, "rarity") or "",
                "item_type": self._first_raw_value(attrs, "item_type") or "",
                "item_design_key": self._first_raw_value(attrs, "item_design_key"),
                "item_design_name_en": self._first_raw_value(attrs, "item_design_name_en"),
                "level": self._value_as_int(attrs, attrs, "level"),
                "item_sub_type": self._first_raw_value(attrs, "item_sub_type"),
                "min_ship_level": self._value_as_int(attrs, attrs, "min_ship_level"),
                "min_room_level": self._value_as_int(attrs, attrs, "min_room_level"),
                "market_price": self._value_as_int(attrs, attrs, "market_price"),
                "fair_price": self._value_as_int(attrs, attrs, "fair_price"),
                "build_time": self._value_as_int(attrs, attrs, "build_time"),
                "build_price": self._value_as_int(attrs, attrs, "build_price"),
                "mineral_cost": self._value_as_int(attrs, attrs, "mineral_cost"),
                "gas_cost": self._value_as_int(attrs, attrs, "gas_cost"),
                "tags": self._first_raw_value(attrs, "tags"),
                "ingredients": self._first_raw_value(attrs, "ingredients"),
                "metadata_json": self._first_raw_value(attrs, "metadata"),
                "stats": {},
            }
        )
        return row

    def _serialize_ship_design(self, ship: ShipDesign) -> Dict[str, Any]:
        return {
            "id": ship.ship_design_id,
            "ship_design_id": ship.ship_design_id,
            "name": ship.name,
            "description": ship.description,
            "class_type": ship.class_type,
            "stats": ship.stats,
            "created_at": ship.created_at.isoformat() if ship.created_at else None,
        }

    def _serialize_crew_design(self, crew: CrewDesign) -> Dict[str, Any]:
        raw = crew.raw_data if isinstance(crew.raw_data, dict) else {}
        return {
            "id": crew.crew_design_id,
            "crew_design_id": crew.crew_design_id,
            "name": crew.name,
            "description": crew.description,
            "race": crew.race,
            "role": crew.role,
            "stats": self._extract_crew_stats(crew.stats, raw),
            "rarity": self._first_raw_value(
                raw,
                "rarity",
                "rarity_type",
                "character_rarity",
                "character_design_rarity",
            ),
            "collection": self._first_raw_value(raw, "collection", "collection_name"),
            "special_ability": self._first_raw_value(
                raw,
                "special_ability",
                "special_ability_type",
                "ability_type",
                "ability",
            ),
            "progression_type": self._first_raw_value(
                raw,
                "progression_type",
                "character_progression_type",
            ),
            "equipment_mask": self._first_raw_value(
                raw,
                "equipment_mask",
                "equipment_slot_mask",
            ),
            "created_at": crew.created_at.isoformat() if crew.created_at else None,
        }

    def _extract_stats(self, obj: Any, raw_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stats: Dict[str, Any] = {}
        stat_attributes = [
            "attack",
            "defense",
            "health",
            "speed",
            "critical",
            "dodge",
            # Common crew stats
            "hp",
            "pilot",
            "repair",
            "weapon",
            "science",
            "engine",
            "research",
            "stamina",
            "ability",
            "fire_resistance",
            "walk_speed",
            "run_speed",
        ]

        for attr in stat_attributes:
            if hasattr(obj, attr):
                stats[attr] = getattr(obj, attr)
        if raw_data:
            for attr in stat_attributes:
                if attr in stats:
                    continue
                value = self._first_raw_value(raw_data, attr)
                if isinstance(value, (int, float)):
                    stats[attr] = value
        return stats

    def _parse_tags(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            return [tag.strip() for tag in value.split(",") if tag.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(tag).strip() for tag in value if str(tag).strip()]
        return [str(value).strip()]

    def _parse_ingredients(self, value: Any) -> list[tuple[int, int]]:
        if value is None:
            return []
        raw = value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            try:
                raw = json.loads(value)
            except Exception:
                raw = value
        if isinstance(raw, str):
            parts = [part.strip() for part in raw.split("|") if part.strip()]
        elif isinstance(raw, (list, tuple, set)):
            parts = [str(part).strip() for part in raw if str(part).strip()]
        else:
            parts = [str(raw).strip()]

        output: list[tuple[int, int]] = []
        for part in parts:
            if "x" not in part:
                continue
            item_id_raw, qty_raw = part.split("x", 1)
            try:
                item_id = int(item_id_raw.strip())
                qty = int(qty_raw.strip())
            except ValueError:
                continue
            output.append((item_id, qty))
        return output

    def _sync_item_relations(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        item_ids = [row.get("item_design_id") for row in rows if row.get("item_design_id") is not None]
        if not item_ids:
            return

        self.db.query(ItemIngredient).filter(ItemIngredient.item_design_id.in_(item_ids)).delete(
            synchronize_session=False
        )
        self.db.query(ItemTag).filter(ItemTag.item_design_id.in_(item_ids)).delete(
            synchronize_session=False
        )

        ingredients_objects: list[ItemIngredient] = []
        tag_objects: list[ItemTag] = []
        for row in rows:
            item_id = row.get("item_design_id")
            if not item_id:
                continue
            for tag in self._parse_tags(row.get("tags")):
                tag_objects.append(ItemTag(item_design_id=item_id, tag=tag))
            for ingredient_id, qty in self._parse_ingredients(row.get("ingredients")):
                ingredients_objects.append(
                    ItemIngredient(
                        item_design_id=item_id,
                        ingredient_item_design_id=ingredient_id,
                        quantity=qty,
                    )
                )

        if ingredients_objects:
            self.db.bulk_save_objects(ingredients_objects)
        if tag_objects:
            self.db.bulk_save_objects(tag_objects)

    def _log_unknown_item_keys(self, raw_data: Dict[str, Any]) -> None:
        if not raw_data:
            return

        # Supported raw keys for item designs (normalized).
        supported = {
            self._normalize_key(key)
            for key in [
                "ItemDesignKey",
                "ItemDesignNameEN",
                "ItemDesignDescription",
                "ItemDesignId",
                "ItemDesignName",
                "ItemType",
                "ItemSubType",
                "Level",
                "Rarity",
                "MinShipLevel",
                "MinRoomLevel",
                "MarketPrice",
                "FairPrice",
                "BuildTime",
                "BuildPrice",
                "MineralCost",
                "GasCost",
                "ManufactureCost",
                "StarbaseManufactureCost",
                "OurPrice",
                "ModuleType",
                "ModuleArgument",
                "EnhancementType",
                "EnhancementValue",
                "DropChance",
                "MaxCount",
                "ItemSpace",
                "RequiredResearchDesignId",
                "Tags",
                "Ingredients",
                "Metadata",
                "ActiveAnimationId",
                "AnimationId",
                "BorderSpriteId",
                "CharacterDesignId",
                "CharacterPartId",
                "CharacterPart",
                "Circulation",
                "Content",
                "CraftDesignId",
                "EquipSoundFileId",
                "Flags",
                "ImageSpriteId",
                "LogoSpriteId",
                "MissileDesignId",
                "ParentItemDesignId",
                "ParticleSpriteId",
                "Priority",
                "RaceId",
                "Rank",
                "ReloadModifier",
                "ReloadTime",
                "RequirementString",
                "RoomDesignId",
                "RootItemDesignId",
                "SituationDesignId",
                "SoundFileId",
                "TrainingDesignId",
                "TransactionVolume",
            ]
            + [
                "attack",
                "defense",
                "health",
                "speed",
                "critical",
                "dodge",
                "hp",
                "pilot",
                "repair",
                "weapon",
                "science",
                "engine",
                "research",
                "stamina",
                "ability",
                "fire_resistance",
                "walk_speed",
                "run_speed",
            ]
        }

        unknown = []
        for key in raw_data.keys():
            normalized = self._normalize_key(str(key))
            if normalized not in supported and normalized not in self._unknown_item_keys:
                self._unknown_item_keys.add(normalized)
                unknown.append(str(key))

        if unknown:
            logger.warning(
                "event=item_design_unknown_raw_keys count=%s sample=%s",
                len(unknown),
                ", ".join(unknown[:20]),
            )
            self._persist_unknown_item_keys(unknown)

    def _persist_unknown_item_keys(self, keys: list[str]) -> None:
        if not keys:
            return
        try:
            log_dir = Path.home() / ".pss_logger"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "unknown_item_keys.log"
            with log_path.open("a", encoding="utf-8") as handle:
                for key in keys:
                    handle.write(f"{key}\n")
        except Exception:
            logger.exception("event=item_design_unknown_keys_persist_error")

    def _extract_crew_stats(self, base_stats: Any, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        stats = dict(base_stats) if isinstance(base_stats, dict) else {}
        candidate_pairs = [
            ("hp", ("hp", "health", "final_hp")),
            ("pilot", ("pilot",)),
            ("attack", ("attack",)),
            ("repair", ("repair",)),
            ("weapon", ("weapon",)),
            ("science", ("science",)),
            ("engine", ("engine",)),
            ("research", ("research",)),
            ("ability", ("ability", "ability_power")),
            ("fire_resistance", ("fire_resistance",)),
            ("walk_speed", ("walk_speed",)),
            ("run_speed", ("run_speed",)),
        ]
        for output_key, aliases in candidate_pairs:
            if output_key in stats:
                continue
            value = self._first_raw_value(raw_data, *aliases)
            if isinstance(value, (int, float)):
                stats[output_key] = value
        return stats

    def _normalize_key(self, key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    def _first_raw_value(self, raw_data: Dict[str, Any], *aliases: str) -> Any:
        if not raw_data:
            return None
        normalized = {self._normalize_key(str(k)): v for k, v in raw_data.items()}
        for alias in aliases:
            value = normalized.get(self._normalize_key(alias))
            if value is not None:
                return value
        return None

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
                timeout = max(1, int(settings.PSS_API_REQUEST_TIMEOUT_SECONDS))
                return await asyncio.wait_for(result, timeout=timeout)
            return result
        logger.warning(
            "event=pss_method_missing service=%s methods=%s",
            service.__class__.__name__,
            ",".join(method_names),
        )
        return None

    def _unwrap_collection(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, set):
            return list(value)
        if isinstance(value, dict):
            for key in ("battles", "users", "players", "rows", "results", "records", "data", "items"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return candidate
                if isinstance(candidate, tuple):
                    return list(candidate)
                if isinstance(candidate, set):
                    return list(candidate)
            return [value]
        return [value]

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

    def _first_attr_or_raw(self, obj: Any, raw_data: Dict[str, Any], *aliases: str) -> Any:
        value = self._first_attr(obj, *aliases)
        if value is not None:
            return value
        return self._first_raw_value(raw_data, *aliases)

    def _value_as_int(self, obj: Any, raw_data: Dict[str, Any], *aliases: str) -> Optional[int]:
        value = self._first_attr_or_raw(obj, raw_data, *aliases)
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    def _value_as_float(self, obj: Any, raw_data: Dict[str, Any], *aliases: str) -> Optional[float]:
        value = self._first_attr_or_raw(obj, raw_data, *aliases)
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _serialize_user_battle(self, battle: Any, username: str) -> Dict[str, Any]:
        raw_data = self._extract_raw_data(battle)

        battle_id = self._first_attr(battle, "battle_id", "id")
        if battle_id is None:
            battle_id = self._first_raw_value(raw_data, "battle_id", "id")

        created_at = self._first_attr(
            battle,
            "battle_end_date",
            "battle_start_date",
            "created_at",
            "start_date",
            "end_date",
        )
        if created_at is None:
            created_at = self._first_raw_value(
                raw_data,
                "battle_end_date",
                "battle_start_date",
                "created_at",
                "start_date",
                "end_date",
                "timestamp",
            )

        return {
            "id": battle_id,
            "player_name": self._first_raw_value(raw_data, "player_name", "username", "captain_name")
            or username,
            "opponent_name": self._first_raw_value(
                raw_data,
                "opponent_name",
                "defender_name",
                "attacker_name",
                "enemy_name",
            ),
            "battle_type": self._first_raw_value(
                raw_data,
                "battle_type",
                "type",
                "battle_mode",
            ),
            "result": self._first_raw_value(
                raw_data,
                "result",
                "outcome",
                "winner",
                "is_win",
            ),
            "trophy_change": self._first_raw_value(
                raw_data,
                "trophy_change",
                "rating_change",
                "stars_change",
                "trophies_delta",
            ),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            "raw_data": raw_data,
        }

    def _serialize_battle_report(
        self,
        report: BattleReport,
        source: str,
    ) -> Dict[str, Any]:
        return {
            "battle_id": report.battle_id,
            "player_name": report.player_name,
            "opponent_name": report.opponent_name,
            "battle_type": report.battle_type,
            "result": report.result,
            "battle_start_date": report.battle_start_date,
            "battle_end_date": report.battle_end_date,
            "xml_report": report.xml_report,
            "summary_data": report.summary_data if isinstance(report.summary_data, dict) else {},
            "source_endpoint": report.source_endpoint,
            "source": source,
            "fetched_at": report.fetched_at.isoformat() if report.fetched_at else None,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        }

    def _persist_battle_index_rows(self, battles: List[Dict[str, Any]]) -> None:
        if not battles:
            return

        rows: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for battle in battles:
            battle_id = battle.get("id")
            if battle_id is None:
                battle_id = battle.get("battle_id")
            if isinstance(battle_id, str):
                if not battle_id.isdigit():
                    continue
                battle_id = int(battle_id)
            if not isinstance(battle_id, int) or battle_id <= 0:
                continue

            rows.append(
                {
                    "battle_id": battle_id,
                    "player_name": str(battle.get("player_name") or "")[:255],
                    "opponent_name": str(battle.get("opponent_name") or "")[:255],
                    "battle_type": str(battle.get("battle_type") or "")[:100],
                    "result": str(battle.get("result") or "")[:100],
                    "trophy_change": str(battle.get("trophy_change") or "")[:100],
                    "created_at_value": str(battle.get("created_at") or "")[:100],
                    "last_seen_at": now,
                    "snapshot_data": battle.get("raw_data") if isinstance(battle.get("raw_data"), dict) else {},
                }
            )

        if not rows:
            return

        try:
            self._upsert_rows(BattleIndex, rows, "battle_id")
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("event=battle_index_upsert_error count=%s", len(rows))

    def _collect_xml_attribute_values(self, root: ET.Element) -> Dict[str, List[str]]:
        output: Dict[str, List[str]] = {}
        for node in root.iter():
            for key, raw_value in node.attrib.items():
                norm_key = self._normalize_key(str(key))
                value = str(raw_value).strip()
                if not norm_key or not value:
                    continue
                output.setdefault(norm_key, [])
                if value not in output[norm_key]:
                    output[norm_key].append(value)
        return output

    def _first_xml_value(self, aggregated: Dict[str, List[str]], *keys: str) -> Optional[str]:
        for key in keys:
            values = aggregated.get(self._normalize_key(key), [])
            for value in values:
                text = str(value).strip()
                if text:
                    return text
        return None

    def _collect_name_candidates(self, aggregated: Dict[str, List[str]]) -> List[str]:
        candidates: List[str] = []
        ignore_tokens = ("ship", "room", "item", "design", "ability", "fleet", "alliance")
        for key, values in aggregated.items():
            if "name" not in key and key not in {"username", "captainname"}:
                continue
            if any(token in key for token in ignore_tokens):
                continue
            for value in values:
                text = str(value).strip()
                if not text:
                    continue
                if text not in candidates:
                    candidates.append(text)
        return candidates

    def _item_row(self, design: Any) -> Dict[str, Any]:
        raw_data = self._extract_raw_data(design)
        self._log_unknown_item_keys(raw_data)
        return {
            "item_design_id": self._first_attr(design, "item_design_id", "id"),
            "name": self._first_attr(design, "item_design_name", "name") or "",
            "description": self._first_attr(design, "description") or "",
            "rarity": self._first_attr_or_raw(design, raw_data, "rarity") or "",
            "item_type": self._first_attr_or_raw(design, raw_data, "item_type") or "",
            "item_design_key": self._first_attr_or_raw(design, raw_data, "item_design_key"),
            "item_design_name_en": self._first_attr_or_raw(design, raw_data, "item_design_name_en"),
            "item_design_description_raw": self._first_attr_or_raw(design, raw_data, "item_design_description"),
            "level": self._value_as_int(design, raw_data, "level"),
            "item_sub_type": self._first_attr_or_raw(design, raw_data, "item_sub_type"),
            "min_ship_level": self._value_as_int(design, raw_data, "min_ship_level"),
            "min_room_level": self._value_as_int(design, raw_data, "min_room_level"),
            "market_price": self._value_as_int(design, raw_data, "market_price"),
            "fair_price": self._value_as_int(design, raw_data, "fair_price"),
            "build_time": self._value_as_int(design, raw_data, "build_time"),
            "build_price": self._value_as_int(design, raw_data, "build_price"),
            "mineral_cost": self._value_as_int(design, raw_data, "mineral_cost"),
            "gas_cost": self._value_as_int(design, raw_data, "gas_cost"),
            "manufacture_cost": self._value_as_int(design, raw_data, "manufacture_cost"),
            "starbase_manufacture_cost": self._value_as_int(design, raw_data, "starbase_manufacture_cost"),
            "our_price": self._value_as_int(design, raw_data, "our_price"),
            "active_animation_id": self._value_as_int(design, raw_data, "active_animation_id"),
            "animation_id": self._value_as_int(design, raw_data, "animation_id"),
            "border_sprite_id": self._value_as_int(design, raw_data, "border_sprite_id"),
            "character_design_id": self._value_as_int(design, raw_data, "character_design_id"),
            "character_part_id": self._value_as_int(design, raw_data, "character_part_id"),
            "character_part": self._first_attr_or_raw(design, raw_data, "character_part"),
            "circulation": self._value_as_int(design, raw_data, "circulation"),
            "content": self._first_attr_or_raw(design, raw_data, "content"),
            "craft_design_id": self._value_as_int(design, raw_data, "craft_design_id"),
            "equip_sound_file_id": self._value_as_int(design, raw_data, "equip_sound_file_id"),
            "flags": self._value_as_int(design, raw_data, "flags"),
            "image_sprite_id": self._value_as_int(design, raw_data, "image_sprite_id"),
            "logo_sprite_id": self._value_as_int(design, raw_data, "logo_sprite_id"),
            "missile_design_id": self._value_as_int(design, raw_data, "missile_design_id"),
            "parent_item_design_id": self._value_as_int(design, raw_data, "parent_item_design_id"),
            "particle_sprite_id": self._value_as_int(design, raw_data, "particle_sprite_id"),
            "priority": self._value_as_int(design, raw_data, "priority"),
            "race_id": self._value_as_int(design, raw_data, "race_id"),
            "rank": self._value_as_int(design, raw_data, "rank"),
            "reload_modifier": self._value_as_float(design, raw_data, "reload_modifier"),
            "reload_time": self._value_as_float(design, raw_data, "reload_time"),
            "requirement_string": self._first_attr_or_raw(design, raw_data, "requirement_string"),
            "room_design_id": self._value_as_int(design, raw_data, "room_design_id"),
            "root_item_design_id": self._value_as_int(design, raw_data, "root_item_design_id"),
            "situation_design_id": self._value_as_int(design, raw_data, "situation_design_id"),
            "sound_file_id": self._value_as_int(design, raw_data, "sound_file_id"),
            "training_design_id": self._value_as_int(design, raw_data, "training_design_id"),
            "transaction_volume": self._value_as_int(design, raw_data, "transaction_volume"),
            "module_type": self._first_attr_or_raw(design, raw_data, "module_type"),
            "module_argument": self._first_attr_or_raw(design, raw_data, "module_argument"),
            "enhancement_type": self._first_attr_or_raw(design, raw_data, "enhancement_type"),
            "enhancement_value": self._value_as_float(design, raw_data, "enhancement_value"),
            "drop_chance": self._value_as_float(design, raw_data, "drop_chance"),
            "max_count": self._value_as_int(design, raw_data, "max_count"),
            "item_space": self._value_as_int(design, raw_data, "item_space"),
            "required_research_design_id": self._value_as_int(
                design, raw_data, "required_research_design_id"
            ),
            "tags": self._first_attr_or_raw(design, raw_data, "tags"),
            "ingredients": self._first_attr_or_raw(design, raw_data, "ingredients"),
            "metadata_json": self._first_attr_or_raw(design, raw_data, "metadata"),
            "stats": self._extract_stats(design, raw_data),
        }

    def _ship_row(self, design: Any) -> Dict[str, Any]:
        raw_data = self._extract_raw_data(design)
        return {
            "ship_design_id": self._first_attr(design, "ship_design_id", "id"),
            "name": self._first_attr(design, "ship_design_name", "name") or "",
            "description": self._first_attr(design, "description") or "",
            "class_type": self._first_attr(design, "class_type") or "",
            "stats": self._extract_stats(design, raw_data),
            "raw_data": raw_data,
        }

    def _crew_row(self, design: Any) -> Dict[str, Any]:
        raw_data = self._extract_raw_data(design)
        return {
            "crew_design_id": self._first_attr(design, "crew_design_id", "character_design_id", "id"),
            "name": self._first_attr(design, "crew_design_name", "character_design_name", "name") or "",
            "description": self._first_attr(design, "description", "character_design_description") or "",
            "race": self._first_attr(design, "race") or "",
            "role": self._first_attr(design, "role") or "",
            "stats": self._extract_stats(design, raw_data),
            "raw_data": raw_data,
        }

    def _upsert_rows(self, model: Any, rows: List[Dict[str, Any]], key_column: str) -> None:
        if not rows:
            return
        bind = self.db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        table = model.__table__
        rows = [self._sanitize_row_for_table(table, row) for row in rows]

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

            # SQLite has a hard cap on bind parameters per statement.
            # Split large upserts into chunks to avoid "too many SQL variables".
            max_sqlite_binds = 900
            column_count = max(1, len(rows[0]))
            chunk_size = max(1, max_sqlite_binds // column_count)

            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                stmt = sqlite_insert(table).values(chunk)
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

    def _sanitize_row_for_table(self, table: Any, row: Dict[str, Any]) -> Dict[str, Any]:
        sanitized: Dict[str, Any] = {}
        for key, value in row.items():
            column = table.c.get(key)
            if column is None:
                sanitized[key] = value
                continue

            type_name = column.type.__class__.__name__.lower()
            is_json_column = "json" in type_name

            if value is None:
                sanitized[key] = None
                continue

            if is_json_column:
                if isinstance(value, set):
                    sanitized[key] = list(value)
                elif isinstance(value, tuple):
                    sanitized[key] = list(value)
                else:
                    sanitized[key] = value
                continue

            if isinstance(value, (dict, list, tuple, set)):
                sanitized[key] = json.dumps(value, ensure_ascii=False)
                continue

            sanitized[key] = value
        return sanitized

    def _resolve_ttl(self, ttl_seconds: Optional[int]) -> int:
        if ttl_seconds is not None:
            return max(0, ttl_seconds)
        return max(0, settings.DESIGNS_CACHE_TTL_SECONDS)

    def _resolve_battle_report_ttl(self, ttl_seconds: Optional[int]) -> int:
        if ttl_seconds is not None:
            return max(0, ttl_seconds)
        return max(0, settings.BATTLE_REPORT_CACHE_TTL_SECONDS)

    def _set_cached_battle_report(self, battle_id: int, payload: Dict[str, Any]) -> None:
        self._battle_report_cache[battle_id] = {
            "cached_at": datetime.now(timezone.utc),
            "payload": payload,
        }

    def _get_cached_battle_report(self, battle_id: int, ttl_seconds: int) -> Optional[Dict[str, Any]]:
        cached = self._battle_report_cache.get(battle_id)
        if not cached:
            return None

        cached_at = cached.get("cached_at")
        payload = cached.get("payload")
        if not isinstance(cached_at, datetime) or not isinstance(payload, dict):
            self._battle_report_cache.pop(battle_id, None)
            return None

        if ttl_seconds > 0:
            age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age_seconds > ttl_seconds:
                self._battle_report_cache.pop(battle_id, None)
                return None

        return payload

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
