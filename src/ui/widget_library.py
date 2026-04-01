"""
控件库面板 — 显示所有可用的群星 GUI 控件类型。
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QInputDialog, QApplication,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QPen, QPalette

from ..core.gui_model import WIDGET_TYPES, WIDGET_LABELS, WIDGET_COLORS, DEFAULT_SIZE
from ..core.theme_manager import ThemeManager


def _make_type_icon(color_str: str, size: int = 22) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color_str)
    c.setAlpha(200)
    p.fillRect(2, 2, size - 4, size - 4, c)
    p.setPen(QPen(QColor(color_str), 1))
    p.drawRect(2, 2, size - 4, size - 4)
    p.end()
    return QIcon(pm)


class WidgetTypeItem(QListWidgetItem):
    def __init__(self, widget_type: str):
        label = WIDGET_LABELS.get(widget_type, widget_type)
        super().__init__(label)
        self.widget_type = widget_type
        color = WIDGET_COLORS.get(widget_type, '#888888')
        self.setIcon(_make_type_icon(color))
        self.setToolTip(
            f'类型: {widget_type}\n'
            f'默认尺寸: {DEFAULT_SIZE.get(widget_type, "N/A")}\n'
            f'双击添加到画布'
        )
        self.setData(Qt.ItemDataRole.UserRole, widget_type)


class WidgetLibrary(QWidget):
    """控件库面板 — 双击或点击按钮添加到画布。"""
    add_widget_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel('控件库')
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        hint = QLabel('双击添加到画布中心')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setIconSize(QSize(18, 18))
        self._list.setSpacing(1)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._add_btn = QPushButton('添加到画布')
        self._add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(self._add_btn)

        self._populate()

    def _populate(self):
        container_types = ['containerWindowType', 'scrollAreaType', 'listboxType', 'smoothListboxType']
        button_types = ['buttonType', 'effectButtonType', 'checkBoxType']
        display_types = ['iconType', 'instantTextBoxType', 'textBoxType', 'editBoxType']
        other_types = [t for t in sorted(WIDGET_TYPES) if t not in container_types + button_types + display_types]

        def _sep(text):
            sep = QListWidgetItem(f'─── {text} ───')
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            sep.setForeground(QApplication.palette().color(QPalette.ColorRole.Mid))
            self._list.addItem(sep)

        _sep('容器类型')
        for wt in container_types:
            if wt in WIDGET_TYPES:
                self._list.addItem(WidgetTypeItem(wt))
        _sep('按钮/交互')
        for wt in button_types:
            if wt in WIDGET_TYPES:
                self._list.addItem(WidgetTypeItem(wt))
        _sep('显示类型')
        for wt in display_types:
            if wt in WIDGET_TYPES:
                self._list.addItem(WidgetTypeItem(wt))
        if other_types:
            _sep('其它')
            for wt in other_types:
                self._list.addItem(WidgetTypeItem(wt))

    def _on_double_click(self, item: QListWidgetItem):
        if isinstance(item, WidgetTypeItem):
            self._request_add(item.widget_type)

    def _on_add_clicked(self):
        item = self._list.currentItem()
        if isinstance(item, WidgetTypeItem):
            self._request_add(item.widget_type)

    def _request_add(self, widget_type: str):
        name, ok = QInputDialog.getText(
            self, '输入控件名称',
            f'为新建的 {widget_type} 输入名称:',
            text=f'new_{widget_type[:10]}'
        )
        if ok:
            self.add_widget_requested.emit(widget_type, name or f'new_{widget_type}')


class PresetLibrary(QWidget):
    """自定义预设控件库。"""
    insert_preset_requested = Signal(str)
    save_preset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._presets = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel('预设库')
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        hint = QLabel('保存和复用控件模板')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_insert)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton('保存选中为预设')
        self._save_btn.setToolTip('将当前选中的控件保存为可复用预设')
        self._save_btn.clicked.connect(self.save_preset_requested.emit)
        btn_row.addWidget(self._save_btn)

        self._del_btn = QPushButton('删除')
        self._del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._del_btn)
        layout.addLayout(btn_row)

        self._load_presets()

    def _load_presets(self):
        from ..core.settings import AppSettings
        presets = AppSettings.instance().get('presets', {})
        if isinstance(presets, dict):
            self._presets = presets
            self._refresh_list()

    def _save_presets(self):
        from ..core.settings import AppSettings
        AppSettings.instance().set('presets', self._presets)

    def _refresh_list(self):
        self._list.clear()
        for name in sorted(self._presets.keys()):
            item = QListWidgetItem(name)
            item.setToolTip('双击插入到画布')
            self._list.addItem(item)

    def add_preset(self, name: str, code: str):
        self._presets[name] = code
        self._refresh_list()
        self._save_presets()

    def _on_insert(self, item: QListWidgetItem):
        self.insert_preset_requested.emit(item.text())

    def _on_delete(self):
        item = self._list.currentItem()
        if item:
            self._presets.pop(item.text(), None)
            self._refresh_list()
            self._save_presets()

    def get_preset_code(self, name: str) -> Optional[str]:
        return self._presets.get(name)
