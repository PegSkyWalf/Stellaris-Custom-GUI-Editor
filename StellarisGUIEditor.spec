# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller 打包配置 — 群星自定义GUI编辑器
#
# 构建方式（推荐使用项目根目录的 build.bat）：
#   build.bat
#
# 或手动构建：
#   pip install -r requirements.txt pyinstaller
#   python packaging/create_icon.py
#   pyinstaller StellarisGUIEditor.spec --noconfirm
#
# 产物：dist/StellarisGUIEditor/StellarisGUIEditor.exe
# 分发时必须将整个 dist/StellarisGUIEditor/ 文件夹（含 _internal 子目录）一并打包为 ZIP。
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

# ── Visual C++ Runtime DLLs ─────────────────────────────────────────────
# PyInstaller 6.x 的 dylib.py 明确排除 vcruntime140.dll 等 VC++ 运行库，
# 即使放在 binaries 列表里也会被过滤掉。
#
# 解决方法：以 datas 形式（纯文件复制）绕过此过滤，
# 放置在 '.'（_internal 根目录），确保 python313.dll 能找到其依赖。
# 注意：build_windows.bat 还会额外把这些 DLL 复制到 EXE 同级目录，
# 因为 PyInstaller 6.x 的 bootloader 在加载 python3XX.dll 时，
# Windows 的 DLL 搜索顺序尚未包含 _internal，所以需要 DLL 在 EXE 旁边。
_runtime_datas = []
_py_dir = os.path.dirname(sys.executable)
for _dll in ('vcruntime140.dll', 'vcruntime140_1.dll', 'python3.dll'):
    _p = os.path.join(_py_dir, _dll)
    if os.path.isfile(_p):
        _runtime_datas.append((_p, '.'))
    else:
        _sys32 = os.path.join(
            os.environ.get('SystemRoot', r'C:\Windows'), 'System32', _dll
        )
        if os.path.isfile(_sys32):
            _runtime_datas.append((_sys32, '.'))

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
    datas=_dds_datas + _extra_datas + _runtime_datas,
    hiddenimports=list({
        # pydds
        'dds', 'dds_sys', 'dds.dds',
        *_dds_hidden,
        # Pillow
        'PIL._imaging', 'PIL.Image', 'PIL.ImageDraw',
        # imageio
        'imageio.plugins', 'imageio.plugins.pillow', 'imageio.v3',
        # numpy
        'numpy.core', 'numpy.core._methods',
        # PySide6
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
        # winreg（Steam 路径检测）
        'winreg',
    }),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    upx=False,          # 关闭 UPX：避免杀毒误报，加快启动
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
