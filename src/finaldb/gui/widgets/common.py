"""页面通用部件工厂：标题/说明标签、卡片容器、忙指示条、工作区提示。."""

from __future__ import annotations

from PySide2.QtWidgets import QFrame, QLabel, QProgressBar

from finaldb.gui.theme import ThemeManager

__all__ = [
    "busy_bar",
    "caption_label",
    "card",
    "page_title",
    "secondary_label",
    "workspace_hint",
]


def page_title(text: str) -> QLabel:
    """页面大标题标签（粗体大字号）。."""
    label = QLabel(text)
    label.setProperty("pageTitle", True)
    return label


def caption_label(text: str = "") -> QLabel:
    """说明文字标签（次色小字号）。."""
    label = QLabel(text)
    label.setProperty("caption", True)
    return label


def secondary_label(text: str = "") -> QLabel:
    """次要文字标签（次色常规字号）。."""
    label = QLabel(text)
    label.setProperty("secondary", True)
    return label


def card() -> QFrame:
    """卡片容器（圆角 + 边框）。."""
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def busy_bar() -> QProgressBar:
    """忙指示条（不定进度，隐藏态，宽度 80）。"""
    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setFixedWidth(80)
    bar.setTextVisible(False)
    bar.hide()
    return bar


def workspace_hint(_theme: ThemeManager, workspace_ctrl: object, empty_text: str = "未选择工作区") -> QLabel:
    """工作区提示标签：随当前工作区切换自动刷新文本。

    Args:
        _theme: 主题管理器（未直接使用，保持签名一致）
        workspace_ctrl: 工作区控制器（连接 current_changed 信号）
        empty_text: 未选择工作区时的提示文本

    Returns:
        说明文字标签（次色小字号）
    """
    label = caption_label(empty_text)

    def refresh() -> None:
        """按当前工作区刷新提示文本。."""
        name = workspace_ctrl.current_workspace()  # type: ignore[attr-defined]
        label.setText(f"当前工作区: {name}" if name else empty_text)

    workspace_ctrl.current_changed.connect(refresh)  # type: ignore[attr-defined] # pyrefly: ignore [missing-attribute]
    refresh()
    return label
