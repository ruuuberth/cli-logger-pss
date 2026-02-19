import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from importlib.util import find_spec
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pss_models import CrewDesign, ItemDesign, ShipDesign

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

    async def get_user_recent_battles(
        self,
        username: str,
        limit: int = 10,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        device_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        normalized_username = username.strip()
        if not normalized_username:
            return []

        safe_limit = max(1, min(limit, 50))

        try:
            if self._ensure_client() is None:
                return []

            user_service = self._get_service("user_service")
            battle_service = self._get_service("battle_service", "pvp_service")
            if user_service is None and battle_service is None:
                return []

            user_id = await self._resolve_user_id(normalized_username, user_service)
            battle_args = self._build_battle_arg_options(normalized_username, user_id, safe_limit)

            battles: Any = None
            if battle_service is not None:
                battles = await self._call_async_with_arg_options(
                    battle_service,
                    [
                        "list_user_battles",
                        "get_user_battles",
                        "list_recent_battles",
                        "get_recent_battles",
                        "list_battle_history",
                        "get_battle_history",
                        "list_battles_by_user",
                        "list_battles_for_user",
                        "search_battles",
                    ],
                    battle_args,
                )

            if battles is None and user_service is not None:
                battles = await self._call_async_with_arg_options(
                    user_service,
                    [
                        "list_user_battles",
                        "get_user_battles",
                        "list_recent_battles",
                        "get_recent_battles",
                        "list_battle_history",
                        "get_battle_history",
                    ],
                    battle_args,
                )

            battle_rows = self._unwrap_collection(battles)
            if battle_rows:
                return [self._serialize_user_battle(row, normalized_username) for row in battle_rows[:safe_limit]]

            token_for_http = (access_token or "").strip() or None
            if token_for_http is None and (refresh_token or "").strip():
                try:
                    token_data = await self.login_with_refresh_token(
                        refresh_token=refresh_token or "",
                        device_key=device_key,
                    )
                    token_for_http = token_data["access_token"]
                except (PSSFeatureNotSupportedError, PSSAuthenticationError):
                    # If exchange is not available, we still try the provided refresh token directly.
                    token_for_http = (refresh_token or "").strip() or None

            http_battles = await self._fetch_battles_via_http(
                normalized_username,
                user_id,
                safe_limit,
                access_token=token_for_http,
            )
            if http_battles:
                return http_battles

            available_methods = self._collect_battle_related_methods()
            raise PSSFeatureNotSupportedError(
                "No se encontro un metodo compatible para obtener historial de batallas en esta version de pssapi. "
                f"Metodos detectados: {available_methods}"
            )
        except PSSFeatureNotSupportedError:
            raise
        except Exception:
            logger.exception("event=user_recent_battles_error username=%s", normalized_username)
            return []

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

    async def _fetch_battles_via_http(
        self,
        username: str,
        user_id: Optional[int],
        limit: int,
        access_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        base_url = str(settings.PSS_API_BASE_URL).rstrip("/")
        normalized_token = (access_token or "").strip()

        param_options: List[Dict[str, Any]] = [
            {"take": limit, "username": username},
        ]
        if user_id is not None:
            param_options.insert(0, {"take": limit, "userId": user_id})
        if normalized_token:
            param_options = [{**params, "accessToken": normalized_token} for params in param_options] + param_options

        endpoints = ["BattleService/ListBattles"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in endpoints:
                url = f"{base_url}/{endpoint}"
                for params in param_options:
                    try:
                        response = await client.get(url, params=params)
                    except Exception:
                        continue
                    if response.status_code != 200:
                        continue
                    parsed = self._parse_battle_xml_response(response.text, username)
                    if parsed:
                        return parsed[:limit]
        return []

    def _parse_battle_xml_response(self, xml_text: str, username: str) -> List[Dict[str, Any]]:
        if not xml_text or "errorMessage=" in xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        battle_nodes = [node for node in root.iter() if node.tag.lower().endswith("battle")]
        parsed: List[Dict[str, Any]] = []
        for node in battle_nodes:
            raw_data = {str(key): value for key, value in node.attrib.items()}
            created_at = self._first_raw_value(
                raw_data,
                "battleenddate",
                "battlestartdate",
                "createdat",
                "startdate",
                "enddate",
            )
            parsed.append(
                {
                    "id": self._first_raw_value(raw_data, "battleid", "id"),
                    "player_name": self._first_raw_value(raw_data, "playername", "username", "captainname")
                    or username,
                    "opponent_name": self._first_raw_value(
                        raw_data,
                        "opponentname",
                        "defendername",
                        "attackername",
                        "enemyname",
                    ),
                    "battle_type": self._first_raw_value(raw_data, "battletype", "type", "battlemode"),
                    "result": self._first_raw_value(raw_data, "result", "outcome", "winner", "iswin"),
                    "trophy_change": self._first_raw_value(
                        raw_data,
                        "trophychange",
                        "ratingchange",
                        "starschange",
                        "trophiesdelta",
                    ),
                    "created_at": created_at,
                    "raw_data": raw_data,
                }
            )
        return parsed

    def _collect_battle_related_methods(self) -> Dict[str, List[str]]:
        client = self._ensure_client()
        if client is None:
            return {}

        output: Dict[str, List[str]] = {}
        for attr_name in dir(client):
            if not attr_name.endswith("_service"):
                continue
            service = getattr(client, attr_name, None)
            if service is None:
                continue
            method_names = [
                name
                for name in dir(service)
                if not name.startswith("_")
                and callable(getattr(service, name, None))
                and any(
                    token in name.lower()
                    for token in ("battle", "pvp", "combat", "history")
                )
            ]
            if method_names:
                output[attr_name] = sorted(method_names)
        return output

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
        raw = crew.raw_data if isinstance(crew.raw_data, dict) else {}
        return {
            "id": crew.crew_design_id,
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
                return await result
            return result
        logger.warning(
            "event=pss_method_missing service=%s methods=%s",
            service.__class__.__name__,
            ",".join(method_names),
        )
        return None

    async def _call_async_with_arg_options(
        self,
        service: Any,
        method_names: List[str],
        arg_options: List[tuple[Any, ...]],
    ) -> Any:
        for method_name in method_names:
            method = getattr(service, method_name, None)
            if method is None:
                continue
            for args in arg_options:
                try:
                    result = method(*args)
                    if hasattr(result, "__await__"):
                        result = await result
                except TypeError:
                    continue
                except Exception:
                    logger.exception(
                        "event=pss_method_call_error service=%s method=%s",
                        service.__class__.__name__,
                        method_name,
                    )
                    continue
                if result is not None:
                    return result

        logger.warning(
            "event=pss_method_missing service=%s methods=%s",
            service.__class__.__name__,
            ",".join(method_names),
        )
        return None

    async def _resolve_user_id(self, username: str, user_service: Any) -> Optional[int]:
        if user_service is None:
            return None

        user_data = await self._call_async_with_arg_options(
            user_service,
            [
                "get_user_by_name",
                "get_user",
                "search_user",
                "search_users",
                "list_users",
                "list_all_users",
            ],
            [(username,), (username, 1), (username, 0, 1)],
        )
        user_candidate = self._first_record(user_data)
        if user_candidate is None:
            return None

        for key in ("id", "user_id", "player_id", "captain_id"):
            value = self._first_value(user_candidate, key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    def _build_battle_arg_options(
        self,
        username: str,
        user_id: Optional[int],
        limit: int,
    ) -> List[tuple[Any, ...]]:
        options: List[tuple[Any, ...]] = [
            (username, limit),
            (username,),
            (username, 0, limit),
            (limit, username),
            (None, username, limit),
        ]
        if user_id is not None:
            options.extend(
                [
                    (user_id, limit),
                    (user_id,),
                    (user_id, 0, limit),
                    (limit, user_id),
                    (None, user_id, limit),
                ]
            )
        return options

    def _first_value(self, value: Any, *keys: str) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            for key in keys:
                if key in value and value[key] is not None:
                    return value[key]
            return None
        for key in keys:
            attr = getattr(value, key, None)
            if attr is not None:
                return attr
        return None

    def _first_record(self, value: Any) -> Any:
        rows = self._unwrap_collection(value)
        if rows:
            return rows[0]
        if isinstance(value, dict):
            for key in ("user", "player", "data", "result"):
                candidate = value.get(key)
                rows = self._unwrap_collection(candidate)
                if rows:
                    return rows[0]
                if candidate is not None and not isinstance(candidate, (list, tuple, set)):
                    return candidate
        if value is not None and not isinstance(value, (list, tuple, set)):
            return value
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

    def _item_row(self, design: Any) -> Dict[str, Any]:
        raw_data = self._extract_raw_data(design)
        return {
            "item_design_id": self._first_attr(design, "item_design_id", "id"),
            "name": self._first_attr(design, "item_design_name", "name") or "",
            "description": self._first_attr(design, "description") or "",
            "rarity": self._first_attr(design, "rarity") or "",
            "item_type": self._first_attr(design, "item_type") or "",
            "stats": self._extract_stats(design, raw_data),
            "raw_data": raw_data,
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
