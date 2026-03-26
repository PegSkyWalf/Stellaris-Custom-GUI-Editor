"""
应用日志系统。

日志同时写入：
  - 旋转文件（~/.stellaris_gui_editor/logs/，保留 5 个历史文件）
  - 控制台（仅 DEBUG 模式下可见）

用法：
    from src.core.logger import get_logger
    log = get_logger(__name__)
    log.info("已加载精灵图 %d 个", count)
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_LOG_DIR = Path.home() / '.stellaris_gui_editor' / 'logs'
_LOG_FILE = _LOG_DIR / 'stellaris_gui_editor.log'
_MAX_BYTES = 2 * 1024 * 1024   # 2 MB per file
_BACKUP_COUNT = 4               # 保留 4 个旧文件（共 5 个）

_initialized = False
_root_logger: Optional[logging.Logger] = None


def setup(log_level: str = 'INFO') -> None:
    """
    初始化日志系统。应在 main() 最开始调用一次。

    Parameters
    ----------
    log_level : str
        日志级别，可选 'DEBUG' / 'INFO' / 'WARNING' / 'ERROR'
    """
    global _initialized, _root_logger
    if _initialized:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt='%(asctime)s  %(levelname)-8s  %(name)s  —  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    root = logging.getLogger('stellaris_gui_editor')
    root.setLevel(logging.DEBUG)

    # 文件处理器：始终记录 DEBUG 及以上
    try:
        fh = RotatingFileHandler(
            _LOG_FILE,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding='utf-8',
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except Exception as exc:
        print(f"[logger] 无法创建日志文件: {exc}", file=sys.stderr)

    # 控制台处理器：仅 DEBUG 级别（生产打包时 console=False 不显示）
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    root.propagate = False
    _root_logger = root
    _initialized = True

    root.info("=== 群星 GUI 编辑器 启动 ===  日志文件: %s", _LOG_FILE)


def get_logger(name: str) -> logging.Logger:
    """
    获取命名子日志器。

    Parameters
    ----------
    name : str
        通常传入 __name__，如 'src.core.resource_manager'
    """
    if not _initialized:
        setup()
    return logging.getLogger(f'stellaris_gui_editor.{name}')


def get_log_dir() -> Path:
    """返回日志目录路径（供设置界面打开文件夹使用）。"""
    return _LOG_DIR


def install_global_exception_handler() -> None:
    """
    将未捕获异常重定向到日志文件。
    在 main() 中调用一次，确保崩溃信息可被用户提交 Bug。
    """
    log = get_logger('crash')

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.critical("未捕获的异常:\n%s", tb_text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook
