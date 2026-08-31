"""CLI Services - Intermediary layer to expose backend services without Qt dependencies"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Optional
from pathlib import Path

from app.dto.api_flow_dto import ApiFlowPageDTO, ApiFlowRowDTO
from app.services.api_flow_list_service import ApiFlowListService
from app.services.catalogo import CatalogoResolver
from app.services.character_inspector_resolver import CharacterInspectorResolver


class ApiFlowCliService:
    """Provides API flow functionality for CLI"""

    def __init__(self):
        self.list_service = ApiFlowListService()
        self.logger = logging.getLogger(__name__)

    def query_events(
        self,
        search: str = "",
        page: int = 0,
        page_size: int = 20,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        outcome: str | None = None,
        trophy_min: int | None = None,
        trophy_max: int | None = None,
    ) -> ApiFlowPageDTO:
        """Query API events from database"""
        try:
            # Get page from service (returns ApiFlowPage with service models)
            service_page = self.list_service.list_page(
                search=search,
                page=page,
                page_size=page_size,
                time_from=time_from,
                time_to=time_to,
                outcome=outcome,
                trophy_min=trophy_min,
                trophy_max=trophy_max,
            )
            
            # Convert to pure DTO
            dto_page = ApiFlowPageDTO.from_service_model(service_page)
            return dto_page
        except Exception as e:
            self.logger.error(f"Error querying events: {e}")
            raise

    def delete_event(self, event_id: int) -> bool:
        """Delete a specific event"""
        try:
            deleted = self.list_service.delete_event(event_id)
            return deleted > 0
        except Exception as e:
            self.logger.error(f"Error deleting event {event_id}: {e}")
            raise

    def clear_all_events(self) -> dict:
        """Clear all events and replays"""
        try:
            result = self.list_service.clear_history()
            return {
                "deleted_events": result.deleted_events,
                "deleted_replays": result.deleted_replays,
            }
        except Exception as e:
            self.logger.error(f"Error clearing events: {e}")
            raise

    def get_battle_detail(self, battle_replay_id: int) -> Optional[dict]:
        """Get detailed battle information"""
        try:
            detail = self.list_service.get_battle_detail(battle_replay_id)
            return detail
        except Exception as e:
            self.logger.error(f"Error getting battle detail: {e}")
            raise


class CharacterCliService:
    """Provides character/crew functionality for CLI"""

    def __init__(self, list_service: Any = None, catalogo: CatalogoResolver | None = None):
        self.list_service = list_service or ApiFlowListService()
        self.logger = logging.getLogger(__name__)
        self.catalogo = catalogo

    def _resolver(self) -> CharacterInspectorResolver:
        return CharacterInspectorResolver(catalogo=self.catalogo, logger=self.logger)

    def list_characters(self, battle_replay_id: int) -> list[dict]:
        """List characters from a battle replay"""
        try:
            detail = self.list_service.get_battle_detail(battle_replay_id)
            if not detail:
                return []
            characters = detail.get("characters", [])
            return [
                {
                    "id": c.get("id"),
                    "character_id": c.get("character_id"),
                    "side": c.get("side"),
                    "name": c.get("character_name") or c.get("character_design_name"),
                    "design_name": c.get("character_design_name"),
                    "level": c.get("level"),
                    "ship_id": c.get("ship_id"),
                }
                for c in characters
                if isinstance(c, dict)
            ]
        except Exception as e:
            self.logger.error(f"Error listing characters: {e}")
            raise

    def inspect_character(self, character_id: int, battle_replay_id: int, side: str = "") -> dict:
        """Get character details for inspection"""
        try:
            detail = self.list_service.get_battle_detail(battle_replay_id)
            if not detail:
                return {"error": "No se encontró el detalle de la batalla"}
            characters = detail.get("characters", [])
            row = None
            for c in characters:
                if not isinstance(c, dict):
                    continue
                if c.get("character_id") == character_id or c.get("id") == character_id:
                    row = c
                    break
            if row is None:
                return {"error": f"No se encontró el personaje {character_id}"}

            resolver = self._resolver()
            return {
                "character_id": row.get("character_id"),
                "name": row.get("character_name") or row.get("character_design_name"),
                "design_name": row.get("character_design_name"),
                "side": row.get("side") or side,
                "level": row.get("level"),
                "xp": row.get("xp"),
                "ship_id": row.get("ship_id"),
                "stats": resolver.get_character_stats_summary(row),
                "actions": resolver.get_character_actions(row),
                "items": resolver.get_character_items(row),
            }
        except Exception as e:
            self.logger.error(f"Error inspecting character: {e}")
            raise


class RoomCliService:
    """Provides room functionality for CLI"""

    def __init__(self, list_service: Any = None, catalogo: CatalogoResolver | None = None):
        self.list_service = list_service or ApiFlowListService()
        self.logger = logging.getLogger(__name__)
        self.catalogo = catalogo

    def _resolvers(self):
        from app.services.battle_inspector_resolver import BattleInspectorResolver
        from app.services.room_item_mapping import RoomItemMappingResolver
        return (
            BattleInspectorResolver(self.catalogo or CatalogoResolver(CatalogoResolver.default_base_dir())),
            RoomItemMappingResolver(catalogo=self.catalogo, logger=self.logger),
        )

    def list_rooms(self, battle_replay_id: int) -> list[dict]:
        """List rooms from a battle replay"""
        try:
            detail = self.list_service.get_battle_detail(battle_replay_id)
            if not detail:
                return []
            rooms = detail.get("rooms", [])
            return [
                {
                    "id": r.get("id"),
                    "room_id": r.get("room_id"),
                    "side": r.get("side"),
                    "design_name": r.get("room_design_name"),
                    "ship_id": r.get("ship_id"),
                    "row": r.get("row"),
                    "column": r.get("column"),
                }
                for r in rooms
                if isinstance(r, dict)
            ]
        except Exception as e:
            self.logger.error(f"Error listing rooms: {e}")
            raise

    def inspect_room(self, room_id: int, battle_replay_id: int, side: str = "") -> dict:
        """Get room details for inspection"""
        try:
            detail = self.list_service.get_battle_detail(battle_replay_id)
            if not detail:
                return {"error": "No se encontró el detalle de la batalla"}
            rooms = detail.get("rooms", [])
            row = None
            for r in rooms:
                if not isinstance(r, dict):
                    continue
                if r.get("room_id") == room_id or r.get("id") == room_id:
                    row = r
                    break
            if row is None:
                return {"error": f"No se encontró la sala {room_id}"}

            resolver, mapping = self._resolvers()
            raw_actions = resolver.get_room_actions(row, detail)
            room_design_id = row.get("room_design_id")
            actions = []
            for a in raw_actions:
                action_type_id = a.get("action_id")
                condition_id = a.get("condition_id")
                if self.catalogo is not None:
                    action_label, condition_label = self.catalogo.resolve_action_condition(
                        action_type_id, condition_id
                    )
                else:
                    action_label, condition_label = (str(action_type_id), str(condition_id))
                room_action_label = mapping.resolve_action_label(
                    room_design_id, action_type_id, fallback_action_name=action_label
                )
                actions.append(
                    {
                        "index": a.get("id"),
                        "action_type_id": action_type_id,
                        "action_label": room_action_label,
                        "condition_type_id": condition_id,
                        "condition_label": condition_label,
                        "room_action_id": a.get("id"),
                    }
                )

            return {
                "room_id": row.get("room_id"),
                "room_id_num": row.get("room_id"),
                "design_name": row.get("room_design_name"),
                "side": row.get("side") or side,
                "ship_id": row.get("ship_id"),
                "row": row.get("row"),
                "column": row.get("column"),
                "room_status": row.get("room_status"),
                "actions": actions,
            }
        except Exception as e:
            self.logger.error(f"Error inspecting room: {e}")
            raise
