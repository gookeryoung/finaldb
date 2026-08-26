"""主题控制器：将设计令牌暴露给 QML 双向绑定。

所有色值/字号/圆角通过 :class:`ThemeController` 暴露为 ``@Property``，
QML 直接绑定（如 ``color: Theme.colorPrimary``），禁止 QML 侧硬编码色值。
暗色模式由 ``isDark`` 双向驱动，切换时仅 emit ``themeChanged``，QML 绑定
自动刷新。

色值沿用 fuscan 风格：GitHub Desktop（浅色）+ Tokyo Night（深色）。

所有 ``@Property`` 共用 :attr:`themeChanged` 作为 NOTIFY 信号：色值/字号/
圆角本身为常量不变，但 QML 绑定要求属性必须声明 NOTIFY 才能在绑定表达式
中使用（否则报 ``depends on non-NOTIFYable properties`` 警告，且暗色模式
切换时 ``Theme.isDark ? colorA : colorB`` 三元不会重新求值）。
"""

from __future__ import annotations

import sys

from PySide2.QtCore import Property, QObject, Signal, Slot
from PySide2.QtGui import QColor

__all__ = ["ThemeController", "detect_font_families"]


def detect_font_families() -> tuple[str, ...]:
    """按平台返回优先级字体族列表，供 ``QFont.setFamilies()`` 回退使用。

    跨平台最佳实践（Qt 5.13+ ``setFamilies`` 支持自动回退到首个可用字体）：

    - **Windows**：``Microsoft YaHei UI``（Win10+ UI 字体）→
      ``Microsoft YaHei``（Win7 兜底）→ ``Segoe UI`` → ``Arial``
    - **macOS**：``PingFang SC``（苹方）→ ``.AppleSystemUIFont`` →
      ``Helvetica Neue``
    - **Linux**：``Noto Sans CJK SC``（思源黑体）→ ``Source Han Sans SC`` →
      ``Roboto`` → ``DejaVu Sans``

    :return: 字体族优先级列表（首个可用者被采用）
    """
    if sys.platform == "win32":
        return ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial")
    if sys.platform == "darwin":
        return ("PingFang SC", ".AppleSystemUIFont", "Helvetica Neue", "Arial")
    return ("Noto Sans CJK SC", "Source Han Sans SC", "Roboto", "DejaVu Sans")


class ThemeController(QObject):
    """主题令牌控制器：暴露色值/字号/圆角给 QML。

    所有 ``@Property`` 只读，仅 :attr:`isDark` 可通过 :meth:`setDark` 双向
    切换。QML 通过 ``Theme.isDark ? colorA : colorB`` 三元表达式切换深浅色。
    """

    themeChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化主题控制器，默认浅色模式、基准字号 14px。."""
        super().__init__(parent)
        self._dark = False
        self._font_size = 14
        self._min_font_size = 12
        self._font_bold = False

    # ----------------------------- 暗色模式 -----------------------------

    @Property(bool, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def isDark(self) -> bool:
        """当前是否为暗色模式。."""
        return self._dark

    @Property(bool, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def isLight(self) -> bool:
        """当前是否为浅色模式（``not isDark`` 的便捷别名）。."""
        return not self._dark

    @Slot(bool)  # pyrefly: ignore [not-callable]
    def setDark(self, value: bool) -> None:
        """切换暗色模式（QML 通过 ``Theme.setDark(...)`` 调用）。."""
        if self._dark != value:
            self._dark = value
            self.themeChanged.emit()  # pyrefly: ignore [missing-attribute]

    @Slot(int)  # pyrefly: ignore [not-callable]
    def setBaseFontSize(self, size: int) -> None:
        """调整基准字号（12~20px 钳位，QML 设置页滑块调用）。."""
        clamped = max(12, min(20, int(size)))
        if self._font_size != clamped:
            self._font_size = clamped
            self.themeChanged.emit()  # pyrefly: ignore [missing-attribute]

    # ----------------------------- 色彩令牌 -----------------------------

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorPrimary(self) -> QColor:
        """主色（浅色 GitHub 蓝 / 暗色 Tokyo Night 蓝紫）。."""
        return QColor("#7AA2F7") if self._dark else QColor("#0366D6")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorDanger(self) -> QColor:
        """危险色（红）。."""
        return QColor("#D73A49")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorWarning(self) -> QColor:
        """警告色（橙）。."""
        return QColor("#F0883E")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorSuccess(self) -> QColor:
        """成功色（绿）。."""
        return QColor("#28A745")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorTextPrimary(self) -> QColor:
        """主文本色。."""
        return QColor("#E0E0EF") if self._dark else QColor("#24292E")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorTextSecondary(self) -> QColor:
        """次要文本色。."""
        return QColor("#A0A0B0") if self._dark else QColor("#586069")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorTextOnPrimary(self) -> QColor:
        """主色背景上的文本色（白）。."""
        return QColor("#FFFFFF")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorBgApp(self) -> QColor:
        """应用背景色。."""
        return QColor("#1A1B26") if self._dark else QColor("#F5F6F8")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorBgCard(self) -> QColor:
        """卡片背景色。."""
        return QColor("#1E1F2A") if self._dark else QColor("#FFFFFF")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorBgHover(self) -> QColor:
        """hover 背景色。."""
        return QColor("#2A2B3A") if self._dark else QColor("#F6F8FA")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorBgSelected(self) -> QColor:
        """选中态背景色。."""
        return QColor("#2A2B3A") if self._dark else QColor("#EDF3FF")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorBorder(self) -> QColor:
        """边框色。."""
        return QColor("#2E2F3A") if self._dark else QColor("#E1E4E8")

    @Property(QColor, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def colorSidebarDark(self) -> QColor:
        """暗色模式侧栏背景色。."""
        return QColor("#16161E")

    # ----------------------------- 排版令牌 -----------------------------

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontSizeCaption(self) -> int:
        """caption 字号（base - 2，不低于最小字号）。."""
        return max(self._min_font_size, self._font_size - 2)

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontSizeSmall(self) -> int:
        """小字号（base - 1，不低于最小字号）。."""
        return max(self._min_font_size, self._font_size - 1)

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontSizeBody(self) -> int:
        """正文字号（base，默认 14px）。."""
        return self._font_size

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontSizeHeading(self) -> int:
        """标题字号（base + 2，默认 16px）。."""
        return self._font_size + 2

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontSizeTitle(self) -> int:
        """大标题字号（base + 4，默认 18px）。."""
        return self._font_size + 4

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontSizePageTitle(self) -> int:
        """页面大标题字号（base + 8，默认 22px）。."""
        return self._font_size + 8

    @Property(str, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontFamily(self) -> str:
        """主字体族（平台默认字体族首个可用字体名）。."""
        return detect_font_families()[0]

    @Property(bool, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def fontBold(self) -> bool:
        """是否全局加粗。."""
        return self._font_bold

    # ----------------------------- 间距令牌（8px 基准网格） -----------------------------

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def spacingXs(self) -> int:
        """超小间距（4px）。."""
        return 4

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def spacingSm(self) -> int:
        """小间距（8px）。."""
        return 8

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def spacingMd(self) -> int:
        """中间距（16px）。."""
        return 16

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def spacingLg(self) -> int:
        """大间距（24px）。"""
        return 24

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def spacingXl(self) -> int:
        """超大间距（32px）。"""
        return 32

    # ----------------------------- 圆角与尺寸 -----------------------------

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def radiusSm(self) -> int:
        """小圆角（4px）。"""
        return 4

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def radiusMd(self) -> int:
        """中圆角（6px）。"""
        return 6

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def radiusLg(self) -> int:
        """大圆角（8px）。"""
        return 8

    @Property(int, notify=themeChanged)  # pyrefly: ignore [not-callable]
    def sidebarWidth(self) -> int:
        """侧栏宽度（200px）。"""
        return 200
