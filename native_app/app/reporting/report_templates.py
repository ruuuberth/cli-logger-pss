"""Report templates for common report types"""
from __future__ import annotations

from typing import Any
from datetime import datetime


class ReportTemplate:
    """Base template for reports"""

    @staticmethod
    def format_datetime(dt: Any) -> str:
        """Format datetime for reports"""
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt)


class BattleReplayTemplate(ReportTemplate):
    """Template for battle replay reports"""

    @staticmethod
    def row_from_battle(battle_data: dict) -> dict[str, Any]:
        """Convert battle data to report row"""
        return {
            "Battle ID": battle_data.get("battle_id", "-"),
            "Attackante": battle_data.get("attacker_name", "-"),
            "Defensor": battle_data.get("defender_name", "-"),
            "Resultado": battle_data.get("outcome", "-"),
            "Botín": battle_data.get("loot", "-"),
            "Copas": battle_data.get("trophy_delta", "-"),
            "Fecha Captura": ReportTemplate.format_datetime(battle_data.get("captured_at")),
        }


class ApiEventTemplate(ReportTemplate):
    """Template for API event reports"""

    @staticmethod
    def row_from_event(event_data: dict) -> dict[str, Any]:
        """Convert event data to report row"""
        return {
            "Timestamp": ReportTemplate.format_datetime(event_data.get("timestamp")),
            "Endpoint": event_data.get("endpoint", "-"),
            "Método": event_data.get("method", "-"),
            "Status": event_data.get("status_code", "-"),
            "Tamaño (bytes)": event_data.get("size_bytes", "-"),
            "Tipo": event_data.get("event_type", "-"),
        }


class CharacterTemplate(ReportTemplate):
    """Template for character/crew reports"""

    @staticmethod
    def row_from_character(char_data: dict) -> dict[str, Any]:
        """Convert character data to report row"""
        return {
            "Character ID": char_data.get("character_id", "-"),
            "Nombre": char_data.get("name", "-"),
            "Rango": char_data.get("rarity", "-"),
            "Habilidades IA": char_data.get("ai_skills", "-"),
            "Stats": char_data.get("stats", "-"),
            "Comandos": char_data.get("commands", "-"),
        }


class RoomTemplate(ReportTemplate):
    """Template for room reports"""

    @staticmethod
    def row_from_room(room_data: dict) -> dict[str, Any]:
        """Convert room data to report row"""
        return {
            "Room ID": room_data.get("room_id", "-"),
            "Nombre": room_data.get("name", "-"),
            "Nivel": room_data.get("level", "-"),
            "Items": room_data.get("items", "-"),
            "Comandos": room_data.get("commands", "-"),
            "IA Actions": room_data.get("room_actions", "-"),
        }


class CaptureStatsTemplate(ReportTemplate):
    """Template for capture statistics reports"""

    @staticmethod
    def row_from_stats(stats: dict) -> dict[str, Any]:
        """Convert stats data to report row"""
        return {
            "Timestamp": ReportTemplate.format_datetime(datetime.now()),
            "Total Eventos": stats.get("total_events", 0),
            "Eventos/seg": f"{stats.get('events_per_second', 0):.2f}",
            "Uptime (seg)": stats.get("uptime_seconds", 0),
            "Estado Proxy": "Activo" if stats.get("proxy_running", False) else "Inactivo",
            "Capturando": "Sí" if stats.get("is_capturing", False) else "No",
        }
