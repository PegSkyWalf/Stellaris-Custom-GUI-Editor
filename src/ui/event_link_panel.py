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
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ..core.resource_manager import ResourceManager


class EventLinkPanel(QWidget):
    """Dock panel that lists events referencing the current GUI."""

    event_selected = Signal(object)   # EventInfo or None
    clear_event = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gui_names: List[str] = []
        self._events: List = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QLabel('事件关联面板')
        hdr.setStyleSheet('font-weight:bold; color:#7ec8e3; padding:2px;')
        layout.addWidget(hdr)

        self._gui_label = QLabel('无当前 GUI')
        self._gui_label.setStyleSheet('color:#888; font-size:9px;')
        layout.addWidget(self._gui_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        # Event list
        list_w = QWidget()
        list_lay = QVBoxLayout(list_w)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(2)
        list_lay.addWidget(QLabel('引用该 GUI 的事件:'))
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_row_changed)
        list_lay.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton('应用事件上下文')
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)
        self._clear_btn = QPushButton('清除上下文')
        self._clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(self._clear_btn)
        list_lay.addLayout(btn_row)
        splitter.addWidget(list_w)

        # Detail view
        detail_w = QWidget()
        detail_lay = QVBoxLayout(detail_w)
        detail_lay.setContentsMargins(0, 0, 0, 0)
        detail_lay.setSpacing(2)
        detail_lay.addWidget(QLabel('事件详情:'))
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(140)
        self._detail.setFont(QFont('Microsoft YaHei', 8))
        detail_lay.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([240, 140])

    def set_gui_names(self, gui_names: List[str]):
        """Called when a new GUI is loaded — scan for events referencing any of the given names.

        A .gui file may contain multiple top-level containerWindowType GUIs; pass all their
        names so events that reference any of them are shown.
        """
        self._gui_names = [n for n in gui_names if n]
        self._events = []
        self._list.clear()
        self._detail.clear()
        self._apply_btn.setEnabled(False)

        if not self._gui_names:
            self._gui_label.setText('无当前 GUI')
            return

        if len(self._gui_names) == 1:
            self._gui_label.setText(f'GUI: {self._gui_names[0]}')
        else:
            self._gui_label.setText(
                f'GUI: {self._gui_names[0]}  (+{len(self._gui_names) - 1} 个)')

        rm = ResourceManager.instance()
        # 懒加载：首次查询时才扫描事件目录（避免启动时扫描大型模组卡死）
        rm.ensure_events_scanned()
        seen_ids: set = set()
        for gui_name in self._gui_names:
            for ev in rm.get_events_for_gui(gui_name):
                if ev.id not in seen_ids:
                    seen_ids.add(ev.id)
                    self._events.append(ev)

        if not self._events:
            item = QListWidgetItem('（未找到引用此 GUI 的事件）')
            item.setForeground(QColor('#888'))
            self._list.addItem(item)
            return

        for ev in self._events:
            title_loc = rm.get_loc(ev.title) if ev.title else ''
            display = f'[{ev.event_type}] {ev.id}'
            if title_loc and title_loc != ev.title:
                display += f'  "{title_loc[:30]}"'
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, ev)
            self._list.addItem(item)

    def set_gui_name(self, gui_name: str):
        """Backwards-compatible single-name wrapper."""
        self.set_gui_names([gui_name] if gui_name else [])

    def _on_row_changed(self, row: int):
        self._apply_btn.setEnabled(row >= 0 and row < len(self._events))
        if row < 0 or row >= len(self._events):
            self._detail.clear()
            return
        ev = self._events[row]
        self._show_detail(ev)

    def _show_detail(self, ev):
        rm = ResourceManager.instance()
        lines = []
        lines.append(f'<b>ID:</b> {ev.id}')
        lines.append(f'<b>类型:</b> {ev.event_type}')
        if ev.title:
            loc_title = rm.get_loc(ev.title)
            lines.append(f'<b>标题:</b> {loc_title}')
        if ev.desc:
            loc_desc = rm.get_loc(ev.desc)
            # Truncate long desc
            preview = loc_desc[:200] + ('...' if len(loc_desc) > 200 else '')
            lines.append(f'<b>描述:</b> {preview}')
        if ev.room:
            scope_note = ' <i>(域引用)</i>' if ev.is_scope_room else ''
            lines.append(f'<b>Room:</b> {ev.room}{scope_note}')
        if ev.custom_gui_option:
            lines.append(f'<b>custom_gui_option:</b> {ev.custom_gui_option}')
        if ev.options:
            opts = []
            for opt in ev.options:
                name_loc = rm.get_loc(opt.name) if opt.name else opt.name
                opts.append(f'  • {name_loc} ({opt.name})')
            lines.append('<b>选项:</b><br>' + '<br>'.join(opts))
        self._detail.setHtml('<br>'.join(lines))

    def _on_apply(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._events):
            self.event_selected.emit(self._events[row])

    def _on_clear(self):
        self._list.clearSelection()
        self._detail.clear()
        self._apply_btn.setEnabled(False)
        self.event_selected.emit(None)
