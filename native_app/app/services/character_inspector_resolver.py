from __future__ import annotations

import logging
import re
from typing import Any

from app.services.catalogo import CatalogoResolver

_CHARACTER_ACTION_PATTERN = re.compile(r"^CharacterActions\.CharacterAction\[(\d+)\]\.(.+)$")
_CHARACTER_ITEM_PATTERN = re.compile(r"^Items\.Item\[(\d+)\]\.(.+)$")


class CharacterInspectorResolver:
    def __init__(
        self,
        catalogo: CatalogoResolver | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.catalogo = catalogo
        self.logger = logger or logging.getLogger(__name__)

    def has_actions(self, character: dict[str, Any]) -> bool:
        return bool(self.get_character_actions(character))

    def has_items(self, character: dict[str, Any]) -> bool:
        return bool(self.get_character_items(character))

    def get_character_actions(self, character: dict[str, Any]) -> list[dict[str, str]]:
        attrs = self._attrs(character)
        normalized = attrs.get("CharacterActionsNormalized")
        rows: list[dict[str, Any]]
        if isinstance(normalized, list) and normalized:
            rows = [entry for entry in normalized if isinstance(entry, dict)]
        else:
            rows = self._rebuild_actions(attrs)

        out: list[dict[str, str]] = []
        for idx, entry in enumerate(rows, start=1):
            action_id = entry.get("action_type_id")
            condition_id = entry.get("condition_type_id")
            action_label, condition_label = self._resolve_action_condition(action_id, condition_id)
            action_index = entry.get("index")
            try:
                action_index_text = str(int(str(action_index)) + 1)
            except Exception:
                action_index_text = str(action_index or idx)
            out.append(
                {
                    "index": action_index_text,
                    "condition_id": self._as_text(condition_id),
                    "condition_label": condition_label,
                    "action_id": self._as_text(action_id),
                    "action_label": action_label,
                    "character_action_id": self._as_text(entry.get("character_action_id")),
                }
            )
        return out

    def get_character_items(self, character: dict[str, Any]) -> list[dict[str, str]]:
        attrs = self._attrs(character)
        normalized = attrs.get("CharacterItemsNormalized")
        rows: list[dict[str, Any]]
        if isinstance(normalized, list) and normalized:
            rows = [entry for entry in normalized if isinstance(entry, dict)]
        else:
            rows = self._rebuild_items(attrs)

        out: list[dict[str, str]] = []
        for idx, entry in enumerate(rows, start=1):
            item_design_id = entry.get("item_design_id")
            item_name = self._resolve_item_name(item_design_id)
            out.append(
                {
                    "index": self._index_text(entry.get("index"), idx),
                    "item_id": self._as_text(entry.get("item_id")),
                    "item_design_id": self._as_text(item_design_id),
                    "item_name": item_name,
                    "quantity": self._as_text(entry.get("quantity"), "-"),
                    "bonus_type": self._as_text(entry.get("bonus_enhancement_type"), "-"),
                    "bonus_value": self._as_text(entry.get("bonus_enhancement_value"), "-"),
                }
            )
        return out

    def get_character_stats_summary(self, character: dict[str, Any]) -> dict[str, str]:
        attrs = self._attrs(character)
        training_design_id = self._as_text(attrs.get("TrainingDesignId"), "-")
        training_end_date = self._as_text(attrs.get("TrainingEndDate"), "-")
        training_value = training_end_date if training_end_date not in {"", "-", "None"} else "-"
        if training_value == "-" and training_design_id not in {"", "-", "0"}:
            training_value = training_design_id
        return {
            "room_id": self._as_text(attrs.get("RoomId"), "-"),
            "ship_id": self._as_text(attrs.get("ShipId"), "-"),
            "stamina": self._as_text(attrs.get("Stamina"), "-"),
            "fatigue": self._as_text(attrs.get("Fatigue"), "-"),
            "attack_improvement": self._as_text(attrs.get("AttackImprovement"), "-"),
            "repair_improvement": self._as_text(attrs.get("RepairImprovement"), "-"),
            "pilot_improvement": self._as_text(attrs.get("PilotImprovement"), "-"),
            "science_improvement": self._as_text(attrs.get("ScienceImprovement"), "-"),
            "engine_improvement": self._as_text(attrs.get("EngineImprovement"), "-"),
            "ability_improvement": self._as_text(attrs.get("AbilityImprovement"), "-"),
            "hp_improvement": self._as_text(attrs.get("HpImprovement"), "-"),
            "weapon_improvement": self._as_text(attrs.get("WeaponImprovement"), "-"),
            "training": training_value,
        }

    def _attrs(self, character: dict[str, Any]) -> dict[str, Any]:
        attrs = character.get("character_attributes_json")
        return attrs if isinstance(attrs, dict) else {}

    def _rebuild_actions(self, attrs: dict[str, Any]) -> list[dict[str, Any]]:
        actions: dict[int, dict[str, Any]] = {}
        for key, value in attrs.items():
            match = _CHARACTER_ACTION_PATTERN.match(str(key))
            if not match:
                continue
            idx = int(match.group(1))
            field = match.group(2)
            actions.setdefault(idx, {})[field] = value
        return [
            {
                "index": payload.get("CharacterActionIndex", idx),
                "condition_type_id": payload.get("ConditionTypeId"),
                "action_type_id": payload.get("ActionTypeId"),
                "character_action_id": payload.get("CharacterActionId"),
            }
            for idx, payload in sorted(actions.items())
        ]

    def _rebuild_items(self, attrs: dict[str, Any]) -> list[dict[str, Any]]:
        items: dict[int, dict[str, Any]] = {}
        for key, value in attrs.items():
            match = _CHARACTER_ITEM_PATTERN.match(str(key))
            if not match:
                continue
            idx = int(match.group(1))
            field = match.group(2)
            items.setdefault(idx, {})[field] = value
        return [
            {
                "index": idx,
                "item_id": payload.get("ItemId"),
                "item_design_id": payload.get("ItemDesignId"),
                "quantity": payload.get("Quantity"),
                "is_new": payload.get("IsNew"),
                "skin_key": payload.get("SkinKey"),
                "bonus_enhancement_type": payload.get("BonusEnhancementType"),
                "bonus_enhancement_value": payload.get("BonusEnhancementValue"),
            }
            for idx, payload in sorted(items.items())
        ]

    def _resolve_action_condition(self, action_id: Any, condition_id: Any) -> tuple[str, str]:
        if self.catalogo is not None:
            return self.catalogo.resolve_action_condition(action_id, condition_id)
        action_text = self._as_text(action_id, "Sin traduccion")
        condition_text = self._as_text(condition_id, "Sin traduccion")
        return action_text, condition_text

    def _resolve_item_name(self, item_design_id: Any) -> str:
        if self.catalogo is not None:
            return self.catalogo.resolve_item_name(item_design_id)
        item_text = self._as_text(item_design_id, "")
        return f"ItemDesignId {item_text}" if item_text else "Sin traduccion"

    def _index_text(self, value: Any, fallback_index: int) -> str:
        try:
            return str(int(str(value)) + 1)
        except Exception:
            return self._as_text(value, str(fallback_index))

    def _as_text(self, value: Any, fallback: str = "-") -> str:
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback
