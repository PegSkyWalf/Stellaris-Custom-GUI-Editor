"""
各类对话框 — 群星 GUI 编辑器。
"""
from __future__ import annotations
import os
import subprocess
import sys
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QDialogButtonBox, QWidget, QListWidget, QListWidgetItem,
    QTabWidget, QSpinBox, QCheckBox, QSplitter, QTextEdit,
    QComboBox, QColorDialog, QApplication, QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QPixmap, QIcon, QColor

from ..core.settings import AppSettings
from ..core.resource_manager import ResourceManager
from ..core.theme_manager import AVAILABLE_THEMES, ThemeManager
from ..core import i18n as _i18n
from ..core.i18n import _, get_available_languages, get_language_display_name


# ===========================================================================
# SettingsDialog — 多标签设置对话框
# ===========================================================================

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('编辑器设置'))
        self.setMinimumSize(540, 430)
        self._settings = AppSettings.instance()
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_paths_tab(), _('路径'))
        tabs.addTab(self._build_canvas_tab(), _('画布'))
        tabs.addTab(self._build_appearance_tab(), _('外观'))
        tabs.addTab(self._build_editor_tab(), _('编辑器'))
        tabs.addTab(self._build_advanced_tab(), _('高级'))

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_('确定'))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(_('取消'))
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    # 路径标签页
    # ------------------------------------------------------------------

    def _build_paths_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)

        self._game_dir_edit = QLineEdit()
        row = QHBoxLayout()
        row.addWidget(self._game_dir_edit)
        browse_btn = QPushButton(_('浏览…'))
        browse_btn.clicked.connect(self._browse_game)
        row.addWidget(browse_btn)
        form.addRow(_('游戏安装目录:'), row)

        note = QLabel(_('群星的安装目录，例如：\n<Steam>/steamapps/common/Stellaris'))
        note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        form.addRow('', note)

        auto_btn = QPushButton(_('自动检测'))
        auto_btn.clicked.connect(self._auto_detect)
        form.addRow('', auto_btn)

        form.addRow(QLabel(''))
        extra_label = QLabel(_('依赖模组目录（用于精灵图贴图查找）:'))
        extra_label.setStyleSheet('font-weight:bold;')
        form.addRow(extra_label)

        self._extra_mods_list = QListWidget()
        self._extra_mods_list.setMaximumHeight(100)
        form.addRow(self._extra_mods_list)

        extra_btn_row = QHBoxLayout()
        add_extra_btn = QPushButton(_('添加目录'))
        add_extra_btn.clicked.connect(self._add_extra_mod)
        remove_extra_btn = QPushButton(_('移除选中'))
        remove_extra_btn.clicked.connect(self._remove_extra_mod)
        extra_btn_row.addWidget(add_extra_btn)
        extra_btn_row.addWidget(remove_extra_btn)
        form.addRow(extra_btn_row)

        extra_note = QLabel(_('若本模组引用了其他模组的贴图/精灵图，\n请将那些模组的根目录添加到此列表。'))
        extra_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        extra_note.setWordWrap(True)
        form.addRow('', extra_note)
        return tab

    # ------------------------------------------------------------------
    # 画布标签页
    # ------------------------------------------------------------------

    def _build_canvas_tab(self) -> QWidget:
        tab = QWidget()
        cform = QFormLayout(tab)
        cform.setContentsMargins(16, 16, 16, 16)
        cform.setSpacing(10)

        self._canvas_w = QSpinBox()
        self._canvas_w.setRange(640, 7680)
        self._canvas_w.setSuffix(' px')
        cform.addRow(_('画布宽度:'), self._canvas_w)

        self._canvas_h = QSpinBox()
        self._canvas_h.setRange(480, 4320)
        self._canvas_h.setSuffix(' px')
        cform.addRow(_('画布高度:'), self._canvas_h)

        res_note = QLabel(_('对应游戏运行分辨率，通常为 1920×1080'))
        res_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        cform.addRow('', res_note)

        self._grid_size = QSpinBox()
        self._grid_size.setRange(1, 64)
        self._grid_size.setSuffix(' px')
        cform.addRow(_('网格尺寸:'), self._grid_size)

        self._show_grid = QCheckBox(_('显示网格'))
        cform.addRow('', self._show_grid)

        self._snap = QCheckBox(_('吸附到网格'))
        cform.addRow('', self._snap)

        # 智能吸附设置
        snap_group = QGroupBox(_('智能吸附'))
        snap_form = QFormLayout(snap_group)
        snap_form.setSpacing(8)

        self._smart_snap = QCheckBox(_('启用智能吸附'))
        self._smart_snap.setToolTip(_('拖拽时自动对齐到其他控件的边缘/中心'))
        snap_form.addRow('', self._smart_snap)

        self._snap_threshold = QSpinBox()
        self._snap_threshold.setRange(1, 20)
        self._snap_threshold.setSuffix(' px')
        self._snap_threshold.setToolTip(_('吸附灵敏度（越大越容易触发）'))
        snap_form.addRow(_('吸附阈值:'), self._snap_threshold)

        self._snap_edges = QCheckBox(_('边缘对齐'))
        snap_form.addRow('', self._snap_edges)

        self._snap_centers = QCheckBox(_('中心对齐'))
        snap_form.addRow('', self._snap_centers)

        self._snap_spacing = QCheckBox(_('等间距检测'))
        snap_form.addRow('', self._snap_spacing)

        cform.addRow(snap_group)

        return tab

    # ------------------------------------------------------------------
    # 外观标签页
    # ------------------------------------------------------------------

    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self._theme_combo = QComboBox()
        for key, (display_name, _theme_extra) in AVAILABLE_THEMES.items():
            self._theme_combo.addItem(display_name, key)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_preview)
        form.addRow(_('界面主题:'), self._theme_combo)

        theme_note = QLabel(_('更改主题后点击"确定"即时生效，无需重启。'))
        theme_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        form.addRow('', theme_note)

        accent_row = QHBoxLayout()
        self._accent_preview = QLabel()
        self._accent_preview.setFixedSize(24, 24)
        self._accent_preview.setStyleSheet('border:1px solid #555;')
        accent_row.addWidget(self._accent_preview)
        self._accent_edit = QLineEdit()
        self._accent_edit.setPlaceholderText(_('如：#4a9fd4  （留空使用主题默认）'))
        self._accent_edit.textChanged.connect(self._on_accent_changed)
        accent_row.addWidget(self._accent_edit)
        pick_btn = QPushButton(_('选色…'))
        pick_btn.setFixedWidth(60)
        pick_btn.clicked.connect(self._pick_accent)
        accent_row.addWidget(pick_btn)
        form.addRow(_('强调色:'), accent_row)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 18)
        self._font_size_spin.setSuffix(' pt')
        form.addRow(_('界面字体大小:'), self._font_size_spin)

        self._lang_combo = QComboBox()
        for lang in get_available_languages():
            self._lang_combo.addItem(get_language_display_name(lang), lang)
        form.addRow(_('UI 语言:'), self._lang_combo)

        lang_note = QLabel(_('更改语言后需重启应用完全生效。'))
        lang_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        form.addRow('', lang_note)

        return tab

    # ------------------------------------------------------------------
    # 编辑器标签页
    # ------------------------------------------------------------------

    def _build_editor_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)

        self._undo_limit_spin = QSpinBox()
        self._undo_limit_spin.setRange(10, 500)
        self._undo_limit_spin.setSuffix(_(' 步'))
        form.addRow(_('撤销历史深度:'), self._undo_limit_spin)

        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(10, 600)
        self._autosave_spin.setSuffix(_(' 秒'))
        form.addRow(_('自动保存间隔:'), self._autosave_spin)

        self._code_font_edit = QLineEdit()
        self._code_font_edit.setPlaceholderText('Consolas')
        form.addRow(_('代码字体:'), self._code_font_edit)

        self._code_font_size_spin = QSpinBox()
        self._code_font_size_spin.setRange(7, 20)
        self._code_font_size_spin.setSuffix(' pt')
        form.addRow(_('代码字体大小:'), self._code_font_size_spin)

        note = QLabel(_('代码字体修改在下次打开文件后生效。'))
        note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        form.addRow('', note)
        return tab

    # ------------------------------------------------------------------
    # 高级标签页
    # ------------------------------------------------------------------

    def _build_advanced_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)

        self._log_level_combo = QComboBox()
        for lvl in ('DEBUG', 'INFO', 'WARNING', 'ERROR'):
            self._log_level_combo.addItem(lvl, lvl)
        form.addRow(_('日志级别:'), self._log_level_combo)

        log_note = QLabel(_('DEBUG 会记录大量信息，适合排查问题；正常使用建议 INFO。'))
        log_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        log_note.setWordWrap(True)
        form.addRow('', log_note)

        open_log_btn = QPushButton(_('打开日志目录'))
        open_log_btn.clicked.connect(self._open_log_dir)
        from ..core.logger import get_log_dir, _LOG_FILE
        log_path_lbl = QLabel(str(_LOG_FILE))
        log_path_lbl.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:8px;')
        log_path_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        log_path_lbl.setWordWrap(True)
        form.addRow('', open_log_btn)
        form.addRow(_('日志文件:'), log_path_lbl)

        form.addRow(QLabel(''))
        clear_mod_btn = QPushButton(_('清除上次加载的模组路径'))
        clear_mod_btn.setToolTip(_('若应用启动时因自动加载模组而卡死，可点此清除记录'))
        clear_mod_btn.clicked.connect(self._clear_last_mod_dir)
        form.addRow(_('恢复:'), clear_mod_btn)

        form.addRow(QLabel(''))
        reset_btn = QPushButton(_('重置首次启动向导'))
        reset_btn.setToolTip(_('下次启动时重新显示首次配置向导'))
        reset_btn.clicked.connect(self._reset_first_run)
        form.addRow('', reset_btn)

        return tab

    # ------------------------------------------------------------------
    # 加载 / 保存
    # ------------------------------------------------------------------

    def _load(self):
        # 路径
        self._game_dir_edit.setText(self._settings.game_dir)
        self._extra_mods_list.clear()
        for d in self._settings.extra_mod_dirs:
            self._extra_mods_list.addItem(d)

        # 画布
        cw, ch = self._settings.canvas_size
        self._canvas_w.setValue(cw)
        self._canvas_h.setValue(ch)
        self._grid_size.setValue(self._settings.grid_size)
        self._show_grid.setChecked(self._settings.show_grid)
        self._snap.setChecked(self._settings.snap_to_grid)

        # 智能吸附
        self._smart_snap.setChecked(self._settings.smart_snap_enabled)
        self._snap_threshold.setValue(self._settings.smart_snap_threshold)
        self._snap_edges.setChecked(self._settings.snap_to_edges)
        self._snap_centers.setChecked(self._settings.snap_to_centers)
        self._snap_spacing.setChecked(self._settings.snap_to_spacing)

        # 外观
        theme = self._settings.theme
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == theme:
                self._theme_combo.setCurrentIndex(i)
                break
        accent = self._settings.accent_color
        self._accent_edit.setText(accent)
        self._update_accent_preview(accent)
        self._font_size_spin.setValue(self._settings.font_size)
        # 语言
        current_lang = self._settings.get('ui_language', 'zh_CN')
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == current_lang:
                self._lang_combo.setCurrentIndex(i)
                break

        # 编辑器
        self._undo_limit_spin.setValue(self._settings.undo_limit)
        self._autosave_spin.setValue(self._settings.autosave_interval_sec)
        self._code_font_edit.setText(self._settings.code_font)
        self._code_font_size_spin.setValue(self._settings.code_font_size)

        # 高级
        log_level = self._settings.log_level
        idx = self._log_level_combo.findData(log_level)
        if idx >= 0:
            self._log_level_combo.setCurrentIndex(idx)

    def _save_and_accept(self):
        # 路径
        self._settings.game_dir = self._game_dir_edit.text().strip()
        extra_dirs = [self._extra_mods_list.item(i).text()
                      for i in range(self._extra_mods_list.count())]
        self._settings.extra_mod_dirs = extra_dirs
        rm = ResourceManager.instance()
        rm._extra_mod_dirs = []
        for d in extra_dirs:
            rm.load_extra_mod_dir(d)

        # 画布
        self._settings.canvas_size = (self._canvas_w.value(), self._canvas_h.value())
        self._settings.grid_size = self._grid_size.value()
        self._settings.show_grid = self._show_grid.isChecked()
        self._settings.snap_to_grid = self._snap.isChecked()

        # 智能吸附
        self._settings.smart_snap_enabled = self._smart_snap.isChecked()
        self._settings.smart_snap_threshold = self._snap_threshold.value()
        self._settings.snap_to_edges = self._snap_edges.isChecked()
        self._settings.snap_to_centers = self._snap_centers.isChecked()
        self._settings.snap_to_spacing = self._snap_spacing.isChecked()

        # 外观
        new_theme = self._theme_combo.currentData()
        new_accent = self._accent_edit.text().strip()
        self._settings.theme = new_theme
        self._settings.accent_color = new_accent
        self._settings.font_size = self._font_size_spin.value()
        # 即时应用主题
        app = QApplication.instance()
        if app:
            ThemeManager.apply(app, new_theme, new_accent or None)
        # 语言（立即生效；控件文字需重启后才能重新渲染）
        new_lang = self._lang_combo.currentData()
        if new_lang:
            self._settings.set('ui_language', new_lang)
            _i18n.set_language(new_lang)

        # 编辑器
        self._settings.undo_limit = self._undo_limit_spin.value()
        self._settings.autosave_interval_sec = self._autosave_spin.value()
        self._settings.code_font = self._code_font_edit.text().strip() or 'Consolas'
        self._settings.code_font_size = self._code_font_size_spin.value()

        # 高级
        self._settings.log_level = self._log_level_combo.currentData()

        self.accept()

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _browse_game(self):
        start = self._game_dir_edit.text() or os.path.expanduser('~')
        path = QFileDialog.getExistingDirectory(self, _('选择群星游戏目录'), start)
        if path:
            self._game_dir_edit.setText(path)

    def _auto_detect(self):
        detected = self._settings.detect_game_dir()
        if detected:
            self._game_dir_edit.setText(detected)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, _('未找到'),
                                    _('无法自动检测群星目录，请手动指定。\n'
                                      '提示：在 Steam 中右键群星 → 管理 → 浏览本地文件'))

    def _add_extra_mod(self):
        start = os.path.expanduser('~')
        path = QFileDialog.getExistingDirectory(self, _('选择依赖模组根目录'), start)
        if path:
            self._extra_mods_list.addItem(path)

    def _remove_extra_mod(self):
        for item in self._extra_mods_list.selectedItems():
            self._extra_mods_list.takeItem(self._extra_mods_list.row(item))

    def _on_theme_preview(self, _idx: int):
        """主题选择变化时实时预览（不保存，取消时会还原）。"""
        pass  # 如需实时预览可在此应用主题

    def _on_accent_changed(self, text: str):
        self._update_accent_preview(text)

    def _update_accent_preview(self, color_str: str):
        if color_str and QColor(color_str).isValid():
            self._accent_preview.setStyleSheet(
                f'background:{color_str}; border:1px solid #555;')
        else:
            self._accent_preview.setStyleSheet('border:1px solid #555;')

    def _pick_accent(self):
        current = self._accent_edit.text().strip()
        init_color = QColor(current) if current and QColor(current).isValid() else QColor('#4a9fd4')
        color = QColorDialog.getColor(init_color, self, _('选择强调色'))
        if color.isValid():
            self._accent_edit.setText(color.name())

    def _open_log_dir(self):
        from ..core.logger import get_log_dir
        log_dir = str(get_log_dir())
        if sys.platform == 'win32':
            os.startfile(log_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', log_dir])
        else:
            subprocess.run(['xdg-open', log_dir])

    def _clear_last_mod_dir(self):
        from PySide6.QtWidgets import QMessageBox
        self._settings.last_mod_dir = ''
        QMessageBox.information(self, _('已清除'), _('上次加载的模组路径已清除。\n下次启动时将不再自动加载该模组。'))

    def _reset_first_run(self):
        self._settings.first_run = True
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, _('已重置'), _('下次启动时将重新显示首次配置向导。'))


# ===========================================================================
# NewFileDialog
# ===========================================================================

class NewFileDialog(QDialog):
    def __init__(self, mod_dir: str = '', parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('新建 GUI 文件'))
        self.setMinimumWidth(440)
        self._mod_dir = mod_dir
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        note = QLabel(
            _('新文件将基于标准 Custom GUI 模板创建，包含所有必要的原版控件占位符。\n'
              '请勿删除或更改模板中隐藏控件的 name 值，否则游戏会崩溃。')
        )
        note.setStyleSheet('color:#f39c12; font-size:9px;')
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(_('my_custom_gui（不含 .gui 扩展名）'))
        form.addRow(_('文件名:'), self._name_edit)

        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText('my_mod_prefix_main_window')
        key_note = QLabel(_('GUI 键名 (name=)，在 custom_gui= 中引用此值触发界面'))
        key_note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        form.addRow(_('GUI 键名:'), self._key_edit)
        form.addRow('', key_note)

        self._dir_edit = QLineEdit()
        self._dir_edit.setText(
            os.path.join(self._mod_dir, 'interface') if self._mod_dir else ''
        )
        row = QHBoxLayout()
        row.addWidget(self._dir_edit)
        btn = QPushButton(_('浏览…'))
        btn.clicked.connect(self._browse_dir)
        row.addWidget(btn)
        form.addRow(_('保存目录:'), row)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_('创建'))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(_('取消'))
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_dir(self):
        start = self._dir_edit.text() or os.path.expanduser('~')
        path = QFileDialog.getExistingDirectory(self, _('选择保存目录'), start)
        if path:
            self._dir_edit.setText(path)

    def _validate(self):
        import re
        if self._name_edit.text().strip():
            if not self._key_edit.text().strip():
                name = self._name_edit.text().strip()
                auto_key = re.sub(r'[^a-zA-Z0-9_]', '_', name.replace('.gui', ''))
                self._key_edit.setText(auto_key)
            self.accept()

    def get_file_path(self) -> str:
        name = self._name_edit.text().strip()
        if not name.endswith('.gui'):
            name += '.gui'
        return os.path.join(self._dir_edit.text(), name)

    def get_gui_key(self) -> str:
        import re
        key = self._key_edit.text().strip()
        if not key:
            name = self._name_edit.text().strip().replace('.gui', '')
            key = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        return key or 'my_gui_key'


# ===========================================================================
# SpritePicker
# ===========================================================================

class SpritePicker(QDialog):
    """精灵图选择对话框。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('选择精灵图'))
        self.setMinimumSize(540, 520)
        self.selected_sprite: str = ''
        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(_('搜索精灵图名称…'))
        self._search.textChanged.connect(self._filter)
        filter_row.addWidget(self._search)

        self._type_filter = QComboBox()
        self._type_filter.addItem(_('全部类型'), '')
        self._type_filter.addItem(_('可拉伸 (corneredTile)'), 'scalable')
        self._type_filter.addItem(_('固定尺寸 (spriteType)'), 'fixed')
        self._type_filter.currentIndexChanged.connect(lambda _: self._filter(self._search.text()))
        filter_row.addWidget(self._type_filter)
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list = QListWidget()
        self._list.setIconSize(QSize(28, 28))
        self._list.itemClicked.connect(lambda item: self._on_select(item.text()))
        self._list.currentItemChanged.connect(
            lambda cur, _: self._on_select(cur.text()) if cur else None
        )
        self._list.setAutoScroll(False)
        self._list.itemDoubleClicked.connect(lambda _: self.accept())
        splitter.addWidget(self._list)

        right = QWidget()
        rl = QVBoxLayout(right)
        self._preview = QLabel(_('无预览'))
        self._preview.setObjectName('sprite_preview')
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFixedSize(140, 140)
        rl.addWidget(self._preview)
        self._info = QLabel()
        self._info.setWordWrap(True)
        self._info.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        rl.addWidget(self._info)
        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([260, 260])
        layout.addWidget(splitter)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_('选择'))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(_('取消'))
        btns.accepted.connect(self._accept_selection)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self):
        rm = ResourceManager.instance()
        for name in rm.get_sprite_names():
            info = rm.get_sprite(name)
            item = QListWidgetItem(name)
            if info and info.is_scalable():
                item.setForeground(QColor(ThemeManager.accent_color()))
            self._list.addItem(item)

    def _filter(self, text: str):
        text = text.lower()
        type_filter = self._type_filter.currentData()
        rm = ResourceManager.instance()
        for i in range(self._list.count()):
            item = self._list.item(i)
            name = item.text()
            text_match = not text or text in name.lower()
            if type_filter and text_match:
                info = rm.get_sprite(name)
                if type_filter == 'scalable':
                    type_match = bool(info and info.is_scalable())
                else:
                    type_match = bool(info and not info.is_scalable())
            else:
                type_match = True
            item.setHidden(not (text_match and type_match))

    def _on_select(self, name: str):
        if not name:
            return
        rm = ResourceManager.instance()
        pm = rm.get_sprite_pixmap(name, target_size=(120, 120))
        if pm and not pm.isNull():
            self._preview.setPixmap(pm)
        else:
            self._preview.setText(_('无法加载'))
        info = rm.get_sprite(name)
        if info:
            nw, nh = rm.get_sprite_natural_size(name)
            type_str = _('可拉伸') if info.is_scalable() else (_('固定 %d×%d') % (nw, nh))
            self._info.setText(
                _('类型: %s\n帧数: %d\n路径: %s') % (type_str, info.no_of_frames, info.texture_path))

    def _accept_selection(self):
        item = self._list.currentItem()
        if item:
            self.selected_sprite = item.text()
        self.accept()


# ===========================================================================
# TooltipPreviewDialog
# ===========================================================================

class TooltipPreviewDialog(QDialog):
    """tooltip 本地化预览对话框。"""
    def __init__(self, tooltip_key: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('Tooltip 预览'))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(_('键值: %s') % tooltip_key))

        rm = ResourceManager.instance()
        loc_text = rm.get_loc(tooltip_key)

        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setPlainText(loc_text)
        text_widget.setStyleSheet('background:#2a2a2a; color:#ddd;')
        text_widget.setMaximumHeight(150)
        layout.addWidget(text_widget)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_('关闭'))
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)


# ===========================================================================
# ShortcutsDialog
# ===========================================================================

class ShortcutsDialog(QDialog):
    """快捷键速查对话框。"""

    # SHORTCUTS 的类别名和动作名在 __init__ 中使用 _() 动态翻译，
    # 此处保留原始中文字符串作为翻译键。
    SHORTCUTS = [
        ('文件操作', [
            ('新建 GUI 文件',   'Ctrl+N'),
            ('打开 GUI 文件',   'Ctrl+O'),
            ('保存',           'Ctrl+S'),
            ('另存为',         'Ctrl+Shift+S'),
            ('退出',           'Ctrl+Q'),
        ]),
        ('编辑操作', [
            ('撤销',           'Ctrl+Z'),
            ('重做',           'Ctrl+Y'),
            ('全选',           'Ctrl+A'),
            ('复制控件',        'Ctrl+D'),
            ('删除控件',        'Delete'),
            ('复制',           'Ctrl+C'),
            ('粘贴',           'Ctrl+V'),
            ('查找控件',        'Ctrl+F'),
        ]),
        ('视图操作', [
            ('放大',           'Ctrl++'),
            ('缩小',           'Ctrl+-'),
            ('适应画布',        'Ctrl+0'),
            ('居中到选中',      'Ctrl+F'),
            ('缩放到选中',      'Ctrl+Shift+F'),
            ('显示/隐藏网格',   'Ctrl+G'),
            ('预览模式',        'Ctrl+P'),
            ('刷新画布',        'Ctrl+Shift+F5'),
            ('手动刷新资源',    'Ctrl+Shift+R'),
        ]),
        ('对齐操作', [
            ('左对齐',         'Ctrl+Alt+1'),
            ('右对齐',         'Ctrl+Alt+2'),
            ('水平居中',        'Ctrl+Alt+3'),
            ('顶部对齐',        'Ctrl+Alt+4'),
            ('底部对齐',        'Ctrl+Alt+5'),
            ('垂直居中',        'Ctrl+Alt+6'),
        ]),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('快捷键列表'))
        self.setMinimumSize(420, 480)
        layout = QVBoxLayout(self)

        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels([_('操作'), _('快捷键')])
        tree.setColumnWidth(0, 220)
        tree.setAlternatingRowColors(True)

        for category, shortcuts in self.SHORTCUTS:
            cat_item = QTreeWidgetItem([_(category), ''])
            cat_item.setFont(0, QFont('Microsoft YaHei', 9, QFont.Weight.Bold))
            for action, key in shortcuts:
                child = QTreeWidgetItem([_(action), key])
                child.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                cat_item.addChild(child)
            tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)

        layout.addWidget(tree)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        layout.addWidget(btns)


# ===========================================================================
# AboutDialog
# ===========================================================================

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from ..core.__version__ import (
            APP_NAME, APP_NAME_EN, VERSION, BUILD_DATE,
            AUTHOR, AUTHOR_EMAIL,
            GITHUB_URL, ISSUES_URL, RELEASES_URL,
            LICENSE_NAME, LICENSE_URL,
            DESCRIPTION_CN,
        )

        self.setWindowTitle(_('关于 %s') % APP_NAME)
        self.setMinimumWidth(500)
        self.setMinimumHeight(420)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 顶部横幅 ─────────────────────────────────────────────────────
        banner = QWidget()
        banner.setStyleSheet(
            f'background:{ThemeManager.accent_color()};'
        )
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(24, 20, 24, 16)
        banner_layout.setSpacing(4)

        name_lbl = QLabel(APP_NAME)
        name_lbl.setFont(QFont('Microsoft YaHei', 16, QFont.Weight.Bold))
        name_lbl.setStyleSheet('color:#ffffff; background:transparent;')
        banner_layout.addWidget(name_lbl)

        name_en_lbl = QLabel(APP_NAME_EN)
        name_en_lbl.setFont(QFont('Segoe UI', 9))
        name_en_lbl.setStyleSheet('color:rgba(255,255,255,180); background:transparent;')
        banner_layout.addWidget(name_en_lbl)

        ver_row = QHBoxLayout()
        ver_badge = QLabel(f' v{VERSION} ')
        ver_badge.setStyleSheet(
            'color:#ffffff; background:rgba(0,0,0,40);'
            'border-radius:3px; padding:1px 6px; font-size:10px; font-weight:bold;'
        )
        ver_row.addWidget(ver_badge)
        date_lbl = QLabel('  ' + (_('构建日期 %s') % BUILD_DATE))
        date_lbl.setStyleSheet('color:rgba(255,255,255,160); font-size:9px; background:transparent;')
        ver_row.addWidget(date_lbl)
        ver_row.addStretch()
        banner_layout.addLayout(ver_row)

        root.addWidget(banner)

        # ── 正文区域 ─────────────────────────────────────────────────────
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 16, 24, 12)
        body_layout.setSpacing(12)

        # 简介
        desc_lbl = QLabel(DESCRIPTION_CN)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet('font-size:10px; line-height:1.5;')
        body_layout.addWidget(desc_lbl)

        # 分隔线
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f'background:{ThemeManager.muted_color()}; opacity:0.3;')
        body_layout.addWidget(sep)

        # 功能列表（两列）
        feat_title = QLabel(_('主要功能'))
        feat_title.setFont(QFont('Microsoft YaHei', 9, QFont.Weight.Bold))
        body_layout.addWidget(feat_title)

        feats = [
            ('可视化编辑', '拖拽布局，实时精灵图渲染'),
            ('坐标系统', 'orientation + origo 精准实现'),
            ('精灵类型', 'spriteType/quadTextureSprite 完整支持'),
            ('代码视图', '实时 PDX 语法代码生成与导出'),
            ('本地化', '键解析与 tooltip 预览'),
            ('源码保留', 'patch 式保存，不破坏原始注释'),
            ('智能吸附', '边缘/中心/等距自动吸附对齐'),
            ('阵列镜像', '线性/圆形阵列 + 镜像复制'),
        ]
        feat_grid = QWidget()
        feat_grid_layout = QHBoxLayout(feat_grid)
        feat_grid_layout.setContentsMargins(0, 0, 0, 0)
        feat_grid_layout.setSpacing(12)
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        col1.setSpacing(3)
        col2.setSpacing(3)
        for i, (title, detail) in enumerate(feats):
            lbl = QLabel(
                f'<b>{_(title)}</b>  <span style="color:{ThemeManager.muted_color()}">{_(detail)}</span>'
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet('font-size:9px;')
            (col1 if i % 2 == 0 else col2).addWidget(lbl)
        feat_grid_layout.addLayout(col1, 1)
        feat_grid_layout.addLayout(col2, 1)
        body_layout.addWidget(feat_grid)

        # 另一条分隔线
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f'background:{ThemeManager.muted_color()}; opacity:0.3;')
        body_layout.addWidget(sep2)

        # 作者 + 链接行
        info_row = QHBoxLayout()

        author_lbl = QLabel(_('作者: ') + f'<b>{AUTHOR}</b>  <a href="mailto:{AUTHOR_EMAIL}">{AUTHOR_EMAIL}</a>')
        author_lbl.setOpenExternalLinks(True)
        author_lbl.setStyleSheet('font-size:9px;')
        info_row.addWidget(author_lbl, 1)

        links_lbl = QLabel(
            f'<a href="{GITHUB_URL}">GitHub</a>'
            + f'  ·  <a href="{RELEASES_URL}">' + _('发布页') + '</a>'
            + f'  ·  <a href="{ISSUES_URL}">' + _('反馈 Bug') + '</a>'
            + f'  ·  <a href="{LICENSE_URL}">{LICENSE_NAME}</a>'
        )
        links_lbl.setOpenExternalLinks(True)
        links_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        links_lbl.setStyleSheet('font-size:9px;')
        info_row.addWidget(links_lbl, 1)

        body_layout.addLayout(info_row)
        body_layout.addStretch()

        root.addWidget(body, 1)

        # ── 底部按钮 ─────────────────────────────────────────────────────
        foot = QWidget()
        foot.setStyleSheet(
            f'border-top:1px solid {ThemeManager.muted_color()};'
        )
        foot_layout = QHBoxLayout(foot)
        foot_layout.setContentsMargins(16, 8, 16, 8)

        copy_lbl = QLabel(f'© 2024–2026 {AUTHOR}  ·  {LICENSE_NAME}')
        copy_lbl.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:8px; border:none;')
        foot_layout.addWidget(copy_lbl, 1)

        close_btn = QPushButton(_('关闭'))
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        foot_layout.addWidget(close_btn)

        root.addWidget(foot)


# ===========================================================================
# UpdateDialog — 有新版本时弹出的提示对话框
# ===========================================================================

class UpdateDialog(QDialog):
    """
    有新版本可用时展示的提示对话框。

    按钮行为：
    - 前往下载  → 打开浏览器 Release 页，关闭对话框
    - 跳过此版本 → 将该版本写入 settings skip_version，关闭
    - 稍后提醒  → 直接关闭（下次启动仍会提示）
    """

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self._info = info
        self._settings = AppSettings.instance()

        self.setWindowTitle(_('发现新版本'))
        self.setMinimumWidth(480)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 16)

        # 标题行
        from ..core.__version__ import VERSION
        title = QLabel(
            _('发现新版本 ') + f'<b>{info["name"]}</b>'
            + f'  <span style="font-size:9px; color:{ThemeManager.muted_color()};">'
            + f'({info["date"]})</span>'
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setFont(QFont('Microsoft YaHei', 12))
        root.addWidget(title)

        cur_lbl = QLabel(
            _('当前版本：') + f'<span style="color:{ThemeManager.muted_color()};">v{VERSION}</span>'
        )
        cur_lbl.setTextFormat(Qt.TextFormat.RichText)
        cur_lbl.setStyleSheet('font-size:9px;')
        root.addWidget(cur_lbl)

        # Release Notes
        if info.get('body'):
            notes_lbl = QLabel(_('更新内容：'))
            notes_lbl.setStyleSheet('font-size:9px; font-weight:bold;')
            root.addWidget(notes_lbl)

            notes = QTextEdit()
            notes.setReadOnly(True)
            notes.setPlainText(info['body'])
            notes.setMaximumHeight(180)
            notes.setStyleSheet('font-size:9px;')
            root.addWidget(notes)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        skip_btn = QPushButton(_('跳过此版本'))
        skip_btn.setFixedWidth(100)
        skip_btn.clicked.connect(self._skip)
        btn_row.addWidget(skip_btn)

        btn_row.addStretch()

        later_btn = QPushButton(_('稍后提醒'))
        later_btn.setFixedWidth(80)
        later_btn.clicked.connect(self.reject)
        btn_row.addWidget(later_btn)

        download_btn = QPushButton(_('前往下载'))
        download_btn.setFixedWidth(90)
        download_btn.setDefault(True)
        download_btn.clicked.connect(self._download)
        btn_row.addWidget(download_btn)

        root.addLayout(btn_row)

    def _download(self):
        url = self._info.get('url', '')
        if url:
            try:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(url))
            except Exception:
                import subprocess
                subprocess.Popen(['start', url], shell=True)
        self.accept()

    def _skip(self):
        self._settings.set('skip_version', self._info.get('tag', ''))
        self.reject()
