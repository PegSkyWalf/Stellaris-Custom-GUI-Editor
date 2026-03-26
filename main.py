"""
群星 GUI 编辑器 — 主入口。
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 1. 初始化日志系统（最先运行，确保后续所有模块都可以记录日志）──────────
from src.core.logger import setup as _setup_logger, install_global_exception_handler
from src.core.settings import AppSettings

_settings = AppSettings.instance()
_setup_logger(_settings.log_level)
install_global_exception_handler()

from src.core.logger import get_logger
_log = get_logger('main')

# ── 2. Qt 高 DPI 支持（必须在创建 QApplication 之前设置）─────────────────
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

# ── 3. 创建 QApplication ─────────────────────────────────────────────────
from src.core.__version__ import APP_NAME_EN, VERSION

app = QApplication(sys.argv)
app.setApplicationName(APP_NAME_EN)
app.setOrganizationName('StellarisModding')
app.setApplicationVersion(VERSION)

# ── 3b. 应用图标（任务栏 + 窗口标题栏）──────────────────────────────────
from PySide6.QtGui import QIcon

_ROOT = os.path.dirname(os.path.abspath(__file__))
_icon_path = os.path.join(_ROOT, 'assets', 'app_icon.ico')

# Auto-generate a placeholder icon if none exists yet
if not os.path.isfile(_icon_path):
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            'create_icon',
            os.path.join(_ROOT, 'packaging', 'create_icon.py'),
        )
        if _spec and _spec.loader:
            _ci = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_ci)
            _ci.create_placeholder_icon()
    except Exception as _e:
        _log.warning("占位图标生成失败: %s", _e)

if os.path.isfile(_icon_path):
    app.setWindowIcon(QIcon(_icon_path))
    _log.info("已设置应用图标: %s", _icon_path)
else:
    _log.warning("未找到应用图标文件: %s", _icon_path)

# ── 4. 应用主题（从设置读取，真正生效）──────────────────────────────────
from src.core.theme_manager import ThemeManager

theme = _settings.theme or 'dark'
accent = _settings.accent_color or None
ThemeManager.apply(app, theme, accent)
_log.info("已应用主题: %s (强调色: %s)", theme, accent or '默认')

# ── 5. 首次启动向导（game_dir 为空 或 first_run=True）────────────────────
def _maybe_show_welcome():
    if _settings.first_run or not _settings.game_dir:
        from src.ui.welcome_dialog import WelcomeDialog
        _log.info("显示首次启动向导")
        dlg = WelcomeDialog()
        dlg.exec()
        # 向导保存设置后，重新应用用户选择的主题
        new_theme = _settings.theme or 'dark'
        new_accent = _settings.accent_color or None
        if new_theme != theme or new_accent != accent:
            ThemeManager.apply(app, new_theme, new_accent)

# ── 6. 主窗口 ─────────────────────────────────────────────────────────────
def main():
    _log.info("=== %s v%s 启动 ===", APP_NAME_EN, VERSION)

    _maybe_show_welcome()

    from src.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    _log.info("主窗口已显示，进入事件循环")
    code = app.exec()
    _log.info("应用退出，退出码: %d", code)
    sys.exit(code)


if __name__ == '__main__':
    main()
