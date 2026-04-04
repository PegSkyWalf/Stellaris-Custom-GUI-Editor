"""
SVG 图标提供器 — 生成主题感知的矢量图标。

所有图标以内联 SVG path data 存储，运行时按需渲染为 QPixmap/QIcon。
通过替换 fill 颜色实现主题适配，按 (name, size, color) 缓存避免重复渲染。
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer


# ---------------------------------------------------------------------------
# SVG path data registry — viewBox 均为 "0 0 16 16"
# ---------------------------------------------------------------------------

_SVG_PATHS: Dict[str, str] = {
    # --- 文件操作 ---
    'new-file': '<path d="M4 1C3.4 1 3 1.4 3 2v12c0 .6.4 1 1 1h8c.6 0 1-.4 1-1V5l-4-4H4zm5 0v3.5c0 .3.2.5.5.5H13" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    'open-file': '<path d="M2 13V4c0-.6.4-1 1-1h3l2 2h5c.6 0 1 .4 1 1v1M2 13l1.7-5c.1-.4.5-.7 1-.7h9.6c.6 0 1.1.5 1 1.1L14 13H2z" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    'save': '<path d="M12.7 2H3c-.6 0-1 .4-1 1v10c0 .6.4 1 1 1h10c.6 0 1-.4 1-1V3.3L12.7 2zM8 12c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zM10 5H4V3h6v2z" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',

    # --- 编辑操作 ---
    'undo': '<path d="M4 6h6c2.2 0 4 1.8 4 4s-1.8 4-4 4H7" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 3L4 6l3 3" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    'redo': '<path d="M12 6H6C3.8 6 2 7.8 2 10s1.8 4 4 4h3" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 3l3 3-3 3" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    'copy': '<rect x="5" y="5" width="8" height="8" rx="1" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M3 11V3c0-.6.4-1 1-1h8" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'delete': '<path d="M3 4h10M6 4V3h4v1M5 4v8c0 .6.4 1 1 1h4c.6 0 1-.4 1-1V4" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    'duplicate': '<rect x="1" y="1" width="8" height="8" rx="1" fill="none" stroke="{color}" stroke-width="1.1"/><rect x="5" y="5" width="8" height="8" rx="1" fill="none" stroke="{color}" stroke-width="1.1"/><path d="M9 7v4M7 9h4" stroke="{color}" stroke-width="1.1" stroke-linecap="round"/>',

    # --- 视图操作 ---
    'zoom-in': '<circle cx="7" cy="7" r="4.5" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M11 11l3.5 3.5M5 7h4M7 5v4" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'zoom-out': '<circle cx="7" cy="7" r="4.5" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M11 11l3.5 3.5M5 7h4" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'zoom-fit': '<rect x="2" y="2" width="12" height="12" rx="1.5" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M2 6h2M2 10h2M12 6h2M12 10h2M6 2v2M10 2v2M6 12v2M10 12v2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'center-view': '<circle cx="8" cy="8" r="2" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M8 2v3M8 11v3M2 8h3M11 8h3" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'preview': '<path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="{color}" stroke-width="1.2"/><circle cx="8" cy="8" r="2.5" fill="none" stroke="{color}" stroke-width="1.2"/>',
    'grid': '<path d="M2 2h12v12H2zM2 6h12M2 10h12M6 2v12M10 2v12" fill="none" stroke="{color}" stroke-width="1" stroke-linecap="round"/>',
    'refresh': '<path d="M2 8a6 6 0 0110.5-4M14 8a6 6 0 01-10.5 4" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/><path d="M12.5 1v3.5H9M3.5 15v-3.5H7" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    'search': '<circle cx="7" cy="7" r="4" fill="none" stroke="{color}" stroke-width="1.3"/><path d="M10.3 10.3L14 14" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>',
    'settings': '<circle cx="8" cy="8" r="2.5" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.1 3.1l1.4 1.4M11.5 11.5l1.4 1.4M3.1 12.9l1.4-1.4M11.5 4.5l1.4-1.4" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',

    # --- 图层面板图标 ---
    'lock': '<rect x="4" y="7" width="8" height="6" rx="1" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'unlock': '<rect x="4" y="7" width="8" height="6" rx="1" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M5.5 7V5a2.5 2.5 0 015 0" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'eye': '<path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="{color}" stroke-width="1.2"/><circle cx="8" cy="8" r="2" fill="{color}"/>',
    'eye-off': '<path d="M2 2l12 12M6.5 6.5a2 2 0 002.9 2.9M1 8s2.5-5 7-5c1 0 1.9.2 2.7.6M15 8s-2.5 5-7 5c-1 0-1.9-.2-2.7-.6" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'checkbox-on': '<rect x="2" y="2" width="12" height="12" rx="2" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M5 8l2.5 2.5L11 6" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
    'checkbox-off': '<rect x="2" y="2" width="12" height="12" rx="2" fill="none" stroke="{color}" stroke-width="1.2"/>',
    'arrow-up': '<path d="M8 3v10M4 7l4-4 4 4" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    'arrow-down': '<path d="M8 13V3M4 9l4 4 4-4" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',

    # --- 状态图标 ---
    'warning': '<path d="M8 1.5L1 14h14L8 1.5z" fill="none" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/><path d="M8 6v4M8 11.5v.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>',
    'checkmark': '<path d="M3 8.5l3.5 3.5L13 4" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
    'diamond': '<path d="M8 2l4 6-4 6-4-6z" fill="{color}"/>',
    'circle-filled': '<circle cx="8" cy="8" r="5" fill="{color}"/>',
    'circle-empty': '<circle cx="8" cy="8" r="5" fill="none" stroke="{color}" stroke-width="1.5"/>',
    'loading': '<path d="M8 2a6 6 0 11-5.2 3" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>',
    'close': '<path d="M4 4l8 8M12 4l-8 8" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>',

    # --- 虚拟编组面板 ---
    'trash': '<path d="M3 4h10M6 4V3h4v1M5 4v8c0 .6.4 1 1 1h4c.6 0 1-.4 1-1V4" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 7v3M9 7v3" stroke="{color}" stroke-width="1" stroke-linecap="round"/>',
    'chevron-left': '<path d="M10 3L5 8l5 5" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
    'chevron-right': '<path d="M6 3l5 5-5 5" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
    'plus': '<path d="M8 3v10M3 8h10" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>',
    'minus': '<path d="M3 8h10" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>',
    'folder-plus': '<path d="M2 4c0-.6.4-1 1-1h3l2 2h6c.6 0 1 .4 1 1v6c0 .6-.4 1-1 1H3c-.6 0-1-.4-1-1V4z" fill="none" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/><path d="M8 7v3M6.5 8.5h3" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'folder-child': '<path d="M2 5c0-.6.4-1 1-1h2.5l1.5 1.5H13c.6 0 1 .4 1 1V12c0 .6-.4 1-1 1H3c-.6 0-1-.4-1-1V5z" fill="none" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/><path d="M4 3v2" stroke="{color}" stroke-width="1" stroke-linecap="round" stroke-dasharray="1 1"/><path d="M7 9.5l1.5 1.5 2-3" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    'group-from-sel': '<rect x="2" y="2" width="12" height="12" rx="1.5" fill="none" stroke="{color}" stroke-width="1" stroke-dasharray="2 1.5"/><path d="M5 5h6v4H5z" fill="none" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/><path d="M8 9v3M6.5 10.5h3" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>',
    'add-to-group': '<rect x="8" y="4" width="6" height="8" rx="1" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M11 7v2M10 8h2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/><path d="M2 8h5M4.5 5.5L2 8l2.5 2.5" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    'remove-from-group': '<rect x="8" y="4" width="6" height="8" rx="1" fill="none" stroke="{color}" stroke-width="1.2"/><path d="M10 8h2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/><path d="M7 8H2M4.5 5.5L2 8l2.5 2.5" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',

    # --- 对齐操作 ---
    'align-left': '<path d="M3 2v12" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/><rect x="5" y="4" width="8" height="3" rx=".5" fill="{color}"/><rect x="5" y="9" width="5" height="3" rx=".5" fill="{color}"/>',
    'align-right': '<path d="M13 2v12" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/><rect x="3" y="4" width="8" height="3" rx=".5" fill="{color}"/><rect x="6" y="9" width="5" height="3" rx=".5" fill="{color}"/>',
    'align-top': '<path d="M2 3h12" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/><rect x="4" y="5" width="3" height="8" rx=".5" fill="{color}"/><rect x="9" y="5" width="3" height="5" rx=".5" fill="{color}"/>',
    'align-bottom': '<path d="M2 13h12" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/><rect x="4" y="3" width="3" height="8" rx=".5" fill="{color}"/><rect x="9" y="6" width="3" height="5" rx=".5" fill="{color}"/>',
    'align-h-center': '<path d="M8 2v12" stroke="{color}" stroke-width="1" stroke-dasharray="1.5 1.5"/><rect x="3" y="4" width="10" height="3" rx=".5" fill="{color}"/><rect x="4.5" y="9" width="7" height="3" rx=".5" fill="{color}"/>',
    'align-v-center': '<path d="M2 8h12" stroke="{color}" stroke-width="1" stroke-dasharray="1.5 1.5"/><rect x="4" y="2" width="3" height="12" rx=".5" fill="{color}"/><rect x="9" y="3.5" width="3" height="9" rx=".5" fill="{color}"/>',
    'distribute-h': '<rect x="1" y="4" width="3" height="8" rx=".5" fill="{color}"/><rect x="6.5" y="4" width="3" height="8" rx=".5" fill="{color}"/><rect x="12" y="4" width="3" height="8" rx=".5" fill="{color}"/><path d="M4.5 8h2M10 8h2" stroke="{color}" stroke-width=".8" stroke-dasharray="1 1"/>',
    'distribute-v': '<rect x="4" y="1" width="8" height="3" rx=".5" fill="{color}"/><rect x="4" y="6.5" width="8" height="3" rx=".5" fill="{color}"/><rect x="4" y="12" width="8" height="3" rx=".5" fill="{color}"/><path d="M8 4.5v2M8 10v2" stroke="{color}" stroke-width=".8" stroke-dasharray="1 1"/>',

    # --- 阵列与镜像 ---
    'array-linear': '<rect x="1" y="5" width="3" height="6" rx=".5" fill="{color}"/><rect x="6" y="5" width="3" height="6" rx=".5" fill="{color}" opacity=".6"/><rect x="11" y="5" width="3" height="6" rx=".5" fill="{color}" opacity=".3"/><path d="M4.5 8h1M9.5 8h1" stroke="{color}" stroke-width="1" stroke-linecap="round"/>',
    'array-circular': '<circle cx="8" cy="8" r="5" fill="none" stroke="{color}" stroke-width=".8" stroke-dasharray="2 1.5"/><rect x="6.5" y="1.5" width="3" height="3" rx=".5" fill="{color}"/><rect x="11.5" y="6.5" width="3" height="3" rx=".5" fill="{color}" opacity=".6"/><rect x="6.5" y="11.5" width="3" height="3" rx=".5" fill="{color}" opacity=".6"/><rect x="1.5" y="6.5" width="3" height="3" rx=".5" fill="{color}" opacity=".3"/>',
    'mirror-h': '<path d="M8 2v12" stroke="{color}" stroke-width="1" stroke-dasharray="2 1.5"/><rect x="2" y="5" width="4" height="6" rx=".5" fill="{color}"/><rect x="10" y="5" width="4" height="6" rx=".5" fill="{color}" opacity=".5"/><path d="M5 8h-.5l-1-1.5v3l1-1.5H5" fill="none" stroke="{color}" stroke-width=".8"/><path d="M11 8h.5l1-1.5v3l-1-1.5H11" fill="none" stroke="{color}" stroke-width=".8"/>',
    'mirror-v': '<path d="M2 8h12" stroke="{color}" stroke-width="1" stroke-dasharray="2 1.5"/><rect x="5" y="2" width="6" height="4" rx=".5" fill="{color}"/><rect x="5" y="10" width="6" height="4" rx=".5" fill="{color}" opacity=".5"/>',

    # --- 尺寸操作 ---
    'same-width': '<path d="M2 2v12M14 2v12" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/><path d="M4 8h8M4 5l-2 3 2 3M12 5l2 3-2 3" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    'same-height': '<path d="M2 2h12M2 14h12" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/><path d="M8 4v8M5 4l3-2 3 2M5 12l3 2 3-2" fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
}

# ---------------------------------------------------------------------------
# Theme colors — updated by ThemeManager.apply()
# ---------------------------------------------------------------------------

_theme_fg: str = '#dddddd'
_theme_accent: str = '#4a9fd4'
_theme_muted: str = '#888888'

# 渲染缓存: (name, size, color) → QPixmap
_cache: Dict[Tuple[str, int, str], QPixmap] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class IconProvider:
    """生成主题感知的 SVG 图标。"""

    @staticmethod
    def set_theme_colors(foreground: str, accent: str, muted: str = ''):
        """主题切换时更新缓存颜色并清空缓存。"""
        global _theme_fg, _theme_accent, _theme_muted
        _theme_fg = foreground or '#dddddd'
        _theme_accent = accent or '#4a9fd4'
        _theme_muted = muted or '#888888'
        _cache.clear()

    @staticmethod
    def pixmap(name: str, size: int = 16, color: str = '') -> QPixmap:
        """返回命名图标的 QPixmap。color 为空时使用主题前景色。"""
        c = color or _theme_fg
        key = (name, size, c)
        cached = _cache.get(key)
        if cached is not None:
            return cached

        svg_body = _SVG_PATHS.get(name)
        if not svg_body:
            # 未知图标 — 返回空 pixmap
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            _cache[key] = pm
            return pm

        # 替换颜色占位符
        svg_content = svg_body.replace('{color}', c)
        svg_doc = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 16 16" width="{size}" height="{size}">'
            f'{svg_content}</svg>'
        )

        renderer = QSvgRenderer(QByteArray(svg_doc.encode('utf-8')))
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()

        _cache[key] = pm
        return pm

    @staticmethod
    def icon(name: str, size: int = 16, color: str = '') -> QIcon:
        """返回命名图标的 QIcon。"""
        return QIcon(IconProvider.pixmap(name, size, color))

    @staticmethod
    def themed_icon(name: str, size: int = 16) -> QIcon:
        """返回使用主题前景色的图标。"""
        return IconProvider.icon(name, size, _theme_fg)

    @staticmethod
    def accent_icon(name: str, size: int = 16) -> QIcon:
        """返回使用主题强调色的图标。"""
        return IconProvider.icon(name, size, _theme_accent)

    @staticmethod
    def muted_icon(name: str, size: int = 16) -> QIcon:
        """返回使用主题弱化色的图标。"""
        return IconProvider.icon(name, size, _theme_muted)
