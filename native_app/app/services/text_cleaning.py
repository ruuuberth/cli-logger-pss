"""Pure text/XML cleaning helpers extracted from ApiFlowRepository.

These functions have no DB access and no instance state, so they live outside
the repository class. ApiFlowRepository keeps thin delegating methods for
backwards compatibility with existing callers and tests.
"""

from __future__ import annotations

import json
import unicodedata
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = repair_mojibake_text(normalized)
    normalized = (
        normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    )
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()
    if not normalized:
        return None
    return normalized


def repair_mojibake_text(value: str) -> str:
    text = str(value)
    if not text:
        return text
    suspicious_markers = ("Ã", "Â", "æ", "ç", "ð", "ã", "œ", "š")
    if not any(marker in text for marker in suspicious_markers):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except Exception:
        return text
    return repaired if repaired.strip() else text


def xml_to_clean_dict(node: ET.Element) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for key, value in node.attrib.items():
        decoded_value = normalize_text(unescape(str(value)))
        if (
            decoded_value is not None
            and decoded_value.strip().startswith("<")
            and decoded_value.strip().endswith(">")
        ):
            nested = try_parse_nested_xml(decoded_value)
            attributes[key] = nested if nested is not None else decoded_value
        else:
            attributes[key] = decoded_value

    children = [xml_to_clean_dict(child) for child in list(node)]
    text_value = normalize_text(node.text)
    result: dict[str, Any] = {"tag": node.tag}
    if attributes:
        result["attributes"] = attributes
    if text_value:
        result["text"] = text_value
    if children:
        result["children"] = children
    return result


def try_parse_nested_xml(raw_xml: str) -> dict[str, Any] | None:
    try:
        nested_root = ET.fromstring(raw_xml)
        return xml_to_clean_dict(nested_root)
    except Exception:
        return None


def clean_response_body(response_body_preview: str | None) -> str | None:
    if not response_body_preview:
        return None

    xml_text = str(response_body_preview).strip()
    if not xml_text:
        return None

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return normalize_text(unescape(xml_text))

    cleaned_tree = xml_to_clean_dict(root)
    return normalize_text(json.dumps(cleaned_tree, ensure_ascii=False, indent=2))
