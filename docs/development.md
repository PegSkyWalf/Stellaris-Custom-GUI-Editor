# 开发者指南

本文档面向希望参与贡献、进行二次开发或深入理解项目架构的开发者。

---

## 目录

1. [开发环境搭建](#1-开发环境搭建)
2. [项目架构](#2-项目架构)
3. [核心模块详解](#3-核心模块详解)
4. [界面模块详解](#4-界面模块详解)
5. [数据流与事件机制](#5-数据流与事件机制)
6. [Stellaris 坐标系统](#6-stellaris-坐标系统)
7. [精灵图渲染流程](#7-精灵图渲染流程)
8. [添加新控件类型](#8-添加新控件类型)
9. [添加新属性字段](#9-添加新属性字段)
10. [主题系统](#10-主题系统)
11. [打包发行](#11-打包发行)
12. [测试](#12-测试)
13. [扩展接口](#13-扩展接口)
14. [设计原则与约定](#14-设计原则与约定)

---

## 1. 开发环境搭建

```bash
# 1. 克隆项目
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd Stellaris-Custom-GUI-Editor

# 2. 安装运行依赖
pip install -r requirements.txt

# 3. 安装开发依赖（可选，用于测试/打包）
pip install pyinstaller pytest

# 4. 运行
python main.py
```

**requirements.txt 主要依赖：**

| 包 | 用途 |
|----|------|
| `PySide6` | Qt GUI 框架 |
| `Pillow` | DDS/PNG/TGA 图像解码 |
| `pydds` | DDS BC7/DX10 高级格式解码（GPLv3） |
| `imageio` | imageio 图像 I/O 后端 |
| `numpy` | pydds 依赖 |

---

## 2. 项目架构

### 目录结构

```
src/
├── core/          # 纯逻辑层，无 PySide6 UI 类依赖
│   ├── __version__.py      # 版本号/元数据唯一来源
│   ├── logger.py           # 轮转日志 + 全局异常捕获
│   ├── pdx_parser.py       # PDX Script 词法分析器 + 解析器
│   ├── gui_model.py        # WidgetNode 数据模型 + 布局计算引擎
│   ├── resource_manager.py # 游戏/Mod 资源管理（精灵索引、纹理缓存、本地化）
│   ├── settings.py         # 设置持久化（JSON）+ Steam 路径自动检测
│   ├── theme_manager.py    # 主题 QPalette + QSS 生成
│   ├── undo.py             # 命令模式撤销/重做栈
│   ├── event_parser.py     # 事件脚本解析（custom_gui 引用）
│   └── virtual_groups.py   # 虚拟编组数据 + .groups.json 持久化
├── ui/            # 界面层（PySide6）
│   ├── main_window.py           # 主窗口（菜单、Dock、工具栏、事件协调）
│   ├── canvas.py                # GUICanvas（QGraphicsView）+ GUIScene（QGraphicsScene）
│   ├── widget_items.py          # GUIWidgetItem（QGraphicsItem），每控件一个实例
│   ├── properties_panel.py      # 属性编辑面板（动态生成表单）
│   ├── welcome_dialog.py        # 首次启动配置向导
│   ├── dialogs.py               # 所有对话框（设置、精灵选择等）
│   ├── widget_library.py        # 控件类型库 + 预设库
│   ├── sprite_library.py        # 精灵图库面板
│   ├── layer_panel.py           # 图层面板（QTreeWidget）
│   ├── event_link_panel.py      # 事件关联面板
│   ├── button_effects_editor.py # Button Effects 可视化编辑器
│   ├── code_view.py             # 代码视图（QPlainTextEdit + PDXHighlighter）
│   ├── file_browser.py          # .gui/.gfx 文件树（QTreeView）
│   └── virtual_groups_panel.py  # 虚拟编组管理面板
└── codegen/
    └── gui_writer.py       # GUIDocument → PDX Script 序列化器
```

### 分层原则

```
┌──────────────────────────────┐
│         ui/ (PySide6)        │  ← 可导入 core/，但 core/ 不能导入 ui/
├──────────────────────────────┤
│    core/ (纯 Python 逻辑)    │  ← 唯一例外：resource_manager 使用 QPixmap
├──────────────────────────────┤
│      codegen/ (生成器)       │  ← 只依赖 core/gui_model
└──────────────────────────────┘
```

**约定：**
- `core/` 中**不得**导入任何 PySide6 UI Widget 类（`QApplication`、`QWidget` 等）
- `QPixmap` 在 `resource_manager.py` 中使用是合理的，因为它在逻辑层管理纹理缓存
- 所有用户可见字符串（按钮标签、菜单名称等）使用**中文**
- 变量名、函数名、类名、注释使用**英文**

---

## 3. 核心模块详解

### `pdx_parser.py` — PDX Script 解析器

**职责**：将 `.gui` / `.gfx` / `.txt` 等文件解析为 Python dict/list 结构。

**实现**：
- `PDXLexer`：基于状态机的词法分析器，生成 Token 流
- `PDXParser`：递归下降解析器，处理嵌套块和重复键（合并为列表）

**支持的语法特性：**
```
guiTypes = {                         # 块结构（嵌套花括号）
    @MY_VAR = 300                    # 变量定义
    name = "hello"                   # 带引号字符串
    name = hello                     # 不带引号字符串（也合法）
    enabled = yes                    # 布尔值
    position = { x = 10 y = 20 }    # 内联块
    # 这是注释                        # 注释（#开头）
    size = { x = 100 y = 50 }       # x/y 或 width/height 两种 size 语法
}
```

**重复键处理**：同一块中的重复键合并为 list（群星 GUI 文件中常见，例如多个 `iconType = {...}`）。

---

### `gui_model.py` — 数据模型与布局引擎

**关键类：**
- `WidgetNode`：表示单个 GUI 控件，含 `widget_type`、`properties`（dict）、`children`（list）、`parent`
- `GUIDocument`：整个 `.gui` 文件，含 `roots`（顶层节点列表）、`variables`、`source_path`

**关键函数：**

| 函数 | 说明 |
|------|------|
| `parse_gui_file(path)` | 解析文件，返回 `GUIDocument` |
| `parse_gui_text(text)` | 解析字符串，返回 `GUIDocument` |
| `create_widget(widget_type, name)` | 创建带类型默认属性的新节点 |
| `compute_widget_topleft(pw, ph, cw, ch, orientation, origo, px, py)` | Stellaris 坐标 → Qt 画布左上角坐标 |
| `reverse_compute_position(...)` | Qt 坐标 → Stellaris position 值 |
| `resolve_editor_layout_sizes(roots, cw, ch, rm)` | 为隐式尺寸容器计算包围盒，填充 `_editor_layout_size` |
| `_solve_layout_node(node, outer_pw, outer_ph, rm)` | 递归计算单个节点的显示尺寸 |

**隐式尺寸容器算法（关键）：**

对未声明 `size` 属性的容器（`_editor_layout_size is not None` 为标识），以 `(0, 0)` 作为子控件锚点参考计算包围盒。这是避免 `orientation=center` 子控件产生错误偏移的核心设计，与游戏的处理方式一致。

---

### `resource_manager.py` — 资源管理器

**单例模式**，通过 `ResourceManager.instance()` 访问。

**主要方法：**

| 方法 | 说明 |
|------|------|
| `load_game_resources(game_path, mod_paths)` | 异步扫描所有资源（在 `_ResourceLoaderThread` 中调用）|
| `get_sprite_pixmap(name, w, h)` | 返回指定精灵图的 QPixmap，带尺寸缓存 |
| `get_localization(key, lang)` | 查询本地化键的翻译文本 |
| `get_sprite_info(name)` | 返回精灵图元数据（路径、帧数、原始尺寸等）|
| `list_sprites()` | 返回所有精灵图名称列表 |

**DDS 解码优先级**：
1. `pydds`（支持 BC7/DX10）
2. Pillow（支持 DXT1/3/5）
3. imageio（通用后端）
4. 全部失败则返回占位棋盘格

---

### `undo.py` — 撤销/重做栈

**命令基类**：`Command`，子类须实现 `execute()` 和 `undo()`。

**内置命令类型：**

| 命令类 | 触发操作 |
|--------|---------|
| `MoveWidgetCommand` | 拖拽移动控件 |
| `SetPropertyCommand` | 属性面板修改属性 |
| `AddWidgetCommand` | 从控件库添加控件 |
| `DeleteWidgetCommand` | Delete 键删除控件 |
| `DuplicateWidgetCommand` | Ctrl+D 复制控件 |
| `CompoundCommand` | 多个命令打包为一步 |

**使用示例（在 main_window.py 中）：**
```python
cmd = SetPropertyCommand(node, 'position', old_val, new_val,
                         callback=self._on_property_changed)
self._undo_stack.push(cmd)
```

---

### `settings.py` — 设置持久化

**单例模式**，通过 `AppSettings.instance()` 访问。

配置文件路径：`~/.stellaris_gui_editor/settings.json`

**关键设置项：**

| Key | 类型 | 说明 |
|-----|------|------|
| `game_path` | str | 群星安装目录 |
| `mod_paths` | list[str] | 模组目录列表 |
| `theme` | str | `dark` / `light` / `dark_blue` |
| `accent_color` | str | 强调色（十六进制） |
| `canvas_width` | int | 参考画布宽度（默认 1920） |
| `canvas_height` | int | 参考画布高度（默认 1080） |
| `undo_limit` | int | 撤销步数上限（默认 100） |

**Steam 路径自动检测**：读取 `HKCU\Software\Valve\Steam\SteamPath`，遍历 `steamapps/libraryfolders.vdf` 查找群星安装路径。

---

### `virtual_groups.py` — 虚拟编组

**数据结构**：`VirtualGroup(name, member_names: set[str], visible: bool)`

**持久化**：以 `*.groups.json` 侧车文件保存，不修改 `.gui` 文件本体。

**关键方法**：
- `VirtualGroupManager.is_node_hidden_by_group(name)` — 判断某控件是否被编组隐藏
- 可见性与图层面板可见性完全独立（互不干扰）

---

## 4. 界面模块详解

### `canvas.py` — 可视化画布

**核心类**：
- `GUIScene(QGraphicsScene)` — 管理所有 `GUIWidgetItem`
- `GUICanvas(QGraphicsView)` — 视口，处理缩放/平移/选择

**渲染流程**（加载文档后）：
1. `GUIScene.load_document(doc)` 清空场景
2. 递归调用 `_build_item_tree(node, parent_item)` 构建 QGraphicsItem 树
3. 每个 `GUIWidgetItem` 在 `paint()` 时计算屏幕坐标：
   - 调用 `_parent_layout_dimensions()` 获取父容器锚点尺寸
   - 对隐式容器（`_editor_layout_size is not None`）返回 `(0.0, 0.0)`
   - 调用 `compute_widget_topleft()` 得到左上角坐标
   - 加载精灵图 QPixmap 并缩放至显示尺寸

**缩放**：`QGraphicsView.scale()` 实现，范围 0.25–4.0（25%–400%）

---

### `widget_items.py` — 控件图形元素

每个 `GUIWidgetItem` 对应一个 `WidgetNode`，是 QGraphicsItem 子类。

**关键属性**：
- `_visible_flag`：图层面板控制的可见性（独立于 `QGraphicsItem.isVisible()`）
- `node`：关联的 `WidgetNode` 引用

**`set_visible_flag(visible)`**：设置图层可见性，同时检查是否被虚拟编组隐藏。

---

### `main_window.py` — 主窗口

**职责**：协调所有面板、响应用户操作、管理文档状态。

**关键信号/槽连接：**
- 画布选中控件 → 图层面板高亮 + 属性面板更新 + 代码视图滚动
- 属性面板修改 → 推送 `SetPropertyCommand` → 画布刷新
- 图层面板可见性切换 → `_on_visibility_changed` → `GUIWidgetItem.set_visible_flag()`
- 虚拟编组可见性切换 → `_on_vgroup_visibility_changed` → 遍历所有 `GUIWidgetItem`

**资源加载**：`_ResourceLoaderThread(QThread)` 在后台加载，信号回调更新进度条和状态栏。

---

### `code_view.py` — 代码视图

**精准定位算法**：
1. `_compute_node_path(node)` — 计算控件在文档中的结构路径（类型+名称+深度索引）
2. `_find_block_by_struct_path(code, path)` — 在代码文本中按结构路径定位对应代码块
3. 同名控件在不同容器中不再混淆（旧版仅按名称搜索）

---

## 5. 数据流与事件机制

### 打开文件流程

```
用户选择文件
    → parse_gui_file() → GUIDocument（WidgetNode 树）
    → resolve_editor_layout_sizes()  # 计算隐式容器尺寸
    → GUIScene.load_document()       # 构建 QGraphicsItem 树
    → _build_layer_tree()            # 同步图层面板
    → CodeView.set_document()        # 同步代码视图
```

### 属性修改流程

```
用户在属性面板修改值
    → SetPropertyCommand(node, key, old, new) 推入 UndoStack
    → command.execute() → node.properties[key] = new_value
    → 信号 property_changed(node)
    → canvas 刷新对应 GUIWidgetItem
    → code_view 重新生成代码文本
```

### 保存流程

```
Ctrl+S
    → GUIWriter.write(document) → PDX Script 文本
    → 写入文件（UTF-8，无 BOM）
```

---

## 6. Stellaris 坐标系统

群星 GUI 使用双锚点定位系统，理解这是开发本项目的关键。

### 核心概念

| 属性 | 含义 |
|------|------|
| `orientation` | 控件锚点相对于**父容器**的位置，默认 `UPPER_LEFT` |
| `origo` | 控件自身的参考点，默认 `UPPER_LEFT` |
| `position` | 从 `orientation` 锚点到 `origo` 点的偏移量 |

### 计算公式

```python
# 父容器尺寸 (pw, ph)，控件尺寸 (cw, ch)
# orientation 确定父容器上的锚点
anchor_x = pw * orientation_factor_x   # UPPER_LEFT → 0, CENTER → pw/2, LOWER_RIGHT → pw
anchor_y = ph * orientation_factor_y

# origo 确定控件自身参考点
origo_offset_x = cw * origo_factor_x   # UPPER_LEFT → 0, CENTER → cw/2
origo_offset_y = ch * origo_factor_y

# 最终左上角坐标
topleft_x = anchor_x + position_x - origo_offset_x
topleft_y = anchor_y + position_y - origo_offset_y
```

### 隐式容器的特殊处理

**隐式容器**：未声明 `size` 属性的 `containerWindowType`。

其子控件计算位置时，使用 `(0, 0)` 作为父容器尺寸（而非容器的实际包围盒尺寸）。这与游戏行为一致：隐式容器本身尺寸为 0，子控件的 `orientation=center` 锚点即为 `(0, 0)`，位置直接就是 `position` 的偏移量。

**识别方式**：`getattr(node, '_editor_layout_size', None) is not None`

---

## 7. 精灵图渲染流程

```
get_sprite_pixmap(name, target_w, target_h)
    ↓
查找 sprite_info[name]（含 texturefile 路径、noOfFrames、borderSize 等）
    ↓
_load_texture(path) → 尝试 pydds → Pillow → imageio → 返回 QPixmap
    ↓
如果是 corneredTileSpriteType（9 块）:
    _render_9slice(pixmap, target_w, target_h, borderSize)
否则（spriteType，固定尺寸）:
    取第一帧（宽 = 总宽 / noOfFrames）
    缩放到 target_w × target_h
```

**帧动画**：`spriteType` 的 `noOfFrames > 1` 时，DDS 横向排列各帧；编辑器始终取第一帧。

---

## 8. 添加新控件类型

假设要添加 `newWidgetType` 支持：

### 步骤 1：注册类型

在 `gui_model.py` 的 `CONTAINER_TYPES` 或 `LEAF_TYPES` 集合中添加（取决于是否可包含子控件）。

在 `DEFAULT_PROPERTIES` 字典中添加该类型的默认属性。

### 步骤 2：属性面板

在 `properties_panel.py` 的 `_build_form()` 中为该类型添加专有属性行。

### 步骤 3：控件库

在 `widget_library.py` 的控件列表中添加条目（含显示名称和默认创建参数）。

### 步骤 4：渲染（可选）

如果该类型有特殊渲染逻辑，在 `widget_items.py` 的 `_paint_widget()` 中添加分支。

### 步骤 5：代码生成

在 `gui_writer.py` 中，如果该类型的序列化方式与标准不同，添加特殊处理。

---

## 9. 添加新属性字段

1. **在 `gui_model.py`** 的 `DEFAULT_PROPERTIES` 中为相关控件类型添加默认值
2. **在 `properties_panel.py`** 的 `_build_form()` 中添加 UI 行（选择合适的控件：`QLineEdit`、`QSpinBox`、`QComboBox` 等）
3. **在 `gui_writer.py`** 的 `_should_write_property()` 中确保该属性不被过滤掉

若属性值为本地化键，在属性面板的 `_resolve_loc()` 中添加查询逻辑。

---

## 10. 主题系统

### 结构

`ThemeManager` 在 `theme_manager.py` 中定义，输出：
- `QPalette`：Qt 原生调色板（控制大部分系统控件颜色）
- QSS 样式表：覆盖 QPalette 无法控制的细节（如 `QTextEdit`、`QPlainTextEdit` 的背景色）

### 添加新主题

1. 在 `theme_manager.py` 的 `THEMES` 字典中添加新主题配色定义
2. 在 `_build_qss()` 中为该主题添加对应 QSS 规则

### 主题感知组件

所有需要主题感知的自定义组件应：
- 将 `objectName` 设置为特定值（如 `setObjectName("code_editor")`）
- 在 QSS 中通过 `QWidget#objectname` 选择器定义样式
- 在 `ThemeManager.apply()` 后调用 `update_theme()` 方法刷新

---

## 11. 打包发行

### 一键构建

```bash
# 双击 build.bat 或命令行运行：
cd Stellaris-Custom-GUI-Editor
build.bat
```

构建完成后生成：
- `dist\StellarisGUIEditor\` — 完整程序目录
- `StellarisCustomGUIEditor_Windows.zip` — 可直接分发的压缩包

### 构建流程细节

`build.bat` → `packaging/build_windows.bat` 执行以下步骤：
1. 自动检测 Python 解释器（`python` → `py -3` → `py -3.11` 回退）
2. 安装 `requirements.txt` 依赖
3. 安装 PyInstaller
4. 运行 `packaging/create_icon.py` 生成占位图标
5. 清理旧构建产物
6. 运行 PyInstaller（使用 `StellarisGUIEditor.spec`）
7. **后处理**：复制 `vcruntime140.dll`、`vcruntime140_1.dll`、`python3.dll` 到 EXE 同级目录（解决目标机器缺少 VC++ Redistributable 的问题）
8. 压缩 `dist\StellarisGUIEditor\` 为 ZIP

### 为什么需要复制 vcruntime DLL？

PyInstaller 6.x 的 bootloader 在加载 `python3XX.dll` 时，Windows DLL 搜索顺序是：
`已知DLL → System32 → EXE所在目录（非 _internal）`

因此 `vcruntime140.dll` 必须放在 EXE 旁边（不仅仅是 `_internal\` 内），否则在没有安装 VC++ 2022 Redistributable 的机器上会报 `Failed to load Python DLL` 错误。

PyInstaller 的 `dylib.py` 明确将这些 DLL 列为系统 DLL 并排除打包，因此需要构建脚本手动复制。

### 发布新版本

```bash
# 1. 更新版本号
# 编辑 src/core/__version__.py 中的 VERSION

# 2. 更新 CHANGELOG.md

# 3. 构建 EXE
build.bat

# 4. 创建 Git 标签
git tag v1.1.0
git push origin v1.1.0

# 5. 创建 GitHub Release（使用 gh CLI）
gh release create v1.1.0 StellarisCustomGUIEditor_Windows.zip \
  --title "v1.1.0" \
  --notes-file RELEASE_NOTES.md
```

---

## 12. 测试

目前项目包含以下测试脚本（`test_*.py`）：

- `test_advanced.py` — 测试解析和布局计算（需要 `TEST_GUICORE_PATH` 环境变量指定测试 GUI 文件）
- `test_comprehensive.py` — 综合功能测试

运行测试：
```bash
# 指定测试文件路径（不硬编码到代码中）
set TEST_GUICORE_PATH=E:\path\to\test.gui
python test_advanced.py
```

---

## 13. 扩展接口

项目预留了以下扩展点，社区开发者可在此基础上添加功能：

### 资源加载钩子

`ResourceManager` 加载完成后发出 `resources_loaded` 信号，可在主窗口中连接：
```python
rm.resources_loaded.connect(self._on_resources_ready)
```

### 文档变更通知

`GUIDocument` 中的节点修改通过 `UndoStack` 的 `stack_changed` 信号广播：
```python
undo_stack.stack_changed.connect(canvas.refresh)
```

### 主题切换通知

`ThemeManager` 提供 `theme_changed(theme_name)` 信号：
```python
theme_mgr.theme_changed.connect(widget.update_theme)
```

### 自定义属性渲染器

在 `properties_panel.py` 的 `_build_form()` 中为特定属性键注册自定义 widget 工厂：
```python
self._custom_renderers['my_property'] = MyCustomWidget
```

---

## 14. 设计原则与约定

| 原则 | 说明 |
|------|------|
| 单向依赖 | `core/` 不依赖 `ui/`；`ui/` 可依赖 `core/` |
| 单例访问 | `ResourceManager.instance()` / `AppSettings.instance()` |
| 命令模式 | 所有可撤销操作必须通过 `Command` 子类实现 |
| 中文 UI | 所有用户可见字符串用中文；代码标识符用英文 |
| 版本集中 | 版本号只在 `src/core/__version__.py` 中定义 |
| 日志规范 | 使用 `get_logger(__name__)` 获取 logger；不使用 `print()` 调试 |
| 不修改 `.gui` 结构 | 虚拟编组等元数据用侧车文件保存，不改变 `.gui` 本体 |

---

*文档版本：v1.0.0 | 2026-03-26*
