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
from PySide6.QtGui import (
    QDrag, QFont, QColor, QIcon, QPixmap, QPainter, QPen, QPalette,
)
from PySide6.QtCore import QMimeData

from ..core.gui_model import WIDGET_TYPES, WIDGET_LABELS, WIDGET_COLORS, DEFAULT_SIZE
from ..core.theme_manager import ThemeManager
from ..core.i18n import _


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
            _('类型: ') + widget_type + '\n' +
            _('默认尺寸: ') + str(DEFAULT_SIZE.get(widget_type, 'N/A')) + '\n' +
            _('双击添加到画布')
        )
        self.setData(Qt.ItemDataRole.UserRole, widget_type)


class WidgetTypeList(QListWidget):
    """List widget that starts a copy drag for widget types."""
    MIME_TYPE = 'application/x-stellaris-widget-type'

    def startDrag(self, _supported_actions):
        item = self.currentItem()
        if not isinstance(item, WidgetTypeItem):
            return
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, item.widget_type.encode('utf-8'))
        mime.setText(item.widget_type)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(item.icon().pixmap(22, 22))
        drag.exec(Qt.DropAction.CopyAction)


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

        header = QLabel(_('控件库'))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        hint = QLabel(_('双击添加到画布中心'))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        layout.addWidget(hint)

        self._list = WidgetTypeList()
        self._list.setIconSize(QSize(18, 18))
        self._list.setSpacing(1)
        self._list.setDragEnabled(True)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._add_btn = QPushButton(_('添加到画布'))
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

        _sep(_('容器类型'))
        for wt in container_types:
            if wt in WIDGET_TYPES:
                self._list.addItem(WidgetTypeItem(wt))
        _sep(_('按钮/交互'))
        for wt in button_types:
            if wt in WIDGET_TYPES:
                self._list.addItem(WidgetTypeItem(wt))
        _sep(_('显示类型'))
        for wt in display_types:
            if wt in WIDGET_TYPES:
                self._list.addItem(WidgetTypeItem(wt))
        if other_types:
            _sep(_('其它'))
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
            self, _('输入控件名称'),
            _('为新建的 {} 输入名称:').format(widget_type),
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

        header = QLabel(_('预设库'))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        hint = QLabel(_('保存和复用控件模板'))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_insert)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton(_('保存选中为预设'))
        self._save_btn.setToolTip(_('将当前选中的控件保存为可复用预设'))
        self._save_btn.clicked.connect(self.save_preset_requested.emit)
        btn_row.addWidget(self._save_btn)

        self._del_btn = QPushButton(_('删除'))
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
            entry = self._presets[name]
            if isinstance(entry, dict):
                count = entry.get('widget_count', 1)
                code_preview = entry.get('code', '')
            else:
                count = 1
                code_preview = str(entry)
            # 显示名称 + 控件数量徽章
            display = name if count <= 1 else f'{name}  [{count} 控件]'
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, name)  # 真实 key
            # Hover 预览：显示前5行 PDX 代码
            preview_lines = code_preview.strip().splitlines()[:5]
            tooltip = '\n'.join(preview_lines)
            if len(code_preview.strip().splitlines()) > 5:
                tooltip += '\n...'
            item.setToolTip(tooltip or _('双击插入到画布'))
            self._list.addItem(item)

    def add_preset(self, name: str, code: str, widget_count: int = 1):
        self._presets[name] = {'code': code, 'widget_count': widget_count}
        self._refresh_list()
        self._save_presets()

    def preset_exists(self, name: str) -> bool:
        return name in self._presets

    def _on_insert(self, item: QListWidgetItem):
        real_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
        self.insert_preset_requested.emit(real_name)

    def _on_delete(self):
        item = self._list.currentItem()
        if item:
            real_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
            self._presets.pop(real_name, None)
            self._refresh_list()
            self._save_presets()

    def get_preset_code(self, name: str) -> Optional[str]:
        entry = self._presets.get(name)
        if entry is None:
            return None
        if isinstance(entry, dict):
            return entry.get('code')
        return str(entry)  # 旧格式兼容
