"""
主窗口 — 群星 GUI 编辑器（完整功能版）。

新增功能：
  - 图层面板（可见性/锁定/Z轴排序）
  - 多选 + 对齐工具
  - 撤销/重做完整支持
  - 代码视图中高亮选中控件
  - 复制/粘贴
  - 重置所有修改
  - 自动保存
  - GUI 验证工具
"""
from __future__ import annotations
import os
import copy
import threading
import time
from typing import Optional, List, Tuple

from ..core.logger import get_logger
_log = get_logger('main_window')
from ..core import i18n as _i18n
from ..core.i18n import _

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QToolBar, QFileDialog, QMessageBox, QInputDialog,
    QTabWidget, QApplication, QSizePolicy, QProgressDialog,
    QPushButton, QDialog, QDialogButtonBox, QComboBox,
)
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QThread
from PySide6.QtGui import QAction, QKeySequence, QFont, QColor, QPixmap, QIcon

from ..core.gui_model import (
    GUIDocument, WidgetNode, parse_gui_file, parse_gui_text,
    create_widget, WIDGET_TYPES, WIDGET_LABELS,
    resolve_editor_layout_sizes,
)
from ..core.resource_manager import ResourceManager
from ..core.settings import AppSettings
from ..core.undo import (
    UndoStack, SetPropertyCommand, MoveWidgetCommand,
    AddWidgetCommand, DeleteWidgetCommand,
)
from ..codegen.gui_writer import write_document, save_document, write_widget_to_string

from .canvas import GUICanvas
from .properties_panel import PropertiesPanel
from .widget_library import WidgetLibrary, PresetLibrary
from .sprite_library import SpriteLibrary
from .file_browser import FileBrowser
from .code_view import CodeView
from .layer_panel import LayerPanel
from .button_effects_editor import ButtonEffectsEditor
from .virtual_groups_panel import VirtualGroupsPanel
from .event_link_panel import EventLinkPanel
from .name_warnings_panel import NameWarningsPanel
from .dialogs import SettingsDialog, NewFileDialog, AboutDialog, ShortcutsDialog
from .icon_provider import IconProvider
from ..core.virtual_groups import VirtualGroupManager
from ..core.theme_manager import ThemeManager


class _GuiLoadThread(QThread):
    """Background thread for loading large .gui files without blocking the UI."""
    # NOTE: named load_finished (not finished) to avoid collision with QThread.finished
    load_finished = Signal(object)   # GUIDocument
    error = Signal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        try:
            from ..core.gui_model import parse_gui_file
            doc = parse_gui_file(self._path)
            self.load_finished.emit(doc)
        except Exception as e:
            self.error.emit(str(e))


class _ResourceLoaderThread(QThread):
    """Background thread for loading game/mod resources without freezing the UI."""
    progress = Signal(str)   # status message
    # NOTE: named load_finished (not finished) to avoid collision with QThread's
    # built-in C++ finished signal, which would cause the slot to fire twice.
    load_finished = Signal()
    cancelled = Signal()
    error = Signal(str)

    def __init__(self, rm: 'ResourceManager', game_dir: str,
                 mod_dir: str, extra_dirs: list, parent=None):
        super().__init__(parent)
        self._rm = rm
        self._game_dir = game_dir
        self._mod_dir = mod_dir
        self._extra_dirs = extra_dirs
        self._cancel_event = threading.Event()

    def cancel(self):
        """Request cancellation. The thread will stop at the next checkpoint."""
        self._cancel_event.set()

    def run(self):
        t_start = time.monotonic()
        _log.info("资源加载线程启动: game=%s  mod=%s  extra=%s",
                  self._game_dir or '(无)', self._mod_dir or '(无)',
                  [os.path.basename(d) for d in self._extra_dirs])
        try:
            if self._game_dir:
                self.progress.emit(_('正在加载原版资源: ') + self._game_dir + ' ...')
                t = time.monotonic()
                self._rm.load_game_dir(self._game_dir, self._cancel_event)
                _log.info("游戏目录加载耗时 %.2fs", time.monotonic() - t)
            if self._cancel_event.is_set():
                _log.info("加载线程：game_dir 后取消，总耗时 %.2fs", time.monotonic() - t_start)
                self.cancelled.emit()
                return
            if self._mod_dir and os.path.isdir(self._mod_dir):
                self.progress.emit(_('正在加载模组: ') + os.path.basename(self._mod_dir) + ' ...')
                t = time.monotonic()
                self._rm.load_mod_dir(self._mod_dir, self._cancel_event)
                _log.info("模组目录加载耗时 %.2fs", time.monotonic() - t)
            if self._cancel_event.is_set():
                _log.info("加载线程：mod_dir 后取消，总耗时 %.2fs", time.monotonic() - t_start)
                self.cancelled.emit()
                return
            for extra in self._extra_dirs:
                if self._cancel_event.is_set():
                    _log.info("加载线程：extra_dirs 中取消，总耗时 %.2fs", time.monotonic() - t_start)
                    self.cancelled.emit()
                    return
                if os.path.isdir(extra):
                    self.progress.emit(_('正在加载额外目录: ') + os.path.basename(extra) + ' ...')
                    t = time.monotonic()
                    self._rm.load_extra_mod_dir(extra, self._cancel_event)
                    _log.info("额外目录 %s 加载耗时 %.2fs", os.path.basename(extra), time.monotonic() - t)
            _log.info("资源加载线程完成，总耗时 %.2fs", time.monotonic() - t_start)
            self.load_finished.emit()
        except Exception as e:
            _log.exception("资源加载线程异常: %s", e)
            self.error.emit(str(e))


def _icon(color: str, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


# Template for new GUI files (based on Stellaris custom GUI structure)
_NEW_GUI_TEMPLATE = '''\
@hide_x = 100000
@hide_y = 100000

guiTypes = {{

    containerWindowType = {{
        name = "{key}"
        orientation = center
        origo = center
        moveable = yes
        size = {{ width = 660 height = 300 }}

        background = {{
            name = "background"
            quadTextureSprite = "GFX_tile_outliner_bg"
        }}

        buttonType = {{
            name = "close"
            quadTextureSprite = "GFX_close"
            position = {{ x = -42 y = 12 }}
            Orientation = "UPPER_RIGHT"
            shortcut = "ESCAPE"
            clicksound = "back_click"
        }}

        instantTextBoxType = {{
            name = "my_header"
            font = "malgun_goth_24"
            text = "{key}"
            position = {{ x = 20 y = 5 }}
            maxWidth = 543
            maxHeight = 22
            fixedSize = yes
            alwaysTransparent = yes
        }}

        buttonType = {{
            name = "focus_button"
            position = {{ x = -1180 y = -1112 }}
            spriteType = "GFX_fleetview_focus"
        }}

        instantTextBoxType = {{
            name = "heading"
            font = "malgun_goth_24"
            position = {{ x = -1120 y = -115 }}
        }}

        buttonType = {{
            name = "alien_message_background"
            size = {{ x = 0 y = 0 }}
            position = {{ x = -1110 y = -11430 }}
            spriteType = "GFX_tiles_dark_area_cut_8"
        }}

        buttonType = {{
            name = "confirm_button"
            quadTextureSprite = "GFX_standard_button_142_34_button"
        }}

        containerWindowType = {{
            name = "portrait_background"
            position = {{ x = -1117 y = -1145 }}
            size = {{ width = 0 height = 0 }}
            iconType = {{ name = "event_picture" spriteType = "GFX_diplomacy_portrait_frame" }}
            iconType = {{ name = "portrait" spriteType = "GFX_portrait_character" }}
        }}

        containerWindowType = {{
            name = "portrait"
            position = {{ x = -1117 y = -1145 }}
            size = {{ width = 0 height = 0 }}
            iconType = {{ name = "portrait" spriteType = "GFX_portrait_gamesetup_mask" }}
            iconType = {{ name = "black_frame" spriteType = "GFX_diplomacy_portrait_shadow_frame" }}
            iconType = {{ name = "stripes_1" spriteType = "GFX_diplomacy_stripes_2" }}
            iconType = {{ name = "city_frame" spriteType = "GFX_diplomacy_portrait_frame" }}
        }}

        iconType = {{
            name = "empire_info_bg"
            spriteType = "GFX_diplomacy_dark_fade_bg"
        }}

        instantTextBoxType = {{
            name = "empire_name"
            font = "malgun_goth_24"
        }}

        instantTextBoxType = {{
            name = "empire_government_type"
            font = "cg_16b"
        }}

        instantTextBoxType = {{
            name = "empire_personality_type"
            font = "cg_16b"
        }}

        OverlappingElementsBoxType = {{
            name = "empire_ethics_icons"
            position = {{ x = -1145 y = -11138 }}
        }}

        iconType = {{
            name = "empire_flag"
            spriteType = "GFX_empire_flag_128"
            position = {{ x = -1125 y = -11235 }}
        }}

        containerWindowType = {{
            name = "leader_details"
            position = {{ x = -1125 y = -1175 }}
            containerWindowType = {{ name = "empire_traits_box" }}
            instantTextBoxType = {{ name = "empire_traits_label" font = "cg_16b" }}
            overlappingElementsBoxType = {{ name = "leader_traits" }}
            instantTextBoxType = {{ name = "leader_name" font = "cg_16b" }}
            instantTextBoxType = {{ name = "leader_species" font = "cg_16b" }}
        }}

        containerWindowType = {{
            name = "opinion_window"
            position = {{ x = -1127 y = -11110 }}
            size = {{ width = 94 height = 30 }}
            iconType = {{ name = "their_opinion_icon" spriteType = "GFX_diplomacy_opinion" }}
            instantTextBoxType = {{ name = "their_opinion" font = "cg_16b" }}
        }}

        containerWindowType = {{
            name = "EVENT_DIPLO"
            position = {{ x = 2 y = 50 }}
            moveable = no

            instantTextBoxType = {{
                name = "action_title"
                font = "malgun_goth_24"
                position = {{ x = 20 y = 0 }}
                maxWidth = 200
                alwaysTransparent = yes
            }}

            instantTextBoxType = {{
                name = "action_desc"
                font = "malgun_goth_24"
                position = {{ x = 490 y = 0 }}
                maxWidth = 500
                maxHeight = 180
                Orientation = "UPPER_LEFT"
                format = center
                alwaysTransparent = yes
                text_color_code = "H"
            }}

            listboxType = {{
                name = "option_list"
                position = {{ x = -11500 y = -1130 }}
            }}
        }}

        instantTextBoxType = {{
            name = "alien_message"
            font = "cg_16b"
            position = {{ x = 20 y = 100 }}
            maxWidth = 465
            maxHeight = 220
            format = left
            scrollbartype = "standardtext_slider"
        }}
    }}
}}
'''


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._settings = AppSettings.instance()
        # Apply saved UI language before building any UI
        _i18n.set_language(self._settings.get('ui_language', 'zh_CN'))
        self._rm = ResourceManager.instance()
        self._current_doc: Optional[GUIDocument] = None
        self._saved_doc_copy: Optional[GUIDocument] = None  # for reset
        self._mod_dir: str = ''
        self._undo_stack = UndoStack(on_change=self._on_undo_state_changed)
        self._preview_mode = False
        self._vgroup_manager = VirtualGroupManager()
        self._syncing_selection = False  # guard against canvas<->layer panel selection loops
        self._autosave_timer = QTimer()
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(60000)  # 60s auto-save
        self._autosave_timer.timeout.connect(self._auto_save)
        self._res_loader: Optional[_ResourceLoaderThread] = None
        # File actions — stored here for enable/disable during resource loading;
        # actual QAction objects are created in _setup_menu()
        self._act_new: Optional[QAction] = None
        self._act_open: Optional[QAction] = None
        self._act_save: Optional[QAction] = None
        self._act_save_as: Optional[QAction] = None
        self._act_load_mod: Optional[QAction] = None

        self.setWindowTitle(_('群星 GUI 编辑器'))
        self.setMinimumSize(1200, 800)
        self.resize(1720, 960)

        self._setup_central()
        self._setup_docks()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_connections()

        QTimer.singleShot(100, self._initial_load)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_central(self):
        # Wrap canvas in a container that includes a GUI-selector header bar.
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # --- GUI selector bar ---
        gui_bar = QWidget()
        gui_bar.setFixedHeight(30)
        # Use palette instead of hardcoded dark color so the bar follows the theme
        gui_bar.setObjectName('gui_selector_bar')
        bar_lay = QHBoxLayout(gui_bar)
        bar_lay.setContentsMargins(8, 0, 8, 0)
        bar_lay.setSpacing(6)

        bar_lbl = QLabel(_('自定义 GUI:'))
        bar_lbl.setStyleSheet('font-size:9px;')
        bar_lay.addWidget(bar_lbl)

        self._gui_selector = QComboBox()
        self._gui_selector.setMinimumWidth(260)
        self._gui_selector.setMaximumWidth(480)
        self._gui_selector.setStyleSheet('font-size:9px;')
        self._gui_selector.setToolTip(
            _('当前文件中所有顶层 containerWindowType（完整自定义 GUI）。\n'
              '选择后事件面板自动筛选，点击"定位"可在画布中居中该 GUI。')
        )
        self._gui_selector.currentIndexChanged.connect(self._on_gui_selector_changed)
        bar_lay.addWidget(self._gui_selector)

        accent = self._settings.accent_color or '#0e639c'
        locate_btn = QPushButton(_('定位'))
        locate_btn.setFixedWidth(46)
        locate_btn.setFixedHeight(22)
        locate_btn.setStyleSheet(
            f'background:{accent}; color:#fff; border:none; border-radius:3px; font-size:9px;'
        )
        locate_btn.setToolTip(_('在画布中居中显示所选 GUI'))
        locate_btn.clicked.connect(self._locate_selected_gui)
        bar_lay.addWidget(locate_btn)
        bar_lay.addStretch()

        central_layout.addWidget(gui_bar)

        # --- Canvas ---
        self._canvas = GUICanvas(self)
        self._canvas.gui_scene.undo_stack = self._undo_stack
        central_layout.addWidget(self._canvas, 1)

        self.setCentralWidget(central)

    def _setup_docks(self):
        # 左侧：控件库 + 预设库 + 文件浏览器
        left_dock = QDockWidget(_('库'), self)
        left_dock.setObjectName('left_dock')
        left_dock.setMinimumWidth(220)
        left_tabs = QTabWidget()
        self._widget_lib = WidgetLibrary()
        left_tabs.addTab(self._widget_lib, _('控件库'))
        self._preset_lib = PresetLibrary()
        left_tabs.addTab(self._preset_lib, _('预设库'))
        self._file_browser = FileBrowser()
        left_tabs.addTab(self._file_browser, _('文件'))
        left_dock.setWidget(left_tabs)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)

        # 左下：图层面板
        layer_dock = QDockWidget(_('图层'), self)
        layer_dock.setObjectName('layer_dock')
        self._layer_panel = LayerPanel()
        layer_dock.setWidget(self._layer_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, layer_dock)

        # 左下：虚拟编组面板
        vgroup_dock = QDockWidget(_('编组'), self)
        vgroup_dock.setObjectName('vgroup_dock')
        self._vgroup_panel = VirtualGroupsPanel()
        vgroup_dock.setWidget(self._vgroup_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, vgroup_dock)
        self.tabifyDockWidget(layer_dock, vgroup_dock)
        layer_dock.raise_()  # 默认显示图层标签页

        # 右侧：属性面板 + 精灵图库
        props_dock = QDockWidget(_('属性'), self)
        props_dock.setObjectName('props_dock')
        props_dock.setMinimumWidth(270)
        self._props_panel = PropertiesPanel()
        props_dock.setWidget(self._props_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        sprite_dock = QDockWidget(_('精灵图库'), self)
        sprite_dock.setObjectName('sprite_dock')
        self._sprite_lib = SpriteLibrary()
        sprite_dock.setWidget(self._sprite_lib)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, sprite_dock)
        self.tabifyDockWidget(props_dock, sprite_dock)
        props_dock.raise_()

        # 下方：代码视图
        be_dock = QDockWidget(_('Button Effects 编辑器'), self)
        self._be_editor = ButtonEffectsEditor()
        be_dock.setWidget(self._be_editor)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, be_dock)
        be_dock.hide()   # hidden by default; user opens via menu

        code_dock = QDockWidget(_('代码视图'), self)
        code_dock.setObjectName('code_dock')
        code_dock.setMinimumHeight(140)
        self._code_view = CodeView()
        code_dock.setWidget(self._code_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, code_dock)

        # 名称重复警告面板
        warnings_dock = QDockWidget(_('名称警告'), self)
        warnings_dock.setObjectName('warnings_dock')
        self._warnings_panel = NameWarningsPanel()
        warnings_dock.setWidget(self._warnings_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, warnings_dock)
        self.tabifyDockWidget(code_dock, warnings_dock)
        code_dock.raise_()

        # 右侧：事件关联面板
        event_dock = QDockWidget(_('事件关联'), self)
        event_dock.setObjectName('event_dock')
        event_dock.setMinimumWidth(260)
        self._event_panel = EventLinkPanel()
        event_dock.setWidget(self._event_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, event_dock)
        self.tabifyDockWidget(sprite_dock, event_dock)
        props_dock.raise_()

    def _setup_menu(self):
        mb = self.menuBar()

        # ---- 文件 ----
        file_menu = mb.addMenu(_('文件(&F)'))
        self._act_new = file_menu.addAction(_('新建 GUI 文件(&N)'), self._new_file)
        self._act_new.setShortcut(QKeySequence.StandardKey.New)
        self._act_open = file_menu.addAction(_('打开 GUI 文件(&O)...'), self._open_file)
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_load_mod = file_menu.addAction(_('打开模组目录(&M)...'), self._open_mod_dir)
        file_menu.addSeparator()
        self._act_save = file_menu.addAction(_('保存(&S)'), self._save)
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save_as = file_menu.addAction(_('另存为(&A)...'), self._save_as)
        self._act_save_as.setShortcut(QKeySequence('Ctrl+Shift+S'))
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu(_('最近文件'))
        self._update_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction(_('退出(&Q)'), self.close).setShortcut(QKeySequence.StandardKey.Quit)

        # ---- 编辑 ----
        edit_menu = mb.addMenu(_('编辑(&E)'))

        self._act_undo = edit_menu.addAction(_('撤销(&Z)'))
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self._undo)

        self._act_redo = edit_menu.addAction(_('重做(&Y)'))
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_redo.setEnabled(False)
        self._act_redo.triggered.connect(self._redo)

        edit_menu.addSeparator()
        edit_menu.addAction(_('全选(&A)'), self._canvas.select_all).setShortcut(QKeySequence.StandardKey.SelectAll)
        edit_menu.addAction(_('复制控件(&D)'), self._duplicate_widget).setShortcut(QKeySequence('Ctrl+D'))
        edit_menu.addAction(_('删除控件(&X)'), self._delete_widget).setShortcut(QKeySequence.StandardKey.Delete)
        edit_menu.addSeparator()
        edit_menu.addAction(_('复制 (Ctrl+C)'), self._copy_selected).setShortcut(QKeySequence.StandardKey.Copy)
        edit_menu.addAction(_('粘贴 (Ctrl+V)'), self._paste_selected).setShortcut(QKeySequence.StandardKey.Paste)
        edit_menu.addSeparator()
        edit_menu.addAction(_('保存选中为预设...'), self._save_preset)
        edit_menu.addSeparator()
        edit_menu.addAction(_('查找控件(&F)'), self._find_widget).setShortcut(QKeySequence('Ctrl+F'))

        # Reset submenu (防误触)
        reset_menu = edit_menu.addMenu(_('重置'))
        reset_menu.addAction(_('重置当前文件的所有修改'), self._reset_all_changes)

        # ---- 视图 ----
        view_menu = mb.addMenu(_('视图(&V)'))
        view_menu.addAction(_('适应画布(&0)'), self._canvas.fit_to_canvas).setShortcut(QKeySequence('Ctrl+0'))
        view_menu.addAction(_('放大(&+)'), self._canvas.zoom_in).setShortcut(QKeySequence.StandardKey.ZoomIn)
        view_menu.addAction(_('缩小(&-)'), self._canvas.zoom_out).setShortcut(QKeySequence.StandardKey.ZoomOut)
        view_menu.addAction(_('居中到选中 (Ctrl+F)'), self._canvas.center_on_selected).setShortcut(QKeySequence('Ctrl+F'))
        view_menu.addAction(_('缩放到选中 (Ctrl+Shift+F)'), self._canvas.zoom_to_selection).setShortcut(QKeySequence('Ctrl+Shift+F'))
        view_menu.addSeparator()

        self._act_grid = view_menu.addAction(_('显示网格(&G)'))
        self._act_grid.setCheckable(True)
        self._act_grid.setChecked(self._settings.show_grid)
        self._act_grid.setShortcut(QKeySequence('Ctrl+G'))
        self._act_grid.triggered.connect(self._toggle_grid)

        self._act_snap = view_menu.addAction(_('吸附网格(&S)'))
        self._act_snap.setCheckable(True)
        self._act_snap.setChecked(self._settings.snap_to_grid)
        self._act_snap.triggered.connect(self._toggle_snap)

        view_menu.addSeparator()
        self._act_preview = view_menu.addAction(_('预览模式(&P)'))
        self._act_preview.setCheckable(True)
        self._act_preview.setShortcut(QKeySequence('Ctrl+P'))
        self._act_preview.triggered.connect(self._toggle_preview)
        self._act_editor_scrollbars = view_menu.addAction(_('显示编辑器滑条(&B)'))
        self._act_editor_scrollbars.setCheckable(True)
        self._act_editor_scrollbars.setChecked(self._settings.show_editor_scrollbars)
        self._act_editor_scrollbars.setToolTip(
            _('关闭后隐藏画布上由编辑器生成的预览用滑条，避免遮挡或与游戏布局不一致'))
        self._act_editor_scrollbars.triggered.connect(self._toggle_editor_scrollbars)
        view_menu.addSeparator()
        view_menu.addAction(_('重新加载所有精灵图'), self._reload_sprites)
        view_menu.addAction(_('刷新画布(&F5)'), self._refresh_canvas).setShortcut(
            QKeySequence('Ctrl+Shift+F5')
        )

        # ---- 工作区 ----
        ws_menu = mb.addMenu(_('工作区(&W)'))
        ws_menu.addAction(_('添加文件夹到工作区...'), self._add_workspace_folder)
        ws_menu.addAction(_('管理工作区文件夹...'), self._manage_workspace_folders)
        ws_menu.addSeparator()
        self._ws_folders_menu = ws_menu.addMenu(_('快速切换模组'))
        ws_menu.aboutToShow.connect(self._update_ws_folders_menu)

        # ---- 排列 ----
        arrange_menu = mb.addMenu(_('排列(&A)'))
        # 对齐
        arrange_menu.addAction(_('左对齐'), lambda: self._align('left')).setShortcut(QKeySequence('Ctrl+Alt+1'))
        arrange_menu.addAction(_('右对齐'), lambda: self._align('right')).setShortcut(QKeySequence('Ctrl+Alt+2'))
        arrange_menu.addAction(_('水平居中'), lambda: self._align('hcenter')).setShortcut(QKeySequence('Ctrl+Alt+3'))
        arrange_menu.addAction(_('顶部对齐'), lambda: self._align('top')).setShortcut(QKeySequence('Ctrl+Alt+4'))
        arrange_menu.addAction(_('底部对齐'), lambda: self._align('bottom')).setShortcut(QKeySequence('Ctrl+Alt+5'))
        arrange_menu.addAction(_('垂直居中'), lambda: self._align('vcenter')).setShortcut(QKeySequence('Ctrl+Alt+6'))
        arrange_menu.addSeparator()
        # 分布
        arrange_menu.addAction(_('水平均匀分布'), lambda: self._align('hdistrib'))
        arrange_menu.addAction(_('垂直均匀分布'), lambda: self._align('vdistrib'))
        arrange_menu.addSeparator()
        # 阵列
        arrange_menu.addAction(_('线性阵列...'), self._linear_array).setShortcut(QKeySequence('Ctrl+Shift+L'))
        arrange_menu.addAction(_('圆形阵列...'), self._circular_array).setShortcut(QKeySequence('Ctrl+Shift+O'))
        arrange_menu.addSeparator()
        # 镜像
        arrange_menu.addAction(_('水平镜像'), lambda: self._mirror('h'))
        arrange_menu.addAction(_('垂直镜像'), lambda: self._mirror('v'))
        arrange_menu.addAction(_('镜像复制...'), self._mirror_dialog)
        arrange_menu.addSeparator()
        # 尺寸
        arrange_menu.addAction(_('相同宽度'), lambda: self._canvas.gui_scene.make_same_size('width'))
        arrange_menu.addAction(_('相同高度'), lambda: self._canvas.gui_scene.make_same_size('height'))
        arrange_menu.addAction(_('相同尺寸'), lambda: self._canvas.gui_scene.make_same_size('both'))

        # ---- 工具 ----
        tools_menu = mb.addMenu(_('工具(&T)'))
        tools_menu.addAction(_('设置(&,)...'), self._open_settings).setShortcut(QKeySequence('Ctrl+,'))
        tools_menu.addSeparator()
        tools_menu.addAction(_('生成 .gfx 精灵注册文件...'), self._generate_gfx)
        tools_menu.addSeparator()
        tools_menu.addAction(_('验证当前 GUI 文件...'), self._validate_gui)
        tools_menu.addSeparator()
        tools_menu.addAction(_('Button Effects 编辑器...'), self._open_be_editor)
        tools_menu.addSeparator()
        tools_menu.addAction(_('手动刷新资源'), self._manual_refresh_resources).setShortcut(
            QKeySequence('Ctrl+Shift+R')
        )

        # ---- 帮助 ----
        help_menu = mb.addMenu(_('帮助(&H)'))
        help_menu.addAction(_('快捷键列表...'), lambda: ShortcutsDialog(self).exec())
        help_menu.addSeparator()
        help_menu.addAction(_('关于...'), lambda: AboutDialog(self).exec())

    def _setup_toolbar(self):
        tb = self.addToolBar(_('主工具栏'))
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self._toolbar = tb
        self._toolbar_icon_actions: list[tuple[QAction, str]] = []

        def _add(label, cb, tip='', icon_name=''):
            a = QAction(label, self)
            if icon_name:
                a.setIcon(IconProvider.themed_icon(icon_name, 18))
                self._toolbar_icon_actions.append((a, icon_name))
            a.triggered.connect(cb)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return a

        _add(_('新建'), self._new_file, _('新建 GUI 文件'), 'new-file')
        _add(_('打开'), self._open_file, _('打开 .gui 文件'), 'open-file')
        _add(_('保存'), self._save, _('保存 (Ctrl+S)'), 'save')
        tb.addSeparator()

        self._tb_undo = _add(_('撤销'), self._undo, _('撤销 (Ctrl+Z)'), 'undo')
        self._tb_undo.setEnabled(False)
        self._tb_redo = _add(_('重做'), self._redo, _('重做 (Ctrl+Y)'), 'redo')
        self._tb_redo.setEnabled(False)
        tb.addSeparator()

        _add(_('适应画布'), self._canvas.fit_to_canvas, _('适应画布 (Ctrl+0)'), 'zoom-fit')
        _add(_('放大+'), self._canvas.zoom_in, _('放大'), 'zoom-in')
        _add(_('缩小-'), self._canvas.zoom_out, _('缩小'), 'zoom-out')
        _add(_('居中'), self._canvas.center_on_selected, _('居中到选中 (Ctrl+F)'), 'center-view')
        tb.addSeparator()

        _add(_('复制控件'), self._duplicate_widget, _('复制控件 (Ctrl+D)'), 'duplicate')
        _add(_('删除控件'), self._delete_widget, _('删除选中控件 (Del)'), 'delete')
        tb.addSeparator()

        _add(_('左对齐'), lambda: self._align('left'), _('左对齐'), 'align-left')
        _add(_('水平居中'), lambda: self._align('hcenter'), _('水平居中'), 'align-h-center')
        _add(_('右对齐'), lambda: self._align('right'), _('右对齐'), 'align-right')
        _add(_('顶对齐'), lambda: self._align('top'), _('顶部对齐'), 'align-top')
        _add(_('垂直居中'), lambda: self._align('vcenter'), _('垂直居中'), 'align-v-center')
        _add(_('底对齐'), lambda: self._align('bottom'), _('底部对齐'), 'align-bottom')
        tb.addSeparator()

        self._tb_preview = QAction(_('预览模式'), self)
        self._tb_preview.setCheckable(True)
        self._tb_preview.setIcon(IconProvider.themed_icon('preview', 18))
        self._toolbar_icon_actions.append((self._tb_preview, 'preview'))
        self._tb_preview.setToolTip(_('切换预览模式 (Ctrl+P)'))
        self._tb_preview.triggered.connect(self._toggle_preview)
        tb.addAction(self._tb_preview)
        tb.addSeparator()

        # Refresh canvas button
        _add(_('刷新画布'), self._refresh_canvas, _('强制刷新画布显示 (Ctrl+Shift+F5)'),
             'refresh')

        tb.addSeparator()
        # Language selector
        self._lang_label = QLabel(_('  本地化: '))
        lang_label = self._lang_label
        lang_label.setStyleSheet(f'color:{ThemeManager.muted_color()};')
        tb.addWidget(lang_label)
        self._lang_combo = QComboBox()
        self._lang_combo.setMinimumWidth(120)
        self._lang_combo.setToolTip(_('切换本地化语言'))
        self._lang_combo.addItem(_('（未加载）'), '')
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        tb.addWidget(self._lang_combo)

    def _setup_statusbar(self):
        self._status = self.statusBar()
        self._pos_label = QLabel('')
        self._status.addPermanentWidget(self._pos_label)
        self._sel_count_label = QLabel('')
        self._status.addPermanentWidget(self._sel_count_label)
        self._sprite_label = QLabel('')
        self._status.addPermanentWidget(self._sprite_label)
        self._zoom_label = QLabel('100%')
        self._status.addPermanentWidget(self._zoom_label)

        # 常驻游戏/模组加载状态指示器
        self._game_status_icon = QLabel()
        self._game_status_icon.setPixmap(IconProvider.pixmap('circle-empty', 10, '#e74c3c'))
        self._game_status_icon.setFixedSize(14, 14)
        self._status.addPermanentWidget(self._game_status_icon)
        self._game_status_label = QLabel(_('未配置游戏目录'))
        self._game_status_label.setStyleSheet('color:#f39c12; font-size:9px; padding:0 6px;')
        self._game_status_label.setToolTip(_('游戏目录加载状态。前往 工具→设置 配置游戏目录。'))
        self._status.addPermanentWidget(self._game_status_label)

        self._mod_status_icon = QLabel()
        self._mod_status_icon.setFixedSize(14, 14)
        self._mod_status_icon.setVisible(False)
        self._status.addPermanentWidget(self._mod_status_icon)
        self._mod_status_label = QLabel('')
        self._mod_status_label.setStyleSheet('color:#3498db; font-size:9px; padding:0 6px;')
        self._status.addPermanentWidget(self._mod_status_label)

        # 加载取消按钮（仅在资源加载期间显示）
        self._cancel_load_btn = QPushButton(_('取消加载'))
        self._cancel_load_btn.setIcon(QIcon(IconProvider.pixmap('close', 10, '#e74c3c')))
        self._cancel_load_btn.setFixedHeight(18)
        self._cancel_load_btn.setStyleSheet(
            'QPushButton { font-size:9px; padding:0 6px; color:#e74c3c;'
            ' background:transparent; border:1px solid #e74c3c; border-radius:2px; }'
            'QPushButton:hover { background:#e74c3c; color:#fff; }'
        )
        self._cancel_load_btn.setVisible(False)
        self._cancel_load_btn.clicked.connect(self._cancel_loading)
        self._status.addPermanentWidget(self._cancel_load_btn)

        self._status.showMessage(_('就绪。请打开模组目录或 .gui 文件开始编辑。'))

    def _update_game_status_indicator(self):
        """更新状态栏中的游戏目录状态指示器。"""
        if self._rm.game_dir and self._rm.sprite_count > 0:
            self._game_status_icon.setPixmap(
                IconProvider.pixmap('circle-filled', 10, '#2ecc71'))
            self._game_status_label.setText(
                _('游戏已加载 (') + str(self._rm.sprite_count) + _(' 精灵图)'))
            self._game_status_label.setStyleSheet(
                'color:#2ecc71; font-size:9px; padding:0 6px;')
        elif self._rm.game_dir:
            self._game_status_icon.setPixmap(
                IconProvider.pixmap('circle-filled', 10, '#f39c12'))
            self._game_status_label.setText(_('游戏目录已配置'))
            self._game_status_label.setStyleSheet(
                'color:#f39c12; font-size:9px; padding:0 6px;')
        else:
            self._game_status_icon.setPixmap(
                IconProvider.pixmap('circle-empty', 10, '#e74c3c'))
            self._game_status_label.setText(_('未配置游戏目录'))
            self._game_status_label.setStyleSheet(
                'color:#e74c3c; font-size:9px; padding:0 6px;')

    def _update_mod_status_indicator(self):
        """更新状态栏中的模组加载状态指示器。"""
        if self._mod_dir:
            mod_name = os.path.basename(self._mod_dir)
            self._mod_status_icon.setPixmap(
                IconProvider.pixmap('circle-filled', 10, '#3498db'))
            self._mod_status_icon.setVisible(True)
            self._mod_status_label.setText(_('模组: ') + mod_name)
            self._mod_status_label.setToolTip(self._mod_dir)
        else:
            self._mod_status_icon.setVisible(False)
            self._mod_status_label.setText('')

    def _setup_connections(self):
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.node_property_changed.connect(self._on_node_changed)
        # node_position_changed: only update props panel (NOT the canvas item — would cause loop)
        self._canvas.node_position_changed.connect(self._on_node_position_changed)
        self._canvas.document_modified.connect(self._on_document_modified)
        self._canvas.cursor_pos_changed.connect(self._on_cursor_pos)

        self._props_panel.property_changed.connect(self._on_property_edited)
        self._props_panel.widget_renamed.connect(self._on_widget_renamed)
        self._widget_lib.add_widget_requested.connect(self._add_widget_from_library)
        self._sprite_lib.sprite_selected.connect(self._assign_sprite)
        self._file_browser.open_file_requested.connect(self._open_gui_file)
        self._code_view.code_applied.connect(self._apply_code)
        self._preset_lib.insert_preset_requested.connect(self._insert_preset)
        self._preset_lib.save_preset_requested.connect(self._save_preset)

        # Layer panel
        self._layer_panel.node_selected.connect(self._on_layer_node_selected)
        self._layer_panel.visibility_changed.connect(self._on_visibility_changed)
        self._layer_panel.lock_changed.connect(self._on_lock_changed)
        self._layer_panel.order_changed.connect(self._on_order_changed)
        self._layer_panel.structure_changed.connect(self._on_layer_structure_changed)

        # Virtual groups panel
        self._vgroup_panel.set_canvas(self._canvas)
        self._vgroup_panel.visibility_changed.connect(self._on_vgroup_visibility_changed)

        # Name warnings panel
        self._warnings_panel.set_canvas(self._canvas)

        # Event link panel
        self._event_panel.event_selected.connect(self._on_event_selected)

        # Canvas scene settings
        self._canvas.gui_scene.grid_size = self._settings.grid_size
        self._canvas.gui_scene.snap_to_grid = self._settings.snap_to_grid

    # ------------------------------------------------------------------
    # Initial load
    # ------------------------------------------------------------------

    def _initial_load(self):
        game_dir = self._settings.game_dir or self._settings.detect_game_dir()
        if game_dir:
            self._settings.game_dir = game_dir

        last_mod = self._settings.last_mod_dir
        if last_mod and os.path.isdir(last_mod):
            self._mod_dir = last_mod

        # Collect all extra dirs (extra_mod_dirs + enabled workspace folders)
        extra_dirs: List[str] = list(self._settings.extra_mod_dirs or [])
        for wf in (self._settings.workspace_folders or []):
            p = wf.get('path', '')
            if wf.get('enabled', True) and p and os.path.isdir(p):
                extra_dirs.append(p)

        if not game_dir:
            self._status.showMessage(_('未配置游戏目录。请前往 工具→设置 进行配置。'))
            self._update_game_status_indicator()
            self._update_mod_status_indicator()
            return

        # Disable actions that depend on resources being loaded
        self._set_loading_state(True)
        self._status.showMessage(_('正在后台加载资源，请稍候...'))

        self._cancel_load_btn.setEnabled(True)
        self._res_loader = _ResourceLoaderThread(
            self._rm, game_dir,
            last_mod if (last_mod and os.path.isdir(last_mod)) else '',
            extra_dirs,
            self,
        )
        self._res_loader.progress.connect(self._status.showMessage)
        self._res_loader.load_finished.connect(self._on_resources_loaded)
        self._res_loader.cancelled.connect(self._on_loading_cancelled)
        self._res_loader.error.connect(self._on_resources_error)
        self._res_loader.start()

    def _set_loading_state(self, loading: bool):
        """Disable/enable UI actions that require resources to be loaded."""
        enabled = not loading
        for act in (self._act_open, self._act_new, self._act_save,
                    self._act_save_as, self._act_load_mod):
            if act is not None:
                act.setEnabled(enabled)
        self._cancel_load_btn.setVisible(loading)
        if loading:
            self._game_status_icon.setPixmap(
                IconProvider.pixmap('loading', 10, '#f39c12'))
            self._game_status_label.setText(_('资源加载中...'))
            self._game_status_label.setStyleSheet('color:#f39c12; font-size:9px; padding:0 6px;')

    def _cancel_loading(self):
        """取消当前正在进行的资源加载。"""
        if self._res_loader and self._res_loader.isRunning():
            _log.info("用户点击取消加载")
            self._res_loader.cancel()
            self._status.showMessage(_('正在取消加载，请稍候...'))
            self._cancel_load_btn.setEnabled(False)
        else:
            _log.warning("取消加载：加载线程不在运行状态")

    def _on_resources_loaded(self):
        """Called on the GUI thread when _ResourceLoaderThread finishes."""
        self._set_loading_state(False)
        game_dir = self._settings.game_dir
        last_mod = self._mod_dir

        _log.info("主线程：开始更新 UI（精灵图库 + 文件浏览器）...")
        t = time.monotonic()
        self._sprite_lib.populate()
        _log.debug("精灵图库更新耗时 %.2fs", time.monotonic() - t)
        t = time.monotonic()
        self._file_browser.set_directories(game_dir or '', last_mod or '')
        _log.debug("文件浏览器更新耗时 %.2fs", time.monotonic() - t)
        if last_mod:
            self._be_editor.set_mod_dir(last_mod)

        self._status.showMessage(
            _('已加载 ') + str(self._rm.sprite_count) + _(' 个精灵图，') + str(self._rm.loc_count) + _(' 条本地化。')
        )
        _log.info("资源加载完成: %d 精灵图 / %d 本地化", self._rm.sprite_count, self._rm.loc_count)
        self._update_game_status_indicator()
        self._update_mod_status_indicator()

    def _on_resources_error(self, msg: str):
        """Called on the GUI thread when _ResourceLoaderThread encounters an error."""
        self._set_loading_state(False)
        self._status.showMessage(_('资源加载出错: ') + msg)
        self._update_game_status_indicator()
        self._update_mod_status_indicator()

    def _on_loading_cancelled(self):
        """Called on the GUI thread when the user cancels loading."""
        _log.info("资源加载已取消（主线程回调）")
        self._set_loading_state(False)
        self._cancel_load_btn.setEnabled(True)
        # 清除 last_mod_dir，避免下次启动再次自动加载被取消的模组
        self._settings.last_mod_dir = ''
        self._mod_dir = ''
        self._status.showMessage(_('已取消加载。资源仅部分加载，精灵图和本地化数据可能不完整。'))
        self._update_game_status_indicator()
        self._update_mod_status_indicator()

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _new_file(self):
        dlg = NewFileDialog(self._mod_dir, self)
        if dlg.exec():
            file_path = dlg.get_file_path()
            gui_key = dlg.get_gui_key()
            # Build from template with user-specified key
            template_text = _NEW_GUI_TEMPLATE.format(key=gui_key)
            try:
                doc = parse_gui_text(template_text, file_path)
            except Exception:
                doc = GUIDocument(file_path=file_path)
            self._load_document(doc)
            self._undo_stack.clear()

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, _('打开 GUI 文件'),
            self._settings.get('last_open_dir', ''),
            _('GUI 文件 (*.gui *.guicore);;所有文件 (*.*)')
        )
        if path:
            self._settings.set('last_open_dir', os.path.dirname(path))
            self._open_gui_file(path)

    def _open_gui_file(self, path: str):
        if not os.path.isfile(path):
            QMessageBox.warning(self, _('文件未找到'), _('文件不存在:\n') + path)
            return

        file_size = os.path.getsize(path)
        # Use async loading for files > 200 KB to keep UI responsive
        if file_size > 200_000:
            self._open_gui_file_async(path)
        else:
            try:
                doc = parse_gui_file(path)
                self._finish_open_gui_file(doc, path)
            except Exception as e:
                QMessageBox.critical(self, _('错误'), _('打开文件失败:\n') + str(e))

    def _open_gui_file_async(self, path: str):
        progress = QProgressDialog(_('正在加载 ') + os.path.basename(path) + '...', _('取消'), 0, 0, self)
        progress.setWindowTitle(_('打开大文件'))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        self._load_thread = _GuiLoadThread(path, self)

        def on_finished(doc):
            progress.close()
            self._finish_open_gui_file(doc, path)

        def on_error(msg):
            progress.close()
            QMessageBox.critical(self, _('错误'), _('打开文件失败:\n') + msg)

        def on_cancelled():
            if hasattr(self, '_load_thread'):
                self._load_thread.quit()

        self._load_thread.load_finished.connect(on_finished)
        self._load_thread.error.connect(on_error)
        progress.canceled.connect(on_cancelled)
        self._load_thread.start()

    def _finish_open_gui_file(self, doc, path: str):
        self._load_document(doc)
        self._undo_stack.clear()
        self._settings.add_recent_file(path)
        self._update_recent_menu()
        total = sum(1 for _ in doc.all_widgets())
        self._status.showMessage(
            _('已打开: ') + os.path.basename(path) + _('  (') + str(total) + _(' 个控件)')
        )

    def _open_mod_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, _('打开模组目录'),
            self._settings.get('last_open_dir', '')
        )
        if path:
            self._load_mod_dir(path)

    def _load_mod_dir(self, path: str):
        """Load a mod directory in a background thread (non-blocking)."""
        self._mod_dir = path
        # 注意：仅在加载成功后（_on_mod_loaded）才写入 last_mod_dir
        # 避免因卡死/取消导致下次启动仍自动加载同一问题目录
        self._settings.add_recent_mod_dir(path)
        self._settings.set('last_open_dir', path)

        extra_dirs: List[str] = list(self._settings.extra_mod_dirs or [])
        for wf in (self._settings.workspace_folders or []):
            p = wf.get('path', '')
            if wf.get('enabled', True) and p and os.path.isdir(p):
                extra_dirs.append(p)

        self._set_loading_state(True)
        self._cancel_load_btn.setEnabled(True)
        self._status.showMessage(_('正在后台加载模组: ') + os.path.basename(path) + ' ...')

        self._res_loader = _ResourceLoaderThread(
            self._rm, '',   # game_dir already loaded; skip it
            path, extra_dirs, self,
        )
        self._res_loader.progress.connect(self._status.showMessage)
        self._res_loader.load_finished.connect(self._on_mod_loaded)
        self._res_loader.cancelled.connect(self._on_loading_cancelled)
        self._res_loader.error.connect(self._on_resources_error)
        self._res_loader.start()

    def _on_mod_loaded(self):
        """Called on the GUI thread when a mod directory finishes loading."""
        self._set_loading_state(False)
        game_dir = self._settings.game_dir
        path = self._mod_dir
        # 加载成功，现在才持久化 last_mod_dir
        self._settings.last_mod_dir = path

        _log.info("主线程：模组加载后更新 UI: %s", path)
        t = time.monotonic()
        self._sprite_lib.populate()
        _log.debug("精灵图库更新耗时 %.2fs", time.monotonic() - t)
        t = time.monotonic()
        self._file_browser.set_directories(game_dir, path)
        _log.debug("文件浏览器更新耗时 %.2fs", time.monotonic() - t)
        self._be_editor.set_mod_dir(path)
        self._update_language_combo()
        self._status.showMessage(
            _('模组已加载: ') + os.path.basename(path) + '  ('
            + str(self._rm.sprite_count) + _(' 精灵图 / ') + str(self._rm.loc_count) + _(' 本地化)')
        )
        _log.info("模组加载完成: %s — %d 精灵图 / %d 本地化", path,
                  self._rm.sprite_count, self._rm.loc_count)
        self._update_mod_status_indicator()
        self._update_game_status_indicator()

    def _load_document(self, doc: GUIDocument):
        self._current_doc = doc
        # Save a deep copy for reset
        self._saved_doc_copy = copy.deepcopy(doc)
        self._canvas.load_document(doc)
        self._code_view.set_document(doc)
        self._layer_panel.populate(doc)
        self._props_panel.set_doc(doc)
        # Load virtual groups sidecar
        if doc.file_path:
            self._vgroup_manager.load(doc.file_path)
        else:
            self._vgroup_manager = VirtualGroupManager()
        self._vgroup_panel.set_doc(doc, self._vgroup_manager)
        self._warnings_panel.set_doc(doc)
        fname = os.path.basename(doc.file_path) if doc.file_path else _('未命名')
        self.setWindowTitle(_('群星 GUI 编辑器 — ') + fname)
        self._props_panel.set_node(None)
        # Populate GUI selector bar
        all_gui_names = self._get_all_gui_names(doc)
        self._populate_gui_selector(all_gui_names)
        # Notify event panel with ALL top-level GUI names so events for any are shown
        self._event_panel.set_gui_names(all_gui_names)
        # Clear any previous event context
        self._canvas.gui_scene.set_event_context(None)
        # Start auto-save timer
        self._autosave_timer.start()

    def _get_all_gui_names(self, doc: 'GUIDocument') -> List[str]:
        """Return names of every top-level containerWindowType in the document.

        In Stellaris, the top-level containerWindowType nodes inside guiTypes are
        complete independent custom GUIs.  A single .gui file can define several.
        Each one's 'name' attribute is the key referenced by custom_gui = <name>.
        """
        if not doc:
            return []
        names = []
        for root in doc.roots:
            if root.widget_type.lower() == 'containerwindowtype' and root.name:
                names.append(root.name)
        return names

    def _populate_gui_selector(self, gui_names: List[str]):
        """Populate the GUI selector combo with names from the current file."""
        self._gui_selector.blockSignals(True)
        self._gui_selector.clear()
        if not gui_names:
            self._gui_selector.addItem(_('（无顶层 GUI）'), None)
        elif len(gui_names) > 1:
            self._gui_selector.addItem(_('全部 (') + str(len(gui_names)) + _(' 个 GUI)'), '__ALL__')
        for name in gui_names:
            self._gui_selector.addItem(name, name)
        self._gui_selector.blockSignals(False)

    def _on_gui_selector_changed(self, index: int):
        """Called when the user picks a specific top-level GUI in the selector bar."""
        if not self._current_doc:
            return
        selected = self._gui_selector.itemData(index)
        if selected == '__ALL__' or selected is None:
            # Show events for all GUIs in the file
            self._event_panel.set_gui_names(self._get_all_gui_names(self._current_doc))
        else:
            # Show events only for the chosen GUI
            self._event_panel.set_gui_names([selected])
        # Reset event context when switching focus
        self._canvas.gui_scene.set_event_context(None)

    def _locate_selected_gui(self):
        """Center the canvas view on the currently selected top-level GUI."""
        if not self._current_doc:
            return
        index = self._gui_selector.currentIndex()
        selected_name = self._gui_selector.itemData(index)
        if not selected_name or selected_name == '__ALL__':
            # Fit all roots in view
            self._canvas.fitInView(
                self._canvas.gui_scene.itemsBoundingRect(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            return
        # Find the root node whose name matches, then center the view on its item
        scene = self._canvas.gui_scene
        for item in scene.items():
            if hasattr(item, 'node') and item.node.name == selected_name and item.parentItem() is None:
                self._canvas.centerOn(item)
                scene.clearSelection()
                item.setSelected(True)
                break

    def _on_event_selected(self, event_info):
        """Called when user picks an event in the event link panel."""
        self._canvas.gui_scene.set_event_context(event_info)
        if event_info:
            self._status.showMessage(
                _('事件上下文已应用: ') + event_info.id + '  (Room: ' + (event_info.room or _('无')) + ')'
            )
        else:
            self._status.showMessage(_('已清除事件上下文。'))

    def _save(self):
        if not self._current_doc:
            return
        if not self._current_doc.file_path:
            self._save_as()
            return
        try:
            save_document(self._current_doc)
            self._vgroup_manager.save()  # also persist virtual groups
            self._saved_doc_copy = copy.deepcopy(self._current_doc)
            self.setWindowTitle(_('群星 GUI 编辑器 — ') + os.path.basename(self._current_doc.file_path))
            self._status.showMessage(_('已保存: ') + self._current_doc.file_path)
        except Exception as e:
            QMessageBox.critical(self, _('保存错误'), str(e))

    def _save_as(self):
        if not self._current_doc:
            return
        default = self._current_doc.file_path or os.path.join(
            self._mod_dir, 'interface', 'custom_gui.gui'
        )
        path, _ = QFileDialog.getSaveFileName(self, _('另存为'), default,
                                               _('GUI 文件 (*.gui);;所有文件 (*.*)'))
        if path:
            try:
                save_document(self._current_doc, path)
                self._saved_doc_copy = copy.deepcopy(self._current_doc)
                self._settings.add_recent_file(path)
                self._update_recent_menu()
                self.setWindowTitle(_('群星 GUI 编辑器 — ') + os.path.basename(path))
                self._status.showMessage(_('已另存为: ') + path)
            except Exception as e:
                QMessageBox.critical(self, _('保存错误'), str(e))

    def _auto_save(self):
        """Auto-save to a temp file."""
        if not self._current_doc or not self._current_doc.modified:
            return
        if not self._current_doc.file_path:
            return
        try:
            auto_path = self._current_doc.file_path + '.autosave'
            save_document(copy.deepcopy(self._current_doc), auto_path)
        except Exception:
            pass
        self._autosave_timer.start()

    def _update_recent_menu(self):
        self._recent_menu.clear()
        for path in self._settings.recent_files[:10]:
            act = self._recent_menu.addAction(os.path.basename(path))
            act.setToolTip(path)
            act.triggered.connect(lambda checked=False, p=path: self._open_gui_file(p))

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def _undo(self):
        desc = self._undo_stack.undo()
        if desc:
            self._status.showMessage(_('已撤销: ') + desc)
            self._refresh_after_undo()

    def _redo(self):
        desc = self._undo_stack.redo()
        if desc:
            self._status.showMessage(_('已重做: ') + desc)
            self._refresh_after_undo()

    def _refresh_after_undo(self):
        if self._current_doc:
            selected = self._canvas.gui_scene.get_selected_node()
            self._canvas.load_document(self._current_doc)
            self._layer_panel.populate(self._current_doc)
            if selected:
                self._canvas.gui_scene.select_node(selected)
            self._code_view.schedule_update()

    def _on_undo_state_changed(self):
        can_u = self._undo_stack.can_undo()
        can_r = self._undo_stack.can_redo()
        self._act_undo.setEnabled(can_u)
        self._act_redo.setEnabled(can_r)
        self._tb_undo.setEnabled(can_u)
        self._tb_redo.setEnabled(can_r)
        self._act_undo.setText(
            _('撤销: ') + self._undo_stack.undo_description() if can_u else _('撤销'))
        self._act_redo.setText(
            _('重做: ') + self._undo_stack.redo_description() if can_r else _('重做'))

    # ------------------------------------------------------------------
    # Widget operations
    # ------------------------------------------------------------------

    def _add_widget_from_library(self, widget_type: str, name: str):
        if not self._current_doc:
            doc = GUIDocument(file_path='')
            self._load_document(doc)
        # Place into currently selected container if possible
        selected = self._canvas.gui_scene.get_selected_node()
        parent_node = None
        if selected is not None:
            from ..core.gui_model import CONTAINER_TYPES
            if selected.widget_type in CONTAINER_TYPES:
                parent_node = selected
            elif selected.parent and selected.parent.widget_type in CONTAINER_TYPES:
                parent_node = selected.parent
        if parent_node is not None:
            settings = AppSettings.instance()
            cw, ch = settings.canvas_size
            pw, ph = self._canvas.gui_scene._layout_dims_for_parent(parent_node)
            from PySide6.QtCore import QPointF
            center = self._canvas.gui_scene.get_item_for_node(parent_node)
            if center:
                scene_pos = center.mapToScene(QPointF(pw / 2, ph / 2))
            else:
                scene_pos = self._canvas.viewport_center_scene()
            node = self._canvas.gui_scene.add_widget(widget_type, scene_pos, parent_node, name=name)
        else:
            node = self._canvas.add_widget_at_center(widget_type, name)
        self._canvas.gui_scene.select_node(node)
        self._props_panel.set_node(node)
        self._layer_panel.populate(self._current_doc)
        self._code_view.schedule_update()

    def _delete_widget(self):
        self._canvas.gui_scene.delete_selected()

    def _duplicate_widget(self):
        node = self._canvas.gui_scene.duplicate_selected()
        if node:
            self._props_panel.set_node(node)
            self._layer_panel.populate(self._current_doc)

    def _copy_selected(self):
        self._canvas.gui_scene.copy_selected()

    def _paste_selected(self):
        self._canvas.gui_scene.paste_from_clipboard()
        self._layer_panel.populate(self._current_doc)

    def _reset_all_changes(self):
        """Reset the document to the last saved state."""
        if not self._saved_doc_copy:
            QMessageBox.information(self, _('无法重置'), _('没有已保存的状态可以重置。'))
            return
        reply = QMessageBox.warning(
            self, _('重置所有修改'),
            _('确定要丢弃所有未保存的修改并恢复到上次保存的状态吗？\n此操作无法撤销。'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Yes:
            restored = copy.deepcopy(self._saved_doc_copy)
            self._load_document(restored)
            self._undo_stack.clear()
            self._status.showMessage(_('已重置所有修改。'))

    def _save_preset(self):
        nodes = self._canvas.gui_scene.get_selected_nodes()
        # 按文档顺序排序，确保预设恢复时 Z 轴顺序与原始一致
        nodes = sorted(nodes, key=self._canvas.gui_scene._node_doc_index)
        if not nodes:
            QMessageBox.information(self, _('无选中控件'), _('请先选中至少一个控件。'))
            return
        # 默认预设名：单控件用控件名，多控件用第一个控件名
        default_name = nodes[0].name or nodes[0].widget_type
        name, ok = QInputDialog.getText(
            self, _('保存预设'), _('输入预设名称:'), text=default_name
        )
        if not ok or not name:
            return
        # 名称冲突处理
        if self._preset_lib.preset_exists(name):
            reply = QMessageBox.question(
                self, _('预设已存在'),
                _('预设 "') + name + _('" 已存在，是否覆盖？'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        # 序列化所有选中控件
        code_parts = [write_widget_to_string(n) for n in nodes]
        code = '\n'.join(code_parts)
        self._preset_lib.add_preset(name, code, widget_count=len(nodes))
        self._status.showMessage(_('预设已保存: ') + name + (f'  ({len(nodes)} 个控件)' if len(nodes) > 1 else ''))

    def _insert_preset(self, name: str):
        if not self._current_doc:
            doc = GUIDocument(file_path='')
            self._load_document(doc)
        code = self._preset_lib.get_preset_code(name)
        if not code:
            return
        try:
            from ..core.gui_model import compute_widget_topleft, make_names_unique
            from PySide6.QtCore import QPointF
            preset_doc = parse_gui_text(code)
            existing_names = {w.name for w in self._current_doc.all_widgets()}
            settings = AppSettings.instance()
            pw, ph = settings.canvas_size
            rm = ResourceManager.instance()

            # 预先计算每个 root 节点的场景位置，再整体平移到视窗中心
            nodes_and_positions = []
            for node in preset_doc.roots:
                make_names_unique(node, existing_names)
                dw, dh = self._canvas.gui_scene._get_display_size(node, rm)
                px, py = node.position
                tl_x, tl_y = compute_widget_topleft(pw, ph, dw, dh,
                                                      node.orientation, node.origo, px, py)
                nodes_and_positions.append((node, px, py, tl_x, tl_y))

            if nodes_and_positions:
                # 计算预设整体中心，偏移到当前视窗中心
                avg_x = sum(tp[3] for tp in nodes_and_positions) / len(nodes_and_positions)
                avg_y = sum(tp[4] for tp in nodes_and_positions) / len(nodes_and_positions)
                vc = self._canvas.viewport_center_scene()
                dx = round(vc.x() - avg_x)
                dy = round(vc.y() - avg_y)
            else:
                dx, dy = 0, 0

            from .widget_items import GUIWidgetItem
            for node, px, py, tl_x, tl_y in nodes_and_positions:
                # 更新 node.position 使保存时坐标正确
                node.position = (px + dx, py + dy)
                self._current_doc.roots.append(node)
                new_item = GUIWidgetItem(node)
                new_item.setPos(tl_x + dx, tl_y + dy)
                self._canvas.gui_scene.addItem(new_item)
                self._canvas.gui_scene._node_to_item[id(node)] = new_item
            self._layer_panel.populate(self._current_doc)
            self._code_view.schedule_update()
        except Exception as e:
            QMessageBox.warning(self, _('错误'), _('插入预设失败: ') + str(e))

    # ------------------------------------------------------------------
    # Canvas / property sync
    # ------------------------------------------------------------------

    def _on_node_selected(self, node_or_list):
        # Guard against re-entrant selection loops between canvas and layer panel
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            if isinstance(node_or_list, list):
                # Multi-select
                count = len(node_or_list)
                self._props_panel.set_node(None)
                self._sel_count_label.setText(_('已选中 ') + str(count) + _(' 个控件'))
                self._pos_label.setText('')
                self._sprite_label.setText('')
                # Highlight first in code view
                if node_or_list:
                    self._code_view.highlight_node(node_or_list[0])
                    self._layer_panel.select_node(node_or_list[0])
            elif isinstance(node_or_list, WidgetNode):
                node = node_or_list
                self._props_panel.set_node(node)
                self._sel_count_label.setText('')
                x, y = node.position
                w, h = self._status_display_wh(node)
                self._pos_label.setText(f'x:{x}  y:{y}  w:{w}  h:{h}  [{node.widget_type}]')
                sprite = node.get_sprite_name()
                tooltip = node.get_tooltip_key()
                info_parts = []
                if sprite:
                    rm = ResourceManager.instance()
                    mode = rm.get_widget_render_mode(node)
                    type_str = _('9块') if mode == 'nine_patch' else _('固定')
                    info_parts.append(_('精灵[') + type_str + _(']: ') + sprite)
                if tooltip:
                    rm = ResourceManager.instance()
                    info_parts.append(f'Tip: {rm.get_loc(tooltip)[:20]}')
                self._sprite_label.setText('  '.join(info_parts))
                # Highlight in code and layer panel
                self._code_view.highlight_node(node)
                self._layer_panel.select_node(node)
            else:
                self._props_panel.set_node(None)
                self._sel_count_label.setText('')
                self._pos_label.setText('')
                self._sprite_label.setText('')
                self._code_view.highlight_node(None)
        finally:
            self._syncing_selection = False

    def _on_node_changed(self, node: WidgetNode):
        self._props_panel.refresh_from_node(node)
        self._code_view.schedule_update()
        if node:
            x, y = node.position
            w, h = self._status_display_wh(node)
            self._pos_label.setText(f'x:{x}  y:{y}  w:{w}  h:{h}  [{node.widget_type}]')
            self._layer_panel.refresh_item(node)

    def _on_widget_renamed(self, old_name: str, new_name: str):
        """控件被重命名 → 同步更新所有虚拟组中的控件名引用。"""
        if self._vgroup_manager:
            self._vgroup_manager.rename_widget(old_name, new_name)
        if hasattr(self, '_vgroup_panel'):
            self._vgroup_panel.refresh()

    def _on_property_edited(self, node: WidgetNode):
        # Push to undo stack
        # (Individual property changes tracked in props panel)
        scene = self._canvas.gui_scene
        if self._current_doc:
            cw, ch = AppSettings.instance().canvas_size
            resolve_editor_layout_sizes(
                self._current_doc.roots, cw, ch, ResourceManager.instance())
            for r in self._current_doc.roots:
                scene.refresh_item(r)
        scene._refresh_all_auto_sizes()
        if self._current_doc:
            for r in self._current_doc.roots:
                scene.refresh_item(r)
        self._code_view.schedule_update()
        self._layer_panel.refresh_item(node)

    def _status_display_wh(self, node: WidgetNode) -> Tuple[int, int]:
        """Width/height for status bar: use canvas item for implicit containers."""
        if node.is_implicit_size_container():
            item = self._canvas.gui_scene.get_item_for_node(node)
            if item:
                return item._display_w, item._display_h
            els = getattr(node, '_editor_layout_size', None)
            if els:
                return els[0], els[1]
        w, h = node.size
        return w, h

    def _refresh_canvas(self):
        """Force a complete canvas reload from the current document model."""
        if not self._current_doc:
            return
        from ..core.gui_model import resolve_editor_layout_sizes
        rm = ResourceManager.instance()
        cw, ch = AppSettings.instance().canvas_size
        resolve_editor_layout_sizes(self._current_doc.roots, cw, ch, rm)
        self._canvas.load_document(self._current_doc)
        self._layer_panel.populate(self._current_doc)
        # Keep GUI selector and event panel in sync
        all_gui_names = self._get_all_gui_names(self._current_doc)
        self._populate_gui_selector(all_gui_names)
        self._event_panel.set_gui_names(all_gui_names)
        self._status.showMessage(_('画布已刷新。'))

    def _update_language_combo(self):
        """Refresh the language selector based on available languages."""
        rm = ResourceManager.instance()
        langs = rm.get_available_languages()
        active = rm.get_active_language()

        # Language display names
        _LANG_DISPLAY = {
            'l_english': 'English', 'l_simp_chinese': '简体中文',
            'l_german': 'Deutsch', 'l_french': 'Français',
            'l_spanish': 'Español', 'l_russian': 'Русский',
            'l_polish': 'Polski', 'l_braz_por': 'Português (BR)',
            'l_japanese': '日本語', 'l_korean': '한국어',
        }
        self._lang_combo.blockSignals(True)
        self._lang_combo.clear()
        if not langs:
            self._lang_combo.addItem(_('（未检测到语言）'), '')
        else:
            for lang in langs:
                display = _LANG_DISPLAY.get(lang, lang.replace('l_', '').capitalize())
                self._lang_combo.addItem(display, lang)
            # Select active
            for i in range(self._lang_combo.count()):
                if self._lang_combo.itemData(i) == active:
                    self._lang_combo.setCurrentIndex(i)
                    break
        self._lang_combo.blockSignals(False)

    def _on_language_changed(self, index: int):
        """User switched localization language — reload loc data and refresh canvas."""
        lang = self._lang_combo.itemData(index)
        if not lang:
            return
        rm = ResourceManager.instance()
        rm.set_active_language(lang)
        # Refresh all text in canvas
        if self._current_doc:
            self._canvas.gui_scene.update()
            self._canvas.viewport().update()
        self._status.showMessage(_('本地化已切换: ') + lang)

    def _on_document_modified(self):
        if self._current_doc:
            fname = os.path.basename(self._current_doc.file_path or _('未命名'))
            self.setWindowTitle(_('群星 GUI 编辑器 — ') + fname + ' *')
        self._code_view.schedule_update()
        self._warnings_panel.refresh()
        # 清理组中已被删除的控件名，然后刷新组面板
        if self._current_doc and self._vgroup_manager:
            valid = {w.name for w in self._current_doc.all_widgets()}
            self._vgroup_manager.clean_stale_names(valid)
        if hasattr(self, '_vgroup_panel'):
            self._vgroup_panel.refresh()
        self._autosave_timer.start()

    def _assign_sprite(self, sprite_name: str):
        node = self._canvas.gui_scene.get_selected_node()
        if not node:
            return
        rm = ResourceManager.instance()
        info = rm.get_sprite(sprite_name)
        from ..core.gui_model import CONTAINER_TYPES
        if node.widget_type in CONTAINER_TYPES:
            # Containers have no sprite properties directly — modify background sub-block
            bg = node.properties.get('background', {})
            if not isinstance(bg, dict):
                bg = {}
            bg.setdefault('name', 'background')
            bg['quadTextureSprite'] = sprite_name
            node.properties['background'] = bg
            self._status.showMessage(_('已设置容器背景精灵图: ') + sprite_name)
        elif info and info.is_scalable():
            node.properties.pop('spriteType', None)
            node.properties['quadTextureSprite'] = sprite_name
            self._status.showMessage(_('已分配精灵图 (可拉伸): ') + sprite_name)
        else:
            node.properties.pop('quadTextureSprite', None)
            node.properties['spriteType'] = sprite_name
            self._status.showMessage(_('已分配精灵图 (固定): ') + sprite_name)
        self._props_panel.refresh_from_node(node)
        self._canvas.gui_scene.refresh_item(node)

    def _apply_code(self, code: str):
        if not self._current_doc:
            return
        try:
            new_doc = parse_gui_text(code, self._current_doc.file_path)
            new_doc.modified = True
            self._load_document(new_doc)
            self._undo_stack.clear()
            self._status.showMessage(_('代码已应用。'))
        except Exception as e:
            QMessageBox.warning(self, _('解析错误'), _('解析代码失败:\n') + str(e))

    # ------------------------------------------------------------------
    # Layer panel events
    # ------------------------------------------------------------------

    def _on_layer_node_selected(self, node: Optional[WidgetNode]):
        # Guard against re-entrant selection loops between canvas and layer panel
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            if node:
                self._canvas.gui_scene.select_node(node)
                self._props_panel.set_node(node)
                # Update status bar info
                x, y = node.position
                w, h = self._status_display_wh(node)
                self._pos_label.setText(f'x:{x}  y:{y}  w:{w}  h:{h}  [{node.widget_type}]')
                self._sel_count_label.setText('')
                self._code_view.highlight_node(node)
                # Scroll canvas to widget
                item = self._canvas.gui_scene.get_item_for_node(node)
                if item:
                    self._canvas.centerOn(item)
        finally:
            self._syncing_selection = False

    def _on_visibility_changed(self, node: WidgetNode, visible: bool):
        item = self._canvas.gui_scene.get_item_for_node(node)
        if item:
            item.set_visible_flag(visible)
            # If layer wants to show this item, respect any active group-hide
            if visible and node.name:
                if self._vgroup_manager.is_node_hidden_by_group(node.name):
                    item.setVisible(False)

    def _on_lock_changed(self, node: WidgetNode, locked: bool):
        item = self._canvas.gui_scene.get_item_for_node(node)
        if item:
            item.set_locked(locked)
        for child in node.children:
            self._on_lock_changed(child, locked)

    def _on_order_changed(self, node: WidgetNode, delta: int):
        if delta != 0:
            self._canvas.gui_scene.move_widget_order(node, delta)
        # Refresh layer panel
        self._layer_panel.populate(self._current_doc)
        if self._current_doc:
            self._current_doc.modified = True
        self._code_view.schedule_update()

    def _on_layer_structure_changed(self):
        """Called when drag-drop in layer panel changes the widget tree structure."""
        if not self._current_doc:
            return
        # Rebuild canvas from updated model
        self._canvas.load_document(self._current_doc)
        self._current_doc.modified = True
        self._code_view.schedule_update()
        self._status.showMessage(_('图层结构已更新。'))

    def _on_node_position_changed(self, node: WidgetNode):
        """Called when a widget is dragged/resized in the canvas.
        Only refreshes the properties panel — never triggers canvas refresh (avoids loop)."""
        self._props_panel.refresh_from_node(node)
        self._code_view.schedule_update()

    def _on_cursor_pos(self, x: float, y: float):
        """Show scene coordinates in status bar."""
        self._pos_label.setText(f'  X: {int(x)}  Y: {int(y)}  ')

    def _find_widget(self):
        """Ctrl+F: find a widget by name and select it."""
        if not self._current_doc:
            return
        names = [w.name for w in self._current_doc.all_widgets() if w.name]
        name, ok = QInputDialog.getItem(self, _('查找控件'), _('控件名称:'), sorted(names), editable=True)
        if ok and name:
            node = self._current_doc.find_by_name(name)
            if node:
                item = self._canvas.gui_scene.get_item_for_node(node)
                if item:
                    self._canvas.gui_scene.clearSelection()
                    item.setSelected(True)
                    self._canvas.centerOn(item)
                    self._status.showMessage(_('已定位控件: ') + name)
            else:
                self._status.showMessage(_('未找到控件: ') + name)

    def _on_vgroup_visibility_changed(self):
        """Apply virtual group visibility to canvas items."""
        if not self._current_doc:
            return
        from .widget_items import GUIWidgetItem
        for item in self._canvas.gui_scene.items():
            if isinstance(item, GUIWidgetItem):
                node = item.node
                if node.name:
                    hidden = self._vgroup_manager.is_node_hidden_by_group(node.name)
                    # Respect the layer panel's own visibility flag
                    layer_visible = getattr(item, '_visible_flag', True)
                    item.setVisible(not hidden and layer_visible)
        self._canvas.gui_scene.update()

    # ------------------------------------------------------------------
    # Workspace management
    # ------------------------------------------------------------------

    def _add_workspace_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, _('添加文件夹到工作区'),
            self._settings.get('last_open_dir', '')
        )
        if path:
            name, ok = QInputDialog.getText(
                self, _('工作区文件夹名称'),
                _('为此文件夹指定一个名称（可选）:'),
                text=os.path.basename(path)
            )
            if ok:
                self._settings.add_workspace_folder(path, name)
                self._load_mod_dir(path)
                self._status.showMessage(_('已添加工作区文件夹: ') + (name or path))

    def _manage_workspace_folders(self):
        """Show a dialog to view/remove workspace folders."""
        from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(_('管理工作区文件夹'))
        dlg.resize(540, 360)
        layout = QVBoxLayout(dlg)
        lbl = QLabel(_('工作区文件夹（用于自动加载资源）:'))
        layout.addWidget(lbl)
        lst = QListWidget()
        folders = self._settings.workspace_folders
        for wf in folders:
            item = QListWidgetItem(f"{'[ON]' if wf.get('enabled', True) else '[--]'}  {wf.get('name', '')}  —  {wf.get('path', '')}")
            item.setData(Qt.ItemDataRole.UserRole, wf.get('path', ''))
            lst.addItem(item)
        layout.addWidget(lst)
        btn_row = QHBoxLayout()
        add_btn = QPushButton(_('添加...'))
        remove_btn = QPushButton(_('删除选中'))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        layout.addLayout(btn_row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.accept)
        layout.addWidget(buttons)

        def do_add():
            dlg.accept()
            self._add_workspace_folder()

        def do_remove():
            cur = lst.currentItem()
            if cur:
                p = cur.data(Qt.ItemDataRole.UserRole)
                self._settings.remove_workspace_folder(p)
                lst.takeItem(lst.row(cur))
                self._status.showMessage(_('已移除工作区文件夹: ') + p)

        add_btn.clicked.connect(do_add)
        remove_btn.clicked.connect(do_remove)
        dlg.exec()

    def _update_ws_folders_menu(self):
        self._ws_folders_menu.clear()
        folders = self._settings.workspace_folders
        if not folders:
            self._ws_folders_menu.addAction(_('（无工作区文件夹）')).setEnabled(False)
            return
        for wf in folders:
            path = wf.get('path', '')
            name = wf.get('name', os.path.basename(path))
            act = self._ws_folders_menu.addAction(name, lambda p=path: self._load_mod_dir(p))
            act.setToolTip(path)
            if path == self._mod_dir:
                act.setCheckable(True)
                act.setChecked(True)

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------

    def _align(self, axis: str):
        self._canvas.gui_scene.align_selected(axis)

    def _linear_array(self):
        from .array_dialogs import LinearArrayDialog
        dlg = LinearArrayDialog(self)
        if dlg.exec():
            self._canvas.gui_scene.linear_array_selected(
                dlg.count, dlg.offset_x, dlg.offset_y)

    def _circular_array(self):
        from .array_dialogs import CircularArrayDialog
        settings = AppSettings.instance()
        cw, ch = settings.canvas_size
        # 默认圆心 = 选中控件中心（on_ring 模式使用）；center 模式由 canvas 自行计算
        sel = self._canvas.gui_scene._get_selected_pos_size()
        if sel:
            default_cx = sum((p[0] + s[0] / 2) for _, p, s in sel) / len(sel)
            default_cy = sum((p[1] + s[1] / 2) for _, p, s in sel) / len(sel)
        else:
            default_cx, default_cy = cw / 2, ch / 2
        dlg = CircularArrayDialog(default_cx, default_cy, self)
        if dlg.exec():
            self._canvas.gui_scene.circular_array_selected(
                dlg.count, dlg.center_x, dlg.center_y, dlg.radius,
                mode=dlg.mode)

    def _mirror(self, axis: str):
        self._canvas.gui_scene.mirror_selected(axis, copy=True)

    def _mirror_dialog(self):
        from .array_dialogs import MirrorDialog
        dlg = MirrorDialog(self)
        if dlg.exec():
            self._canvas.gui_scene.mirror_selected(
                dlg.axis, copy=dlg.copy_mode)

    def _toggle_grid(self):
        self._settings.show_grid = self._act_grid.isChecked()
        self._canvas.gui_scene.update()

    def _toggle_snap(self):
        self._settings.snap_to_grid = self._act_snap.isChecked()
        self._canvas.gui_scene.snap_to_grid = self._settings.snap_to_grid

    def _toggle_preview(self):
        mode = self._canvas.toggle_preview_mode()
        self._act_preview.setChecked(mode)
        self._tb_preview.setChecked(mode)
        self._status.showMessage(_('预览模式: ') + (_('开启') if mode else _('关闭')))

    def _toggle_editor_scrollbars(self):
        self._settings.show_editor_scrollbars = self._act_editor_scrollbars.isChecked()
        self._canvas.gui_scene.sync_editor_scrollbar_visibility()
        self._status.showMessage(
            _('编辑器滑条: ') + (_('显示') if self._settings.show_editor_scrollbars else _('隐藏')))

    def _reload_sprites(self):
        self._rm.clear_cache()
        if self._current_doc:
            for item in self._canvas.gui_scene.items():
                from .widget_items import GUIWidgetItem
                if isinstance(item, GUIWidgetItem):
                    item.refresh()
        self._sprite_lib.populate()
        self._status.showMessage(_('精灵图已重新加载。'))

    def _manual_refresh_resources(self):
        """
        Manual full refresh (no periodic scanning):
        reload game/mod/extra-mod resources and update visible editor state.
        """
        try:
            self._status.showMessage(_('正在手动刷新资源...'))
            QApplication.processEvents()
            self._rm.reload_all()
            self._sprite_lib.populate()
            self._file_browser.set_directories(self._settings.game_dir, self._mod_dir)
            self._be_editor.set_mod_dir(self._mod_dir)
            self._update_language_combo()

            # Refresh texts/sprites currently on canvas
            if self._current_doc:
                cw, ch = AppSettings.instance().canvas_size
                resolve_editor_layout_sizes(self._current_doc.roots, cw, ch, self._rm)
                self._canvas.load_document(self._current_doc)
                self._layer_panel.populate(self._current_doc)
                self._code_view.schedule_update()

            self._status.showMessage(
                _('资源刷新完成: ') + str(self._rm.sprite_count) + _(' 个精灵 / ') + str(self._rm.loc_count) + _(' 条本地化')
            )
        except Exception as e:
            QMessageBox.warning(self, _('刷新失败'), str(e))

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Re-apply theme in case user changed it
            ThemeManager.apply(
                QApplication.instance(),
                self._settings.theme,
                self._settings.accent_color or None,
            )
            self._canvas.update_theme()
            self._code_view.update_theme(self._settings.theme)
            self._refresh_theme_icons()

            game_dir = self._settings.game_dir
            if game_dir != self._rm.game_dir:
                self._rm.clear_cache()
                self._rm.load_game_dir(game_dir)
                self._sprite_lib.populate()
                self._file_browser.set_directories(game_dir, self._mod_dir)
            self._canvas.gui_scene.grid_size = self._settings.grid_size
            self._canvas.gui_scene.snap_to_grid = self._settings.snap_to_grid
            self._act_grid.setChecked(self._settings.show_grid)
            self._act_snap.setChecked(self._settings.snap_to_grid)
            self._canvas.gui_scene.update()

    def _refresh_theme_icons(self):
        """主题切换后刷新所有静态设置的图标和主题色标签。"""
        for action, icon_name in self._toolbar_icon_actions:
            action.setIcon(IconProvider.themed_icon(icon_name, 18))
        self._lang_label.setStyleSheet(f'color:{ThemeManager.muted_color()};')
        self._layer_panel.refresh_icons()
        self._vgroup_panel.refresh_icons()

    def _validate_gui(self):
        """Validate the current GUI document for common issues."""
        if not self._current_doc:
            QMessageBox.information(self, _('验证'), _('没有打开的文件。'))
            return
        issues = []
        rm = ResourceManager.instance()
        for widget in self._current_doc.all_widgets():
            sprite = widget.get_sprite_name()
            if sprite and not rm.get_sprite(sprite):
                issues.append(_('控件 "') + widget.name + _('": 精灵图 "') + sprite + _('" 未在 GFX 中注册'))
            if not widget.name:
                issues.append(_('控件 ') + widget.widget_type + _(': 缺少 name 属性 (可能导致游戏崩溃)'))
            # Duplicate names in same parent
        # Check name uniqueness
        seen_names = {}
        for widget in self._current_doc.all_widgets():
            parent_id = id(widget.parent) if widget.parent else 0
            key = (parent_id, widget.name)
            if widget.name and key in seen_names:
                issues.append(_('名称重复: "') + widget.name + _('" (同级控件中名称必须唯一)'))
            elif widget.name:
                seen_names[key] = widget

        if issues:
            from PySide6.QtWidgets import QDialog, QTextEdit, QDialogButtonBox, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle(_('GUI 验证结果'))
            dlg.setMinimumSize(500, 350)
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(_('发现 ') + str(len(issues)) + _(' 个问题:')))
            te = QTextEdit()
            te.setReadOnly(True)
            te.setPlainText('\n'.join(f'• {i}' for i in issues))
            layout.addWidget(te)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btns.accepted.connect(dlg.accept)
            layout.addWidget(btns)
            dlg.exec()
        else:
            QMessageBox.information(self, _('GUI 验证'), _('未发现问题！'))

    def _open_be_editor(self):
        """Show the Button Effects editor dock and populate from current mod."""
        # Find and show the dock that contains _be_editor
        for dock in self.findChildren(QDockWidget):
            if dock.widget() is self._be_editor:
                dock.show()
                dock.raise_()
                break
        if self._mod_dir:
            self._be_editor.set_mod_dir(self._mod_dir)

    def _generate_gfx(self):
        from PySide6.QtWidgets import QDialog, QTextEdit, QDialogButtonBox, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(_('生成 .gfx 精灵注册文件'))
        dlg.setMinimumSize(640, 440)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            _('每行格式: 精灵名称|纹理路径|类型|帧数\n'
              '类型: spriteType / corneredTileSpriteType\n'
              '例: GFX_my_btn|gfx/interface/buttons/my_btn.dds|spriteType|3')
        ))
        editor = QTextEdit()
        editor.setFont(QFont('Consolas', 10))
        editor.setStyleSheet('background: #1e1e1e; color: #d4d4d4;')
        layout.addWidget(editor)
        from ..codegen.gui_writer import generate_gfx_file
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont('Consolas', 10))
        preview.setStyleSheet('background: #1e1e1e; color: #d4d4d4;')
        layout.addWidget(QLabel(_('预览:')))
        layout.addWidget(preview)

        def _upd():
            regs = []
            for line in editor.toPlainText().strip().split('\n'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    regs.append({
                        'sprite_name': parts[0], 'texture_path': parts[1],
                        'sprite_type': parts[2] if len(parts) > 2 else 'spriteType',
                        'no_of_frames': int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1,
                    })
            if regs:
                try: preview.setPlainText(generate_gfx_file(regs))
                except Exception as e: preview.setPlainText(_('错误: ') + str(e))

        editor.textChanged.connect(_upd)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText(_('保存'))
        btns.button(QDialogButtonBox.StandardButton.Close).setText(_('关闭'))

        def _save():
            content = preview.toPlainText()
            if not content: return
            default = os.path.join(self._mod_dir, 'interface', 'sprites.gfx') if self._mod_dir else ''
            path, _ = QFileDialog.getSaveFileName(dlg, _('保存 .gfx'), default, _('GFX 文件 (*.gfx);;所有文件 (*.*)'))
            if path:
                with open(path, 'w', encoding='utf-8') as f: f.write(content)
                self._status.showMessage(_('已保存: ') + path)

        btns.accepted.connect(_save)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        dlg.exec()

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        self._autosave_timer.stop()
        if self._current_doc and self._current_doc.modified:
            reply = QMessageBox.question(
                self, _('未保存的修改'),
                _('有未保存的修改，是否在退出前保存？'),
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
