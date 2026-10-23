from __future__ import annotations

import json

from app.services.text_cleaning import (
    clean_response_body,
    normalize_text,
    repair_mojibake_text,
    try_parse_nested_xml,
    xml_to_clean_dict,
)


def test_normalize_text_repairs_common_mojibake() -> None:
    assert normalize_text("æ¢¦ç\x86\x8a1") == "梦熊1"
    assert normalize_text("ç\x9a®ç\x9a®030") == "皮皮030"


def test_normalize_text_returns_none_for_empty_values() -> None:
    assert normalize_text(None) is None
    assert normalize_text("") is None
    assert normalize_text("   \n  ") is None


def test_normalize_text_strips_trailing_space_per_line() -> None:
    assert normalize_text("  hola\r\nmundo  ") == "hola\nmundo"
    assert normalize_text("a\x00b") == "ab"


def test_repair_mojibake_text_leaves_clean_text_untouched() -> None:
    assert repair_mojibake_text("plain ascii") == "plain ascii"
    assert repair_mojibake_text("") == ""


def test_clean_response_body_parses_xml_into_tree() -> None:
    cleaned = clean_response_body('<Battle><Room RoomId="1" RoomName="Lab"/></Battle>')
    assert cleaned is not None
    tree = json.loads(cleaned)
    assert tree["tag"] == "Battle"
    assert tree["children"][0]["attributes"]["RoomId"] == "1"


def test_clean_response_body_falls_back_to_text_for_invalid_xml() -> None:
    assert clean_response_body("plain text & entity") == "plain text & entity"


def test_clean_response_body_returns_none_for_empty_input() -> None:
    assert clean_response_body(None) is None
    assert clean_response_body("") is None
    assert clean_response_body("   ") is None


def test_try_parse_nested_xml_returns_none_on_invalid_xml() -> None:
    assert try_parse_nested_xml("<not closed") is None


def test_xml_to_clean_dict_extracts_nested_xml_attributes() -> None:
    import xml.etree.ElementTree as ET

    # El XML anidado llega como entidad escapada en el valor del atributo
    node = ET.fromstring("<a b='&lt;c d=&quot;1&quot;/&gt;'/>")
    result = xml_to_clean_dict(node)
    assert result["attributes"]["b"]["attributes"]["d"] == "1"
