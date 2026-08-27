"""矢量图标工厂：QPainter 绘制工具栏单色图标，随主题色重建。

不依赖外部图标资源（.qrc/图标字体），所有图形在 24x24 网格内
以 2px 圆头笔画绘制；调用方按主题色取色后经 :func:`build_icon`
生成 QIcon，主题切换时以新色值整体重建。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide2.QtCore import QPointF, QRectF, Qt
from PySide2.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

__all__ = ["ICON_NAMES", "build_icon"]

# 绘制网格边长（逻辑像素）与笔画宽度
_GRID = 24
_PEN_WIDTH = 2.0


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


# 图标名 → 绘制函数注册表
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
}

# 全部可用图标名（对外只读清单）
ICON_NAMES = tuple(_PAINTERS)


def build_icon(name: str, color: str) -> QIcon:
    """按名称与颜色绘制单色矢量图标。

    Args:
        name: 图标名（须在 ``ICON_NAMES`` 内）
        color: 十六进制色值（须与所在按钮的文字色一致）

    Returns:
        24x24 逻辑尺寸（2x 物理像素）的 QIcon

    Raises:
        ValueError: 图标名不存在时
    """
    painter_fn = _PAINTERS.get(name)
    if painter_fn is None:
        raise ValueError(f"未知图标名称: {name}")
    # 2x 物理像素绘制，保证高 DPI 下笔画锐利
    pixmap = QPixmap(_GRID * 2, _GRID * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(_pen(color))
    painter_fn(painter)
    painter.end()
    return QIcon(pixmap)
