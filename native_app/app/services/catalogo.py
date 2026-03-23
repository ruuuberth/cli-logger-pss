from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable


_NUMERIC_PARENS_RE = re.compile(r"\s*\(\d+\)\s*$")
_ITEM_LEVEL_PATTERNS = (
    re.compile(r"\s+nivel\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"\s+level\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"\s+\(niv\.?\d+\)\s*$", re.IGNORECASE),
    re.compile(r"\s+lv\.?\d+\s*$", re.IGNORECASE),
    re.compile(r"\s+[ivx]+\s*$", re.IGNORECASE),
)


class CatalogoResolver:
    def __init__(
        self,
        base_dir: Path | None,
        db_session_factory: Callable[[], Any] | None = None,
        status_callback: Callable[[str], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.db_session_factory = db_session_factory
        self.status_callback = status_callback
        self.logger = logger or logging.getLogger(__name__)
        self._maps: dict[str, dict[str, str]] = {}
        self._db_cache: dict[str, dict[int, str | None]] = {}
        self._item_records_cache: list[dict[str, str]] | None = None
        self._resolved_design_cache: dict[tuple[str, str, str], str] = {}
        self._resolved_item_cache: dict[tuple[str, str], str] = {}
        self._resolved_action_condition_cache: dict[tuple[str, str], tuple[str, str]] = {}
        self._warned: set[str] = set()
        self._last_status: str | None = None

    def set_base_dir(self, base_dir: Path | None) -> None:
        self.base_dir = base_dir
        self._maps.clear()
        self._db_cache.clear()
        self._item_records_cache = None
        self._resolved_design_cache.clear()
        self._resolved_item_cache.clear()
        self._resolved_action_condition_cache.clear()
        if base_dir is None:
            self._emit_status("missing_path")

    @staticmethod
    def default_base_dir() -> Path | None:
        candidate = (
            Path.home()
            / ".config"
            / "unity3d"
            / "SavySoda"
            / "Pixel Starships"
            / "Data"
            / "Prod"
        )
        if candidate.exists():
            return candidate
        return None

    def resolve_design_name(self, design_id: Any, current_name: Any, kind: str) -> str:
        design_id_text = str(design_id) if design_id is not None else ""
        current_name_text = str(current_name).strip() if current_name is not None else ""
        cache_key = (kind, design_id_text, current_name_text)
        cached = self._resolved_design_cache.get(cache_key)
        if cached is not None:
            return cached
        local_name = self._lookup_local_design_name(kind, design_id_text)
        if local_name:
            self._emit_status("local")
            resolved = self._normalize_item_name_base(local_name)
            self._resolved_design_cache[cache_key] = resolved
            return resolved

        db_name = self._get_db_design_name(kind, design_id)
        if db_name:
            self._emit_status("db")
            resolved = self.format_name(db_name)
            self._resolved_design_cache[cache_key] = resolved
            return resolved

        if current_name and current_name_text and str(current_name) != "Sin traduccion":
            self._emit_status("current_name")
            resolved = self.format_name(current_name_text)
            self._resolved_design_cache[cache_key] = resolved
            return resolved

        self._emit_status("placeholder")
        self._resolved_design_cache[cache_key] = "Sin traduccion"
        return "Sin traduccion"

    def resolve_action_condition(self, action_id: Any, condition_id: Any) -> tuple[str, str]:
        cache_key = (str(action_id) if action_id is not None else "", str(condition_id) if condition_id is not None else "")
        cached = self._resolved_action_condition_cache.get(cache_key)
        if cached is not None:
            return cached
        action_name = self._lookup_local_map(
            "ActionTypes",
            "ActionTypes.txt",
            "ActionType",
            "ActionTypeId",
            "ActionTypeName",
            str(action_id) if action_id is not None else "",
        )
        condition_name = self._lookup_local_map(
            "ConditionTypes",
            "ConditionTypes.txt",
            "ConditionType",
            "ConditionTypeId",
            "ConditionTypeName",
            str(condition_id) if condition_id is not None else "",
        )
        if action_name or condition_name:
            self._emit_status("local")
        else:
            self._emit_status("placeholder")
        action_label = self.format_name(action_name) if action_name else self._format_raw_id(action_id)
        condition_label = self.format_name(condition_name) if condition_name else self._format_raw_id(condition_id)
        resolved = (action_label, condition_label)
        self._resolved_action_condition_cache[cache_key] = resolved
        return resolved

    def resolve_item_name(self, item_design_id: Any, fallback: str | None = None) -> str:
        item_design_text = str(item_design_id) if item_design_id is not None else ""
        cache_key = (item_design_text, fallback or "")
        cached = self._resolved_item_cache.get(cache_key)
        if cached is not None:
            return cached
        local_name = self._lookup_local_map(
            "ItemDesigns",
            "ItemDesigns.txt",
            "ItemDesign",
            "ItemDesignId",
            "ItemDesignName",
            item_design_text,
        )
        if local_name:
            self._emit_status("local")
            resolved = self.format_name(local_name)
            self._resolved_item_cache[cache_key] = resolved
            return resolved
        if fallback:
            self._emit_status("placeholder")
            resolved = self.format_name(fallback, fallback=fallback)
            self._resolved_item_cache[cache_key] = resolved
            return resolved
        self._emit_status("placeholder")
        if item_design_text:
            resolved = f"ItemDesignId {item_design_text}"
            self._resolved_item_cache[cache_key] = resolved
            return resolved
        self._resolved_item_cache[cache_key] = "Sin traduccion"
        return "Sin traduccion"

    def resolve_item_name_from_base(self, item_name_en_base: str, fallback: str | None = None) -> str:
        target = self._normalize_item_name_base(item_name_en_base)
        if not target:
            return self.format_name(fallback) if fallback else "Sin traduccion"
        records = self._load_item_records()
        if records:
            for record in records:
                name_en = self._normalize_item_name_base(record.get("name_en"))
                if name_en == target:
                    self._emit_status("local")
                    return self._normalize_item_name_base(record.get("name")) or self.format_name(
                        record.get("name_en"), fallback=record.get("name_en") or "Sin traduccion"
                    )
        self._emit_status("placeholder")
        if fallback:
            return self.format_name(fallback, fallback=fallback)
        return self.format_name(item_name_en_base)

    def format_name(self, name: str | None, fallback: str = "Sin traduccion") -> str:
        if not name:
            return fallback
        cleaned = str(name).strip()
        if not cleaned:
            return fallback
        cleaned = _NUMERIC_PARENS_RE.sub("", cleaned).strip()
        return cleaned or fallback

    def _normalize_item_name_base(self, name: Any) -> str:
        text = self.format_name(str(name), fallback="") if name is not None else ""
        if not text:
            return ""
        normalized = text
        for pattern in _ITEM_LEVEL_PATTERNS:
            normalized = pattern.sub("", normalized).strip()
        return normalized

    def _format_raw_id(self, raw_id: Any) -> str:
        if raw_id is None:
            return "-"
        text = str(raw_id).strip()
        return text if text else "-"

    def _lookup_local_design_name(self, kind: str, design_id: str) -> str | None:
        if not design_id:
            return None
        if kind == "ship":
            return self._lookup_local_map(
                "ShipDesigns",
                "ShipDesigns.txt",
                "ShipDesign",
                "ShipDesignId",
                "ShipDesignName",
                design_id,
            )
        if kind == "room":
            return self._lookup_local_map(
                "RoomDesigns",
                "RoomDesigns.txt",
                "RoomDesign",
                "RoomDesignId",
                "RoomName",
                design_id,
            )
        if kind == "character":
            return self._lookup_local_map(
                "CharacterDesigns",
                "CharacterDesigns.txt",
                "CharacterDesign",
                "CharacterDesignId",
                "CharacterDesignName",
                design_id,
            )
        return None

    def _lookup_local_map(
        self,
        cache_key: str,
        filename: str,
        tag: str,
        id_attr: str,
        name_attr: str,
        design_id: str,
    ) -> str | None:
        mapping = self._get_local_map(cache_key, filename, tag, id_attr, name_attr)
        if not mapping:
            return None
        return mapping.get(design_id)

    def _get_local_map(
        self, cache_key: str, filename: str, tag: str, id_attr: str, name_attr: str
    ) -> dict[str, str]:
        if cache_key in self._maps:
            return self._maps[cache_key]
        if self.base_dir is None:
            self._warn_once("catalogo_missing_path", "event=catalogo_missing_path")
            self._emit_status("missing_path")
            self._maps[cache_key] = {}
            return {}
        path = self.base_dir / filename
        if not path.exists():
            self._warn_once(
                f"catalogo_file_missing:{filename}",
                "event=catalogo_file_missing file=%s",
                filename,
            )
            self._emit_status("missing_file")
            self._maps[cache_key] = {}
            return {}
        mapping = self._load_catalog_map(path, tag, id_attr, name_attr)
        self._maps[cache_key] = mapping
        return mapping

    def _load_item_records(self) -> list[dict[str, str]]:
        cache_key = "ItemDesignRecords"
        if self._item_records_cache is not None:
            return self._item_records_cache
        if self.base_dir is None:
            self._warn_once("catalogo_missing_path", "event=catalogo_missing_path")
            self._emit_status("missing_path")
            return []
        path = self.base_dir / "ItemDesigns.txt"
        if not path.exists():
            self._warn_once(
                "catalogo_file_missing:ItemDesigns.txt",
                "event=catalogo_file_missing file=%s",
                "ItemDesigns.txt",
            )
            self._emit_status("missing_file")
            return []
        try:
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
            if not raw:
                return []
            root = ET.fromstring(raw)
        except Exception as exc:
            self._warn_once(
                f"catalogo_parse_error:{path}",
                "event=catalogo_parse_error file=%s error=%s",
                str(path),
                exc,
            )
            self._emit_status("parse_error")
            return []
        records: list[dict[str, str]] = []
        for node in root.findall(".//ItemDesign"):
            attrs = node.attrib or {}
            item_id = attrs.get("ItemDesignId")
            name = attrs.get("ItemDesignName")
            name_en = attrs.get("ItemDesignNameEN") or name
            if item_id and name:
                records.append(
                    {
                        "id": str(item_id),
                        "name": str(name),
                        "name_en": str(name_en or ""),
                    }
                )
        self._item_records_cache = records
        return records

    def _load_catalog_map(self, path: Path, tag: str, id_attr: str, name_attr: str) -> dict[str, str]:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
            if not raw:
                return {}
            root = ET.fromstring(raw)
        except Exception as exc:
            self._warn_once(
                f"catalogo_parse_error:{path}",
                "event=catalogo_parse_error file=%s error=%s",
                str(path),
                exc,
            )
            self._emit_status("parse_error")
            return {}
        mapping: dict[str, str] = {}
        for node in root.findall(f".//{tag}"):
            attrs = node.attrib or {}
            raw_id = attrs.get(id_attr)
            name = attrs.get(name_attr)
            if raw_id and name:
                mapping[str(raw_id)] = str(name)
        return mapping

    def _get_db_design_name(self, kind: str, design_id: Any) -> str | None:
        if self.db_session_factory is None or design_id is None:
            return None
        try:
            design_id_int = int(design_id)
        except Exception:
            return None
        cache = self._db_cache.setdefault(kind, {})
        if design_id_int in cache:
            return cache[design_id_int]
        try:
            from sqlalchemy.exc import SQLAlchemyError
            from app.models.pss_models import CrewDesign, RoomDesign, ShipDesign
        except Exception:
            return None
        db = self.db_session_factory()
        try:
            if kind == "ship":
                row = (
                    db.query(ShipDesign.name_es, ShipDesign.name)
                    .filter(ShipDesign.ship_design_id == design_id_int)
                    .first()
                )
            elif kind == "room":
                row = (
                    db.query(RoomDesign.name_es, RoomDesign.name)
                    .filter(RoomDesign.room_design_id == design_id_int)
                    .first()
                )
            elif kind == "character":
                row = (
                    db.query(CrewDesign.name_es, CrewDesign.name)
                    .filter(CrewDesign.crew_design_id == design_id_int)
                    .first()
                )
            else:
                row = None
            if row:
                name_es, name = row
                result = name_es or name
            else:
                result = None
            cache[design_id_int] = result
            if result:
                self._warn_once(
                    f"catalogo_db_fallback_used:{kind}",
                    "event=catalogo_db_fallback_used kind=%s",
                    kind,
                )
            return result
        except SQLAlchemyError as exc:
            self._warn_once(
                f"catalogo_db_error:{kind}",
                "event=catalogo_db_error kind=%s error=%s",
                kind,
                exc,
            )
            return None
        finally:
            db.close()

    def _warn_once(self, key: str, msg: str, *args: Any) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        self.logger.warning(msg, *args)

    def _emit_status(self, status: str) -> None:
        if self.status_callback is None:
            return
        if status == self._last_status:
            return
        self._last_status = status
        self.status_callback(status)
