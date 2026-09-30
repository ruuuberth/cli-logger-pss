"""Tests for H2HReportTemplate.fleet_breakdown_rows."""
from __future__ import annotations

from app.reporting.report_templates import H2HReportTemplate


def _summary() -> dict:
    return {"player_low_name": "Alice", "player_high_name": "Bob"}


def test_fleet_breakdown_rows_empty_when_no_breakdown() -> None:
    assert H2HReportTemplate.fleet_breakdown_rows({}) == []
    assert H2HReportTemplate.fleet_breakdown_rows({"fleet_breakdown": None}) == []


def test_fleet_breakdown_rows_structure() -> None:
    h2h = {
        "summary": _summary(),
        "fleet_breakdown": {
            "battles_analyzed": 3,
            "player_low": {
                "user_id": 10,
                "total_battles_analyzed": 3,
                "ships": [{"id": 11, "battles": 3, "ship_name": "ShipA", "ship_design_name": "Acorazado",
                           "avg_level": 8.5, "avg_power_score": 4200.0}],
                "rooms": [{"id": 111, "battles": 2, "room_design_name": "Escudo"}],
                "crew": [{"id": 112, "battles": 1, "character_name": "PilotoX", "character_design_name": "Piloto",
                          "avg_level": 12.0}],
            },
            "player_high": {
                "user_id": 20,
                "total_battles_analyzed": 3,
                "ships": [],
                "rooms": [],
                "crew": [],
            },
        },
    }

    rows = H2HReportTemplate.fleet_breakdown_rows(h2h)
    assert len(rows) == 3

    ship_row = rows[0]
    assert ship_row["Jugador"] == "Alice"
    assert ship_row["Tipo"] == "Nave"
    assert ship_row["Nombre"] == "Acorazado"
    assert ship_row["Ship ID"] == 11
    assert ship_row["Nivel Promedio"] == 8.5
    assert ship_row["Power Score Promedio"] == 4200.0
    assert ship_row["Batallas Usado"] == "3/3"

    room_row = rows[1]
    assert room_row["Tipo"] == "Sala"
    assert room_row["Nombre"] == "Escudo"
    assert room_row["Batallas Usado"] == "2/3"

    crew_row = rows[2]
    assert crew_row["Tipo"] == "Tripulacion"
    assert crew_row["Nombre"] == "Piloto"
    assert crew_row["Batallas Usado"] == "1/3"


def test_fleet_breakdown_rows_falls_back_to_raw_names() -> None:
    """Design names missing -> fall back to ship/character name, then placeholder."""
    h2h = {
        "summary": _summary(),
        "fleet_breakdown": {
            "player_low": {
                "user_id": 10,
                "total_battles_analyzed": 2,
                "ships": [{"id": 5, "battles": 2, "ship_name": "RawShip", "ship_design_name": None,
                           "avg_level": 0, "avg_power_score": 0}],
                "rooms": [{"id": 7, "battles": 2, "room_design_name": None}],
                "crew": [{"id": 9, "battles": 1, "character_name": None, "character_design_name": None,
                          "avg_level": 0}],
            },
            "player_high": {
                "user_id": 20,
                "total_battles_analyzed": 2,
                "ships": [],
                "rooms": [],
                "crew": [],
            },
        },
    }

    rows = H2HReportTemplate.fleet_breakdown_rows(h2h)
    by_type = {r["Tipo"]: r for r in rows}
    assert by_type["Nave"]["Nombre"] == "RawShip"
    assert by_type["Sala"]["Nombre"] == "Room 7"
    assert by_type["Tripulacion"]["Nombre"] == "Crew 9"
