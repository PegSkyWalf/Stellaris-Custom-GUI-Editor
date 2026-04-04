"""
Event Link Panel — shows events that reference the current GUI via custom_gui.

When the user selects an event, the panel emits event_selected(EventInfo) so the
canvas can render room images, fill text boxes with desc, and overlay option texts.
"""
from __future__ import annotations
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QTextEdit, QSplitter,
    QMessageBox, QMenu, QApplication, QFrame, QLineEdit,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor, QIcon

from ..core.resource_manager import ResourceManager
from ..core.theme_manager import ThemeManager
from ..core.i18n import _
from .icon_provider import IconProvider


def _reveal_in_explorer(path: str):
    import os, sys, subprocess
    if sys.platform == 'win32':
        if os.path.isfile(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
        else:
            os.startfile(os.path.normpath(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', '-R', path] if os.path.isfile(path) else ['open', path])
    else:
        subprocess.Popen(['xdg-open', os.path.dirname(path) if os.path.isfile(path) else path])


# 事件类型颜色表
_EVENT_TYPE_COLORS = {
    'country_event':    '#4a9fd4',
    'fleet_event':      '#e07b53',
    'ship_event':       '#e0c353',
    'planet_event':     '#79c87e',
    'pop_event':        '#b07ed4',
    'observer_event':   '#d4a04a',
    'leader_event':     '#4ad4c4',
}


class EventListItem(QListWidgetItem):
    def __init__(self, ev, title_loc: str):
        super().__init__()
        self._ev = ev
        ev_color = _EVENT_TYPE_COLORS.get(ev.event_type, '#888888')
        type_short = ev.event_type.replace('_event', '').upper() if ev.event_type else '?'
        n_opts = len(ev.options) if ev.options else 0
        opt_badge = f'  [{n_opts}选]' if n_opts else ''

        # 使用 HTML 富文本
        self.setText(ev.id)
        self.setData(Qt.ItemDataRole.UserRole, ev)
        self.setData(Qt.ItemDataRole.UserRole + 1, type_short)
        self.setData(Qt.ItemDataRole.UserRole + 2, ev_color)

        # 标题行
        title_short = title_loc[:28] + ('…' if len(title_loc) > 28 else '') if title_loc else ''
        display = f'[{type_short}] {ev.id}'
        if title_short and title_short != ev.id:
            display += f'\n  {title_short}{opt_badge}'
        elif opt_badge:
            display += opt_badge
        self.setText(display)

        tip = f'ID: {ev.id}\n类型: {ev.event_type}'
        if title_loc:
            tip += f'\n标题: {title_loc}'
        if ev.file_path:
            tip += f'\n文件: {ev.file_path}'
        self.setToolTip(tip)

        self.setForeground(QColor(ev_color))


class EventLinkPanel(QWidget):
    """Dock panel that lists events referencing the current GUI."""

    event_selected = Signal(object)   # EventInfo or None
    clear_event = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gui_names: List[str] = []
        self._events: List = []
        self._filtered_events: List = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # ── 标题栏 ────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(4)
        hdr_icon = QLabel()
        hdr_icon.setPixmap(IconProvider.accent_icon('search', 14).pixmap(QSize(14, 14)))
        hdr_row.addWidget(hdr_icon)
        hdr = QLabel(_('事件关联'))
        hdr.setStyleSheet(
            f'font-weight:bold; font-size:11px; color:{ThemeManager.accent_color()};')
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        self._count_badge = QLabel('0')
        self._count_badge.setStyleSheet(
            f'background:{ThemeManager.accent_color()}; color:#fff; '
            f'border-radius:7px; padding:1px 5px; font-size:9px; font-weight:bold;')
        hdr_row.addWidget(self._count_badge)
        layout.addLayout(hdr_row)

        # ── 当前 GUI 标签 ─────────────────────────────────────────────────
        self._gui_label = QLabel(_('未加载 GUI'))
        self._gui_label.setStyleSheet(
            f'color:{ThemeManager.muted_color()}; font-size:9px; '
            f'padding:1px 2px; background:transparent;')
        self._gui_label.setWordWrap(True)
        layout.addWidget(self._gui_label)

        # ── 分割线 ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color:{ThemeManager.muted_color()};')
        layout.addWidget(sep)

        # ── 搜索框 ────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText(_('搜索事件 ID / 标题…'))
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet('font-size:10px; padding:2px 4px;')
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        # ── 主 Splitter ──────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        # ── 事件列表区 ────────────────────────────────────────────────────
        list_frame = QFrame()
        list_frame.setFrameShape(QFrame.Shape.StyledPanel)
        list_frame.setStyleSheet('QFrame { border:none; }')
        list_lay = QVBoxLayout(list_frame)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(2)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {ThemeManager.border_color()};
                border-radius: 3px;
                font-size: 10px;
                font-family: 'Microsoft YaHei', 'Consolas';
            }}
            QListWidget::item {{ padding: 3px 5px; min-height: 30px; }}
            QListWidget::item:selected {{ background: {ThemeManager.selection_bg_color()}; }}
        """)
        list_lay.addWidget(self._list, 1)

        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._apply_btn = QPushButton(_('▶ 应用上下文'))
        self._apply_btn.setEnabled(False)
        self._apply_btn.setToolTip(_('将选中事件的上下文（文本、图像、选项）加载到画布'))
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setStyleSheet(
            f'QPushButton {{ background:{ThemeManager.accent_color()}; color:#fff; '
            f'border:none; border-radius:3px; padding:4px 8px; font-weight:bold; }}'
            f'QPushButton:disabled {{ background:{ThemeManager.border_color()}; '
            f'color:{ThemeManager.muted_color()}; }}'
        )
        btn_row.addWidget(self._apply_btn, 1)

        self._clear_btn = QPushButton(_('✕ 清除'))
        self._clear_btn.setToolTip(_('清除事件上下文，恢复空白画布'))
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setStyleSheet(
            f'QPushButton {{ border:1px solid {ThemeManager.border_color()}; '
            f'border-radius:3px; padding:4px 8px; }}'
            f'QPushButton:hover {{ border-color:{ThemeManager.fg_color()}; }}'
        )
        btn_row.addWidget(self._clear_btn)
        list_lay.addLayout(btn_row)
        splitter.addWidget(list_frame)

        # ── 事件详情区 ────────────────────────────────────────────────────
        detail_frame = QFrame()
        detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        detail_lay = QVBoxLayout(detail_frame)
        detail_lay.setContentsMargins(0, 0, 0, 0)
        detail_lay.setSpacing(2)

        detail_hdr = QLabel(_('事件详情'))
        detail_hdr.setStyleSheet(
            f'font-size:9px; font-weight:bold; color:{ThemeManager.muted_color()}; '
            f'padding:2px 3px; background:{ThemeManager.base_color()}; border-radius:2px;')
        detail_lay.addWidget(detail_hdr)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setFont(QFont('Microsoft YaHei', 8))
        self._detail.setStyleSheet(
            f'QTextEdit {{ border:none; background:{ThemeManager.base_color()}; '
            f'font-size:10px; color:{ThemeManager.fg_color()}; padding:4px; }}')
        detail_lay.addWidget(self._detail, 1)
        splitter.addWidget(detail_frame)
        splitter.setSizes([260, 150])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_gui_names(self, gui_names: List[str]):
        self._gui_names = [n for n in gui_names if n]
        self._events = []
        self._filtered_events = []
        self._list.clear()
        self._detail.clear()
        self._apply_btn.setEnabled(False)
        self._search.clear()

        if not self._gui_names:
            self._gui_label.setText(_('未加载 GUI'))
            self._count_badge.setText('0')
            return

        name_display = self._gui_names[0]
        if len(self._gui_names) > 1:
            name_display += f' +{len(self._gui_names) - 1}'
        self._gui_label.setText(name_display)

        rm = ResourceManager.instance()
        rm.ensure_events_scanned()
        seen_ids: set = set()
        for gui_name in self._gui_names:
            for ev in rm.get_events_for_gui(gui_name):
                if ev.id not in seen_ids:
                    seen_ids.add(ev.id)
                    self._events.append(ev)

        self._count_badge.setText(str(len(self._events)))
        self._apply_filter('')

    def set_gui_name(self, gui_name: str):
        self.set_gui_names([gui_name] if gui_name else [])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_filter(self, text: str):
        self._list.clear()
        self._apply_btn.setEnabled(False)
        text = text.lower().strip()
        rm = ResourceManager.instance()

        if not self._events:
            item = QListWidgetItem(_('（未找到引用此 GUI 的事件）'))
            item.setForeground(QColor(ThemeManager.muted_color()))
            self._list.addItem(item)
            self._filtered_events = []
            return

        self._filtered_events = []
        for ev in self._events:
            title_loc = rm.get_loc(ev.title) if ev.title else ''
            if text and text not in ev.id.lower() and text not in title_loc.lower():
                continue
            self._filtered_events.append(ev)
            item = EventListItem(ev, title_loc)
            self._list.addItem(item)

        if not self._filtered_events and text:
            no_item = QListWidgetItem(_('（无匹配结果）'))
            no_item.setForeground(QColor(ThemeManager.muted_color()))
            self._list.addItem(no_item)

    def _on_search_changed(self, text: str):
        self._apply_filter(text)
        self._detail.clear()

    def _on_row_changed(self, row: int):
        self._apply_btn.setEnabled(row >= 0 and row < len(self._filtered_events))
        if row < 0 or row >= len(self._filtered_events):
            self._detail.clear()
            return
        ev = self._filtered_events[row]
        self._show_detail(ev)

    def _on_double_click(self, item: QListWidgetItem):
        ev = item.data(Qt.ItemDataRole.UserRole)
        if ev:
            self.event_selected.emit(ev)

    def _show_detail(self, ev):
        rm = ResourceManager.instance()
        ev_color = _EVENT_TYPE_COLORS.get(ev.event_type, ThemeManager.muted_color())
        muted = ThemeManager.muted_color()
        fg = ThemeManager.fg_color()
        lines = []
        lines.append(
            f'<div style="background:{ev_color}22; border-left:3px solid {ev_color}; '
            f'padding:4px 6px; margin-bottom:6px;">'
            f'<b style="color:{ev_color};">[{ev.event_type}]</b> '
            f'<b style="color:{fg};">{ev.id}</b></div>'
        )
        if ev.title:
            loc_title = rm.get_loc(ev.title)
            lines.append(
                f'<p style="margin:2px 0; color:{fg};"><b>{_("标题:")}</b> {loc_title}</p>')
        if ev.desc:
            loc_desc = rm.get_loc(ev.desc)
            preview = loc_desc[:220] + ('…' if len(loc_desc) > 220 else '')
            lines.append(
                f'<p style="margin:2px 0; color:{muted}; font-size:9px;">'
                f'<b>{_("描述:")}</b> {preview}</p>')
        if ev.room:
            scope_note = (
                f' <i style="color:{muted};">(域引用)</i>' if ev.is_scope_room else '')
            lines.append(
                f'<p style="margin:2px 0; color:{fg};"><b>Room:</b> {ev.room}{scope_note}</p>')
        if ev.custom_gui_option:
            lines.append(
                f'<p style="margin:2px 0; color:{fg};"><b>custom_gui_option:</b> '
                f'<span style="color:{ev_color};">{ev.custom_gui_option}</span></p>')
        if ev.options:
            opt_lines = []
            for opt in ev.options:
                name_loc = rm.get_loc(opt.name) if opt.name else (opt.name or '?')
                cg = getattr(opt, 'custom_gui', '')
                cg_str = (
                    f' <span style="color:{muted}; font-size:9px;">({cg})</span>'
                    if cg else '')
                opt_lines.append(f'  <li style="color:{fg};">{name_loc}{cg_str}</li>')
            lines.append(
                f'<p style="margin:2px 0; color:{fg};">'
                f'<b>{_("选项 ({0}):").format(len(ev.options))}</b></p>'
                f'<ul style="margin:2px 0 2px 12px; padding:0;">{"".join(opt_lines)}</ul>')
        if ev.file_path:
            short = ev.file_path.replace('\\', '/').split('/')[-1]
            lines.append(
                f'<p style="margin:4px 0 2px 0; color:{muted}; font-size:9px;">'
                f'📄 {short}</p>')
        self._detail.setHtml(''.join(lines))

    def _on_apply(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._filtered_events):
            self.event_selected.emit(self._filtered_events[row])

    def _on_clear(self):
        self._list.clearSelection()
        self._detail.clear()
        self._apply_btn.setEnabled(False)
        self.event_selected.emit(None)

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        ev = item.data(Qt.ItemDataRole.UserRole)
        if not ev:
            return
        menu = QMenu(self)
        file_path = getattr(ev, 'file_path', '')
        if file_path:
            menu.addAction(_('在文件管理器中打开')).triggered.connect(
                lambda: _reveal_in_explorer(file_path))
            menu.addAction(_('复制文件路径')).triggered.connect(
                lambda: QApplication.clipboard().setText(file_path))
            menu.addSeparator()
        menu.addAction(_('应用事件上下文')).triggered.connect(
            lambda: self.event_selected.emit(ev))
        menu.addAction(_('复制事件 ID')).triggered.connect(
            lambda: QApplication.clipboard().setText(ev.id))
        menu.exec(self._list.viewport().mapToGlobal(pos))
