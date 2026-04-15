"""
Canvas widget items for the Stellaris GUI editor.

Rendering rules (from Stellaris wiki):
  - spriteType: ALWAYS fixed size = natural image size × scale. Size property ignored.
  - quadTextureSprite → check actual sprite type in GFX registry:
      * corneredTileSpriteType (is_scalable=True): rendered as 9-patch at widget's size
      * spriteType in registry: rendered at natural size × scale (same as spriteType attr)
  - background: fills parent container using 9-patch or fixed sprite
  - centerPosition = yes: behaves like origo = center

Position commit (reverse calculation):
  When a widget is dragged, convert Qt top-left → Stellaris position:
    stellaris_pos = qt_tl - anchor + origo_offset
"""
from __future__ import annotations
import math
from typing import List, Optional, Tuple, TYPE_CHECKING

from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QStyleOptionGraphicsItem, QWidget
from PySide6.QtCore import Qt, QRectF, QPointF, QRect
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPixmap, QFontMetrics, QTextDocument,
)

from ..core.gui_model import (
    WidgetNode, WIDGET_COLORS, WIDGET_LABELS,
    reverse_compute_position, orientation_to_anchor, origo_to_offset,
    effective_origo,
)
from .icon_provider import IconProvider
from ..core.resource_manager import ResourceManager

if TYPE_CHECKING:
    pass

HANDLE_SIZE = 8
HANDLE_HALF = HANDLE_SIZE // 2
HANDLE_NW, HANDLE_N, HANDLE_NE = 0, 1, 2
HANDLE_E, HANDLE_SE, HANDLE_S   = 3, 4, 5
HANDLE_SW, HANDLE_W              = 6, 7


def _paint_single_line_loc_with_icons(
    painter: QPainter,
    line_rect: QRectF,
    line: str,
    fm: QFontMetrics,
    halign: Qt.AlignmentFlag,
    base_color: QColor,
    rm: ResourceManager,
) -> None:
    """Draw one line that may contain £text_icon£ segments; left/center/right within line_rect."""
    lh = fm.height()
    gap = 2
    segments = ResourceManager.split_loc_text_and_icons(line)
    items: List[Tuple] = []
    for kind, payload in segments:
        if kind == 'text':
            plain = ResourceManager.strip_stellaris_color_codes_plain(payload)
            if plain:
                items.append(('t', plain))
        else:
            pm = rm.get_text_icon_pixmap_for_line_height(payload, lh)
            items.append(('i', pm, payload))
    if not items:
        return

    tw = 0.0
    for i, it in enumerate(items):
        if i > 0:
            tw += gap
        if it[0] == 't':
            tw += fm.horizontalAdvance(it[1])
        else:
            pm = it[1]
            tw += pm.width() if pm and not pm.isNull() else lh

    x = line_rect.left() + 2
    if halign & Qt.AlignmentFlag.AlignHCenter:
        x = line_rect.center().x() - tw / 2
    elif halign & Qt.AlignmentFlag.AlignRight:
        x = line_rect.right() - tw - 2

    baseline = line_rect.top() + (line_rect.height() + fm.ascent() - fm.descent()) / 2
    painter.setPen(QPen(base_color))
    for i, it in enumerate(items):
        if i > 0:
            x += gap
        if it[0] == 't':
            painter.drawText(QPointF(x, baseline), it[1])
            x += fm.horizontalAdvance(it[1])
        else:
            pm = it[1]
            if pm and not pm.isNull():
                py = baseline - fm.ascent() + max(0, (fm.ascent() - pm.height()) // 2)
                painter.drawPixmap(int(x), int(py), pm)
                x += pm.width()


def paint_localized_text_with_text_icons(
    painter: QPainter,
    rect: QRectF,
    resolved_text: str,
    font: QFont,
    halign: Qt.AlignmentFlag,
    base_color: QColor,
    rm: ResourceManager,
    vert_align: str = 'center',
) -> None:
    """Preview localisation with £key£ inline icons (GFX_text_* sprites)."""
    painter.setFont(font)
    fm = QFontMetrics(font)
    line_spacing = fm.lineSpacing()
    lines = resolved_text.split('\n')
    total_h = max(line_spacing, len(lines) * line_spacing)
    if vert_align == 'top':
        y0 = rect.top()
    else:
        y0 = rect.top() + max(0.0, (rect.height() - total_h) / 2)

    painter.save()
    painter.setClipRect(rect)
    for li, line in enumerate(lines):
        y_line = y0 + li * line_spacing
        lr = QRectF(rect.x(), y_line, rect.width(), line_spacing)
        if '£' not in line:
            plain = ResourceManager.strip_stellaris_color_codes_plain(line)
            painter.setPen(QPen(base_color))
            painter.drawText(
                lr.adjusted(2, 0, -2, 0),
                halign | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                plain,
            )
        else:
            _paint_single_line_loc_with_icons(
                painter, lr, line, fm, halign, base_color, rm,
            )
    painter.restore()


# ---------------------------------------------------------------------------
# 9-patch drawing
# ---------------------------------------------------------------------------

def draw_nine_patch(
    painter: QPainter,
    pixmap: QPixmap,
    border_x: int,
    border_y: int,
    target_rect: QRectF,
):
    """
    Draw a corneredTileSpriteType (9-patch) sprite into target_rect.

    The borderSize { x=bx y=by } in the .gfx definition means:
      - Corners are bx×by pixels (fixed, not stretched)
      - Edges and center are stretched to fill target_rect
    """
    if pixmap.isNull():
        return

    tx, ty = int(target_rect.x()), int(target_rect.y())
    tw, th = max(1, int(target_rect.width())), max(1, int(target_rect.height()))
    pw, ph = pixmap.width(), pixmap.height()

    bx = min(border_x, pw // 3, tw // 3)
    by = min(border_y, ph // 3, th // 3)
    if bx <= 0 or by <= 0:
        # No border: just stretch
        painter.drawPixmap(QRect(tx, ty, tw, th), pixmap)
        return

    # Source dimensions
    cw_src = pw - 2 * bx   # center width in source
    ch_src = ph - 2 * by   # center height in source
    # Target dimensions
    cw_dst = tw - 2 * bx   # center width in target
    ch_dst = th - 2 * by   # center height in target

    if cw_src <= 0 or ch_src <= 0:
        painter.drawPixmap(QRect(tx, ty, tw, th), pixmap)
        return

    def src(x, y, w, h):
        return QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))

    def dst(x, y, w, h):
        return QRect(tx + int(x), ty + int(y), max(1, int(w)), max(1, int(h)))

    # Draw all 9 pieces
    painter.drawPixmap(dst(0,           0,           bx,     by),     pixmap, src(0,          0,           bx,     by))    # TL
    painter.drawPixmap(dst(bx,          0,           cw_dst, by),     pixmap, src(bx,         0,           cw_src, by))    # T
    painter.drawPixmap(dst(bx + cw_dst, 0,           bx,     by),     pixmap, src(bx + cw_src,0,           bx,     by))    # TR
    painter.drawPixmap(dst(0,           by,          bx,     ch_dst), pixmap, src(0,          by,          bx,     ch_src)) # L
    painter.drawPixmap(dst(bx,          by,          cw_dst, ch_dst), pixmap, src(bx,         by,          cw_src, ch_src)) # C
    painter.drawPixmap(dst(bx + cw_dst, by,          bx,     ch_dst), pixmap, src(bx + cw_src,by,          bx,     ch_src)) # R
    painter.drawPixmap(dst(0,           by + ch_dst, bx,     by),     pixmap, src(0,          by + ch_src, bx,     by))    # BL
    painter.drawPixmap(dst(bx,          by + ch_dst, cw_dst, by),     pixmap, src(bx,         by + ch_src, cw_src, by))    # B
    painter.drawPixmap(dst(bx + cw_dst, by + ch_dst, bx,     by),     pixmap, src(bx + cw_src,by + ch_src, bx,     by))    # BR


# ---------------------------------------------------------------------------
# Tooltip overlay (preview mode hover simulation)
# ---------------------------------------------------------------------------

class TooltipOverlayItem(QGraphicsRectItem):
    """
    Renders a Stellaris-style tooltip popup in preview mode.
    Uses GFX_tooltip_bg as a nine-patch background.
    """
    _TIP_W = 280
    _TIP_H = 80
    _PAD   = 8

    def __init__(self, text: str, scene_pos: QPointF):
        super().__init__()
        self.setZValue(9999)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, False)
        self._text = text
        self._bg_pixmap: Optional[QPixmap] = None
        self._bg_bx = 6
        self._bg_by = 6

        rm = ResourceManager.instance()
        bg_info = rm.get_sprite('GFX_tooltip_bg')
        if bg_info:
            self._bg_pixmap = rm.get_raw_pixmap('GFX_tooltip_bg')
            self._bg_bx, self._bg_by = bg_info.border_size

        # Measure text to size the box
        fm = QFont('Microsoft YaHei', 9)
        from PySide6.QtGui import QFontMetrics
        fmx = QFontMetrics(fm)
        if '£' in text:
            tw = 0
            for kind, seg in ResourceManager.split_loc_text_and_icons(text):
                if kind == 'text':
                    tw += fmx.horizontalAdvance(
                        ResourceManager.strip_stellaris_color_codes_plain(seg))
                else:
                    tw += max(18, fmx.height())
            max_w = min(tw + self._PAD * 2, 380)
            lines = text.split('\n')
            text_h = fmx.height() * max(1, len(lines)) + self._PAD * 2
        else:
            lines = text.split('\n')
            max_w = min(max((fmx.horizontalAdvance(l) for l in lines), default=100) + self._PAD * 2, 380)
            text_h = fmx.height() * max(1, len(lines)) + self._PAD * 2
        w = max(max_w, 120)
        h = max(text_h + self._PAD * 2, 40)

        self.setRect(0, 0, w, h)
        # Position near cursor but keep on screen
        self.setPos(scene_pos.x() + 12, scene_pos.y() + 12)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            draw_nine_patch(painter, self._bg_pixmap, self._bg_bx, self._bg_by, rect)
        else:
            painter.fillRect(rect, QColor(20, 20, 30, 220))
            painter.setPen(QPen(QColor('#c8b45a'), 1))
            painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

        inner = QRectF(rect.adjusted(self._PAD, self._PAD, -self._PAD, -self._PAD))
        tip_font = QFont('Microsoft YaHei', 9)
        painter.setFont(tip_font)
        if '£' in self._text:
            paint_localized_text_with_text_icons(
                painter, inner, self._text, tip_font,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                QColor('#e8e0c8'), ResourceManager.instance(), vert_align='top',
            )
        else:
            painter.setPen(QPen(QColor('#e8e0c8')))
            painter.drawText(
                inner,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                self._text,
            )


# ---------------------------------------------------------------------------
# ScrollbarOverlayItem — interactive scrollbar for preview mode
# ---------------------------------------------------------------------------

class ScrollbarOverlayItem(QGraphicsRectItem):
    """Visual scrollbar that can scroll parent widget's child content.
    Constructed from a scrollbarType WidgetNode definition."""

    def __init__(self, sb_node, parent_item, is_horizontal: bool = False):
        super().__init__(parent=parent_item)
        self._sb_node = sb_node
        self._is_horizontal = is_horizontal
        self._scroll_value: float = 0.0  # 0..1
        self._dragging = False
        self._drag_start_val = 0.0
        self._drag_start_pos = QPointF()

        rm = ResourceManager.instance()
        self._track_pm: Optional[QPixmap] = None
        self._slider_pm: Optional[QPixmap] = None
        self._up_pm: Optional[QPixmap] = None
        self._down_pm: Optional[QPixmap] = None

        parent_rect = parent_item.rect()
        sb_size = sb_node.size if sb_node else (18, 200)
        sb_w, sb_h = max(sb_size[0], 12), max(sb_size[1], 12)

        if is_horizontal:
            self.setRect(0, 0, parent_rect.width(), sb_h)
            self.setPos(0, parent_rect.height())
        else:
            self.setRect(0, 0, sb_w, parent_rect.height())
            self.setPos(parent_rect.width(), 0)

        for child in (sb_node.children if sb_node else []):
            sn = child.get_sprite_name()
            nm = (child.name or '').lower()
            if not sn:
                continue
            pm = rm.get_raw_pixmap(sn, frame=child.get_sprite_frame_index())
            if not pm or pm.isNull():
                continue
            if 'slider' in nm and 'track' not in nm:
                self._slider_pm = pm
            elif 'track' in nm:
                self._track_pm = pm
            elif 'up' in nm or 'left' in nm:
                self._up_pm = pm
            elif 'down' in nm or 'right' in nm:
                self._down_pm = pm

        self.setZValue(500)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def get_content_extent(self) -> float:
        """Scrollable content size in parent coordinates (uses layout bases, full subtrees)."""
        parent = self.parentItem()
        if not parent:
            return 0.0
        m = 0.0
        for ch in parent.childItems():
            if ch is self:
                continue
            base_y = getattr(ch, '_scroll_base_y', ch.pos().y())
            base_x = getattr(ch, '_scroll_base_x', ch.pos().x())
            if isinstance(ch, GUIWidgetItem):
                loc_b = ch.scrollable_content_bottom_local()
                loc_r = ch.scrollable_content_right_local()
            else:
                u = ch.boundingRect().united(ch.childrenBoundingRect())
                loc_b = u.bottom()
                loc_r = u.right()
            if self._is_horizontal:
                m = max(m, base_x + loc_r)
            else:
                m = max(m, base_y + loc_b)
        return m

    @property
    def scroll_offset(self) -> float:
        """Pixel scroll offset based on current value."""
        parent = self.parentItem()
        if not parent:
            return 0.0
        prect = parent.rect()
        extent = self.get_content_extent()
        visible = prect.width() if self._is_horizontal else prect.height()
        overflow = max(0, extent - visible)
        return self._scroll_value * overflow

    def _apply_scroll(self):
        """Offset all sibling items to simulate scrolling."""
        parent = self.parentItem()
        if not parent:
            return
        off = self.scroll_offset
        for child in parent.childItems():
            if child is self:
                continue
            if hasattr(child, '_scroll_base_y'):
                if self._is_horizontal:
                    child.setPos(child._scroll_base_x - off, child.pos().y())
                else:
                    child.setPos(child.pos().x(), child._scroll_base_y - off)

    def _ensure_base_positions(self):
        parent = self.parentItem()
        if not parent:
            return
        for child in parent.childItems():
            if child is self:
                continue
            if not hasattr(child, '_scroll_base_y'):
                child._scroll_base_y = child.pos().y()
                child._scroll_base_x = child.pos().x()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        painter.fillRect(rect, QColor(30, 30, 40, 140))

        if self._track_pm and not self._track_pm.isNull():
            painter.drawPixmap(rect.toRect(), self._track_pm)

        slider_rect = self._slider_rect()
        if self._slider_pm and not self._slider_pm.isNull():
            painter.drawPixmap(slider_rect.toRect(), self._slider_pm)
        else:
            painter.fillRect(slider_rect, QColor(120, 110, 80, 200))
            painter.setPen(QPen(QColor(180, 170, 130), 1))
            painter.drawRect(slider_rect.adjusted(0.5, 0.5, -0.5, -0.5))

    def _slider_rect(self) -> QRectF:
        rect = self.rect()
        extent = self.get_content_extent()
        parent = self.parentItem()
        visible = (parent.rect().height() if parent else rect.height()) if not self._is_horizontal \
            else (parent.rect().width() if parent else rect.width())
        ratio = min(1.0, visible / max(1.0, extent))
        if self._is_horizontal:
            slider_w = max(20, rect.width() * ratio)
            x = (rect.width() - slider_w) * self._scroll_value
            return QRectF(rect.x() + x, rect.y(), slider_w, rect.height())
        else:
            slider_h = max(20, rect.height() * ratio)
            y = (rect.height() - slider_h) * self._scroll_value
            return QRectF(rect.x(), rect.y() + y, rect.width(), slider_h)

    def mousePressEvent(self, event):
        if self._slider_rect().contains(event.pos()):
            self._dragging = True
            self._drag_start_val = self._scroll_value
            self._drag_start_pos = event.pos()
            event.accept()
        else:
            r = self.rect()
            if self._is_horizontal:
                self._scroll_value = max(0, min(1, (event.pos().x() - r.x()) / max(1, r.width())))
            else:
                self._scroll_value = max(0, min(1, (event.pos().y() - r.y()) / max(1, r.height())))
            self._ensure_base_positions()
            self._apply_scroll()
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            r = self.rect()
            parent = self.parentItem()
            extent = max(1.0, self.get_content_extent())
            if self._is_horizontal:
                visible = parent.rect().width() if parent else r.width()
                slider_w = max(20.0, r.width() * min(1.0, visible / extent))
                travel = max(1.0, r.width() - slider_w)
                delta = event.pos().x() - self._drag_start_pos.x()
            else:
                visible = parent.rect().height() if parent else r.height()
                slider_h = max(20.0, r.height() * min(1.0, visible / extent))
                travel = max(1.0, r.height() - slider_h)
                delta = event.pos().y() - self._drag_start_pos.y()
            self._scroll_value = max(0, min(1, self._drag_start_val + delta / travel))
            self._ensure_base_positions()
            self._apply_scroll()
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def wheelEvent(self, event):
        delta = event.delta() if hasattr(event, 'delta') else 0
        if delta == 0:
            try:
                delta = event.angleDelta().y()
            except Exception:
                delta = -120
        step = -0.05 if delta > 0 else 0.05
        self._scroll_value = max(0, min(1, self._scroll_value + step))
        self._ensure_base_positions()
        self._apply_scroll()
        self.update()
        event.accept()


# ---------------------------------------------------------------------------
# GUIWidgetItem
# ---------------------------------------------------------------------------

class GUIWidgetItem(QGraphicsRectItem):
    """
    Visual representation of a WidgetNode on the canvas.
    """

    def __init__(self, node: WidgetNode, parent_item=None):
        super().__init__(parent=parent_item)
        self.node = node
        self._sprite_pixmap: Optional[QPixmap] = None
        self._bg_pixmap: Optional[QPixmap] = None
        self._render_mode: str = 'none'   # 'none', 'fixed', 'nine_patch'
        self._bg_render_mode: str = 'none'
        self._handles_visible = False
        self._resize_handle = -1
        self._resize_start_rect: Optional[QRectF] = None
        self._drag_start: Optional[QPointF] = None
        self._preview_mode = False
        self._locked = False
        self._visible_flag = True
        self._display_w = 0
        self._display_h = 0
        self.hasMoved = False
        self._old_pos: Optional[Tuple[int, int]] = None
        self._tooltip_overlay: Optional['TooltipOverlayItem'] = None
        self._bg_bx_override: Optional[int] = None
        self._bg_by_override: Optional[int] = None
        # Event context overrides
        self._event_text_override: Optional[str] = None   # desc / option text
        self._event_room_pixmap = None                    # room image for portrait
        self._event_room_scale: float = 1.0               # scale for room image
        # (reserved for future override; currently unused — see set_event_overrides)
        self._event_room_display_size: Optional[Tuple[int, int]] = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

        self.refresh()

    def refresh(self):
        self.prepareGeometryChange()
        self._compute_display_size()
        self._load_sprites()
        self.setRect(0, 0, self._display_w, self._display_h)
        self.update()

    def refresh_auto_size(self):
        """
        For containers without size= in script: visual rect from child items.
        Keeps node._editor_layout_size in sync for layout math.
        """
        node = self.node
        if not node.is_implicit_size_container():
            return
        cbr = self.childrenBoundingRect()
        if cbr.isEmpty():
            return
        margin = 8
        new_w = max(10, int(cbr.right()) + margin)
        new_h = max(10, int(cbr.bottom()) + margin)
        if new_w != self._display_w or new_h != self._display_h:
            self.prepareGeometryChange()
            self._display_w = new_w
            self._display_h = new_h
            self.node._editor_layout_size = (new_w, new_h)
            self.node._editor_resolved_size = (new_w, new_h)
            self.setRect(0, 0, new_w, new_h)
            self.update()

    def scrollable_content_right_local(self) -> float:
        """Right edge of this item + descendants in local coords (for horizontal scroll)."""
        return float(self.boundingRect().united(self.childrenBoundingRect()).right())

    def scrollable_content_bottom_local(self) -> float:
        """Bottom edge in local coords; text boxes use wrapped text height when taller than rect."""
        united = self.boundingRect().united(self.childrenBoundingRect())
        base = float(united.bottom())
        wt = self.node.widget_type.lower()
        if wt not in ('instanttextboxtype', 'textboxtype'):
            return base

        if self._event_text_override is not None:
            text = self._event_text_override
        else:
            text_key = self.node.get_text_localization_key()
            if not text_key:
                return base
            text = ResourceManager.instance().get_loc(text_key) or text_key
        if not text or not str(text).strip():
            return base

        font = QFont('Microsoft YaHei', 9)
        fm = QFontMetrics(font)
        mw = self.node.properties.get('maxWidth')
        try:
            mwf = float(mw) if mw else float(self.rect().width())
        except (TypeError, ValueError):
            mwf = float(self.rect().width())
        w = max(20, int(min(mwf, self.rect().width()) - 4))
        br = fm.boundingRect(
            QRect(0, 0, w, 2_000_000),
            int(Qt.TextFlag.TextWordWrap),
            str(text),
        )
        cap = self.node.properties.get('maxHeight')
        try:
            cap_i = int(cap) if cap else 2_000_000
        except (TypeError, ValueError):
            cap_i = 2_000_000
        text_h = float(min(br.height() + 8, cap_i))
        return max(base, text_h)

    def _compute_display_size(self):
        node = self.node
        rm = ResourceManager.instance()
        render_mode = rm.get_widget_render_mode(node)
        self._render_mode = render_mode

        # spriteType (fixed): Stellaris renders at natural size regardless of declared size=.
        # Use sprite natural size × scale as the visual bounding box so the selection rect
        # matches what is actually drawn.  corneredTileSpriteType (nine_patch) fills the
        # declared size, so that path falls through to _editor_resolved_size below.
        if render_mode == 'fixed':
            sprite_name = node.get_sprite_name()
            if sprite_name:
                nw, nh = rm.get_sprite_natural_size(sprite_name)
                if nw > 0:
                    sc = node.scale
                    self._display_w = max(1, int(nw * sc))
                    self._display_h = max(1, int(nh * sc))
                    self._display_w, self._display_h = node.editor_expand_fixed_size_for_caption(
                        self._display_w, self._display_h,
                    )
                    return

        # nine_patch / no sprite / sprite not found: use declared or layout-computed size
        ers = getattr(node, '_editor_resolved_size', None)
        if ers:
            self._display_w = max(1, int(ers[0]))
            self._display_h = max(1, int(ers[1]))
            return
        els = getattr(node, '_editor_layout_size', None)
        if els:
            self._display_w = max(1, int(els[0]))
            self._display_h = max(1, int(els[1]))
            return
        w, h = node.size
        self._display_w = max(1, w)
        self._display_h = max(1, h)

    def _load_sprites(self):
        node = self.node
        rm = ResourceManager.instance()
        self._sprite_pixmap = None
        self._bg_pixmap = None
        self._bg_render_mode = 'none'
        self._bg_bx_override = None
        self._bg_by_override = None
        self._has_missing_sprite = False  # 精灵已指定但无法加载（动态精灵或未索引）

        # Support direct textureFile path (common in textBoxType).
        # instantTextBoxType + font property: game ignores textureFile in this combination.
        is_text_widget = node.widget_type == 'instantTextBoxType' and node.properties.get('font')
        tex_file = '' if is_text_widget else (
            node.properties.get('textureFile') or
            node.properties.get('texturefile') or
            node.properties.get('textureFilePath', '')
        )
        if tex_file and isinstance(tex_file, str):
            abs_path = rm.resolve_texture_path(tex_file)
            if abs_path:
                pm = rm._load_pixmap_from_file(abs_path)
                if pm and not pm.isNull():
                    self._bg_pixmap = pm
                    # Detect if the texture path refers to a corneredTileSpriteType sprite
                    # by searching registered sprites that share this texture path.
                    # Also treat any texture under a "tiles/" directory as nine-patch.
                    tex_norm = tex_file.replace('\\', '/').lower()
                    is_tile = 'tiles/' in tex_norm or 'tile/' in tex_norm
                    if not is_tile:
                        # Check GFX registry for a matching corneredTileSpriteType
                        for _sname, _sinfo in rm.iter_sprites():
                            stex = (_sinfo.texture_path or '').replace('\\', '/').lower()
                            if stex and (stex in tex_norm or tex_norm.endswith(stex)):
                                if _sinfo.is_scalable():
                                    is_tile = True
                                    # Use registered border sizes
                                    self._bg_bx_override = _sinfo.border_size[0]
                                    self._bg_by_override = _sinfo.border_size[1]
                                break
                    self._bg_render_mode = 'nine_patch' if is_tile else 'fixed'
                    # Update display size based on maxWidth/maxHeight if specified
                    mw = node.properties.get('maxWidth', 0)
                    mh = node.properties.get('maxHeight', 0)
                    if mw and mh:
                        try:
                            self._display_w = max(1, int(mw))
                            self._display_h = max(1, int(mh))
                        except (TypeError, ValueError):
                            pass

        sprite_name = node.get_sprite_name()
        sprite_frame = node.get_sprite_frame_index()
        if sprite_name:
            if self._render_mode == 'fixed':
                self._sprite_pixmap = rm.get_sprite_pixmap_scaled(
                    sprite_name, node.scale, frame=sprite_frame,
                )
            else:
                # nine_patch: load at natural size, draw with 9-patch
                self._sprite_pixmap = rm.get_raw_pixmap(
                    sprite_name, frame=sprite_frame,
                )
            # 精灵已指定但无法加载时标记（动态精灵/未索引/纹理缺失）
            if self._sprite_pixmap is None:
                self._has_missing_sprite = True

        bg = node.get_background()
        if bg:
            bg_sprite = bg.get('quadTextureSprite', bg.get('spriteType', ''))
            if bg_sprite:
                bg_frame = node.get_background_sprite_frame_index()
                bg_info = rm.get_sprite(bg_sprite)
                if bg_info and bg_info.is_scalable():
                    self._bg_render_mode = 'nine_patch'
                    self._bg_pixmap = rm.get_raw_pixmap(bg_sprite, frame=bg_frame)
                else:
                    self._bg_render_mode = 'fixed'
                    self._bg_pixmap = rm.get_sprite_pixmap_scaled(
                        bg_sprite, 1.0, frame=bg_frame,
                    )

    def set_handles_visible(self, visible: bool):
        self._handles_visible = visible
        self.update()

    def set_preview_mode(self, enabled: bool):
        self._preview_mode = enabled
        if not enabled:
            self._remove_tooltip_overlay()
        self.update()

    def set_event_overrides(self, text_override: Optional[str], room_pixmap,
                            room_scale: float = 1.0):
        """Apply event context: override text and/or room image for this widget."""
        self._event_text_override = text_override
        self._event_room_pixmap = room_pixmap
        self._event_room_scale = room_scale
        self.update()

    def hoverEnterEvent(self, event):
        if self._preview_mode:
            tooltip_key = self.node.get_tooltip_key()
            if tooltip_key:
                rm = ResourceManager.instance()
                tip_text = rm.get_loc(tooltip_key)
                if tip_text and tip_text != tooltip_key:
                    scene = self.scene()
                    if scene:
                        scene_pos = self.mapToScene(event.pos())
                        self._tooltip_overlay = TooltipOverlayItem(tip_text, scene_pos)
                        scene.addItem(self._tooltip_overlay)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._remove_tooltip_overlay()
        super().hoverLeaveEvent(event)

    def _remove_tooltip_overlay(self):
        if self._tooltip_overlay:
            scene = self.scene()
            if scene and self._tooltip_overlay.scene() == scene:
                scene.removeItem(self._tooltip_overlay)
            self._tooltip_overlay = None

    def set_locked(self, locked: bool):
        """
        Locked items remain visible but are NOT interactive.
        Mouse events are ignored so they pass through to items behind them.
        """
        self._locked = locked
        # Disable movable + selectable so Qt won't include it in drags/selections
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not locked)
        # Also propagate to children – they should be locked too
        for child in self.childItems():
            if isinstance(child, GUIWidgetItem):
                child.set_locked(locked)
        self.update()

    def set_visible_flag(self, visible: bool):
        """
        Hidden items are completely invisible and pass all events through.
        Use Qt's setVisible() so the item is removed from hit-testing entirely.
        """
        self._visible_flag = visible
        self.setVisible(visible)
        # Children inherit Qt visibility automatically

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        rect = self.rect()
        color_str = WIDGET_COLORS.get(self.node.widget_type, '#555555')
        color = QColor(color_str)

        # ── Room image (event context — renders at portrait iconType's position & scale)
        if self._event_room_pixmap and not self._event_room_pixmap.isNull():
            pm = self._event_room_pixmap
            rs = getattr(self, '_event_room_scale', 1.0) or 1.0
            draw_w = int(pm.width() * rs)
            draw_h = int(pm.height() * rs)
            painter.drawPixmap(
                QRect(int(rect.x()), int(rect.y()), draw_w, draw_h), pm)
        elif self._event_room_pixmap is not None:
            painter.fillRect(rect, QColor(40, 30, 60, 180))
            painter.setPen(QPen(QColor('#aaa')))
            painter.setFont(QFont('Microsoft YaHei', 8))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             self._event_text_override or '[域引用 Room]')

        # ── Background sprite ────────────────────────────────────────────────
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            # 应用 background 块自身的 position 偏移（容器内背景可独立定位）
            bg_off_x, bg_off_y = 0.0, 0.0
            _bg_block = self.node.get_background()
            if _bg_block:
                _bg_pos = _bg_block.get('position', {})
                if isinstance(_bg_pos, dict):
                    try:
                        bg_off_x = float(_bg_pos.get('x', 0) or 0)
                        bg_off_y = float(_bg_pos.get('y', 0) or 0)
                    except (TypeError, ValueError):
                        pass
            bg_rect = QRectF(rect.x() + bg_off_x, rect.y() + bg_off_y,
                             rect.width(), rect.height())
            if self._bg_render_mode == 'nine_patch':
                # Use override border sizes (from textureFile tile detection) if available
                if self._bg_bx_override is not None:
                    bx, by = self._bg_bx_override, self._bg_by_override
                else:
                    bg_sprite = _bg_block.get('quadTextureSprite', _bg_block.get('spriteType', '')) if _bg_block else ''
                    info = ResourceManager.instance().get_sprite(bg_sprite)
                    bx, by = info.border_size if info else (6, 6)
                draw_nine_patch(painter, self._bg_pixmap, bx, by, bg_rect)
            else:
                # fixed 模式：按精灵自然尺寸绘制，不拉伸至容器边界
                pm = self._bg_pixmap
                target = QRectF(bg_rect.x(), bg_rect.y(), pm.width(), pm.height())
                painter.drawPixmap(target.toRect(), pm)

        # ── Main sprite (with optional rotation) ────────────────────────────
        rotation_rad = 0.0
        rot_raw = self.node.properties.get('rotation', 0)
        if rot_raw:
            try:
                rotation_rad = float(rot_raw)
            except (TypeError, ValueError):
                pass

        if self._sprite_pixmap and not self._sprite_pixmap.isNull():
            # Apply rotation transform when rotation property is present
            if rotation_rad != 0.0:
                cx = rect.x() + rect.width() / 2
                cy = rect.y() + rect.height() / 2
                painter.save()
                painter.translate(cx, cy)
                painter.rotate(-math.degrees(rotation_rad))
                painter.translate(-cx, -cy)

            if self._render_mode == 'nine_patch':
                sprite_name = self.node.get_sprite_name()
                info = ResourceManager.instance().get_sprite(sprite_name) if sprite_name else None
                bx, by = info.border_size if info else (8, 8)
                draw_nine_patch(painter, self._sprite_pixmap, bx, by, rect)
            else:
                # spriteType: Stellaris renders at natural size from the widget's top-left.
                # The widget's declared size= does NOT scale or center the image.
                pm = self._sprite_pixmap
                painter.drawPixmap(int(rect.x()), int(rect.y()), pm)

            if rotation_rad != 0.0:
                painter.restore()
        elif getattr(self, '_has_missing_sprite', False) and not self._preview_mode:
            # 精灵已指定但无法加载（动态精灵或资源未索引）：绘制醒目的占位显示
            painter.save()
            # 半透明灰色底色
            painter.fillRect(rect, QColor(80, 80, 80, 60))
            # 橙色虚线边框表示"有精灵但未加载"
            pen_miss = QPen(QColor('#e67e22'), 1, Qt.PenStyle.DashLine)
            pen_miss.setDashPattern([4, 3])
            painter.setPen(pen_miss)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            # 在控件中央绘制精灵名（截断以适应宽度）
            sprite_name = self.node.get_sprite_name() or ''
            if sprite_name and rect.width() > 20 and rect.height() > 12:
                font_miss = QFont('Arial', 7)
                painter.setFont(font_miss)
                painter.setPen(QColor('#e67e22'))
                fm = QFontMetrics(font_miss)
                label = fm.elidedText(sprite_name, Qt.TextElideMode.ElideMiddle, int(rect.width()) - 4)
                painter.drawText(
                    rect.adjusted(2, 2, -2, -2),
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                    label,
                )
            painter.restore()
        elif not self._bg_pixmap:
            # Placeholder fill
            fill = QColor(color)
            fill.setAlpha(0 if self._preview_mode else 30)
            if fill.alpha() > 0:
                painter.fillRect(rect, fill)

        # ── Preview mode: render as close to game as possible ───────────────
        if self._preview_mode:
            self._draw_preview_text(painter, rect)
            if self.isSelected():
                painter.setPen(QPen(QColor('#f0c040'), 2))
                painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
            return

        # ── Editor chrome ────────────────────────────────────────────────────
        # Border style by widget type / state
        is_container = self.node.widget_type in ('containerWindowType', 'scrollAreaType')
        is_protected = getattr(self.node, '_protected', False)
        if is_protected:
            # Protected/vanilla control: distinct border
            pen = QPen(QColor('#c0392b'), 1, Qt.PenStyle.DotLine)
        elif self._locked:
            pen = QPen(QColor('#666666'), 1, Qt.PenStyle.DotLine)
        elif self.isSelected():
            pen = QPen(QColor('#f0c040'), 2, Qt.PenStyle.SolidLine)
        elif is_container:
            # Containers get a more visible solid border
            pen = QPen(color, 1.5, Qt.PenStyle.SolidLine)
        else:
            pen = QPen(color, 1, Qt.PenStyle.DashLine)
            pen.setDashPattern([4, 3])
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

        # Container corner accents for better visibility
        if is_container and not self._locked:
            acc = QColor(color)
            acc.setAlpha(180)
            painter.setPen(QPen(acc, 2))
            corner = min(8, int(rect.width() / 4), int(rect.height() / 4))
            for cx, cy, sdx, sdy in [
                (rect.left(), rect.top(), 1, 1),
                (rect.right(), rect.top(), -1, 1),
                (rect.left(), rect.bottom(), 1, -1),
                (rect.right(), rect.bottom(), -1, -1),
            ]:
                painter.drawLine(int(cx), int(cy), int(cx + sdx * corner), int(cy))
                painter.drawLine(int(cx), int(cy), int(cx), int(cy + sdy * corner))

        # Lock indicator
        if self._locked:
            lock_pm = IconProvider.pixmap('lock', 12)  # 使用主题前景色
            painter.drawPixmap(int(rect.right()) - 14, int(rect.top()) + 2, lock_pm)

        # Label
        self._draw_label(painter, rect)

        # Tooltip indicator badge
        tooltip_key = self.node.get_tooltip_key()
        if tooltip_key and rect.width() > 20:
            ind = QRect(int(rect.right()) - 14, int(rect.top()) + 2, 12, 12)
            painter.fillRect(ind, QColor('#f39c12'))
            painter.setPen(QPen(QColor('#fff')))
            painter.setFont(QFont('Arial', 6, QFont.Weight.Bold))
            painter.drawText(ind, Qt.AlignmentFlag.AlignCenter, 'T')

        # Selection handles
        if self.isSelected() and self._handles_visible and not self._locked:
            self._draw_handles(painter, rect)

    # Stellaris text color codes (from fonts.gfx textcolors block)
    _STELLARIS_COLORS = {
        'M': QColor(163, 53, 238),
        'L': QColor(195, 176, 145),
        'G': QColor(41, 225, 38),
        'R': QColor(252, 86, 70),
        'B': QColor(51, 167, 255),
        'Y': QColor(247, 252, 52),
        'H': QColor(251, 170, 41),
        'C': QColor(31, 224, 202),
        'K': QColor(251, 170, 41),
        'I': QColor(247, 252, 52),
        'T': QColor(255, 255, 255),
        't': QColor(198, 198, 198),
        'E': QColor(135, 255, 207),
        'S': QColor(228, 156, 42),
        'W': QColor(255, 255, 255),
        'P': QColor(225, 110, 110),
        'V': QColor(76, 138, 113),
        'g': QColor(128, 128, 128),
        '_': QColor(255, 0, 255),
        'U': QColor(204, 179, 255),
        'c': QColor(60, 208, 146),
        'v': QColor(139, 174, 162),
        'd': QColor(255, 221, 122),
        'r': QColor(163, 130, 255),
        'l': QColor(178, 236, 104),
        '0': QColor(31, 224, 202),
        '1': QColor(51, 167, 255),
        '2': QColor(163, 53, 238),
        '3': QColor(251, 170, 41),
    }

    @staticmethod
    def _parse_stellaris_text(text: str, extra_colors: dict = None):
        """Parse §X...§! color codes into segments: list of (text, QColor).

        extra_colors overrides _STELLARIS_COLORS when provided (e.g. from fonts.gfx).
        """
        import re
        segments = []
        pos = 0
        pattern = re.compile(r'§(.)(.*?)§!', re.DOTALL)
        default_color = QColor('#e8e0c8')
        color_map = GUIWidgetItem._STELLARIS_COLORS
        if extra_colors:
            color_map = {**color_map, **extra_colors}
        for m in pattern.finditer(text):
            if m.start() > pos:
                segments.append((text[pos:m.start()], default_color))
            code = m.group(1)
            seg_text = m.group(2)
            color = color_map.get(code, default_color)
            segments.append((seg_text, color))
            pos = m.end()
        if pos < len(text):
            segments.append((text[pos:], default_color))
        return segments

    def _draw_preview_text(self, painter: QPainter, rect: QRectF):
        """Render localised text in preview mode (game-like appearance)."""
        node = self.node
        rm = ResourceManager.instance()

        # Event context override takes priority over widget's own text key
        if self._event_text_override is not None:
            resolved = self._event_text_override
        else:
            text_key = node.get_text_localization_key()
            if not text_key:
                return

            resolved = rm.get_loc(text_key)
            if not resolved:
                resolved = text_key

        # instantTextBoxType: default alignment is top-left; other types: center
        is_itb = node.widget_type.lower() == 'instanttextboxtype'
        default_fmt = 'left' if is_itb else 'center'
        fmt = str(node.properties.get('format', default_fmt)).strip('"').lower()
        halign = {
            'left':        Qt.AlignmentFlag.AlignLeft,
            'right':       Qt.AlignmentFlag.AlignRight,
            'center':      Qt.AlignmentFlag.AlignHCenter,
            'centre':      Qt.AlignmentFlag.AlignHCenter,
            'center_left': Qt.AlignmentFlag.AlignLeft,
        }.get(fmt, Qt.AlignmentFlag.AlignLeft if is_itb else Qt.AlignmentFlag.AlignHCenter)
        valign = Qt.AlignmentFlag.AlignTop if is_itb else Qt.AlignmentFlag.AlignVCenter

        font = QFont('Microsoft YaHei', 9)
        painter.setFont(font)

        # text_color_code property overrides default base color
        color_code = str(node.properties.get('text_color_code', '')).strip('"')
        game_colors = rm.get_text_colors()
        color_map = {**self._STELLARIS_COLORS, **game_colors}
        base_color = color_map.get(color_code, QColor('#e8e0c8'))

        draw_rect = rect.adjusted(2, 2, -2, -2)

        # £key£ text icons → GFX_text_<key> sprites
        if '£' in resolved:
            paint_localized_text_with_text_icons(
                painter, rect, resolved, font, halign, base_color, rm)
            return

        if '§' in resolved:
            # Render multi-colored segments using QTextDocument
            segments = self._parse_stellaris_text(resolved, game_colors)
            html_parts = []
            for seg_text, col in segments:
                safe = (seg_text.replace('&', '&amp;')
                               .replace('<', '&lt;')
                               .replace('>', '&gt;')
                               .replace('\n', '<br>'))
                html_parts.append(f'<span style="color:{col.name()};">{safe}</span>')
            align_css = ('center' if halign == Qt.AlignmentFlag.AlignHCenter
                         else 'right' if halign == Qt.AlignmentFlag.AlignRight
                         else 'left')
            tdoc = QTextDocument()
            tdoc.setDefaultFont(font)
            tdoc.setHtml(f'<div style="text-align:{align_css};">{"".join(html_parts)}</div>')
            tdoc.setTextWidth(draw_rect.width())
            th = tdoc.size().height()
            if valign == Qt.AlignmentFlag.AlignVCenter and th < draw_rect.height():
                ty = draw_rect.y() + (draw_rect.height() - th) / 2
            else:
                ty = draw_rect.y()
            painter.save()
            painter.translate(draw_rect.x(), ty)
            tdoc.drawContents(painter)
            painter.restore()
        else:
            painter.setPen(QPen(base_color))
            painter.drawText(
                draw_rect,
                halign | valign | Qt.TextFlag.TextWordWrap,
                resolved,
            )

    def _draw_label(self, painter: QPainter, rect: QRectF):
        # Don't show labels when widget is very small (zoomed out, or tiny widget)
        if rect.width() < 18 or rect.height() < 10:
            return

        rm = ResourceManager.instance()
        node = self.node

        # Event context override shown in label
        if self._event_text_override is not None:
            text_content = self._event_text_override
        else:
            raw_key = node.get_text_localization_key()
            if raw_key:
                resolved = rm.get_loc(raw_key)
                text_content = resolved if resolved else raw_key
            else:
                text_content = None

        name = node.name

        # Determine header label (small type tag in top-left corner)
        if name:
            header_label = name
        else:
            header_label = node.widget_type.replace('Type', '')
        if getattr(node, '_protected', False):
            header_label = f'[L] {header_label}'

        font_small = QFont('Microsoft YaHei', 7)
        painter.setFont(font_small)
        fm = painter.fontMetrics()
        tw = min(fm.horizontalAdvance(header_label) + 4, rect.width() - 4)
        th = fm.height() + 2
        bg_r = QRectF(rect.x() + 1, rect.y() + 1, tw, th)
        painter.fillRect(bg_r, QColor(0, 0, 0, 130))
        painter.setPen(QPen(QColor('#e0e0e0')))
        painter.drawText(
            rect.adjusted(2, 2, -2, -2),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            header_label
        )

        # Also render text content inside widget body (like preview, but dimmer) for text widgets
        if text_content and rect.height() > 16 and rect.width() > 24:
            text_types = ('instantTextBoxType', 'textBoxType', 'editBoxType',
                          'buttonType', 'effectButtonType', 'guiButtonType')
            if node.widget_type in text_types:
                color_code = str(node.properties.get('text_color_code', '')).strip('"')
                base_color = self._STELLARIS_COLORS.get(color_code, QColor('#e8e0c8'))
                base_color.setAlpha(180)
                painter.setPen(QPen(base_color))
                font_content = QFont('Microsoft YaHei', 8)
                painter.setFont(font_content)
                # Tight layout under header; still draw when sprite-only box is short
                text_rect = rect.adjusted(4, th + 1, -4, -2)
                if text_rect.height() < 6:
                    text_rect = rect.adjusted(4, min(th + 1, rect.height() * 0.35), -4, -2)
                fmt = str(node.properties.get('format', 'center')).strip('"').lower()
                halign = {
                    'left': Qt.AlignmentFlag.AlignLeft,
                    'right': Qt.AlignmentFlag.AlignRight,
                    'center': Qt.AlignmentFlag.AlignHCenter,
                    'centre': Qt.AlignmentFlag.AlignHCenter,
                }.get(fmt, Qt.AlignmentFlag.AlignHCenter)
                if '£' in text_content:
                    paint_localized_text_with_text_icons(
                        painter, text_rect, text_content, font_content,
                        halign, base_color, rm, vert_align='center',
                    )
                else:
                    import re as _re
                    plain_text = _re.sub(r'§.', '', text_content).replace('§!', '')
                    painter.drawText(
                        text_rect,
                        halign | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                        plain_text,
                    )

    def _draw_handles(self, painter: QPainter, rect: QRectF):
        painter.setPen(QPen(QColor('#f0c040'), 1))
        painter.setBrush(QBrush(QColor('#2d2d2d')))
        for hp in self._handle_positions(rect):
            painter.drawRect(hp.x() - HANDLE_HALF, hp.y() - HANDLE_HALF,
                             HANDLE_SIZE, HANDLE_SIZE)

    def _handle_positions(self, rect: QRectF):
        cx, cy = rect.center().x(), rect.center().y()
        return [
            QPointF(rect.left(), rect.top()), QPointF(cx, rect.top()),
            QPointF(rect.right(), rect.top()), QPointF(rect.right(), cy),
            QPointF(rect.right(), rect.bottom()), QPointF(cx, rect.bottom()),
            QPointF(rect.left(), rect.bottom()), QPointF(rect.left(), cy),
        ]

    def _handle_at(self, pos: QPointF) -> int:
        if not self._handles_visible:
            return -1
        for i, hp in enumerate(self._handle_positions(self.rect())):
            r = QRectF(hp.x() - HANDLE_HALF - 3, hp.y() - HANDLE_HALF - 3,
                       HANDLE_SIZE + 6, HANDLE_SIZE + 6)
            if r.contains(pos):
                return i
        return -1

    def boundingRect(self) -> QRectF:
        extra = HANDLE_HALF + 4
        return self.rect().adjusted(-extra, -extra, extra, extra)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if self._locked:
            # Pass event to item underneath (Adobe-style: locked = click-through)
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.isSelected():
            handle = self._handle_at(event.pos())
            if handle >= 0:
                self._resize_handle = handle
                self._resize_start_rect = QRectF(self.rect())
                self._drag_start = event.pos()
                event.accept()
                return
        self._resize_handle = -1
        self.hasMoved = False
        self._constrained_axis = None  # Shift 约束拖拽方向
        self._drag_origin = self.pos()  # 拖拽起始位置
        # Record position before move for undo
        self._old_pos = self.node.position
        # 重建吸附索引
        scene = self.scene()
        if scene and hasattr(scene, 'rebuild_snap_index'):
            selected = [i for i in scene.selectedItems()
                        if isinstance(i, GUIWidgetItem)]
            scene.rebuild_snap_index(selected)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_handle >= 0 and self._resize_start_rect and self._drag_start:
            self._do_resize(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)
        # Shift 约束拖拽方向
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and self._drag_origin:
            pos = self.pos()
            dx = abs(pos.x() - self._drag_origin.x())
            dy = abs(pos.y() - self._drag_origin.y())
            if self._constrained_axis is None and (dx > 3 or dy > 3):
                self._constrained_axis = 'h' if dx >= dy else 'v'
            if self._constrained_axis == 'h':
                self.setPos(pos.x(), self._drag_origin.y())
            elif self._constrained_axis == 'v':
                self.setPos(self._drag_origin.x(), pos.y())
        else:
            self._constrained_axis = None

    def mouseReleaseEvent(self, event):
        if self._resize_handle >= 0:
            self._resize_handle = -1
            self._drag_start = None
            self._resize_start_rect = None
            self._commit_to_node(push_undo=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self.hasMoved:
            self._commit_to_node(push_undo=True)
        self.hasMoved = False
        self._old_pos = None
        self._constrained_axis = None
        self._drag_origin = None
        # 清除吸附参考线
        scene = self.scene()
        if scene and hasattr(scene, 'clear_snap_guides'):
            scene.clear_snap_guides()

    _in_snap_adjust = False  # 防止吸附修正触发递归

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.hasMoved = True
            scene = self.scene()
            # 智能吸附（仅在非递归时执行）
            if not GUIWidgetItem._in_snap_adjust and scene and hasattr(scene, 'query_snap'):
                result = scene.query_snap(self)
                if result and (result.snapped_x or result.snapped_y):
                    GUIWidgetItem._in_snap_adjust = True
                    try:
                        self.setPos(self.pos().x() + result.dx,
                                    self.pos().y() + result.dy)
                    finally:
                        GUIWidgetItem._in_snap_adjust = False
            if scene and hasattr(scene, 'on_widget_moved'):
                scene.on_widget_moved(self)
        return super().itemChange(change, value)

    def _get_parent_size(self) -> Tuple[int, int]:
        """Get the parent container's size for position calculation."""
        parent_item = self.parentItem()
        if parent_item and isinstance(parent_item, GUIWidgetItem):
            return parent_item._display_w, parent_item._display_h
        from ..core.settings import AppSettings
        return AppSettings.instance().canvas_size

    def _commit_to_node(self, push_undo: bool = False):
        """
        Write Qt position back to WidgetNode using reverse orientation/origo calculation.
        This correctly recovers the Stellaris script position value.
        """
        qt_pos = self.pos()
        pw, ph = self._get_parent_size()

        # Snap to grid
        scene = self.scene()
        grid = getattr(scene, 'grid_size', 1) if scene else 1
        snap = getattr(scene, 'snap_to_grid', False) if scene else False
        qt_x, qt_y = qt_pos.x(), qt_pos.y()
        if snap and grid > 1:
            qt_x = round(qt_x / grid) * grid
            qt_y = round(qt_y / grid) * grid
            self.setPos(qt_x, qt_y)

        # Reverse calculate Stellaris position
        new_pos = reverse_compute_position(
            qt_x, qt_y, pw, ph,
            self._display_w, self._display_h,
            self.node.orientation, effective_origo(self.node),
        )

        if push_undo and self._old_pos is not None and self._old_pos != new_pos:
            scene = self.scene()
            undo_stack = getattr(scene, 'undo_stack', None) if scene else None
            if undo_stack:
                from ..core.undo import MoveWidgetCommand
                cmd = MoveWidgetCommand(self.node, self._old_pos, new_pos)
                cmd.execute()
                undo_stack.push(cmd, execute=False)
                self._old_pos = new_pos
                return

        self.node.position = new_pos

        scene = self.scene()
        if scene and hasattr(scene, 'on_widget_property_changed'):
            scene.on_widget_property_changed(self)

    def _do_resize(self, mouse_pos: QPointF):
        if not self._resize_start_rect or not self._drag_start:
            return
        dx = mouse_pos.x() - self._drag_start.x()
        dy = mouse_pos.y() - self._drag_start.y()
        r = QRectF(self._resize_start_rect)

        h = self._resize_handle
        if h in (HANDLE_NW, HANDLE_N, HANDLE_NE): r.setTop(r.top() + dy)
        if h in (HANDLE_SW, HANDLE_S, HANDLE_SE): r.setBottom(r.bottom() + dy)
        if h in (HANDLE_NW, HANDLE_W, HANDLE_SW): r.setLeft(r.left() + dx)
        if h in (HANDLE_NE, HANDLE_E, HANDLE_SE): r.setRight(r.right() + dx)
        if r.width() < 4: r.setWidth(4)
        if r.height() < 4: r.setHeight(4)

        self.prepareGeometryChange()
        self._display_w = int(r.width())
        self._display_h = int(r.height())
        self.setRect(r.normalized())

        if self._render_mode == 'fixed':
            sprite_name = self.node.get_sprite_name()
            rm = ResourceManager.instance()
            nw, nh = rm.get_sprite_natural_size(sprite_name) if sprite_name else (0, 0)
            if nw > 0:
                new_scale = round(self._display_w / nw, 4)
                self.node.scale = new_scale
        else:
            self.node.size = (self._display_w, self._display_h)

        # Emit widget_moved_signal (guarded in GUIScene) for live props-panel update
        scene = self.scene()
        if scene and hasattr(scene, 'on_widget_moved') and not getattr(scene, '_refreshing', False):
            scene.widget_moved_signal.emit(self.node)

    def hoverMoveEvent(self, event):
        if self._locked:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            return
        if self.isSelected():
            h = self._handle_at(event.pos())
            cursors = {
                HANDLE_NW: Qt.CursorShape.SizeFDiagCursor,
                HANDLE_SE: Qt.CursorShape.SizeFDiagCursor,
                HANDLE_NE: Qt.CursorShape.SizeBDiagCursor,
                HANDLE_SW: Qt.CursorShape.SizeBDiagCursor,
                HANDLE_N: Qt.CursorShape.SizeVerCursor,
                HANDLE_S: Qt.CursorShape.SizeVerCursor,
                HANDLE_E: Qt.CursorShape.SizeHorCursor,
                HANDLE_W: Qt.CursorShape.SizeHorCursor,
            }
            if h >= 0:
                self.setCursor(cursors.get(h, Qt.CursorShape.SizeAllCursor))
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def wheelEvent(self, event):
        for child in self.childItems():
            if isinstance(child, ScrollbarOverlayItem):
                child.wheelEvent(event)
                if event.isAccepted():
                    return
        super().wheelEvent(event)
