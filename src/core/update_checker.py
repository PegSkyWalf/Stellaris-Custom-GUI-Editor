"""
自动更新检查器。

通过 GitHub Releases API 获取最新版本信息，与当前版本比较，
在有新版本时通知 UI 层。网络请求在后台线程中执行，不阻塞界面。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QThread, Signal

from .__version__ import VERSION_TUPLE, GITHUB_URL

_API_URL = 'https://api.github.com/repos/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases/latest'
_TIMEOUT = 8  # 秒


def _parse_version(tag: str) -> tuple:
    """将 'v1.3.2' 或 '1.3.2' 解析为 (1, 3, 2)。解析失败返回 (0, 0, 0)。"""
    tag = tag.lstrip('v').strip()
    try:
        parts = tuple(int(x) for x in tag.split('.')[:3])
        # 补齐至三元组
        return parts + (0,) * (3 - len(parts))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _fetch_latest_release() -> Optional[dict]:
    """
    同步请求 GitHub API，返回解析后的 release 信息字典，失败返回 None。

    返回字典格式：
        {
            'tag':     str,   # e.g. 'v1.4.0'
            'version': tuple, # e.g. (1, 4, 0)
            'name':    str,   # Release 标题
            'body':    str,   # Release Notes（Markdown）
            'url':     str,   # Release 页面 URL
            'date':    str,   # 发布日期 'YYYY-MM-DD'
        }
    """
    try:
        req = urllib.request.Request(
            _API_URL,
            headers={
                'User-Agent': 'StellarisGUIEditor-UpdateChecker',
                'Accept': 'application/vnd.github+json',
            }
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        tag = data.get('tag_name', '')
        published = data.get('published_at', '')
        date_str = ''
        if published:
            try:
                dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                date_str = dt.astimezone(timezone.utc).strftime('%Y-%m-%d')
            except Exception:
                date_str = published[:10]

        return {
            'tag':     tag,
            'version': _parse_version(tag),
            'name':    data.get('name', tag),
            'body':    data.get('body', ''),
            'url':     data.get('html_url', f'{GITHUB_URL}/releases/latest'),
            'date':    date_str,
        }
    except Exception:
        return None


class UpdateCheckThread(QThread):
    """
    在后台线程中检查更新。

    Signals
    -------
    update_available(dict)
        有新版本时发射，payload 为 _fetch_latest_release() 返回的字典。
    no_update()
        当前已是最新版本时发射。
    check_failed()
        网络不可用或解析失败时发射（静默，不向用户报错）。
    """
    update_available = Signal(dict)
    no_update = Signal()
    check_failed = Signal()

    def __init__(self, skip_version: str = '', parent=None):
        super().__init__(parent)
        self._skip_version = _parse_version(skip_version) if skip_version else (0, 0, 0)

    def run(self):
        info = _fetch_latest_release()
        if info is None:
            self.check_failed.emit()
            return

        latest = info['version']
        if latest <= (0, 0, 0):
            self.check_failed.emit()
            return

        # 用户选择跳过的版本
        if self._skip_version and latest <= self._skip_version:
            self.no_update.emit()
            return

        if latest > VERSION_TUPLE:
            self.update_available.emit(info)
        else:
            self.no_update.emit()
