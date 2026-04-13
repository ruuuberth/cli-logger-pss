from __future__ import annotations

from app.core.build_info import get_build_info


def test_build_info_has_display_label() -> None:
    info = get_build_info()
    assert info.version
    assert info.git_sha
    assert "(" in info.display_label
    assert ")" in info.display_label
