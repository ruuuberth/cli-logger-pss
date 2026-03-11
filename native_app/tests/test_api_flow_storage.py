from __future__ import annotations

import base64
import gzip
import json

from app.services.api_flow_storage import ApiFlowRepository


def test_redacts_sensitive_headers() -> None:
    repo = ApiFlowRepository()
    headers = {
        "Authorization": "Bearer abc",
        "Cookie": "session=x",
        "Content-Type": "application/json",
    }
    redacted = repo._redact_headers(headers)
    assert redacted["Authorization"] == "***REDACTED***"
    assert redacted["Cookie"] == "***REDACTED***"
    assert redacted["Content-Type"] == "application/json"


def test_truncate_body_uses_config_limit() -> None:
    repo = ApiFlowRepository()
    long_body = "x" * (repo.body_max_chars + 50)
    out = repo._truncate(long_body)
    assert out is not None
    assert out.endswith("...")
    assert len(out) == repo.body_max_chars + 3


def test_parse_datetime_handles_z_suffix() -> None:
    repo = ApiFlowRepository()
    parsed = repo._parse_datetime("2026-02-20T10:00:00Z")
    assert parsed is not None
    assert parsed.isoformat().startswith("2026-02-20T10:00:00")


def test_extracts_normalized_attacker_name_from_battle_xml() -> None:
    repo = ApiFlowRepository()
    event = {
        "path": "/BattleService/GetBattle3?battleId=1",
        "response_body_preview": (
            '<BattleService><GetBattle><Battle '
            'AttackingShipXml="&lt;Ship ShipName=&quot;  Ruuuberth4  &quot; /&gt;" /></GetBattle></BattleService>'
        ),
    }
    normalized = repo._normalize_event(event)
    assert "attacker_name" not in normalized


def test_keeps_full_response_body_preview_without_truncation() -> None:
    repo = ApiFlowRepository()
    very_long_body = "x" * (repo.body_max_chars + 500)
    normalized = repo._normalize_event({"response_body_preview": very_long_body})
    assert normalized["response_body_preview"] == very_long_body


def test_generates_cleaned_response_body_for_developer_readability() -> None:
    repo = ApiFlowRepository()
    raw_xml = (
        '<BattleService><GetBattle><Battle '
        'AttackingShipXml="&lt;Ship ShipName=&quot;Ruuuberth4&quot; /&gt;" '
        'BattleId="123" /></GetBattle></BattleService>'
    )
    normalized = repo._normalize_event({"response_body_preview": raw_xml})

    assert normalized["response_body_preview"] == raw_xml
    assert normalized["response_body_cleaned"] is not None

    cleaned = json.loads(normalized["response_body_cleaned"])
    assert cleaned["tag"] == "BattleService"
    battle_node = cleaned["children"][0]["children"][0]
    assert battle_node["attributes"]["BattleId"] == "123"
    assert battle_node["attributes"]["AttackingShipXml"]["attributes"]["ShipName"] == "Ruuuberth4"


def test_extracts_normalized_battle_payload_from_cleaned() -> None:
    repo = ApiFlowRepository()
    cleaned_payload = json.dumps(
        {
            "tag": "BattleService",
            "children": [
                {
                    "tag": "GetBattle",
                    "children": [
                        {
                            "tag": "Battle",
                            "attributes": {
                                "BattleId": "2",
                                "AttackingShipId": "8657106",
                                "DefendingShipId": "8761013",
                                "OutcomeType": "Attacker Won",
                                "ClientOutcomeType": "Attacker Won",
                                "WinTrophyResult": "15",
                                "WinMineralsResult": "0",
                                "WinGasResult": "0",
                                "LoseTrophyResult": "0",
                                "LoseMineralsResult": "0",
                                "LoseGasResult": "0",
                                "BattleEndFrame": "0",
                                "ClientEndFrame": "1215",
                                "AttackingUserXml": {
                                    "tag": "User",
                                    "attributes": {"Id": "11342404", "Name": "lord stella", "Trophy": "5327"},
                                },
                                "DefendingUserXml": {
                                    "tag": "User",
                                    "attributes": {"Id": "11483762", "Name": "Ruuuberth4", "Trophy": "5023"},
                                },
                                "AttackingShipXml": {
                                    "tag": "Ship",
                                    "attributes": {"ShipName": " 2Trick "},
                                }
                            },
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )
    normalized = repo._extract_battle_replay_normalized_from_cleaned(cleaned_payload)
    assert normalized is not None
    assert normalized["battle_id"] == 2
    assert normalized["attacking_ship_id"] == 8657106
    assert normalized["defending_ship_id"] == 8761013
    assert normalized["attacker_name"] == "lord stella"
    assert normalized["defender_name"] == "Ruuuberth4"
    assert normalized["win_trophy_result"] == 15


def test_extracts_child_entities_from_cleaned_payload() -> None:
    repo = ApiFlowRepository()
    cleaned_payload = json.dumps(
        {
            "tag": "BattleService",
            "children": [
                {
                    "tag": "GetBattle",
                    "children": [
                        {
                            "tag": "Battle",
                            "attributes": {
                                "BattleId": "2",
                                "AttackingShipXml": {
                                    "tag": "Ship",
                                    "attributes": {
                                        "ShipId": "10",
                                        "ShipDesignId": "200",
                                        "ShipName": "AttackerShip",
                                        "ShipLevel": "12",
                                        "PowerScore": "1111",
                                        "Hp": "40.5",
                                        "ShipStatus": "Offline",
                                    },
                                    "children": [
                                        {
                                            "tag": "Rooms",
                                            "children": [
                                                {
                                                    "tag": "Room",
                                                    "attributes": {
                                                        "RoomId": "501",
                                                        "RoomDesignId": "700",
                                                        "ShipId": "10",
                                                        "Row": "20",
                                                        "Column": "40",
                                                        "RoomStatus": "Normal",
                                                    },
                                                }
                                            ],
                                        },
                                        {
                                            "tag": "Characters",
                                            "children": [
                                                {
                                                    "tag": "Character",
                                                    "attributes": {
                                                        "CharacterId": "9001",
                                                        "ShipId": "10",
                                                        "CharacterDesignId": "300",
                                                        "CharacterName": "Crew A",
                                                        "Level": "40",
                                                        "Xp": "1000",
                                                    },
                                                }
                                            ],
                                        },
                                    ],
                                },
                                "DefendingShipXml": {
                                    "tag": "Ship",
                                    "attributes": {
                                        "ShipId": "11",
                                        "ShipDesignId": "201",
                                        "ShipName": "DefenderShip",
                                    },
                                    "children": [],
                                },
                                "Commands": {
                                    "tag": "UserCommands",
                                    "children": [
                                        {
                                            "tag": "Commands",
                                            "children": [
                                                {
                                                    "tag": "Command",
                                                    "attributes": {
                                                        "UserId": "123",
                                                        "ShipId": "10",
                                                        "RoomId": "501",
                                                        "CharacterId": "9001",
                                                    },
                                                }
                                            ],
                                        }
                                    ],
                                },
                            },
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )

    parsed = repo._extract_battle_nodes_from_cleaned(cleaned_payload)
    assert parsed is not None

    ships = repo._build_ship_rows_for_replay(1, parsed)
    rooms = repo._build_room_rows_for_replay(1, parsed)
    characters = repo._build_character_rows_for_replay(1, parsed)
    commands = repo._build_command_rows_for_replay(1, parsed)

    assert len(ships) == 2
    assert len(rooms) == 1
    assert len(characters) == 1
    assert len(commands) == 1
    assert ships[0].ship_id == 10
    assert rooms[0].room_id == 501
    assert characters[0].character_id == 9001
    assert commands[0].user_id == 123


def test_build_ship_rows_adds_fallback_when_defender_ship_xml_is_missing() -> None:
    repo = ApiFlowRepository()
    cleaned_payload = json.dumps(
        {
            "tag": "BattleService",
            "children": [
                {
                    "tag": "GetBattle",
                    "children": [
                        {
                            "tag": "Battle",
                            "attributes": {
                                "BattleId": "2",
                                "AttackingShipId": "10",
                                "DefendingShipId": "11",
                                "AttackingShipXml": {
                                    "tag": "Ship",
                                    "attributes": {
                                        "ShipId": "10",
                                        "ShipDesignId": "200",
                                        "ShipName": "AttackerShip",
                                    },
                                },
                            },
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )
    parsed = repo._extract_battle_nodes_from_cleaned(cleaned_payload)
    assert parsed is not None

    ships = repo._build_ship_rows_for_replay(1, parsed)

    assert len(ships) == 2
    sides = {ship.side for ship in ships}
    assert sides == {"attacker", "defender"}
    defender = [ship for ship in ships if ship.side == "defender"][0]
    assert defender.ship_id == 11


def test_extracts_ship_designs_from_compressed_static_design_payload() -> None:
    repo = ApiFlowRepository()
    xml_payload = (
        '<DesignService><ListAllStaticDesigns><ShipDesigns version="1">'
        '<ShipDesign ShipDesignId="292" ShipDesignName="Interceptor" ShipDescription="Desc A" ShipType="TypeA" ShipLevel="4" Hp="55" Rows="10" Columns="20" />'
        '<ShipDesign ShipDesignId="293" ShipDesignName="Defender" ShipDescription="Desc B" ShipType="TypeB" ShipLevel="5" Hp="60" Rows="11" Columns="21" />'
        '</ShipDesigns><RoomDesigns version="1">'
        '<RoomDesign RoomDesignId="101" RoomName="Laser" RoomDescription="Desc Room" RoomType="Weapon" MinShipLevel="5" Capacity="3" PowerUse="2" />'
        '</RoomDesigns><CharacterDesigns version="1">'
        '<CharacterDesign CharacterDesignId="901" CharacterDesignName="CrewOne" CharacterDesignDescription="Desc Crew" RaceType="Human" CharacterType="Hero" Hp="100" Attack="12" FireResistance="3" />'
        "</CharacterDesigns></ListAllStaticDesigns></DesignService>"
    )
    encoded = base64.b64encode(gzip.compress(xml_payload.encode("utf-8"))).decode("ascii")

    ship_designs = repo._extract_ship_designs_from_payload(encoded)
    room_designs = repo._extract_room_designs_from_payload(encoded)
    character_designs = repo._extract_character_designs_from_payload(encoded)

    assert len(ship_designs) == 2
    assert ship_designs[0]["ship_design_id"] == 292
    assert ship_designs[0]["name"] == "Interceptor"
    assert ship_designs[0]["class_type"] == "TypeA"
    assert ship_designs[1]["ship_design_id"] == 293
    assert len(room_designs) == 1
    assert room_designs[0]["room_design_id"] == 101
    assert room_designs[0]["name"] == "Laser"
    assert len(character_designs) == 1
    assert character_designs[0]["crew_design_id"] == 901
    assert character_designs[0]["name"] == "CrewOne"


def test_design_decoder_accepts_wrapped_base64_payload() -> None:
    repo = ApiFlowRepository()
    xml_payload = (
        '<DesignService><ListAllStaticDesigns><ShipDesigns version="1">'
        '<ShipDesign ShipDesignId="292" ShipDesignName="Interceptor" />'
        "</ShipDesigns></ListAllStaticDesigns></DesignService>"
    )
    encoded = base64.b64encode(gzip.compress(xml_payload.encode("utf-8"))).decode("ascii")
    wrapped = "\n".join(encoded[i : i + 64] for i in range(0, len(encoded), 64))

    ship_designs = repo._extract_ship_designs_from_payload(wrapped)

    assert len(ship_designs) == 1
    assert ship_designs[0]["ship_design_id"] == 292
