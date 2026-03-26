"""
GUI widget data model for Stellaris .gui files.

Key concepts (from Stellaris GUI system):
  - orientation: where in the PARENT the widget's anchor point sits
  - origo: which point on THIS widget aligns with the anchor
  - position: offset FROM the anchor TO the origo point
  
  Widget top-left in parent coords:
    anchor = orientation_to_anchor(parent_w, parent_h, orientation)
    origo_offset = origo_to_offset(widget_w, widget_h, origo)
    top_left = anchor + position - origo_offset

  spriteType: size property is IGNORED for visual display; use scale attribute.
    displayed size = sprite_natural_size × scale
  quadTextureSprite: corneredTileSpriteType, uses widget's size property.
  background: fills the entire parent container; size is inherited.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from .pdx_parser import pairs_to_dict, parse_text


# ---------------------------------------------------------------------------
# Widget types — those that create WidgetNode children
# ---------------------------------------------------------------------------

CONTAINER_TYPES = {
    'containerWindowType',
    'scrollAreaType',
    'dropDownBoxType',   # dropDownBoxType is essentially a container with special sub-elements
    'expandedWindow',    # expandedWindow is a toggleable sub-container inside dropDownBoxType
    'windowType',        # floating container element
}

# Canonical widget type keys (case style used internally by editor)
_WIDGET_KEYS_CANONICAL = [
    'containerWindowType', 'iconType', 'buttonType',
    'effectButtonType',
    'instantTextBoxType', 'textBoxType', 'editBoxType',
    'checkBoxType', 'listboxType', 'scrollAreaType',
    'overlappingElementsBoxType',
    'gridBoxType', 'smoothListboxType',
    'extendedScrollbarType', 'scrollbarType',
    'dropDownBoxType',
    'expandButton',      # trigger button inside dropDownBoxType
    'expandedWindow',    # toggleable container inside dropDownBoxType
    'guiButtonType',     # button subtype used inside scrollbarType / spinnerType
    'spinnerType',       # clickable carousel element
    'windowType',        # floating container element
    'positionType',
]

# These keys in a block create a child WidgetNode
_WIDGET_KEYS = set(_WIDGET_KEYS_CANONICAL)

# These keys are sub-blocks stored as property dicts (NOT child WidgetNodes)
_PROPERTY_BLOCK_KEYS = {
    'background', 'track', 'slider', 'increaseButton', 'decreaseButton',
    'animation',
    # expandButton / expandedWindow intentionally REMOVED — they are real child WidgetNodes
}

# All user-facing widget types (for library display)
WIDGET_TYPES = {
    'containerWindowType', 'iconType', 'buttonType', 'effectButtonType',
    'instantTextBoxType', 'textBoxType', 'editBoxType', 'checkBoxType',
    'listboxType', 'scrollAreaType', 'overlappingElementsBoxType',
    'gridBoxType', 'smoothListboxType', 'extendedScrollbarType',
    'guiButtonType', 'spinnerType', 'windowType',
}

# Chinese labels for each widget type
WIDGET_LABELS = {
    'containerWindowType':          '容器窗口 (containerWindowType)',
    'iconType':                     '图标 (iconType)',
    'buttonType':                   '按钮 (buttonType)',
    'effectButtonType':             '效果按钮 (effectButtonType)',
    'instantTextBoxType':           '文本框 (instantTextBoxType)',
    'textBoxType':                  '滚动文本框 (textBoxType)',
    'editBoxType':                  '输入框 (editBoxType)',
    'checkBoxType':                 '复选框 (checkBoxType)',
    'listboxType':                  '列表框 (listboxType)',
    'scrollAreaType':               '滚动区域 (scrollAreaType)',
    'overlappingElementsBoxType':   '重叠元素框 (overlappingElementsBoxType)',
    'gridBoxType':                  '网格框 (gridBoxType)',
    'smoothListboxType':            '平滑列表 (smoothListboxType)',
    'extendedScrollbarType':        '扩展滚动条 (extendedScrollbarType)',
    'dropDownBoxType':              '下拉框 (dropDownBoxType)',
    'expandButton':                 '展开按钮 (expandButton)',
    'expandedWindow':               '展开窗口 (expandedWindow)',
    'scrollbarType':                '滚动条 (scrollbarType)',
    'guiButtonType':                'GUI按钮 (guiButtonType)',
    'spinnerType':                  '旋转选择器 (spinnerType)',
    'windowType':                   '浮动窗口 (windowType)',
    'positionType':                 '位置锚点 (positionType)',
}

# Display colors for canvas
WIDGET_COLORS = {
    'containerWindowType':          '#3a7abf',
    'iconType':                     '#4a9f5c',
    'buttonType':                   '#b86a00',
    'effectButtonType':             '#c0392b',
    'instantTextBoxType':           '#8e44ad',
    'textBoxType':                  '#7f8c8d',
    'editBoxType':                  '#16a085',
    'checkBoxType':                 '#d35400',
    'listboxType':                  '#1abc9c',
    'scrollAreaType':               '#2980b9',
    'overlappingElementsBoxType':   '#7d3c98',
    'gridBoxType':                  '#c0392b',
    'smoothListboxType':            '#1abc9c',
    'extendedScrollbarType':        '#95a5a6',
    'scrollbarType':                '#7f8c8d',
    'dropDownBoxType':              '#e67e22',
    'expandButton':                 '#d35400',
    'expandedWindow':               '#a04000',
    'guiButtonType':                '#b07d32',
    'spinnerType':                  '#d4a017',
    'windowType':                   '#2c6fbb',
    'positionType':                 '#5d6d7e',
}

DEFAULT_SIZE = {
    'containerWindowType':          (200, 150),
    'iconType':                     (32, 32),
    'buttonType':                   (142, 34),
    'effectButtonType':             (142, 34),
    'instantTextBoxType':           (200, 20),
    'textBoxType':                  (200, 80),
    'editBoxType':                  (200, 30),
    'checkBoxType':                 (24, 24),
    'listboxType':                  (200, 150),
    'scrollAreaType':               (200, 150),
    'overlappingElementsBoxType':   (200, 30),
    'gridBoxType':                  (200, 200),
    'smoothListboxType':            (200, 150),
    'extendedScrollbarType':        (20, 200),  # vertical scrollbar default
    'scrollbarType':                (20, 200),
    'dropDownBoxType':              (200, 30),
    'expandButton':                 (142, 30),
    'expandedWindow':               (200, 150),
    'guiButtonType':                (30, 30),
    'spinnerType':                  (120, 30),
    'windowType':                   (200, 150),
}

# All valid orientation values from CWT gui_types.cwt enum[direction]
# Case-insensitive per CWT comment; canonical form is UPPER_CASE here
ORIENTATIONS = [
    'UPPER_LEFT', 'UPPER_CENTER', 'UPPER_RIGHT',
    'CENTER_LEFT', 'CENTER', 'CENTER_RIGHT',
    'LOWER_LEFT', 'LOWER_CENTER', 'LOWER_RIGHT',
    'CENTER_UP', 'CENTER_DOWN',
    'LEFT', 'RIGHT', 'TOP', 'BOTTOM',
    'TOP_LEFT', 'TOP_RIGHT', 'BOTTOM_LEFT', 'BOTTOM_RIGHT',
    'LEFT_UP', 'LEFT_DOWN', 'RIGHT_UP', 'RIGHT_DOWN',
]

# Fractional (x, y) anchor within the parent — built from CWT enum[direction]
# x: 0.0=left, 0.5=center, 1.0=right
# y: 0.0=top,  0.5=center, 1.0=bottom
_ORIENTATION_FRACS: dict = {
    # ── UPPER row ──────────────────────────────────────────────────────
    'UPPER_LEFT':     (0.0, 0.0),
    'UPPER_CENTER':   (0.5, 0.0),
    'UPPER_RIGHT':    (1.0, 0.0),
    # TOP_* aliases for UPPER_*
    'TOP':            (0.5, 0.0),
    'TOP_LEFT':       (0.0, 0.0),
    'TOP_RIGHT':      (1.0, 0.0),
    # CENTER_UP / CENTERED_UP / CENTERUP – horiz center, vert top
    'CENTER_UP':      (0.5, 0.0),
    'CENTERUP':       (0.5, 0.0),
    'CENTERED_UP':    (0.5, 0.0),
    'LEFT_UP':        (0.0, 0.0),
    'RIGHT_UP':       (1.0, 0.0),
    # ── CENTER row ─────────────────────────────────────────────────────
    'CENTER_LEFT':    (0.0, 0.5),
    'CENTERED_LEFT':  (0.0, 0.5),
    'LEFT':           (0.0, 0.5),
    'CENTER':         (0.5, 0.5),
    'CENTER_CENTER':  (0.5, 0.5),
    'CENTER_RIGHT':   (1.0, 0.5),
    'CENTERED_RIGHT': (1.0, 0.5),
    'RIGHT':          (1.0, 0.5),
    # ── LOWER / BOTTOM row ─────────────────────────────────────────────
    'LOWER_LEFT':     (0.0, 1.0),
    'LOWER_CENTER':   (0.5, 1.0),
    'LOWER_RIGHT':    (1.0, 1.0),
    'BOTTOM':         (0.5, 1.0),
    'BOTTOM_LEFT':    (0.0, 1.0),
    'BOTTOM_RIGHT':   (1.0, 1.0),
    # CENTER_DOWN / CENTERED_DOWN – horiz center, vert bottom
    'CENTER_DOWN':    (0.5, 1.0),
    'CENTERED_DOWN':  (0.5, 1.0),
    'LEFT_DOWN':      (0.0, 1.0),
    'RIGHT_DOWN':     (1.0, 1.0),
}


# ---------------------------------------------------------------------------
# Position calculation helpers
# ---------------------------------------------------------------------------

def _normalize_orientation(raw: str) -> str:
    """Normalise to UPPER_CASE with underscores; remove surrounding quotes."""
    return (raw or '').strip().strip('"').upper().replace('-', '_').replace(' ', '_')


def orientation_to_anchor(parent_w: float, parent_h: float, orientation: str) -> Tuple[float, float]:
    """
    Return the (x, y) anchor point **inside the parent** for the given orientation.
    Covers every value in the CWT enum[direction] list.
    """
    ori = _normalize_orientation(orientation)
    fx, fy = _ORIENTATION_FRACS.get(ori, (0.0, 0.0))   # default UPPER_LEFT
    return parent_w * fx, parent_h * fy


def origo_to_offset(widget_w: float, widget_h: float, origo: str) -> Tuple[float, float]:
    """
    Return the origo offset: distance from widget top-left to the origo point.
    Same enum as orientation; default UPPER_LEFT → (0, 0).
    """
    ori = _normalize_orientation(origo)
    fx, fy = _ORIENTATION_FRACS.get(ori, (0.0, 0.0))
    return widget_w * fx, widget_h * fy


def effective_origo(node: 'WidgetNode') -> str:
    """
    Return the effective origo string for position calculation.
    centerPosition = yes behaves like origo = center (Stellaris wiki).
    """
    cp = node.properties.get('centerPosition', '')
    if str(cp).strip().lower() in ('yes', 'true', '1'):
        return 'CENTER'
    return node.origo


def compute_widget_topleft(
    parent_w: float, parent_h: float,
    widget_w: float, widget_h: float,
    orientation: str, origo: str,
    pos_x: float, pos_y: float,
) -> Tuple[float, float]:
    """
    Compute the top-left corner of a widget within its parent coordinate space.
      qt_tl = anchor + stellaris_pos - origo_offset
    """
    ax, ay = orientation_to_anchor(parent_w, parent_h, orientation)
    ox, oy = origo_to_offset(widget_w, widget_h, origo)
    return ax + pos_x - ox, ay + pos_y - oy


def reverse_compute_position(
    qt_x: float, qt_y: float,
    parent_w: float, parent_h: float,
    widget_w: float, widget_h: float,
    orientation: str, origo: str,
) -> Tuple[int, int]:
    """
    Reverse of compute_widget_topleft.
    Given a widget's Qt top-left position in parent coords, recover the
    Stellaris script position value.
      stellaris_pos = qt_tl - anchor + origo_offset
    """
    ax, ay = orientation_to_anchor(parent_w, parent_h, orientation)
    ox, oy = origo_to_offset(widget_w, widget_h, origo)
    return int(round(qt_x - ax + ox)), int(round(qt_y - ay + oy))


# ---------------------------------------------------------------------------
# Localization / caption helpers (mods interchange buttonText, text, title, etc.)
# ---------------------------------------------------------------------------

TEXT_LOC_PROPERTY_KEYS: Tuple[str, ...] = (
    'buttonText', 'ButtonText',
    'text', 'Text',
    'caption', 'Caption',
    'label', 'Label',
    'title', 'Title',
)


def coerce_localization_key(value: Any) -> Optional[str]:
    """
    Normalize a .gui property value to a localization key string.
    Handles quoted strings, numeric keys, bare tokens, and single-element lists.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != int(value):
            s = str(value).strip()
        else:
            s = str(int(value))
        return s if s else None
    if isinstance(value, str):
        s = value.strip().strip('"')
        return s if s else None
    if isinstance(value, (list, tuple)):
        for item in value:
            s = coerce_localization_key(item)
            if s:
                return s
    return None


# ---------------------------------------------------------------------------
# WidgetNode
# ---------------------------------------------------------------------------

@dataclass
class WidgetNode:
    """
    Represents a single widget in the Stellaris GUI hierarchy.

    Properties are stored as a flat dict. Sub-blocks like `background`,
    `track`, `slider` are stored as nested dicts in properties (NOT child nodes).
    Children are actual widget nodes (containerWindowType, iconType, etc.).
    """
    # Names of mandatory vanilla controls that must not be deleted
    VANILLA_PROTECTED_NAMES: ClassVar[frozenset] = frozenset({
        'focus_button', 'heading', 'alien_message_background', 'confirm_button',
        'portrait_background', 'portrait', 'empire_info_bg', 'empire_name',
        'empire_government_type', 'empire_personality_type', 'empire_ethics_icons',
        'empire_flag', 'leader_details', 'opinion_window', 'EVENT_DIPLO',
        'alien_message',
    })

    widget_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List['WidgetNode'] = field(default_factory=list)
    parent: Optional['WidgetNode'] = field(default=None, repr=False, compare=False)
    _dirty: bool = field(default=True, repr=False, compare=False)
    # Resolved bounds for implicit-size containers (never written to .gui)
    _editor_layout_size: Optional[Tuple[int, int]] = field(default=None, repr=False, compare=False)
    # Pixel size after Stellaris rules (negative = parent−N, % = percent of parent); set by layout pass
    _editor_resolved_size: Optional[Tuple[int, int]] = field(default=None, repr=False, compare=False)
    # Editor-only protection flag (not persisted)
    _protected: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self):
        # Auto-protect known vanilla mandatory controls
        if self.name in self.VANILLA_PROTECTED_NAMES:
            self._protected = True

    # ---- name ----
    @property
    def name(self) -> str:
        return str(self.properties.get('name', ''))

    @name.setter
    def name(self, value: str):
        self.properties['name'] = value

    # ---- position ----
    @property
    def position(self) -> Tuple[int, int]:
        pos = self.properties.get('position', None)
        if pos is None:
            return (0, 0)
        if isinstance(pos, dict):
            return (int(pos.get('x', 0)), int(pos.get('y', 0)))
        if isinstance(pos, list) and pos and isinstance(pos[0], tuple):
            d = pairs_to_dict(pos)
            return (int(d.get('x', 0)), int(d.get('y', 0)))
        return (0, 0)

    @position.setter
    def position(self, value: Tuple[int, int]):
        self.properties['position'] = {'x': int(value[0]), 'y': int(value[1])}
        self._dirty = True

    def has_explicit_size_property(self) -> bool:
        """True if the script contains a size = { ... } line (key present)."""
        return 'size' in self.properties

    def is_implicit_size_container(self) -> bool:
        """containerWindowType / scrollAreaType without size= in source."""
        return self.widget_type in CONTAINER_TYPES and not self.has_explicit_size_property()

    def has_explicit_orientation(self) -> bool:
        return 'orientation' in self.properties or 'Orientation' in self.properties

    def has_explicit_origo(self) -> bool:
        return 'origo' in self.properties or 'origin' in self.properties

    # ---- size ----
    @property
    def size(self) -> Tuple[int, int]:
        """
        Parsed size from script. If size= is **absent** on a container, returns (0, 0)
        — do NOT invent 200×150, that breaks child CENTER anchors and misleads the UI.
        Non-containers without size still use editor defaults for placement.
        When size is absent, maxWidth/maxHeight are used as a display fallback so that
        widgets like instantTextBoxType with only maxWidth/maxHeight show correctly.
        """
        sz = self.properties.get('size', None)
        if sz is None:
            if self.widget_type in CONTAINER_TYPES:
                return (0, 0)
            # Fallback: use maxWidth / maxHeight if present
            try:
                mw = int(self.properties.get('maxWidth', 0))
            except (TypeError, ValueError):
                mw = 0
            try:
                mh = int(self.properties.get('maxHeight', 0))
            except (TypeError, ValueError):
                mh = 0
            if mw > 0 or mh > 0:
                default_w, default_h = DEFAULT_SIZE.get(self.widget_type, (100, 30))
                return (max(1, mw or default_w), max(1, mh or default_h))
            return DEFAULT_SIZE.get(self.widget_type, (100, 30))
        if isinstance(sz, dict):
            pw, ph = float(_EDITOR_SIZE_FALLBACK_PARENT[0]), float(_EDITOR_SIZE_FALLBACK_PARENT[1])
            dw, dh = DEFAULT_SIZE.get(self.widget_type, (100, 30))
            w = sz.get('width', sz.get('x', dw))
            h = sz.get('height', sz.get('y', dh))
            return (
                _resolve_stellaris_size_dim(w, pw, float(dw)),
                _resolve_stellaris_size_dim(h, ph, float(dh)),
            )
        if isinstance(sz, list) and sz and isinstance(sz[0], tuple):
            d = pairs_to_dict(sz)
            pw, ph = float(_EDITOR_SIZE_FALLBACK_PARENT[0]), float(_EDITOR_SIZE_FALLBACK_PARENT[1])
            dw, dh = DEFAULT_SIZE.get(self.widget_type, (100, 30))
            w = d.get('width', d.get('x', dw))
            h = d.get('height', d.get('y', dh))
            return (
                _resolve_stellaris_size_dim(w, pw, float(dw)),
                _resolve_stellaris_size_dim(h, ph, float(dh)),
            )
        if self.widget_type in CONTAINER_TYPES:
            return (0, 0)
        return DEFAULT_SIZE.get(self.widget_type, (100, 30))

    @size.setter
    def size(self, value: Tuple[int, int]):
        self.properties['size'] = {'width': max(1, int(value[0])), 'height': max(1, int(value[1]))}
        self._dirty = True

    def clear_size_property(self):
        """Remove size from script (implicit container)."""
        self.properties.pop('size', None)
        self._editor_layout_size = None
        self._dirty = True

    # ---- orientation ----
    @property
    def orientation(self) -> str:
        """Empty string if not in script — geometry uses UPPER_LEFT equivalent."""
        o = self.properties.get('orientation', self.properties.get('Orientation', ''))
        return str(o).strip() if o else ''

    @orientation.setter
    def orientation(self, value: str):
        self.properties['orientation'] = value
        self._dirty = True

    # ---- origo ----
    @property
    def origo(self) -> str:
        o = self.properties.get('origo', self.properties.get('origin', ''))
        return str(o).strip() if o else ''

    @origo.setter
    def origo(self, value: str):
        self.properties['origo'] = value
        self._dirty = True

    # ---- scale ----
    @property
    def scale(self) -> float:
        s = self.properties.get('scale', 1.0)
        try:
            return float(s)
        except (TypeError, ValueError):
            return 1.0

    @scale.setter
    def scale(self, value: float):
        self.properties['scale'] = round(float(value), 4)
        self._dirty = True

    # ---- sprite ----
    def get_sprite_name(self) -> Optional[str]:
        for key in ('spriteType', 'quadTextureSprite'):
            v = self.properties.get(key)
            if v and isinstance(v, str):
                return v.strip().strip('"')
        return None

    def get_text_localization_key(self) -> Optional[str]:
        """First usable caption key among common property names (buttonText vs text, etc.)."""
        for k in TEXT_LOC_PROPERTY_KEYS:
            s = coerce_localization_key(self.properties.get(k))
            if s:
                return s
        return None

    def get_sprite_frame_index(self) -> int:
        """GUI `frame` for multi-frame spriteType / quadTextureSprite (0-based in engine)."""
        for k in ('frame', 'Frame', 'spriteFrame', 'sprite_frame'):
            v = self.properties.get(k)
            if v is None:
                continue
            try:
                return int(float(v))
            except (TypeError, ValueError):
                continue
        return 0

    def get_background_sprite_frame_index(self) -> int:
        """Optional `frame` inside a `background = { ... }` block."""
        bg = self.get_background()
        if not isinstance(bg, dict):
            return 0
        for k in ('frame', 'Frame', 'spriteFrame', 'sprite_frame'):
            v = bg.get(k)
            if v is None:
                continue
            try:
                return int(float(v))
            except (TypeError, ValueError):
                continue
        return 0

    def editor_expand_fixed_size_for_caption(self, w: int, h: int) -> Tuple[int, int]:
        """
        Editor-only: ensure fixed-mode buttons are tall enough to show localized
        caption under the type header (small sprite + text was clipping body text).
        """
        wt = self.widget_type.lower()
        if wt not in ('effectbuttontype', 'buttontype', 'guibuttontype'):
            return w, h
        if not self.get_text_localization_key():
            return w, h
        return w, max(h, 44)

    def is_sprite_type(self) -> bool:
        """True if widget uses spriteType (fixed size from image, uses scale)."""
        return bool(self.properties.get('spriteType'))

    def is_quad_sprite(self) -> bool:
        """True if widget uses quadTextureSprite (scalable, uses size property)."""
        return bool(self.properties.get('quadTextureSprite'))

    def get_background(self) -> Optional[Dict[str, Any]]:
        """Return the background sub-block dict, or None."""
        bg = self.properties.get('background')
        if isinstance(bg, dict):
            return bg
        return None

    # ---- tooltips ----
    def get_tooltip_key(self) -> Optional[str]:
        """Return the tooltip localization key, if any."""
        for k in ('tooltipText', 'pdx_tooltip', 'tooltip', 'custom_tooltip'):
            v = self.properties.get(k)
            if v:
                return str(v)
        return None

    # ---- helpers ----
    def is_container(self) -> bool:
        return self.widget_type in CONTAINER_TYPES or self.widget_type == 'containerWindowType'

    def add_child(self, child: 'WidgetNode'):
        child.parent = self
        self.children.append(child)

    def insert_child(self, index: int, child: 'WidgetNode'):
        child.parent = self
        self.children.insert(index, child)

    def remove_child(self, child: 'WidgetNode'):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def clone(self) -> 'WidgetNode':
        new = WidgetNode(
            widget_type=self.widget_type,
            properties=copy.deepcopy(self.properties),
        )
        for child in self.children:
            new.add_child(child.clone())
        return new

    def compute_topleft_in_parent(self, parent_w: float, parent_h: float) -> Tuple[float, float]:
        """
        Compute top-left position within the parent's coordinate space.
        Uses orientation + origo + position.
        For spriteType widgets without size set, the display size may differ,
        but we use the declared size here (caller should override with natural size if known).
        """
        w, h = self.size
        pos_x, pos_y = self.position
        return compute_widget_topleft(
            parent_w, parent_h, w, h,
            self.orientation, self.origo,
            pos_x, pos_y
        )


# ---------------------------------------------------------------------------
# GUIDocument
# ---------------------------------------------------------------------------

@dataclass
class GUIDocument:
    """Represents a parsed .gui file."""
    file_path: str = ''
    roots: List[WidgetNode] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    modified: bool = False

    def all_widgets(self) -> List[WidgetNode]:
        result = []
        def _collect(node: WidgetNode):
            result.append(node)
            for child in node.children:
                _collect(child)
        for root in self.roots:
            _collect(root)
        return result

    def find_by_name(self, name: str) -> Optional[WidgetNode]:
        for w in self.all_widgets():
            if w.name == name:
                return w
        return None


# ---------------------------------------------------------------------------
# Parser: PDX pairs → WidgetNode tree
# ---------------------------------------------------------------------------

def _normalize_widget_key(key: str) -> str:
    """Normalize widget type key to canonical camelCase form (case-insensitive)."""
    canonical = _WIDGET_KEYS_LOWER.get((key or '').lower())
    return canonical if canonical else key


# Precomputed lookup for O(1) case-insensitive matching.
# IMPORTANT: build from ordered canonical list, not set, to avoid random canonical case.
_WIDGET_KEYS_LOWER = {k.lower(): k for k in _WIDGET_KEYS_CANONICAL}


def _build_node(widget_type: str, pairs: list) -> WidgetNode:
    """Build a WidgetNode from a list of (key, value) pairs."""
    node = WidgetNode(widget_type=_normalize_widget_key(widget_type))
    props = {}
    children = []

    for key, val in pairs:
        key_lower = key.lower()
        # Skip resolution-scale override blocks — game-only branches irrelevant to editing
        if key_lower == 'if_scaled_resolution':
            continue
        normalized_key = _WIDGET_KEYS_LOWER.get(key_lower, key)

        if normalized_key in _WIDGET_KEYS and isinstance(val, list):
            child = _build_node(normalized_key, val)
            children.append(child)
        elif key_lower in {k.lower() for k in _PROPERTY_BLOCK_KEYS} and isinstance(val, list):
            # Property sub-block → store as dict
            canonical_key = next(
                (k for k in _PROPERTY_BLOCK_KEYS if k.lower() == key_lower), key
            )
            props[canonical_key] = pairs_to_dict(val)
        elif key == '_block' or key == '_value':
            pass
        else:
            # Regular scalar or already-converted property
            if key in props:
                existing = props[key]
                if not isinstance(existing, list):
                    props[key] = [existing]
                props[key].append(val)
            else:
                if isinstance(val, list) and val and isinstance(val[0], tuple):
                    val = pairs_to_dict(val)
                props[key] = val

    node.properties = props
    for child in children:
        node.add_child(child)
    return node


def parse_gui_file(path: str) -> GUIDocument:
    """Parse a .gui or .guicore file into a GUIDocument.
    Uses multi-encoding fallback and error recovery for robustness with modded files.
    """
    from .pdx_parser import parse_file, ParseError
    try:
        pairs = parse_file(path)
    except ParseError as e:
        import warnings
        warnings.warn(f'PDX parse error in {path}: {e}')
        return GUIDocument(file_path=path)
    except Exception as e:
        import warnings
        warnings.warn(f'Unexpected error loading {path}: {e}')
        return GUIDocument(file_path=path)

    doc = GUIDocument(file_path=path)
    _process_pairs_into_doc(pairs, doc)
    return doc


def parse_gui_text(text: str, file_path: str = '<text>') -> GUIDocument:
    """Parse .gui text content into a GUIDocument."""
    from .pdx_parser import parse_text as _parse_text
    try:
        pairs = _parse_text(text)
    except Exception:
        return GUIDocument(file_path=file_path)

    doc = GUIDocument(file_path=file_path)
    _process_pairs_into_doc(pairs, doc)
    return doc


def _process_pairs_into_doc(pairs: list, doc: GUIDocument):
    _all_widget_keys_lower = {k.lower() for k in _WIDGET_KEYS}
    for key, val in pairs:
        key_lower = key.lower()
        if key_lower == 'guitypes' and isinstance(val, list):
            for sub_key, sub_val in val:
                if sub_key.lower() in _all_widget_keys_lower and isinstance(sub_val, list):
                    node = _build_node(sub_key, sub_val)
                    doc.roots.append(node)
        elif key_lower in _all_widget_keys_lower and isinstance(val, list):
            node = _build_node(key, val)
            doc.roots.append(node)


# Parent dimensions used only in WidgetNode.size when % / negative appear before layout runs
_EDITOR_SIZE_FALLBACK_PARENT: Tuple[int, int] = (1920, 1080)


def _resolve_stellaris_size_dim(raw: Any, parent_dim: float, fallback: float) -> int:
    """
    Stellaris GUI size rules (Clausewitz):
    - Negative value N: parent inner size + N (N is typically negative, e.g. -10 → parent−10).
    - String ending with %: percentage of parent inner size.
    """
    if raw is None:
        return max(1, int(fallback))
    if isinstance(raw, str):
        rs = raw.strip()
        if rs.endswith('%'):
            try:
                pct = float(rs.rstrip('%').strip())
                return max(1, int(float(parent_dim) * pct / 100.0))
            except ValueError:
                return max(1, int(fallback))
        try:
            v = float(rs)
        except ValueError:
            return max(1, int(fallback))
    else:
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return max(1, int(fallback))
    if v < 0:
        return max(1, int(float(parent_dim) + v))
    return max(1, int(v))


def _raw_size_dict(node: 'WidgetNode') -> Dict[str, Any]:
    sz = node.properties.get('size')
    if isinstance(sz, dict):
        return sz
    if isinstance(sz, list) and sz and isinstance(sz[0], tuple):
        return pairs_to_dict(sz)
    return {}


def resolve_size_for_parent(node: 'WidgetNode', parent_pw: float, parent_ph: float) -> Tuple[int, int]:
    """Pixel size from size = { } using Stellaris negative / % rules."""
    d = _raw_size_dict(node)
    dw, dh = DEFAULT_SIZE.get(node.widget_type, (100, 30))
    w_raw = d.get('width', d.get('x', dw))
    h_raw = d.get('height', d.get('y', dh))
    return (
        _resolve_stellaris_size_dim(w_raw, parent_pw, float(dw)),
        _resolve_stellaris_size_dim(h_raw, parent_ph, float(dh)),
    )


def _solver_leaf_pixel_size(node: 'WidgetNode', rm: Any) -> Tuple[int, int]:
    """Pixel size for a non-implicit-container widget (for layout union)."""
    render_mode = rm.get_widget_render_mode(node)
    if render_mode == 'fixed':
        sn = node.get_sprite_name()
        if sn:
            nw, nh = rm.get_sprite_natural_size(sn)
            if nw > 0:
                sc = node.scale
                return max(1, int(nw * sc)), max(1, int(nh * sc))
    w, h = node.size
    return max(1, w), max(1, h)


def _clear_editor_layout_sizes(node: WidgetNode) -> None:
    node._editor_layout_size = None
    node._editor_resolved_size = None
    for ch in node.children:
        _clear_editor_layout_sizes(ch)


def _solve_layout_node(node: WidgetNode, outer_pw: float, outer_ph: float, rm: Any) -> Tuple[int, int]:
    """
    Recursively compute layout sizes. Sets _editor_layout_size on implicit containers.
    Returns (w, h) pixel size of this widget for parent's union calculation.
    """
    if node.has_explicit_size_property():
        w, h = resolve_size_for_parent(node, outer_pw, outer_ph)
        node._editor_layout_size = None
        node._editor_resolved_size = (w, h)
        # Descendants still need _editor_resolved_size; previously we returned here and never recursed.
        if node.widget_type in CONTAINER_TYPES:
            Lw, Lh = float(w), float(h)
            for child in node.children:
                _solve_layout_node(child, Lw, Lh, rm)
        return w, h

    if node.widget_type in CONTAINER_TYPES:
        margin = 8.0
        # For implicit containers (no declared size), compute the bounding box of
        # children as if this container has size (0, 0).  Using the parent's size
        # as the starting reference (as the old iterative approach did) causes
        # orientation=center children to produce a diverging/wrong large bounding
        # box, because their anchor (Lw/2, Lh/2) shifts with every iteration.
        # With size=(0,0): center anchor = (0,0) = same as upper_left, so the
        # children's positions are just their raw offsets — which matches the
        # in-game behaviour for zero-sized / implicit containers.
        max_r = 0.0
        max_b = 0.0
        for child in node.children:
            cw, ch = _solve_layout_node(child, outer_pw, outer_ph, rm)
            tlx, tly = compute_widget_topleft(
                0.0, 0.0, float(cw), float(ch),
                child.orientation, effective_origo(child),
                child.position[0], child.position[1],
            )
            max_r = max(max_r, tlx + float(cw))
            max_b = max(max_b, tly + float(ch))
        iw = max(10, int(round(max_r + margin)))
        ih = max(10, int(round(max_b + margin)))
        node._editor_layout_size = (iw, ih)
        node._editor_resolved_size = (iw, ih)
        return iw, ih

    node._editor_layout_size = None
    lw, lh = _solver_leaf_pixel_size(node, rm)
    node._editor_resolved_size = (lw, lh)
    return lw, lh


def resolve_editor_layout_sizes(roots: List[WidgetNode], canvas_w: int, canvas_h: int, rm: Any) -> None:
    """
    Before building QGraphicsItems, compute implicit container bounds from children.
    Does not modify properties dict — only fills _editor_layout_size.
    """
    for root in roots:
        _clear_editor_layout_sizes(root)
    cw, ch = max(1, int(canvas_w)), max(1, int(canvas_h))
    for root in roots:
        _solve_layout_node(root, float(cw), float(ch), rm)


def create_widget(widget_type: str, name: str = '', **kwargs) -> WidgetNode:
    """Create a new widget node with default properties."""
    node = WidgetNode(widget_type=widget_type)
    w, h = DEFAULT_SIZE.get(widget_type, (100, 30))
    node.properties = {
        'name': name or f'new_{widget_type}',
        'position': {'x': 0, 'y': 0},
    }
    # All newly-created widgets get an explicit size so they're immediately visible on canvas.
    # For containerWindowType and scrollAreaType this is required because without size AND
    # without children they would have zero display dimensions and be invisible/unselectable.
    node.properties['size'] = {'width': w, 'height': h}
    node.properties.update(kwargs)
    return node
