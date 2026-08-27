"""状态浮层：页面顶部居中的临时消息提示（成功/错误）。."""

from __future__ import annotations

from PySide2.QtCore import QEvent, QObject, Qt, QTimer
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QLabel, QWidget

from finaldb.gui.theme import ThemeManager

__all__ = ["Toast"]

# 浮层自动隐藏延时（毫秒）
_HIDE_DELAY_MS = 3200


class Toast(QLabel):
    """页面顶部居中的状态浮层（仿 QML 版 statusToast）。

    用法：页面持有实例，控制器信号触发 ``show_message``；
    浮层随父部件 resize 自动重新居中。
    """

    def __init__(self, parent: QWidget, theme: ThemeManager) -> None:
        """初始化浮层（默认隐藏）。

        Args:
            parent: 宿主页面（浮层覆盖其顶部居中位置）
            theme: 主题管理器（取成功/危险色）
        """
        super().__init__(parent)
        self._theme = theme
        self.setVisible(False)
        self.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPixelSize(theme.font_size_small())
        self.setFont(font)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_HIDE_DELAY_MS)
        self._timer.timeout.connect(self.hide)
        # 父部件缩放时保持居中
        parent.installEventFilter(self)

    def show_message(self, message: str, is_error: bool = False) -> None:
        """显示一条状态消息（3.2 秒后自动隐藏）。

        Args:
            message: 消息文本
            is_error: True 用危险色（红），False 用成功色（绿）
        """
        color = self._theme.color("danger" if is_error else "success")
        self.setText(message)
        self.setStyleSheet(f"background-color: {color}; color: #FFFFFF; border-radius: 4px; padding: 4px 16px;")
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start()

    def show_error(self, message: str) -> None:
        """以错误样式显示一条状态消息（供信号直接连接）。."""
        self.show_message(message, is_error=True)

    def _reposition(self) -> None:
        """移动到父部件顶部居中。."""
        parent = self.parentWidget()
        if parent is not None:
            x = max(8, (parent.width() - self.width()) // 2)
            self.move(x, 8)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """父部件 resize 时重新居中浮层。."""
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(watched, event)
