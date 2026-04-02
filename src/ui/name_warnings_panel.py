"""
名称重复警告面板 — 扫描文档中的重复控件名并支持快速导航。

类似 IDE 的 Problems 面板，列出所有名称冲突，点击可跳转到对应控件。
"""
from __future__ import annotations
from collections import defaultdict
from typing import Optional, List, Tuple, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ..core.theme_manager import ThemeManager
from ..core.i18n import _
from .icon_provider import IconProvider

if TYPE_CHECKING:
    from ..core.gui_model import GUIDocument, WidgetNode


class NameWarningsPanel(QWidget):
    """显示文档中重复名称的警告面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional['GUIDocument'] = None
        self._canvas = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._header = QLabel()
        self._header.setStyleSheet('font-size: 10px; padding: 2px;')
        layout.addWidget(self._header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setIndentation(14)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setStyleSheet("""
            QTreeWidget { border: none; font-size: 10px; }
            QTreeWidget::item { padding: 1px 0; }
        """)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree, 1)

        self._update_header(0)

    def set_doc(self, doc: Optional['GUIDocument']):
        self._doc = doc
        self.refresh()

    def set_canvas(self, canvas):
        self._canvas = canvas

    def refresh(self):
        """重新扫描文档，更新重复名称列表。"""
        self._tree.clear()
        if not self._doc:
            self._update_header(0)
            return

        # 收集所有名称及其所属节点
        name_to_nodes: dict[str, list['WidgetNode']] = defaultdict(list)
        for widget in self._doc.all_widgets():
            name = widget.name
            if name:
                name_to_nodes[name].append(widget)

        # 找出重复名称
        duplicates = {name: nodes for name, nodes in name_to_nodes.items()
                      if len(nodes) > 1}

        if not duplicates:
            self._update_header(0)
            return

        total_issues = 0
        for name in sorted(duplicates.keys()):
            nodes = duplicates[name]
            total_issues += 1

            # 父级项：重复名称
            parent_item = QTreeWidgetItem(self._tree)
            parent_item.setText(0, f'"{name}" — {len(nodes)}' + _(' 处重复'))
            parent_item.setIcon(0, IconProvider.icon('warning', 14, '#f39c12'))
            parent_item.setData(0, Qt.ItemDataRole.UserRole, None)
            parent_item.setExpanded(True)

            # 子项：每个重复实例
            for node in nodes:
                child_item = QTreeWidgetItem(parent_item)
                path = self._node_path(node)
                child_item.setText(0, f'  {path}')
                child_item.setForeground(0, QColor(ThemeManager.muted_color()))
                child_item.setData(0, Qt.ItemDataRole.UserRole, id(node))
                # 存储节点引用用于导航
                child_item.setData(0, Qt.ItemDataRole.UserRole + 1, node)

        self._update_header(total_issues)

    def _update_header(self, count: int):
        if count == 0:
            self._header.setText(_('没有名称冲突'))
            self._header.setStyleSheet(
                f'font-size: 10px; padding: 2px; color: {ThemeManager.muted_color()};')
        else:
            self._header.setText(str(count) + _(' 个名称存在重复'))
            self._header.setStyleSheet(
                'font-size: 10px; padding: 2px; color: #f39c12;')

    def _node_path(self, node: 'WidgetNode') -> str:
        """获取节点在树中的路径，如 'containerA > buttonX'。"""
        parts = []
        current = node
        while current:
            name = current.name or current.widget_type
            parts.append(name)
            current = current.parent
        parts.reverse()
        return ' > '.join(parts)

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        """点击子项时导航到对应控件。"""
        node = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if node is None or not self._canvas:
            return
        scene = self._canvas.gui_scene
        canvas_item = scene.get_item_for_node(node)
        if canvas_item:
            scene.clearSelection()
            canvas_item.setSelected(True)
            self._canvas.centerOn(canvas_item)
