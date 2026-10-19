"""Unified write surface across report generators (issue #39).

CsvReportGenerator and JsonReportGenerator used to store rows in
``self.data`` while ExcelReportGenerator used ``self._sheets``, so the
three formats had no common write path. They now share the base-class
surface (``add_rows``/``add_sheet`` backed by registration-ordered
``_sheets``); single-table formats flatten every sheet into one table
at generate time, and Excel-specific name validation stays in Excel.
"""

from __future__ import annotations

import csv
import json
from io import StringIO

import pytest

from app.reporting.report_generator import (
    CsvReportGenerator,
    ExcelReportGenerator,
    JsonReportGenerator,
    ReportConfig,
)


def _generator(cls, tmp_path, title="test report"):
    return cls(
        ReportConfig(
            title=title,
            output_path=tmp_path,
            include_timestamp=False,
        )
    )


def test_default_sheet_constant_is_shared_across_formats() -> None:
    for cls in (ExcelReportGenerator, CsvReportGenerator, JsonReportGenerator):
        assert cls.DEFAULT_SHEET == "Data"


def test_csv_accepts_add_sheet_and_flattens_in_registration_order(
    tmp_path,
) -> None:
    gen = _generator(CsvReportGenerator, tmp_path)
    gen.add_sheet("Resumen", [{"id": 1}])
    gen.add_rows([{"id": 2}])

    rows = list(csv.DictReader(StringIO(gen.generate().read_text(encoding="utf-8"))))
    assert rows == [{"id": "1"}, {"id": "2"}]


def test_json_accepts_add_sheet_and_flattens_in_registration_order(
    tmp_path,
) -> None:
    gen = _generator(JsonReportGenerator, tmp_path)
    gen.add_sheet("Resumen", [{"id": 1}])
    gen.add_rows([{"id": 2}])

    data = json.loads(gen.generate().read_text(encoding="utf-8"))
    assert data == [{"id": 1}, {"id": 2}]


def test_csv_add_rows_accumulates_across_calls(tmp_path) -> None:
    """Base contract shared by every format: add_rows appends, never raises."""
    gen = _generator(CsvReportGenerator, tmp_path)
    gen.add_rows([{"id": 1}])
    gen.add_rows([{"id": 2}])

    rows = list(csv.DictReader(StringIO(gen.generate().read_text(encoding="utf-8"))))
    assert [r["id"] for r in rows] == ["1", "2"]


def test_csv_duplicate_sheet_name_raises(tmp_path) -> None:
    gen = _generator(CsvReportGenerator, tmp_path)
    gen.add_sheet("Resumen", [{"id": 1}])
    with pytest.raises(ValueError, match="Resumen"):
        gen.add_sheet("Resumen", [{"id": 2}])


def test_csv_accepts_sheet_names_invalid_for_excel(tmp_path) -> None:
    """Charset/length validation belongs to Excel, not the shared surface."""
    gen = _generator(CsvReportGenerator, tmp_path)
    gen.add_sheet("My[Sheet]:extra", [{"id": 1}])

    rows = list(csv.DictReader(StringIO(gen.generate().read_text(encoding="utf-8"))))
    assert rows == [{"id": "1"}]
