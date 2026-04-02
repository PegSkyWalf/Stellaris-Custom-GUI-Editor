"""
属性面板 — 编辑选中控件的属性。

包含：
  - 基本信息（名称、类型）
  - 位置与大小（position, size, orientation, origo）
  - 外观（spriteType, quadTextureSprite, scale）
  - 文本内容
  - 交互（effectButtonType 专用）
  - 背景（background 子块）
  - 其它属性
  - 原始属性编辑器（显示并编辑所有"未被上方区块覆盖"的属性）
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QScrollArea,
    QGroupBox, QFrame, QSizePolicy, QTabWidget,
    QTextEdit, QToolButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ..core.gui_model import (
    WidgetNode, WIDGET_TYPES, ORIENTATIONS,
    WIDGET_LABELS, WIDGET_COLORS,
)
from ..core.i18n import _
from ..core.resource_manager import ResourceManager
from ..core.theme_manager import ThemeManager


class SpriteSelector(QWidget):
    sprite_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(_('GFX_精灵名称'))
        layout.addWidget(self._edit)
        btn = QPushButton('…')
        btn.setFixedWidth(28)
        btn.clicked.connect(self._open_picker)
        layout.addWidget(btn)
        self._edit.textChanged.connect(self.sprite_changed.emit)

    def value(self) -> str:
        return self._edit.text()

    def set_value(self, v: str):
        self._edit.blockSignals(True)
        self._edit.setText(v or '')
        self._edit.blockSignals(False)

    def _open_picker(self):
        from .dialogs import SpritePicker
        picker = SpritePicker(self)
        if picker.exec():
            self._edit.setText(picker.selected_sprite)


class Vec2Editor(QWidget):
    value_changed = Signal(int, int)

    def __init__(self, label1='x', label2='y', parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(QLabel(f'{label1}:'))
        self._x = QSpinBox()
        self._x.setRange(-99999, 999999)
        layout.addWidget(self._x)
        layout.addWidget(QLabel(f'{label2}:'))
        self._y = QSpinBox()
        self._y.setRange(-99999, 999999)
        layout.addWidget(self._y)
        self._x.valueChanged.connect(lambda _: self.value_changed.emit(self._x.value(), self._y.value()))
        self._y.valueChanged.connect(lambda _: self.value_changed.emit(self._x.value(), self._y.value()))

    def get_value(self) -> Tuple[int, int]:
        return self._x.value(), self._y.value()

    def set_value(self, x: int, y: int):
        self._x.blockSignals(True)
        self._y.blockSignals(True)
        self._x.setValue(x)
        self._y.setValue(y)
        self._x.blockSignals(False)
        self._y.blockSignals(False)


class PropertiesPanel(QWidget):
    """属性面板，显示和编辑选中控件的属性。"""
    property_changed = Signal(object)
    widget_renamed = Signal(str, str)   # (old_name, new_name) — 控件重命名时发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node: Optional[WidgetNode] = None
        self._doc = None    # GUIDocument reference for duplicate name detection
        self._updating = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._title = QLabel(_('属性面板'))
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(self._title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(6)
        scroll.setWidget(self._content)

        self._build_identity_section()
        self._build_geometry_section()
        self._build_appearance_section()
        self._build_text_section()
        self._build_interaction_section()
        self._build_background_section()
        self._build_extra_section()
        self._build_raw_section()
        self._content_layout.addStretch()

        self._set_enabled(False)

    def _make_group(self, title: str) -> Tuple[QGroupBox, QFormLayout]:
        group = QGroupBox(title)
        group.setStyleSheet('QGroupBox { font-weight: bold; }')
        form = QFormLayout(group)
        form.setContentsMargins(6, 14, 6, 6)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._content_layout.addWidget(group)
        return group, form

    def _build_identity_section(self):
        self._id_group, form = self._make_group(_('基本信息'))
        self._type_label = QLabel('')
        self._type_label.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 9px;')
        form.addRow(_('控件类型:'), self._type_label)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(_('控件名称 (唯一标识)'))
        self._name_edit.textChanged.connect(self._on_name_changed)
        form.addRow(_('名称:'), self._name_edit)
        self._name_dup_label = QLabel()
        self._name_dup_label.setStyleSheet('color: #e74c3c; font-size: 9px;')
        self._name_dup_label.hide()
        form.addRow('', self._name_dup_label)

    def _build_geometry_section(self):
        self._geo_group, form = self._make_group(_('位置与大小'))

        self._pos_editor = Vec2Editor('x', 'y')
        self._pos_editor.value_changed.connect(self._on_pos_changed)
        form.addRow(_('位置 (position):'), self._pos_editor)

        # Size: shown always, but with different states
        self._size_editor = Vec2Editor(_('宽'), _('高'))
        self._size_editor.value_changed.connect(self._on_size_changed)
        form.addRow(_('大小 (size):'), self._size_editor)

        # Placeholder when no size property defined
        self._no_size_row = QHBoxLayout()
        self._no_size_label = QLabel('-')
        self._no_size_label.setStyleSheet(f'color: {ThemeManager.accent_color()}; font-size: 11px; font-weight: bold;')
        self._no_size_row.addWidget(self._no_size_label)
        self._create_size_btn = QPushButton(_('创建 size 属性'))
        self._create_size_btn.setFixedHeight(20)
        self._create_size_btn.setStyleSheet('font-size: 9px;')
        self._create_size_btn.clicked.connect(self._on_create_size)
        self._no_size_row.addWidget(self._create_size_btn)
        self._no_size_row.addStretch()
        no_size_widget = QWidget()
        no_size_widget.setLayout(self._no_size_row)
        form.addRow('', no_size_widget)
        self._no_size_widget = no_size_widget
        self._no_size_widget.setVisible(False)

        self._size_placeholder_label = QLabel()
        self._size_placeholder_label.setWordWrap(True)
        self._size_placeholder_label.setStyleSheet(f'color: {ThemeManager.accent_color()}; font-size: 9px;')
        self._size_placeholder_label.setVisible(False)
        form.addRow('', self._size_placeholder_label)

        # Size note for spriteType
        self._size_note = QLabel(_('[!] spriteType 控件的大小由精灵图决定,\n请用 scale 属性调整显示尺寸。'))
        self._size_note.setStyleSheet('color: #f39c12; font-size: 8px;')
        self._size_note.setWordWrap(True)
        form.addRow('', self._size_note)

        self._orient_combo = QComboBox()
        self._orient_combo.addItem(_('（默认，不写脚本）'))
        for o in ORIENTATIONS:
            self._orient_combo.addItem(o)
        self._orient_combo.currentIndexChanged.connect(self._on_orient_index_changed)
        form.addRow(_('锚点方向 (orientation):'), self._orient_combo)

        self._origo_combo = QComboBox()
        self._origo_combo.addItem(_('（默认，不写脚本）'))
        for o in ORIENTATIONS:
            self._origo_combo.addItem(o)
        self._origo_combo.currentIndexChanged.connect(self._on_origo_index_changed)
        form.addRow(_('自身参考点 (origo):'), self._origo_combo)

        note = QLabel(
            _('orientation: 锚点在父元素中的位置\n'
              'origo: 本控件的哪个点对齐到锚点')
        )
        note.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 8px;')
        form.addRow('', note)

        self._moveable_cb = QCheckBox(_('可移动'))
        self._moveable_cb.stateChanged.connect(
            lambda s: self._set_prop('moveable', s == Qt.CheckState.Checked.value)
        )
        form.addRow('', self._moveable_cb)

    def _build_appearance_section(self):
        self._app_group, form = self._make_group(_('外观 (精灵图)'))

        self._sprite_sel = SpriteSelector()
        self._sprite_sel.sprite_changed.connect(self._on_sprite_changed)
        form.addRow('spriteType:', self._sprite_sel)

        sprite_note = QLabel(_('固定尺寸精灵 (大小由图片决定)'))
        sprite_note.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 8px;')
        form.addRow('', sprite_note)

        self._quad_sel = SpriteSelector()
        self._quad_sel.sprite_changed.connect(lambda v: self._set_prop('quadTextureSprite', v) if v else None)
        form.addRow('quadTextureSprite:', self._quad_sel)

        quad_note = QLabel(_('可拉伸精灵 (大小由 size 属性决定)'))
        quad_note.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 8px;')
        form.addRow('', quad_note)

        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.001, 100.0)
        self._scale_spin.setSingleStep(0.05)
        self._scale_spin.setValue(1.0)
        self._scale_spin.setDecimals(4)
        self._scale_spin.valueChanged.connect(lambda v: self._set_prop('scale', round(v, 4)))
        form.addRow(_('缩放 (scale):'), self._scale_spin)

        self._always_transparent_cb = QCheckBox(_('鼠标透明 (alwaysTransparent)'))
        self._always_transparent_cb.stateChanged.connect(
            lambda s: self._set_prop('alwaysTransparent', s == Qt.CheckState.Checked.value)
        )
        form.addRow('', self._always_transparent_cb)

    def _build_text_section(self):
        self._text_group, form = self._make_group(_('文本内容'))

        self._button_text_edit = QLineEdit()
        self._button_text_edit.setPlaceholderText(_('本地化键或直接文字'))
        self._button_text_edit.textChanged.connect(lambda v: self._set_prop('buttonText', v))
        form.addRow('buttonText:', self._button_text_edit)

        self._loc_preview = QLabel()
        self._loc_preview.setStyleSheet(f'color: {ThemeManager.accent_color()}; font-size: 9px;')
        self._loc_preview.setWordWrap(True)
        form.addRow(_('→ 本地化文本:'), self._loc_preview)

        self._text_edit = QLineEdit()
        self._text_edit.setPlaceholderText(_('文本内容 (text/instantTextBox)'))
        self._text_edit.textChanged.connect(lambda v: self._set_prop('text', v))
        form.addRow('text:', self._text_edit)

        self._font_edit = QLineEdit()
        self._font_edit.setPlaceholderText(_('如: cg_16b, malgun_goth_24'))
        self._font_edit.textChanged.connect(lambda v: self._set_prop('font', v))
        form.addRow(_('字体 (font):'), self._font_edit)

        self._button_font_edit = QLineEdit()
        self._button_font_edit.textChanged.connect(lambda v: self._set_prop('buttonFont', v))
        form.addRow(_('按钮字体 (buttonFont):'), self._button_font_edit)

        self._max_w_spin = QSpinBox()
        self._max_w_spin.setRange(0, 99999)
        self._max_w_spin.valueChanged.connect(lambda v: self._set_prop('maxWidth', v) if v > 0 else None)
        form.addRow(_('最大宽度 (maxWidth):'), self._max_w_spin)

        self._max_h_spin = QSpinBox()
        self._max_h_spin.setRange(0, 99999)
        self._max_h_spin.valueChanged.connect(lambda v: self._set_prop('maxHeight', v) if v > 0 else None)
        form.addRow(_('最大高度 (maxHeight):'), self._max_h_spin)

        self._format_combo = QComboBox()
        for fmt in ('', 'left', 'right', 'center', 'centre', 'justified', 'CENTER', 'CENTER_LEFT'):
            self._format_combo.addItem(fmt)
        self._format_combo.currentTextChanged.connect(
            lambda v: self._set_prop('format', v) if v else None
        )
        form.addRow(_('文本对齐 (format):'), self._format_combo)

        self._text_offset_editor = Vec2Editor('x', 'y')
        self._text_offset_editor.value_changed.connect(
            lambda x, y: self._set_prop('text_offset', {'x': x, 'y': y})
        )
        form.addRow(_('文本偏移 (text_offset):'), self._text_offset_editor)

        self._color_code_edit = QLineEdit()
        self._color_code_edit.setMaxLength(2)
        self._color_code_edit.setPlaceholderText('H/R/G/B/E')
        self._color_code_edit.textChanged.connect(lambda v: self._set_prop('text_color_code', v))
        form.addRow(_('颜色代码 (text_color_code):'), self._color_code_edit)

        self._fixed_size_cb = QCheckBox(_('固定大小 (fixedSize)'))
        self._fixed_size_cb.stateChanged.connect(
            lambda s: self._set_prop('fixedSize', s == Qt.CheckState.Checked.value)
        )
        form.addRow('', self._fixed_size_cb)

    def _build_interaction_section(self):
        self._int_group, form = self._make_group(_('交互 (effectButtonType)'))

        self._effect_edit = QLineEdit()
        self._effect_edit.setPlaceholderText(_('button_effect 名称'))
        self._effect_edit.textChanged.connect(lambda v: self._set_prop('effect', v))
        form.addRow(_('效果 (effect):'), self._effect_edit)

        self._tooltip_text_edit = QLineEdit()
        self._tooltip_text_edit.setPlaceholderText(_('本地化键'))
        self._tooltip_text_edit.textChanged.connect(lambda v: self._set_prop('tooltipText', v))
        form.addRow(_('悬浮提示键 (tooltipText):'), self._tooltip_text_edit)

        self._tooltip_loc_preview = QLabel()
        self._tooltip_loc_preview.setStyleSheet(f'color: {ThemeManager.accent_color()}; font-size: 9px;')
        self._tooltip_loc_preview.setWordWrap(True)
        form.addRow(_('→ 提示本地化:'), self._tooltip_loc_preview)

        self._pdx_tooltip_edit = QLineEdit()
        self._pdx_tooltip_edit.setPlaceholderText(_('本地化键 (非effectButton)'))
        self._pdx_tooltip_edit.textChanged.connect(lambda v: self._set_prop('pdx_tooltip', v))
        form.addRow('pdx_tooltip:', self._pdx_tooltip_edit)

        self._shortcut_edit = QLineEdit()
        self._shortcut_edit.textChanged.connect(lambda v: self._set_prop('shortcut', v))
        form.addRow(_('快捷键 (shortcut):'), self._shortcut_edit)

        self._click_sound_edit = QLineEdit()
        self._click_sound_edit.setPlaceholderText(_('如: confirm_click, back_click'))
        self._click_sound_edit.textChanged.connect(lambda v: self._set_prop('clicksound', v))
        form.addRow(_('点击音效 (clicksound):'), self._click_sound_edit)

    def _build_background_section(self):
        self._bg_group, form = self._make_group(_('背景 (background 子块)'))

        bg_note = QLabel(
            _('background 是 containerWindowType 的可选子块，\n'
              '使用 quadTextureSprite 填充整个容器。')
        )
        bg_note.setStyleSheet(f'color: {ThemeManager.muted_color()}; font-size: 8px;')
        bg_note.setWordWrap(True)
        form.addRow('', bg_note)

        self._bg_sprite_sel = SpriteSelector()
        self._bg_sprite_sel.sprite_changed.connect(self._on_bg_sprite_changed)
        form.addRow(_('背景精灵:'), self._bg_sprite_sel)

        self._bg_transparent_cb = QCheckBox(_('鼠标透明 (alwaysTransparent)'))
        self._bg_transparent_cb.stateChanged.connect(self._on_bg_transparent_changed)
        form.addRow('', self._bg_transparent_cb)

    def _build_extra_section(self):
        self._extra_group, form = self._make_group(_('其它属性'))

        self._clipping_cb = QCheckBox(_('子元素裁剪 (clipping)'))
        self._clipping_cb.stateChanged.connect(
            # checked=yes(默认) → 不写属性; unchecked=no → 写 clipping = no
            lambda s: self._set_prop('clipping', False if (s == Qt.CheckState.Checked.value) else 'no')
        )
        form.addRow('', self._clipping_cb)

        self._smooth_scroll_cb = QCheckBox(_('平滑滚动 (smooth_scrolling)'))
        self._smooth_scroll_cb.stateChanged.connect(
            lambda s: self._set_prop('smooth_scrolling', s == Qt.CheckState.Checked.value)
        )
        form.addRow('', self._smooth_scroll_cb)

        self._vscroll_edit = QLineEdit()
        self._vscroll_edit.setPlaceholderText(_('滚动条名称引用'))
        self._vscroll_edit.textChanged.connect(lambda v: self._set_prop('verticalScrollbar', v))
        form.addRow(_('垂直滚动条:'), self._vscroll_edit)

        self._rotation_spin = QDoubleSpinBox()
        self._rotation_spin.setRange(-360.0, 360.0)
        self._rotation_spin.setSingleStep(5.0)
        self._rotation_spin.valueChanged.connect(lambda v: self._set_prop('rotation', round(v, 2)))
        form.addRow(_('旋转 (rotation):'), self._rotation_spin)

    def _build_raw_section(self):
        """
        原始属性编辑器：列出节点中所有未被上方区块覆盖的键值对。
        允许用户直接编辑、删除、添加任意属性，防止未知属性丢失。
        """
        self._raw_group = QGroupBox(_('原始属性编辑器'))
        self._raw_group.setStyleSheet('QGroupBox { font-weight: bold; }')
        self._raw_group.setCheckable(True)
        self._raw_group.setChecked(False)   # 默认折叠

        raw_layout = QVBoxLayout(self._raw_group)
        raw_layout.setContentsMargins(6, 14, 6, 6)
        raw_layout.setSpacing(3)

        note = QLabel(_('显示并编辑所有"未被上方表单覆盖"的属性键值对。\n'
                       '可添加自定义属性或修改不常见属性，修改立即生效。'))
        note.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:8px;')
        note.setWordWrap(True)
        raw_layout.addWidget(note)

        # 属性行容器
        self._raw_rows_widget = QWidget()
        self._raw_rows_layout = QVBoxLayout(self._raw_rows_widget)
        self._raw_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._raw_rows_layout.setSpacing(2)
        raw_layout.addWidget(self._raw_rows_widget)

        # 新增属性行
        add_row = QHBoxLayout()
        self._raw_new_key = QLineEdit()
        self._raw_new_key.setPlaceholderText(_('属性名 (key)'))
        self._raw_new_key.setFixedWidth(120)
        self._raw_new_val = QLineEdit()
        self._raw_new_val.setPlaceholderText(_('属性值 (value)'))
        add_btn = QPushButton('+')
        add_btn.setFixedWidth(28)
        add_btn.setToolTip(_('添加新属性'))
        add_btn.clicked.connect(self._raw_add_property)
        add_row.addWidget(self._raw_new_key)
        add_row.addWidget(self._raw_new_val, 1)
        add_row.addWidget(add_btn)
        raw_layout.addLayout(add_row)

        self._content_layout.addWidget(self._raw_group)

    # 已知的由上方表单管理的属性集（这些属性不在原始编辑器中显示）
    _MANAGED_KEYS: Set[str] = {
        'name', 'position', 'size', 'orientation', 'Orientation',
        'origo', 'origin', 'moveable', 'alwaysTransparent', 'alwaystransparent',
        'spriteType', 'quadTextureSprite', 'scale',
        'buttonText', 'ButtonText', 'text', 'Text', 'font', 'buttonFont',
        'maxWidth', 'maxHeight', 'format', 'text_offset', 'text_color_code', 'fixedSize', 'fixedsize',
        'effect', 'tooltipText', 'pdx_tooltip', 'shortcut', 'clicksound',
        'background',
        'clipping', 'smooth_scrolling', 'verticalScrollbar', 'rotation',
        'centerPosition',
    }

    def _refresh_raw_section(self, node: Optional['WidgetNode']):
        """重建原始属性编辑器中的行。"""
        # 清除现有行
        while self._raw_rows_layout.count():
            item = self._raw_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if node is None:
            return

        # 找出所有未被管理的属性
        unmanaged = {
            k: v for k, v in node.properties.items()
            if k not in self._MANAGED_KEYS
            and not isinstance(v, (dict, list))
        }
        unmanaged_complex = {
            k: v for k, v in node.properties.items()
            if k not in self._MANAGED_KEYS
            and isinstance(v, (dict, list))
        }

        for key, val in sorted(unmanaged.items()):
            self._raw_rows_layout.addWidget(
                self._make_raw_row(key, str(val) if not isinstance(val, bool)
                                   else ('yes' if val else 'no')))

        for key, val in sorted(unmanaged_complex.items()):
            row_widget = self._make_raw_readonly_row(key, str(val))
            self._raw_rows_layout.addWidget(row_widget)

        self._raw_group.setTitle(
            (_('原始属性编辑器（') + str(len(unmanaged) + len(unmanaged_complex)) + _(' 个额外属性）'))
            if (unmanaged or unmanaged_complex) else _('原始属性编辑器')
        )

    def _make_raw_row(self, key: str, val: str) -> QWidget:
        """创建一个可编辑的原始属性行。"""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        key_lbl = QLabel(key)
        key_lbl.setFixedWidth(120)
        key_lbl.setStyleSheet('color:#9cdcfe; font-size:9px;')
        key_lbl.setToolTip(key)
        lay.addWidget(key_lbl)

        val_edit = QLineEdit(val)
        val_edit.setStyleSheet('font-size:9px;')
        val_edit.textChanged.connect(
            lambda v, k=key: self._raw_set_property(k, v))
        lay.addWidget(val_edit, 1)

        del_btn = QPushButton('×')
        del_btn.setFixedSize(20, 20)
        del_btn.setToolTip(_('删除属性 ') + key)
        del_btn.clicked.connect(lambda _, k=key: self._raw_delete_property(k))
        lay.addWidget(del_btn)
        return w

    def _make_raw_readonly_row(self, key: str, val: str) -> QWidget:
        """创建一个只读提示行（复杂类型如 dict/list）。"""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        key_lbl = QLabel(key)
        key_lbl.setFixedWidth(120)
        key_lbl.setStyleSheet('color:#9cdcfe; font-size:9px;')
        lay.addWidget(key_lbl)

        info_lbl = QLabel(_('[复杂类型]  ') + val[:40] + ('...' if len(val) > 40 else ''))
        info_lbl.setStyleSheet(f'color:{ThemeManager.muted_color()}; font-size:9px;')
        info_lbl.setToolTip(val)
        lay.addWidget(info_lbl, 1)
        return w

    def _raw_set_property(self, key: str, value: str):
        if self._updating or self._node is None:
            return
        if value == '':
            self._node.properties.pop(key, None)
        else:
            # 尝试转换为数字类型
            try:
                if '.' in value:
                    self._node.properties[key] = float(value)
                else:
                    self._node.properties[key] = int(value)
            except ValueError:
                if value.lower() == 'yes':
                    self._node.properties[key] = True
                elif value.lower() == 'no':
                    self._node.properties[key] = False
                else:
                    self._node.properties[key] = value
        self.property_changed.emit(self._node)

    def _raw_delete_property(self, key: str):
        if self._node is None:
            return
        self._node.properties.pop(key, None)
        self._refresh_raw_section(self._node)
        self.property_changed.emit(self._node)

    def _raw_add_property(self):
        if self._node is None:
            return
        key = self._raw_new_key.text().strip()
        val = self._raw_new_val.text().strip()
        if not key:
            return
        self._raw_set_property(key, val)
        self._raw_new_key.clear()
        self._raw_new_val.clear()
        self._refresh_raw_section(self._node)

    def _set_enabled(self, enabled: bool):
        for g in [self._id_group, self._geo_group, self._app_group,
                  self._text_group, self._int_group, self._bg_group, self._extra_group,
                  self._raw_group]:
            g.setEnabled(enabled)
        if not enabled:
            self._no_size_widget.setVisible(False)
            self._size_placeholder_label.setVisible(False)
            self._size_editor.setVisible(True)

    def set_doc(self, doc):
        """Set the current GUIDocument for duplicate name detection."""
        self._doc = doc

    def set_node(self, node: Optional[WidgetNode]):
        self._node = node
        self._updating = True
        try:
            if node is None:
                self._title.setText(_('属性面板'))
                self._title.setStyleSheet('')
                self._set_enabled(False)
                self._refresh_raw_section(None)
                return

            self._set_enabled(True)
            color = WIDGET_COLORS.get(node.widget_type, '#888')
            self._title.setText(WIDGET_LABELS.get(node.widget_type, node.widget_type))
            self._title.setStyleSheet(f'color: {color}; font-weight: bold;')
            self._type_label.setText(node.widget_type)
            self._name_edit.setText(node.name)

            x, y = node.position
            self._pos_editor.set_value(x, y)

            is_implicit = node.is_implicit_size_container()
            has_size = node.has_explicit_size_property()
            is_sprite = node.is_sprite_type()

            # Determine size display mode
            if is_implicit:
                # Container without size= in script: show auto-size info + option to create size
                self._size_editor.setVisible(False)
                self._no_size_widget.setVisible(True)
                self._size_placeholder_label.setVisible(False)
                els = getattr(node, '_editor_layout_size', None)
                info = _('自动 (由子控件轮廓计算)')
                if els:
                    info += '  [' + str(els[0]) + ' × ' + str(els[1]) + ']'
                self._no_size_label.setText(info)
                self._size_note.setVisible(False)
            elif not has_size:
                # Widget without size property: show '-' with create button
                self._size_editor.setVisible(False)
                self._no_size_widget.setVisible(True)
                self._size_placeholder_label.setVisible(False)
                els = getattr(node, '_editor_layout_size', None)
                if els:
                    self._no_size_label.setText(f'-  ({els[0]} × {els[1]})')
                else:
                    self._no_size_label.setText('-')
                self._size_note.setVisible(False)
            else:
                # Normal: has explicit size
                self._size_editor.setVisible(True)
                self._no_size_widget.setVisible(False)
                self._size_placeholder_label.setVisible(False)
                w, h = node.size
                self._size_editor.set_value(w, h)
                self._size_editor.setEnabled(not is_sprite)
                if is_sprite:
                    self._size_note.setText(_('[!] spriteType 控件的大小由精灵图决定，\n请用 scale 属性调整显示尺寸。'))
                    self._size_note.setVisible(True)
                else:
                    self._size_note.setVisible(False)

            # orientation — index 0 = default (no key in script)
            self._orient_combo.setCurrentIndex(0)
            if node.has_explicit_orientation():
                ori = str(node.properties.get('orientation') or node.properties.get('Orientation', ''))
                idx = self._find_combo_index_case_insensitive(self._orient_combo, ori)
                if idx < 0:
                    self._orient_combo.addItem(ori)
                    idx = self._orient_combo.count() - 1
                self._orient_combo.setCurrentIndex(idx)

            # origo
            self._origo_combo.setCurrentIndex(0)
            if node.has_explicit_origo():
                origo = str(node.properties.get('origo') or node.properties.get('origin', ''))
                idx2 = self._find_combo_index_case_insensitive(self._origo_combo, origo)
                if idx2 < 0:
                    self._origo_combo.addItem(origo)
                    idx2 = self._origo_combo.count() - 1
                self._origo_combo.setCurrentIndex(idx2)

            props = node.properties
            self._moveable_cb.setChecked(bool(props.get('moveable', False)))
            self._always_transparent_cb.setChecked(bool(props.get('alwaysTransparent', props.get('alwaystransparent', False))))

            # Appearance
            self._sprite_sel.set_value(str(props.get('spriteType', '')))
            self._quad_sel.set_value(str(props.get('quadTextureSprite', '')))
            self._scale_spin.setValue(float(props.get('scale', 1.0)))

            # Text
            bt = str(props.get('buttonText', ''))
            self._button_text_edit.setText(bt)
            rm = ResourceManager.instance()
            if bt:
                loc = rm.get_loc(bt)
                self._loc_preview.setText('"' + loc + '"' if loc != bt else _('(未找到本地化)'))
            else:
                self._loc_preview.setText('')

            self._text_edit.setText(str(props.get('text', '')))
            self._font_edit.setText(str(props.get('font', '')))
            self._button_font_edit.setText(str(props.get('buttonFont', '')))
            self._max_w_spin.setValue(int(props.get('maxWidth', 0)))
            self._max_h_spin.setValue(int(props.get('maxHeight', 0)))

            fmt = str(props.get('format', ''))
            fi = self._format_combo.findText(fmt)
            self._format_combo.setCurrentIndex(max(0, fi))

            to = props.get('text_offset', {})
            if isinstance(to, dict):
                self._text_offset_editor.set_value(int(to.get('x', 0)), int(to.get('y', 0)))

            self._color_code_edit.setText(str(props.get('text_color_code', '')))
            self._fixed_size_cb.setChecked(bool(props.get('fixedSize', props.get('fixedsize', False))))

            # Interaction
            self._effect_edit.setText(str(props.get('effect', '')))

            tt = str(props.get('tooltipText', ''))
            self._tooltip_text_edit.setText(tt)
            if tt:
                tt_loc = rm.get_loc(tt)
                self._tooltip_loc_preview.setText('"' + tt_loc + '"' if tt_loc != tt else _('(未找到)'))
            else:
                self._tooltip_loc_preview.setText('')

            self._pdx_tooltip_edit.setText(str(props.get('pdx_tooltip', '')))
            self._shortcut_edit.setText(str(props.get('shortcut', '')))
            self._click_sound_edit.setText(str(props.get('clicksound', '')))

            # Background
            bg = node.get_background()
            if bg:
                bg_s = bg.get('quadTextureSprite', bg.get('spriteType', ''))
                self._bg_sprite_sel.set_value(str(bg_s))
                self._bg_transparent_cb.setChecked(bool(bg.get('alwaysTransparent', False)))
            else:
                self._bg_sprite_sel.set_value('')
                self._bg_transparent_cb.setChecked(False)

            # Extra
            # absent = Stellaris default = clipping enabled; 'no'/'false'/'0' = disabled
            _clip_raw = props.get('clipping', 'yes')
            if isinstance(_clip_raw, bool):
                _clip_on = _clip_raw
            else:
                _clip_on = str(_clip_raw).lower() not in ('no', 'false', '0')
            self._clipping_cb.setChecked(_clip_on)
            self._smooth_scroll_cb.setChecked(bool(props.get('smooth_scrolling', False)))
            self._vscroll_edit.setText(str(props.get('verticalScrollbar', '')))
            self._rotation_spin.setValue(float(props.get('rotation', 0.0)))

            # Show/hide sections
            is_text = node.widget_type in ('instantTextBoxType', 'textBoxType', 'editBoxType')
            is_btn = node.widget_type in ('buttonType', 'effectButtonType')
            is_cont = node.widget_type in ('containerWindowType', 'scrollAreaType')

            # containerWindowType has no sprite properties (only background sub-block)
            self._app_group.setVisible(not is_cont)
            self._text_group.setVisible(is_text or is_btn)
            self._int_group.setVisible(node.widget_type == 'effectButtonType')
            self._bg_group.setVisible(is_cont or node.widget_type in ('listboxType',))
            self._extra_group.setVisible(is_cont)

            # 原始属性编辑器：始终刷新
            self._refresh_raw_section(node)

        finally:
            self._updating = False

    @staticmethod
    def _find_combo_index_case_insensitive(combo: QComboBox, text: str) -> int:
        t = text.strip()
        idx = combo.findText(t, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            return idx
        tl = t.lower()
        for i in range(combo.count()):
            if combo.itemText(i).lower() == tl:
                return i
        return -1

    def _on_orient_index_changed(self, idx: int):
        if self._updating or self._node is None:
            return
        if idx <= 0:
            self._node.properties.pop('orientation', None)
            self._node.properties.pop('Orientation', None)
        else:
            self._node.properties['orientation'] = self._orient_combo.itemText(idx)
        self.property_changed.emit(self._node)

    def _on_origo_index_changed(self, idx: int):
        if self._updating or self._node is None:
            return
        if idx <= 0:
            self._node.properties.pop('origo', None)
            self._node.properties.pop('origin', None)
        else:
            self._node.properties['origo'] = self._origo_combo.itemText(idx)
        self.property_changed.emit(self._node)

    def _on_name_changed(self, value: str):
        """Handle name field change; warn if duplicate."""
        # 捕获改名前的旧名，用于同步编组
        old_name = self._node.name if (self._node and not self._updating) else ''
        self._set_prop('name', value)
        # 通知编组系统更新成员名
        if old_name and value and old_name != value:
            self.widget_renamed.emit(old_name, value)
        if self._node is None:
            return
        # Warn about duplicate names
        doc = getattr(self, '_doc', None)
        if doc is not None and value:
            dups = [w for w in doc.all_widgets() if w.name == value and w is not self._node]
            if dups:
                self._name_dup_label.setText(_('[!] 名称重复（已有 ') + str(len(dups)) + _(' 个同名控件）'))
                self._name_dup_label.show()
                self._name_edit.setStyleSheet('border: 1px solid #e74c3c;')
                return
        self._name_dup_label.hide()
        self._name_edit.setStyleSheet('')

    def _set_prop(self, key: str, value):
        if self._updating or self._node is None:
            return
        if isinstance(value, str) and not value:
            self._node.properties.pop(key, None)
        elif isinstance(value, bool) and value is False:
            self._node.properties.pop(key, None)
        else:
            self._node.properties[key] = value
        # Update localization preview
        if key == 'buttonText':
            rm = ResourceManager.instance()
            loc = rm.get_loc(str(value))
            self._loc_preview.setText(f'"{loc}"' if value and loc != value else '')
        elif key == 'tooltipText':
            rm = ResourceManager.instance()
            loc = rm.get_loc(str(value))
            self._tooltip_loc_preview.setText(f'"{loc}"' if value and loc != value else '')
        self.property_changed.emit(self._node)

    def _on_pos_changed(self, x: int, y: int):
        if self._updating or self._node is None:
            return
        self._node.position = (x, y)
        self.property_changed.emit(self._node)

    def _on_size_changed(self, w: int, h: int):
        if self._updating or self._node is None:
            return
        self._node.size = (w, h)
        self.property_changed.emit(self._node)

    def _on_create_size(self):
        """Create the size property for a node that doesn't have one."""
        if self._node is None:
            return
        # Use computed layout size if available, otherwise default
        els = getattr(self._node, '_editor_layout_size', None)
        if els:
            w, h = int(els[0]), int(els[1])
        else:
            w, h = 100, 50
        self._node.size = (w, h)
        # Refresh the display
        self.set_node(self._node)
        self.property_changed.emit(self._node)

    def _on_sprite_changed(self, v: str):
        if self._updating or self._node is None:
            return
        if v:
            self._node.properties['spriteType'] = v
            self._node.properties.pop('quadTextureSprite', None)
        else:
            self._node.properties.pop('spriteType', None)
        self.property_changed.emit(self._node)

    def _on_bg_sprite_changed(self, v: str):
        if self._updating or self._node is None:
            return
        bg = self._node.properties.get('background', {})
        if not isinstance(bg, dict):
            bg = {}
        if v:
            bg['quadTextureSprite'] = v
            bg.setdefault('name', 'background')
            self._node.properties['background'] = bg
        else:
            self._node.properties.pop('background', None)
        self.property_changed.emit(self._node)

    def _on_bg_transparent_changed(self, state):
        if self._updating or self._node is None:
            return
        bg = self._node.properties.get('background', {})
        if isinstance(bg, dict):
            checked = state == Qt.CheckState.Checked.value
            if checked:
                bg['alwaysTransparent'] = True
            else:
                bg.pop('alwaysTransparent', None)
            self._node.properties['background'] = bg
        self.property_changed.emit(self._node)

    def refresh_from_node(self, node: Optional[WidgetNode] = None):
        if node:
            self._node = node
        self.set_node(self._node)
