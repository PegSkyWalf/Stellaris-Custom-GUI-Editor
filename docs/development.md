# 开发者指南

本文档面向希望参与贡献或深入理解项目架构的开发者。

---

## 目录

1. [项目架构](#1-项目架构)
2. [核心模块说明](#2-核心模块说明)
3. [界面模块说明](#3-界面模块说明)
4. [数据流](#4-数据流)
5. [添加新控件类型](#5-添加新控件类型)
6. [添加新属性字段](#6-添加新属性字段)
7. [主题系统](#7-主题系统)
8. [打包发行](#8-打包发行)
9. [测试](#9-测试)
10. [扩展接口说明](#10-扩展接口说明)

---

## 1. 项目架构

```
src/
├── core/          # 纯逻辑层，无 UI 依赖
│   ├── __version__.py      # 版本信息（唯一来源）
│   ├── logger.py           # 日志系统
│   ├── theme_manager.py    # 主题定义与切换
│   ├── pdx_parser.py       # PDX 脚本分词器/解析器
│   ├── gui_model.py        # WidgetNode / GUIDocument 数据模型
│   ├── resource_manager.py # 游戏/Mod 资源管理（精灵、本地化、事件）
│   ├── settings.py         # 设置持久化（JSON）
│   ├── undo.py             # 命令模式撤销/重做
│   ├── event_parser.py     # 事件脚本解析
│   └── virtual_groups.py   # 虚拟编组系统
├── ui/            # 界面层（PySide6）
│   ├── main_window.py      # 主窗口（菜单、dock、工具栏）
│   ├── canvas.py           # GUICanvas / GUIScene（QGraphicsView/Scene）
│   ├── widget_items.py     # GUIWidgetItem（QGraphicsItem）
│   ├── properties_panel.py # 属性编辑面板
│   ├── welcome_dialog.py   # 首次启动向导
│   ├── dialogs.py          # 所有对话框（设置、新建、精灵选择等）
│   ├── widget_library.py   # 控件库 + 预设库
│   ├── sprite_library.py   # 精灵图库
│   ├── layer_panel.py      # 图层面板
│   ├── event_link_panel.py # 事件关联面板
│   ├── button_effects_editor.py # Button Effects 编辑器
│   ├── code_view.py        # 代码视图（QPlainTextEdit + 语法高亮）
│   ├── file_browser.py     # 文件浏览器（QTreeView）
│   └── virtual_groups_panel.py  # 虚拟编组面板
└── codegen/       # 代码生成
    └── gui_writer.py       # GUIDocument → .gui 文本
```

**设计原则：**
- `core/` 不得导入 PySide6 中的任何 UI 类（`QPixmap` 除外，resource_manager 需要）
- `ui/` 可以导入 `core/`，但 `core/` 不得导入 `ui/`
- 所有用户可见字符串（UI 标签）使用中文，变量/函数/类名使用英文

---

## 2. 核心模块说明

### `gui_model.py`

**关键类：**
- `WidgetNode`：表示单个 GUI 控件节点，含 `widget_type`、`properties`、`children`、`parent`
- `GUIDocument`：表示整个 `.gui` 文件，含 `roots`（顶层节点列表）和 `variables`

**关键函数：**
- `parse_gui_file(path)` → `GUIDocument`：解析文件
- `parse_gui_text(text)` → `GUIDocument`：解析字符串
- `create_widget(widget_type, name)` → `WidgetNode`：创建带默认属性的新节点
- `compute_widget_topleft(...)` → `(x, y)`：Stellaris 坐标 → Qt 坐标
- `reverse_compute_position(...)` → `(x, y)`：Qt 坐标 → Stellaris 坐标
- `resolve_editor_layout_sizes(roots, cw, ch, rm)`：计算隐式大小容器的尺寸

**Stellaris 定位系统：**
```
qt_top_left = anchor + stellaris_position - origo_offset
其中：
  anchor = parent_size * orientation_fraction
  origo_offset = widget_size * origo_fraction
```

### `resource_manager.py`

单例模式，通过 `ResourceManager.instance()` 获取。

**主要功能：**
- `load_game_dir(path)` / `load_mod_dir(path)` / `load_extra_mod_dir(path)`：加载资源
- `reload_all()`：完全重载（手动刷新时调用）
- `get_sprite(name)` → `SpriteInfo | None`
- `get_sprite_pixmap(name, target_size, frame)` → `QPixmap | None`
- `resolve_texture_path(relative)` → 绝对路径
- `get_loc(key)` → 本地化文本（支持 `$KEY$` 递归替换）

### `settings.py`

单例模式，通过 `AppSettings.instance()` 获取。

设置自动持久化到 `~/.stellaris_gui_editor/settings.json`。  
修改任意属性后立即调用 `save()`。

**新增设置项时：** 在 `_DEFAULTS` 字典中添加默认值，在类中添加 property。

---

## 3. 界面模块说明

### `canvas.py` / `widget_items.py`

- `GUICanvas`（QGraphicsView）：处理鼠标事件、视图变换
- `GUIScene`（QGraphicsScene）：管理所有 QGraphicsItem，维护 `_node_to_item` 映射
- `GUIWidgetItem`（QGraphicsItem）：渲染单个控件，处理选中/拖拽/缩放

**主要信号：**
```python
canvas.node_selected           # 选中控件改变
canvas.node_property_changed   # 属性通过画布改变
canvas.node_position_changed   # 位置改变（拖拽）
canvas.document_modified       # 文档被修改
```

### `main_window.py`

主窗口是所有组件的协调者（观察者模式）：
- 接收 canvas 的信号 → 更新 properties_panel、layer_panel、code_view
- 接收 properties_panel 的信号 → 通知 canvas 刷新渲染
- 管理 undo_stack，分发 Undo/Redo 命令

---

## 4. 数据流

```
用户拖拽控件
     ↓
canvas.py (GUIScene)
  │ 更新 WidgetNode.position
  │ 发送 node_position_changed
     ↓
main_window._on_node_position_changed()
  │ 调用 properties_panel.refresh_from_node()
  │ 调用 code_view.schedule_update()
     ↓
properties_panel 显示新坐标
code_view 异步刷新代码
```

```
用户在属性面板修改属性
     ↓
properties_panel._set_prop(key, value)
  │ 直接修改 WidgetNode.properties
  │ 发送 property_changed(node)
     ↓
main_window._on_property_edited(node)
  │ 调用 resolve_editor_layout_sizes()
  │ 调用 canvas.gui_scene.refresh_item(node)
  │ 调用 code_view.schedule_update()
```

---

## 5. 添加新控件类型

1. 在 `gui_model.py` 中：
   - 将类型名加入 `_WIDGET_KEYS_CANONICAL`
   - 在 `WIDGET_TYPES`、`WIDGET_LABELS`、`WIDGET_COLORS`、`DEFAULT_SIZE` 中添加对应条目

2. 在 `widget_items.py` 中：
   - 在 `GUIWidgetItem.paint()` 中为新类型添加渲染分支（若需特殊外观）

3. 在 `properties_panel.py` 中：
   - 若新类型有特殊属性，在 `set_node()` 末尾的 `setVisible()` 逻辑中处理显示/隐藏

4. 在 `widget_library.py` 中：
   - 将类型加入 `_populate()` 的分类列表

---

## 6. 添加新属性字段

在 `properties_panel.py` 中：

1. 在适当的 `_build_xxx_section()` 方法中创建 UI 控件（QLineEdit、QSpinBox 等）
2. 连接 `textChanged` / `valueChanged` 信号 → `_set_prop(key, value)`
3. 在 `set_node(node)` 的对应位置读取 `node.properties.get(key)` 并填充 UI
4. 将 key 加入 `_MANAGED_KEYS` 集合（防止在原始属性编辑器中重复显示）

---

## 7. 主题系统

`src/core/theme_manager.py` 中：

- 每套主题由 `QPalette` 构建函数 + QSS 字符串组成
- `AVAILABLE_THEMES` 字典定义所有可用主题

**添加新主题：**
1. 编写 `_build_xxx_palette(accent)` 函数
2. 编写 `_xxx_qss(accent)` 函数
3. 在 `AVAILABLE_THEMES` 中添加 `'key': ('显示名', '默认强调色')`
4. 在 `ThemeManager.apply()` 的 if-elif 链中添加分支

---

## 8. 打包发行

### Windows

```batch
packaging\build_windows.bat
```

脚本自动执行：安装依赖 → 生成图标 → 清理旧构建 → PyInstaller 打包

### 手动步骤

```bash
pip install -r requirements.txt pyinstaller
python packaging/create_icon.py
pyinstaller StellarisGUIEditor.spec --noconfirm
```

产物：`dist/StellarisGUIEditor/`（整个文件夹分发给用户）

### 替换应用图标

将正式设计的 ICO 文件放到 `assets/app_icon.ico`（256×256，包含多尺寸），
重新运行 `build_windows.bat`。

---

## 9. 测试

```bash
# 基础功能测试
python test_advanced.py

# 综合测试（包含画布渲染）
python test_comprehensive.py

# 若测试真实文件（可选）
set TEST_GUICORE_PATH=E:\...\your_file.guicore
python test_advanced.py
```

---

## 10. 扩展接口说明

本项目设计了以下扩展点，供未来社区开发：

### 自定义资源后端
`ResourceManager` 的 `decode_image_to_pixmap()` 方法使用多后端降级策略（pydds → ffmpeg → texconv → Pillow → imageio → OpenCV → Wand → Qt）。  
可在此方法中添加新的解码后端（按优先级插入）。

### 自定义导出格式
在 `src/codegen/` 中添加新模块（如 `json_exporter.py`），实现 `GUIDocument → str` 的转换函数，
然后在 `main_window.py` 的文件菜单中添加对应动作。

### 自定义主题
在 `theme_manager.py` 中参照现有主题添加新主题（见第 7 节）。

### 插件系统（规划中）
未来版本计划支持 Python 插件，接口草案：
```python
class EditorPlugin:
    def on_load(self, app_context): ...
    def on_node_selected(self, node): ...
    def on_document_saved(self, doc, path): ...
    def get_menu_actions(self): ...
```
