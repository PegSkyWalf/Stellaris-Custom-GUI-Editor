"""
图层面板 — 显示控件层级树，支持可见性切换、锁定和 Z 轴排序。
"""
from __future__ import annotations
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton,
    QMenu, QAbstractItemView, QApplication,
)
from PySide6.QtCore import Qt, Signal, QSize, QMimeData
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QPen, QDropEvent, QPalette

from ..core.gui_model import WidgetNode, GUIDocument, WIDGET_COLORS, WIDGET_LABELS
from ..core.theme_manager import ThemeManager
from ..core.i18n import _
from .icon_provider import IconProvider


def _make_dot_icon(color: str, size: int = 14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    c = QColor(color)
    p.setBrush(c)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)
    p.end()
    return QIcon(pm)


class LayerItem(QTreeWidgetItem):
    """Tree item representing one WidgetNode."""
    def __init__(self, node: WidgetNode, parent=None):
        super().__init__(parent)
        self.node = node
        self._is_visible = True
        self._is_locked = False
        self._update_display()

    def _update_display(self):
        is_protected = getattr(self.node, '_protected', False)
        name = self.node.name or self.node.widget_type
        type_short = self.node.widget_type.replace('Type', '').replace('type', '')
        display_name = name
        self.setText(0, display_name)
        self.setText(1, type_short)
        # Use SVG icons for visibility and lock columns
        self.setText(2, '')
        self.setText(3, '')
        vis_icon_name = 'checkbox-on' if self._is_visible else 'checkbox-off'
        lock_icon_name = 'lock' if self._is_locked else 'unlock'
        self.setIcon(2, IconProvider.muted_icon(vis_icon_name, size=14))
        self.setIcon(3, IconProvider.muted_icon(lock_icon_name, size=14))

        if is_protected:
            self.setIcon(0, IconProvider.icon('lock', size=14, color='#c0392b'))
        else:
            color = WIDGET_COLORS.get(self.node.widget_type, '#888')
            self.setIcon(0, _make_dot_icon(color))

        if is_protected:
            self.setForeground(0, QColor('#e67e22'))
        elif not self._is_visible:
            self.setForeground(0, QApplication.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text))
        elif self._is_locked:
            self.setForeground(0, QColor(ThemeManager.muted_color()))
        else:
            self.setForeground(0, QApplication.palette().color(QPalette.ColorRole.Text))

    @property
    def is_visible(self):
        return self._is_visible

    @is_visible.setter
    def is_visible(self, v: bool):
        self._is_visible = v
        self._update_display()

    @property
    def is_locked(self):
        return self._is_locked

    @is_locked.setter
    def is_locked(self, v: bool):
        self._is_locked = v
        self._update_display()


class _LayerTree(QTreeWidget):
    """QTreeWidget subclass that emits structure_changed after drag-drop."""
    structure_changed = Signal()

    def startDrag(self, supportedActions):
        """拖拽前过滤：若父节点也在选中集合中，则取消子节点的选中状态，
        防止 Qt InternalMove 同时移动父节点（含子节点）和子节点本身，
        导致子节点在树中出现两次（复制 bug）。
        同时阻止受保护的原版控件被拖拽。"""
        selected = set(self.selectedItems())
        for item in list(selected):
            # 阻止受保护控件被拖拽移动
            if isinstance(item, LayerItem) and getattr(item.node, '_protected', False):
                item.setSelected(False)
                selected.discard(item)
                continue
            # 若祖先节点也在选中集合中，取消该子节点的选中状态
            parent = item.parent()
            while parent:
                if parent in selected:
                    item.setSelected(False)
                    break
                parent = parent.parent()
        super().startDrag(supportedActions)

    def dropEvent(self, event: QDropEvent):
        super().dropEvent(event)
        self.structure_changed.emit()


class LayerPanel(QWidget):
    """图层面板。"""
    node_selected = Signal(object)          # WidgetNode
    visibility_changed = Signal(object, bool)  # (WidgetNode, is_visible)
    lock_changed = Signal(object, bool)     # (WidgetNode, is_locked)
    order_changed = Signal(object, int)     # (WidgetNode, delta)  delta=-1 or +1
    structure_changed = Signal()            # emitted after drag-drop rearrangement

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[GUIDocument] = None
        self._node_to_item: Dict[int, LayerItem] = {}
        self._last_structure_snapshot: Dict[int, tuple] = {}
        self._last_structure_moves: list = []
        self._updating = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel(_('图层'))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        # Tool row
        btn_row = QHBoxLayout()
        self._up_btn = QPushButton()
        self._up_btn.setIcon(IconProvider.themed_icon('arrow-up', size=16))
        self._up_btn.setFixedWidth(28)
        self._up_btn.setToolTip(_('上移一层'))
        self._up_btn.clicked.connect(lambda: self._move_selection(-1))
        btn_row.addWidget(self._up_btn)

        self._down_btn = QPushButton()
        self._down_btn.setIcon(IconProvider.themed_icon('arrow-down', size=16))
        self._down_btn.setFixedWidth(28)
        self._down_btn.setToolTip(_('下移一层'))
        self._down_btn.clicked.connect(lambda: self._move_selection(1))
        btn_row.addWidget(self._down_btn)

        btn_row.addStretch()

        self._vis_btn = QPushButton()
        self._vis_btn.setIcon(IconProvider.themed_icon('eye', size=16))
        self._vis_btn.setFixedWidth(28)
        self._vis_btn.setToolTip(_('切换可见性'))
        self._vis_btn.clicked.connect(self._toggle_visibility)
        btn_row.addWidget(self._vis_btn)

        self._lock_btn = QPushButton()
        self._lock_btn.setIcon(IconProvider.themed_icon('lock', size=16))
        self._lock_btn.setFixedWidth(28)
        self._lock_btn.setToolTip(_('切换锁定'))
        self._lock_btn.clicked.connect(self._toggle_lock)
        btn_row.addWidget(self._lock_btn)

        layout.addLayout(btn_row)

        # Tree
        self._tree = _LayerTree()
        self._tree.setHeaderLabels([_('名称'), _('类型'), _('显示'), _('锁定')])
        self._tree.setColumnWidth(0, 130)
        self._tree.setColumnWidth(1, 70)
        self._tree.setColumnWidth(2, 30)
        self._tree.setColumnWidth(3, 30)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        # Single-click on col 2/3 toggles visibility/lock
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.structure_changed.connect(self._on_tree_structure_changed)
        layout.addWidget(self._tree)

    def populate(self, doc: Optional[GUIDocument]):
        self._doc = doc
        self._updating = True
        self._tree.clear()
        self._node_to_item.clear()
        if doc:
            for root in reversed(doc.roots):  # reversed so top-most shows first
                self._add_item_tree(root, None)
        self._last_structure_snapshot = self._snapshot_structure()
        self._last_structure_moves = []
        self._updating = False

    def _add_item_tree(self, node: WidgetNode, parent_item: Optional[LayerItem]):
        item = LayerItem(node, parent=parent_item)
        if parent_item is None:
            self._tree.addTopLevelItem(item)
        self._node_to_item[id(node)] = item
        for child in reversed(node.children):
            self._add_item_tree(child, item)
        item.setExpanded(True)

    def select_node(self, node: Optional[WidgetNode]):
        """
        Highlight the tree item for the given node.
        Uses blockSignals to prevent re-entrant selection loops.
        """
        if self._updating:
            return
        self._updating = True
        # Block tree signals so setCurrentItem doesn't trigger _on_selection_changed
        self._tree.blockSignals(True)
        try:
            self._tree.clearSelection()
            if node:
                item = self._node_to_item.get(id(node))
                if item:
                    self._tree.setCurrentItem(item)
                    self._tree.scrollToItem(item)
        finally:
            self._tree.blockSignals(False)
            self._updating = False

    def refresh_icons(self):
        """主题切换后刷新所有按钮图标。"""
        self._up_btn.setIcon(IconProvider.themed_icon('arrow-up', size=16))
        self._down_btn.setIcon(IconProvider.themed_icon('arrow-down', size=16))
        self._vis_btn.setIcon(IconProvider.themed_icon('eye', size=16))
        self._lock_btn.setIcon(IconProvider.themed_icon('lock', size=16))
        # 刷新树中已显示的控件图标
        for item in self._node_to_item.values():
            item._update_display()

    def refresh_item(self, node: WidgetNode):
        """Refresh display of a single item (e.g., after name change)."""
        item = self._node_to_item.get(id(node))
        if item:
            item._update_display()

    def get_visibility(self, node: WidgetNode) -> bool:
        item = self._node_to_item.get(id(node))
        return item.is_visible if item else True

    def get_locked(self, node: WidgetNode) -> bool:
        item = self._node_to_item.get(id(node))
        return item.is_locked if item else False

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        if self._updating:
            return
        items = self._tree.selectedItems()
        if items:
            node = items[0].node if isinstance(items[0], LayerItem) else None
            if node:
                self.node_selected.emit(node)

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        """Single-click toggles visibility (col 2) or lock (col 3)."""
        if not isinstance(item, LayerItem):
            return
        if col == 2:
            self._toggle_visibility_item(item)
        elif col == 3:
            self._toggle_lock_item(item)

    def _on_tree_structure_changed(self):
        """Called after drag-drop rearrangement — sync model to tree."""
        if self._updating or not self._doc:
            return
        self._updating = True
        try:
            self._sync_model_from_tree()
            self.structure_changed.emit()
        finally:
            self._updating = False

    def _sync_model_from_tree(self):
        """Rebuild WidgetNode parent/children from the current tree item order."""
        if not self._doc:
            return
        before = dict(self._last_structure_snapshot)

        def _collect(tree_item: QTreeWidgetItem) -> WidgetNode:
            node: WidgetNode = tree_item.node  # type: ignore[attr-defined]
            node.children = []
            for i in range(tree_item.childCount()):
                child_item = tree_item.child(i)
                child_node = _collect(child_item)
                child_node.parent = node
                node.children.append(child_node)
            node.children.reverse()
            return node

        new_roots = []
        for i in range(self._tree.topLevelItemCount()):
            ti = self._tree.topLevelItem(i)
            node = _collect(ti)
            node.parent = None
            new_roots.append(node)
        # Stellaris tree shows reversed order (top of list = visually on top = rendered last)
        # The populate() call reverses roots when inserting. Reverse back.
        self._doc.roots = list(reversed(new_roots))

        # 拖拽重排后标记所有节点为已修改，确保代码视图重新生成而非保留旧源码
        def _mark_modified(node: WidgetNode):
            node._source_modified = True
            for child in node.children:
                _mark_modified(child)
        for root in self._doc.roots:
            _mark_modified(root)

        after = self._snapshot_structure()
        moves = []
        for node_id, new_info in after.items():
            old_info = before.get(node_id)
            if old_info and old_info != new_info:
                node = self._node_to_item.get(node_id).node if node_id in self._node_to_item else None
                if node is not None:
                    moves.append((node, old_info, new_info))
        self._last_structure_snapshot = after
        self._last_structure_moves = moves

    def _snapshot_structure(self) -> Dict[int, tuple]:
        """Return node id -> (parent id or 0, index) for the current model tree."""
        result: Dict[int, tuple] = {}
        if not self._doc:
            return result

        def _walk(node: WidgetNode, parent_id: int, index: int):
            result[id(node)] = (parent_id, index)
            for child_idx, child in enumerate(node.children):
                _walk(child, id(node), child_idx)

        for root_idx, root in enumerate(self._doc.roots):
            _walk(root, 0, root_idx)
        return result

    def take_last_structure_moves(self) -> list:
        moves = list(self._last_structure_moves)
        self._last_structure_moves = []
        return moves

    def _on_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if not isinstance(item, LayerItem):
            return
        node = item.node
        menu = QMenu(self)
        menu.addAction(_('可见') if not item.is_visible else _('隐藏'),
                       self._toggle_visibility)
        menu.addAction(_('解锁') if item.is_locked else _('锁定'),
                       self._toggle_lock)
        menu.addSeparator()
        menu.addAction(_('上移'), lambda: self._move_selection(-1))
        menu.addAction(_('下移'), lambda: self._move_selection(1))
        menu.addSeparator()
        menu.addAction(_('移到顶层'), lambda: self._move_to_end(node, front=True))
        menu.addAction(_('移到底层'), lambda: self._move_to_end(node, front=False))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _get_selected_layer_item(self) -> Optional[LayerItem]:
        items = self._tree.selectedItems()
        for item in items:
            if isinstance(item, LayerItem):
                return item
        return None

    def _toggle_visibility(self):
        item = self._get_selected_layer_item()
        if item:
            self._toggle_visibility_item(item)

    def _toggle_lock(self):
        item = self._get_selected_layer_item()
        if item:
            self._toggle_lock_item(item)

    def _toggle_visibility_item(self, item: LayerItem):
        item.is_visible = not item.is_visible
        self.visibility_changed.emit(item.node, item.is_visible)

    def _toggle_lock_item(self, item: LayerItem):
        item.is_locked = not item.is_locked
        self.lock_changed.emit(item.node, item.is_locked)

    def _move_selection(self, delta: int):
        item = self._get_selected_layer_item()
        if item:
            self.order_changed.emit(item.node, delta)

    def _move_to_end(self, node: WidgetNode, front: bool):
        """Move node to front (first in list) or back (last in list)."""
        container = node.parent
        doc = self._doc
        if container:
            lst = container.children
        elif doc:
            lst = doc.roots
        else:
            return
        if node in lst:
            lst.remove(node)
            if front:
                lst.append(node)
            else:
                lst.insert(0, node)
            self.order_changed.emit(node, 0)  # 0 = full rebuild
