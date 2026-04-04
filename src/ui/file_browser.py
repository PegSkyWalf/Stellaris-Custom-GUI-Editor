"""
文件浏览器面板 — 浏览并打开 GUI 文件。
"""
from __future__ import annotations
import os
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLineEdit, QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QApplication

from ..core.resource_manager import ResourceManager
from ..core.theme_manager import ThemeManager
from ..core.i18n import _
from ..core.logger import get_logger
_log = get_logger('file_browser')


def _reveal_in_explorer(path: str):
    """在系统文件管理器中显示文件/目录（跨平台）。"""
    import sys, subprocess
    if sys.platform == 'win32':
        if os.path.isfile(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
        else:
            os.startfile(os.path.normpath(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', '-R', path] if os.path.isfile(path) else ['open', path])
    else:
        subprocess.Popen(['xdg-open', os.path.dirname(path) if os.path.isfile(path) else path])


class FileBrowser(QWidget):
    """文件浏览器，显示游戏和模组目录的 .gui/.gfx 文件。"""
    open_file_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._game_dir = ''
        self._mod_dir = ''
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel(_('文件浏览器'))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText(_('过滤文件...'))
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tree)

        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton(_('刷新'))
        self._refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self._refresh_btn)
        layout.addLayout(btn_row)

    def set_directories(self, game_dir: str, mod_dir: str):
        self._game_dir = game_dir
        self._mod_dir = mod_dir
        self.refresh()

    def refresh(self):
        self._tree.clear()
        t0 = time.monotonic()

        if self._mod_dir:
            mod_root = QTreeWidgetItem(self._tree,
                [f'[D] 模组: {os.path.basename(self._mod_dir)}'])
            mod_root.setExpanded(True)
            mod_root.setForeground(0, QColor(ThemeManager.accent_color()))
            # 只扫描 interface/ 子目录，避免递归遍历整个模组目录（含大量非 GUI 文件）
            mod_iface = os.path.join(self._mod_dir, 'interface')
            scan_root = mod_iface if os.path.isdir(mod_iface) else self._mod_dir
            _log.debug("文件浏览器扫描目录: %s", scan_root)
            self._add_directory_tree(
                mod_root, scan_root,
                filter_ext={'.gui', '.guicore', '.gfx', '.gfxcore'}
            )

        if self._game_dir:
            iface = os.path.join(self._game_dir, 'interface')
            if os.path.isdir(iface):
                game_root = QTreeWidgetItem(self._tree, [_('[D] 原版: interface')])
                game_root.setForeground(0, QColor(ThemeManager.muted_color()))
                self._add_directory_tree(game_root, iface,
                    filter_ext={'.gui', '.gfx'})

        _log.debug("文件浏览器刷新完成，耗时 %.3fs", time.monotonic() - t0)

    def _add_directory_tree(self, parent_item: QTreeWidgetItem, dir_path: str, filter_ext=None):
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return

        dirs, files = [], []
        for entry in entries:
            full = os.path.join(dir_path, entry)
            if os.path.isdir(full):
                dirs.append((entry, full))
            elif os.path.isfile(full):
                ext = os.path.splitext(entry)[1].lower()
                if filter_ext is None or ext in filter_ext:
                    files.append((entry, full))

        for name, full in dirs:
            di = QTreeWidgetItem(parent_item, [f'[D] {name}'])
            di.setData(0, Qt.ItemDataRole.UserRole, full)
            self._add_directory_tree(di, full, filter_ext)
            if di.childCount() == 0:
                parent_item.removeChild(di)

        for name, full in files:
            ext = os.path.splitext(name)[1].lower()
            icon = '[G]' if ext in ('.gui', '.guicore') else '[F]'
            fi = QTreeWidgetItem(parent_item, [f'{icon} {name}'])
            fi.setData(0, Qt.ItemDataRole.UserRole, full)
            if ext in ('.gui', '.guicore'):
                fi.setForeground(0, QColor('#c3e88d'))
            else:
                fi.setForeground(0, QColor('#f78c6c'))

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.gui', '.guicore'):
                self.open_file_requested.emit(path)

    def _on_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        menu = QMenu(self)
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.gui', '.guicore'):
                menu.addAction(_('在编辑器中打开')).triggered.connect(
                    lambda: self.open_file_requested.emit(path))
            menu.addAction(_('在资源管理器中显示')).triggered.connect(
                lambda: _reveal_in_explorer(path))
        elif os.path.isdir(path):
            menu.addAction(_('在资源管理器中打开')).triggered.connect(
                lambda: _reveal_in_explorer(path))
        menu.addSeparator()
        menu.addAction(_('复制路径')).triggered.connect(
            lambda: QApplication.clipboard().setText(path))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _filter(self, text: str):
        text = text.lower()
        def _fi(item: QTreeWidgetItem):
            if item.childCount() == 0:
                item.setHidden(bool(text) and text not in item.text(0).lower())
            else:
                any_vis = False
                for i in range(item.childCount()):
                    _fi(item.child(i))
                    if not item.child(i).isHidden():
                        any_vis = True
                item.setHidden(not any_vis)
                if any_vis:
                    item.setExpanded(True)
        for i in range(self._tree.topLevelItemCount()):
            _fi(self._tree.topLevelItem(i))
