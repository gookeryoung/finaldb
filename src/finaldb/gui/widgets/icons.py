"""矢量图标工厂：QPainter 自绘 + assets/icons SVG 资产加载，随主题色重建。

自绘图标（分页/预览/刷新等通用操作）在 24x24 网格内以 2px 圆头笔画绘制；
SVG 资产图标按 ``assets/icons/*.svg`` 加载：读取 path 数据做单色化替换
（fill 统一为主题色）后经 QSvgRenderer 渲染，支持高 DPI。
两者统一经 :func:`build_icon` 出口，主题切换时以新色值整体重建。
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from PySide2.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide2.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide2.QtSvg import QSvgRenderer

__all__ = ["ICON_NAMES", "build_icon"]

# 绘制网格边长（逻辑像素）与笔画宽度
_GRID = 24
_PEN_WIDTH = 2.0

# SVG 资产目录
_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"

# 资产图标名 → SVG 文件名映射（与自绘图标的用途对应）
_ASSET_FILES = {
    "undo": "undo.svg",
    "redo": "redo.svg",
    "add_row": "grid_add_row_after.svg",
    "del_row": "delete_row.svg",
    "add_col": "edit_table_add_column_left.svg",
    "del_col": "delete_column.svg",
    "rename_col": "edit.svg",
    "clear_table": "clear.svg",
    "import_data": "diff.svg",
    "rename": "rename.svg",
    "refresh": "refresh.svg",
    "database": "database.svg",
    "stats": "stats.svg",
    "settings": "settings.svg",
    "about": "about.svg",
    "moon": "moon.svg",
    "sun": "sun.svg",
    "question": "question.svg",
}

# SVG 单色化：把全部 fill 属性值替换为占位符（渲染前换主题色）
_FILL_TOKEN = "__FINALDB_ICON_COLOR__"


def _pen(color: str) -> QPen:
    """构造统一风格画笔：指定颜色、圆头圆角 2px 笔画。."""
    pen = QPen(QColor(color), _PEN_WIDTH)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _table_top(p: QPainter) -> None:
    """行操作图标的表体：横向表格 + 表头分隔线（占上半区）。."""
    p.drawRoundedRect(QRectF(3, 3, 18, 11), 2, 2)
    p.drawLine(QPointF(3, 8.5), QPointF(21, 8.5))


def _table_left(p: QPainter) -> None:
    """列操作图标的表体：纵向表格 + 竖向分隔线（占左半区）。."""
    p.drawRoundedRect(QRectF(3, 3, 11, 18), 2, 2)
    p.drawLine(QPointF(8.5, 3), QPointF(8.5, 21))


def _plus(p: QPainter, cx: float, cy: float, arm: float = 4.0) -> None:
    """以 (cx, cy) 为中心绘制加号。."""
    p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
    p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))


def _cross(p: QPainter, cx: float, cy: float, arm: float = 3.5) -> None:
    """以 (cx, cy) 为中心绘制 ✕ 叉号。."""
    p.drawLine(QPointF(cx - arm, cy - arm), QPointF(cx + arm, cy + arm))
    p.drawLine(QPointF(cx + arm, cy - arm), QPointF(cx - arm, cy + arm))


def _draw_undo(p: QPainter) -> None:
    """撤销：上半圆弧 + 左向箭头。."""
    p.drawArc(QRectF(4, 7, 12, 12), 0, -180 * 16)
    p.drawLine(QPointF(4, 13), QPointF(8, 9.5))
    p.drawLine(QPointF(4, 13), QPointF(8, 16.5))


def _draw_redo(p: QPainter) -> None:
    """重做：上半圆弧 + 右向箭头。."""
    p.drawArc(QRectF(8, 7, 12, 12), 0, -180 * 16)
    p.drawLine(QPointF(20, 13), QPointF(16, 9.5))
    p.drawLine(QPointF(20, 13), QPointF(16, 16.5))


def _draw_add_row(p: QPainter) -> None:
    """加行：表格 + 下方加号。."""
    _table_top(p)
    _plus(p, 12, 19)


def _draw_del_row(p: QPainter) -> None:
    """删行：表格 + 下方叉号。."""
    _table_top(p)
    _cross(p, 12, 19)


def _draw_add_col(p: QPainter) -> None:
    """加列：表格 + 右侧加号。."""
    _table_left(p)
    _plus(p, 18, 12)


def _draw_del_col(p: QPainter) -> None:
    """删列：表格 + 右侧叉号。."""
    _table_left(p)
    _cross(p, 18, 12)


def _draw_rename_col(p: QPainter) -> None:
    """重命名列：铅笔。."""
    p.drawPolygon(
        QPolygonF(
            [
                QPointF(13.5, 3.5),
                QPointF(20.5, 10.5),
                QPointF(10.5, 20.5),
                QPointF(3.5, 20.5),
                QPointF(3.5, 13.5),
            ]
        )
    )
    # 笔尖分隔线
    p.drawLine(QPointF(6.5, 17.5), QPointF(10.5, 13.5))


def _draw_clear_table(p: QPainter) -> None:
    """清空表：垃圾桶。."""
    p.drawLine(QPointF(9.5, 3), QPointF(14.5, 3))  # 提手
    p.drawLine(QPointF(4, 6), QPointF(20, 6))  # 桶盖
    p.drawPolygon(
        QPolygonF(
            [
                QPointF(6, 9),
                QPointF(18, 9),
                QPointF(17, 21),
                QPointF(7, 21),
            ]
        )
    )
    p.drawLine(QPointF(10, 12), QPointF(10.4, 18))
    p.drawLine(QPointF(14, 12), QPointF(13.6, 18))


def _draw_prev_page(p: QPainter) -> None:
    """上一页：左向折线箭头。."""
    p.drawPolyline(QPolygonF([QPointF(14, 5), QPointF(7, 12), QPointF(14, 19)]))


def _draw_next_page(p: QPainter) -> None:
    """下一页：右向折线箭头。"""
    p.drawPolyline(QPolygonF([QPointF(10, 5), QPointF(17, 12), QPointF(10, 19)]))


def _draw_refresh(p: QPainter) -> None:
    """刷新：环形箭头。."""
    p.drawArc(QRectF(5, 5, 14, 14), 30 * 16, 300 * 16)
    p.drawPolygon(QPolygonF([QPointF(17, 4), QPointF(21, 8), QPointF(16, 9)]))


def _draw_preview(p: QPainter) -> None:
    """预览：放大镜。."""
    p.drawEllipse(QRectF(4, 4, 11, 11))
    p.drawLine(QPointF(13.5, 13.5), QPointF(20, 20))


def _draw_apply(p: QPainter) -> None:
    """应用/执行：勾选圆。."""
    p.drawEllipse(QRectF(4, 4, 16, 16))
    p.drawPolyline(QPolygonF([QPointF(8.5, 12.5), QPointF(11, 15), QPointF(16, 9.5)]))


def _draw_delete(p: QPainter) -> None:
    """删除：叉号圆。."""
    p.drawEllipse(QRectF(4, 4, 16, 16))
    _cross(p, 12, 12, arm=4.0)


def _draw_add(p: QPainter) -> None:
    """新增：加号圆。."""
    p.drawEllipse(QRectF(4, 4, 16, 16))
    _plus(p, 12, 12, arm=4.0)


def _draw_import_data(p: QPainter) -> None:
    """导入：托盘 + 上箭头。."""
    p.drawPolyline(QPolygonF([QPointF(12, 4), QPointF(12, 13), QPointF(8, 9.5), QPointF(12, 13), QPointF(16, 9.5)]))
    p.drawPolyline(QPolygonF([QPointF(4, 15), QPointF(4, 20), QPointF(20, 20), QPointF(20, 15)]))


def _draw_rename(p: QPainter) -> None:
    """重命名：铅笔（与 rename_col 同形）。"""
    _draw_rename_col(p)


def _draw_database(p: QPainter) -> None:
    """数据库：圆柱体（顶面椭圆 + 两侧弧身）。."""
    p.drawEllipse(QRectF(4, 4, 16, 6))
    p.drawArc(QRectF(4, 14, 16, 6), 180 * 16, 180 * 16)
    p.drawLine(QPointF(4, 7), QPointF(4, 17))
    p.drawLine(QPointF(20, 7), QPointF(20, 17))


def _draw_stats(p: QPainter) -> None:
    """统计：三柱条形图。."""
    p.drawLine(QPointF(4, 20), QPointF(20, 20))
    p.drawRect(QRectF(6, 12, 3, 8))
    p.drawRect(QRectF(11, 8, 3, 12))
    p.drawRect(QRectF(16, 4, 3, 16))


def _draw_settings(p: QPainter) -> None:
    """设置：齿轮（外圆 + 齿辐 + 中心孔）。."""
    p.drawEllipse(QRectF(7, 7, 10, 10))
    for _angle in range(0, 360, 45):
        rad = math.radians(_angle)
        cx, cy = 12 + 8 * math.cos(rad), 12 + 8 * math.sin(rad)
        p.drawEllipse(QPointF(cx, cy), 1.6, 1.6)


def _draw_about(p: QPainter) -> None:
    """关于：信息圆（i）。."""
    p.drawEllipse(QRectF(4, 4, 16, 16))
    p.drawPoint(QPointF(12, 8.5))
    p.drawLine(QPointF(12, 11.5), QPointF(12, 16.5))


def _draw_moon(p: QPainter) -> None:
    """月亮：月牙（大圆弧 + 偏移小圆弧）。."""
    p.drawArc(QRectF(5, 4, 15, 16), 30 * 16, 280 * 16)
    p.drawArc(QRectF(2, 4, 15, 16), -60 * 16, 140 * 16)


def _draw_question(p: QPainter) -> None:
    """问号圆：信息圆变体（? 形）。."""
    p.drawEllipse(QRectF(4, 4, 16, 16))
    p.drawArc(QRectF(8.5, 7, 7, 7), 0, -180 * 16)
    p.drawLine(QPointF(12, 14), QPointF(12, 16.5))
    p.drawPoint(QPointF(12, 19))


def _draw_sun(p: QPainter) -> None:
    """太阳：中心圆 + 八向光芒。."""
    p.drawEllipse(QRectF(8, 8, 8, 8))
    for _angle in range(0, 360, 45):
        rad = math.radians(_angle)
        x1, y1 = 12 + 5.5 * math.cos(rad), 12 + 5.5 * math.sin(rad)
        x2, y2 = 12 + 8 * math.cos(rad), 12 + 8 * math.sin(rad)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


# 图标名 → 绘制函数注册表（自绘）
_PAINTERS: dict[str, Callable[[QPainter], None]] = {
    "undo": _draw_undo,
    "redo": _draw_redo,
    "add_row": _draw_add_row,
    "del_row": _draw_del_row,
    "add_col": _draw_add_col,
    "del_col": _draw_del_col,
    "rename_col": _draw_rename_col,
    "clear_table": _draw_clear_table,
    "prev_page": _draw_prev_page,
    "next_page": _draw_next_page,
    "refresh": _draw_refresh,
    "preview": _draw_preview,
    "apply": _draw_apply,
    "delete": _draw_delete,
    "add": _draw_add,
    "import_data": _draw_import_data,
    "rename": _draw_rename,
    "database": _draw_database,
    "stats": _draw_stats,
    "settings": _draw_settings,
    "about": _draw_about,
    "moon": _draw_moon,
    "sun": _draw_sun,
    "question": _draw_question,
}

# 全部可用图标名（对外只读清单）
ICON_NAMES = tuple(_PAINTERS)


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
    # （SVG 默认黑色，补占位符后由主题色接管）
    text = re.sub(r'fill="[^"]*"', f'fill="{_FILL_TOKEN}"', text)
    text = re.sub(r"fill='[^']*'", f"fill='{_FILL_TOKEN}'", text)
    text = text.replace("<path ", f'<path fill="{_FILL_TOKEN}" ')
    return text


def _build_asset_icon(svg_text: str, color: str) -> QIcon:
    """把单色化 SVG 按主题色渲染为图标。

    :param svg_text: 含 fill 占位符的 SVG 文本
    :param color: 十六进制色值
    :return: 渲染后的 QIcon（渲染失败返回空 QIcon）
    """
    data = QByteArray(svg_text.replace(_FILL_TOKEN, color).encode("utf-8"))
    renderer = QSvgRenderer(data)
    if not renderer.isValid():
        return QIcon()
    # 2x 物理像素渲染，保证高 DPI 下边缘锐利
    pixmap = QPixmap(_GRID * 2, _GRID * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, _GRID, _GRID))
    painter.end()
    return QIcon(pixmap)


def build_icon(name: str, color: str) -> QIcon:
    """按名称与颜色生成单色图标（优先 SVG 资产，回退自绘）。

    Args:
        name: 图标名（须在 ``ICON_NAMES`` 内）
        color: 十六进制色值（须与所在按钮的文字色一致）

    Returns:
        24x24 逻辑尺寸（2x 物理像素）的 QIcon

    Raises:
        ValueError: 图标名不存在时
    """
    if name not in _PAINTERS:
        raise ValueError(f"未知图标名称: {name}")
    # 有对应 SVG 资产且渲染成功：走资产渲染（视觉更丰富）
    asset = _ASSET_FILES.get(name)
    if asset is not None:
        svg_text = _asset_svg(asset)
        if svg_text:
            icon = _build_asset_icon(svg_text, color)
            if not icon.isNull():
                return icon
    # 回退：QPainter 自绘
    pixmap = QPixmap(_GRID * 2, _GRID * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(_pen(color))
    _PAINTERS[name](painter)
    painter.end()
    return QIcon(pixmap)


def icon_size() -> QSize:
    """标准图标逻辑尺寸（24x24）。."""
    return QSize(_GRID, _GRID)
