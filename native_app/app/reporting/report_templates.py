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


class H2HReportTemplate(ReportTemplate):
    """Template for H2H (Head-to-Head) comparative reports"""

    @staticmethod
    def summary_rows(h2h_data: dict) -> list[dict[str, Any]]:
        """Generate summary sheet rows from H2H data"""
        summary = h2h_data.get("summary", {})
        player_low = summary.get("player_low_name", "Player A")
        player_high = summary.get("player_high_name", "Player B")
        low_wins = summary.get("player_low_wins", 0)
        high_wins = summary.get("player_high_wins", 0)
        draws = summary.get("unknown_results", 0)
        total = summary.get("total_battles", 0)
        low_avg_trophies = summary.get("player_low_avg_trophies", 0)
        high_avg_trophies = summary.get("player_high_avg_trophies", 0)
        low_total_loot = summary.get("player_low_total_loot", 0)
        high_total_loot = summary.get("player_high_total_loot", 0)

        return [
            {"Métrica": "Jugador 1", "Valor": player_low},
            {"Métrica": "Jugador 2", "Valor": player_high},
            {"Métrica": "Total Batallas", "Valor": total},
            {"Métrica": f"Victorias {player_low}", "Valor": low_wins},
            {"Métrica": f"Victorias {player_high}", "Valor": high_wins},
            {"Métrica": "Empates", "Valor": draws},
            {"Métrica": f"Win Rate {player_low}", "Valor": f"{(low_wins/total*100):.1f}%" if total > 0 else "0%"},
            {"Métrica": f"Win Rate {player_high}", "Valor": f"{(high_wins/total*100):.1f}%" if total > 0 else "0%"},
            {"Métrica": f"Promedio Trofeos {player_low}", "Valor": low_avg_trophies},
            {"Métrica": f"Promedio Trofeos {player_high}", "Valor": high_avg_trophies},
            {"Métrica": f"Total Botín {player_low}", "Valor": low_total_loot},
            {"Métrica": f"Total Botín {player_high}", "Valor": high_total_loot},
            {"Métrica": "Fecha Primera Batalla", "Valor": ReportTemplate.format_datetime(summary.get("first_battle_date"))},
            {"Métrica": "Fecha Última Batalla", "Valor": ReportTemplate.format_datetime(summary.get("last_battle_date"))},
        ]

    @staticmethod
    def battle_rows(h2h_data: dict) -> list[dict[str, Any]]:
        """Generate battles sheet rows from H2H data"""
        battles = h2h_data.get("battles", [])
        rows = []
        for b in battles:
            rows.append({
                "Fecha": ReportTemplate.format_datetime(b.get("captured_at")),
                "Battle ID": b.get("battle_id", "-"),
                "Atacante": b.get("attacker_name", "-"),
                "Defensor": b.get("defender_name", "-"),
                "Resultado": b.get("outcome", "-"),
                "Trofeos Atacante": b.get("attacker_trophy_delta", 0),
                "Trofeos Defensor": b.get("defender_trophy_delta", 0),
                "Botín Minerales": b.get("loot_minerals", "-"),
                "Botín Gas": b.get("loot_gas", "-"),
            })
        return rows

    @staticmethod
    def trend_rows(h2h_data: dict) -> list[dict[str, Any]]:
        """Generate trends sheet rows from H2H data (time-series buckets)"""
        trends = h2h_data.get("trends", [])
        rows = []
        for t in trends:
            rows.append({
                "Periodo": t.get("period", "-"),
                "Batallas": t.get("battle_count", 0),
                f"Win Rate {h2h_data.get('summary', {}).get('player_low_name', 'Player A')}": f"{(t.get('player_low_wins', 0)/t.get('battle_count', 1)*100):.1f}%" if t.get('battle_count', 0) > 0 else "0%",
                f"Win Rate {h2h_data.get('summary', {}).get('player_high_name', 'Player B')}": f"{(t.get('player_high_wins', 0)/t.get('battle_count', 1)*100):.1f}%" if t.get('battle_count', 0) > 0 else "0%",
                f"Promedio Trofeos {h2h_data.get('summary', {}).get('player_low_name', 'Player A')}": t.get("player_low_avg_trophies", 0),
                f"Promedio Trofeos {h2h_data.get('summary', {}).get('player_high_name', 'Player B')}": t.get("player_high_avg_trophies", 0),
            })
        return rows
