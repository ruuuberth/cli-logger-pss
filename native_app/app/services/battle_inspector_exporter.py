from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.services.battle_inspector_resolver import BattleInspectorResolver
from app.services.catalogo import CatalogoResolver
from app.services.character_inspector_resolver import CharacterInspectorResolver
from app.services.room_item_mapping import RoomItemMappingResolver


class BattleInspectorExportService:
    def __init__(
        self,
        catalogo: CatalogoResolver | None = None,
        character_inspector: CharacterInspectorResolver | None = None,
        room_item_mapping: RoomItemMappingResolver | None = None,
        battle_resolver: BattleInspectorResolver | None = None,
    ) -> None:
        self.catalogo = catalogo or CatalogoResolver(base_dir=CatalogoResolver.default_base_dir())
        self.character_inspector = character_inspector or CharacterInspectorResolver(catalogo=self.catalogo)
        self.room_item_mapping = room_item_mapping
        self.battle_resolver = battle_resolver or BattleInspectorResolver(catalogo=self.catalogo)

    def build_payload(self, detail: dict[str, Any]) -> dict[str, Any]:
        replay = detail.get("replay") or {}
        return {
            "exported_at": self._utc_timestamp(),
            "battle": self._build_simplified_battle(replay, detail),
            "rooms": self._build_simplified_rooms(detail),
            "characters": self._build_simplified_characters(detail),
        }

    def _build_simplified_battle(self, replay: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
        """Construye los datos esenciales de la batalla para el JSON.

        Args:
            replay: Datos crudos de la repetición.
            detail: Detalles adicionales.

        Returns:
            Diccionario con datos simplificados de la batalla.
        """
        return {
            "fecha": self._as_text(replay.get("captured_at"), "-"),
            "battle_id": self._as_text(replay.get("battle_id"), "-"),
            "players": [
                {"side": "attacker", "name": self._as_text(replay.get("attacker_name"), "-")},
                {"side": "defender", "name": self._as_text(replay.get("defender_name"), "-")},
            ],
            "h2h": detail.get("matchup_summary") or {},
            "botin": {
                "trophy": f"{self._as_text(replay.get('win_trophy_result'), '0')} / {self._as_text(replay.get('lose_trophy_result'), '0')}",
                "minerals": f"{self._as_text(replay.get('win_minerals_result'), '0')} / {self._as_text(replay.get('lose_minerals_result'), '0')}",
                "gas": f"{self._as_text(replay.get('win_gas_result'), '0')} / {self._as_text(replay.get('lose_gas_result'), '0')}",
            },
            "score": {
                "atacante": self._as_text(replay.get("attacker_user_attributes_json", {}).get("power_score"), "0"),
                "defensor": self._as_text(replay.get("defender_user_attributes_json", {}).get("power_score"), "0"),
            },
        }

    def _format_ai_chains(self, actions: list[dict[str, Any]]) -> tuple[str, str]:
        human_parts = []
        raw_parts = []
        for a in actions:
            cond = a.get("condition_label") or a.get("condition_type_label") or "-"
            act = a.get("resolved_action_label") or a.get("action_label") or a.get("action_type_label") or "-"
            cond_id = a.get("condition_id") or a.get("condition_type_id") or "-"
            act_id = a.get("action_id") or a.get("action_type_id") or "-"

            if cond_id == "-" and act_id == "-":
                continue

            human_parts.append(f"{cond} -> {act}")
            raw_parts.append(f"{cond_id}x{act_id}")

        return " | ".join(human_parts) or "-", "|".join(raw_parts) or "-"

    def _build_simplified_rooms(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        """Construye la lista simplificada de salas con IA para el JSON.

        Args:
            detail: Datos crudos de la batalla.

        Returns:
            Lista de salas normalizadas.
        """
        rooms = detail.get("rooms") or []
        return [formatted for r in rooms if (formatted := self._format_room(r, detail))]

    def _format_room(self, room: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any] | None:
        """Formatea una única sala si tiene acciones de IA."""
        ai_actions = self._build_room_actions_for_room(room, detail)
        if not ai_actions:
            return None

        attrs = room.get("room_attributes_json") or {}
        design_id = room.get("room_design_id")
        ai_human, ai_raw = self._format_ai_chains(ai_actions)

        return {
            "1_id_diseno": self._as_text(design_id, "-"),
            "2_nombre_diseno": self._resolve_design_name("room", design_id, room.get("room_design_name")),
            "3_prioridad": attrs.get("Priority", "-"),
            "4_fila": self._as_text(room.get("row"), "-"),
            "5_columna": self._as_text(room.get("column"), "-"),
            "6_target_manufacture": attrs.get("TargetManufactureString", "-"),
            "7_cadena_ia_humana": ai_human,
            "7_cadena_ia_raw": ai_raw,
            "design_id": self._as_text(design_id, "-"),
            "design_name": self._resolve_design_name("room", design_id, room.get("room_design_name")),
            "ai_chain": ai_raw,
        }

    def _build_simplified_characters(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        """Construye la lista simplificada de tripulantes para el JSON.

        Args:
            detail: Datos crudos de la batalla.

        Returns:
            Lista de tripulantes normalizados.
        """
        characters = detail.get("characters") or []
        room_map = {str(r.get("room_id")): r.get("room_design_name") for r in detail.get("rooms") or []}
        return [self._format_character(char, room_map) for char in characters]

    def _format_character(self, character: dict[str, Any], room_map: dict[str, str]) -> dict[str, Any]:
        """Formatea un único tripulante."""
        design_id = character.get("character_design_id")
        stats = self.character_inspector.get_character_stats_summary(character)
        room_id = stats.get("room_id", "-")
        actions = self.character_inspector.get_character_actions(character)
        ai_human, ai_raw = self._format_ai_chains(actions)

        return {
            "1_id_diseno": self._as_text(design_id, "-"),
            "2_nombre_diseno": self._resolve_design_name("character", design_id, character.get("character_design_name")),
            "3_nombre": self._as_text(character.get("character_name"), "-"),
            "4_nivel": self._as_text(character.get("level"), "-"),
            "5_xp": self._as_text(character.get("xp"), "-"),
            "6_sala": room_id,
            "6_nombre_sala": room_map.get(room_id, "-"),
            "7_atributos": {
                "stamina": stats.get("stamina", "-"),
                "fatigue": stats.get("fatigue", "-"),
                "vida": stats.get("hp_improvement", "-"),
                "ataque": stats.get("attack_improvement", "-"),
                "reparacion": stats.get("repair_improvement", "-"),
                "pilotaje": stats.get("pilot_improvement", "-"),
                "ciencia": stats.get("science_improvement", "-"),
                "ingenieria": stats.get("engine_improvement", "-"),
                "arma": stats.get("weapon_improvement", "-"),
                "habilidad": stats.get("ability_improvement", "-"),
            },
            "8_equipo": self.character_inspector.get_character_items(character),
            "9_cadena_ia_humana": ai_human,
            "9_cadena_ia_raw": ai_raw,
            "design_id": self._as_text(design_id, "-"),
            "attributes": {
                "stamina": stats.get("stamina", "-"),
            },
            "equipment": self.character_inspector.get_character_items(character),
            "ai_chain": ai_raw,
        }

    def _build_commands_payload(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        commands = detail.get("commands") or []
        out: list[dict[str, Any]] = []
        for command in commands:
            out.append(
                {
                    "command_order": self._as_text(command.get("command_order"), "-"),
                    "command_tag": self._as_text(command.get("command_tag"), "-"),
                    "raw_command": command,
                }
            )
        return out

    def _build_room_actions_payload(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for room in detail.get("rooms") or []:
            actions = self._build_room_actions_for_room(room, detail)
            for action in actions:
                rows.append(
                    {
                        "room_id": self._as_text(room.get("room_id"), "-"),
                        "room_design_id": self._as_text(room.get("room_design_id"), "-"),
                        "side": self._as_text(room.get("side"), "-"),
                        **action,
                    }
                )
        return rows

    def _build_character_items_payload(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for character in detail.get("characters") or []:
            items = self.character_inspector.get_character_items(character)
            if not items:
                continue
            rows.append(
                {
                    "character_name": self._as_text(character.get("character_name"), "-"),
                    "character_design_id": self._as_text(character.get("character_design_id"), "-"),
                    "items": items,
                }
            )
        return rows

    def _build_character_actions_payload(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for character in detail.get("characters") or []:
            actions = self.character_inspector.get_character_actions(character)
            if not actions:
                continue
            rows.append(
                {
                    "character_name": self._as_text(character.get("character_name"), "-"),
                    "character_design_id": self._as_text(character.get("character_design_id"), "-"),
                    "actions": actions,
                }
            )
        return rows

    def _build_room_actions_for_room(self, room: dict[str, Any], detail: dict[str, Any]) -> list[dict[str, Any]]:
        attrs = room.get("room_attributes_json")
        if not isinstance(attrs, dict):
            attrs = {}
        normalized = attrs.get("RoomActionsNormalized")
        rows: list[dict[str, Any]] = []
        if isinstance(normalized, list) and normalized:
            for entry in normalized:
                if not isinstance(entry, dict):
                    continue
                rows.append(self._normalize_room_action_entry(room, entry))
            return rows
        fallback_actions = self.battle_resolver.get_room_actions(room, detail)
        for entry in fallback_actions:
            rows.append(self._normalize_room_action_entry(room, entry))
        return rows

    def _normalize_room_action_entry(self, room: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        action_id = entry.get("action_id") or entry.get("action_type_id") or entry.get("room_action_id")
        condition_id = entry.get("condition_id") or entry.get("condition_type_id")
        action_index = entry.get("id") or entry.get("index") or "-"
        action_label, condition_label = self._resolve_action_condition(action_id, condition_id)
        resolved_action_label = self._resolve_room_action_label(room, action_id, action_label)
        return {
            "id": self._as_text(action_index, "-"),
            "condition_id": self._as_text(condition_id, "-"),
            "condition_label": self._as_text(condition_label, "-"),
            "action_id": self._as_text(action_id, "-"),
            "action_label": self._as_text(action_label, "-"),
            "resolved_action_label": self._as_text(resolved_action_label, "-"),
            "action_chain": self._build_ai_chain(condition_id, action_id),
        }

    def _resolve_action_condition(self, action_id: Any, condition_id: Any) -> tuple[str, str]:
        """Resuelve las etiquetas de acción y condición usando el catálogo.

        Args:
            action_id: ID de la acción.
            condition_id: ID de la condición.

        Returns:
            Tupla con (etiqueta_acción, etiqueta_condición).
        """
        return self.catalogo.resolve_action_condition(action_id, condition_id)

    def _resolve_room_action_label(self, room: dict[str, Any], action_id: Any, fallback_action_name: str) -> str:
        """Resuelve la etiqueta de acción específica para una sala.

        Args:
            room: Datos de la sala.
            action_id: ID de la acción.
            fallback_action_name: Etiqueta por defecto si no se encuentra mapeo.

        Returns:
            Etiqueta resuelta.
        """
        if self.room_item_mapping is None:
            return fallback_action_name
        room_design_id = room.get("room_design_id")
        return self.room_item_mapping.resolve_action_label(
            room_design_id,
            action_id,
            fallback_action_name=fallback_action_name,
        )

    def _resolve_design_name(self, kind: str, design_id: Any, current_name: Any) -> str:
        """Resuelve el nombre de diseño usando el catálogo.

        Args:
            kind: Tipo de diseño (ship, room, character).
            design_id: ID del diseño.
            current_name: Nombre actual opcional.

        Returns:
            Nombre resuelto o "Sin traduccion".
        """
        return self.catalogo.resolve_design_name(design_id, current_name, kind)

    def _compact_attributes(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(attrs, dict):
            return {}
        return {str(key): self._normalize_value(value) for key, value in sorted(attrs.items())}

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._normalize_value(inner) for key, inner in sorted(value.items())}
        if isinstance(value, list):
            return [self._normalize_value(item) for item in value]
        if value is None:
            return None
        return value

    def _build_ai_chain(self, condition_id: Any, action_id: Any) -> str:
        condition_text = self._as_text(condition_id, "-")
        action_text = self._as_text(action_id, "-")
        if condition_text == "-" and action_text == "-":
            return "-"
        return f"{condition_text}x{action_text}"

    def _fallback_label(self, value: Any, prefix: str) -> str:
        text = self._as_text(value, "-")
        return f"{prefix} {text}" if text != "-" else prefix

    def _as_text(self, value: Any, fallback: str | None = None) -> str:
        if value is None:
            return "" if fallback is None else str(fallback)
        if isinstance(value, str):
            return value
        return str(value)

    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def export_battle_inspector_json(detail: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    service = BattleInspectorExportService(**kwargs)
    return service.build_payload(detail)
