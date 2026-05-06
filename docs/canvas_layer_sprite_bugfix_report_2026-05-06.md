# 画布、图层与精灵图库问题诊断修复报告

日期：2026-05-06  
分支：`main`  
基线：`HEAD` 与 `origin/main` 均为 `060c23180d73fc37d5e6416ad8299288c4702ecc`  
状态：已完成本地验证，随本次修复提交并推送到 GitHub

## 1. 项目与约束理解

本项目是 PySide6 桌面应用，用于可视化编辑 Stellaris Clausewitz `.gui` 文件。

主要架构：

- `src/core/`：纯模型、解析、资源索引、撤销命令等核心逻辑。
- `src/ui/`：PySide6 UI、画布、属性面板、图层面板、控件库、精灵图库。
- `src/codegen/`：`.gui` 保留式序列化与输出。
- 根目录 `test_*.py`：轻量脚本式回归测试，GUI 测试需支持 headless。

关键技术路径：

- 加载：`.gui` -> `PDXParser` -> `WidgetNode` 树 -> `GUIDocument` -> 画布 / 图层 / 属性 / 代码视图。
- 编辑：UI 操作 -> `Command` / `UndoStack` 或受控模型变更 -> `GUIDocument` -> 多视图同步。
- 保存/代码视图：`GUIDocument` -> `gui_writer.write_document_preserving()` -> 保留原源码注释和未修改块。
- 坐标：`orientation` 表示父级锚点，`origo` 表示自身锚点，核心换算在 `compute_widget_topleft()` 与 `reverse_compute_position()`。

已遵守本轮约束：

- 已阅读 `CLAUDE.md` 和 `AGENTS.md`，保持 `ui -> core` 的依赖方向。
- 工作开始前确认远端备份存在：本地 `HEAD` 与 `origin/main` 一致。
- 未执行任何 `git push`。
- 未改动已有未跟踪的 `AGENTS.md`。

## 2. 根因诊断

### 2.1 撤回后画布控件瞬间偏移或错乱

主要根因是新增/复制相关操作存在“先改模型，再把命令塞进 undo 栈”的混合路径。部分命令在 redo 或重复 execute 时会再次把同一个 `WidgetNode` 引用插入父节点或根节点，导致模型树出现重复对象引用。之后画布 reload、图层同步或 writer 遍历模型时，同一个对象可能被当成多个控件处理，从而表现为位置错乱、索引跳错和渲染偏移。

修复方向：

- `AddWidgetCommand` 和 `DuplicateWidgetCommand` 改为幂等。
- 画布新增、复制、阵列、镜像复制统一由命令执行模型变更。
- 删除命令防御性清理重复引用。

### 2.2 修改容器裁切属性或点击刷新后布局错乱

根因集中在隐式尺寸容器。Stellaris 中没有显式 `size` 的容器，其子节点锚点计算不能把编辑器推导出的包围盒尺寸再当作父级锚点尺寸，否则 `orientation = CENTER` 等锚点会随推导尺寸变化而产生二次偏移。刷新画布会重新计算这些尺寸，因此问题在刷新、属性变化后更明显。

修复方向：

- 隐式容器的子控件锚点参考统一使用 `(0, 0)`。
- 画布构建、单项刷新、拖拽写回都复用同一套父级布局尺寸逻辑。
- 属性编辑后强制重新计算布局尺寸，再刷新受影响节点和祖先。

### 2.3 图层移动后代码视图跳转到错误控件

代码视图的结构定位依赖“当前模型顺序”和“生成代码顺序”一致。原先保留式 writer 会倾向按旧源码 span 顺序输出未修改块；当图层顺序已经被用户调整后，代码仍可能保持旧顺序，导致结构路径和代码块不再对应。

修复方向：

- writer 检测根节点和子节点顺序是否已偏离原始源码 span 顺序。
- 一旦发生同级重排，输出顺序以当前模型树为准。
- 图层结构变化后强制更新代码视图。

### 2.4 图层重排或层级切换导致控件位置偏移

拖拽图层树会改变父子关系。若直接把节点挂到新父级而不重算 `position`，原来的坐标会被解释成新父级坐标，从而发生视觉跳动。

修复方向：

- 图层面板在 drop 前后记录结构快照。
- 主窗口根据旧画布 scene 坐标反推新父级下的 Stellaris `position`。
- 重建画布前保持视觉 scene 位置稳定。

### 2.5 图层选中容器后从控件库新增未进入容器

原实现只看画布当前选中项，图层选中时可能没有正确更新插入父级；并且缓存父级优先级可能导致插入到上一次容器。

修复方向：

- 主窗口维护插入父级，但优先以当前选择实时计算。
- 选中容器时，新控件插入该容器；选中容器内控件时，新控件插入其父容器。
- 新增后同步画布、属性面板、图层面板和代码视图。

### 2.6 控件库无法直接拖入画布或容器

原控件库没有 drag MIME 协议，画布也没有对应 drop 接收逻辑。

修复方向：

- 控件库列表支持 `application/x-stellaris-widget-type` 拖拽。
- 画布接收拖放，按鼠标位置寻找最深层可用容器。
- 拖到容器上则作为子控件创建；拖到空白处则创建为根控件。

### 2.7 左上图层上移/下移语义混乱

图层面板显示顺序是“视觉最上层在列表上方”，而模型顺序是后绘制节点在更高 Z 值。此前根节点和子节点的显示/写回顺序不完全一致，容易造成按钮语义与实际结果反向。

修复方向：

- 图层面板显示根和子节点时统一反向展示。
- 从树写回模型时统一反向恢复。
- 上移表示提高 Z 层级，下移表示降低 Z 层级。
- 画布对所有兄弟项重建 Z 值，而不是只改当前项。

### 2.8 精灵图库显示所有依赖模组资源

资源管理器会加载原版、当前模组和额外依赖模组，但精灵图库之前没有来源范围过滤。结果是依赖模组中的精灵也直接暴露在默认列表，容易让当前模组引用不存在于发布内容中的资源。

修复方向：

- `SpriteInfo` 增加 `source_scope`：`vanilla` / `current_mod` / `dependency`。
- 默认精灵图库只显示 `current_mod + vanilla`。
- UI 增加范围筛选：`当前+原版`、`仅当前`、`全部资源`。
- 仍保留“全部资源”作为高级排查入口。

### 2.9 `iconType` 误用 `quadTextureSprite`

经实测，Stellaris 的 `iconType` 不支持 `quadTextureSprite`，应使用 `spriteType`。此前编辑器会根据精灵资源是否可拉伸，把 `corneredTileSpriteType` 分配为 `quadTextureSprite`，这对 `iconType` 会生成无效 GUI 字段，并可能造成画布预览与游戏实际表现不一致。

修复方向：

- `WidgetNode.get_sprite_name()` 对 `iconType` 只读取 `spriteType`。
- `ResourceManager.get_widget_render_mode()` 对 `iconType` 忽略 `quadTextureSprite`，并把 `spriteType` 按固定精灵渲染。
- 精灵图库分配到 `iconType` 时始终写入 `spriteType`，并清理残留 `quadTextureSprite`。
- 属性面板在选中 `iconType` 时禁用 `quadTextureSprite` 输入。
- 代码生成层对被重新生成的 `iconType` 块做兜底转换：残留 `quadTextureSprite` 会转为 `spriteType`。

### 2.10 右键“更改控件类型”没有生效

根因是类型切换只改了内存中的 `node.widget_type`，但没有标记 `_source_modified`。在保留式 writer 路径中，未标记修改的源码块会继续复用旧文本，因此代码视图/保存结果仍可能保留旧控件类型，看起来像操作没有生效。

修复方向：

- 类型切换后调用 `mark_source_modified()`，确保保留式写回会重新生成该块头部。
- 重新计算编辑器布局尺寸，刷新被改节点、子节点和祖先节点。
- 发出属性变更信号，让属性面板、图层面板和代码视图同步显示新类型。
- 切换到 `iconType` 时把旧 `quadTextureSprite` 转为 `spriteType`，避免生成无效字段。
- 切换到容器类型时移除直接精灵属性，保留容器应使用的背景子块路径。

## 3. 本地改动范围

核心模型与撤销：

- `src/core/undo.py`
- `src/core/gui_model.py`

画布与控件项：

- `src/ui/canvas.py`
- `src/ui/widget_items.py`

图层、主窗口和控件库：

- `src/ui/layer_panel.py`
- `src/ui/main_window.py`
- `src/ui/properties_panel.py`
- `src/ui/widget_library.py`

代码生成：

- `src/codegen/gui_writer.py`

资源与精灵图库：

- `src/core/resource_manager.py`
- `src/ui/sprite_library.py`

新增回归测试：

- `test_undo_integrity.py`
- `test_layer_roundtrip_order.py`
- `test_layout_stability.py`
- `test_sprite_scope.py`
- `test_widget_type_sprite_rules.py`

## 4. 验证结果

已运行并通过：

- `.\.venv\Scripts\python.exe -m py_compile src\codegen\gui_writer.py src\core\resource_manager.py src\core\undo.py src\core\gui_model.py src\ui\canvas.py src\ui\layer_panel.py src\ui\main_window.py src\ui\properties_panel.py src\ui\sprite_library.py src\ui\widget_items.py src\ui\widget_library.py test_widget_type_sprite_rules.py`
- `.\.venv\Scripts\python.exe test_undo_integrity.py`
- `.\.venv\Scripts\python.exe test_layer_roundtrip_order.py`
- `.\.venv\Scripts\python.exe test_layout_stability.py`
- `.\.venv\Scripts\python.exe test_sprite_scope.py`
- `.\.venv\Scripts\python.exe test_widget_type_sprite_rules.py`
- `.\.venv\Scripts\python.exe test_imports.py`
- `.\.venv\Scripts\python.exe test_parser.py`
- `.\.venv\Scripts\python.exe test_roundtrip.py`
- `.\.venv\Scripts\python.exe test_advanced.py`
- `.\.venv\Scripts\python.exe test_comprehensive.py`
- `git diff --check`

已知非阻塞现象：

- 当前环境可能输出日志文件权限警告：`Permission denied: C:\Users\陈\.stellaris_gui_editor\logs\stellaris_gui_editor.log`。该警告不影响本轮功能测试，但属于本机日志目录权限问题。

## 5. 人工验收清单

建议按以下顺序验收：

1. 新建控件、撤销、重做，确认画布位置不跳动，图层树没有重复节点。
2. 复制容器内控件，撤销、重做，确认子控件只出现一次且仍在原父容器下。
3. 修改容器 `clipping` 或其他属性后，确认容器内子控件不发生整体偏移。
4. 点击工具栏“刷新画布”，确认当前布局稳定。
5. 在图层面板使用上移/下移，确认显示层级符合预期且画布位置不变。
6. 在图层面板拖拽控件到另一个容器，确认视觉位置不跳动，代码视图定位仍跳到正确控件。
7. 在图层面板选中容器后，从控件库双击或按钮新增控件，确认新控件进入该容器。
8. 从控件库拖拽控件到画布空白处，确认创建根控件。
9. 从控件库拖拽控件到已有容器区域，确认创建为该容器子控件。
10. 打开精灵图库，默认应只显示当前加载模组与原版精灵；切换“全部资源”后才显示依赖资源。
11. 给 `iconType` 分配可拉伸精灵，确认代码写出 `spriteType`，不会写出 `quadTextureSprite`。
12. 右键使用“更改控件类型”，确认属性面板、图层面板、代码视图和保存结果都显示新类型。

## 6. 剩余风险

- 保留式 writer 在发生同级重排时会更积极地重写该同级块，能保证顺序和代码定位正确，但被重排区域内的局部空行/注释格式可能不如完全未改动块那样原样保留。
- 图层树拖拽依赖 Qt `InternalMove` 行为，复杂多选拖拽仍建议重点人工验证。
- 控件库拖拽当前使用默认名称直接创建，不弹命名对话框；这是为满足“直接拖拽到画布中”的交互目标。
- 对未被编辑器重新生成的旧源码块，保留式 writer 会继续原样保留；若旧文件中已经存在无效 `iconType.quadTextureSprite`，需在该控件被编辑后才会触发自动转换。

## 7. 最终仓库状态

- 开工前确认 `HEAD` 与 `origin/main` 一致。
- 提交前再次执行 `git fetch origin`，确认 `HEAD...origin/main = 0 0`。
- 本修复将提交并推送至 `origin/main`。
- `AGENTS.md` 是开工前已存在的未跟踪文件，本轮未纳入修改。
