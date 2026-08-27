from __future__ import annotations
import json
import logging
from typing import Any
from app.services.api_flow_storage import ApiFlowRepository
from app.services.catalogo import CatalogoResolver
from app.services.perf_metrics import profile_method

logger = logging.getLogger(__name__)

class BattleInspectorResolver:
    def __init__(self, catalogo: CatalogoResolver) -> None:
        self.catalogo = catalogo
        self.repo = ApiFlowRepository()
        self._room_actions_cache: dict[str, dict[str, list[dict[str, str]]]] = {}

    @profile_method(threshold_ms=50)
    def resolve_battle_detail(self, detail: dict[str, Any]) -> dict[str, Any]:
        return detail

    @profile_method(threshold_ms=20)
    def get_room_actions(self, room: dict[str, Any], detail: dict[str, Any]) -> list[dict[str, str]]:
        attrs = room.get("room_attributes_json")
        if not isinstance(attrs, dict):
            attrs = {}

        # Logic moved from _room_actions_for_room
        normalized = attrs.get("RoomActionsNormalized")
        if isinstance(normalized, list) and normalized:
            out: list[dict[str, str]] = []
            for entry in normalized:
                if not isinstance(entry, dict):
                    continue
                out.append(
                    {
                        "id": str(entry.get("index") or "-"),
                        "condition_id": str(entry.get("condition_type_id") or "-"),
                        "action_id": str(entry.get("action_type_id") or entry.get("room_action_id") or "-"),
                    }
                )
            if out:
                return out

        # Fallback parsing logic
        fallback_actions = self._room_actions_from_cleaned(detail)
        room_id = str(room.get("room_id") or "")
        if room_id and room_id in fallback_actions:
            return fallback_actions[room_id]

        return []

    def _room_actions_from_cleaned(self, detail: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        api_flow = detail.get("api_flow_event") or {}
        event_id = str(api_flow.get("event_id") or api_flow.get("battle_id") or "")
        full_body = api_flow.get("response_body_full")
        cache_key = event_id or str(full_body or "")
        if cache_key in self._room_actions_cache:
            return self._room_actions_cache[cache_key]

        cleaned = ApiFlowRepository._clean_response_body(full_body)
        if not cleaned:
            self._room_actions_cache[cache_key] = {}
            return self._room_actions_cache[cache_key]
        try:
            payload = json.loads(cleaned)
        except Exception:
            self._room_actions_cache[cache_key] = {}
            return self._room_actions_cache[cache_key]
        room_actions: dict[str, list[dict[str, str]]] = {}
        for node in self._iter_nodes(payload):
            if node.get("tag") != "Room":
                continue
            attrs = node.get("attributes")
            if not isinstance(attrs, dict):
                continue
            room_id = attrs.get("RoomId")
            if room_id is None:
                continue
            actions = []
            for action_node in self._extract_children_by_path(node, ["RoomActions", "RoomAction"]):
                action_attrs = action_node.get("attributes")
                if not isinstance(action_attrs, dict):
                    continue
                actions.append(
                    {
                        "id": str(action_attrs.get("RoomActionIndex") or len(actions) + 1),
                        "condition_id": str(action_attrs.get("ConditionTypeId") or "-"),
                        "action_id": str(action_attrs.get("ActionTypeId") or action_attrs.get("RoomActionId") or "-"),
                    }
                )
            if actions:
                room_actions[str(room_id)] = actions
        self._room_actions_cache[cache_key] = room_actions
        return self._room_actions_cache[cache_key]

    def _iter_nodes(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        stack = [node]
        out: list[dict[str, Any]] = []
        while stack:
            current = stack.pop()
            if not isinstance(current, dict):
                continue
            out.append(current)
            children = current.get("children")
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        stack.append(child)
            attrs = current.get("attributes")
            if isinstance(attrs, dict):
                for value in attrs.values():
                    if isinstance(value, dict):
                        stack.append(value)
                    elif isinstance(value, list):
                        for entry in value:
                            if isinstance(entry, dict):
                                stack.append(entry)
        return out

    def _extract_children_by_path(
        self, node: dict[str, Any], path: list[str | None]
    ) -> list[dict[str, Any]]:
        current: list[dict[str, Any]] = [node]
        for expected_tag in path:
            next_nodes: list[dict[str, Any]] = []
            for item in current:
                children = item.get("children")
                if not isinstance(children, list):
                    continue
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    if expected_tag is None or child.get("tag") == expected_tag:
                        next_nodes.append(child)
            current = next_nodes
            if not current:
                break
        return current