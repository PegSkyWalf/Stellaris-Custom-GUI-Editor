"""
Button Effects Editor — for editing Stellaris common/button_effects/*.txt files.

A button_effect file has the top-level structure:
    effect_name = {
        potential = { ... }   # when the button is shown
        allow    = { ... }    # when the button is enabled / clickable
        effect   = { ... }    # what the button does when clicked
    }
Multiple effects can live in one file.
"""
from __future__ import annotations
import os
import re
import textwrap
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton,
    QLabel, QLineEdit, QFileDialog, QMessageBox, QMenu,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox,
    QTabWidget, QInputDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QKeySequence

from ..core.pdx_parser import parse_text, pairs_to_dict
from ..core.resource_manager import ResourceManager
from ..core.theme_manager import ThemeManager


# ---------------------------------------------------------------------------
# Syntax highlighter (reuses the same colour scheme as code_view.py)
# ---------------------------------------------------------------------------

class _BEHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self._rules: List[Tuple] = []

        def add(pattern, color, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(700)
            self._rules.append((re.compile(pattern), fmt))

        add(r'#[^\n]*',                            '#6a9955')          # comment
        add(r'\b(potential|allow|effect)\b',        '#569cd6', True)    # block keys
        add(r'\b(yes|no|always)\b',                 '#569cd6')
        add(r'"[^"]*"',                             '#ce9178')          # strings
        add(r'\b\d+(\.\d+)?\b',                     '#b5cea8')          # numbers
        add(r'\b[A-Z_]{2,}\b',                      '#9cdcfe')          # UPPER_CASE keys
        add(r'^\s*\w+\s*=\s*\{',                    '#dcdcaa')          # block headers

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import QSize


class ButtonEffectsEditor(QWidget):
    """
    Dockable panel for browsing and editing button_effects files.
    """

    modified_signal = Signal()   # emitted when any file is edited

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file: Optional[str] = None
        self._current_effect: Optional[str] = None
        self._effects: Dict[str, str] = {}   # name → raw block text
        self._dirty = False
        self._mod_dir: str = ''
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(2000)
        self._save_timer.timeout.connect(self._auto_save)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Top toolbar ─────────────────────────────────────────────
        toolbar = QHBoxLayout()
        self._file_label = QLabel('未打开文件')
        self._file_label.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        toolbar.addWidget(self._file_label, 1)

        open_btn = QPushButton('打开文件')
        open_btn.setFixedHeight(24)
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)

        new_file_btn = QPushButton('新建文件')
        new_file_btn.setFixedHeight(24)
        new_file_btn.clicked.connect(self._new_file)
        toolbar.addWidget(new_file_btn)

        save_btn = QPushButton('保存')
        save_btn.setFixedHeight(24)
        save_btn.setShortcut(QKeySequence('Ctrl+S'))
        save_btn.clicked.connect(self._save_file)
        toolbar.addWidget(save_btn)

        layout.addLayout(toolbar)

        # ── Main splitter: file tree | effect list | editor ─────────
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: file tree ─────────────────────────────────────────
        file_panel = QWidget()
        fp_layout = QVBoxLayout(file_panel)
        fp_layout.setContentsMargins(0, 0, 0, 0)
        fp_layout.setSpacing(2)

        file_hdr = QHBoxLayout()
        file_hdr.addWidget(QLabel('文件库'))
        refresh_btn = QPushButton('↻')
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setToolTip('重新扫描按钮效果目录')
        refresh_btn.clicked.connect(self._refresh_file_tree)
        file_hdr.addWidget(refresh_btn)
        fp_layout.addLayout(file_hdr)

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderHidden(True)
        self._file_tree.setColumnCount(1)
        self._file_tree.setIconSize(QSize(14, 14))
        self._file_tree.itemClicked.connect(self._on_file_tree_clicked)
        fp_layout.addWidget(self._file_tree)

        main_splitter.addWidget(file_panel)

        # ── Middle: splitter containing effect list | editor ─────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left of right section: effect list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        list_header = QHBoxLayout()
        list_header.addWidget(QLabel('效果列表'))
        new_effect_btn = QPushButton('+')
        new_effect_btn.setFixedSize(22, 22)
        new_effect_btn.setToolTip('新建 button_effect')
        new_effect_btn.clicked.connect(self._new_effect)
        del_effect_btn = QPushButton('−')
        del_effect_btn.setFixedSize(22, 22)
        del_effect_btn.setToolTip('删除选中效果')
        del_effect_btn.clicked.connect(self._delete_effect)
        list_header.addWidget(new_effect_btn)
        list_header.addWidget(del_effect_btn)
        left_layout.addLayout(list_header)

        self._effect_list = QListWidget()
        self._effect_list.currentItemChanged.connect(self._on_effect_selected)
        self._effect_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._effect_list.customContextMenuRequested.connect(self._effect_list_menu)
        left_layout.addWidget(self._effect_list)

        splitter.addWidget(left)

        # Right: tabbed editor (one tab per block)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)

        # Effect name display
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel('效果名称:'))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText('effect_name')
        self._name_edit.returnPressed.connect(self._rename_current_effect)
        name_row.addWidget(self._name_edit, 1)
        rename_btn = QPushButton('重命名')
        rename_btn.setFixedHeight(22)
        rename_btn.clicked.connect(self._rename_current_effect)
        name_row.addWidget(rename_btn)
        right_layout.addLayout(name_row)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._potential_edit = self._make_editor()
        self._allow_edit = self._make_editor()
        self._effect_edit = self._make_editor()

        self._tabs.addTab(self._potential_edit, 'potential  (显示条件)')
        self._tabs.addTab(self._allow_edit,     'allow      (激活条件)')
        self._tabs.addTab(self._effect_edit,    'effect     (执行效果)')

        right_layout.addWidget(self._tabs)

        # Reference note
        note = QLabel(
            'potential: 按钮显示条件   allow: 按钮可点击条件   effect: 点击执行的效果\n'
            '可用作用域: This = 当前所选对象  From = 玩家国家'
        )
        note.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 8px;')
        note.setWordWrap(True)
        right_layout.addWidget(note)

        splitter.addWidget(right)
        splitter.setSizes([160, 400])
        main_splitter.addWidget(splitter)
        main_splitter.setSizes([140, 560])
        layout.addWidget(main_splitter, 1)

        # ── Status bar ──────────────────────────────────────────────
        self._status = QLabel('')
        self._status.setStyleSheet(f'color: {ThemeManager.accent_color()}; font-size: 9px;')
        layout.addWidget(self._status)

        self._set_editor_enabled(False)

    def _make_editor(self) -> QTextEdit:
        edit = QTextEdit()
        edit.setFont(QFont('Consolas', 9))
        edit.setAcceptRichText(False)
        edit.setPlaceholderText('# 在此编写脚本...\nalways = yes')
        _BEHighlighter(edit.document())
        edit.textChanged.connect(self._on_content_changed)
        return edit

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def open_file(self, path: str):
        """Load a button_effects .txt file."""
        try:
            # button_effects files are expected to be UTF-8 without BOM
            with open(path, 'r', encoding='utf-8', errors='strict') as f:
                raw = f.read()
        except UnicodeDecodeError:
            # Fallback for non-standard legacy files
            with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
                raw = f.read()
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法打开文件:\n{e}')
            return
        self._current_file = path
        self._file_label.setText(os.path.basename(path))
        self._parse_file(raw)
        self._dirty = False

    def set_mod_dir(self, mod_dir: str):
        """Update mod dir and refresh file tree."""
        self._mod_dir = mod_dir or ''
        self._refresh_file_tree()

    def _refresh_file_tree(self):
        """Scan game and mod dirs for button_effects files and populate the tree."""
        self._file_tree.clear()
        rm = ResourceManager.instance()

        def _add_dir_to_tree(root_path: str, label: str):
            be_dir = os.path.join(root_path, 'common', 'button_effects')
            if not os.path.isdir(be_dir):
                return
            files = sorted(f for f in os.listdir(be_dir) if f.endswith('.txt'))
            if not files:
                return
            parent_item = QTreeWidgetItem(self._file_tree)
            parent_item.setText(0, label)
            parent_item.setExpanded(True)
            for fname in files:
                fpath = os.path.join(be_dir, fname)
                child = QTreeWidgetItem(parent_item)
                child.setText(0, fname)
                child.setData(0, Qt.ItemDataRole.UserRole, fpath)
                child.setToolTip(0, fpath)

        if self._mod_dir:
            _add_dir_to_tree(self._mod_dir, f'模组: {os.path.basename(self._mod_dir)}')
        if rm.game_dir:
            _add_dir_to_tree(rm.game_dir, '原版游戏')

        if self._file_tree.topLevelItemCount() == 0:
            placeholder = QTreeWidgetItem(self._file_tree)
            placeholder.setText(0, '(未找到 button_effects 文件)')

    def _on_file_tree_clicked(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            if self._dirty:
                resp = QMessageBox.question(
                    self, '未保存更改', '当前文件有未保存的更改，是否切换？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return
            self.open_file(path)

    def _parse_file(self, raw: str):
        """Parse a button_effects file into a dict of name → block content."""
        self._effects.clear()
        self._effect_list.clear()

        # Each top-level block: name = { ... }
        pattern = re.compile(r'(\w+)\s*=\s*\{', re.MULTILINE)
        pos = 0
        while pos < len(raw):
            m = pattern.search(raw, pos)
            if not m:
                break
            name = m.group(1)
            start = m.end()  # position after '{'
            # Find matching closing brace
            depth = 1
            i = start
            while i < len(raw) and depth > 0:
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                i += 1
            block_inner = raw[start:i - 1]
            self._effects[name] = block_inner
            self._effect_list.addItem(name)
            pos = i

        if self._effect_list.count() > 0:
            self._effect_list.setCurrentRow(0)

    def _serialize_file(self) -> str:
        """Serialize all effects back to file text."""
        parts = []
        for name, content in self._effects.items():
            parts.append(f'{name} = {{\n{content}\n}}\n')
        return '\n'.join(parts)

    def _save_file(self):
        if not self._current_file:
            self._save_as()
            return
        self._flush_current_effect()
        try:
            content = self._serialize_file()
            # Save as UTF-8 without BOM
            with open(self._current_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            self._dirty = False
            self._status.setText(f'已保存: {os.path.basename(self._current_file)}')
            self.modified_signal.emit()
        except Exception as e:
            QMessageBox.critical(self, '保存失败', str(e))

    def _save_as(self):
        rm = ResourceManager.instance()
        default_dir = ''
        if rm.mod_dir:
            default_dir = os.path.join(rm.mod_dir, 'common', 'button_effects')
            os.makedirs(default_dir, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, '另存为', default_dir,
            'Stellaris Script (*.txt);;All Files (*)'
        )
        if path:
            self._current_file = path
            self._file_label.setText(os.path.basename(path))
            self._save_file()

    def _auto_save(self):
        if self._dirty and self._current_file:
            self._save_file()

    def _open_file(self):
        rm = ResourceManager.instance()
        start_dir = ''
        if rm.mod_dir:
            start_dir = os.path.join(rm.mod_dir, 'common', 'button_effects')
        if not os.path.isdir(start_dir) and rm.game_dir:
            start_dir = os.path.join(rm.game_dir, 'common', 'button_effects')
        path, _ = QFileDialog.getOpenFileName(
            self, '打开 button_effects 文件', start_dir,
            'Stellaris Script (*.txt);;All Files (*)'
        )
        if path:
            self.open_file(path)

    def _new_file(self):
        if self._dirty:
            resp = QMessageBox.question(
                self, '未保存更改', '当前文件有未保存的更改，是否继续新建？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self._current_file = None
        self._file_label.setText('新文件 (未保存)')
        self._effects.clear()
        self._effect_list.clear()
        self._set_editor_enabled(False)
        self._dirty = False

    # ------------------------------------------------------------------
    # Effect management
    # ------------------------------------------------------------------

    def _on_effect_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if previous is not None:
            self._flush_current_effect(previous.text())
        if current is None:
            self._set_editor_enabled(False)
            return
        name = current.text()
        self._current_effect = name
        self._load_effect(name)
        self._set_editor_enabled(True)

    def _load_effect(self, name: str):
        """Parse the inner block text and fill the three tab editors."""
        if name not in self._effects:
            return
        raw = self._effects[name]

        # Extract each sub-block
        for block_name, editor in [
            ('potential', self._potential_edit),
            ('allow', self._allow_edit),
            ('effect', self._effect_edit),
        ]:
            content = self._extract_block(raw, block_name)
            editor.blockSignals(True)
            editor.setPlainText(content)
            editor.blockSignals(False)

        self._name_edit.setText(name)

    def _extract_block(self, outer: str, block_name: str) -> str:
        """Extract the inner content of a named block within outer text, dedented."""
        pattern = re.compile(rf'\b{re.escape(block_name)}\s*=\s*\{{', re.MULTILINE)
        m = pattern.search(outer)
        if not m:
            return ''
        start = m.end()
        depth = 1
        i = start
        while i < len(outer) and depth > 0:
            if outer[i] == '{':
                depth += 1
            elif outer[i] == '}':
                depth -= 1
            i += 1
        content = outer[start:i - 1]
        # Normalize indentation robustly: strip outer blank lines, then dedent.
        return textwrap.dedent(content).strip('\n')

    def _flush_current_effect(self, name: Optional[str] = None):
        """Write editor content back to _effects dict."""
        name = name or self._current_effect
        if not name or name not in self._effects:
            return
        potential = self._normalize_block_text(self._potential_edit.toPlainText())
        allow = self._normalize_block_text(self._allow_edit.toPlainText())
        effect = self._normalize_block_text(self._effect_edit.toPlainText())
        self._effects[name] = (
            f'\tpotential = {{\n'
            f'{self._indent(potential)}\n'
            f'\t}}\n'
            f'\tallow = {{\n'
            f'{self._indent(allow)}\n'
            f'\t}}\n'
            f'\teffect = {{\n'
            f'{self._indent(effect)}\n'
            f'\t}}'
        )

    @staticmethod
    def _indent(text: str, tabs: int = 2) -> str:
        prefix = '\t' * tabs
        return '\n'.join(prefix + line if line.strip() else '' for line in text.splitlines())

    @staticmethod
    def _normalize_block_text(text: str) -> str:
        """
        Normalize user-edited block text so save doesn't accumulate indentation.
        """
        if not text:
            return ''
        # Expand tabs to spaces for stable dedent, then convert back through _indent()
        dedented = textwrap.dedent(text.expandtabs(4)).strip('\n')
        return dedented

    def _on_content_changed(self):
        self._dirty = True
        self._save_timer.start()

    def _new_effect(self):
        name, ok = QInputDialog.getText(
            self, '新建效果', '效果名称 (英文+下划线):',
            text='my_new_button_effect'
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._effects:
            QMessageBox.warning(self, '重复', f'效果 "{name}" 已存在。')
            return
        self._effects[name] = (
            '\tpotential = {\n\t\talways = yes\n\t}\n'
            '\tallow = {\n\t\talways = yes\n\t}\n'
            '\teffect = {\n\t\t# 在此添加效果\n\t}'
        )
        item = QListWidgetItem(name)
        self._effect_list.addItem(item)
        self._effect_list.setCurrentItem(item)

    def _delete_effect(self):
        item = self._effect_list.currentItem()
        if not item:
            return
        name = item.text()
        resp = QMessageBox.question(
            self, '确认删除', f'确定删除效果 "{name}"？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            del self._effects[name]
            self._effect_list.takeItem(self._effect_list.row(item))
            self._dirty = True

    def _rename_current_effect(self):
        if not self._current_effect:
            return
        old_name = self._current_effect
        new_name = self._name_edit.text().strip()
        if not new_name or new_name == old_name:
            return
        if new_name in self._effects:
            QMessageBox.warning(self, '重复', f'效果 "{new_name}" 已存在。')
            return
        self._flush_current_effect(old_name)
        content = self._effects.pop(old_name)
        # Reorder: replace in-place
        new_effects = {}
        for k, v in self._effects.items():
            new_effects[k] = v
        new_effects = {new_name if k == old_name else k: v
                       for k, v in ({old_name: content} | new_effects).items()}
        # Actually just rename
        self._effects = dict(self._effects)
        self._effects[new_name] = content
        self._current_effect = new_name
        # Update list
        for i in range(self._effect_list.count()):
            if self._effect_list.item(i).text() == old_name:
                self._effect_list.item(i).setText(new_name)
                break
        self._dirty = True

    def _effect_list_menu(self, pos):
        item = self._effect_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction('重命名', self._rename_current_effect)
        menu.addAction('复制效果名称', lambda: __import__('PySide6.QtWidgets',
                       fromlist=['QApplication']).QApplication.clipboard().setText(item.text()))
        menu.addSeparator()
        menu.addAction('删除', self._delete_effect)
        menu.exec(self._effect_list.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_editor_enabled(self, enabled: bool):
        self._tabs.setEnabled(enabled)
        self._name_edit.setEnabled(enabled)
        if not enabled:
            for ed in (self._potential_edit, self._allow_edit, self._effect_edit):
                ed.blockSignals(True)
                ed.clear()
                ed.blockSignals(False)
            self._name_edit.clear()
            self._current_effect = None

    def populate_from_mod(self, mod_dir: str):
        """Scan mod/common/button_effects/ and populate the file tree."""
        self.set_mod_dir(mod_dir)
