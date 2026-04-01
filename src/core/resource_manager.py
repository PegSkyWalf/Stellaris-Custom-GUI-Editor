"""
Resource Manager for Stellaris GUI Editor.

Loads and indexes all GUI-related resources from:
  1. Vanilla game directory (read-only base)
  2. Active mod directory (read-write, overrides vanilla)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .logger import get_logger
_log = get_logger('resource_manager')

from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QRect

from .pdx_parser import parse_file, ParseError, pairs_to_dict

# pydds：正式依赖，随 requirements / 安装包提供；先于 Pillow 解码 DDS，避免 BC7 等被误解析花屏
try:
    from dds import decode_dds as _PYDDS_DECODE_BYTES
except ImportError:
    _PYDDS_DECODE_BYTES = None


class SpriteInfo:
    """Holds information about a registered sprite."""
    def __init__(
        self,
        name: str,
        texture_path: str,
        sprite_type: str = 'spriteType',
        no_of_frames: int = 1,
        border_size: Tuple[int, int] = (0, 0),
        width: int = 0,
        height: int = 0,
    ):
        self.name = name
        self.texture_path = texture_path
        self.sprite_type = sprite_type
        self.no_of_frames = max(1, no_of_frames)
        self.border_size = border_size
        # Natural pixel dimensions (set after loading image)
        self.natural_width = width
        self.natural_height = height
        self._priority = 0

    def is_scalable(self) -> bool:
        """True if this sprite stretches to fit size (corneredTileSpriteType)."""
        return self.sprite_type in ('corneredTileSpriteType', 'textSpriteType')

    def natural_size(self) -> Tuple[int, int]:
        """Natural single-frame size in pixels."""
        return (self.natural_width, self.natural_height)

    def __repr__(self):
        return f'SpriteInfo({self.name!r}, {self.texture_path!r})'


class ResourceManager:
    """
    Singleton resource manager.
    Call load_game_dir() and optionally load_mod_dir() / load_extra_mod_dir() before use.
    """
    _instance: Optional['ResourceManager'] = None

    def __init__(self):
        self.game_dir: str = ''
        self.mod_dir: str = ''
        self._extra_mod_dirs: List[str] = []   # additional dependency mods
        self._sprites: Dict[str, SpriteInfo] = {}
        self._pixmap_cache: Dict[str, QPixmap] = {}
        self._size_cache: Dict[str, Tuple[int, int]] = {}
        self._loc: Dict[str, str] = {}
        # Per-language loc storage: lang_code → {key → value}
        self._loc_by_lang: Dict[str, Dict[str, str]] = {}
        self._active_language: str = 'english'
        self._available_languages: List[str] = []
        self._gui_files: Dict[str, str] = {}
        self._gfx_files: Dict[str, str] = {}
        # Event data: custom_gui_name → [EventInfo, ...]
        self._events: Dict[str, List] = {}
        # Top-level GUI index: gui_name → (file_path, WidgetNode) — populated lazily
        self._top_level_gui_index: Dict[str, Tuple[str, object]] = {}
        self._gui_index_built: bool = False
        # Scrollbar definition index: scrollbar_name → WidgetNode — populated lazily
        self._scrollbar_index: Dict[str, object] = {}
        # Resolved room image path cache (strict decode success)
        self._room_file_cache: Dict[str, str] = {}
        # Cached scaled pixmaps for £text_icon£ previews (key → QPixmap)
        self._text_icon_pixmap_cache: Dict[str, 'QPixmap'] = {}
        # Track which dirs have already been event-scanned (lazy scan support)
        self._events_scanned_dirs: Set[str] = set()

    @classmethod
    def instance(cls) -> 'ResourceManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_game_dir(self, game_dir: str, cancel_event: Optional[threading.Event] = None):
        _log.info("开始加载游戏目录: %s", game_dir)
        t0 = time.monotonic()
        self.game_dir = game_dir
        if not os.path.isdir(game_dir):
            _log.warning("游戏目录不存在: %s", game_dir)
            return
        iface_dir = os.path.join(game_dir, 'interface')
        if os.path.isdir(iface_dir):
            self._index_interface_dir(iface_dir, priority=0, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            _log.info("load_game_dir: 在 interface 扫描后收到取消信号")
            return
        self._index_gfx_directory(game_dir, priority=0, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            _log.info("load_game_dir: 在 gfx 扫描后收到取消信号")
            return
        loc_dir = os.path.join(game_dir, 'localisation')
        if os.path.isdir(loc_dir):
            self._load_localisation_dir(loc_dir, cancel_event=cancel_event)
        # 事件扫描已改为懒加载，不在此处调用 _scan_events
        _log.info("游戏目录加载完成: %d 精灵图 / %d 本地化词条，耗时 %.2fs",
                  len(self._sprites), len(self._loc), time.monotonic() - t0)

    def load_mod_dir(self, mod_dir: str, cancel_event: Optional[threading.Event] = None):
        _log.info("开始加载模组目录: %s", mod_dir)
        t0 = time.monotonic()
        self.mod_dir = mod_dir
        if not os.path.isdir(mod_dir):
            _log.warning("模组目录不存在: %s", mod_dir)
            return
        iface_dir = os.path.join(mod_dir, 'interface')
        if os.path.isdir(iface_dir):
            self._index_interface_dir(iface_dir, priority=1, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            _log.info("load_mod_dir: 在 interface 扫描后收到取消信号")
            return
        self._index_gfx_directory(mod_dir, priority=1, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            _log.info("load_mod_dir: 在 gfx 扫描后收到取消信号")
            return
        loc_dir = os.path.join(mod_dir, 'localisation')
        if os.path.isdir(loc_dir):
            self._load_localisation_dir(loc_dir, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            _log.info("load_mod_dir: 在 localisation 扫描后收到取消信号")
            return
        self._detect_available_languages(mod_dir)
        # 事件扫描已改为懒加载，不在此处调用 _scan_events
        _log.info("模组目录加载完成: %d 精灵图 / %d 本地化词条，耗时 %.2fs",
                  len(self._sprites), len(self._loc), time.monotonic() - t0)

    def load_extra_mod_dir(self, extra_mod_dir: str, cancel_event: Optional[threading.Event] = None):
        """
        Load an additional dependency mod for texture/sprite resolution.
        Priority 0.5 — higher than vanilla, lower than the primary mod.
        """
        _log.info("开始加载额外模组目录: %s", extra_mod_dir)
        t0 = time.monotonic()
        if not os.path.isdir(extra_mod_dir):
            _log.warning("额外模组目录不存在: %s", extra_mod_dir)
            return
        if extra_mod_dir not in self._extra_mod_dirs:
            self._extra_mod_dirs.append(extra_mod_dir)
        prio = max(0, len(self._extra_mod_dirs) - 1)
        iface_dir = os.path.join(extra_mod_dir, 'interface')
        if os.path.isdir(iface_dir):
            self._index_interface_dir(iface_dir, priority=prio, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            return
        self._index_gfx_directory(extra_mod_dir, priority=prio, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            return
        loc_dir = os.path.join(extra_mod_dir, 'localisation')
        if os.path.isdir(loc_dir):
            self._load_localisation_dir(loc_dir, cancel_event=cancel_event)
        # 事件扫描已改为懒加载，不在此处调用 _scan_events
        _log.info("额外模组目录加载完成，耗时 %.2fs", time.monotonic() - t0)

    @staticmethod
    def _safe_walk(top: str):
        """
        os.walk 的安全包装：检测 Windows 目录联接点（junction）导致的循环引用。
        通过对比 st_dev + st_ino 避免重复访问同一物理目录。
        """
        seen: Set[tuple] = set()
        for dirpath, dirnames, filenames in os.walk(top):
            try:
                s = os.stat(dirpath)
                key = (s.st_dev, s.st_ino)
            except OSError:
                key = None
            if key is not None:
                if key in seen:
                    _log.warning("检测到循环目录引用（联接点？），跳过: %s", dirpath)
                    dirnames[:] = []  # 阻止 os.walk 继续下降
                    continue
                seen.add(key)
            yield dirpath, dirnames, filenames

    def _index_interface_dir(self, iface_dir: str, priority: int,
                             cancel_event: Optional[threading.Event] = None):
        t0 = time.monotonic()
        gui_count = gfx_count = 0
        _log.debug("扫描 interface 目录: %s", iface_dir)
        for dirpath, dirs, files in self._safe_walk(iface_dir):
            if cancel_event and cancel_event.is_set():
                _log.debug("_index_interface_dir: 收到取消信号，当前目录 %s", dirpath)
                return
            _log.debug("  进入子目录: %s (%d 个文件)", dirpath, len(files))
            for fname in files:
                if cancel_event and cancel_event.is_set():
                    _log.debug("_index_interface_dir: 文件循环中收到取消信号")
                    return
                fpath = os.path.join(dirpath, fname)
                ext = os.path.splitext(fname)[1].lower()
                if ext in ('.gui', '.guicore'):
                    self._gui_files[fname] = fpath
                    gui_count += 1
                elif ext in ('.gfx', '.gfxcore'):
                    _log.debug("    解析 GFX: %s", fname)
                    tf = time.monotonic()
                    self._gfx_files[fname] = fpath
                    self._parse_gfx_file(fpath, priority)
                    elapsed = time.monotonic() - tf
                    if elapsed > 1.0:
                        _log.warning("GFX 解析耗时过长 %.2fs: %s", elapsed, fpath)
                    gfx_count += 1
        _log.debug("interface 扫描完成: %d .gui, %d .gfx，耗时 %.3fs",
                   gui_count, gfx_count, time.monotonic() - t0)

    # Subdirectories under gfx/ that never contain spriteType / corneredTileSpriteType
    # definitions — only 3D models, map data, fonts, etc.  Skipping them avoids
    # hanging on large mesh .gfx files (e.g. protoss_01 with 226 files / multi-MB).
    _GFX_SKIP_SUBDIRS = frozenset({
        'models', 'fonts', 'loadingscreens', 'particles',
        'portraits',   # portrait definitions, not sprite types
        'map',         # map assets
        'holosphere',  # 3D holosphere assets
        'brushes',
        'lasers',
        'projectiles',
        'shields',
        'ships',       # 3D ship assets at root gfx/ships level
        'galaxy',
        'lights',
    })
    _GFX_MAX_FILE_BYTES = 512 * 1024   # 512 KB — sprite defs are never this large

    def _index_gfx_directory(self, root: str, priority: int,
                             cancel_event: Optional[threading.Event] = None):
        """Walk gfx/ for .gfx files so text icons and sprites work when defined outside interface/.
        Skips gfx/models/ and similar directories that only contain 3D mesh definitions."""
        gfx_root = os.path.join(root, 'gfx')
        if not os.path.isdir(gfx_root):
            return
        t0 = time.monotonic()
        gfx_count = dir_count = skip_count = 0
        _log.debug("扫描 gfx 目录: %s", gfx_root)
        for dirpath, dirs, files in self._safe_walk(gfx_root):
            if cancel_event and cancel_event.is_set():
                _log.debug("_index_gfx_directory: 收到取消信号，当前目录 %s", dirpath)
                return
            # Prune subdirectories that never contain sprite type definitions to
            # prevent walking large 3D-model trees that can freeze the parser.
            dirs[:] = [
                d for d in dirs
                if d.lower() not in self._GFX_SKIP_SUBDIRS
            ]
            dir_count += 1
            _log.debug("  gfx 子目录 #%d: %s (%d 个文件)", dir_count, dirpath, len(files))
            for fname in files:
                if cancel_event and cancel_event.is_set():
                    _log.debug("_index_gfx_directory: 文件循环中收到取消信号")
                    return
                ext = os.path.splitext(fname)[1].lower()
                if ext not in ('.gfx', '.gfxcore'):
                    continue
                fpath = os.path.join(dirpath, fname)
                # Skip files that are too large to be sprite definitions
                try:
                    fsize = os.path.getsize(fpath)
                except OSError:
                    fsize = 0
                if fsize > self._GFX_MAX_FILE_BYTES:
                    _log.debug("    跳过过大的 GFX 文件 (%.0f KB): %s", fsize / 1024, fname)
                    skip_count += 1
                    continue
                _log.debug("    解析 GFX: %s", fname)
                tf = time.monotonic()
                self._gfx_files[fpath] = fpath
                self._parse_gfx_file(fpath, priority)
                elapsed = time.monotonic() - tf
                if elapsed > 1.0:
                    _log.warning("GFX 解析耗时过长 %.2fs: %s", elapsed, fpath)
                gfx_count += 1
        _log.debug("gfx 扫描完成: 遍历 %d 个目录，解析 %d 个 .gfx（跳过 %d 个过大文件），耗时 %.3fs",
                   dir_count, gfx_count, skip_count, time.monotonic() - t0)

    _SPRITE_BLOCK_KEYS_CANONICAL = (
        'spriteType', 'corneredTileSpriteType', 'textSpriteType',
        'progressbartype', 'frameAnimatedSpriteType',
    )

    def _normalize_sprite_block_key(self, key: str) -> Optional[str]:
        kl = key.lower()
        for canon in self._SPRITE_BLOCK_KEYS_CANONICAL:
            if kl == canon.lower():
                return canon
        return None

    def _parse_gfx_file(self, gfx_path: str, priority: int):
        try:
            pairs = parse_file(gfx_path)
        except Exception as e:
            _log.warning("解析 GFX 文件失败: %s — %s", gfx_path, e)
            return
        before = len(self._sprites)
        self._register_sprites_from_gfx_pairs(pairs, priority)
        added = len(self._sprites) - before
        if added:
            _log.debug("    %s: 注册 %d 个精灵图", os.path.basename(gfx_path), added)

    def _register_sprites_from_gfx_pairs(self, pairs: list, priority: int):
        """Register sprite* blocks: spriteTypes = { ... }, or top-level spriteType = { ... }."""
        if not isinstance(pairs, list):
            return
        for key, val in pairs:
            if not isinstance(key, str):
                continue
            if key.lower() == 'spritetypes' and isinstance(val, list):
                self._register_sprites_from_gfx_pairs(val, priority)
                continue
            canon = self._normalize_sprite_block_key(key)
            if canon and isinstance(val, list):
                self._register_sprite(canon, val, priority)

    def _register_sprite(self, sprite_type: str, pairs: list, priority: int):
        d = pairs_to_dict(pairs)
        name = d.get('name')
        if not name or not isinstance(name, str):
            return
        if name in self._sprites and priority <= self._sprites[name]._priority:
            return

        # textureFile can appear with various capitalizations in the wild
        texture = ''
        for key in ('textureFile', 'texturefile', 'TextureFile', 'textureFilePath',
                    'texturefilepath'):
            if key in d and isinstance(d[key], str):
                texture = d[key]
                break
        if not isinstance(texture, str):
            texture = ''

        nof = d.get('noOfFrames', 1)
        try:
            nof = int(nof)
        except Exception:
            nof = 1

        border = (0, 0)
        bs = d.get('borderSize')
        if isinstance(bs, dict):
            border = (int(bs.get('x', 0)), int(bs.get('y', 0)))

        info = SpriteInfo(
            name=name,
            texture_path=texture,
            sprite_type=sprite_type,
            no_of_frames=nof,
            border_size=border,
        )
        info._priority = priority
        self._sprites[name] = info

    def _load_localisation_dir(self, loc_dir: str,
                               cancel_event: Optional[threading.Event] = None):
        """
        Scan the entire localisation directory tree for .yml files.
        Handles any subdirectory structure (including language prefixes like
        'english', 'l_english', 'simp_chinese', 'l_simp_chinese', etc.).
        Also loads files directly in loc_dir without a language subfolder.
        """
        t0 = time.monotonic()
        file_count = 0
        _log.debug("扫描本地化目录: %s", loc_dir)
        seen: set = set()
        for root, dirs, files in self._safe_walk(loc_dir):
            if cancel_event and cancel_event.is_set():
                _log.debug("_load_localisation_dir: 收到取消信号，当前目录 %s", root)
                break
            for fname in files:
                if cancel_event and cancel_event.is_set():
                    _log.debug("_load_localisation_dir: 文件循环中收到取消信号")
                    break
                if fname.lower().endswith(('.yml', '.ymlcore')):
                    fpath = os.path.join(root, fname)
                    if fpath not in seen:
                        seen.add(fpath)
                        _log.debug("  解析本地化文件: %s", fname)
                        tf = time.monotonic()
                        self._parse_loc_file(fpath)
                        elapsed = time.monotonic() - tf
                        if elapsed > 1.0:
                            _log.warning("本地化文件解析耗时过长 %.2fs: %s", elapsed, fpath)
                        file_count += 1
        # Flat _loc must match _loc_by_lang (active language + fallbacks)
        _log.debug("本地化文件扫描完成: %d 个文件，耗时 %.3fs，开始重建词条索引...",
                   file_count, time.monotonic() - t0)
        t1 = time.monotonic()
        self._rebuild_loc()
        _log.debug("词条索引重建完成: %d 条词条，重建耗时 %.3fs", len(self._loc), time.monotonic() - t1)

    def _load_localisation(self, loc_dir: str, lang: str):
        """Legacy method kept for compatibility — routes to _load_localisation_dir."""
        self._load_localisation_dir(loc_dir)

    def _detect_available_languages(self, mod_dir: str):
        """Detect available languages from localisation subdirectory names."""
        loc_dir = os.path.join(mod_dir, 'localisation')
        if not os.path.isdir(loc_dir):
            return
        # Subfolders named like 'english', 'simp_chinese', etc. → l_<name>
        for name in os.listdir(loc_dir):
            full = os.path.join(loc_dir, name)
            if os.path.isdir(full):
                lang_key = f'l_{name}'
                if lang_key not in self._available_languages:
                    self._available_languages.append(lang_key)
            # Also detect from languages.yml
            if name.lower() == 'languages.yml':
                self._parse_languages_yml(os.path.join(loc_dir, name))

    def _parse_languages_yml(self, path: str):
        """Parse languages.yml to find all available language keys."""
        for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                with open(path, 'r', encoding=enc, errors='strict') as f:
                    content = f.read()
                break
            except Exception:
                continue
        else:
            return
        for m in re.finditer(r'^(l_\w+)\s*:', content, re.MULTILINE):
            lang = m.group(1)
            if lang not in self._available_languages:
                self._available_languages.append(lang)

    def _parse_loc_file(self, path: str):
        """
        Parse a Stellaris localisation YAML file.
        Handles UTF-8 BOM (utf-8-sig) and plain UTF-8.
        Keys are stored per-language AND merged into the flat _loc dict.
        """
        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                with open(path, 'r', encoding=enc, errors='strict') as f:
                    lines = f.readlines()
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                _log.warning("本地化文件编码异常，使用容错模式读取: %s", path)
            except Exception as e:
                _log.warning("无法读取本地化文件: %s — %s", path, e)
                return

        current_lang = ''
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            hdr = re.match(r'^(l_\w+)\s*:', stripped)
            if hdr:
                current_lang = hdr.group(1)
                # Track available languages
                if current_lang and current_lang not in self._available_languages:
                    self._available_languages.append(current_lang)
                continue
            # Stellaris: key:0 "text" 或 key:0"text"（版本号与引号间可无空格）；亦支持 key:"text"
            m = re.match(
                r'^\s*([\w.\-]+)\s*:\s*(?:\d+\s*)?"(.*)"\s*(?:#.*)?$',
                line.rstrip('\r\n'),
            )
            if m:
                key, val = m.group(1), m.group(2)
                if current_lang:
                    if current_lang not in self._loc_by_lang:
                        self._loc_by_lang[current_lang] = {}
                    self._loc_by_lang[current_lang][key] = val

    # ------------------------------------------------------------------
    # Event scanning（懒加载：仅在事件关联面板首次展开时调用）
    # ------------------------------------------------------------------

    def ensure_events_scanned(self) -> bool:
        """
        按需扫描事件目录（懒加载）。
        仅扫描尚未扫描过的目录，避免重复开销。
        返回 True 表示本次调用确实执行了扫描，False 表示全部命中缓存。
        """
        dirs_to_scan: List[str] = []
        for d in [self.game_dir, self.mod_dir] + self._extra_mod_dirs:
            if d and os.path.isdir(d):
                abs_d = os.path.abspath(d)
                if abs_d not in self._events_scanned_dirs:
                    dirs_to_scan.append(d)
                    self._events_scanned_dirs.add(abs_d)
        if not dirs_to_scan:
            return False
        self._scan_events(dirs_to_scan)
        return True

    def _scan_events(self, search_dirs: List[str]):
        """Background-friendly: scan event dirs and merge results into _events."""
        try:
            from .event_parser import scan_event_dirs
            new_events = scan_event_dirs(search_dirs)
            for gui_name, evts in new_events.items():
                if gui_name not in self._events:
                    self._events[gui_name] = []
                existing_ids = {e.id for e in self._events[gui_name]}
                for ev in evts:
                    if ev.id not in existing_ids:
                        self._events[gui_name].append(ev)
        except Exception:
            pass

    def get_events_for_gui(self, gui_name: str) -> List:
        """Return all EventInfo objects that reference the given custom_gui name."""
        return list(self._events.get(gui_name, []))

    _ROOM_WALK_SKIP_DIRS = frozenset({
        '.git', '__pycache__', '.venv', 'venv', 'node_modules',
        'python_embeded', '.idea', '.vs',
    })

    def _collect_room_search_bases(self, gui_file_hint: str) -> List[str]:
        """Ordered mod/game roots for room lookup (deduped)."""
        search_bases: List[str] = []
        seen: set = set()

        def _add_base(p: str):
            if p and os.path.isdir(p):
                ap = os.path.abspath(p)
                if ap not in seen:
                    seen.add(ap)
                    search_bases.append(ap)

        if gui_file_hint and os.path.isfile(gui_file_hint):
            gui_dir = os.path.dirname(os.path.abspath(gui_file_hint))
            if os.path.basename(gui_dir).lower() == 'interface':
                _add_base(os.path.dirname(gui_dir))
            else:
                _add_base(gui_dir)

        if self.mod_dir:
            _add_base(self.mod_dir)
        for d in self._extra_mod_dirs:
            _add_base(d)
        if self.game_dir:
            _add_base(self.game_dir)
        return search_bases

    def _collect_room_extended_roots(self, seen_paths: set) -> List[str]:
        """Extra roots: Steam Workshop Stellaris mods, workspace, recent mod dirs."""
        roots: List[str] = []

        def _add(p: str):
            if not p or not os.path.isdir(p):
                return
            ap = os.path.abspath(p)
            if ap not in seen_paths:
                seen_paths.add(ap)
                roots.append(ap)

        try:
            from .settings import AppSettings
            st = AppSettings.instance()
            for d in st.recent_mod_dirs:
                _add(d)
            for wf in st.workspace_folders:
                if wf.get('enabled', True):
                    _add(wf.get('path', '') or '')
        except Exception:
            pass

        if self.game_dir:
            gd = os.path.abspath(self.game_dir)
            common = os.path.dirname(gd)
            if os.path.basename(common).lower() == 'common':
                steamapps = os.path.dirname(common)
                wsp = os.path.join(steamapps, 'workshop', 'content', '281990')
                _add(wsp)
        return roots

    def _try_room_file(self, abs_path: str, room_key: str) -> Optional[QPixmap]:
        pm = self.decode_image_to_pixmap(abs_path, strict=True)
        if pm and not pm.isNull():
            self._room_file_cache[room_key] = abs_path
            return pm
        return None

    def _walk_room_match(
        self, base: str, room_name: str, exts: Tuple[str, ...], room_key: str
    ) -> Optional[QPixmap]:
        """Walk *base* for a file named room_name + ext; skip heavy/irrelevant dirs."""
        rn_low = room_name.lower()
        try:
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in self._ROOM_WALK_SKIP_DIRS
                    and not d.startswith('.')
                ]
                for fname in filenames:
                    stem, ext = os.path.splitext(fname)
                    if stem.lower() != rn_low or ext.lower() not in exts:
                        continue
                    candidate = os.path.join(dirpath, fname)
                    pm = self._try_room_file(candidate, room_key)
                    if pm:
                        return pm
        except Exception:
            pass
        return None

    def resolve_room_pixmap(self, room_name: str, gui_file_hint: str = ''):
        """
        Resolve a room name to a QPixmap.
        Uses strict image decode (no placeholder) so failed DDS are retried.
        Phase 1: gfx priority paths + walk usual mod/game roots.
        Phase 2: Steam Workshop 281990, workspace folders, recent mod dirs — full tree walk.
        """
        from .event_parser import _is_scope
        if _is_scope(room_name):
            return None, True

        room_name = str(room_name).strip().strip('"').strip()
        if not room_name:
            return None, False

        room_key = room_name.lower()
        if room_key in self._room_file_cache:
            cached = self._room_file_cache[room_key]
            if cached and os.path.isfile(cached):
                pm = self.decode_image_to_pixmap(cached, strict=True)
                if pm and not pm.isNull():
                    return pm, False

        search_bases = self._collect_room_search_bases(gui_file_hint)
        exts = ('.dds', '.png', '.tga', '.jpg', '.jpeg', '.bmp', '.webp')
        priority_subs = [
            'gfx/event_pictures',
            'gfx/portraits/rooms',
            'gfx/portraits/city_sets',
            'gfx/portraits',
            'gfx/interface',
            'gfx',
        ]

        def phase_walk(bases: List[str]) -> Optional[QPixmap]:
            for base in bases:
                for sub in priority_subs:
                    for ext in exts:
                        candidate = os.path.join(
                            base, sub.replace('/', os.sep), room_name + ext)
                        if os.path.isfile(candidate):
                            pm = self._try_room_file(candidate, room_key)
                            if pm:
                                return pm
                pm = self._walk_room_match(base, room_name, exts, room_key)
                if pm:
                    return pm
            return None

        pm = phase_walk(search_bases)
        if pm:
            return pm, False

        seen = {os.path.abspath(b) for b in search_bases}
        extra = self._collect_room_extended_roots(seen)
        pm = phase_walk(extra)
        if pm:
            return pm, False

        return None, False

    def get_option_gui_root(self, gui_name: str):
        """
        Find and return the top-level WidgetNode (containerWindowType) whose name
        matches gui_name, searched across all indexed GUI files.
        Results are cached.  Returns None if not found.
        """
        from .gui_model import parse_gui_file
        gui_name_lower = gui_name.lower().strip('"')
        # Check cache first
        cached = self._top_level_gui_index.get(gui_name_lower)
        if cached is not None:
            return cached  # may be a WidgetNode or sentinel False

        # Scan all known .gui / .guicore files
        for fname, fpath in list(self._gui_files.items()):
            try:
                doc = parse_gui_file(fpath)
            except Exception:
                continue
            for root in doc.roots:
                if (root.widget_type.lower() == 'containerwindowtype'
                        and root.name
                        and root.name.lower() == gui_name_lower):
                    self._top_level_gui_index[gui_name_lower] = root
                    return root
        # Not found — cache sentinel to avoid repeated scans
        self._top_level_gui_index[gui_name_lower] = False  # type: ignore[assignment]
        return None

    @staticmethod
    def _walk_widget_subtree(node):
        yield node
        for ch in node.children:
            yield from ResourceManager._walk_widget_subtree(ch)

    def get_scrollbar_node(self, scrollbar_name: str):
        """Find a scrollbarType / extendedScrollbarType definition by its name.
        Searches all known GUI files (full widget subtree). Returns WidgetNode or None."""
        from .gui_model import parse_gui_file
        name_lower = scrollbar_name.lower().strip('"')
        cached = self._scrollbar_index.get(name_lower)
        if cached is not None:
            return cached if cached else None

        for fname, fpath in list(self._gui_files.items()):
            try:
                doc = parse_gui_file(fpath)
            except Exception:
                continue
            for root in doc.roots:
                for n in self._walk_widget_subtree(root):
                    wt = n.widget_type.lower()
                    if wt in ('scrollbartype', 'extendedscrollbartype'):
                        if (n.name or '').lower() == name_lower:
                            self._scrollbar_index[name_lower] = n
                            return n

        self._scrollbar_index[name_lower] = False  # type: ignore[assignment]
        return None

    # ------------------------------------------------------------------
    # Language switching
    # ------------------------------------------------------------------

    def get_available_languages(self) -> List[str]:
        """Return list of language keys (e.g. 'l_english', 'l_simp_chinese') detected."""
        return list(self._available_languages)

    def get_active_language(self) -> str:
        return self._active_language

    def set_active_language(self, lang: str):
        """Switch the active localisation language. Rebuilds the flat _loc dict."""
        if lang == self._active_language:
            return
        self._active_language = lang
        self._rebuild_loc()

    def _rebuild_loc(self):
        """Rebuild flat _loc dict from per-language stores, prioritising active language."""
        self._loc = {}
        # First load all languages as fallback (english → active language overwrites)
        for lang, data in self._loc_by_lang.items():
            if lang != self._active_language:
                for k, v in data.items():
                    if k not in self._loc:
                        self._loc[k] = v
        # Then apply active language on top
        active_data = self._loc_by_lang.get(self._active_language, {})
        self._loc.update(active_data)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_sprite(self, name: str) -> Optional[SpriteInfo]:
        return self._sprites.get(name)

    def get_all_sprites(self) -> List[SpriteInfo]:
        return list(self._sprites.values())

    def get_sprite_names(self) -> List[str]:
        return sorted(self._sprites.keys())

    def iter_sprites(self):
        """Iterate over (name, SpriteInfo) pairs for all registered sprites."""
        return self._sprites.items()

    def get_loc(self, key, _depth: int = 0) -> str:
        """Resolve a localization key with full Stellaris loc processing:
        - Literal \\n in the value → actual newline character
        - $OTHER_KEY$ references → recursively resolved (max depth 8)
        Falls back to the raw key string if the key is not found.
        """
        if not key:
            return ''
        # 防御性处理：事件文件中同名键重复时 key 可能是列表，取第一个字符串
        if not isinstance(key, str):
            if isinstance(key, list):
                key = next((x for x in key if isinstance(x, str)), '')
            else:
                key = str(key)
            if not key:
                return ''
        key = key.strip('"')
        value = self._loc.get(key, key)
        if _depth < 8:
            # Resolve $KEY$ substitution references
            import re
            def _replace_ref(m: 're.Match') -> str:
                ref_key = m.group(1)
                resolved = self.get_loc(ref_key, _depth + 1)
                # If resolution returned the raw key (not found), show it in brackets
                return resolved if resolved != ref_key else f'[{ref_key}]'
            try:
                value = re.sub(r'\$([^$\n]+)\$', _replace_ref, value)
            except Exception:
                pass
        # Convert Stellaris literal escape sequences
        value = value.replace('\\n', '\n')
        return value

    TEXT_ICON_SPRITE_PREFIX = 'GFX_text_'

    @staticmethod
    def split_loc_text_and_icons(text: str) -> List[Tuple[str, str]]:
        """
        Split resolved localisation into alternating text and text-icon segments.
        £energy£ → icon key 'energy' mapped to sprite GFX_text_energy in game files.
        """
        if not text:
            return []
        if '£' not in text:
            return [('text', text)]
        out: List[Tuple[str, str]] = []
        pos = 0
        for m in re.finditer(r'£([^£\n]*)£', text):
            if m.start() > pos:
                out.append(('text', text[pos:m.start()]))
            inner = (m.group(1) or '').strip()
            if inner:
                out.append(('icon', inner))
            pos = m.end()
        if pos < len(text):
            out.append(('text', text[pos:]))
        return out

    @staticmethod
    def strip_stellaris_color_codes_plain(s: str) -> str:
        """Remove § colour / style codes for measuring or plain preview."""
        if not s:
            return ''
        t = re.sub(r'§.', '', s)
        return t.replace('§!', '')

    def resolve_text_icon_sprite_name(self, icon_key: str) -> Optional[str]:
        """
        Map £key£ to a registered sprite name (GFX_text_<suffix>).
        Tries exact / lower-case / underscore forms, then case-insensitive suffix match.
        """
        k = (icon_key or '').strip()
        if not k:
            return None
        prefix = self.TEXT_ICON_SPRITE_PREFIX
        candidates = [
            f'{prefix}{k}',
            f'{prefix}{k.lower()}',
            f'{prefix}{k.replace(" ", "_")}',
            f'{prefix}{k.replace("-", "_")}',
        ]
        seen = set()
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            if c in self._sprites:
                return c
        kl = k.lower()
        pl = prefix.lower()
        for name in self._sprites.keys():
            if len(name) <= len(prefix):
                continue
            if not name.lower().startswith(pl):
                continue
            suffix = name[len(prefix):]
            if suffix.lower() == kl:
                return name
        return None

    def get_text_icon_pixmap_for_line_height(
        self, icon_key: str, line_height: int,
    ) -> Optional[QPixmap]:
        """Scaled pixmap for inline £icon£ preview; preserves aspect ratio."""
        name = self.resolve_text_icon_sprite_name(icon_key)
        if not name:
            return None
        lh = max(8, int(line_height))
        cache_key = f'{name}@h{lh}'
        cached = self._text_icon_pixmap_cache.get(cache_key)
        if cached is not None and not cached.isNull():
            return cached
        base = self.get_sprite_pixmap(name)
        if not base or base.isNull():
            return None
        nh, nw = base.height(), base.width()
        if nh <= 0:
            return base
        tw = max(1, int(nw * lh / nh))
        pm = self.get_sprite_pixmap(name, target_size=(tw, lh))
        if pm and not pm.isNull():
            self._text_icon_pixmap_cache[cache_key] = pm
        return pm

    def get_gui_files(self) -> Dict[str, str]:
        return dict(self._gui_files)

    def resolve_texture_path(self, relative_path: str) -> Optional[str]:
        """
        Resolve a texture path to an absolute file path.
        Search order: primary mod → extra mods (in order) → vanilla game.
        Tries the exact extension first, then .dds / .tga / .png / .jpg fallbacks.
        The path may use either '/' or '\\' as separator and may be quoted.
        """
        if not relative_path:
            return None
        rel = relative_path.strip('"').replace('\\', os.sep).replace('/', os.sep)

        search_dirs: List[str] = []
        if self.mod_dir:
            search_dirs.append(self.mod_dir)
        search_dirs.extend(self._extra_mod_dirs)
        if self.game_dir:
            search_dirs.append(self.game_dir)

        ext_variants = ('.dds', '.tga', '.png', '.jpg', '.bmp')

        for base in search_dirs:
            full = os.path.join(base, rel)
            if os.path.isfile(full):
                return full
            # Try alternate extensions
            stem = os.path.splitext(full)[0]
            for ext in ext_variants:
                alt = stem + ext
                if os.path.isfile(alt):
                    return alt
                # Case-insensitive fallback on Windows is automatic, but try
                # explicit upper-case extension for cross-platform safety
                alt_up = stem + ext.upper()
                if os.path.isfile(alt_up):
                    return alt_up
        return None

    @staticmethod
    def _pil_image_to_qpixmap(img) -> Optional[QPixmap]:
        """Convert a loaded PIL Image to QPixmap (RGBA)."""
        try:
            from PIL import Image
            if img.mode == 'P':
                img = img.convert('RGBA')
            elif img.mode == 'PA':
                img = img.convert('RGBA')
            elif img.mode in ('RGB', 'RGBX'):
                img = img.convert('RGBA')
            elif img.mode == 'BGRA':
                try:
                    r, g, b, a = img.split()
                    img = Image.merge('RGBA', (b, g, r, a))
                except Exception:
                    img = img.convert('RGBA')
            elif img.mode in ('LA',):
                img = img.convert('RGBA')
            elif img.mode == 'L':
                img = img.convert('RGBA')
            elif img.mode == 'CMYK':
                img = img.convert('RGBA')
            elif img.mode != 'RGBA':
                img = img.convert('RGBA')
            w, h = img.size
            if w < 1 or h < 1:
                return None
            data = img.tobytes('raw', 'RGBA')
            qimg = QImage(data, w, h, QImage.Format.Format_RGBA8888)
            if qimg.isNull():
                return None
            pm = QPixmap.fromImage(qimg.copy())
            return pm if pm and not pm.isNull() else None
        except Exception:
            return None

    def _try_decode_dds_with_pydds(self, abs_path: str) -> Optional[QPixmap]:
        """Decode DDS via bundled ``pydds`` (BC7/DX10 等)；正常安装下始终可用。"""
        if _PYDDS_DECODE_BYTES is None:
            return None
        try:
            with open(abs_path, 'rb') as f:
                raw = f.read()
            if len(raw) < 128 or raw[:4] != b'DDS ':
                return None
            img = _PYDDS_DECODE_BYTES(raw)
            if img is None:
                return None
            return self._pil_image_to_qpixmap(img)
        except Exception:
            return None

    @staticmethod
    def _try_decode_dds_via_ffmpeg(abs_path: str) -> Optional[QPixmap]:
        """If ``ffmpeg`` is on PATH, decode DDS to PNG in memory (helps BC7 without pydds)."""
        if not shutil.which('ffmpeg'):
            return None
        try:
            kwargs: dict = {
                'args': ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', abs_path,
                         '-f', 'png', 'pipe:1'],
                'capture_output': True,
                'timeout': 60,
            }
            if os.name == 'nt':
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            r = subprocess.run(**kwargs)
            if r.returncode != 0 or not r.stdout:
                return None
            pm = QPixmap()
            if pm.loadFromData(r.stdout, 'PNG') and not pm.isNull():
                return pm
        except Exception:
            return None
        return None

    @staticmethod
    def _try_decode_dds_via_texconv(abs_path: str) -> Optional[QPixmap]:
        """
        Optional Microsoft DirectXTex ``texconv.exe`` (many DXGI / BC formats).
        Set ``TEXCONV_PATH`` to the full path of texconv.exe, or put texconv on PATH.
        """
        exe = (os.environ.get('TEXCONV_PATH') or '').strip().strip('"')
        if not exe or not os.path.isfile(exe):
            w = shutil.which('texconv')
            exe = w if w else ''
        if not exe:
            return None
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                before = set(os.listdir(td))
                kwargs: dict = {
                    'args': [
                        exe, '-y', '-ft', 'png', '-o', td, os.path.normpath(abs_path),
                    ],
                    'capture_output': True,
                    'timeout': 90,
                }
                if os.name == 'nt':
                    kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                r = subprocess.run(**kwargs)
                if r.returncode != 0:
                    return None
                after = set(os.listdir(td))
                new_pngs = [f for f in (after - before) if f.lower().endswith('.png')]
                if not new_pngs:
                    return None
                out_png = os.path.join(td, new_pngs[0])
                pm = QPixmap(out_png)
                return pm if pm and not pm.isNull() else None
        except Exception:
            return None

    def decode_image_to_pixmap(
        self, abs_path: str, *, strict: bool = False
    ) -> Optional[QPixmap]:
        """
        Decode texture to QPixmap using multiple backends (Pillow, imageio, OpenCV, Wand, Qt).
        If strict=False and all fail, returns a checkerboard placeholder (editor fallback).
        If strict=True, returns None on failure (used for room / success detection).
        """
        if not abs_path or not os.path.isfile(abs_path):
            return None

        # 0) DDS: pydds / ffmpeg / texconv before Pillow — BC6/BC7 etc. often fail in Pillow
        if abs_path.lower().endswith('.dds'):
            pm = self._try_decode_dds_with_pydds(abs_path)
            if pm:
                return pm
            pm = ResourceManager._try_decode_dds_via_ffmpeg(abs_path)
            if pm:
                return pm
            pm = ResourceManager._try_decode_dds_via_texconv(abs_path)
            if pm:
                return pm

        # 1) Pillow — most DDS DXT + many PNG variants
        try:
            from PIL import Image
            img = Image.open(abs_path)
            img.load()
            pm = self._pil_image_to_qpixmap(img)
            if pm:
                return pm
        except Exception:
            pass

        # 2) imageio v2 / v3 (often picks ffmpeg-freeimage; helps some DDS/PNG)
        for _use_v3 in (True, False):
            try:
                if _use_v3:
                    import imageio.v3 as iio
                    arr = iio.imread(abs_path)
                else:
                    import imageio
                    arr = imageio.imread(abs_path)
                import numpy as np
                if arr is None:
                    continue
                if arr.ndim == 2:
                    arr = np.stack([arr, arr, arr, np.full_like(arr, 255)], axis=-1)
                elif arr.ndim == 3 and arr.shape[2] == 3:
                    alpha = np.full((*arr.shape[:2], 1), 255, dtype=arr.dtype)
                    arr = np.concatenate([arr, alpha], axis=-1)
                elif arr.ndim == 3 and arr.shape[2] == 4:
                    pass
                else:
                    continue
                if arr.dtype != np.uint8:
                    if arr.max() <= 1.0:
                        arr = (np.asarray(arr) * 255).clip(0, 255).astype(np.uint8)
                    else:
                        arr = arr.astype(np.uint8)
                h, w = arr.shape[:2]
                # BGRA → RGBA (OpenCV-style arrays from some readers)
                if arr.shape[2] == 4:
                    pass
                data = arr.tobytes()
                qimg = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
                if not qimg.isNull():
                    pm = QPixmap.fromImage(qimg.copy())
                    if pm and not pm.isNull():
                        return pm
            except Exception:
                pass

        # 3) OpenCV (many “odd” PNG/BMP; some DDS when built with opencv-contrib)
        try:
            import cv2
            import numpy as np
            arr = cv2.imread(abs_path, cv2.IMREAD_UNCHANGED)
            if arr is not None and arr.size > 0:
                if arr.ndim == 2:
                    arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGBA)
                elif arr.shape[2] == 3:
                    arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGBA)
                elif arr.shape[2] == 4:
                    arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA)
                if arr.dtype != np.uint8:
                    arr = arr.astype(np.uint8)
                h, w = arr.shape[:2]
                data = arr.tobytes()
                qimg = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
                if not qimg.isNull():
                    pm = QPixmap.fromImage(qimg.copy())
                    if pm and not pm.isNull():
                        return pm
        except Exception:
            pass

        # 4) Wand (ImageMagick) — broad format support
        try:
            from wand.image import Image as WandImage
            with WandImage(filename=abs_path) as wi:
                wi.alpha_channel = 'activate'
                img_bytes = wi.make_blob('png')
            pm = QPixmap()
            if pm.loadFromData(img_bytes):
                return pm if not pm.isNull() else None
        except Exception:
            pass

        # 5) Qt direct (PNG/JPEG/BMP and some TGAs)
        try:
            pm = QPixmap(abs_path)
            if pm and not pm.isNull() and pm.width() > 0 and pm.height() > 0:
                return pm
        except Exception:
            pass

        if strict:
            return None
        return self._make_error_placeholder(abs_path, 64, 64)

    def _load_pixmap_from_file(self, abs_path: str) -> Optional[QPixmap]:
        """Editor sprite path: decode or placeholder (never None for missing file path)."""
        if not abs_path or not os.path.isfile(abs_path):
            return None
        return self.decode_image_to_pixmap(abs_path, strict=False)

    @staticmethod
    def _make_error_placeholder(path: str, w: int = 64, h: int = 64) -> QPixmap:
        """Return a recognizable checkerboard placeholder when image loading fails."""
        from PySide6.QtGui import QPainter, QColor
        pm = QPixmap(w, h)
        # Use filename hash for a unique-but-consistent color
        color_seed = hash(os.path.basename(path)) & 0xFFFFFF
        r = (color_seed >> 16) & 0xFF
        g = (color_seed >> 8) & 0xFF
        b = color_seed & 0xFF
        base_col = QColor(max(60, r), max(60, g), max(60, b), 180)
        dark_col = QColor(30, 30, 30, 180)
        pm.fill(base_col)
        painter = QPainter(pm)
        tile = max(8, w // 4)
        for ty in range(0, h, tile):
            for tx in range(0, w, tile):
                if (tx // tile + ty // tile) % 2 == 0:
                    painter.fillRect(tx, ty, tile, tile, dark_col)
        painter.end()
        return pm

    def get_sprite_natural_size(self, sprite_name: str) -> Tuple[int, int]:
        """
        Get the natural single-frame size of a sprite.
        For spriteType widgets, this is the actual display size (before scale).
        Returns (0, 0) if unknown.
        """
        info = self._sprites.get(sprite_name)
        if not info:
            return (0, 0)

        if info.natural_width > 0:
            return (info.natural_width, info.natural_height)

        # Load the image to get size
        abs_path = self.resolve_texture_path(info.texture_path)
        if not abs_path:
            return (0, 0)

        cache_key = f'_size_{abs_path}'
        if cache_key in self._size_cache:
            w, h = self._size_cache[cache_key]
        else:
            try:
                from PIL import Image
                with Image.open(abs_path) as img:
                    w, h = img.width, img.height
            except Exception:
                pm = QPixmap(abs_path)
                if pm and not pm.isNull():
                    w, h = pm.width(), pm.height()
                else:
                    return (0, 0)
            self._size_cache[cache_key] = (w, h)

        frame_w = w // info.no_of_frames
        info.natural_width = frame_w
        info.natural_height = h
        return (frame_w, h)

    def get_sprite_pixmap(
        self,
        sprite_name: str,
        target_size: Optional[Tuple[int, int]] = None,
        frame: int = 0,
    ) -> Optional[QPixmap]:
        """
        Get a QPixmap for a named sprite.
        If target_size is given, scale to fit.
        """
        info = self._sprites.get(sprite_name)
        if not info or not info.texture_path:
            return None
        abs_path = self.resolve_texture_path(info.texture_path)
        if not abs_path:
            return None

        cache_key = f'{sprite_name}@f{frame}'
        if cache_key in self._pixmap_cache:
            pm = self._pixmap_cache[cache_key]
        else:
            base_pm = self._load_pixmap_from_file(abs_path)
            if not base_pm or base_pm.isNull():
                # Return None so callers can use their own fallback rendering
                return None
            if info.no_of_frames > 1:
                frame_width = base_pm.width() // info.no_of_frames
                frame = max(0, min(frame, info.no_of_frames - 1))
                pm = base_pm.copy(QRect(frame * frame_width, 0, frame_width, base_pm.height()))
            else:
                pm = base_pm
            if info.natural_width == 0:
                info.natural_width = pm.width()
                info.natural_height = pm.height()
            self._pixmap_cache[cache_key] = pm

        if target_size and target_size[0] > 0 and target_size[1] > 0:
            from PySide6.QtCore import Qt
            pm = pm.scaled(
                target_size[0], target_size[1],
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pm

    def is_cornered_tile(self, sprite_name: str) -> bool:
        """Return True if this sprite is a corneredTileSpriteType (9-patch)."""
        info = self._sprites.get(sprite_name)
        return info is not None and info.is_scalable()

    def get_widget_render_mode(self, node) -> str:
        """
        Determine how to render a widget based on its sprite attribute AND
        the actual sprite type in the registry.

        Returns:
          'none'       - no sprite
          'nine_patch' - corneredTileSpriteType, use widget size + 9-patch
          'fixed'      - spriteType (fixed size), use natural size × scale
        """
        sprite_name = None
        if hasattr(node, 'get_sprite_name'):
            sprite_name = node.get_sprite_name()
        if not sprite_name:
            return 'none'

        info = self._sprites.get(sprite_name)

        # Check the actual GFX registry type — if the registered sprite is a
        # corneredTileSpriteType (is_scalable), render as nine_patch regardless
        # of whether the GUI file used spriteType or quadTextureSprite.
        if hasattr(node, 'properties'):
            if node.properties.get('spriteType'):
                # spriteType in GUI but if GFX registry says it's corneredTile → nine_patch
                if info and info.is_scalable():
                    return 'nine_patch'
                return 'fixed'
            if node.properties.get('quadTextureSprite'):
                if info and info.is_scalable():
                    return 'nine_patch'
                return 'fixed'
        return 'fixed' if info and not info.is_scalable() else 'nine_patch'

    def get_raw_pixmap(self, sprite_name: str, frame: int = 0) -> Optional[QPixmap]:
        """Get the raw pixmap for one horizontal frame of a sprite (strip / noOfFrames)."""
        return self.get_sprite_pixmap(sprite_name, frame=frame)

    def get_sprite_pixmap_scaled(
        self, sprite_name: str, scale: float = 1.0, frame: int = 0
    ) -> Optional[QPixmap]:
        """Get pixmap at natural size × scale. Used for fixed-size (spriteType) widgets."""
        nw, nh = self.get_sprite_natural_size(sprite_name)
        if nw <= 0 or nh <= 0:
            pm = self.get_sprite_pixmap(sprite_name, frame=frame)
            if pm and not pm.isNull():
                nw, nh = pm.width(), pm.height()
            else:
                return None
        disp_w = max(1, int(nw * scale))
        disp_h = max(1, int(nh * scale))
        return self.get_sprite_pixmap(
            sprite_name, target_size=(disp_w, disp_h), frame=frame,
        )

    def clear_cache(self):
        self._pixmap_cache.clear()
        self._size_cache.clear()
        self._room_file_cache.clear()
        self._text_icon_pixmap_cache.clear()

    def reload_all(self):
        """
        Full resource reload (manual action):
        - Rebuild sprite registry from game/mod/extra mods
        - Reparse localisation
        - Clear pixmap/size caches
        """
        game_dir = self.game_dir
        mod_dir = self.mod_dir
        extra_dirs = list(self._extra_mod_dirs)

        self._sprites.clear()
        self._loc.clear()
        self._loc_by_lang.clear()
        self._available_languages.clear()
        self._gui_files.clear()
        self._gfx_files.clear()
        self._top_level_gui_index.clear()
        self._scrollbar_index.clear()
        self._events.clear()
        self._events_scanned_dirs.clear()
        self.clear_cache()

        if game_dir:
            self.load_game_dir(game_dir)
        if mod_dir:
            self.load_mod_dir(mod_dir)
        for d in extra_dirs:
            self.load_extra_mod_dir(d)

    @property
    def sprite_count(self) -> int:
        return len(self._sprites)

    @property
    def loc_count(self) -> int:
        return len(self._loc)
