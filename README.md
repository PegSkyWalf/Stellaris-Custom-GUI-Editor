# 群星自定义GUI编辑器 / Stellaris Custom-GUI Editor

**中文** | [English](#english)

一个为群星（Stellaris）Mod 制作者设计的**可视化自定义 GUI 编辑器**。  
无需手动编写繁琐的脚本代码，拖拽即可完成界面设计，实时预览精灵图渲染效果。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-informational.svg)](https://doc.qt.io/qtforpython/)

---

## 主要功能

| 功能 | 说明 |
|------|------|
| 可视化画布 | 拖拽控件、调整大小、对齐工具、多选操作 |
| 精灵图渲染 | 加载 DDS/BC7/TGA/PNG 贴图，正确渲染 9 块拉伸和固定尺寸精灵 |
| 代码视图 | 实时 PDX 语法高亮，支持直接编辑代码并回写到画布 |
| 属性面板 | 编辑所有属性，含**原始属性编辑器**（防止未知属性丢失） |
| 精灵图库 | 浏览 7900+ 原版精灵图，支持类型筛选与预览 |
| 本地化预览 | 解析 `.yml` 文件，属性面板内直接显示翻译文本 |
| 事件关联 | 自动扫描事件文件中的 `custom_gui` 引用 |
| Button Effects | 可视化编辑 `common/button_effects/*.txt` |
| GFX 生成器 | 快速生成 `.gfx` 精灵注册文件 |
| 主题系统 | 深色 / 浅色 / 深海蓝，支持自定义强调色 |
| 首次向导 | 引导新用户完成游戏目录配置与主题选择 |
| 日志记录 | 写入本地日志文件，便于 Bug 排查 |

---

## 快速开始（3 步）

### 1. 安装

```bash
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd Stellaris-Custom-GUI-Editor
pip install -r requirements.txt
```

### 2. 运行

```bash
python main.py
```

首次启动时，向导会引导你配置游戏目录。

### 3. 开始编辑

1. **文件 → 打开模组目录** — 选择你的 Mod 文件夹
2. **文件 → 新建 GUI 文件** — 输入文件名和 GUI 键名
3. 从**控件库**双击添加控件，在**属性面板**编辑属性
4. **Ctrl+S** 保存

---

## 画布操作快捷键

| 操作 | 快捷键 |
|------|--------|
| 移动视图 | 鼠标中键拖拽 / Alt+拖拽 |
| 缩放 | Ctrl+滚轮 |
| 适应画布 | Ctrl+0 |
| 撤销 / 重做 | Ctrl+Z / Ctrl+Y |
| 复制控件 | Ctrl+D |
| 删除控件 | Delete |
| 查找控件 | Ctrl+F |
| 对齐（左/右/水平居中） | Ctrl+Alt+1 / 2 / 3 |
| 对齐（上/下/垂直居中） | Ctrl+Alt+4 / 5 / 6 |
| 预览模式 | Ctrl+P |

完整快捷键列表：**帮助 → 快捷键列表**

---

## 分发版（免安装 EXE）

### 下载现成的 EXE

前往 [Releases](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases) 下载最新版 ZIP，**解压后再运行 EXE**。

> ⚠️ **重要**：必须解压整个 ZIP，不能只复制 `.exe` 文件单独运行。  
> EXE 文件旁边的 `_internal\` 目录包含所有必要的运行时库，缺少它将无法启动。

### 自行编译

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（建议勾选 **Add Python to PATH**；未勾选也可，只要安装了 `py launcher`）
2. 克隆仓库：
   ```bash
   git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
   cd Stellaris-Custom-GUI-Editor
   ```
3. **双击项目根目录的 `build.bat`** — 自动安装依赖、编译、打包为 ZIP

编译产物在 `dist\StellarisGUIEditor\`，同时会生成 `StellarisCustomGUIEditor_Windows.zip` 可直接分发。

> 详见 [docs/development.md](docs/development.md)

---

## 免责声明

本项目为开源社区工具，与 Paradox Interactive 无任何官方关联。  
详见 [DISCLAIMER.md](DISCLAIMER.md)。

---

## 项目结构

```
Stellaris-Custom-GUI-Editor/
├── main.py                     # 程序入口
├── requirements.txt            # Python 依赖
├── StellarisGUIEditor.spec     # PyInstaller 打包配置
├── DISCLAIMER.md               # 免责声明
├── assets/                     # 图标等静态资源
├── packaging/                  # 构建脚本
│   ├── build_windows.bat       # Windows 一键构建
│   ├── create_icon.py          # 图标生成器
│   └── version_info.txt        # Windows EXE 元数据
├── docs/                       # 文档
│   ├── user_guide_CN.md        # 中文用户手册
│   ├── user_guide_EN.md        # 英文用户手册
│   ├── development.md          # 开发者指南
│   └── stellaris_gui_reference.md  # 群星 GUI 脚本速查
└── src/
    ├── core/                   # 核心逻辑
    │   ├── __version__.py      # 版本信息
    │   ├── logger.py           # 日志系统
    │   ├── theme_manager.py    # 主题管理
    │   ├── pdx_parser.py       # PDX 脚本解析器
    │   ├── gui_model.py        # 控件数据模型
    │   ├── resource_manager.py # 游戏/Mod 资源管理
    │   ├── settings.py         # 应用设置
    │   ├── undo.py             # 撤销/重做系统
    │   ├── event_parser.py     # 事件文件解析
    │   └── virtual_groups.py   # 虚拟编组系统
    ├── ui/                     # 界面层
    │   ├── main_window.py      # 主窗口
    │   ├── canvas.py           # 可视化画布
    │   ├── widget_items.py     # 画布控件渲染
    │   ├── properties_panel.py # 属性面板
    │   ├── welcome_dialog.py   # 首次启动向导
    │   ├── dialogs.py          # 各类对话框
    │   ├── widget_library.py   # 控件库
    │   ├── sprite_library.py   # 精灵图库
    │   ├── layer_panel.py      # 图层面板
    │   ├── event_link_panel.py # 事件关联面板
    │   ├── button_effects_editor.py # Button Effects 编辑器
    │   ├── code_view.py        # 代码视图
    │   ├── file_browser.py     # 文件浏览器
    │   └── virtual_groups_panel.py  # 虚拟编组面板
    └── codegen/                # 代码生成
        └── gui_writer.py       # .gui/.gfx 文件生成器
```

---

## 常见问题

**Q：打开程序后提示"未配置游戏目录"**  
A：前往 工具 → 设置 → 路径，点击"自动检测"或手动浏览到群星安装目录（应包含 `interface/` 子目录）。

**Q：精灵图无法显示（显示为棋盘格）**  
A：检查游戏目录是否正确配置；某些 BC7 格式的 DDS 文件需要 ffmpeg（在 PATH 中）或 texconv.exe。

**Q：保存后的 .gui 文件游戏无法识别**  
A：确保文件编码为 UTF-8，并放置在 Mod 的 `interface/` 目录下。

**Q：程序崩溃如何报告？**  
A：日志文件位于 `C:\Users\用户名\.stellaris_gui_editor\logs\`，提交 Issue 时请附上最新日志。

---

## 贡献

欢迎提交 Issue 和 Pull Request！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

GPL-3.0 — 详见 [LICENSE](LICENSE)

> 注：本项目依赖 pydds（GPLv3），因此整体采用 GPL-3.0 许可证。

---

<a id="english"></a>

## English

A visual custom GUI editor for Stellaris mod creators. Design UI layouts with drag-and-drop, preview sprites in real-time, and generate `.gui` script files automatically.

**[Quick Start]**

```bash
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd Stellaris-Custom-GUI-Editor
pip install -r requirements.txt
python main.py
```

**[User Manual]** [docs/user_guide_EN.md](docs/user_guide_EN.md)  
**[Contributing]** [CONTRIBUTING.md](CONTRIBUTING.md)  
**[Disclaimer]** [DISCLAIMER.md](DISCLAIMER.md)

**Key Features:** Visual canvas editing · DDS sprite rendering · Live PDX code preview · Localization preview · Button Effects editor · Theme system (dark/light/dark-blue) · First-run setup wizard · Windows auto-packager

**License:** GPL-3.0 · This project is not affiliated with Paradox Interactive.
