"""Report Generator base class and interfaces"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReportConfig:
    """Configuration for report generation"""
    title: str
    output_path: Path
    include_timestamp: bool = True
    format: str = "excel"  # excel, csv, json


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
        pass

    def _get_output_filename(self, extension: str) -> Path:
        """Generate output filename with optional timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if self.config.include_timestamp else ""
        base_name = self.config.title.replace(" ", "_").lower()
        
        if timestamp:
            filename = f"{base_name}_{timestamp}.{extension}"
        else:
            filename = f"{base_name}.{extension}"
        
        return self.config.output_path / filename


class ExcelReportGenerator(ReportGenerator):
    """Generate reports in Excel format (.xlsx)"""

    DEFAULT_SHEET = "Data"
    _INVALID_SHEET_CHARS = set('[]:*?/\\')
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
            raise ValueError(f"Nombre de hoja contiene caracteres no válidos ({''.join(invalid)}): {name!r}")
        self._sheets.setdefault(name, []).extend(rows)

    def add_rows(self, rows: list[dict[str, Any]]) -> None:
        """Add rows to the default sheet (backward-compatible entry point)."""
        self.add_sheet(self.DEFAULT_SHEET, rows)

    def _write_sheet(self, ws, rows: list[dict[str, Any]]) -> None:
        """Write headers and rows with styling into a worksheet."""
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        if not rows:
            return

        headers = list(rows[0].keys())

        # Write headers
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
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
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_length + 2, 50)

    def generate(self) -> Path:
        """Generate Excel report (one workbook, one sheet per added dataset)"""
        try:
            from openpyxl import Workbook
        except ImportError:
            raise ImportError("openpyxl no está instalado. Instala con: pip install openpyxl")

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

        wb.save(output_file)
        return output_file


class CsvReportGenerator(ReportGenerator):
    """Generate reports in CSV format"""

    def generate(self) -> Path:
        """Generate CSV report"""
        import csv

        if not self.data:
            raise ValueError("No hay datos para reportar")

        output_file = self._get_output_filename("csv")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Get headers
        headers = list(self.data[0].keys()) if self.data else []

        # Write CSV
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(self.data)

        return output_file


class JsonReportGenerator(ReportGenerator):
    """Generate reports in JSON format"""

    def generate(self) -> Path:
        """Generate JSON report"""
        import json

        if not self.data:
            raise ValueError("No hay datos para reportar")

        output_file = self._get_output_filename("json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False, default=str)

        return output_file
