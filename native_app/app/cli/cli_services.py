"""CLI Services - Intermediary layer to expose backend services without Qt dependencies"""
from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path

from app.dto.api_flow_dto import ApiFlowPageDTO, ApiFlowRowDTO
from app.services.api_flow_list_service import ApiFlowListService


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
    ) -> ApiFlowPageDTO:
        """Query API events from database"""
        try:
            # Get page from service (returns ApiFlowPage with service models)
            service_page = self.list_service.list_page(
                search=search,
                page=page,
                page_size=page_size,
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

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def inspect_character(self, character_id: int) -> dict:
        """Get character details for inspection"""
        try:
            from app.services.character_inspector_resolver import CharacterInspectorResolver
            resolver = CharacterInspectorResolver()
            # TODO: Implement once we understand the service API
            return {
                "character_id": character_id,
                "name": "Character",
                "ai_skills": [],
                "commands": [],
            }
        except Exception as e:
            self.logger.error(f"Error inspecting character: {e}")
            raise

    def list_characters(self, search: str = "") -> list[dict]:
        """List characters with optional search"""
        try:
            # TODO: Implement once we understand the service API
            return []
        except Exception as e:
            self.logger.error(f"Error listing characters: {e}")
            raise


class RoomCliService:
    """Provides room functionality for CLI"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def inspect_room(self, room_id: int) -> dict:
        """Get room details for inspection"""
        try:
            from app.services.room_item_mapping import RoomItemMappingService
            # TODO: Implement once we understand the service API
            return {
                "room_id": room_id,
                "name": "Room",
                "level": 0,
                "items": [],
                "commands": [],
                "room_actions": [],
            }
        except Exception as e:
            self.logger.error(f"Error inspecting room: {e}")
            raise

    def list_rooms(self) -> list[dict]:
        """List all rooms"""
        try:
            # TODO: Implement once we understand the service API
            return []
        except Exception as e:
            self.logger.error(f"Error listing rooms: {e}")
            raise
