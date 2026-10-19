"""Tests for CsvReportGenerator (regression for #29: heterogeneous rows)."""

from __future__ import annotations

import csv
from io import StringIO

from app.reporting.report_generator import CsvReportGenerator, ReportConfig


def _generator(tmp_path, title="test report") -> CsvReportGenerator:
    return CsvReportGenerator(
        ReportConfig(
            title=title,
            output_path=tmp_path,
            include_timestamp=False,
        )
    )


# --- Regression for #29: heterogeneous rows must not crash CSV save ---


def test_csv_heterogeneous_rows_preserve_extra_keys(tmp_path) -> None:
    """Rows with keys absent from the first row must not raise."""
    gen = _generator(tmp_path)
    gen.add_rows(
        [
            {"A": "a1", "B": "b1"},
            {"A": "a2", "B": "b2", "C_extra": "LOST_C"},
            {"A": "a3", "D_extra": "LOST_D"},
        ]
    )
    output_file = gen.generate()

    text = output_file.read_text(encoding="utf-8")
    reader = csv.DictReader(StringIO(text))
    assert reader.fieldnames == ["A", "B", "C_extra", "D_extra"]
    rows = list(reader)
    assert rows[0] == {"A": "a1", "B": "b1", "C_extra": "", "D_extra": ""}
    assert rows[1] == {"A": "a2", "B": "b2", "C_extra": "LOST_C", "D_extra": ""}
    assert rows[2] == {"A": "a3", "B": "", "C_extra": "", "D_extra": "LOST_D"}


def test_csv_homogeneous_rows_unchanged(tmp_path) -> None:
    """Existing homogeneous behavior must be preserved."""
    gen = _generator(tmp_path)
    gen.add_rows([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
    output_file = gen.generate()

    reader = csv.DictReader(StringIO(output_file.read_text(encoding="utf-8")))
    assert reader.fieldnames == ["a", "b"]
    assert list(reader) == [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
