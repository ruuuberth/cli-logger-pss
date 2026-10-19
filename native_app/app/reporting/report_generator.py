"""Report Generator base class and interfaces"""

from __future__ import annotations

import csv
import json
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _atomic_write(target: Path, write_fn: Callable[[Path], None]) -> Path:
    """Write ``write_fn(tmp)`` and publish atomically with ``os.replace``.

    - temp file lives in ``target.parent`` (same filesystem; required for the
      atomicity of ``os.replace``), never in the system temp dir
    - success: ``os.replace(tmp, target)`` — atomic rename, readers see the
      old or the new file, never a half-written one
    - failure: unlink the temp and re-raise; the destination remains
      byte-identical (if it existed) or absent (if it did not)

    Note: this covers in-process failures (any exception, incl. ``OSError``);
    it does not add fsync durability against OS/power crashes.
    """
    tmp = target.parent / f".{target.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        write_fn(tmp)
        os.replace(tmp, target)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass  # Windows: unlink fails with an open handle; leave the temp
        raise
    return target


def _write_csv_rows(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    """Write CSV rows to ``path`` (DictWriter needs an open file object)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_json_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSON rows to ``path`` (json.dump needs an open file object)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False, default=str)


def _union_headers(rows: list[dict[str, Any]]) -> list[str]:
    """Union of all keys across ``rows``, preserving first-seen order.

    Keys from the first row keep their original order; any new key appearing
    in later rows is appended at first sight. Missing values serialize as
    ``None``/empty, consistent with ``row_data.get(header)`` used by Excel.
    """
    headers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                headers.append(key)
                seen.add(key)
    return headers


_PATH_SEPARATORS = ("/", "\\", os.sep)


def _sanitize_title(title: str) -> str:
    """Sanitize a user-controlled report title into a safe filename base.

    Removes path-traversal components (``..``) and path separators (``/``,
    ``\\``, OS-specific) so the resulting filename can never escape
    ``output_path`` when joined. Spaces are collapsed to ``_`` and the
    result is lowercased, matching the previous behavior for safe titles.
    """
    sanitized = title
    for sep in _PATH_SEPARATORS:
        sanitized = sanitized.replace(sep, "")
    # Collapse any remaining ``..`` segments (e.g. after separator removal)
    while ".." in sanitized:
        sanitized = sanitized.replace("..", "")
    return sanitized.replace(" ", "_").lower()


@dataclass
class ReportConfig:
    """Configuration for report generation"""

    title: str
    output_path: Path
    include_timestamp: bool = True


class ReportGenerator(ABC):
    """Base class for report generators"""

    def __init__(self, config: ReportConfig):
        self.config = config
        self.data: list[dict[str, Any]] = []

    def add_rows(self, rows: list[dict[str, Any]]) -> None:
        """Add rows to the report"""
        self.data.extend(rows)

    @abstractmethod
    def generate(self) -> Path:
        """Generate and save the report. Return the file path."""

    def _get_output_filename(self, extension: str) -> Path:
        """Generate output filename with optional timestamp"""
        timestamp = (
            datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.config.include_timestamp
            else ""
        )
        base_name = _sanitize_title(self.config.title)

        if timestamp:
            filename = f"{base_name}_{timestamp}.{extension}"
        else:
            filename = f"{base_name}.{extension}"

        return self.config.output_path / filename


class ExcelReportGenerator(ReportGenerator):
    """Generate reports in Excel format (.xlsx)"""

    DEFAULT_SHEET = "Data"
    _INVALID_SHEET_CHARS = set("[]:*?/\\")
    _MAX_SHEET_NAME_LENGTH = 31

    def __init__(self, config: ReportConfig):
        super().__init__(config)
        # Single source of truth: sheet name -> rows (insertion-ordered).
        self._sheets: dict[str, list[dict[str, Any]]] = {}

    def add_sheet(self, name: str, rows: list[dict[str, Any]]) -> None:
        """Add rows to a named sheet (created on first call for that name).

        Per-sheet emptiness is the caller's choice: an empty ``rows`` list
        still registers the sheet.
        """
        name = name or self.DEFAULT_SHEET
        if name in self._sheets:
            raise ValueError(f"Ya existe una hoja con el nombre: {name}")
        if len(name) > self._MAX_SHEET_NAME_LENGTH:
            raise ValueError(
                f"Nombre de hoja demasiado largo (máx. {self._MAX_SHEET_NAME_LENGTH} caracteres): {name!r}"
            )
        invalid = sorted(set(name) & self._INVALID_SHEET_CHARS)
        if invalid:
            raise ValueError(
                f"Nombre de hoja contiene caracteres no válidos ({''.join(invalid)}): {name!r}"
            )
        self._sheets[name] = list(rows)

    def add_rows(self, rows: list[dict[str, Any]]) -> None:
        """Add rows to the default sheet, accumulating across calls (#38).

        Matches the base class contract (``self.data.extend``): repeated
        calls append instead of raising. ``add_sheet`` keeps its strict
        duplicate-name error for direct calls.
        """
        if self.DEFAULT_SHEET in self._sheets:
            self._sheets[self.DEFAULT_SHEET].extend(rows)
        else:
            self.add_sheet(self.DEFAULT_SHEET, rows)

    def _write_sheet(self, ws, rows: list[dict[str, Any]]) -> None:
        """Write headers and rows with styling into a worksheet."""
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        if not rows:
            return

        headers = _union_headers(rows)

        # Write headers
        header_fill = PatternFill(
            start_color="4472C4", end_color="4472C4", fill_type="solid"
        )
        header_font = Font(bold=True, color="FFFFFF")

        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Write data rows
        for row_idx, row_data in enumerate(rows, 2):
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=row_data.get(header))
                cell.alignment = Alignment(horizontal="left", vertical="center")

        # Auto-adjust column widths
        for col_idx, header in enumerate(headers, 1):
            max_length = len(str(header))
            for row_data in rows:
                max_length = max(max_length, len(str(row_data.get(header, ""))))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(
                max_length + 2, 50
            )

    def generate(self) -> Path:
        """Generate Excel report (one workbook, one sheet per added dataset)"""
        try:
            from openpyxl import Workbook
        except ImportError:
            raise ImportError(
                "openpyxl no está instalado. Instala con: pip install openpyxl"
            )

        if not any(self._sheets.values()):
            raise ValueError("No hay datos para reportar")

        output_file = self._get_output_filename("xlsx")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Create workbook and drop the default sheet so every sheet is
        # created uniformly via create_sheet (preserves insertion order).
        wb = Workbook()
        default_ws = wb.active
        if default_ws is not None:
            wb.remove(default_ws)
        for name, rows in self._sheets.items():
            ws = wb.create_sheet(name)
            self._write_sheet(ws, rows)

        def _write_xlsx(p: Path) -> None:
            # Save via a file object we own: the ``with`` guarantees the OS
            # handle is closed even if ``wb.save`` raises mid-write. openpyxl
            # leaves its zip archive open on failure, and Windows cannot
            # unlink a file with an open handle, so passing the path would
            # strand the temp file in _atomic_write's cleanup.
            with open(p, "wb") as f:
                wb.save(f)

        return _atomic_write(output_file, _write_xlsx)


class CsvReportGenerator(ReportGenerator):
    """Generate reports in CSV format"""

    def generate(self) -> Path:
        """Generate CSV report"""

        if not self.data:
            raise ValueError("No hay datos para reportar")

        output_file = self._get_output_filename("csv")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Get headers
        headers = _union_headers(self.data)

        # Write CSV (to temp, then publish atomically)
        return _atomic_write(
            output_file, lambda p: _write_csv_rows(p, self.data, headers)
        )


class JsonReportGenerator(ReportGenerator):
    """Generate reports in JSON format"""

    def generate(self) -> Path:
        """Generate JSON report"""

        if not self.data:
            raise ValueError("No hay datos para reportar")

        output_file = self._get_output_filename("json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON (to temp, then publish atomically)
        return _atomic_write(output_file, lambda p: _write_json_rows(p, self.data))
