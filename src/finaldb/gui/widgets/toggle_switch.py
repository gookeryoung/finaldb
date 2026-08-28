"""滑动开关控件：明暗主题等布尔切换的动画 Toggle。."""

from __future__ import annotations

from PySide2.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide2.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide2.QtWidgets import QWidget

from finaldb.gui.theme import ThemeManager

__all__ = ["ToggleSwitch"]

# 开关几何（逻辑像素）
_WIDTH = 40
_HEIGHT = 22
_KNOB = 16  # 滑块直径
_PAD = 3  # 轨道内边距


class ToggleSwitch(QWidget):
    """iOS 风格滑动开关：轨道 + 圆形滑块，切换带滑动动画。

    选中态轨道取主题主色；未选中取边框色。主题切换时
    自动重绘。经 ``toggled`` 信号通知状态变化。
    """

    toggled = Signal(bool)

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """初始化开关（默认未选中）。

        Args:
            theme: 主题管理器（轨道颜色随主题）
            parent: 父部件
        """
        super().__init__(parent)
        self._theme = theme
        self._checked = False
        self._pos = 0.0  # 滑块位置 0.0(左)~1.0(右)，动画驱动
        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(QSize(_WIDTH, _HEIGHT))
        theme.theme_changed.connect(self.update)  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 对外 API -----------------------------

    def is_checked(self) -> bool:
        """当前开关状态。."""
        return self._checked

    def set_checked(self, checked: bool, animate: bool = True) -> None:
        """设置开关状态（可选动画），不发射 toggled。."""
        if checked == self._checked:
            return
        self._checked = checked
        self._animate_to(1.0 if checked else 0.0, animate)

    # ----------------------------- 属性（动画驱动） -----------------------------

    def _get_knob_pos(self) -> float:
        """滑块位置（0.0~1.0）。."""
        return self._pos

    def _set_knob_pos(self, pos: float) -> None:
        """设置滑块位置并重绘（QPropertyAnimation 回调）。."""
        self._pos = pos
        self.update()

    knobPos = Property(float, _get_knob_pos, _set_knob_pos)

    # ----------------------------- 交互 -----------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """点击任意位置切换状态。."""
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self._animate_to(1.0 if self._checked else 0.0, True)
            self.toggled.emit(self._checked)  # pyrefly: ignore [missing-attribute]
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002  # 与父类签名参数名保持一致
        """绘制轨道与滑块（颜色按状态与主题）。."""
        palette = self._theme.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 轨道
        track_color = QColor(palette["primary"]) if self._checked else QColor(palette["border"])
        rect = QRectF(0, 0, _WIDTH, _HEIGHT)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, _HEIGHT / 2, _HEIGHT / 2)
        # 未选中时轨道内侧描边增强可见性
        if not self._checked:
            painter.setPen(QPen(QColor(palette["text_secondary"]), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), _HEIGHT / 2 - 0.5, _HEIGHT / 2 - 0.5)
            painter.setPen(Qt.NoPen)
        # 滑块
        x = _PAD + self._pos * (_WIDTH - _KNOB - 2 * _PAD)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, (_HEIGHT - _KNOB) / 2, _KNOB, _KNOB))
        painter.end()

    # ----------------------------- 内部 -----------------------------

    def _animate_to(self, target: float, animate: bool) -> None:
        """滑块滑动到目标位置（无动画时直接落位）。."""
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._pos = target
            self.update()
