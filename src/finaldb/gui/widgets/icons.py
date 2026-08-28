"""矢量图标工厂：加载 assets/icons SVG 资产，随主题色重建。

图标一律来自用户提供的 ``assets/icons/*.svg``；加载时把全部
fill 属性值统一替换为主题色（单色化）后经 QSvgRenderer 渲染，
支持高 DPI。主题切换时以新色值整体重建。
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PySide2.QtCore import QByteArray, QRectF, QSize, Qt
from PySide2.QtGui import QIcon, QPainter, QPixmap
from PySide2.QtSvg import QSvgRenderer

__all__ = ["ICON_NAMES", "build_icon", "icon_size"]

# 绘制网格边长（逻辑像素）
_GRID = 24

# SVG 资产目录
_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"

# 图标名 → SVG 文件名映射（全部来自用户提供的资产）
_ASSET_FILES = {
    "undo": "undo.svg",
    "redo": "redo.svg",
    "add_row": "grid_add_row_after.svg",
    "del_row": "delete_row.svg",
    "add_col": "edit_table_add_column_left.svg",
    "del_col": "delete_column.svg",
    "edit": "edit.svg",
    "rename": "rename.svg",
    "clear_table": "clear.svg",
    "import_data": "diff.svg",
    "preview": "diff.svg",
    "refresh": "refresh.svg",
    "database": "database.svg",
    "stats": "stats.svg",
    "settings": "settings.svg",
    "about": "about.svg",
    "moon": "moon.svg",
    "sun": "sun.svg",
    "question": "question.svg",
    "wash_data": "wash_data.svg",
    "merge_data": "merge_data.svg",
    "cancel": "cancel.svg",
}

# SVG 单色化：把全部 fill 属性值替换为占位符（渲染前换主题色）
_FILL_TOKEN = "__FINALDB_ICON_COLOR__"

# 全部可用图标名（对外只读清单）
ICON_NAMES = tuple(_ASSET_FILES)


@lru_cache(maxsize=64)
def _asset_svg(filename: str) -> str:
    """读取 SVG 文件并单色化（fill 属性统一替换为占位符）。

    结果缓存：文件不变时只读一次；占位符在渲染时替换为主题色。

    :param filename: SVG 文件名（位于 assets/icons）
    :return: 单色化 SVG 文本（空串表示文件缺失）
    """
    svg_file = _ICONS_DIR / filename
    if not svg_file.is_file():
        return ""
    text = svg_file.read_text("utf-8")
    # 单色化：已有 fill 的替换其值；无 fill 的 path 补上
    # （SVG 默认黑色，补占位符后由主题色接管；
    #   负向前瞻确保不重复添加 fill 属性，否则 XML 解析失败）
    text = re.sub(r'fill="[^"]*"', f'fill="{_FILL_TOKEN}"', text)
    text = re.sub(r"fill='[^']*'", f"fill='{_FILL_TOKEN}'", text)
    text = re.sub(r"<path(?![^>]*\bfill=)", f'<path fill="{_FILL_TOKEN}"', text)
    return text


def build_icon(name: str, color: str) -> QIcon:
    """按名称与颜色渲染单色 SVG 资产图标。

    Args:
        name: 图标名（须在 ``ICON_NAMES`` 内）
        color: 十六进制色值（须与所在按钮的文字色一致）

    Returns:
        24x24 逻辑尺寸（2x 物理像素）的 QIcon

    Raises:
        ValueError: 图标名不存在或资产文件缺失时
    """
    filename = _ASSET_FILES.get(name)
    if filename is None:
        raise ValueError(f"未知图标名称: {name}")
    svg_text = _asset_svg(filename)
    if not svg_text:
        raise ValueError(f"图标资产缺失: {name} ({filename})")
    data = QByteArray(svg_text.replace(_FILL_TOKEN, color).encode("utf-8"))
    renderer = QSvgRenderer(data)
    if not renderer.isValid():
        raise ValueError(f"图标资产无法渲染: {name} ({filename})")
    # 2x 物理像素渲染，保证高 DPI 下边缘锐利
    pixmap = QPixmap(_GRID * 2, _GRID * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, _GRID, _GRID))
    painter.end()
    return QIcon(pixmap)


def icon_size() -> QSize:
    """标准图标逻辑尺寸（24x24）。."""
    return QSize(_GRID, _GRID)
