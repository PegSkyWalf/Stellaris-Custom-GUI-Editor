"""
主题管理器 — 为应用提供可切换的视觉主题。

内置主题：
  dark       深色（默认，与原版一致）
  light      浅色（高亮环境友好）
  dark_blue  深蓝（专业感更强）

用法：
    from src.core.theme_manager import ThemeManager
    ThemeManager.apply(app, 'dark')
    ThemeManager.apply(app, 'light', accent='#2ecc71')
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# 主题定义：每项包含 palette 颜色 + stylesheet 字符串
# ---------------------------------------------------------------------------

def _build_dark_palette(accent: str = '#4a9fd4') -> QPalette:
    p = QPalette()
    a = QColor(accent)
    p.setColor(QPalette.ColorRole.Window,          QColor(30, 30, 30))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(20, 20, 20))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(50, 50, 50))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(30, 30, 30))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Button,          QColor(50, 50, 50))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link,            a)
    p.setColor(QPalette.ColorRole.Highlight,       a)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor(100, 100, 100))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(100, 100, 100))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(100, 100, 100))
    return p


def _build_light_palette(accent: str = '#0e639c') -> QPalette:
    p = QPalette()
    a = QColor(accent)
    p.setColor(QPalette.ColorRole.Window,          QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(20, 20, 20))
    p.setColor(QPalette.ColorRole.Base,            QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(225, 225, 225))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(255, 255, 220))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.Text,            QColor(20, 20, 20))
    p.setColor(QPalette.ColorRole.Button,          QColor(225, 225, 225))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(20, 20, 20))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.Link,            a)
    p.setColor(QPalette.ColorRole.Highlight,       a)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor(150, 150, 150))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(150, 150, 150))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(150, 150, 150))
    return p


def _build_dark_blue_palette(accent: str = '#5bc0de') -> QPalette:
    p = QPalette()
    a = QColor(accent)
    p.setColor(QPalette.ColorRole.Window,          QColor(18, 26, 40))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(200, 215, 235))
    p.setColor(QPalette.ColorRole.Base,            QColor(10, 16, 28))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(28, 40, 60))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(18, 26, 40))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(200, 215, 235))
    p.setColor(QPalette.ColorRole.Text,            QColor(200, 215, 235))
    p.setColor(QPalette.ColorRole.Button,          QColor(28, 40, 60))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(200, 215, 235))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link,            a)
    p.setColor(QPalette.ColorRole.Highlight,       a)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(10, 16, 28))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor(80, 100, 130))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(80, 100, 130))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(80, 100, 130))
    return p


def _dark_qss(accent: str = '#4a9fd4') -> str:
    return f'''
        QToolTip {{color:#ddd; background:#2a2a2a; border:1px solid #555;}}
        QDockWidget::title {{background:#2d2d2d; padding:4px; font-weight:bold;}}
        QTabBar::tab {{background:#2d2d2d; color:#bbb; padding:4px 10px; border:1px solid #444;}}
        QTabBar::tab:selected {{background:#3d3d3d; color:#fff; border-bottom:2px solid {accent};}}
        QTreeWidget, QListWidget {{background:#1e1e1e; alternate-background-color:#252525; border:1px solid #333;}}
        QScrollBar:vertical {{background:#2d2d2d; width:12px;}}
        QScrollBar::handle:vertical {{background:#555; border-radius:4px; min-height:20px;}}
        QScrollBar:horizontal {{background:#2d2d2d; height:12px;}}
        QScrollBar::handle:horizontal {{background:#555; border-radius:4px; min-width:20px;}}
        QGroupBox {{border:1px solid #444; margin-top:8px;}}
        QGroupBox::title {{color:#aaa;}}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{background:#2d2d2d; border:1px solid #444; padding:2px; color:#ddd;}}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{border:1px solid {accent};}}
        QPushButton {{background:#3d3d3d; border:1px solid #555; padding:4px 8px; color:#ddd;}}
        QPushButton:hover {{background:#4d4d4d; border:1px solid {accent};}}
        QPushButton:pressed {{background:#2d2d2d;}}
        QStatusBar {{background:#1a1a1a; color:#888;}}
        QMenuBar {{background:#252525;}}
        QMenuBar::item:selected {{background:#3d3d3d;}}
        QMenu {{background:#2d2d2d; border:1px solid #444;}}
        QMenu::item:selected {{background:{accent}; color:#fff;}}
        QToolBar {{background:#252525; border-bottom:1px solid #333; spacing:2px;}}
        QTextEdit {{background:#1e1e1e; color:#d4d4d4; border:1px solid #3c3c3c;}}
        QPlainTextEdit {{background:#1e1e1e; color:#d4d4d4; border:1px solid #3c3c3c;}}
        QLabel#sprite_preview {{background:#2a2a2a; border:1px solid #444;}}
        QWidget#gui_selector_bar {{background:#252526; border-bottom:1px solid #3c3c3c;}}
    '''


def _light_qss(accent: str = '#0e639c') -> str:
    return f'''
        QToolTip {{color:#333; background:#ffffc0; border:1px solid #aaa;}}
        QDockWidget::title {{background:#e0e0e0; padding:4px; font-weight:bold;}}
        QTabBar::tab {{background:#e0e0e0; color:#333; padding:4px 10px; border:1px solid #bbb;}}
        QTabBar::tab:selected {{background:#fff; color:#000; border-bottom:2px solid {accent};}}
        QTreeWidget, QListWidget {{background:#fff; alternate-background-color:#f5f5f5; border:1px solid #ccc;}}
        QScrollBar:vertical {{background:#e0e0e0; width:12px;}}
        QScrollBar::handle:vertical {{background:#aaa; border-radius:4px; min-height:20px;}}
        QScrollBar:horizontal {{background:#e0e0e0; height:12px;}}
        QScrollBar::handle:horizontal {{background:#aaa; border-radius:4px; min-width:20px;}}
        QGroupBox {{border:1px solid #ccc; margin-top:8px;}}
        QGroupBox::title {{color:#555;}}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{background:#fff; border:1px solid #bbb; padding:2px; color:#222;}}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{border:1px solid {accent};}}
        QPushButton {{background:#e8e8e8; border:1px solid #bbb; padding:4px 8px; color:#222;}}
        QPushButton:hover {{background:#d0d0d0; border:1px solid {accent};}}
        QPushButton:pressed {{background:#c0c0c0;}}
        QStatusBar {{background:#f0f0f0; color:#555;}}
        QMenuBar {{background:#e8e8e8;}}
        QMenuBar::item:selected {{background:#d0d0d0;}}
        QMenu {{background:#f0f0f0; border:1px solid #bbb;}}
        QMenu::item:selected {{background:{accent}; color:#fff;}}
        QToolBar {{background:#e8e8e8; border-bottom:1px solid #ccc; spacing:2px;}}
        QTextEdit {{background:#ffffff; color:#1e1e1e; border:1px solid #cccccc;}}
        QPlainTextEdit {{background:#ffffff; color:#1e1e1e; border:1px solid #cccccc;}}
        QLabel#sprite_preview {{background:#e8e8e8; border:1px solid #bbb;}}
        QWidget#gui_selector_bar {{background:#e8e8e8; border-bottom:1px solid #ccc;}}
    '''


def _dark_blue_qss(accent: str = '#5bc0de') -> str:
    return f'''
        QToolTip {{color:#c8d7eb; background:#12203a; border:1px solid #3a5880;}}
        QDockWidget::title {{background:#1a2d4a; padding:4px; font-weight:bold;}}
        QTabBar::tab {{background:#1a2d4a; color:#8aadcf; padding:4px 10px; border:1px solid #2a4060;}}
        QTabBar::tab:selected {{background:#243d60; color:#c8d7eb; border-bottom:2px solid {accent};}}
        QTreeWidget, QListWidget {{background:#0a101c; alternate-background-color:#12203a; border:1px solid #1e3050;}}
        QScrollBar:vertical {{background:#1a2d4a; width:12px;}}
        QScrollBar::handle:vertical {{background:#3a5880; border-radius:4px; min-height:20px;}}
        QScrollBar:horizontal {{background:#1a2d4a; height:12px;}}
        QScrollBar::handle:horizontal {{background:#3a5880; border-radius:4px; min-width:20px;}}
        QGroupBox {{border:1px solid #2a4060; margin-top:8px;}}
        QGroupBox::title {{color:#8aadcf;}}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{background:#1a2d4a; border:1px solid #2a4060; padding:2px; color:#c8d7eb;}}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{border:1px solid {accent};}}
        QPushButton {{background:#1e3050; border:1px solid #3a5880; padding:4px 8px; color:#c8d7eb;}}
        QPushButton:hover {{background:#2a4060; border:1px solid {accent};}}
        QPushButton:pressed {{background:#12203a;}}
        QStatusBar {{background:#0a101c; color:#6a8aaf;}}
        QMenuBar {{background:#12203a;}}
        QMenuBar::item:selected {{background:#1e3050;}}
        QMenu {{background:#1a2d4a; border:1px solid #2a4060;}}
        QMenu::item:selected {{background:{accent}; color:#0a101c;}}
        QToolBar {{background:#12203a; border-bottom:1px solid #1e3050; spacing:2px;}}
        QTextEdit {{background:#0d1a2a; color:#cdd6e0; border:1px solid #1e3a5a;}}
        QPlainTextEdit {{background:#0d1a2a; color:#cdd6e0; border:1px solid #1e3a5a;}}
        QLabel#sprite_preview {{background:#12203a; border:1px solid #2a4060;}}
        QWidget#gui_selector_bar {{background:#12203a; border-bottom:1px solid #1e3050;}}
    '''


def is_dark_theme(theme: str) -> bool:
    """Returns True for dark-background themes (dark, dark_blue)."""
    return theme != 'light'


# ---------------------------------------------------------------------------
# 主题注册表
# ---------------------------------------------------------------------------

AVAILABLE_THEMES: Dict[str, Tuple[str, str]] = {
    'dark':      ('深色（默认）',  '#4a9fd4'),
    'light':     ('浅色',         '#0e639c'),
    'dark_blue': ('深海蓝',        '#5bc0de'),
}

DEFAULT_THEME = 'dark'


class ThemeManager:
    """静态工具类，负责将主题应用到 QApplication。"""

    @staticmethod
    def apply(app: QApplication, theme: str = DEFAULT_THEME,
              accent: Optional[str] = None) -> None:
        """
        将指定主题应用到整个应用程序。

        Parameters
        ----------
        app    : QApplication 实例
        theme  : 主题名称，可选 'dark' / 'light' / 'dark_blue'
        accent : 可选的强调色十六进制字符串，覆盖主题默认值
        """
        app.setStyle('Fusion')

        _, default_accent = AVAILABLE_THEMES.get(theme, AVAILABLE_THEMES[DEFAULT_THEME])
        effective_accent = accent or default_accent

        if theme == 'light':
            palette = _build_light_palette(effective_accent)
            qss = _light_qss(effective_accent)
        elif theme == 'dark_blue':
            palette = _build_dark_blue_palette(effective_accent)
            qss = _dark_blue_qss(effective_accent)
        else:
            palette = _build_dark_palette(effective_accent)
            qss = _dark_qss(effective_accent)

        app.setPalette(palette)
        app.setStyleSheet(qss)

    @staticmethod
    def theme_display_name(theme: str) -> str:
        """返回主题的中文显示名称。"""
        return AVAILABLE_THEMES.get(theme, (theme, ''))[0]

    @staticmethod
    def default_accent(theme: str) -> str:
        """返回主题的默认强调色。"""
        return AVAILABLE_THEMES.get(theme, AVAILABLE_THEMES[DEFAULT_THEME])[1]
