from __future__ import annotations

APP_FONT_STACK = (
    "'Noto Sans', 'Noto Sans CJK SC', 'Noto Sans Arabic', 'Noto Sans JP', "
    "'Noto Sans KR', 'Segoe UI', 'Arial Unicode MS', 'DejaVu Sans', sans-serif"
)


def window_font_qss(selector: str = "QMainWindow") -> str:
    return f"{selector} {{ font-family: {APP_FONT_STACK}; }}"
