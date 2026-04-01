"""
吸附参考线叠层 — 在画布上绘制虚线对齐参考线。

用于可视化智能吸附引擎检测到的对齐关系。
参考线以主题强调色绘制，拖拽结束后自动隐藏。
"""
from __future__ import annotations

from typing import List

from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor

from ..core.snap_engine import SnapLine


class SnapGuideOverlay(QGraphicsItem):
    """画布上的吸附参考线叠层。

    作为 QGraphicsScene 的顶层 item，绘制当前活跃的吸附参考线。
    设为不可交互，不影响鼠标事件。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._guides: List[SnapLine] = []
        self._color = QColor('#4a9fd4')
        self._pen_width = 1.0
        # 不可选、不可交互
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)
        self.setZValue(99999)  # 最顶层
        self.setVisible(False)
        # 缓存的包围盒
        self._cached_rect = QRectF()

    def set_accent_color(self, color: str):
        """设置参考线颜色（跟随主题强调色）。"""
        self._color = QColor(color)

    def update_guides(self, guides: List[SnapLine]):
        """更新参考线列表并刷新显示。"""
        if not guides and not self._guides:
            return
        self.prepareGeometryChange()
        self._guides = list(guides)
        self._cached_rect = self._compute_rect()
        self.setVisible(bool(self._guides))
        self.update()

    def clear_guides(self):
        """清除所有参考线。"""
        if self._guides:
            self.prepareGeometryChange()
            self._guides.clear()
            self._cached_rect = QRectF()
            self.setVisible(False)
            self.update()

    def boundingRect(self) -> QRectF:
        return self._cached_rect

    def _compute_rect(self) -> QRectF:
        if not self._guides:
            return QRectF()
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        for g in self._guides:
            if g.is_horizontal:
                min_x = min(min_x, g.start)
                max_x = max(max_x, g.end)
                min_y = min(min_y, g.position)
                max_y = max(max_y, g.position)
            else:
                min_x = min(min_x, g.position)
                max_x = max(max_x, g.position)
                min_y = min(min_y, g.start)
                max_y = max(max_y, g.end)
        margin = 2
        return QRectF(min_x - margin, min_y - margin,
                      max_x - min_x + 2 * margin,
                      max_y - min_y + 2 * margin)

    def paint(self, painter: QPainter,
              option: QStyleOptionGraphicsItem,
              widget: QWidget = None):
        if not self._guides:
            return

        pen = QPen(self._color, self._pen_width)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 3])
        pen.setCosmetic(True)  # 不随缩放变粗
        painter.setPen(pen)

        for g in self._guides:
            if g.is_horizontal:
                painter.drawLine(int(g.start), int(g.position),
                                 int(g.end), int(g.position))
            else:
                painter.drawLine(int(g.position), int(g.start),
                                 int(g.position), int(g.end))
