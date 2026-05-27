"""UI theme helpers removed in CLI migration.

Legacy implementation available at `app.ui.ui_theme_legacy`.
"""

def window_font_qss(selector: str = "QMainWindow") -> str:
    return ""  # no-op for CLI mode
