# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller 打包配置 — 群星 GUI 编辑器
#
# 构建方式（推荐使用 build_windows.bat）：
#   pip install -r requirements.txt pyinstaller
#   python packaging/create_icon.py        # 生成占位图标（若尚无图标）
#   pyinstaller StellarisGUIEditor.spec --noconfirm
#
# 产物：dist/StellarisGUIEditor/StellarisGUIEditor.exe
# 将整个 dist/StellarisGUIEditor/ 文件夹打包分发给用户。
#

import os
import sys

# ── pydds (DDS BC7/DX10 解码器) ──────────────────────────────────────────
try:
    from PyInstaller.utils.hooks import collect_all
    _dds_datas, _dds_binaries, _dds_hidden = collect_all('dds')
except Exception:
    _dds_datas, _dds_binaries, _dds_hidden = [], [], []

try:
    import dds_sys
    _dds_sys_binaries = [(dds_sys.__file__, '.')]
except ImportError:
    _dds_sys_binaries = []

# ── 应用图标 ──────────────────────────────────────────────────────────────
_icon_path = os.path.join('assets', 'app_icon.ico')
_icon = _icon_path if os.path.isfile(_icon_path) else None

# ── 版本信息文件（Windows EXE 元数据）────────────────────────────────────
_version_file = os.path.join('packaging', 'version_info.txt')
_version = _version_file if os.path.isfile(_version_file) else None

# ── assets 目录（图标等）────────────────────────────────────────────────
_extra_datas = []
if os.path.isdir('assets'):
    _extra_datas.append(('assets', 'assets'))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_dds_binaries + _dds_sys_binaries,
    datas=_dds_datas + _extra_datas,
    hiddenimports=list({
        # pydds
        'dds', 'dds_sys', 'dds.dds',
        *_dds_hidden,
        # Pillow 解码器（动态加载）
        'PIL._imaging', 'PIL.Image', 'PIL.ImageDraw',
        # imageio 插件
        'imageio.plugins', 'imageio.plugins.pillow', 'imageio.v3',
        # numpy
        'numpy.core', 'numpy.core._methods',
        # PySide6 可能漏掉的模块
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
        # winreg（Steam 路径检测，Windows 内置，打包时可能需要显式包含）
        'winreg',
    }),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不需要的大型库
        'tkinter', 'matplotlib', 'scipy', 'pandas',
        'IPython', 'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StellarisGUIEditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # 关闭 UPX 压缩：避免杀毒软件误报，提升启动速度
    console=False,      # 不显示控制台窗口（日志写入文件）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
    version=_version,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='StellarisGUIEditor',
)
