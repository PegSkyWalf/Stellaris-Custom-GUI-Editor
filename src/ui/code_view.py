"""
代码视图面板 — 实时代码预览，支持语法高亮和选中控件定位。
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QCheckBox, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QTimer, QRegularExpression
from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import (
    QFont, QColor, QTextCharFormat, QSyntaxHighlighter,
    QTextDocument, QTextCursor,
)

from ..core.gui_model import GUIDocument, WidgetNode
from ..codegen.gui_writer import write_document
from ..core.theme_manager import is_dark_theme
from ..core.settings import AppSettings

# Dark theme token colors (VS Code Dark+)
_DARK_COLORS = {
    'comment':    ('#6a9955', False, True),
    'keyword':    ('#4ec9b0', False, False),
    'property':   ('#9cdcfe', False, False),
    'value':      ('#ce9178', False, False),
    'gfx':        ('#dcdcaa', False, False),
    'variable':   ('#c586c0', False, False),
    'number':     ('#b5cea8', False, False),
    'brace':      ('#ffd700', False, False),
    'equals':     ('#d4d4d4', False, False),
}

# Light theme token colors (VS Code Light)
_LIGHT_COLORS = {
    'comment':    ('#008000', False, True),
    'keyword':    ('#267f99', False, False),
    'property':   ('#0070c1', False, False),
    'value':      ('#a31515', False, False),
    'gfx':        ('#795e26', False, False),
    'variable':   ('#800080', False, False),
    'number':     ('#098658', False, False),
    'brace':      ('#d4630a', False, False),
    'equals':     ('#444444', False, False),
}

_KW_PATTERN = r'\b({kw})\b'.format(kw='|'.join([
    'guiTypes', 'spriteTypes', 'containerWindowType', 'iconType',
    'buttonType', 'effectButtonType', 'effectbuttontype',
    'instantTextBoxType', 'textBoxType', 'editBoxType', 'background',
    'checkBoxType', 'listboxType', 'scrollAreaType', 'spriteType',
    'corneredTileSpriteType', 'frameAnimatedSpriteType',
    'extendedScrollbarType', 'gridBoxType', 'smoothListboxType',
    'overlappingElementsBoxType', 'OverlappingElementsBoxType',
]))
_PROPS_PATTERN = r'\b({props})\b'.format(props='|'.join([
    'name', 'position', 'size', 'orientation', 'Orientation', 'origo',
    'spriteType', 'quadTextureSprite', 'texturefile', 'textureFile',
    'buttonText', 'buttonFont', 'text', 'appendText', 'font',
    'maxWidth', 'maxHeight', 'format', 'borderSize', 'fixedSize', 'fixedsize',
    'text_color_code', 'text_offset', 'scale', 'alwaysTransparent',
    'alwaystransparent', 'clicksound', 'oversound', 'shortcut',
    'actionShortcut', 'pdx_tooltip', 'tooltipText', 'custom_tooltip',
    'effect', 'noOfFrames', 'moveable', 'clipping', 'effectFile',
    'verticalScrollbar', 'smooth_scrolling', 'startValue',
    'spacing', 'offset', 'rotation', 'centerPosition',
    'vertical_alignment', 'multiline', 'mirror', 'frame',
]))


class PDXHighlighter(QSyntaxHighlighter):
    """PDX 脚本语法高亮器，支持深色/浅色双主题。"""

    def __init__(self, document: QTextDocument, dark_mode: bool = True):
        super().__init__(document)
        self._rules: list = []
        self.set_dark_mode(dark_mode)

    def set_dark_mode(self, dark_mode: bool) -> None:
        """Switch between dark and light color palettes and rehighlight."""
        colors = _DARK_COLORS if dark_mode else _LIGHT_COLORS

        def _fmt(key: str) -> QTextCharFormat:
            color, bold, italic = colors[key]
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(700)
            if italic:
                f.setFontItalic(True)
            return f

        self._rules = [
            (QRegularExpression(r'#[^\n]*'),      _fmt('comment')),
            (QRegularExpression(_KW_PATTERN),     _fmt('keyword')),
            (QRegularExpression(_PROPS_PATTERN),  _fmt('property')),
            (QRegularExpression(r'\b(yes|no)\b'), _fmt('value')),
            (QRegularExpression(r'"[^"]*"'),       _fmt('value')),
            (QRegularExpression(r'\bGFX_\w+'),    _fmt('gfx')),
            (QRegularExpression(r'@\w+'),          _fmt('variable')),
            (QRegularExpression(r'\b-?\d+(\.\d+)?\b'), _fmt('number')),
            (QRegularExpression(r'[{}]'),          _fmt('brace')),
            (QRegularExpression(r'='),             _fmt('equals')),
        ]
        self.rehighlight()

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# Code view threshold: above this many lines, disable auto-update and syntax highlighting
_LARGE_DOC_LINE_THRESHOLD = 3000


class CodeView(QWidget):
    """代码预览和编辑面板，支持选中控件高亮跳转。"""
    code_applied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[GUIDocument] = None
        self._auto_update = True
        self._auto_apply = False           # auto-apply code edits to canvas
        self._large_file_mode = False
        self._writing_to_editor = False    # prevents feedback loop when we update editor text

        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(600)
        self._update_timer.timeout.connect(self._do_update)

        # Debounced auto-apply: fires 1.5s after last keypress
        self._apply_timer = QTimer()
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(1500)
        self._apply_timer.timeout.connect(self._auto_apply_edits)

        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor('#264f78'))
        self._highlighter: Optional[PDXHighlighter] = None
        self._setup_ui()
        # Apply current theme on construction
        theme = AppSettings.instance().theme
        self.update_theme(theme)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header row
        header_row = QHBoxLayout()
        lbl = QLabel('代码视图')
        lbl.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        header_row.addWidget(lbl)
        header_row.addStretch()

        self._auto_cb = QCheckBox('自动更新')
        self._auto_cb.setChecked(True)
        self._auto_cb.setToolTip('当画布/属性改变时自动刷新代码视图')
        self._auto_cb.stateChanged.connect(
            lambda s: setattr(self, '_auto_update', s == Qt.CheckState.Checked.value)
        )
        header_row.addWidget(self._auto_cb)

        self._auto_apply_cb = QCheckBox('实时同步')
        self._auto_apply_cb.setChecked(False)
        self._auto_apply_cb.setToolTip('编辑代码后1.5秒自动同步到画布（实时双向同步）')
        self._auto_apply_cb.stateChanged.connect(self._on_auto_apply_toggled)
        header_row.addWidget(self._auto_apply_cb)

        self._manual_refresh_btn = QPushButton('手动刷新')
        self._manual_refresh_btn.setFixedWidth(70)
        self._manual_refresh_btn.setToolTip('强制重新生成代码（大文件模式下使用）')
        self._manual_refresh_btn.clicked.connect(self._do_update)
        header_row.addWidget(self._manual_refresh_btn)
        layout.addLayout(header_row)

        # Search bar
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText('在代码中搜索...')
        self._search_edit.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_edit)
        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # Code editor — QPlainTextEdit is significantly faster than QTextEdit for large files
        self._editor = QPlainTextEdit()
        self._editor.setObjectName('code_editor')
        self._editor.setReadOnly(False)
        font = QFont('Consolas', 10)
        font.setFixedPitch(True)
        self._editor.setFont(font)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._editor.document().setUndoRedoEnabled(False)
        # Highlighter init with dark_mode=True; update_theme() will correct it after
        self._highlighter = PDXHighlighter(self._editor.document(), dark_mode=True)
        # Connect textChanged to trigger auto-apply debounce
        self._editor.textChanged.connect(self._on_editor_text_changed)
        layout.addWidget(self._editor)

        # Large-file notice bar (hidden normally)
        self._large_file_bar = QLabel()
        self._large_file_bar.setStyleSheet(
            'background: #3a2a00; color: #ffcc44; padding: 4px; font-size: 9px;'
        )
        self._large_file_bar.setWordWrap(True)
        self._large_file_bar.hide()
        layout.addWidget(self._large_file_bar)

        # Buttons
        btn_row = QHBoxLayout()
        self._copy_btn = QPushButton('复制全部')
        self._copy_btn.clicked.connect(self._copy_all)
        btn_row.addWidget(self._copy_btn)

        self._goto_btn = QPushButton('跳转到选中控件')
        self._goto_btn.setToolTip('在代码中定位当前选中的控件')
        self._goto_btn.clicked.connect(self.scroll_to_selected)
        btn_row.addWidget(self._goto_btn)

        self._apply_btn = QPushButton('应用代码修改')
        self._apply_btn.setToolTip('将当前代码解析并同步回画布')
        self._apply_btn.clicked.connect(self._apply_edits)
        btn_row.addWidget(self._apply_btn)
        layout.addLayout(btn_row)

        # Status
        self._status_label = QLabel('')
        self._status_label.setStyleSheet('color: #888; font-size: 9px;')
        layout.addWidget(self._status_label)

    def update_theme(self, theme_name: str) -> None:
        """Apply the given theme to the editor and syntax highlighter."""
        dark = is_dark_theme(theme_name)
        if self._highlighter is not None:
            self._highlighter.set_dark_mode(dark)
        # Highlight format: blue for dark, muted blue for light
        if dark:
            self._highlight_format.setBackground(QColor('#264f78'))
        else:
            self._highlight_format.setBackground(QColor('#add8e6'))
        # Status label text color
        self._status_label.setStyleSheet(
            'color: #555; font-size: 9px;' if not dark else 'color: #888; font-size: 9px;'
        )

    def _on_auto_apply_toggled(self, state):
        self._auto_apply = (state == Qt.CheckState.Checked.value)
        if not self._auto_apply:
            self._apply_timer.stop()

    def _on_editor_text_changed(self):
        """Called whenever the editor content changes (user typing or programmatic update)."""
        if self._writing_to_editor:
            return   # avoid feedback loop when we update editor programmatically
        if self._auto_apply and not self._large_file_mode:
            self._apply_timer.start()

    def _auto_apply_edits(self):
        """Debounced auto-apply: parse code and emit code_applied signal."""
        if not self._auto_apply or self._large_file_mode:
            return
        self.code_applied.emit(self._editor.toPlainText())

    def set_document(self, doc: Optional[GUIDocument]):
        self._doc = doc
        self._large_file_mode = False
        self.update_code()

    def schedule_update(self):
        """Schedule a code update. Always runs even in large-file mode."""
        self._update_timer.start()

    def force_update(self):
        """Immediately update code view (called on structural changes: add/delete widget)."""
        self._update_timer.stop()
        self._do_update()

    def update_code(self):
        if self._doc is None:
            self._editor.setPlainText('')
            self._large_file_bar.hide()
            return
        self._do_update()

    def _do_update(self):
        if self._doc is None:
            return
        try:
            code = write_document(self._doc)
            line_count = code.count('\n') + 1

            # Detect large file: disable highlighter and auto-apply (code→canvas)
            # Note: canvas→code sync always runs regardless of large file mode
            is_large = line_count > _LARGE_DOC_LINE_THRESHOLD
            if is_large and not self._large_file_mode:
                self._large_file_mode = True
                self._auto_update = False
                self._auto_cb.setChecked(False)
                # Detach highlighter to avoid O(n) re-highlighting on every change
                if self._highlighter:
                    self._highlighter.setDocument(None)
                    self._highlighter = None
                self._large_file_bar.setText(
                    f'⚠ 大文件模式 ({line_count} 行) — 已禁用自动应用和语法高亮以保持流畅。'
                    '  代码视图仍会跟随画布更新。'
                )
                self._large_file_bar.show()
            elif not is_large and self._large_file_mode:
                # File became small again (e.g. after reset)
                self._large_file_mode = False
                if self._highlighter is None:
                    self._highlighter = PDXHighlighter(self._editor.document())
                self._large_file_bar.hide()

            cursor_pos = self._editor.textCursor().position()
            self._writing_to_editor = True
            try:
                self._editor.setPlainText(code)
            finally:
                self._writing_to_editor = False
            cursor = self._editor.textCursor()
            cursor.setPosition(min(cursor_pos, len(code)))
            self._editor.setTextCursor(cursor)
            self._status_label.setText(f'{line_count} 行 / {len(code)} 字符')
        except Exception as e:
            self._editor.setPlainText(f'# 生成代码时发生错误:\n# {e}')

    def highlight_node(self, node: Optional[WidgetNode]):
        """Highlight the code block corresponding to the selected node."""
        if node is None:
            self._clear_extra_selections()
            return

        text = self._editor.toPlainText()
        if not text or self._doc is None:
            return

        # 1) Primary: structure-based定位（按节点在控件树中的路径）
        node_path = self._compute_node_path(node)
        if node_path is not None:
            block = self._find_block_by_struct_path(text, node_path)
            if block is not None:
                self._highlight_range(block[0], block[1])
                return

        # 2) Fallback: 旧的名称匹配（仅在无法建立结构路径时使用）
        name = node.name
        if not name:
            return
        esc = re.escape(name)
        exact_name_pat = (
            rf'name\s*=\s*'
            rf'(?:"(?P<dq>{esc})"'
            rf"|'(?P<sq>{esc})'"
            rf'|(?P<uq>{esc})(?=[^a-zA-Z0-9_]|$))'
        )
        m = re.search(exact_name_pat, text, re.IGNORECASE)
        if m:
            self._highlight_range(m.start(), m.end())

    # --------------------------------------------------------------
    # Structure-based block lookup
    # --------------------------------------------------------------
    _WIDGET_BLOCK_KEYS = {
        'containerwindowtype', 'icontype', 'buttontype', 'effectbuttontype',
        'instanttextboxtype', 'textboxtype', 'editboxtype', 'checkboxtype',
        'listboxtype', 'scrollareatype', 'overlappingelementsboxtype',
        'gridboxtype', 'smoothlistboxtype', 'extendedscrollbartype',
        'scrollbartype', 'dropdownboxtype', 'positiontype', 'guibuttontype',
        'spinnertype', 'windowtype', 'expandbutton', 'expandedwindow',
    }

    def _compute_node_path(self, node: WidgetNode) -> Optional[Tuple[int, ...]]:
        """
        Return structural path tuple for *node*.
        Example: (0, 3, 1) means:
          root[0] -> children[3] -> children[1]
        """
        if self._doc is None:
            return None
        if node.parent is None:
            try:
                return (self._doc.roots.index(node),)
            except ValueError:
                return None

        indices: List[int] = []
        cur = node
        while cur.parent is not None:
            p = cur.parent
            try:
                idx = p.children.index(cur)
            except ValueError:
                return None
            indices.append(idx)
            cur = p
        try:
            root_idx = self._doc.roots.index(cur)
        except ValueError:
            return None
        return (root_idx, *reversed(indices))

    @staticmethod
    def _find_matching_brace(text: str, open_idx: int) -> Optional[int]:
        """Find matching '}' for text[open_idx] == '{', with basic string/comment skipping."""
        if open_idx < 0 or open_idx >= len(text) or text[open_idx] != '{':
            return None
        depth = 0
        i = open_idx
        n = len(text)
        while i < n:
            c = text[i]
            if c == '#':
                while i < n and text[i] != '\n':
                    i += 1
                continue
            if c in ('"', "'"):
                q = c
                i += 1
                while i < n:
                    if text[i] == '\\':
                        i += 2
                        continue
                    if text[i] == q:
                        break
                    i += 1
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None

    def _find_block_by_struct_path(
        self, text: str, target_path: Tuple[int, ...]
    ) -> Optional[Tuple[int, int]]:
        """
        Parse widget blocks in generated code and return (start, end) span
        for the widget at *target_path*.
        """
        key_pat = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{')
        stack: List[Tuple[Tuple[int, ...], int]] = []  # (path, end_idx)
        child_counters: Dict[Tuple[int, ...], int] = {}
        root_counter = 0
        pos = 0
        while True:
            m = key_pat.search(text, pos)
            if not m:
                break
            block_start = m.start()
            key = m.group(1).lower()
            brace_open = text.find('{', m.end() - 1)
            if brace_open < 0:
                break
            block_end = self._find_matching_brace(text, brace_open)
            if block_end is None:
                break

            # drop finished parent stack frames
            while stack and block_start > stack[-1][1]:
                stack.pop()

            if key in self._WIDGET_BLOCK_KEYS:
                if not stack:
                    path = (root_counter,)
                    root_counter += 1
                else:
                    parent_path = stack[-1][0]
                    idx = child_counters.get(parent_path, 0)
                    child_counters[parent_path] = idx + 1
                    path = (*parent_path, idx)

                if path == target_path:
                    return (block_start, block_end + 1)
                stack.append((path, block_end))

            pos = m.end()
        return None

    def scroll_to_selected(self):
        """Scroll the code view to show the selected node."""
        extra = self._editor.extraSelections()
        if extra:
            cursor = extra[0].cursor
            self._editor.setTextCursor(cursor)
            self._editor.centerCursor()

    def _highlight_range(self, start: int, end: int):
        """Highlight a character range with background color."""
        cursor = self._editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        sel = QTextEdit.ExtraSelection()
        sel.format = self._highlight_format
        sel.cursor = cursor

        self._editor.setExtraSelections([sel])
        self._editor.setTextCursor(cursor)
        self._editor.centerCursor()

    def _clear_extra_selections(self):
        self._editor.setExtraSelections([])

    def _do_search(self):
        text = self._search_edit.text().strip()
        if not text:
            return
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        found = doc.find(text, cursor)
        if found.isNull():
            # Wrap around
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            found = doc.find(text, cursor)
        if not found.isNull():
            self._editor.setTextCursor(found)
            self._editor.centerCursor()

    def _copy_all(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._editor.toPlainText())

    def _apply_edits(self):
        self.code_applied.emit(self._editor.toPlainText())
