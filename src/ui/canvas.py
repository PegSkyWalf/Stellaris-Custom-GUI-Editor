"""
可视化编辑画布 — 支持多选、橡皮筋选框、撤销/重做集成。
"""
from __future__ import annotations
from typing import Dict, List, Optional, TYPE_CHECKING, Set, Tuple

from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem,
    QMenu, QInputDialog, QApplication,
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QRect
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QKeyEvent, QWheelEvent,
    QMouseEvent, QKeySequence, QPalette,
)

from ..core.gui_model import (
    WidgetNode, GUIDocument, create_widget,
    WIDGET_TYPES, WIDGET_LABELS,
    compute_widget_topleft, reverse_compute_position,
    orientation_to_anchor, origo_to_offset,
    resolve_editor_layout_sizes, effective_origo,
    make_names_unique,
)
from ..core.resource_manager import ResourceManager
from ..core.settings import AppSettings
from ..core.snap_engine import SnapEngine
from .snap_guide_overlay import SnapGuideOverlay
from .widget_items import GUIWidgetItem

if TYPE_CHECKING:
    from ..core.undo import UndoStack

# Stellaris only binds scrollbars to these widget types; ignore stray parsed keys elsewhere.
_EDITOR_SCROLLBAR_PARENT_WIDGET_TYPES = frozenset({
    'listboxtype', 'smoothlistboxtype', 'instanttextboxtype', 'textboxtype',
    'containerwindowtype', 'scrollareatype', 'expandedwindow',
})


class GUIScene(QGraphicsScene):
    """
    Scene with full undo/redo, multi-select, and layer operations.
    """
    selection_changed_signal = Signal(object)           # selected WidgetNode or list
    widget_moved_signal = Signal(object)
    widget_property_changed_signal = Signal(object)
    document_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: Optional[GUIDocument] = None
        self._node_to_item: Dict[int, GUIWidgetItem] = {}
        self.grid_size = 8
        self.snap_to_grid = True
        self._preview_mode = False
        self.undo_stack: Optional['UndoStack'] = None
        # Re-entrancy guard
        self._refreshing: bool = False
        # Event context: text/room overrides applied when user picks a linked event
        self._event_context = None   # EventInfo or None
        # node id → override text (for desc→alien_message, option→button)
        self._text_overrides: Dict[int, str] = {}
        # node id → room pixmap (for portrait container)
        self._room_pixmap_cache = {}
        # Top-level items hidden during event context (option button templates rendered
        # at their native position when no event context is active; hidden + re-built
        # inside option_list when an event context is set)
        self._hidden_template_items: list = []

        # 智能吸附引擎和参考线叠层
        self.snap_engine = SnapEngine()
        self.snap_overlay = SnapGuideOverlay()
        self.addItem(self.snap_overlay)

        self.selectionChanged.connect(self._on_selection_changed)

    def load_document(self, doc: GUIDocument):
        # Discard event-overlay item list BEFORE self.clear() so we never hold
        # Python wrappers that point to C++ objects Qt is about to delete.
        self._event_overlay_items = []
        self._hidden_template_items = []
        self._event_context = None
        self.clear()
        self._node_to_item.clear()
        # Re-add snap overlay after clear()
        self.snap_overlay = SnapGuideOverlay()
        self.addItem(self.snap_overlay)
        self.doc = doc
        settings = AppSettings.instance()
        cw, ch = settings.canvas_size
        # Use a very large scene rect so items can exist anywhere (unbounded canvas)
        # The actual canvas frame is drawn as a reference rect in drawBackground.
        self.setSceneRect(-4000, -4000, cw + 8000, ch + 8000)

        # Count total widgets to choose index method
        total_widgets = sum(1 for _ in doc.all_widgets())
        # For large scenes NoIndex is faster for inserts; BspTree for static scenes
        if total_widgets > 500:
            self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        else:
            self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)

        rm = ResourceManager.instance()
        resolve_editor_layout_sizes(doc.roots, cw, ch, rm)

        # Batch-build items; process app events periodically to keep UI responsive
        self.blockSignals(True)
        try:
            for i, root in enumerate(doc.roots):
                self._build_item_tree(root, parent_item=None, parent_w=cw, parent_h=ch)
                if i % 20 == 0:
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
        finally:
            self.blockSignals(False)

        # Refine implicit containers from actual Qt child geometry (margins)
        self._refresh_all_auto_sizes()
        self.sync_editor_scrollbar_visibility()

    def sync_editor_scrollbar_visibility(self):
        """Apply 视图 → 显示编辑器滑条 设置 to existing ScrollbarOverlayItem instances."""
        from .widget_items import ScrollbarOverlayItem
        vis = AppSettings.instance().show_editor_scrollbars
        for it in self.items():
            if isinstance(it, ScrollbarOverlayItem):
                it.setVisible(vis)

    # ------------------------------------------------------------------
    # Event context (links event desc/room/options to GUI widgets)
    # ------------------------------------------------------------------

    def _find_event_portrait_anchor(self) -> Tuple[Optional[GUIWidgetItem], Optional[GUIWidgetItem]]:
        """
        Return (portrait_container_item, portrait_mask_icon_item) for event room art.

        Stellaris / mod convention (see spth_event_ui.gui): the room image is tied to
        iconType name "portrait" inside containerWindowType name "portrait".

        Many mods include HIDDEN dummy portrait containers (size=0×0, placed far off-screen)
        required by the Clausewitz engine as stubs. We must skip those and find only the
        real, visible portrait container.  Filtering rules (strict pass):
          1. portrait_c rect must be ≥ 5×5 px (size=0 → max(1,0)=1 after layout; skip dummies)
          2. portrait_c center-y must be within [−1500, 7000] scene pixels (skip far off-screen)
          3. Among remaining candidates, prefer the one with the LARGEST area (real portrait
             is usually much bigger than any stub that slipped through the size filter).
        """
        strict: List[Tuple[GUIWidgetItem, GUIWidgetItem, float, float]] = []
        for item in self.items():
            if not isinstance(item, GUIWidgetItem):
                continue
            node = item.node
            if node.widget_type.lower() != 'icontype':
                continue
            if (node.name or '').lower() != 'portrait':
                continue
            p = item.parentItem()
            portrait_c: Optional[GUIWidgetItem] = None
            while p:
                if isinstance(p, GUIWidgetItem):
                    if p.node.widget_type.lower() == 'containerwindowtype':
                        if (p.node.name or '').lower() == 'portrait':
                            portrait_c = p
                            break
                p = p.parentItem()
            if portrait_c is None:
                continue
            r = portrait_c.rect()
            # Skip explicitly-hidden dummy containers (size ≤ 4 in either dimension)
            if r.width() < 5 or r.height() < 5:
                continue
            cy = portrait_c.scenePos().y() + r.center().y()
            # Skip containers that are clearly off-screen
            if not (-1500.0 < cy < 7000.0):
                continue
            area = r.width() * r.height()
            strict.append((portrait_c, item, cy, area))

        if strict:
            # Prefer the largest portrait container (real portrait >> any stub)
            strict.sort(key=lambda t: -t[3])
            c, ic, _, _ = strict[0]
            return c, ic

        loose: List[Tuple[GUIWidgetItem, GUIWidgetItem, float, float]] = []
        for item in self.items():
            if not isinstance(item, GUIWidgetItem):
                continue
            if item.node.widget_type.lower() != 'icontype':
                continue
            if (item.node.name or '').lower() != 'portrait':
                continue
            cy = item.scenePos().y() + item.rect().center().y()
            if not (-1500.0 < cy < 6500.0):
                continue
            p = item.parentItem()
            anc: Optional[GUIWidgetItem] = None
            while p:
                if isinstance(p, GUIWidgetItem) and p.node.widget_type.lower() == 'containerwindowtype':
                    anc = p
                    break
                p = p.parentItem()
            c = anc if anc is not None else item
            area = c.rect().width() * c.rect().height() if isinstance(c, GUIWidgetItem) else 0.0
            loose.append((c, item, cy, area))
        if loose:
            # Prefer the largest container; fall back to topmost on tie
            loose.sort(key=lambda t: (-t[3], t[2]))
            return loose[0][0], loose[0][1]
        return None, None

    def _item_is_under_named_container(self, item: 'GUIWidgetItem', container_name: str) -> bool:
        """True if an ancestor GUIWidgetItem is containerWindowType with this name (case-insensitive)."""
        target = (container_name or '').strip().lower()
        if not target:
            return False
        p = item.parentItem()
        while p:
            if isinstance(p, GUIWidgetItem):
                n = p.node
                if n.widget_type.lower() == 'containerwindowtype':
                    if (n.name or '').strip().lower() == target:
                        return True
            p = p.parentItem()
        return False

    def set_event_context(self, event_info):
        """
        Apply an EventInfo context to the scene.

        Linking rules (matching Stellaris hard-coded event GUI conventions):
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │ alien_message (instantTextBoxType) ← event.desc (localized)                │
        │                                                                              │
        │ containerWindowType name="EVENT_DIPLO"                                      │
        │   └─ widget name="action_title" ← event.title (localized)                  │
        │                                                                              │
        │ portrait container (containerWindowType name="portrait")                    │
        │   └─ portrait iconType (iconType name="portrait") ← room image is rendered  │
        │      at this item's scene position (not filling the whole container)         │
        │                                                                              │
        │ option buttons:                                                              │
        │   • any widget named "option_button" (in option GUI) gets option text       │
        │   • any widget whose text/buttonText == "OPTION_TEXT" gets option text      │
        │   • custom_gui_option name → direct button name match (legacy)              │
        │   • option.custom_gui → button name match per-option                        │
        │   • listboxType "option_list" → multi-option text overlay                  │
        └──────────────────────────────────────────────────────────────────────────────┘

        Pass None to clear all overrides.
        """
        self._event_context = event_info
        self._text_overrides = {}

        if event_info is None:
            # Remove option-GUI overlay items (guard against stale C++ objects)
            for overlay in getattr(self, '_event_overlay_items', []):
                try:
                    overlay.setParentItem(None)
                    if overlay.scene() is self:
                        self.removeItem(overlay)
                except RuntimeError:
                    pass
            self._event_overlay_items = []
            # Restore any top-level template items that were hidden
            for item in getattr(self, '_hidden_template_items', []):
                try:
                    item.setVisible(True)
                except RuntimeError:
                    pass
            self._hidden_template_items = []
            for item in self.items():
                if isinstance(item, GUIWidgetItem):
                    try:
                        item.set_event_overrides(None, None)
                    except RuntimeError:
                        pass
            return

        rm = ResourceManager.instance()
        gui_hint = (getattr(self.doc, 'file_path', None) or '') if self.doc else ''

        # Pre-resolve room pixmap once
        room_pm = None
        room_scope_text: str = ''
        if event_info.room:
            if event_info.is_scope_room:
                room_scope_text = f'[{event_info.room}]'
            else:
                room_pm, _ = rm.resolve_room_pixmap(
                    event_info.room, gui_file_hint=gui_hint)

        # Pre-resolve option texts
        # Build list: [(opt_loc_text, opt)] sorted by option order, excluding default-hidden
        opt_texts = []
        for opt in event_info.options:
            if opt.name:
                opt_texts.append(rm.get_loc(opt.name))

        # custom_gui_option: find the first option linked via custom_gui_option name
        cgo_text = ''
        if event_info.custom_gui_option and event_info.options:
            for opt in event_info.options:
                if (opt.custom_gui == event_info.custom_gui_option
                        or not getattr(opt, 'hidden', False)):
                    if opt.name:
                        cgo_text = rm.get_loc(opt.name)
                        break
            if not cgo_text and event_info.options:
                if event_info.options[0].name:
                    cgo_text = rm.get_loc(event_info.options[0].name)

        # ── Pass 1: locate key anchors in the scene ──────────────────────────
        portrait_container_item, portrait_icon_item = self._find_event_portrait_anchor()
        option_list_item: Optional[GUIWidgetItem] = None

        for item in self.items():
            if not isinstance(item, GUIWidgetItem):
                continue
            node = item.node
            wt = node.widget_type.lower()
            nm = (node.name or '').lower()
            if wt == 'listboxtype' and nm == 'option_list':
                option_list_item = item

        # ── Room image ───────────────────────────────────────────────────────
        # Stellaris convention: room draws in the mask slot — iconType name
        # "portrait" inside containerWindowType name "portrait" only. Using any
        # other iconType also named "portrait" (e.g. off-screen portrait_background)
        # breaks display when scene iteration order varies.
        if event_info.room:
            target_item = portrait_icon_item or portrait_container_item
            if target_item:
                icon_scale = 1.0
                if portrait_icon_item:
                    icon_scale = portrait_icon_item.node.scale or 1.0
                if room_scope_text:
                    target_item.set_event_overrides(room_scope_text, None, room_scale=icon_scale)
                else:
                    target_item.set_event_overrides(None, room_pm, room_scale=icon_scale)

        # ── Pass 2: apply text overrides to existing scene items ─────────────
        for item in self.items():
            if not isinstance(item, GUIWidgetItem):
                continue
            node = item.node
            wt = node.widget_type.lower()
            nm = (node.name or '').lower()

            # desc → alien_message
            if nm == 'alien_message' and event_info.desc:
                desc_text = rm.get_loc(event_info.desc)
                item.set_event_overrides(desc_text, None)
                self._text_overrides[id(node)] = desc_text

            # title → EVENT_DIPLO / action_title (vanilla diplomatic event header)
            if nm == 'action_title' and self._item_is_under_named_container(item, 'EVENT_DIPLO'):
                if event_info.title:
                    title_text = rm.get_loc(event_info.title)
                    item.set_event_overrides(title_text, None)
                    self._text_overrides[id(node)] = title_text

            # option_button widget (in option-GUI, may be in this scene)
            if nm == 'option_button':
                chosen = cgo_text or (opt_texts[0] if opt_texts else '')
                if chosen:
                    item.set_event_overrides(chosen, None)
                    self._text_overrides[id(node)] = chosen

            # OPTION_TEXT placeholder (any caption property)
            btn_key = node.get_text_localization_key()
            btn_text_val = btn_key or ''
            if btn_text_val.strip().upper() == 'OPTION_TEXT':
                chosen = cgo_text or (opt_texts[0] if opt_texts else '')
                if chosen:
                    item.set_event_overrides(chosen, None)
                    self._text_overrides[id(node)] = chosen

            # custom_gui_option direct name match
            if event_info.custom_gui_option and nm == event_info.custom_gui_option.lower():
                if cgo_text:
                    item.set_event_overrides(cgo_text, None)
                    self._text_overrides[id(node)] = cgo_text

            # Per-option custom_gui button
            for opt in event_info.options:
                if opt.custom_gui and nm == opt.custom_gui.lower() and opt.name:
                    t = rm.get_loc(opt.name)
                    item.set_event_overrides(t, None)
                    self._text_overrides[id(node)] = t

        # ── Pass 3: render option GUIs inside option_list ────────────────────
        # Remove any previously-added overlay items before re-building.
        # Guard with try-except: if a prior scene.clear() already deleted the C++ objects
        # the Python wrappers will raise RuntimeError — just discard them silently.
        for overlay in getattr(self, '_event_overlay_items', []):
            try:
                overlay.setParentItem(None)  # detach from parent first
                if overlay.scene() is self:
                    self.removeItem(overlay)
            except RuntimeError:
                pass  # C++ object already deleted; nothing to do
        self._event_overlay_items: list = []
        # Restore previously hidden template items before hiding new ones
        for item in getattr(self, '_hidden_template_items', []):
            try:
                item.setVisible(True)
            except RuntimeError:
                pass
        self._hidden_template_items = []

        has_explicit_gui = (event_info.custom_gui_option
                            or any(getattr(o, 'custom_gui', '') for o in event_info.options))

        # Fallback: when no custom_gui_option / per-option custom_gui is set,
        # detect option button template containers from the document roots.
        # These are top-level containerWindowType widgets (other than the main event
        # GUI) that contain a buttonType named "option_button" or a text/buttonText
        # placeholder of "OPTION_TEXT".  Hide them at their native position and
        # re-render them inside option_list instead.
        fallback_reg: list = []
        fallback_last: list = []
        if option_list_item and not has_explicit_gui and event_info.options:
            fallback_reg, fallback_last = self._find_option_template_names(event_info)
            if fallback_reg or fallback_last:
                template_lower = {n.lower() for n in (fallback_reg + fallback_last)}
                for item in self.items():
                    if not isinstance(item, GUIWidgetItem):
                        continue
                    if item.parentItem() is not None:
                        continue  # only top-level items
                    node = item.node
                    if (node.widget_type.lower() == 'containerwindowtype'
                            and (node.name or '').lower() in template_lower):
                        item.setVisible(False)
                        self._hidden_template_items.append(item)

        if option_list_item and (has_explicit_gui or fallback_reg or fallback_last):
            self._build_option_guis_in_list(
                option_list_item, event_info, rm, opt_texts,
                fallback_reg=fallback_reg, fallback_last=fallback_last,
            )

        self.update()

    def _build_option_guis_in_list(self, option_list_item: 'GUIWidgetItem',
                                    event_info, rm, opt_texts: list,
                                    *, fallback_reg: list = None,
                                    fallback_last: list = None):
        """Build scene items for each option GUI inside the option_list listbox.

        fallback_reg / fallback_last: template names detected from the document when
        the event has neither custom_gui_option nor per-option custom_gui.
        fallback_last is used for the last option (e.g. ae_dialogue_button_last);
        fallback_reg is used for all other options.
        """
        from ..core.gui_model import resolve_editor_layout_sizes
        from ..core.settings import AppSettings

        fallback_reg = fallback_reg or []
        fallback_last = fallback_last or []

        # Collect option GUI names in order
        option_gui_names: list = []
        if event_info.custom_gui_option:
            option_gui_names.append((event_info.custom_gui_option,
                                     opt_texts[0] if opt_texts else ''))
        for i, opt in enumerate(event_info.options):
            gui_n = getattr(opt, 'custom_gui', '')
            if gui_n:
                opt_loc = rm.get_loc(opt.name) if opt.name else ''
                option_gui_names.append((gui_n, opt_loc))

        # Fallback: no explicit custom_gui_option / per-option custom_gui — use
        # template containers detected from the document (e.g. ae_dialogue_button /
        # ae_dialogue_button_last when options have no custom_gui attribute).
        if not option_gui_names and (fallback_reg or fallback_last):
            n_opts = len(event_info.options)
            for i, opt in enumerate(event_info.options):
                opt_loc = rm.get_loc(opt.name) if opt.name else ''
                if fallback_last and i == n_opts - 1:
                    option_gui_names.append((fallback_last[0], opt_loc))
                elif fallback_reg:
                    option_gui_names.append((fallback_reg[0], opt_loc))

        if not option_gui_names:
            return

        list_rect = option_list_item.rect()
        list_w = max(1, int(list_rect.width()))
        cw, ch = AppSettings.instance().canvas_size

        y_offset = 0
        for idx, (gui_name, loc_text) in enumerate(option_gui_names):
            root_node = rm.get_option_gui_root(gui_name)
            if root_node is None:
                continue
            resolve_editor_layout_sizes([root_node], cw, ch, rm)
            rw, rh = root_node.size
            slot_h = max(rh, 30)
            try:
                self._build_option_gui_item(root_node, option_list_item,
                                            list_w, slot_h, y_offset, loc_text)
            except Exception:
                pass
            y_offset += slot_h

    def _build_option_gui_item(self, root_node, parent_item: 'GUIWidgetItem',
                                avail_w: int, avail_h: int, y_offset: int,
                                opt_loc_text: str):
        """Build a mini sub-tree for one option GUI inside the option_list item.
        Option GUIs are rendered at their native size (no scaling).
        Scrollbar handles overflow."""
        item = GUIWidgetItem(root_node, parent_item=parent_item)
        item.setPos(0, y_offset)
        item.set_preview_mode(self._preview_mode)
        if opt_loc_text:
            self._apply_option_text_to_subtree(item, opt_loc_text)
        self._event_overlay_items.append(item)
        for child in root_node.children:
            self._build_option_gui_child(child, item, opt_loc_text)

    def _build_option_gui_child(self, node, parent_item: 'GUIWidgetItem',
                                 opt_loc_text: str):
        """Recursive helper for building option GUI child items."""
        from ..core.gui_model import compute_widget_topleft, effective_origo
        from ..core.resource_manager import ResourceManager
        rm = ResourceManager.instance()
        disp_w, disp_h = node.size
        if disp_w <= 1:
            disp_w, disp_h = 120, 30
        px, py = node.position
        pw, ph = (parent_item.node.size[0] or 200), (parent_item.node.size[1] or 150)
        tl_x, tl_y = compute_widget_topleft(pw, ph, disp_w, disp_h,
                                             node.orientation, effective_origo(node), px, py)
        child_item = GUIWidgetItem(node, parent_item=parent_item)
        child_item.setPos(tl_x, tl_y)
        child_item.set_preview_mode(self._preview_mode)
        if opt_loc_text:
            self._apply_option_text_to_subtree(child_item, opt_loc_text)
        self._event_overlay_items.append(child_item)
        for grandchild in node.children:
            self._build_option_gui_child(grandchild, child_item, opt_loc_text)

    def _apply_option_text_to_subtree(self, item: 'GUIWidgetItem', text: str):
        """Set event text override on any button in a subtree with OPTION_TEXT placeholder."""
        node = item.node
        btn_val = node.get_text_localization_key() or ''
        if (btn_val.strip().upper() == 'OPTION_TEXT'
                or (node.name or '').lower() == 'option_button'):
            item.set_event_overrides(text, None)

        self.update()

    @staticmethod
    def _node_contains_option_button(node) -> bool:
        """Return True if node or any descendant is an option_button widget or
        has an OPTION_TEXT text/buttonText placeholder."""
        if (node.name or '').lower() == 'option_button':
            return True
        key = node.get_text_localization_key() or ''
        if key.strip().upper() == 'OPTION_TEXT':
            return True
        for child in node.children:
            if GUIScene._node_contains_option_button(child):
                return True
        return False

    def _find_option_template_names(self, event_info) -> tuple:
        """Scan the current document's top-level nodes for containerWindowType widgets
        that look like option button templates (contain option_button / OPTION_TEXT).
        Returns (regular_names, last_names) — last_names are for the final option.
        Only looks at siblings of the main event GUI, not the event GUI itself."""
        if not self.doc:
            return [], []
        main_gui_lower = (event_info.custom_gui or '').lower()
        regular: list = []
        last: list = []
        for root in self.doc.roots:
            if root.widget_type.lower() != 'containerwindowtype':
                continue
            name = root.name or ''
            if name.lower() == main_gui_lower:
                continue  # skip the main event GUI itself
            if self._node_contains_option_button(root):
                if 'last' in name.lower():
                    last.append(name)
                else:
                    regular.append(name)
        return regular, last

    def _layout_dims_for_parent(self, parent_node: Optional[WidgetNode]) -> Tuple[float, float]:
        """Convenience: canvas size + _parent_layout_dimensions."""
        cw, ch = AppSettings.instance().canvas_size
        return self._parent_layout_dimensions(parent_node, float(cw), float(ch))

    def _parent_layout_dimensions(self, parent_node: Optional[WidgetNode],
                                  canvas_w: float, canvas_h: float) -> Tuple[float, float]:
        """Anchor box size for positioning children (matches game parent client area)."""
        if parent_node is None:
            return canvas_w, canvas_h
        # Implicit containers (no declared size) have _editor_layout_size computed
        # from their children. Their children's positions must be computed with (0, 0)
        # as the anchor reference — consistent with _solve_layout_node which also
        # uses (0, 0). Returning the computed layout size here would incorrectly
        # shift orientation=center children by half the container's computed dimensions.
        if getattr(parent_node, '_editor_layout_size', None) is not None:
            return 0.0, 0.0
        rm = ResourceManager.instance()
        w, h = self._get_display_size(parent_node, rm)
        return float(w), float(h)

    def _build_item_tree(self, node: WidgetNode, parent_item: Optional[GUIWidgetItem],
                         parent_w: float, parent_h: float):
        rm = ResourceManager.instance()
        disp_w, disp_h = self._get_display_size(node, rm)
        pos_x, pos_y = node.position
        tl_x, tl_y = compute_widget_topleft(
            parent_w, parent_h, disp_w, disp_h,
            node.orientation, effective_origo(node), pos_x, pos_y
        )
        item = GUIWidgetItem(node, parent_item=parent_item)
        item.setPos(tl_x, tl_y)
        if parent_item is None:
            self.addItem(item)
        self._node_to_item[id(node)] = item
        item.set_preview_mode(self._preview_mode)
        ccw, cch = AppSettings.instance().canvas_size
        for child in node.children:
            ch_pw, ch_ph = self._parent_layout_dimensions(node, float(ccw), float(cch))
            self._build_item_tree(child, item, ch_pw, ch_ph)

        # Attach scrollbar overlay if the node references one
        self._attach_scrollbar_overlay(node, item, rm)

    def _attach_scrollbar_overlay(self, node: WidgetNode, item: 'GUIWidgetItem',
                                    rm: ResourceManager):
        """Only when script declares a scrollbar on a supported widget type."""
        from .widget_items import ScrollbarOverlayItem

        wt = node.widget_type.lower()
        if wt not in _EDITOR_SCROLLBAR_PARENT_WIDGET_TYPES:
            return

        def _pick_ref() -> Tuple[str, bool]:
            for key, v in node.properties.items():
                lk = str(key).lower().replace(' ', '')
                if lk not in ('scrollbartype', 'verticalscrollbar', 'horizontalscrollbar'):
                    continue
                if v is None or isinstance(v, (dict, list)):
                    continue
                s = str(v).strip().strip('"').strip()
                if not s:
                    continue
                low = s.lower()
                if low in ('no', 'none', 'false', '0', 'null'):
                    continue
                is_h = lk == 'horizontalscrollbar'
                return s, is_h
            return '', False

        sb_ref_str, is_horiz = _pick_ref()
        if not sb_ref_str:
            return

        sb_node = rm.get_scrollbar_node(sb_ref_str)
        if sb_node is None:
            return
        try:
            ov = ScrollbarOverlayItem(sb_node, item, is_horizontal=is_horiz)
            ov.setVisible(AppSettings.instance().show_editor_scrollbars)
        except Exception:
            pass

    def _refresh_all_auto_sizes(self):
        """Bottom-up pass: let zero-size containers expand to fit children."""
        # Process deepest items first (reverse BFS)
        all_items = [i for i in self.items() if isinstance(i, GUIWidgetItem)]
        # Sort by depth (deepest first) so parents resize after children
        def depth(item):
            d = 0
            p = item.parentItem()
            while p:
                d += 1
                p = p.parentItem()
            return d
        all_items.sort(key=depth, reverse=True)
        for item in all_items:
            item.refresh_auto_size()

    def _get_display_size(self, node: WidgetNode, rm: ResourceManager) -> tuple:
        # spriteType (fixed): natural size takes precedence over declared size=
        # (Stellaris does not scale spriteType images to fit the declared size).
        render_mode = rm.get_widget_render_mode(node)
        if render_mode == 'fixed':
            sprite_name = node.get_sprite_name()
            if sprite_name:
                nw, nh = rm.get_sprite_natural_size(sprite_name)
                if nw > 0:
                    scale = node.scale
                    w, h = max(1, int(nw * scale)), max(1, int(nh * scale))
                    return node.editor_expand_fixed_size_for_caption(w, h)
        # nine_patch / no sprite / sprite not found: use declared or layout-computed size
        ers = getattr(node, '_editor_resolved_size', None)
        if ers:
            return max(1, int(ers[0])), max(1, int(ers[1]))
        els = getattr(node, '_editor_layout_size', None)
        if els:
            return max(1, int(els[0])), max(1, int(els[1]))
        w, h = node.size
        return max(1, w), max(1, h)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def get_item_for_node(self, node: WidgetNode) -> Optional[GUIWidgetItem]:
        return self._node_to_item.get(id(node))

    def get_selected_nodes(self) -> List[WidgetNode]:
        return [item.node for item in self.selectedItems()
                if isinstance(item, GUIWidgetItem)]

    def get_selected_node(self) -> Optional[WidgetNode]:
        nodes = self.get_selected_nodes()
        return nodes[0] if nodes else None

    def get_selected_item(self) -> Optional[GUIWidgetItem]:
        for item in self.selectedItems():
            if isinstance(item, GUIWidgetItem):
                return item
        return None

    def select_node(self, node: Optional[WidgetNode]):
        self.clearSelection()
        if node:
            item = self.get_item_for_node(node)
            if item:
                item.setSelected(True)

    def _on_selection_changed(self):
        for item in self.items():
            if isinstance(item, GUIWidgetItem):
                item.set_handles_visible(item.isSelected())
        nodes = self.get_selected_nodes()
        if len(nodes) == 1:
            self.selection_changed_signal.emit(nodes[0])
        elif len(nodes) > 1:
            self.selection_changed_signal.emit(nodes)
        else:
            self.selection_changed_signal.emit(None)

    # ------------------------------------------------------------------
    # Widget operations
    # ------------------------------------------------------------------

    def on_widget_moved(self, item: GUIWidgetItem):
        # Do not emit during a refresh_item call — would cause infinite loop
        if self._refreshing:
            return
        self.widget_moved_signal.emit(item.node)
        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def on_widget_property_changed(self, item: GUIWidgetItem):
        if self._refreshing:
            return
        self.widget_property_changed_signal.emit(item.node)
        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def add_widget(self, widget_type: str, pos: QPointF,
                   parent_node: Optional[WidgetNode] = None, name: str = '') -> WidgetNode:
        node = create_widget(widget_type, name)
        settings = AppSettings.instance()
        pw, ph = self._layout_dims_for_parent(parent_node)

        rm = ResourceManager.instance()
        dw, dh = self._get_display_size(node, rm)

        # Convert scene position to Stellaris position
        x, y = int(pos.x()), int(pos.y())
        if parent_node:
            parent_item = self.get_item_for_node(parent_node)
            if parent_item:
                parent_scene_pos = parent_item.mapToScene(QPointF(0, 0))
                x -= int(parent_scene_pos.x())
                y -= int(parent_scene_pos.y())

        stellaris_x, stellaris_y = reverse_compute_position(
            x, y, pw, ph, dw, dh, node.orientation, effective_origo(node)
        )
        if self.snap_to_grid and self.grid_size > 1:
            stellaris_x = round(stellaris_x / self.grid_size) * self.grid_size
            stellaris_y = round(stellaris_y / self.grid_size) * self.grid_size
        node.position = (stellaris_x, stellaris_y)

        # Add to model
        if parent_node:
            parent_node.add_child(node)
            parent_item = self.get_item_for_node(parent_node)
        else:
            if self.doc:
                self.doc.roots.append(node)
            parent_item = None

        # Add to undo stack
        if self.undo_stack and self.doc:
            from ..core.undo import AddWidgetCommand
            cmd = AddWidgetCommand(self.doc, node,
                                   parent_node,
                                   len(parent_node.children) - 1 if parent_node else len(self.doc.roots) - 1)
            self.undo_stack.push(cmd, execute=False)

        # Build item in scene
        tl_x, tl_y = compute_widget_topleft(pw, ph, dw, dh, node.orientation, effective_origo(node),
                                            stellaris_x, stellaris_y)
        new_item = GUIWidgetItem(node, parent_item=parent_item)
        new_item.setPos(tl_x, tl_y)
        if parent_item is None:
            self.addItem(new_item)
        self._node_to_item[id(node)] = new_item
        new_item.set_preview_mode(self._preview_mode)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()
        self._refresh_all_auto_sizes()
        return node

    def delete_selected(self):
        items = [i for i in self.selectedItems() if isinstance(i, GUIWidgetItem)]
        if not items:
            return

        # Skip protected (vanilla mandatory) controls
        protected = [i for i in items if getattr(i.node, '_protected', False)]
        if protected:
            from PySide6.QtWidgets import QMessageBox
            names = ', '.join(i.node.name for i in protected)
            QMessageBox.warning(
                None, '无法删除',
                f'以下控件是原版必要控件，不能删除：\n{names}',
            )
            items = [i for i in items if not getattr(i.node, '_protected', False)]
            if not items:
                return

        from ..core.undo import DeleteWidgetCommand, CompoundCommand
        cmds = []
        for item in items:
            node = item.node
            if self.undo_stack and self.doc:
                cmd = DeleteWidgetCommand(self.doc, node)
                cmds.append(cmd)
            else:
                if node.parent:
                    node.parent.remove_child(node)
                elif self.doc and node in self.doc.roots:
                    self.doc.roots.remove(node)
            self._remove_item_tree(item)

        if cmds and self.undo_stack:
            compound = CompoundCommand(cmds, f'删除 {len(cmds)} 个控件')
            for cmd in cmds:
                cmd.execute()
            self.undo_stack.push(compound, execute=False)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def _remove_item_tree(self, item: GUIWidgetItem):
        for child in list(item.childItems()):
            if isinstance(child, GUIWidgetItem):
                self._remove_item_tree(child)
        self._node_to_item.pop(id(item.node), None)
        self.removeItem(item)

    def duplicate_selected(self) -> Optional[WidgetNode]:
        item = self.get_selected_item()
        if not item:
            return None
        node = item.node
        new_node = node.clone()
        # 自动为克隆节点生成唯一名称
        if self.doc:
            existing = {w.name for w in self.doc.all_widgets() if w.name}
            make_names_unique(new_node, existing)
        x, y = new_node.position
        new_node.position = (x + 16, y + 16)

        parent_item = None
        if node.parent:
            node.parent.add_child(new_node)
            parent_item = self.get_item_for_node(node.parent)
            pw, ph = self._layout_dims_for_parent(node.parent)
        elif self.doc:
            self.doc.roots.append(new_node)
            settings = AppSettings.instance()
            pw, ph = settings.canvas_size
        else:
            return None

        if self.undo_stack and self.doc:
            from ..core.undo import DuplicateWidgetCommand
            cmd = DuplicateWidgetCommand(self.doc, node)
            cmd.clone = new_node
            self.undo_stack.push(cmd, execute=False)

        rm = ResourceManager.instance()
        dw, dh = self._get_display_size(new_node, rm)
        px, py = new_node.position
        tl_x, tl_y = compute_widget_topleft(pw, ph, dw, dh,
                                             new_node.orientation, effective_origo(new_node), px, py)
        new_item = GUIWidgetItem(new_node, parent_item=parent_item)
        new_item.setPos(tl_x, tl_y)
        if parent_item is None:
            self.addItem(new_item)
        self._node_to_item[id(new_node)] = new_item
        new_item.set_preview_mode(self._preview_mode)
        self.clearSelection()
        new_item.setSelected(True)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()
        self._refresh_all_auto_sizes()
        return new_node

    def copy_selected(self):
        """Copy selected nodes to clipboard."""
        nodes = self.get_selected_nodes()
        if nodes:
            from ..codegen.gui_writer import write_widget_to_string
            text = '\n\n'.join(write_widget_to_string(n) for n in nodes)
            QApplication.clipboard().setText(text)

    def paste_from_clipboard(self):
        """Paste from clipboard as new widgets."""
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        try:
            from ..core.gui_model import parse_gui_text
            doc = parse_gui_text(text)
            for node in doc.roots:
                x, y = node.position
                node.position = (x + 20, y + 20)
                if self.doc:
                    self.doc.roots.append(node)
                settings = AppSettings.instance()
                pw, ph = settings.canvas_size
                rm = ResourceManager.instance()
                dw, dh = self._get_display_size(node, rm)
                px, py = node.position
                tl_x, tl_y = compute_widget_topleft(pw, ph, dw, dh,
                                                     node.orientation, effective_origo(node), px, py)
                new_item = GUIWidgetItem(node, parent_item=None)
                new_item.setPos(tl_x, tl_y)
                self.addItem(new_item)
                self._node_to_item[id(node)] = new_item
                new_item.set_preview_mode(self._preview_mode)
            if self.doc:
                self.doc.modified = True
            self.document_modified.emit()
        except Exception:
            pass

    def refresh_item(self, node: WidgetNode, _force_children: bool = False):
        """
        Refresh the canvas item for a single node.
        Re-entrancy safe: uses _refreshing guard to prevent setPos → widget_moved → refresh loops.
        Only recurses into children when the display size actually changed (or forced).
        Does NOT emit document_modified (caller is responsible for that).
        """
        if self._refreshing:
            return
        item = self.get_item_for_node(node)
        if not item:
            return

        self._refreshing = True
        try:
            rm = ResourceManager.instance()
            old_w, old_h = item._display_w, item._display_h
            dw, dh = self._get_display_size(node, rm)

            parent_item = item.parentItem()
            if parent_item and isinstance(parent_item, GUIWidgetItem):
                pnode = parent_item.node
                cw, ch = AppSettings.instance().canvas_size
                pw, ph = self._parent_layout_dimensions(pnode, float(cw), float(ch))
            else:
                settings = AppSettings.instance()
                pw, ph = settings.canvas_size

            px, py = node.position
            tl_x, tl_y = compute_widget_topleft(pw, ph, dw, dh,
                                                 node.orientation, effective_origo(node), px, py)
            item.setPos(tl_x, tl_y)
            item.refresh()

            # Only refresh children when this item's size changed (they use it as parent ref)
            size_changed = (dw != old_w or dh != old_h)
            if size_changed or _force_children:
                for child in node.children:
                    # Each child refresh is independent — temporarily release guard
                    self._refreshing = False
                    self.refresh_item(child, _force_children=False)
                    self._refreshing = True
        finally:
            self._refreshing = False

    def move_widget_order(self, node: WidgetNode, delta: int):
        """Move a widget's position in its sibling list. delta=-1 (up/forward) or +1 (down/back)."""
        container = node.parent
        if container:
            lst = container.children
        elif self.doc:
            lst = self.doc.roots
        else:
            return
        if node not in lst:
            return
        idx = lst.index(node)
        new_idx = max(0, min(len(lst) - 1, idx + delta))
        if new_idx == idx:
            return
        lst.remove(node)
        lst.insert(new_idx, node)
        # Rebuild just the affected items
        self._rebuild_siblings(lst, container, node)

    def _rebuild_siblings(self, siblings: list, parent_node: Optional[WidgetNode], node: WidgetNode):
        """Rebuild z-order of sibling items by removing and re-adding them."""
        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()
        # Z-order in Qt is determined by insertion order; simplest is to rebuild
        # Just emit modified so the main window can reload if needed
        # For now, adjust z-values
        item = self.get_item_for_node(node)
        if item:
            idx = siblings.index(node)
            item.setZValue(float(idx))

    def set_preview_mode(self, enabled: bool):
        self._preview_mode = enabled
        for item in self.items():
            if isinstance(item, GUIWidgetItem):
                item.set_preview_mode(enabled)
        self.update()

    # ------------------------------------------------------------------
    # Alignment helpers
    # ------------------------------------------------------------------

    def align_selected(self, axis: str):
        """
        Align selected widgets.
        axis: 'left','right','top','bottom','hcenter','vcenter','hdistrib','vdistrib'

        Implementation note: we MUST NOT call _commit_to_node inside the loop because
        that would trigger on_widget_property_changed → node_property_changed →
        _on_node_changed → refresh_from_node → potentially property_changed →
        _on_property_edited → refresh_item, which could undo the alignment for later items.
        Instead we batch-update all positions and emit once at the end.
        """
        items = [i for i in self.selectedItems() if isinstance(i, GUIWidgetItem)]
        if len(items) < 2:
            return

        # Compute deltas entirely in scene coordinates first, then apply
        scene_rects = [(item, item.mapToScene(item.rect().topLeft()), item.rect())
                       for item in items]

        deltas: List[Tuple[GUIWidgetItem, float, float]] = []

        if axis == 'left':
            min_x = min(sr[1].x() for sr in scene_rects)
            deltas = [(item, min_x - sp.x(), 0.0) for item, sp, r in scene_rects]

        elif axis == 'right':
            max_x = max(sr[1].x() + sr[2].width() for sr in scene_rects)
            deltas = [(item, (max_x - r.width()) - sp.x(), 0.0) for item, sp, r in scene_rects]

        elif axis == 'top':
            min_y = min(sr[1].y() for sr in scene_rects)
            deltas = [(item, 0.0, min_y - sp.y()) for item, sp, r in scene_rects]

        elif axis == 'bottom':
            max_y = max(sr[1].y() + sr[2].height() for sr in scene_rects)
            deltas = [(item, 0.0, (max_y - r.height()) - sp.y()) for item, sp, r in scene_rects]

        elif axis == 'hcenter':
            cx = sum(sp.x() + r.width() / 2 for _, sp, r in scene_rects) / len(scene_rects)
            deltas = [(item, (cx - r.width() / 2) - sp.x(), 0.0) for item, sp, r in scene_rects]

        elif axis == 'vcenter':
            cy = sum(sp.y() + r.height() / 2 for _, sp, r in scene_rects) / len(scene_rects)
            deltas = [(item, 0.0, (cy - r.height() / 2) - sp.y()) for item, sp, r in scene_rects]

        elif axis == 'hdistrib':
            sorted_sr = sorted(scene_rects, key=lambda s: s[1].x())
            if len(sorted_sr) >= 3:
                leftmost = sorted_sr[0][1].x()
                rightmost = sorted_sr[-1][1].x() + sorted_sr[-1][2].width()
                total_width = sum(r.width() for _, _, r in sorted_sr)
                spacing = (rightmost - leftmost - total_width) / (len(sorted_sr) - 1)
                x = leftmost
                for item, sp, r in sorted_sr:
                    deltas.append((item, x - sp.x(), 0.0))
                    x += r.width() + spacing

        elif axis == 'vdistrib':
            sorted_sr = sorted(scene_rects, key=lambda s: s[1].y())
            if len(sorted_sr) >= 3:
                topmost = sorted_sr[0][1].y()
                bottommost = sorted_sr[-1][1].y() + sorted_sr[-1][2].height()
                total_height = sum(r.height() for _, _, r in sorted_sr)
                spacing = (bottommost - topmost - total_height) / (len(sorted_sr) - 1)
                y = topmost
                for item, sp, r in sorted_sr:
                    deltas.append((item, 0.0, y - sp.y()))
                    y += r.height() + spacing

        if not deltas:
            return

        # Build undo commands for each move
        from ..core.undo import MoveWidgetCommand, CompoundCommand
        move_cmds = []

        # Apply all position changes silently (guard avoids signal cascade)
        self._refreshing = True
        try:
            for item, dx, dy in deltas:
                if abs(dx) < 0.5 and abs(dy) < 0.5:
                    continue
                old_pos = item.node.position
                new_x = item.pos().x() + dx
                new_y = item.pos().y() + dy
                item.setPos(new_x, new_y)
                # Write back to node directly without emitting property_changed
                pw, ph = item._get_parent_size()
                new_pos = reverse_compute_position(
                    new_x, new_y, pw, ph,
                    item._display_w, item._display_h,
                    item.node.orientation, effective_origo(item.node),
                )
                item.node.position = new_pos
                if old_pos != new_pos:
                    move_cmds.append(MoveWidgetCommand(item.node, old_pos, new_pos))
        finally:
            self._refreshing = False

        # Push compound undo command
        if move_cmds and self.undo_stack:
            n = len(move_cmds)
            desc = f'对齐 {axis} ({n} 个控件)'
            compound = CompoundCommand(move_cmds, desc)
            self.undo_stack.push(compound, execute=False)

        if self.doc:
            self.doc.modified = True
        # One unified signal at the end
        self.document_modified.emit()
        self.widget_property_changed_signal.emit(items[0].node)

    # ------------------------------------------------------------------
    # Smart snap helpers (called by widget_items during drag)
    # ------------------------------------------------------------------

    def rebuild_snap_index(self, exclude_items: List[GUIWidgetItem]):
        """重建吸附索引，排除正在拖拽的物体。"""
        settings = AppSettings.instance()
        self.snap_engine.threshold = settings.smart_snap_threshold
        exclude_ids = {id(it) for it in exclude_items}
        rects = []
        for it in self.items():
            if not isinstance(it, GUIWidgetItem):
                continue
            if id(it) in exclude_ids:
                continue
            if not it.isVisible():
                continue
            sp = it.scenePos()
            r = it.rect()
            rects.append((id(it), (sp.x(), sp.y(), r.width(), r.height())))
        self.snap_engine.rebuild_index(rects)
        # 更新强调色
        accent = AppSettings.instance().accent_color
        if not accent:
            from ..core.theme_manager import AVAILABLE_THEMES, DEFAULT_THEME
            theme = settings.theme
            accent = AVAILABLE_THEMES.get(theme, AVAILABLE_THEMES[DEFAULT_THEME])[1]
        self.snap_overlay.set_accent_color(accent)

    def query_snap(self, item: GUIWidgetItem):
        """查询吸附并应用修正。返回 SnapResult。"""
        settings = AppSettings.instance()
        if not settings.smart_snap_enabled:
            return None
        sp = item.scenePos()
        r = item.rect()
        result = self.snap_engine.query_snap(
            (sp.x(), sp.y(), r.width(), r.height()),
            snap_edges=settings.snap_to_edges,
            snap_centers=settings.snap_to_centers,
            snap_spacing=settings.snap_to_spacing,
        )
        self.snap_overlay.update_guides(result.guides)
        return result

    def clear_snap_guides(self):
        """清除吸附参考线。"""
        self.snap_overlay.clear_guides()

    # ------------------------------------------------------------------
    # Array, mirror, same-size operations
    # ------------------------------------------------------------------

    def _get_selected_pos_size(self) -> list:
        """获取所有选中控件的 (position, size) 列表。"""
        items = [i for i in self.selectedItems() if isinstance(i, GUIWidgetItem)]
        return [(i, i.node.position, (i._display_w, i._display_h)) for i in items]

    def linear_array_selected(self, count: int, offset_x: int, offset_y: int):
        """对选中控件执行线性阵列。"""
        from ..core.array_mirror import compute_linear_array
        from ..core.undo import AddWidgetCommand, CompoundCommand

        sel = self._get_selected_pos_size()
        if not sel:
            return

        sources = [(pos, size) for _, pos, size in sel]
        copies_per_step = compute_linear_array(sources, count, offset_x, offset_y)

        cmds = []
        new_items = []
        existing_names = {w.name for w in self.doc.all_widgets() if w.name} if self.doc else set()
        for step_copies in copies_per_step:
            for i, ((nx, ny), (w, h)) in enumerate(step_copies):
                src_item = sel[i][0]
                src_node = src_item.node
                new_node = src_node.clone()
                make_names_unique(new_node, existing_names)
                new_node.position = (nx, ny)
                # 加入父节点或根列表
                if src_node.parent:
                    src_node.parent.add_child(new_node)
                elif self.doc:
                    self.doc.roots.append(new_node)
                if self.undo_stack and self.doc:
                    cmd = AddWidgetCommand(self.doc, new_node,
                                           parent=src_node.parent)
                    cmds.append(cmd)
                new_items.append((new_node, src_item.parentItem()))

        if cmds and self.undo_stack:
            compound = CompoundCommand(cmds,
                                       f'线性阵列 ({count} 副本)')
            self.undo_stack.push(compound, execute=False)

        # 创建场景 item
        for new_node, parent_item in new_items:
            self._create_item_for_node(new_node, parent_item)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def circular_array_selected(self, count: int, center_x: float,
                                center_y: float, radius: float,
                                mode: str = 'center'):
        """对选中控件执行圆形阵列。"""
        from ..core.array_mirror import compute_circular_array
        from ..core.undo import (AddWidgetCommand, MoveWidgetCommand,
                                 CompoundCommand)

        sel = self._get_selected_pos_size()
        if not sel:
            return

        sources = [(pos, size) for _, pos, size in sel]

        # center 模式：以选中控件的集合中心为圆心，忽略 dialog 传来的坐标
        if mode == 'center':
            actual_cx = sum((pos[0] + size[0] / 2) for _, pos, size in sel) / len(sel)
            actual_cy = sum((pos[1] + size[1] / 2) for _, pos, size in sel) / len(sel)
        else:
            actual_cx, actual_cy = center_x, center_y

        copies_per_step, original_moves = compute_circular_array(
            sources, count, actual_cx, actual_cy, radius, mode=mode)

        cmds = []
        new_items = []
        existing_names = {w.name for w in self.doc.all_widgets() if w.name} if self.doc else set()

        # on_ring 模式：先移动原件到环上起始位置
        if mode == 'on_ring' and original_moves:
            for i, ((nx, ny), _) in enumerate(original_moves):
                src_item = sel[i][0]
                src_node = src_item.node
                old_pos = src_node.position
                if old_pos != (nx, ny):
                    src_node.position = (nx, ny)
                    src_node.mark_source_modified()
                    if self.undo_stack and self.doc:
                        cmd = MoveWidgetCommand(self.doc, src_node,
                                                old_pos, (nx, ny))
                        cmds.append(cmd)
                    self._refresh_item_position(src_item)

        # 创建新副本
        for step_copies in copies_per_step:
            for i, ((nx, ny), (w, h)) in enumerate(step_copies):
                src_item = sel[i][0]
                src_node = src_item.node
                new_node = src_node.clone()
                make_names_unique(new_node, existing_names)
                new_node.position = (nx, ny)
                if src_node.parent:
                    src_node.parent.add_child(new_node)
                elif self.doc:
                    self.doc.roots.append(new_node)
                if self.undo_stack and self.doc:
                    cmd = AddWidgetCommand(self.doc, new_node,
                                           parent=src_node.parent)
                    cmds.append(cmd)
                new_items.append((new_node, src_item.parentItem()))

        if cmds and self.undo_stack:
            compound = CompoundCommand(cmds,
                                       f'圆形阵列 ({count} 份)')
            self.undo_stack.push(compound, execute=False)

        for new_node, parent_item in new_items:
            self._create_item_for_node(new_node, parent_item)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def mirror_selected(self, axis: str, copy: bool = True):
        """对选中控件执行镜像操作。"""
        from ..core.array_mirror import compute_mirror
        from ..core.undo import (MoveWidgetCommand, AddWidgetCommand,
                                 CompoundCommand)

        sel = self._get_selected_pos_size()
        if not sel:
            return

        sources = [(pos, size) for _, pos, size in sel]
        mirrored = compute_mirror(sources, axis)

        cmds = []
        if copy:
            # 镜像复制：创建新控件
            new_items = []
            existing_names = {w.name for w in self.doc.all_widgets() if w.name} if self.doc else set()
            for i, ((nx, ny), (w, h)) in enumerate(mirrored):
                src_item = sel[i][0]
                src_node = src_item.node
                new_node = src_node.clone()
                make_names_unique(new_node, existing_names)
                new_node.position = (nx, ny)
                if src_node.parent:
                    src_node.parent.add_child(new_node)
                elif self.doc:
                    self.doc.roots.append(new_node)
                if self.undo_stack and self.doc:
                    cmd = AddWidgetCommand(self.doc, new_node,
                                           parent=src_node.parent)
                    cmds.append(cmd)
                new_items.append((new_node, src_item.parentItem()))

            if cmds and self.undo_stack:
                axis_name = '水平' if axis == 'h' else '垂直'
                compound = CompoundCommand(cmds,
                                           f'镜像复制 ({axis_name})')
                self.undo_stack.push(compound, execute=False)

            for new_node, parent_item in new_items:
                self._create_item_for_node(new_node, parent_item)
        else:
            # 镜像移动：改变原控件位置
            for i, ((nx, ny), (w, h)) in enumerate(mirrored):
                item = sel[i][0]
                old_pos = item.node.position
                new_pos = (nx, ny)
                item.node.position = new_pos
                if old_pos != new_pos:
                    cmds.append(MoveWidgetCommand(item.node, old_pos, new_pos))
                # 更新 item 位置
                self._refresh_item_position(item)

            if cmds and self.undo_stack:
                axis_name = '水平' if axis == 'h' else '垂直'
                compound = CompoundCommand(cmds,
                                           f'镜像 ({axis_name})')
                self.undo_stack.push(compound, execute=False)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def make_same_size(self, mode: str = 'width'):
        """使选中控件具有相同尺寸。mode: 'width'/'height'/'both'"""
        from ..core.undo import ResizeWidgetCommand, CompoundCommand

        items = [i for i in self.selectedItems() if isinstance(i, GUIWidgetItem)]
        if len(items) < 2:
            return

        # 以第一个选中的控件为参考
        ref = items[0]
        ref_w, ref_h = ref._display_w, ref._display_h

        cmds = []
        for item in items[1:]:
            old_size = (item._display_w, item._display_h)
            w, h = old_size
            if mode in ('width', 'both'):
                w = ref_w
            if mode in ('height', 'both'):
                h = ref_h
            new_size = (w, h)
            if old_size != new_size:
                item.node.size = new_size
                cmds.append(ResizeWidgetCommand(item.node, old_size, new_size))
                self._refresh_item_position(item)

        if cmds and self.undo_stack:
            desc = {'width': '相同宽度', 'height': '相同高度', 'both': '相同尺寸'}
            compound = CompoundCommand(cmds, desc.get(mode, '相同尺寸'))
            self.undo_stack.push(compound, execute=False)

        if self.doc:
            self.doc.modified = True
        self.document_modified.emit()

    def _create_item_for_node(self, node: WidgetNode,
                              parent_item=None):
        """为节点创建场景 item 并添加到场景。"""
        rm = ResourceManager.instance()
        settings = AppSettings.instance()
        if parent_item and isinstance(parent_item, GUIWidgetItem):
            pw, ph = parent_item._display_w, parent_item._display_h
        else:
            pw, ph = settings.canvas_size
            parent_item = None
        dw, dh = self._get_display_size(node, rm)
        px, py = node.position
        tl_x, tl_y = compute_widget_topleft(
            pw, ph, dw, dh,
            node.orientation, effective_origo(node), px, py)
        new_item = GUIWidgetItem(node, parent_item=parent_item)
        new_item.setPos(tl_x, tl_y)
        if parent_item is None:
            self.addItem(new_item)
        self._node_to_item[id(node)] = new_item
        new_item.set_preview_mode(self._preview_mode)
        return new_item

    def _refresh_item_position(self, item: GUIWidgetItem):
        """从节点数据刷新 item 的 Qt 位置。"""
        node = item.node
        pw, ph = item._get_parent_size()
        rm = ResourceManager.instance()
        dw, dh = self._get_display_size(node, rm)
        px, py = node.position
        tl_x, tl_y = compute_widget_topleft(
            pw, ph, dw, dh,
            node.orientation, effective_origo(node), px, py)
        item.setPos(tl_x, tl_y)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF):
        settings = AppSettings.instance()
        palette = QApplication.palette()

        # Outer area (outside the canvas frame) — slightly darker than Window
        outer_col = palette.color(QPalette.ColorRole.Window)
        outer_col = outer_col.darker(120)
        painter.fillRect(rect, outer_col)

        cw, ch = settings.canvas_size
        canvas_rect = QRectF(0, 0, cw, ch)

        # Shadow under canvas
        shadow_rect = canvas_rect.adjusted(4, 4, 4, 4)
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 60))

        # Canvas area — Base role
        canvas_col = palette.color(QPalette.ColorRole.Base)
        painter.fillRect(canvas_rect, canvas_col)

        # Canvas border — Highlight role (follows accent color)
        border_col = palette.color(QPalette.ColorRole.Highlight)
        painter.setPen(QPen(border_col, 1))
        painter.drawRect(canvas_rect.adjusted(0, 0, -1, -1))

        # Subtle canvas dimension label in bottom-right corner
        label_col = palette.color(QPalette.ColorRole.PlaceholderText
                                  if hasattr(QPalette.ColorRole, 'PlaceholderText')
                                  else QPalette.ColorRole.Mid)
        painter.setPen(label_col)
        painter.setFont(QFont('Arial', 8))
        painter.drawText(
            QRectF(canvas_rect.right() - 100, canvas_rect.bottom() + 4, 100, 16),
            Qt.AlignmentFlag.AlignLeft,
            f'{int(cw)} × {int(ch)}'
        )

        if settings.show_grid and not self._preview_mode:
            gs = settings.grid_size
            # Grid lines: use Mid color from palette, converted to RGBA with alpha
            mid_col = palette.color(QPalette.ColorRole.Mid)
            r, g, b = mid_col.red(), mid_col.green(), mid_col.blue()
            pen_minor = QPen(QColor(r, g, b, 40), 0)
            pen_major = QPen(QColor(r, g, b, 80), 0)
            x = float(max(0, int(rect.left() / gs) * gs))
            while x <= min(cw, rect.right()):
                painter.setPen(pen_major if int(x) % (gs * 8) == 0 else pen_minor)
                painter.drawLine(QPointF(x, max(0, rect.top())),
                                 QPointF(x, min(ch, rect.bottom())))
                x += gs
            y = float(max(0, int(rect.top() / gs) * gs))
            while y <= min(ch, rect.bottom()):
                painter.setPen(pen_major if int(y) % (gs * 8) == 0 else pen_minor)
                painter.drawLine(QPointF(max(0, rect.left()), y),
                                 QPointF(min(cw, rect.right()), y))
                y += gs

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        nodes = self.get_selected_nodes()
        if not nodes:
            super().keyPressEvent(event)
            return

        step = self.grid_size if self.snap_to_grid else 1

        if event.key() == Qt.Key.Key_Escape:
            # Escape: deselect children, select parent container instead
            current = self.get_selected_item()
            if current:
                parent_item = current.parentItem()
                if isinstance(parent_item, GUIWidgetItem):
                    self.clearSelection()
                    parent_item.setSelected(True)
                    return
            # No parent: just clear selection
            self.clearSelection()
            return

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            return
        elif event.key() == Qt.Key.Key_D and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.duplicate_selected()
            return
        elif event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.copy_selected()
            return
        elif event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.paste_from_clipboard()
            return

        # Arrow key nudge
        dx, dy = 0, 0
        if event.key() == Qt.Key.Key_Up:    dy = -step
        elif event.key() == Qt.Key.Key_Down: dy = step
        elif event.key() == Qt.Key.Key_Left: dx = -step
        elif event.key() == Qt.Key.Key_Right: dx = step

        if dx != 0 or dy != 0:
            for node in nodes:
                x, y = node.position
                node.position = (x + dx, y + dy)
                item = self.get_item_for_node(node)
                if item:
                    self.refresh_item(node)
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)


class GUICanvas(QGraphicsView):
    """Main editing canvas view."""

    node_selected = Signal(object)
    node_property_changed = Signal(object)   # property edited → full canvas refresh needed
    node_position_changed = Signal(object)   # drag/resize → props panel update only (no canvas refresh)
    document_modified = Signal()
    cursor_pos_changed = Signal(float, float)   # scene x, y under cursor

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = GUIScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._apply_background_brush()
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._scene.selection_changed_signal.connect(self.node_selected.emit)
        self._scene.widget_property_changed_signal.connect(self.node_property_changed.emit)
        # widget_moved_signal must NOT connect to node_property_changed (causes infinite loop via
        # refresh_item → setPos → ItemPositionHasChanged → on_widget_moved → node_property_changed
        # → refresh_item). Instead route only to the props-panel-only update signal.
        self._scene.widget_moved_signal.connect(self._on_widget_dragged)
        self._scene.document_modified.connect(self.document_modified.emit)

        self._panning = False
        self._pan_start = None
        self._zoom_level = 1.0
        self._preview_mode = False

    def _on_widget_dragged(self, node):
        """Route drag/resize move signals only to props panel — never back to canvas."""
        self.node_position_changed.emit(node)

    @property
    def gui_scene(self) -> GUIScene:
        return self._scene

    def load_document(self, doc: GUIDocument):
        self._scene.load_document(doc)
        self.fit_to_canvas()

    def fit_to_canvas(self):
        settings = AppSettings.instance()
        cw, ch = settings.canvas_size
        margin = 80
        self.fitInView(QRectF(-margin, -margin, cw + margin * 2, ch + margin * 2),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = self.transform().m11()

    def zoom_in(self):   self._zoom(1.25)
    def zoom_out(self):  self._zoom(1 / 1.25)
    def zoom_reset(self):
        self.resetTransform()
        self._zoom_level = 1.0

    def _zoom(self, factor: float):
        new_zoom = self._zoom_level * factor
        if new_zoom < 0.03 or new_zoom > 32:
            return
        self.scale(factor, factor)
        self._zoom_level = new_zoom

    def center_on_selected(self):
        item = self._scene.get_selected_item()
        if item:
            self.centerOn(item)

    def zoom_to_selection(self):
        """Fit the view to the selected item(s)."""
        items = [i for i in self._scene.selectedItems() if isinstance(i, GUIWidgetItem)]
        if not items:
            return
        from PySide6.QtCore import QRectF
        rect = QRectF()
        for item in items:
            scene_rect = item.mapToScene(item.boundingRect()).boundingRect()
            rect = rect.united(scene_rect)
        margin = 40
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = self.transform().m11()

    def drawForeground(self, painter, rect):
        """Draw a zoom level indicator in the bottom-right corner."""
        super().drawForeground(painter, rect)
        if self._zoom_level <= 0:
            return
        palette = QApplication.palette()
        vp = self.viewport()
        pct = int(round(self._zoom_level * 100))
        text = f'{pct}%'
        font = QFont('Arial', 9)
        painter.save()
        painter.setTransform(self.transform().inverted()[0])  # screen-space
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + 8
        th = fm.height() + 4
        x = vp.width() - tw - 4
        y = vp.height() - th - 4
        # Map viewport corner to scene coords
        scene_pt = self.mapToScene(x, y)
        # HUD background: semi-transparent window color
        hud_bg = palette.color(QPalette.ColorRole.Window)
        hud_bg.setAlpha(180)
        painter.fillRect(QRectF(scene_pt.x(), scene_pt.y(), tw, th), hud_bg)
        hud_text = palette.color(QPalette.ColorRole.WindowText)
        painter.setPen(QPen(hud_text))
        painter.setFont(font)
        painter.drawText(
            QRectF(scene_pt.x() + 4, scene_pt.y() + 2, tw, th),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text
        )
        painter.restore()

    def _apply_background_brush(self):
        """Apply the viewport background color from the current palette."""
        palette = QApplication.palette()
        bg = palette.color(QPalette.ColorRole.Window)
        bg = bg.darker(115)
        self.setBackgroundBrush(QBrush(bg))

    def update_theme(self):
        """Call after a theme change to refresh all canvas colors."""
        self._apply_background_brush()
        self.viewport().update()

    def toggle_preview_mode(self):
        self._preview_mode = not self._preview_mode
        self._scene.set_preview_mode(self._preview_mode)
        return self._preview_mode

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if (event.button() == Qt.MouseButton.MiddleButton or
                (event.button() == Qt.MouseButton.LeftButton and
                 event.modifiers() & Qt.KeyboardModifier.AltModifier)):
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            event.accept()
        else:
            # Re-enable rubber band
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # Emit cursor position in scene coordinates for status bar
        scene_pos = self.mapToScene(event.pos())
        self.cursor_pos_changed.emit(scene_pos.x(), scene_pos.y())
        if self._panning and self._pan_start:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        item = self._scene.itemAt(scene_pos, self.transform())
        menu = QMenu(self)

        if isinstance(item, GUIWidgetItem):
            node = item.node
            title = menu.addAction(f'[{node.widget_type}]  {node.name}')
            title.setEnabled(False)
            menu.addSeparator()

            # Parent container selection
            parent_item = item.parentItem()
            if isinstance(parent_item, GUIWidgetItem):
                sel_parent = menu.addAction(f'选中父容器: {parent_item.node.name}  (Esc)')
                sel_parent.setData(('select_parent', None, None))

            menu.addAction('复制 (Ctrl+D)', self._scene.duplicate_selected)
            if not getattr(node, '_protected', False):
                menu.addAction('删除 (Del)', self._scene.delete_selected)
                # Change widget type submenu
                change_type_menu = menu.addMenu('更改控件类型')
                for wt in sorted(WIDGET_TYPES):
                    if wt != node.widget_type:
                        act = change_type_menu.addAction(WIDGET_LABELS.get(wt, wt))
                        act.setData(('change_type', wt, node))
            menu.addAction('居中视图 (Ctrl+F)', self.center_on_selected)
            menu.addSeparator()
            add_child = menu.addMenu('添加子控件')
            for wt in sorted(WIDGET_TYPES):
                act = add_child.addAction(WIDGET_LABELS.get(wt, wt))
                act.setData(('child', wt, node))
        else:
            add_menu = menu.addMenu('添加控件')
            for wt in sorted(WIDGET_TYPES):
                act = add_menu.addAction(WIDGET_LABELS.get(wt, wt))
                act.setData(('root', wt, None))

        chosen = menu.exec(event.globalPos())
        if chosen and chosen.data():
            mode, wt, parent_node = chosen.data()
            if mode == 'select_parent':
                current = self.get_selected_item()
                if current:
                    p = current.parentItem()
                    if isinstance(p, GUIWidgetItem):
                        self.clearSelection()
                        p.setSelected(True)
                return
            if mode == 'change_type':
                self._change_widget_type(parent_node, wt)
                return
            if wt in WIDGET_TYPES:
                new_name, ok = QInputDialog.getText(
                    self, '控件名称', f'为新建的 {wt} 输入名称:',
                    text=f'new_{wt[:12]}'
                )
                if ok and new_name:
                    self._scene.add_widget(wt, scene_pos, parent_node, name=new_name)

    def _change_widget_type(self, node: 'WidgetNode', new_type: str):
        """Change a widget's type, preserving compatible properties."""
        from ..core.gui_model import CONTAINER_TYPES
        from ..core.undo import CompoundCommand
        old_type = node.widget_type
        # Warn if changing between container and non-container
        if (old_type in CONTAINER_TYPES) != (new_type in CONTAINER_TYPES):
            from PySide6.QtWidgets import QMessageBox
            ret = QMessageBox.question(
                self, '确认更改',
                f'将容器/非容器相互转换可能导致子控件丢失，确认继续？'
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
        node.widget_type = new_type
        if node.widget_type in CONTAINER_TYPES:
            # Remove direct sprite properties - containers don't have them
            for k in ('spriteType', 'quadTextureSprite', 'scale'):
                node.properties.pop(k, None)
        if self._scene.doc:
            self._scene.doc.modified = True
        # Rebuild item in scene
        self._scene.refresh_item(node)
        self._scene.document_modified.emit()

    def add_widget_at_center(self, widget_type: str, name: str = '') -> WidgetNode:
        settings = AppSettings.instance()
        cw, ch = settings.canvas_size
        return self._scene.add_widget(widget_type, QPointF(cw // 2, ch // 2), name=name)

    def select_all(self):
        for item in self._scene.items():
            if isinstance(item, GUIWidgetItem) and not item._locked:
                item.setSelected(True)
