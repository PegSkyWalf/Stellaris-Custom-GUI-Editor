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
    QTabWidget, QInputDialog, QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QKeySequence

from ..core.pdx_parser import parse_text, pairs_to_dict
from ..core.resource_manager import ResourceManager
from ..core.theme_manager import ThemeManager
from ..core.i18n import _


def _reveal_in_explorer(path: str):
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


# ---------------------------------------------------------------------------
# Syntax highlighter
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

        add(r'#[^\n]*',                            '#6a9955')
        add(r'\b(potential|allow|effect)\b',        '#569cd6', True)
        add(r'\b(yes|no|always)\b',                 '#569cd6')
        add(r'"[^"]*"',                             '#ce9178')
        add(r'\b\d+(\.\d+)?\b',                     '#b5cea8')
        add(r'\b[A-Z_]{2,}\b',                      '#9cdcfe')
        add(r'^\s*\w+\s*=\s*\{',                    '#dcdcaa')

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

    工作流：
    - 左侧文件树列出模组和原版游戏中的 button_effects/*.txt 文件
    - 点击文件即打开；模组文件可新建/删除（原版文件只读）
    - 中间列出当前文件中的所有 button_effect 条目
    - 右侧三个 Tab 分别编辑 potential / allow / effect 块
    """

    modified_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file: Optional[str] = None
        self._current_effect: Optional[str] = None
        self._effects: Dict[str, str] = {}
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

        # ── 顶部状态栏 ────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        self._file_label = QLabel(_('← 从左侧文件树选择文件'))
        self._file_label.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        toolbar.addWidget(self._file_label, 1)

        save_btn = QPushButton(_('保存'))
        save_btn.setFixedHeight(24)
        save_btn.setShortcut(QKeySequence('Ctrl+S'))
        save_btn.setToolTip(_('保存当前文件 (Ctrl+S)'))
        save_btn.clicked.connect(self._save_file)
        toolbar.addWidget(save_btn)

        layout.addLayout(toolbar)

        # ── 主分割器：文件树 | 效果列表 | 编辑器 ────────────────────
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── 左：文件树 ───────────────────────────────────────────────
        file_panel = QWidget()
        fp_layout = QVBoxLayout(file_panel)
        fp_layout.setContentsMargins(0, 0, 0, 0)
        fp_layout.setSpacing(2)

        file_hdr = QHBoxLayout()
        file_hdr.addWidget(QLabel(_('文件库')))

        new_file_btn = QPushButton('+')
        new_file_btn.setFixedSize(22, 22)
        new_file_btn.setToolTip(_('在模组目录中新建 button_effects .txt 文件'))
        new_file_btn.clicked.connect(self._new_file_in_mod)
        file_hdr.addWidget(new_file_btn)

        del_file_btn = QPushButton('−')
        del_file_btn.setFixedSize(22, 22)
        del_file_btn.setToolTip(_('删除选中的模组文件（不可恢复）'))
        del_file_btn.clicked.connect(self._delete_current_file)
        file_hdr.addWidget(del_file_btn)

        refresh_btn = QPushButton('↻')
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setToolTip(_('重新扫描 button_effects 目录'))
        refresh_btn.clicked.connect(self._refresh_file_tree)
        file_hdr.addWidget(refresh_btn)

        fp_layout.addLayout(file_hdr)

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderHidden(True)
        self._file_tree.setColumnCount(1)
        self._file_tree.setIconSize(QSize(14, 14))
        self._file_tree.itemClicked.connect(self._on_file_tree_clicked)
        self._file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_tree.customContextMenuRequested.connect(self._file_tree_menu)
        fp_layout.addWidget(self._file_tree)

        main_splitter.addWidget(file_panel)

        # ── 中：效果列表 + 右：编辑器 ───────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        list_header = QHBoxLayout()
        list_header.addWidget(QLabel(_('效果列表')))
        new_effect_btn = QPushButton('+')
        new_effect_btn.setFixedSize(22, 22)
        new_effect_btn.setToolTip(_('新建 button_effect 条目'))
        new_effect_btn.clicked.connect(self._new_effect)
        del_effect_btn = QPushButton('−')
        del_effect_btn.setFixedSize(22, 22)
        del_effect_btn.setToolTip(_('删除选中效果条目'))
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

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(_('效果名称:')))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText('effect_name')
        self._name_edit.returnPressed.connect(self._rename_current_effect)
        name_row.addWidget(self._name_edit, 1)
        rename_btn = QPushButton(_('重命名'))
        rename_btn.setFixedHeight(22)
        rename_btn.clicked.connect(self._rename_current_effect)
        name_row.addWidget(rename_btn)
        right_layout.addLayout(name_row)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._potential_edit = self._make_editor()
        self._allow_edit = self._make_editor()
        self._effect_edit = self._make_editor()
        self._tabs.addTab(self._potential_edit, _('potential  (显示条件)'))
        self._tabs.addTab(self._allow_edit,     _('allow      (激活条件)'))
        self._tabs.addTab(self._effect_edit,    _('effect     (执行效果)'))
        right_layout.addWidget(self._tabs)

        note = QLabel(
            _('potential: 按钮显示条件   allow: 按钮可点击条件   effect: 点击执行的效果\n'
              '可用作用域: This = 当前所选对象  From = 玩家国家')
        )
        note.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 8px;')
        note.setWordWrap(True)
        right_layout.addWidget(note)

        splitter.addWidget(right)
        splitter.setSizes([160, 400])
        main_splitter.addWidget(splitter)
        main_splitter.setSizes([140, 560])
        layout.addWidget(main_splitter, 1)

        self._status = QLabel('')
        self._status.setStyleSheet(f'color: {ThemeManager.accent_color()}; font-size: 9px;')
        layout.addWidget(self._status)

        self._set_editor_enabled(False)

    def _make_editor(self) -> QTextEdit:
        edit = QTextEdit()
        edit.setFont(QFont('Consolas', 9))
        edit.setAcceptRichText(False)
        edit.setPlaceholderText(_('# 在此编写脚本...\nalways = yes'))
        _BEHighlighter(edit.document())
        edit.textChanged.connect(self._on_content_changed)
        return edit

    # ------------------------------------------------------------------
    # 文件树操作
    # ------------------------------------------------------------------

    def set_mod_dir(self, mod_dir: str):
        self._mod_dir = mod_dir or ''
        self._refresh_file_tree()

    def _refresh_file_tree(self):
        """扫描模组和原版游戏目录中的 button_effects 文件，填充文件树。"""
        self._file_tree.clear()
        rm = ResourceManager.instance()

        def _add_dir(root_path: str, label: str, is_mod: bool):
            be_dir = os.path.join(root_path, 'common', 'button_effects')
            if not os.path.isdir(be_dir):
                return
            files = sorted(f for f in os.listdir(be_dir) if f.endswith('.txt'))
            if not files:
                return
            parent_item = QTreeWidgetItem(self._file_tree)
            parent_item.setText(0, label)
            parent_item.setData(0, Qt.ItemDataRole.UserRole + 1, be_dir)   # 目录路径
            parent_item.setData(0, Qt.ItemDataRole.UserRole + 2, is_mod)   # 是否模组
            parent_item.setExpanded(True)
            for fname in files:
                fpath = os.path.join(be_dir, fname)
                child = QTreeWidgetItem(parent_item)
                child.setText(0, fname)
                child.setData(0, Qt.ItemDataRole.UserRole, fpath)
                child.setData(0, Qt.ItemDataRole.UserRole + 2, is_mod)
                child.setToolTip(0, fpath)
                if not is_mod:
                    child.setForeground(0, QColor(ThemeManager.muted_color()))

        if self._mod_dir:
            _add_dir(self._mod_dir, _('模组: ') + os.path.basename(self._mod_dir), True)
        if rm.game_dir:
            _add_dir(rm.game_dir, _('原版游戏 (只读)'), False)

        if self._file_tree.topLevelItemCount() == 0:
            placeholder = QTreeWidgetItem(self._file_tree)
            placeholder.setText(0, _('(未找到 button_effects 文件)'))

    def _on_file_tree_clicked(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            return
        if self._dirty:
            resp = QMessageBox.question(
                self, _('未保存更改'), _('当前文件有未保存的更改，是否切换文件？'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self.open_file(path)
        is_mod = bool(item.data(0, Qt.ItemDataRole.UserRole + 2))
        self._set_editor_readonly(not is_mod)

    def _file_tree_menu(self, pos):
        item = self._file_tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        is_mod = bool(item.data(0, Qt.ItemDataRole.UserRole + 2))
        menu = QMenu(self)
        if path and os.path.isfile(path):
            if is_mod:
                menu.addAction(_('删除此文件'), self._delete_current_file)
                menu.addSeparator()
            menu.addAction(_('在文件管理器中显示')).triggered.connect(
                lambda: _reveal_in_explorer(path))
            menu.addAction(_('复制文件路径')).triggered.connect(
                lambda: QApplication.clipboard().setText(path))
        elif not path:
            # 点在了目录节点上
            be_dir = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if be_dir:
                if is_mod:
                    menu.addAction(_('在此目录新建文件'), lambda: self._new_file_in_dir(be_dir))
                    menu.addSeparator()
                menu.addAction(_('在文件管理器中打开')).triggered.connect(
                    lambda: _reveal_in_explorer(be_dir))
                menu.addAction(_('复制目录路径')).triggered.connect(
                    lambda: QApplication.clipboard().setText(be_dir))
        if menu.isEmpty():
            return
        menu.exec(self._file_tree.mapToGlobal(pos))

    def _new_file_in_mod(self):
        """在模组的 common/button_effects/ 下新建 .txt 文件。"""
        if not self._mod_dir:
            QMessageBox.warning(self, _('未配置模组目录'),
                                _('请先在主窗口中加载模组目录，才能新建文件。'))
            return
        be_dir = os.path.join(self._mod_dir, 'common', 'button_effects')
        self._new_file_in_dir(be_dir)

    def _new_file_in_dir(self, be_dir: str):
        name, ok = QInputDialog.getText(
            self, _('新建按钮效果文件'),
            _('文件名（不含扩展名，仅英文字母/数字/下划线）:'),
            text='my_button_effects'
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if not re.match(r'^[\w]+$', name):
            QMessageBox.warning(self, _('无效文件名'),
                                _('文件名只能包含英文字母、数字和下划线。'))
            return
        os.makedirs(be_dir, exist_ok=True)
        fpath = os.path.join(be_dir, name + '.txt')
        if os.path.exists(fpath):
            QMessageBox.warning(self, _('文件已存在'),
                                _('文件 "{}" 已存在。').format(name + '.txt'))
            return

        # 写入空文件模板
        template = (
            '# Button effects for {}\n'
            '# potential = 按钮显示条件\n'
            '# allow     = 按钮可点击条件\n'
            '# effect    = 点击执行效果\n'
        ).format(name)
        try:
            with open(fpath, 'w', encoding='utf-8', newline='\n') as f:
                f.write(template)
        except Exception as e:
            QMessageBox.critical(self, _('创建失败'), str(e))
            return

        self._refresh_file_tree()
        self.open_file(fpath)
        self._set_editor_readonly(False)
        self._status.setText(_('已创建: ') + os.path.basename(fpath))

        # 在文件树中高亮新文件
        self._select_file_in_tree(fpath)

    def _delete_current_file(self):
        """删除当前选中的模组文件（二次确认）。"""
        item = self._file_tree.currentItem()
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not path:
            path = self._current_file

        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, _('未选择文件'), _('请先在文件树中选中要删除的文件。'))
            return

        is_mod = bool(item.data(0, Qt.ItemDataRole.UserRole + 2)) if item else True
        if not is_mod:
            QMessageBox.warning(self, _('只读'), _('原版游戏文件不可删除。'))
            return

        fname = os.path.basename(path)
        resp = QMessageBox.question(
            self, _('确认删除文件'),
            _('确定要删除文件 "{}" 吗？\n\n此操作不可恢复，文件将被永久删除。').format(fname),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(path)
        except Exception as e:
            QMessageBox.critical(self, _('删除失败'), str(e))
            return

        # 如果删的是当前打开的文件，清空编辑器
        if self._current_file == path:
            self._current_file = None
            self._file_label.setText(_('← 从左侧文件树选择文件'))
            self._effects.clear()
            self._effect_list.clear()
            self._set_editor_enabled(False)
            self._dirty = False

        self._refresh_file_tree()
        self._status.setText(_('已删除: ') + fname)

    def _select_file_in_tree(self, path: str):
        """在文件树中找到并高亮指定路径的文件条目。"""
        for i in range(self._file_tree.topLevelItemCount()):
            top = self._file_tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == path:
                    self._file_tree.setCurrentItem(child)
                    return

    def _set_editor_readonly(self, readonly: bool):
        """原版游戏文件以只读模式显示。"""
        for ed in (self._potential_edit, self._allow_edit, self._effect_edit):
            ed.setReadOnly(readonly)
        self._name_edit.setReadOnly(readonly)
        if readonly:
            self._status.setText(_('[只读] 原版游戏文件，无法编辑'))

    # ------------------------------------------------------------------
    # 文件读写
    # ------------------------------------------------------------------

    def open_file(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8', errors='strict') as f:
                raw = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
                raw = f.read()
        except Exception as e:
            QMessageBox.critical(self, _('错误'), _('无法打开文件:\n') + str(e))
            return
        self._current_file = path
        self._file_label.setText(os.path.basename(path))
        self._parse_file(raw)
        self._dirty = False
        self._status.setText(_('已打开: ') + os.path.basename(path))

    def _parse_file(self, raw: str):
        self._effects.clear()
        self._effect_list.clear()

        pattern = re.compile(r'(\w+)\s*=\s*\{', re.MULTILINE)
        pos = 0
        while pos < len(raw):
            m = pattern.search(raw, pos)
            if not m:
                break
            name = m.group(1)
            start = m.end()
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
        else:
            self._set_editor_enabled(False)

    def _serialize_file(self) -> str:
        parts = []
        for name, content in self._effects.items():
            parts.append(f'{name} = {{\n{content}\n}}\n')
        return '\n'.join(parts)

    def _save_file(self):
        if not self._current_file:
            return
        self._flush_current_effect()
        try:
            content = self._serialize_file()
            with open(self._current_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            self._dirty = False
            self._status.setText(_('已保存: ') + os.path.basename(self._current_file))
            self.modified_signal.emit()
        except Exception as e:
            QMessageBox.critical(self, _('保存失败'), str(e))

    def _auto_save(self):
        if self._dirty and self._current_file:
            self._save_file()

    # ------------------------------------------------------------------
    # 效果条目管理
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
        if name not in self._effects:
            return
        raw = self._effects[name]
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
        return textwrap.dedent(content).strip('\n')

    def _flush_current_effect(self, name: Optional[str] = None):
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
        if not text:
            return ''
        return textwrap.dedent(text.expandtabs(4)).strip('\n')

    def _on_content_changed(self):
        self._dirty = True
        self._save_timer.start()

    def _new_effect(self):
        if not self._current_file:
            QMessageBox.information(self, _('提示'), _('请先从文件树中打开或新建一个文件。'))
            return
        name, ok = QInputDialog.getText(
            self, _('新建效果条目'),
            _('效果名称（英文字母/数字/下划线）:'),
            text='my_new_button_effect'
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._effects:
            QMessageBox.warning(self, _('重复'), _('效果 "{}" 已存在。').format(name))
            return
        self._effects[name] = (
            '\tpotential = {\n\t\talways = yes\n\t}\n'
            '\tallow = {\n\t\talways = yes\n\t}\n'
            '\teffect = {\n\t\t# 在此添加效果\n\t}'
        )
        item = QListWidgetItem(name)
        self._effect_list.addItem(item)
        self._effect_list.setCurrentItem(item)
        self._dirty = True

    def _delete_effect(self):
        item = self._effect_list.currentItem()
        if not item:
            return
        name = item.text()
        resp = QMessageBox.question(
            self, _('确认删除'), _('确定删除效果条目 "{}"？').format(name),
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
            QMessageBox.warning(self, _('重复'), _('效果 "{}" 已存在。').format(new_name))
            return
        self._flush_current_effect(old_name)
        content = self._effects.pop(old_name)
        self._effects[new_name] = content
        self._current_effect = new_name
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
        menu.addAction(_('重命名'), self._rename_current_effect)
        menu.addAction(_('复制效果名称'), lambda: __import__('PySide6.QtWidgets',
                       fromlist=['QApplication']).QApplication.clipboard().setText(item.text()))
        menu.addSeparator()
        menu.addAction(_('删除'), self._delete_effect)
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
        self.set_mod_dir(mod_dir)
