"""Atomicity tests for report generators (scratch validation of the t_bbf23611 plan).

Property under test: a failed save leaves the destination absent-or-byte-identical
and never leaves temp leftovers. Mirrors the plan's 10-test suite; imports point at
the scratch copy of report_generator.py.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.writer.excel import ExcelWriter

import app.reporting.report_generator as rg
from app.reporting.report_generator import (
    CsvReportGenerator,
    ExcelReportGenerator,
    JsonReportGenerator,
    ReportConfig,
)

ROW = {"Métrica": "Batallas", "Valor": 10}


def _generator(tmp_path, cls=ExcelReportGenerator, title="test report"):
    return cls(
        ReportConfig(
            title=title,
            output_path=tmp_path,
            include_timestamp=False,
        )
    )


def _assert_no_temp_leftovers(d: Path) -> None:
    leftovers = [p.name for p in d.iterdir() if p.name.startswith(".") or ".tmp-" in p.name]
    assert leftovers == [], f"temp leftovers in {d}: {leftovers}"


def _boom_oserror(*args, **kwargs):
    raise OSError(28, "No space left on device")


# ---------------------------------------------------------------- Excel (AC-1/2/3/6/7/8)


def test_save_failure_midwrite_leaves_no_destination_file(tmp_path, monkeypatch):
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    monkeypatch.setattr(ExcelWriter, "write_data", lambda self: _boom_oserror())
    with pytest.raises(OSError):
        gen.generate()
    assert not (tmp_path / "test_report.xlsx").exists()
    assert list(tmp_path.iterdir()) == []


def test_save_failure_midwrite_preserves_previous_report(tmp_path, monkeypatch):
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    dest = gen.generate()  # happy path first, no patch active
    original = dest.read_bytes()

    gen2 = _generator(tmp_path)
    gen2.add_sheet("Resumen", [{"Métrica": "Batallas", "Valor": 999}])
    monkeypatch.setattr(ExcelWriter, "write_data", lambda self: _boom_oserror())
    with pytest.raises(OSError):
        gen2.generate()
    assert dest.exists()
    assert dest.read_bytes() == original
    _assert_no_temp_leftovers(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["test_report.xlsx"]


def test_workbook_save_raises_propagates_after_cleanup(tmp_path, monkeypatch):
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    monkeypatch.setattr("openpyxl.workbook.workbook.Workbook.save", lambda self, fn: _boom_oserror())
    with pytest.raises(OSError):
        gen.generate()
    assert not (tmp_path / "test_report.xlsx").exists()
    assert list(tmp_path.iterdir()) == []


def test_success_path_publishes_valid_workbook(tmp_path):
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    dest = gen.generate()
    assert dest == tmp_path / "test_report.xlsx"
    wb = load_workbook(dest)
    assert wb.sheetnames == ["Resumen"]
    assert wb["Resumen"].cell(row=2, column=2).value == 10
    assert [p.name for p in tmp_path.iterdir()] == ["test_report.xlsx"]


def test_no_temp_leftovers_after_failure(tmp_path, monkeypatch):
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    monkeypatch.setattr(ExcelWriter, "write_data", lambda self: _boom_oserror())
    with pytest.raises(OSError):
        gen.generate()
    assert list(tmp_path.glob(".*")) == []
    assert list(tmp_path.glob("*tmp*")) == []
    assert list(tmp_path.glob("*.part")) == []
    assert list(tmp_path.iterdir()) == []


def test_os_replace_failure_cleans_temp(tmp_path, monkeypatch):
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    monkeypatch.setattr(rg.os, "replace", lambda src, dst: _boom_oserror())
    with pytest.raises(OSError):
        gen.generate()
    assert not (tmp_path / "test_report.xlsx").exists()
    assert list(tmp_path.iterdir()) == []


def test_temp_file_created_in_same_directory(tmp_path, monkeypatch):
    calls = []
    real_replace = os.replace

    def _recording_replace(src, dst):
        calls.append((Path(src), Path(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(rg.os, "replace", _recording_replace)
    gen = _generator(tmp_path)
    gen.add_sheet("Resumen", [ROW])
    dest = gen.generate()
    (src, dst) = calls[0]
    assert src.parent == dst.parent == tmp_path
    assert src.name != dest.name
    assert dest == tmp_path / "test_report.xlsx"


# ---------------------------------------------------------------- CSV (AC-4/8)


def test_csv_failure_midwrite_preserves_destination(tmp_path, monkeypatch):
    gen = _generator(tmp_path, CsvReportGenerator)
    gen.add_rows([{"a": 1, "b": "x"}])
    dest = gen.generate()  # happy path first
    original = dest.read_bytes()
    assert dest.read_text(encoding="utf-8").splitlines()[0] == "a,b"

    def _boom(self, rows):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(csv.DictWriter, "writerows", _boom)
    gen2 = _generator(tmp_path, CsvReportGenerator)
    gen2.add_rows([{"a": 2, "b": "y"}])
    with pytest.raises(OSError):
        gen2.generate()
    assert dest.exists()
    assert dest.read_bytes() == original
    _assert_no_temp_leftovers(tmp_path)
    with pytest.raises(ValueError):
        _generator(tmp_path, CsvReportGenerator).generate()  # AC-8: guard intact


# ---------------------------------------------------------------- JSON (AC-5/8)


def test_json_failure_midwrite_preserves_destination(tmp_path, monkeypatch):
    gen = _generator(tmp_path, JsonReportGenerator)
    gen.add_rows([{"a": 1}])
    dest = gen.generate()  # happy path first
    original = dest.read_bytes()
    assert json.loads(dest.read_text(encoding="utf-8")) == [{"a": 1}]

    monkeypatch.setattr(json, "dump", lambda obj, fh, **kw: _boom_oserror())
    gen2 = _generator(tmp_path, JsonReportGenerator)
    gen2.add_rows([{"a": 2}])
    with pytest.raises(OSError):
        gen2.generate()
    assert dest.exists()
    assert dest.read_bytes() == original
    _assert_no_temp_leftovers(tmp_path)
    with pytest.raises(ValueError):
        _generator(tmp_path, JsonReportGenerator).generate()  # AC-8: guard intact


# ---------------------------------------------------------------- temp naming (AC-6)


def test_unique_temp_names_no_collision(tmp_path, monkeypatch):
    calls = []
    real_replace = os.replace

    def _recording_replace(src, dst):
        calls.append((Path(src), Path(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(rg.os, "replace", _recording_replace)
    gen_a = _generator(tmp_path, title="report a")
    gen_a.add_sheet("Resumen", [ROW])
    gen_b = _generator(tmp_path, title="report b")
    gen_b.add_sheet("Resumen", [ROW])
    dest_a = gen_a.generate()
    dest_b = gen_b.generate()
    assert dest_a != dest_b
    assert len(calls) == 2
    (src1, dst1), (src2, dst2) = calls
    assert src1 != src2
    for src in (src1, src2):
        assert src.name not in {dst1.name, dst2.name}
        assert src.parent == tmp_path


# ---------------------------------------------------------------- caller contract (AC-8, command level)


def test_h2h_command_failing_save_returns_rc1_and_no_partial(tmp_path, monkeypatch):
    from test_excel_report_generator import _h2h_data, _run_h2h_excel
    from openpyxl.writer.excel import ExcelWriter

    monkeypatch.setattr(
        ExcelWriter,
        "write_data",
        lambda self: (_ for _ in ()).throw(OSError(28, "disk full")),
    )
    rc, out_dir = _run_h2h_excel(tmp_path, monkeypatch, _h2h_data(with_fleet=True))
    assert rc == 1
    assert list(out_dir.glob("*.xlsx")) == []  # no partial published
    assert list(out_dir.glob(".*")) == []  # no orphan temp
