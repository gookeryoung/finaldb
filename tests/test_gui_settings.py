"""界面设置持久化测试：QSettings 读写、默认值与越界钳位。."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from finaldb.gui.settings import clear_theme_settings, load_theme_settings, save_theme_settings

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _clean_settings() -> Iterator[None]:
    """每个用例前后清空持久化设置，避免跨用例泄漏。."""
    clear_theme_settings()
    yield
    clear_theme_settings()


def test_defaults() -> None:
    """无记录时返回默认浅色/14px。."""
    assert load_theme_settings() == (False, 14)


def test_roundtrip() -> None:
    """保存后读取保持一致。."""
    save_theme_settings(True, 17)
    assert load_theme_settings() == (True, 17)
    save_theme_settings(False, 12)
    assert load_theme_settings() == (False, 12)


def test_font_size_clamped() -> None:
    """字号越界时读取钳位到 12~20。."""
    save_theme_settings(False, 99)
    assert load_theme_settings() == (False, 20)
    save_theme_settings(False, 1)
    assert load_theme_settings() == (False, 12)


def test_clear_resets_to_defaults() -> None:
    """清空后回到默认值。."""
    save_theme_settings(True, 18)
    clear_theme_settings()
    assert load_theme_settings() == (False, 14)
