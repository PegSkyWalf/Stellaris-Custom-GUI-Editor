"""
精灵图库面板 — 浏览、搜索和预览可用精灵图。
"""
from __future__ import annotations
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSplitter, QFrame, QMenu, QApplication,
    QButtonGroup, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap, QPainter, QBrush

from ..core.resource_manager import ResourceManager, SpriteInfo
from ..core.theme_manager import ThemeManager
from ..core.i18n import _
from .icon_provider import IconProvider

PREVIEW_SIZE = 64


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


def _checkerboard_pixmap(size: int) -> QPixmap:
    """生成棋盘格透明背景占位图。"""
    pm = QPixmap(size, size)
    pm.fill(QColor(ThemeManager.base_color()))
    painter = QPainter(pm)
    tile = 8
    c1 = QColor(ThemeManager.secondary_bg_color())
    for row in range(size // tile + 1):
        for col in range(size // tile + 1):
            if (row + col) % 2 == 0:
                painter.fillRect(col * tile, row * tile, tile, tile, QBrush(c1))
    painter.end()
    return pm


class SpriteListItem(QListWidgetItem):
    def __init__(self, info: SpriteInfo):
        super().__init__(info.name)
        self.sprite_info = info
        type_str = _('可拉伸') if info.is_scalable() else _('固定尺寸')
        src_file = info.source_file.replace('\\', '/').split('/')[-1] if info.source_file else ''
        tip = (
            f'{info.name}\n'
            f'{_("类型:")}{info.sprite_type} ({type_str})\n'
            f'{_("纹理:")}{info.texture_path}\n'
            f'{_("帧数:")}{info.no_of_frames}'
        )
        if src_file:
            tip += f'\n{_("注册文件:")}{src_file}'
        self.setToolTip(tip)

    def load_icon(self, size: int = 32):
        rm = ResourceManager.instance()
        pm = rm.get_sprite_pixmap(self.sprite_info.name, target_size=(size, size))
        if pm and not pm.isNull():
            self.setIcon(QIcon(pm))
        else:
            # 占位棋盘格
            self.setIcon(QIcon(_checkerboard_pixmap(size)))


class SpriteLibrary(QWidget):
    """精灵图库面板，列出所有已索引精灵图。"""
    sprite_selected = Signal(str)

    # 过滤模式
    _FILTER_ALL = 0
    _FILTER_FIXED = 1
    _FILTER_SCALABLE = 2
    _SCOPE_PRIMARY = 0
    _SCOPE_CURRENT_ONLY = 1
    _SCOPE_ALL = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_items: List[SpriteListItem] = []
        self._filter_mode = self._FILTER_ALL
        self._scope_mode = self._SCOPE_PRIMARY
        self._search_text = ''
        self._icon_load_timer = QTimer()
        self._icon_load_timer.setSingleShot(True)
        self._icon_load_timer.timeout.connect(self._load_visible_icons)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # ── 标题行 ────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(4)
        hdr_icon = QLabel()
        hdr_icon.setPixmap(IconProvider.accent_icon('preview', 14).pixmap(QSize(14, 14)))
        hdr_row.addWidget(hdr_icon)
        hdr = QLabel(_('精灵图库'))
        hdr.setStyleSheet(
            f'font-weight:bold; font-size:11px; color:{ThemeManager.accent_color()};')
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        self._stats_badge = QLabel('0')
        self._stats_badge.setStyleSheet(
            f'background:{ThemeManager.accent_color()}; color:#fff; '
            f'border-radius:7px; padding:1px 5px; font-size:9px; font-weight:bold;')
        hdr_row.addWidget(self._stats_badge)
        layout.addLayout(hdr_row)

        # ── 分割线 ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color:{ThemeManager.muted_color()};')
        layout.addWidget(sep)

        # ── 搜索框 ────────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_icon = QLabel()
        search_icon.setPixmap(IconProvider.muted_icon('search', 12).pixmap(QSize(12, 12)))
        search_row.addWidget(search_icon)
        self._search = QLineEdit()
        self._search.setPlaceholderText(_('搜索精灵图名称…'))
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet('font-size:10px; padding:2px 4px;')
        self._search.textChanged.connect(self._on_search)
        search_row.addWidget(self._search, 1)
        layout.addLayout(search_row)

        # ── 类型筛选器 ────────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(2)
        filter_label = QLabel(_('类型:'))
        filter_label.setStyleSheet(f'font-size:9px; color:{ThemeManager.muted_color()};')
        filter_row.addWidget(filter_label)

        btn_style_active, btn_style_inactive = self._filter_btn_styles()
        self._btn_all = QPushButton(_('全部'))
        self._btn_fixed = QPushButton(_('固定'))
        self._btn_scalable = QPushButton(_('可拉伸'))
        self._btn_all.setCheckable(True)
        self._btn_fixed.setCheckable(True)
        self._btn_scalable.setCheckable(True)
        self._btn_all.setChecked(True)
        self._btn_all.setStyleSheet(btn_style_active)
        self._btn_fixed.setStyleSheet(btn_style_inactive)
        self._btn_scalable.setStyleSheet(btn_style_inactive)

        self._filter_btn_group = QButtonGroup(self)
        self._filter_btn_group.addButton(self._btn_all, self._FILTER_ALL)
        self._filter_btn_group.addButton(self._btn_fixed, self._FILTER_FIXED)
        self._filter_btn_group.addButton(self._btn_scalable, self._FILTER_SCALABLE)
        self._filter_btn_group.setExclusive(True)
        self._filter_btn_group.idToggled.connect(self._on_filter_toggled)

        filter_row.addWidget(self._btn_all)
        filter_row.addWidget(self._btn_fixed)
        filter_row.addWidget(self._btn_scalable)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        scope_row = QHBoxLayout()
        scope_row.setSpacing(2)
        scope_label = QLabel(_('范围:'))
        scope_label.setStyleSheet(f'font-size:9px; color:{ThemeManager.muted_color()};')
        scope_row.addWidget(scope_label)
        self._btn_scope_primary = QPushButton(_('当前+原版'))
        self._btn_scope_current = QPushButton(_('仅当前'))
        self._btn_scope_all = QPushButton(_('全部资源'))
        for btn in (self._btn_scope_primary, self._btn_scope_current, self._btn_scope_all):
            btn.setCheckable(True)
        self._btn_scope_primary.setChecked(True)
        self._scope_btn_group = QButtonGroup(self)
        self._scope_btn_group.addButton(self._btn_scope_primary, self._SCOPE_PRIMARY)
        self._scope_btn_group.addButton(self._btn_scope_current, self._SCOPE_CURRENT_ONLY)
        self._scope_btn_group.addButton(self._btn_scope_all, self._SCOPE_ALL)
        self._scope_btn_group.setExclusive(True)
        self._scope_btn_group.idToggled.connect(self._on_scope_toggled)
        scope_row.addWidget(self._btn_scope_primary)
        scope_row.addWidget(self._btn_scope_current)
        scope_row.addWidget(self._btn_scope_all)
        scope_row.addStretch()
        layout.addLayout(scope_row)
        self._update_scope_button_styles()

        # ── 主 Splitter ──────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        # ── 列表 ─────────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setIconSize(QSize(32, 32))
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.verticalScrollBar().valueChanged.connect(
            lambda: self._icon_load_timer.start(120))
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {ThemeManager.border_color()};
                border-radius: 3px;
                font-size: 10px;
                font-family: 'Consolas', 'Microsoft YaHei';
            }}
            QListWidget::item {{ padding: 2px 4px; min-height: 36px; }}
            QListWidget::item:selected {{ background: {ThemeManager.selection_bg_color()}; }}
        """)
        splitter.addWidget(self._list)

        # ── 预览区 ────────────────────────────────────────────────────────
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_frame.setStyleSheet(
            f'QFrame {{ border:1px solid {ThemeManager.border_color()}; '
            f'border-radius:4px; background:{ThemeManager.base_color()}; }}')
        pv_lay = QVBoxLayout(preview_frame)
        pv_lay.setContentsMargins(6, 6, 6, 6)
        pv_lay.setSpacing(4)

        # 预览图
        self._preview_label = QLabel(_('选择精灵图以预览'))
        self._preview_label.setObjectName('sprite_preview')
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(72)
        self._preview_label.setStyleSheet(
            f'background:{ThemeManager.secondary_bg_color()}; '
            f'border:1px solid {ThemeManager.border_color()}; '
            f'border-radius:3px; color:{ThemeManager.muted_color()};')
        pv_lay.addWidget(self._preview_label)

        # 精灵名称
        self._name_label = QLabel()
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet(f'font-size:9px; font-weight:bold; color:{ThemeManager.fg_color()};')
        self._name_label.setWordWrap(True)
        pv_lay.addWidget(self._name_label)

        # 元信息行
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        self._type_badge = QLabel()
        self._type_badge.setStyleSheet(
            'font-size:8px; padding:1px 4px; border-radius:3px; '
            'background:#2a4a6a; color:#7ab8d4;')
        meta_row.addWidget(self._type_badge)
        self._size_badge = QLabel()
        self._size_badge.setStyleSheet(
            'font-size:8px; padding:1px 4px; border-radius:3px; '
            'background:#2a3a2a; color:#79c87e;')
        meta_row.addWidget(self._size_badge)
        self._frames_badge = QLabel()
        self._frames_badge.setStyleSheet(
            'font-size:8px; padding:1px 4px; border-radius:3px; '
            'background:#3a2a2a; color:#e07b53;')
        meta_row.addWidget(self._frames_badge)
        meta_row.addStretch()
        pv_lay.addLayout(meta_row)

        # 纹理路径
        self._tex_label = QLabel()
        self._tex_label.setStyleSheet(
            f'font-size:8px; color:{ThemeManager.muted_color()}; '
            f'background:transparent;')
        self._tex_label.setWordWrap(True)
        pv_lay.addWidget(self._tex_label)

        # 使用按钮
        self._use_btn = QPushButton(_('▶ 分配给选中控件'))
        self._use_btn.setEnabled(False)
        self._use_btn.clicked.connect(self._on_use_clicked)
        self._use_btn.setStyleSheet(
            f'QPushButton {{ background:{ThemeManager.accent_color()}; color:#fff; '
            f'border:none; border-radius:3px; padding:5px 10px; font-weight:bold; }}'
            f'QPushButton:disabled {{ background:{ThemeManager.border_color()}; '
            f'color:{ThemeManager.muted_color()}; }}'
        )
        pv_lay.addWidget(self._use_btn)
        splitter.addWidget(preview_frame)
        splitter.setSizes([300, 200])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(self):
        rm = ResourceManager.instance()
        sprites = rm.get_all_sprites(self._scope_filter())
        self._list.clear()
        self._all_items.clear()
        for info in sorted(sprites, key=lambda s: s.name):
            item = SpriteListItem(info)
            if info.is_scalable():
                item.setForeground(QColor(ThemeManager.accent_color()))
            self._list.addItem(item)
            self._all_items.append(item)
        self._stats_badge.setText(str(len(sprites)))
        self._apply_filter()  # 内部会启动 icon_load_timer

    def _scope_filter(self):
        if self._scope_mode == self._SCOPE_ALL:
            return None
        if self._scope_mode == self._SCOPE_CURRENT_ONLY:
            return {'current_mod'}
        return {'current_mod', 'vanilla'}

    def get_selected_sprite_name(self) -> Optional[str]:
        item = self._list.currentItem()
        if isinstance(item, SpriteListItem):
            return item.sprite_info.name
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_filter(self):
        text = self._search_text
        mode = self._filter_mode
        visible = 0
        for item in self._all_items:
            info = item.sprite_info
            hidden = False
            if text and text not in info.name.lower():
                hidden = True
            elif mode == self._FILTER_FIXED and info.is_scalable():
                hidden = True
            elif mode == self._FILTER_SCALABLE and not info.is_scalable():
                hidden = True
            item.setHidden(hidden)
            if not hidden:
                visible += 1
        total = len(self._all_items)
        if visible < total:
            self._stats_badge.setText(f'{visible}/{total}')
        else:
            self._stats_badge.setText(str(total))
        self._icon_load_timer.start(200)

    def _on_search(self, text: str):
        self._search_text = text.lower().strip()
        self._apply_filter()

    def _filter_btn_styles(self):
        """返回 (active_style, inactive_style)，基于当前主题色生成。"""
        accent = ThemeManager.accent_color()
        muted = ThemeManager.muted_color()
        border = ThemeManager.border_color()
        fg = ThemeManager.fg_color()
        active = (
            f'QPushButton {{ background:{accent}; color:#fff; '
            f'border:none; border-radius:3px; padding:2px 7px; font-size:9px; font-weight:bold; }}'
        )
        inactive = (
            f'QPushButton {{ background:transparent; color:{muted}; '
            f'border:1px solid {border}; border-radius:3px; padding:2px 7px; font-size:9px; }}'
            f'QPushButton:hover {{ border-color:{fg}; color:{fg}; }}'
        )
        return active, inactive

    def _on_filter_toggled(self, btn_id: int, checked: bool):
        if not checked:
            return
        self._filter_mode = btn_id
        btn_style_a, btn_style_i = self._filter_btn_styles()
        self._btn_all.setStyleSheet(btn_style_a if btn_id == self._FILTER_ALL else btn_style_i)
        self._btn_fixed.setStyleSheet(btn_style_a if btn_id == self._FILTER_FIXED else btn_style_i)
        self._btn_scalable.setStyleSheet(btn_style_a if btn_id == self._FILTER_SCALABLE else btn_style_i)
        self._apply_filter()

    def _on_scope_toggled(self, btn_id: int, checked: bool):
        if not checked:
            return
        self._scope_mode = btn_id
        self._update_scope_button_styles()
        self.populate()

    def _update_scope_button_styles(self):
        active, inactive = self._filter_btn_styles()
        self._btn_scope_primary.setStyleSheet(active if self._scope_mode == self._SCOPE_PRIMARY else inactive)
        self._btn_scope_current.setStyleSheet(active if self._scope_mode == self._SCOPE_CURRENT_ONLY else inactive)
        self._btn_scope_all.setStyleSheet(active if self._scope_mode == self._SCOPE_ALL else inactive)

    def _load_visible_icons(self):
        viewport_rect = self._list.viewport().rect()
        loaded = 0
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not isinstance(item, SpriteListItem) or item.isHidden():
                continue
            rect = self._list.visualItemRect(item)
            if rect.top() > viewport_rect.bottom():
                break  # 已超过视口底部，停止
            if not viewport_rect.intersects(rect):
                continue  # 还在视口上方，跳过
            if item.icon().isNull():
                item.load_icon(32)
                loaded += 1
            if loaded >= 30:
                # 每次最多渲染 30 个，剩余的下一轮加载
                self._icon_load_timer.start(50)
                break

    def _on_selection_changed(self, current: QListWidgetItem, _prev):
        if not isinstance(current, SpriteListItem):
            self._preview_label.setText(_('选择精灵图以预览'))
            self._preview_label.setPixmap(QPixmap())
            self._name_label.clear()
            self._type_badge.clear()
            self._size_badge.clear()
            self._frames_badge.clear()
            self._tex_label.clear()
            self._use_btn.setEnabled(False)
            return

        info = current.sprite_info
        rm = ResourceManager.instance()

        # 预览图
        pm = rm.get_sprite_pixmap(info.name, target_size=(128, 128))
        if pm and not pm.isNull():
            pm = pm.scaled(
                max(32, self._preview_label.width() - 8),
                max(72, self._preview_label.height() - 8),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(pm)
            self._preview_label.setStyleSheet(
                f'background:{ThemeManager.secondary_bg_color()}; '
                f'border:1px solid {ThemeManager.border_color()}; border-radius:3px;')
        else:
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText(_('无法加载预览'))
            self._preview_label.setStyleSheet(
                f'color:{ThemeManager.muted_color()}; '
                f'background:{ThemeManager.secondary_bg_color()}; '
                f'border:1px solid {ThemeManager.border_color()}; border-radius:3px;')

        # 元信息
        self._name_label.setText(info.name)
        if info.is_scalable():
            self._type_badge.setText('corneredTile')
            self._type_badge.setStyleSheet(
                'font-size:8px; padding:1px 4px; border-radius:3px; '
                'background:#2a3a4a; color:#4a9fd4;')
        else:
            nw, nh = rm.get_sprite_natural_size(info.name)
            self._type_badge.setText(f'{nw}×{nh}')
            self._type_badge.setStyleSheet(
                'font-size:8px; padding:1px 4px; border-radius:3px; '
                'background:#2a3a2a; color:#79c87e;')

        nw, nh = rm.get_sprite_natural_size(info.name)
        self._size_badge.setText(f'{nw}×{nh}')
        self._size_badge.setVisible(not info.is_scalable())

        frames = info.no_of_frames
        self._frames_badge.setText(f'{frames}f')
        self._frames_badge.setVisible(frames > 1)

        # 纹理路径
        tex_short = info.texture_path.replace('\\', '/').split('gfx/')[-1]
        self._tex_label.setText(tex_short)

        self._use_btn.setEnabled(True)
        self.sprite_selected.emit(info.name)

    def _on_double_click(self, item: QListWidgetItem):
        if isinstance(item, SpriteListItem):
            self.sprite_selected.emit(item.sprite_info.name)

    def _on_use_clicked(self):
        item = self._list.currentItem()
        if isinstance(item, SpriteListItem):
            self.sprite_selected.emit(item.sprite_info.name)

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not isinstance(item, SpriteListItem):
            return
        info = item.sprite_info
        menu = QMenu(self)
        gfx_path = getattr(info, 'source_file', '')
        if gfx_path:
            menu.addAction(_('在文件管理器中打开注册文件')).triggered.connect(
                lambda: _reveal_in_explorer(gfx_path))
            menu.addAction(_('复制注册文件路径')).triggered.connect(
                lambda: QApplication.clipboard().setText(gfx_path))
            menu.addSeparator()
        menu.addAction(_('复制精灵图名称')).triggered.connect(
            lambda: QApplication.clipboard().setText(info.name))
        if info.texture_path:
            menu.addAction(_('复制纹理路径')).triggered.connect(
                lambda: QApplication.clipboard().setText(info.texture_path))
        menu.addSeparator()
        menu.addAction(_('▶ 分配给选中控件')).triggered.connect(
            lambda: self.sprite_selected.emit(info.name))
        menu.exec(self._list.viewport().mapToGlobal(pos))
