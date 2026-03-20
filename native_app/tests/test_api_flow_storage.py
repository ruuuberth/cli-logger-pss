from __future__ import annotations

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


def test_persists_only_whitelisted_battle_paths() -> None:
    repo = ApiFlowRepository()
    allowed = repo._normalize_event({"path": "/BattleService/GetBattle3?battleId=1"})
    blocked = repo._normalize_event({"path": "/UserService/SearchUsers?name=x"})
    assert repo._should_persist_event(allowed) is True
    assert repo._should_persist_event(blocked) is False


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


def test_room_attributes_include_nested_child_nodes() -> None:
    repo = ApiFlowRepository()
    parsed = {
        "attacker_ship_node": {
            "tag": "Ship",
            "attributes": {"ShipId": "10"},
            "children": [
                {
                    "tag": "Rooms",
                    "children": [
                        {
                            "tag": "Room",
                            "attributes": {"RoomId": "1", "RoomDesignId": "2", "Row": "3", "Column": "4"},
                            "children": [
                                {"tag": "Upgrade", "attributes": {"Level": "5"}},
                            ],
                        }
                    ],
                }
            ],
        },
        "defender_ship_node": {},
    }

    rooms = repo._build_room_rows_for_replay(1, parsed)
    assert rooms
    assert rooms[0].room_attributes_json["Upgrade.Level"] == "5"


def test_character_attributes_include_nested_child_nodes() -> None:
    repo = ApiFlowRepository()
    parsed = {
        "attacker_ship_node": {
            "tag": "Ship",
            "attributes": {"ShipId": "10"},
            "children": [
                {
                    "tag": "Characters",
                    "children": [
                        {
                            "tag": "Character",
                            "attributes": {"CharacterId": "9", "CharacterDesignId": "11"},
                            "children": [
                                {"tag": "Equipment", "attributes": {"Slot": "Helmet"}},
                            ],
                        }
                    ],
                }
            ],
        },
        "defender_ship_node": {},
    }

    characters = repo._build_character_rows_for_replay(1, parsed)
    assert characters
    assert characters[0].character_attributes_json["Equipment.Slot"] == "Helmet"


def test_character_attributes_normalize_character_actions() -> None:
    repo = ApiFlowRepository()
    attrs = {
        "CharacterActions.CharacterAction[0].ActionTypeId": "34",
        "CharacterActions.CharacterAction[0].ConditionTypeId": "405",
        "CharacterActions.CharacterAction[0].CharacterActionId": "119846187",
        "CharacterActions.CharacterAction[0].CharacterActionIndex": "0",
    }
    normalized = repo._normalize_character_attributes(attrs)
    assert "CharacterActionsNormalized" in normalized
    actions = normalized["CharacterActionsNormalized"]
    assert isinstance(actions, list)
    assert actions[0]["action_type_id"] == "34"
    assert actions[0]["condition_type_id"] == "405"


def test_character_attributes_normalize_character_items() -> None:
    repo = ApiFlowRepository()
    attrs = {
        "Items.Item[0].ItemId": "254905515",
        "Items.Item[0].ItemDesignId": "1982",
        "Items.Item[0].Quantity": "1",
        "Items.Item[0].BonusEnhancementType": "Ability",
        "Items.Item[0].BonusEnhancementValue": "13.4",
    }
    normalized = repo._normalize_character_attributes(attrs)
    assert "CharacterItemsNormalized" in normalized
    items = normalized["CharacterItemsNormalized"]
    assert isinstance(items, list)
    assert items[0]["item_design_id"] == "1982"
    assert items[0]["bonus_enhancement_type"] == "Ability"


def test_character_normalization_keeps_backward_compatible_attrs() -> None:
    repo = ApiFlowRepository()
    attrs = {
        "CharacterActions.CharacterAction[0].ActionTypeId": "34",
        "Items.Item[0].ItemDesignId": "1982",
    }
    normalized = repo._normalize_character_attributes(attrs)
    assert normalized["CharacterActions.CharacterAction[0].ActionTypeId"] == "34"
    assert normalized["Items.Item[0].ItemDesignId"] == "1982"


def test_room_attributes_normalize_room_actions() -> None:
    repo = ApiFlowRepository()
    attrs = {
        "RoomActions.RoomAction[0].ActionTypeId": "85",
        "RoomActions.RoomAction[0].ConditionTypeId": "216",
        "RoomActions.RoomAction[0].RoomActionId": "118681236",
        "RoomActions.RoomAction[0].RoomActionIndex": "0",
        "RoomActions.RoomAction[1].ActionTypeId": "55",
        "RoomActions.RoomAction[1].ConditionTypeId": "321",
        "RoomActions.RoomAction[1].RoomActionId": "118681237",
        "RoomActions.RoomAction[1].RoomActionIndex": "1",
    }
    normalized = repo._normalize_room_attributes(attrs)
    assert "RoomActionsNormalized" in normalized
    actions = normalized["RoomActionsNormalized"]
    assert isinstance(actions, list)
    assert actions[0]["action_type_id"] == "85"
    assert actions[0]["condition_type_id"] == "216"


def test_translate_design_name_prefers_es_then_en_then_raw() -> None:
    repo = ApiFlowRepository()
    out = repo._translate_design_name(10, {10: "Nave ES"}, {10: "Ship EN"}, "Raw Name")
    assert out == "Nave ES"

    out = repo._translate_design_name(11, {10: "Nave ES"}, {11: "Ship EN"}, "Raw Name")
    assert out == "Ship EN"

    out = repo._translate_design_name(12, {}, {}, "Raw Name")
    assert out == "Raw Name"


def test_translate_design_name_falls_back_to_id_or_placeholder() -> None:
    repo = ApiFlowRepository()
    out = repo._translate_design_name(42, {}, {}, None)
    assert out == "42"

    out = repo._translate_design_name(None, {}, {}, None)
    assert out == "Sin traduccion"


def test_extracts_es_design_name_when_present() -> None:
    repo = ApiFlowRepository()
    xml = (
        "<DesignService>"
        "<ShipDesign ShipDesignId=\"1\" ShipDesignName=\"Ship EN\" ShipDesignName_ES=\"Nave ES\" />"
        "</DesignService>"
    )
    designs = repo._extract_ship_designs_from_payload(xml)
    assert designs
    assert designs[0]["name"] == "Ship EN"
    assert designs[0]["name_es"] == "Nave ES"


def test_event_integrity_validation_accepts_valid_event_shape() -> None:
    repo = ApiFlowRepository()
    normalized = repo._normalize_event(
        {
            "session_id": "s1",
            "direction": "response",
            "method": "get",
            "host": "api.pixelstarships.com",
            "path": "/BattleService/GetBattle3",
            "status_code": 200,
            "port": 80,
        }
    )

    assert repo._validate_normalized_event(normalized) is True
    assert normalized["method"] == "GET"


def test_event_integrity_validation_rejects_invalid_status_code() -> None:
    repo = ApiFlowRepository()
    normalized = repo._normalize_event(
        {
            "session_id": "s2",
            "direction": "response",
            "method": "GET",
            "host": "api.pixelstarships.com",
            "path": "/BattleService/GetBattle3",
            "status_code": 999,
            "port": 80,
        }
    )

    assert repo._validate_normalized_event(normalized) is False


def test_event_integrity_validation_rejects_missing_location_fields() -> None:
    repo = ApiFlowRepository()
    normalized = repo._normalize_event(
        {
            "session_id": "s3",
            "direction": "response",
            "method": "GET",
            "status_code": 200,
        }
    )

    assert repo._validate_normalized_event(normalized) is False
