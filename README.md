# 群星自定义GUI编辑器 / Stellaris Custom-GUI Editor

**中文** | [English](#english)

> 专为《群星》（Stellaris）Mod 制作者设计的**可视化自定义界面编辑器**。  
> 在画布上直接拖拽控件、实时预览精灵图渲染，自动生成符合游戏规范的 `.gui` 脚本，无需手写代码。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-informational.svg)](https://doc.qt.io/qtforpython/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)]()
[![Version](https://img.shields.io/badge/Version-1.0.0-orange.svg)](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases)

---

## 主要功能

| 功能 | 说明 |
|------|------|
| **可视化画布** | 1920×1080 参考画布，拖拽控件、缩放、平移，精确还原游戏坐标系 |
| **精灵图渲染** | 实时加载 DDS/BC7/TGA/PNG 贴图，支持 9 块拉伸（corneredTileSpriteType）和固定尺寸精灵 |
| **Orientation + Origo** | 完整实现群星双锚点定位系统，渲染位置与游戏内完全一致 |
| **代码视图** | 实时 PDX 脚本语法高亮；直接编辑代码，画布同步更新；**按控件结构路径精准高亮**，同名控件不再混淆 |
| **属性面板** | 编辑全部属性；内置**原始属性编辑器**，未知属性不丢失 |
| **图层面板** | 树形展示控件层次；点击即选中；可见性独立控制 |
| **虚拟编组** | 独立于 `.gui` 文件结构的编组管理，按功能区域组织控件；与图层可见性完全解耦 |
| **精灵图库** | 浏览 7900+ 原版精灵图；名称搜索；点击预览；直接应用到选中控件 |
| **本地化预览** | 解析 `.yml` 文件，在属性面板内直接显示翻译文本 |
| **事件关联面板** | 自动扫描事件文件中的 `custom_gui` 引用，显示调用来源 |
| **Button Effects 编辑器** | 可视化编辑 `common/button_effects/*.txt` |
| **GFX 生成器** | 快速生成 `.gfx` 精灵注册代码块 |
| **主题系统** | 深色 / 浅色 / 深海蓝，支持自定义强调色；全界面主题感知 |
| **撤销/重做** | 命令模式实现，最多 100 步，含复合操作 |
| **异步资源加载** | 后台线程扫描游戏资源，启动时不卡顿，进度条实时提示 |
| **首次向导** | 引导新用户完成游戏目录配置与主题选择 |
| **Steam 自动检测** | Windows 注册表自动定位群星安装目录 |
| **日志系统** | 轮转日志写入 `~/.stellaris_gui_editor/logs/`，崩溃可追溯 |

---

## 快速开始

### 方式一：直接下载 EXE（推荐）

1. 前往 **[Releases 页面](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases)** 下载最新版 ZIP
2. **解压**到任意目录（必须解压，不能直接在压缩包内运行）
3. 双击 `StellarisGUIEditor.exe`

> ⚠️ EXE 旁边的 `_internal\` 目录是必须的，请整体保留，不要只复制 `.exe` 单独运行。

### 方式二：从源码运行（开发者）

```bash
# 需要 Python 3.10+
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd Stellaris-Custom-GUI-Editor
pip install -r requirements.txt
python main.py
```

### 方式三：自行编译 EXE

1. 克隆仓库后，**双击项目根目录的 `build.bat`**
2. 脚本自动安装依赖、编译、生成 `StellarisCustomGUIEditor_Windows.zip`

> 详见 [docs/development.md](docs/development.md)

---

## 界面布局

```
┌──────────────────────────────────────────────────────────────────────┐
│  菜单栏  文件 / 编辑 / 工具 / 帮助                                     │
├──────────┬───────────────────────────────────┬──────────────────────┤
│ 左侧面板 │                                   │ 右侧面板             │
│          │          可视化画布               │                      │
│ ・控件库 │   (1920×1080，可缩放 25%~400%)   │ ・属性面板           │
│ ・精灵图 │                                   │ ・代码视图           │
│ ・文件树 │                                   │ ・事件关联           │
│          │                                   │                      │
├──────────┼───────────────────────────────────┼──────────────────────┤
│          │       图层面板 / 虚拟编组面板      │                      │
└──────────┴───────────────────────────────────┴──────────────────────┘
```

---

## 画布快捷键

| 操作 | 快捷键 |
|------|--------|
| 移动视图 | 鼠标中键拖拽 / Alt+拖拽 |
| 缩放 | Ctrl+滚轮 |
| 适应画布 | Ctrl+0 |
| 撤销 / 重做 | Ctrl+Z / Ctrl+Y |
| 复制控件 | Ctrl+D |
| 删除控件 | Delete |
| 预览模式（隐藏框线） | Ctrl+P |

完整快捷键列表：**帮助 → 快捷键列表**

---

## 项目结构

```
Stellaris-Custom-GUI-Editor/
├── main.py                          # 程序入口
├── requirements.txt                 # Python 依赖列表
├── build.bat                        # 一键构建 EXE（双击运行）
├── StellarisGUIEditor.spec          # PyInstaller 打包配置
├── DISCLAIMER.md                    # 免责声明
├── CONTRIBUTING.md                  # 贡献指南
├── CHANGELOG.md                     # 版本变更日志
├── assets/                          # 静态资源（图标等）
├── packaging/                       # 构建工具
│   ├── build_windows.bat            # 实际构建逻辑
│   ├── create_icon.py               # 图标生成器
│   └── version_info.txt             # Windows EXE 版本元数据
├── docs/                            # 文档
│   ├── user_guide_CN.md             # 中文用户手册
│   ├── user_guide_EN.md             # 英文用户手册
│   ├── development.md               # 开发者与贡献者指南
│   └── stellaris_gui_reference.md   # 群星 GUI 脚本速查手册
└── src/
    ├── core/                        # 纯逻辑层（无 UI 依赖）
    │   ├── __version__.py           # 版本号统一来源
    │   ├── logger.py                # 轮转日志系统
    │   ├── pdx_parser.py            # PDX Script 词法+语法解析器
    │   ├── gui_model.py             # WidgetNode 数据模型 + 布局计算引擎
    │   ├── resource_manager.py      # 游戏/Mod 资源管理（精灵、本地化、事件）
    │   ├── settings.py              # 设置持久化（JSON）+ Steam 路径检测
    │   ├── theme_manager.py         # 主题定义与 QSS 生成
    │   ├── undo.py                  # 命令模式撤销/重做栈
    │   ├── event_parser.py          # 事件脚本解析（custom_gui 关联）
    │   └── virtual_groups.py        # 虚拟编组数据与持久化
    ├── ui/                          # 界面层（PySide6）
    │   ├── main_window.py           # 主窗口（菜单、面板、事件协调）
    │   ├── canvas.py                # 可视化画布（QGraphicsView/Scene）
    │   ├── widget_items.py          # 画布控件图形元素（QGraphicsItem）
    │   ├── properties_panel.py      # 属性编辑面板
    │   ├── welcome_dialog.py        # 首次启动配置向导
    │   ├── dialogs.py               # 设置、精灵选择等对话框
    │   ├── widget_library.py        # 控件类型库 + 预设库
    │   ├── sprite_library.py        # 精灵图浏览面板
    │   ├── layer_panel.py           # 图层面板（控件树）
    │   ├── event_link_panel.py      # 事件关联面板
    │   ├── button_effects_editor.py # Button Effects 编辑器
    │   ├── code_view.py             # 代码视图（语法高亮 + 路径定位）
    │   ├── file_browser.py          # .gui/.gfx 文件树浏览
    │   └── virtual_groups_panel.py  # 虚拟编组管理面板
    └── codegen/
        └── gui_writer.py            # GUIDocument → PDX Script 序列化器
```

---

## 常见问题

**Q：打开程序后提示"未配置游戏目录"**  
A：前往 **工具 → 设置 → 路径**，点击"自动检测"，或手动浏览到群星安装目录（目录下应有 `interface/` 子目录）。

**Q：精灵图显示棋盘格（未加载）**  
A：检查游戏目录配置是否正确；部分 BC7 格式 DDS 需要额外的解码支持。确认 `pydds` 已正确安装（`pip install pydds`）。

**Q：EXE 启动报错 `Failed to load Python DLL`**  
A：必须将整个 ZIP 解压后再运行，不能只复制 `.exe` 文件。`_internal\` 目录包含了所有运行时库（含 VC++ 运行时 DLL）。

**Q：保存的 `.gui` 文件游戏内不显示**  
A：确保文件放置在 Mod 的 `interface/` 目录；文件编码应为 UTF-8（无 BOM）；在游戏事件脚本中通过 `custom_gui = "窗口名称"` 触发。

**Q：程序崩溃如何报告？**  
A：日志文件位于 `C:\Users\用户名\.stellaris_gui_editor\logs\`，提交 Issue 时请附上最新的 `.log` 文件。

---

## 贡献

欢迎提交 Issue 和 Pull Request！  
请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

**GPL-3.0** — 详见 [LICENSE](LICENSE)

> 本项目依赖 `pydds`（GPLv3），因此整体采用 GPL-3.0 协议。

---

## 免责声明

本项目为独立开源社区工具，与 Paradox Interactive AB 无任何官方关联。  
详见 [DISCLAIMER.md](DISCLAIMER.md)。

---

<a id="english"></a>

## English

A **visual custom GUI editor** for *Stellaris* mod creators. Drag-and-drop widgets on a 1920×1080 canvas, preview DDS sprites in real-time, and auto-generate `.gui` script files — no manual scripting needed.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-orange.svg)](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases)

### Key Features

- **Visual canvas** — 1920×1080 reference canvas, drag/resize/move widgets, fully accurate `orientation` + `origo` coordinate system
- **Sprite rendering** — DDS/BC7/TGA/PNG textures, including 9-slice (corneredTileSpriteType) and fixed-size sprites
- **Live code view** — PDX Script syntax highlighting; edit code directly and see canvas update; **structure-path-based highlighting** to disambiguate same-name widgets
- **Properties panel** — Edit all widget properties; raw key-value editor preserves unknown properties
- **Layer panel** — Tree view of widget hierarchy; click to select; independent visibility toggles
- **Virtual groups** — Organize widgets into logical groups independent of `.gui` file structure; visibility fully decoupled from layer panel
- **Sprite library** — Browse 7900+ vanilla sprites with search and preview
- **Localization preview** — Parse `.yml` files and display translated text inline
- **Event linking** — Scan event files for `custom_gui` references automatically
- **Button Effects editor** — Visual editor for `common/button_effects/*.txt`
- **Theme system** — Dark / Light / Dark Blue with custom accent color
- **Undo/Redo** — Command-pattern stack, up to 100 steps
- **Async resource loading** — Background thread; no UI freeze on startup
- **Steam auto-detect** — Reads Windows registry to find game install path
- **First-run wizard** — Guides new users through directory setup

### Quick Start

```bash
# Option A: Download pre-built EXE from Releases (recommended)
# Option B: Run from source
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd Stellaris-Custom-GUI-Editor
pip install -r requirements.txt
python main.py
```

**[User Manual (EN)](docs/user_guide_EN.md)** | **[Developer Guide](docs/development.md)** | **[Stellaris GUI Reference](docs/stellaris_gui_reference.md)** | **[Contributing](CONTRIBUTING.md)** | **[Disclaimer](DISCLAIMER.md)**

### License

GPL-3.0 · Not affiliated with Paradox Interactive AB.
