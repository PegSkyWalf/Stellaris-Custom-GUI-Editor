"""
应用设置管理。
持久化用户偏好（游戏路径、最近文件、主题等）至 JSON 文件。

设置文件位置：~/.stellaris_gui_editor/settings.json
"""
import json
import os
import sys
from pathlib import Path
from typing import List, Optional


SETTINGS_FILE = Path.home() / '.stellaris_gui_editor' / 'settings.json'

_DEFAULTS = {
    # 路径
    'game_dir': '',
    'last_mod_dir': '',
    'last_open_dir': '',
    'extra_mod_dirs': [],
    'recent_files': [],
    'recent_mod_dirs': [],
    'workspace_folders': [],

    # 画布
    'canvas_width': 1920,
    'canvas_height': 1080,
    'show_grid': True,
    'grid_size': 8,
    'snap_to_grid': True,
    'show_editor_scrollbars': True,

    # 外观
    'theme': 'dark',
    'accent_color': '',        # 留空 = 使用主题默认强调色
    'font_size': 10,

    # 编辑器行为
    'undo_limit': 100,
    'autosave_interval_sec': 60,
    'code_font': 'Consolas',
    'code_font_size': 10,

    # 智能吸附
    'smart_snap_enabled': True,
    'smart_snap_threshold': 5,     # 像素阈值 (1-20)
    'snap_to_edges': True,
    'snap_to_centers': True,
    'snap_to_spacing': True,

    # 语言
    'ui_language': 'zh_CN',    # UI 显示语言，BCP-47 代码

    # 高级
    'log_level': 'INFO',
    'first_run': True,         # 控制是否显示首次启动向导

    # 预设（内部使用）
    'presets': {},

    # 更新检查
    'check_update_on_startup': True,
    'last_update_check': '',    # ISO 日期字符串，如 '2026-04-04'
    'skip_version': '',         # 用户选择跳过的版本号，如 'v1.4.0'
    'update_check_interval_days': 1,
}


class AppSettings:
    _instance: Optional['AppSettings'] = None

    def __init__(self):
        self._data = dict(_DEFAULTS)
        self._load()

    @classmethod
    def instance(cls) -> 'AppSettings':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                # 只合并已知键，防止旧版本脏数据覆盖新默认值
                for k, v in saved.items():
                    self._data[k] = v
            except Exception:
                pass

    def save(self):
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, default if default is not None else _DEFAULTS.get(key))

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    # ------------------------------------------------------------------
    # 路径属性
    # ------------------------------------------------------------------

    @property
    def game_dir(self) -> str:
        return self._data.get('game_dir', '')

    @game_dir.setter
    def game_dir(self, path: str):
        self._data['game_dir'] = path
        self.save()

    @property
    def last_mod_dir(self) -> str:
        return self._data.get('last_mod_dir', '')

    @last_mod_dir.setter
    def last_mod_dir(self, v: str):
        self._data['last_mod_dir'] = v
        self.save()

    @property
    def extra_mod_dirs(self) -> list:
        return list(self._data.get('extra_mod_dirs', []))

    @extra_mod_dirs.setter
    def extra_mod_dirs(self, v: list):
        self._data['extra_mod_dirs'] = list(v)
        self.save()

    @property
    def recent_files(self) -> List[str]:
        return self._data.get('recent_files', [])

    def add_recent_file(self, path: str):
        files = self.recent_files
        if path in files:
            files.remove(path)
        files.insert(0, path)
        self._data['recent_files'] = files[:20]
        self.save()

    @property
    def recent_mod_dirs(self) -> List[str]:
        return self._data.get('recent_mod_dirs', [])

    def add_recent_mod_dir(self, path: str):
        dirs = self.recent_mod_dirs
        if path in dirs:
            dirs.remove(path)
        dirs.insert(0, path)
        self._data['recent_mod_dirs'] = dirs[:10]
        self.save()

    # ------------------------------------------------------------------
    # 工作区
    # ------------------------------------------------------------------

    @property
    def workspace_folders(self) -> list:
        return list(self._data.get('workspace_folders', []))

    @workspace_folders.setter
    def workspace_folders(self, v: list):
        self._data['workspace_folders'] = list(v)
        self.save()

    def add_workspace_folder(self, path: str, name: str = ''):
        folders = self.workspace_folders
        for f in folders:
            if f.get('path') == path:
                f['name'] = name or f.get('name', os.path.basename(path))
                f['enabled'] = True
                self.workspace_folders = folders
                return
        folders.append({
            'path': path,
            'name': name or os.path.basename(path),
            'enabled': True,
        })
        self.workspace_folders = folders

    def remove_workspace_folder(self, path: str):
        folders = [f for f in self.workspace_folders if f.get('path') != path]
        self.workspace_folders = folders

    # ------------------------------------------------------------------
    # 画布
    # ------------------------------------------------------------------

    @property
    def canvas_size(self):
        return (self._data.get('canvas_width', 1920),
                self._data.get('canvas_height', 1080))

    @canvas_size.setter
    def canvas_size(self, value):
        self._data['canvas_width'] = value[0]
        self._data['canvas_height'] = value[1]
        self.save()

    @property
    def show_grid(self) -> bool:
        return bool(self._data.get('show_grid', True))

    @show_grid.setter
    def show_grid(self, v: bool):
        self._data['show_grid'] = v
        self.save()

    @property
    def grid_size(self) -> int:
        return int(self._data.get('grid_size', 8))

    @grid_size.setter
    def grid_size(self, v: int):
        self._data['grid_size'] = v
        self.save()

    @property
    def snap_to_grid(self) -> bool:
        return bool(self._data.get('snap_to_grid', True))

    @snap_to_grid.setter
    def snap_to_grid(self, v: bool):
        self._data['snap_to_grid'] = v
        self.save()

    @property
    def show_editor_scrollbars(self) -> bool:
        return bool(self._data.get('show_editor_scrollbars', True))

    @show_editor_scrollbars.setter
    def show_editor_scrollbars(self, v: bool):
        self._data['show_editor_scrollbars'] = v
        self.save()

    # ------------------------------------------------------------------
    # 外观
    # ------------------------------------------------------------------

    @property
    def theme(self) -> str:
        return str(self._data.get('theme', 'dark'))

    @theme.setter
    def theme(self, v: str):
        self._data['theme'] = v
        self.save()

    @property
    def accent_color(self) -> str:
        return str(self._data.get('accent_color', ''))

    @accent_color.setter
    def accent_color(self, v: str):
        self._data['accent_color'] = v
        self.save()

    @property
    def font_size(self) -> int:
        return int(self._data.get('font_size', 10))

    @font_size.setter
    def font_size(self, v: int):
        self._data['font_size'] = v
        self.save()

    # ------------------------------------------------------------------
    # 编辑器行为
    # ------------------------------------------------------------------

    @property
    def undo_limit(self) -> int:
        return int(self._data.get('undo_limit', 100))

    @undo_limit.setter
    def undo_limit(self, v: int):
        self._data['undo_limit'] = max(10, min(500, int(v)))
        self.save()

    @property
    def autosave_interval_sec(self) -> int:
        return int(self._data.get('autosave_interval_sec', 60))

    @autosave_interval_sec.setter
    def autosave_interval_sec(self, v: int):
        self._data['autosave_interval_sec'] = max(10, int(v))
        self.save()

    @property
    def code_font(self) -> str:
        return str(self._data.get('code_font', 'Consolas'))

    @code_font.setter
    def code_font(self, v: str):
        self._data['code_font'] = v
        self.save()

    @property
    def code_font_size(self) -> int:
        return int(self._data.get('code_font_size', 10))

    @code_font_size.setter
    def code_font_size(self, v: int):
        self._data['code_font_size'] = v
        self.save()

    # ------------------------------------------------------------------
    # 智能吸附
    # ------------------------------------------------------------------

    @property
    def smart_snap_enabled(self) -> bool:
        return bool(self._data.get('smart_snap_enabled', True))

    @smart_snap_enabled.setter
    def smart_snap_enabled(self, v: bool):
        self._data['smart_snap_enabled'] = v
        self.save()

    @property
    def smart_snap_threshold(self) -> int:
        return int(self._data.get('smart_snap_threshold', 5))

    @smart_snap_threshold.setter
    def smart_snap_threshold(self, v: int):
        self._data['smart_snap_threshold'] = max(1, min(20, int(v)))
        self.save()

    @property
    def snap_to_edges(self) -> bool:
        return bool(self._data.get('snap_to_edges', True))

    @snap_to_edges.setter
    def snap_to_edges(self, v: bool):
        self._data['snap_to_edges'] = v
        self.save()

    @property
    def snap_to_centers(self) -> bool:
        return bool(self._data.get('snap_to_centers', True))

    @snap_to_centers.setter
    def snap_to_centers(self, v: bool):
        self._data['snap_to_centers'] = v
        self.save()

    @property
    def snap_to_spacing(self) -> bool:
        return bool(self._data.get('snap_to_spacing', True))

    @snap_to_spacing.setter
    def snap_to_spacing(self, v: bool):
        self._data['snap_to_spacing'] = v
        self.save()

    # ------------------------------------------------------------------
    # 高级
    # ------------------------------------------------------------------

    @property
    def log_level(self) -> str:
        return str(self._data.get('log_level', 'INFO'))

    @log_level.setter
    def log_level(self, v: str):
        self._data['log_level'] = v
        self.save()

    @property
    def first_run(self) -> bool:
        return bool(self._data.get('first_run', True))

    @first_run.setter
    def first_run(self, v: bool):
        self._data['first_run'] = v
        self.save()

    # ------------------------------------------------------------------
    # 游戏目录自动检测（跨平台 + 注册表）
    # ------------------------------------------------------------------

    def detect_game_dir(self) -> str:
        """
        尝试自动检测群星游戏安装目录。

        检测顺序：
          1. Windows：Steam 注册表（最可靠）
          2. Windows：扫描所有盘符下的常见 Steam 路径
          3. macOS：~/Library/Application Support/Steam/...
          4. Linux：~/.steam / ~/.local/share/Steam / Snap 路径
          5. Paradox Launcher 相关路径

        Returns
        -------
        str
            找到的路径，若未找到则返回空字符串。
        """
        candidates = []

        # ── Windows：注册表 ──────────────────────────────────────────────
        if sys.platform == 'win32':
            candidates.extend(self._detect_steam_windows_registry())
            # 再扫描所有盘符
            for drive_letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                drive = f'{drive_letter}:\\'
                if not os.path.isdir(drive):
                    continue
                candidates.extend([
                    os.path.join(drive, 'Steam', 'steamapps', 'common', 'Stellaris'),
                    os.path.join(drive, 'SteamLibrary', 'steamapps', 'common', 'Stellaris'),
                    os.path.join(drive, 'Games', 'Steam', 'steamapps', 'common', 'Stellaris'),
                    os.path.join(drive, 'Program Files (x86)', 'Steam', 'steamapps', 'common', 'Stellaris'),
                    os.path.join(drive, 'Program Files', 'Steam', 'steamapps', 'common', 'Stellaris'),
                ])

        # ── macOS ─────────────────────────────────────────────────────────
        elif sys.platform == 'darwin':
            home = os.path.expanduser('~')
            candidates.extend([
                os.path.join(home, 'Library', 'Application Support', 'Steam',
                             'steamapps', 'common', 'Stellaris'),
                '/Applications/Stellaris.app/Contents/Resources',
            ])

        # ── Linux ─────────────────────────────────────────────────────────
        else:
            home = os.path.expanduser('~')
            candidates.extend([
                os.path.join(home, '.steam', 'steam', 'steamapps', 'common', 'Stellaris'),
                os.path.join(home, '.local', 'share', 'Steam', 'steamapps', 'common', 'Stellaris'),
                '/usr/share/steam/steamapps/common/Stellaris',
                # Snap Steam
                os.path.join(home, 'snap', 'steam', 'common', '.local', 'share', 'Steam',
                             'steamapps', 'common', 'Stellaris'),
                # Flatpak Steam
                os.path.join(home, '.var', 'app', 'com.valvesoftware.Steam',
                             '.local', 'share', 'Steam', 'steamapps', 'common', 'Stellaris'),
            ])

        for p in candidates:
            if p and os.path.isdir(p):
                # 确认是 Stellaris 目录（应有 interface/ 子目录）
                if os.path.isdir(os.path.join(p, 'interface')):
                    return p

        return ''

    @staticmethod
    def _detect_steam_windows_registry() -> List[str]:
        """
        从 Windows 注册表读取 Steam 安装路径，
        再结合 libraryfolders.vdf 找到所有库位置。
        """
        results = []
        try:
            import winreg
            key_paths = [
                r'SOFTWARE\Valve\Steam',
                r'SOFTWARE\WOW6432Node\Valve\Steam',
            ]
            for key_path in key_paths:
                for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        key = winreg.OpenKey(hive, key_path)
                        steam_path, _ = winreg.QueryValueEx(key, 'InstallPath')
                        winreg.CloseKey(key)
                        if steam_path and os.path.isdir(steam_path):
                            # 默认库
                            default = os.path.join(
                                steam_path, 'steamapps', 'common', 'Stellaris')
                            results.append(default)
                            # 解析 libraryfolders.vdf 获取额外库
                            vdf_path = os.path.join(
                                steam_path, 'steamapps', 'libraryfolders.vdf')
                            results.extend(
                                AppSettings._parse_library_folders(vdf_path))
                    except (FileNotFoundError, OSError, Exception):
                        continue
        except ImportError:
            pass
        return results

    @staticmethod
    def _parse_library_folders(vdf_path: str) -> List[str]:
        """
        简单解析 libraryfolders.vdf 提取额外 Steam 库路径。
        每个库路径下查找 Stellaris。
        """
        results = []
        if not os.path.isfile(vdf_path):
            return results
        try:
            with open(vdf_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            import re
            # 匹配 "path"  "X:\SteamLibrary" 形式
            for m in re.finditer(r'"path"\s+"([^"]+)"', content):
                lib_path = m.group(1).replace('\\\\', '\\')
                stellaris = os.path.join(lib_path, 'steamapps', 'common', 'Stellaris')
                results.append(stellaris)
        except Exception:
            pass
        return results
