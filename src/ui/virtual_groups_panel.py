"""
Virtual Groups Panel — independent of the GUI widget tree (Qt Designer style).

Groups can contain widgets from any hierarchy level. Groups can nest.
Persisted in a sidecar .gui.groups.json file.
"""
from __future__ import annotations
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QMenu,
    QInputDialog, QColorDialog, QAbstractItemView, QMessageBox,
    QToolBar, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QAction, QFont

from ..core.virtual_groups import VirtualGroup, VirtualGroupManager
from ..core.gui_model import GUIDocument
from ..core.theme_manager import ThemeManager
from ..core.i18n import _
from .icon_provider import IconProvider


_ROLE_TYPE = Qt.ItemDataRole.UserRole        # 'group' or 'member'
_ROLE_ID   = Qt.ItemDataRole.UserRole + 1   # group id (str) or widget name (str)
_ROLE_GID  = Qt.ItemDataRole.UserRole + 2   # parent group id for member rows


class VirtualGroupsPanel(QWidget):
    """
    Panel for managing virtual, structure-independent widget groups.

    Layout (Qt Designer-inspired):
    ┌──────────────────────────────────────────┐
    │  [📁+] [📁子] [📦选] [重命名] [删除] [眼] | [→组] [←移]  │  ← toolbar
    ├──────────────────────────────────────────┤
    │  Group tree (with member sub-items)       │
    ├──────────────────────────────────────────┤
    │  Search: [___________________] [搜索]     │
    └──────────────────────────────────────────┘
    """

    visibility_changed = Signal()   # a group's visibility was toggled

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager: Optional[VirtualGroupManager] = None
        self._doc: Optional[GUIDocument] = None
        self._canvas = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)

        # ── Toolbar ────────────────────────────────────────────────────
        tb = QToolBar()
        tb.setIconSize(QSize(14, 14))
        tb.setMovable(False)

        self._icon_actions: list[tuple[QAction, str]] = []  # (action, icon_name)

        def _act(label: str, tip: str, slot, icon_name: str = '') -> QAction:
            a = QAction(label, tb)
            a.setToolTip(tip)
            if icon_name:
                a.setIcon(IconProvider.themed_icon(icon_name, size=14))
                self._icon_actions.append((a, icon_name))
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        _act('', _('新建顶层编组'), self._create_root_group, 'folder-plus')
        _act('', _('在当前组内新建子组'), self._create_child_group, 'folder-child')
        _act('', _('将画布选中控件创建为新编组'), self._create_group_from_selection, 'group-from-sel')
        tb.addSeparator()
        _act(_('重命名'), _('重命名当前组'), self._rename_selected)
        _act('', _('删除当前组'), self._delete_selected, 'trash')
        tb.addSeparator()
        _act('', _('切换可见性'), self._toggle_visibility_selected, 'eye')
        tb.addSeparator()
        _act('', _('将画布中选中的控件加入当前编组'), self._add_canvas_selection, 'add-to-group')
        _act('', _('将选中的控件从当前组中移除'), self._remove_canvas_selection, 'remove-from-group')
        layout.addWidget(tb)

        # ── Group tree ─────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setAnimated(True)
        self._tree.setIndentation(14)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.setStyleSheet("""
            QTreeWidget { border: none; font-size: 10px; }
            QTreeWidget::item { padding: 2px 0; }
        """)
        layout.addWidget(self._tree, 1)

        # ── Status bar ─────────────────────────────────────────────────
        self._status = QLabel()
        self._status.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px; padding:2px;')
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_doc(self, doc: Optional[GUIDocument], manager: Optional[VirtualGroupManager]):
        self._doc = doc
        self._manager = manager
        self._rebuild_tree()

    def set_canvas(self, canvas):
        self._canvas = canvas

    def refresh_icons(self):
        """主题切换后刷新工具栏图标和树节点图标。"""
        for action, icon_name in self._icon_actions:
            action.setIcon(IconProvider.themed_icon(icon_name, size=14))
        self._status.setStyleSheet(
            f'color:{ThemeManager.muted_color()}; font-size:9px; padding:2px;')
        self._rebuild_tree()

    def refresh(self):
        self._rebuild_tree()

    # ------------------------------------------------------------------
    # Tree building
    # ------------------------------------------------------------------

    def _rebuild_tree(self):
        self._tree.clear()
        if not self._manager:
            self._status.setText(_('无文档'))
            return
        # 取当前文档的有效控件名集合，用于过滤已删除控件
        valid_names: Optional[set] = None
        if self._canvas:
            scene = getattr(self._canvas, 'gui_scene', None)
            doc = getattr(scene, 'doc', None) if scene else None
            if doc:
                valid_names = {w.name for w in doc.all_widgets()}
        for g in self._manager.groups:
            self._build_group_item(g, parent=None, valid_names=valid_names)
        self._tree.expandAll()
        total = sum(len(g.all_node_names()) for g in self._manager.groups)
        self._status.setText(f'{len(self._manager.groups)} 个顶层组  /  {total} 个控件引用')

    def _build_group_item(self, group: VirtualGroup, parent,
                          valid_names: Optional[set] = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent or self._tree)
        self._update_group_item(item, group)
        # Member rows — skip stale names (widget was deleted)
        for name in group.node_names:
            if valid_names is not None and name not in valid_names:
                continue
            m = QTreeWidgetItem(item)
            m.setText(0, f'  · {name}')
            m.setForeground(0, QColor(ThemeManager.accent_color()))
            m.setData(0, _ROLE_TYPE, 'member')
            m.setData(0, _ROLE_ID,   name)
            m.setData(0, _ROLE_GID,  group.id)
        # Sub-groups
        for child_group in group.children:
            self._build_group_item(child_group, item, valid_names)
        return item

    def _update_group_item(self, item: QTreeWidgetItem, group: VirtualGroup):
        member_count = len(group.node_names)
        child_count  = len(group.children)
        suffix = ''
        if member_count: suffix += f'  [{member_count}]'
        if child_count:  suffix += f'  +{child_count}子'
        item.setText(0, f'{group.name}{suffix}')
        # 使用 SVG 图标代替 emoji 指示可见性，同时叠加颜色标记
        vis_icon_name = 'eye' if group.visible else 'eye-off'
        item.setIcon(0, IconProvider.icon(vis_icon_name, size=14, color=group.color))
        item.setForeground(0, QColor(group.color if group.visible else ThemeManager.muted_color()))
        item.setFont(0, QFont('Microsoft YaHei', 9, QFont.Weight.Medium))
        item.setData(0, _ROLE_TYPE, 'group')
        item.setData(0, _ROLE_ID,   group.id)
        item.setData(0, _ROLE_GID,  None)

    def _find_item_by_gid(self, gid: str) -> Optional[QTreeWidgetItem]:
        def _search(item: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if item.data(0, _ROLE_TYPE) == 'group' and item.data(0, _ROLE_ID) == gid:
                return item
            for i in range(item.childCount()):
                r = _search(item.child(i))
                if r: return r
            return None
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            r = _search(root.child(i))
            if r: return r
        return None

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _current_group(self) -> Optional[VirtualGroup]:
        if not self._manager: return None
        item = self._tree.currentItem()
        if not item: return None
        if item.data(0, _ROLE_TYPE) != 'group': return None
        gid = item.data(0, _ROLE_ID)
        return self._manager.find_by_id(gid) if gid else None

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        role_type = item.data(0, _ROLE_TYPE)
        if role_type == 'member':
            name = item.data(0, _ROLE_ID)
            self._select_widget_by_name(name)
        elif role_type == 'group':
            gid = item.data(0, _ROLE_ID)
            group = self._manager.find_by_id(gid) if self._manager and gid else None
            if group:
                self._status.setText(
                    f'{group.name}  |  {len(group.node_names)} ' + _('个控件') + '  |  '
                    + (_('可见') if group.visible else _('隐藏'))
                )

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        if item.data(0, _ROLE_TYPE) == 'group':
            gid = item.data(0, _ROLE_ID)
            group = self._manager.find_by_id(gid) if self._manager and gid else None
            if group:
                self._rename_group(group, item)

    def _show_context_menu(self, pos):
        if not self._manager: return
        item = self._tree.itemAt(pos)
        menu = QMenu(self)

        if item and item.data(0, _ROLE_TYPE) == 'member':
            name = item.data(0, _ROLE_ID)
            gid  = item.data(0, _ROLE_GID)
            menu.addAction(f'在画布中定位: {name}', lambda: self._select_widget_by_name(name))
            menu.addAction(_('从组中移除'), lambda: self._remove_member(name, gid))
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return

        if item and item.data(0, _ROLE_TYPE) == 'group':
            gid = item.data(0, _ROLE_ID)
            group = self._manager.find_by_id(gid)
            if group:
                menu.addAction(_('重命名'), lambda: self._rename_group(group, item))
                menu.addAction(_('更改颜色'), lambda: self._change_color(group, item))
                menu.addSeparator()
                menu.addAction(_('切换可见性'), lambda: self._toggle_visibility(group, item))
                menu.addAction(_('全选组内控件 (画布)'), lambda: self._select_all_in_group(group))
                menu.addSeparator()
                menu.addAction(_('添加子组'), lambda: self._create_child_group())
                menu.addAction(_('删除组'), lambda: self._delete_group(gid))
        else:
            menu.addAction(_('新建顶层组'), self._create_root_group)
            menu.addAction(_('从选中控件建组'), self._create_group_from_selection)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    def _create_group_from_selection(self):
        """从画布当前选中控件创建新编组。"""
        if not self._manager:
            return
        if not self._canvas:
            QMessageBox.information(self, _('提示'), _('请先打开文件。'))
            return
        nodes = getattr(self._canvas.gui_scene, 'get_selected_nodes', lambda: [])()
        names = [n.name for n in nodes if n.name]
        if not names:
            QMessageBox.information(self, _('提示'), _('请先在画布中选中已命名控件。'))
            return
        default_name = f'编组 ({len(names)}个控件)'
        name, ok = QInputDialog.getText(self, _('从选中控件建组'), _('编组名称:'), text=default_name)
        if not ok or not name.strip():
            return
        group = self._manager.create_group(name.strip())
        self._manager.add_nodes_to_group(group, names)
        self._manager.save()
        self._rebuild_tree()
        self._status.setText(f'已创建编组 [{name.strip()}]，包含 {len(names)} 个控件')

    def _create_root_group(self):
        if not self._manager: return
        name, ok = QInputDialog.getText(self, _('新建编组'), _('编组名称:'), text=_('新编组'))
        if ok and name.strip():
            self._manager.create_group(name.strip())
            self._manager.save()
            self._rebuild_tree()

    def _create_child_group(self):
        parent = self._current_group()
        if not self._manager: return
        if parent is None:
            self._create_root_group()
            return
        name, ok = QInputDialog.getText(self, _('新建子组'), _('子组名称:'), text=_('子组'))
        if ok and name.strip():
            self._manager.create_group(name.strip(), parent)
            self._manager.save()
            self._rebuild_tree()

    def _rename_selected(self):
        group = self._current_group()
        if not group: return
        item = self._find_item_by_gid(group.id)
        if item: self._rename_group(group, item)

    def _rename_group(self, group: VirtualGroup, item: QTreeWidgetItem):
        name, ok = QInputDialog.getText(self, _('重命名'), _('新名称:'), text=group.name)
        if ok and name.strip():
            group.name = name.strip()
            self._update_group_item(item, group)
            if self._manager: self._manager.save()

    def _change_color(self, group: VirtualGroup, item: QTreeWidgetItem):
        color = QColorDialog.getColor(QColor(group.color), self, _('选择颜色'))
        if color.isValid():
            group.color = color.name()
            self._update_group_item(item, group)
            if self._manager: self._manager.save()

    def _delete_selected(self):
        group = self._current_group()
        if not group or not self._manager: return
        self._delete_group(group.id)

    def _delete_group(self, gid: str):
        if not self._manager: return
        ret = QMessageBox.question(self, _('删除编组'), _('确定删除此组？（控件本身不受影响）'))
        if ret == QMessageBox.StandardButton.Yes:
            self._manager.delete_group(gid)
            self._manager.save()
            self._rebuild_tree()

    def _toggle_visibility_selected(self):
        group = self._current_group()
        if not group: return
        item = self._find_item_by_gid(group.id)
        if item: self._toggle_visibility(group, item)

    def _toggle_visibility(self, group: VirtualGroup, item: QTreeWidgetItem):
        group.visible = not group.visible
        self._update_group_item(item, group)
        if self._manager: self._manager.save()
        self.visibility_changed.emit()

    def _remove_member(self, name: str, gid: str):
        if not self._manager: return
        group = self._manager.find_by_id(gid)
        if group:
            self._manager.remove_nodes_from_group(group, [name])
            self._manager.save()
            self._rebuild_tree()

    # ------------------------------------------------------------------
    # Canvas ↔ group link
    # ------------------------------------------------------------------

    def _add_canvas_selection(self):
        group = self._current_group()
        if not self._manager: return
        if group is None:
            QMessageBox.information(self, _('提示'), _('请先选中一个编组。'))
            return
        if not self._canvas: return
        nodes = getattr(self._canvas.gui_scene, 'get_selected_nodes', lambda: [])()
        names = [n.name for n in nodes if n.name]
        if not names:
            QMessageBox.information(self, _('提示'), _('请先在画布中选中已命名控件。'))
            return
        self._manager.add_nodes_to_group(group, names)
        self._manager.save()
        # Rebuild only the affected group item
        item = self._find_item_by_gid(group.id)
        if item:
            # Remove old children and rebuild
            for i in reversed(range(item.childCount())):
                child = item.child(i)
                if child.data(0, _ROLE_TYPE) == 'member':
                    item.removeChild(child)
            for name in group.node_names:
                m = QTreeWidgetItem(item)
                m.setText(0, f'  · {name}')
                m.setForeground(0, QColor(ThemeManager.accent_color()))
                m.setData(0, _ROLE_TYPE, 'member')
                m.setData(0, _ROLE_ID,   name)
                m.setData(0, _ROLE_GID,  group.id)
            self._update_group_item(item, group)
        self._status.setText(f'已添加 {len(names)} 个控件到 [{group.name}]')

    def _remove_canvas_selection(self):
        group = self._current_group()
        if not self._manager or group is None: return
        if not self._canvas: return
        nodes = getattr(self._canvas.gui_scene, 'get_selected_nodes', lambda: [])()
        names = [n.name for n in nodes if n.name]
        if not names: return
        self._manager.remove_nodes_from_group(group, names)
        self._manager.save()
        self._rebuild_tree()
        self._status.setText(f'已从 [{group.name}] 移除 {len(names)} 个控件')

    def _select_all_in_group(self, group: VirtualGroup):
        if not self._canvas or not self._doc: return
        scene = self._canvas.gui_scene
        scene.clearSelection()
        for name in group.all_node_names():
            node = self._doc.find_by_name(name)
            if node:
                item = scene.get_item_for_node(node)
                if item:
                    item.setSelected(True)

    def _select_widget_by_name(self, name: str):
        if not self._canvas or not self._doc: return
        node = self._doc.find_by_name(name)
        if not node: return
        item = self._canvas.gui_scene.get_item_for_node(node)
        if item:
            self._canvas.gui_scene.clearSelection()
            item.setSelected(True)
            self._canvas.centerOn(item)
