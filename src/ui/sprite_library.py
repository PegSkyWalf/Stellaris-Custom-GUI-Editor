"""
精灵图库面板 — 浏览、搜索和预览可用精灵图。
"""
from __future__ import annotations
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSplitter, QFrame,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QColor

from ..core.resource_manager import ResourceManager, SpriteInfo

PREVIEW_SIZE = 64


class SpriteListItem(QListWidgetItem):
    def __init__(self, info: SpriteInfo):
        super().__init__(info.name)
        self.sprite_info = info
        type_str = '可拉伸' if info.is_scalable() else '固定尺寸'
        self.setToolTip(
            f'名称: {info.name}\n'
            f'类型: {info.sprite_type} ({type_str})\n'
            f'纹理: {info.texture_path}\n'
            f'帧数: {info.no_of_frames}'
        )

    def load_icon(self):
        rm = ResourceManager.instance()
        pm = rm.get_sprite_pixmap(self.sprite_info.name, target_size=(28, 28))
        if pm and not pm.isNull():
            self.setIcon(QIcon(pm))


class SpriteLibrary(QWidget):
    """精灵图库面板，列出所有已索引精灵图。"""
    sprite_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_items: List[SpriteListItem] = []
        self._icon_load_timer = QTimer()
        self._icon_load_timer.setSingleShot(True)
        self._icon_load_timer.timeout.connect(self._load_visible_icons)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel('精灵图库')
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(header)

        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText('搜索精灵图名称...')
        self._search.textChanged.connect(self._on_search)
        search_row.addWidget(self._search)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        self._list = QListWidget()
        self._list.setIconSize(QSize(28, 28))
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.verticalScrollBar().valueChanged.connect(
            lambda: self._icon_load_timer.start(100)
        )
        splitter.addWidget(self._list)

        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(4, 4, 4, 4)

        self._preview_label = QLabel('无预览')
        self._preview_label.setObjectName('sprite_preview')
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(80)
        preview_layout.addWidget(self._preview_label)

        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet('color: #aaa; font-size: 9px;')
        self._info_label.setWordWrap(True)
        preview_layout.addWidget(self._info_label)

        self._use_btn = QPushButton('分配给选中控件')
        self._use_btn.clicked.connect(self._on_use_clicked)
        preview_layout.addWidget(self._use_btn)

        splitter.addWidget(preview_widget)
        splitter.setSizes([280, 180])

        self._stats = QLabel('未加载精灵图')
        self._stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats.setStyleSheet('color: #666; font-size: 9px;')
        layout.addWidget(self._stats)

    def populate(self):
        rm = ResourceManager.instance()
        sprites = rm.get_all_sprites()
        self._list.clear()
        self._all_items.clear()
        for info in sorted(sprites, key=lambda s: s.name):
            item = SpriteListItem(info)
            if info.is_scalable():
                item.setForeground(QColor('#7ec8e3'))
            self._list.addItem(item)
            self._all_items.append(item)
        self._stats.setText(f'共 {len(sprites)} 个精灵图')
        self._icon_load_timer.start(300)

    def _load_visible_icons(self):
        for i in range(min(60, self._list.count())):
            item = self._list.item(i)
            if isinstance(item, SpriteListItem) and item.icon().isNull():
                item.load_icon()

    def _on_search(self, text: str):
        text = text.lower().strip()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if isinstance(item, SpriteListItem):
                item.setHidden(bool(text) and text not in item.sprite_info.name.lower())

    def _on_selection_changed(self, current: QListWidgetItem, _):
        if not isinstance(current, SpriteListItem):
            self._preview_label.setText('无预览')
            self._info_label.clear()
            return

        info = current.sprite_info
        rm = ResourceManager.instance()

        pm = rm.get_sprite_pixmap(info.name, target_size=(128, 128))
        if pm and not pm.isNull():
            from PySide6.QtCore import Qt
            pm = pm.scaled(
                self._preview_label.width() - 8,
                max(80, self._preview_label.height() - 8),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(pm)
            self._preview_label.setStyleSheet('background: #2a2a2a; border: 1px solid #444;')
        else:
            self._preview_label.setText('无法加载')
            self._preview_label.setStyleSheet('color: #666; background: #2a2a2a; border: 1px solid #444;')

        nw, nh = rm.get_sprite_natural_size(info.name)
        type_str = '可拉伸 (corneredTile)' if info.is_scalable() else f'固定尺寸 {nw}×{nh}'
        self._info_label.setText(
            f'{info.name}\n类型: {type_str}\n帧数: {info.no_of_frames}\n{info.texture_path}'
        )
        self.sprite_selected.emit(info.name)

    def _on_double_click(self, item: QListWidgetItem):
        if isinstance(item, SpriteListItem):
            self.sprite_selected.emit(item.sprite_info.name)

    def _on_use_clicked(self):
        item = self._list.currentItem()
        if isinstance(item, SpriteListItem):
            self.sprite_selected.emit(item.sprite_info.name)

    def get_selected_sprite_name(self) -> Optional[str]:
        item = self._list.currentItem()
        if isinstance(item, SpriteListItem):
            return item.sprite_info.name
        return None
