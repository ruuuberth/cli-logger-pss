from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.services.catalogo import CatalogoResolver


_SET_ITEM_ACTION_TO_SLOT = {
    "70": 0,
    "71": 1,
    "72": 2,
    "73": 3,
    "74": 4,
    "75": 5,
}


class RoomItemMappingResolver:
    def __init__(
        self,
        mapping_path: Path | None = None,
        catalogo: CatalogoResolver | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.mapping_path = mapping_path or (
            Path(__file__).resolve().parent.parent / "resources" / "room_item_slot_mappings.json"
        )
        self.catalogo = catalogo
        self.logger = logger or logging.getLogger(__name__)
        self._mapping: dict[str, Any] | None = None
        self._warned: set[str] = set()

    def reload(self) -> None:
        self._mapping = None

    def get_slot_index_for_action_type(self, action_type_id: int | str | None) -> int | None:
        if action_type_id is None:
            return None
        return _SET_ITEM_ACTION_TO_SLOT.get(str(action_type_id))

    def get_item_name_base(self, room_design_id: int | str | None, slot_index: int | None) -> str | None:
        if room_design_id is None or slot_index is None:
            return None
        mapping = self._load_mapping()
        rooms = mapping.get("rooms")
        if not isinstance(rooms, dict):
            return None
        room_entry = rooms.get(str(room_design_id))
        if not isinstance(room_entry, dict):
            self._warn_once(
                f"room_item_mapping_missing_room:{room_design_id}",
                "event=room_item_mapping_missing_room room_design_id=%s",
                room_design_id,
            )
            return None
        slots = room_entry.get("slots")
        if not isinstance(slots, dict):
            return None
        slot_entry = slots.get(str(slot_index))
        if not isinstance(slot_entry, dict):
            self._warn_once(
                f"room_item_mapping_missing_slot:{room_design_id}:{slot_index}",
                "event=room_item_mapping_missing_slot room_design_id=%s slot=%s",
                room_design_id,
                slot_index,
            )
            return None
        raw_name = slot_entry.get("item_name_en_base")
        if not raw_name:
            return None
        return str(raw_name)

    def resolve_action_label(
        self,
        room_design_id: int | str | None,
        action_type_id: int | str | None,
        fallback_action_name: str | None = None,
    ) -> str:
        slot_index = self.get_slot_index_for_action_type(action_type_id)
        if slot_index is None:
            return fallback_action_name or "Sin traduccion"
        item_name_base = self.get_item_name_base(room_design_id, slot_index)
        if item_name_base is None:
            return fallback_action_name or "Sin traduccion"
        item_name = None
        if self.catalogo is not None:
            item_name = self.catalogo.resolve_item_name_from_base(
                item_name_base,
                fallback=item_name_base,
            )
        if not item_name or item_name == "Sin traduccion":
            item_name = item_name_base
        return f"Elegir objeto {item_name}"

    def _load_mapping(self) -> dict[str, Any]:
        if self._mapping is not None:
            return self._mapping
        if not self.mapping_path.exists():
            self._warn_once(
                f"room_item_mapping_missing_file:{self.mapping_path}",
                "event=room_item_mapping_missing_file path=%s",
                self.mapping_path,
            )
            self._mapping = {}
            return self._mapping
        try:
            self._mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._warn_once(
                f"room_item_mapping_parse_error:{self.mapping_path}",
                "event=room_item_mapping_parse_error path=%s error=%s",
                self.mapping_path,
                exc,
            )
            self._mapping = {}
        return self._mapping

    def _warn_once(self, key: str, msg: str, *args: Any) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        self.logger.warning(msg, *args)
