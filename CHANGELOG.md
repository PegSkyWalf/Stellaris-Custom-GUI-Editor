# Changelog

所有版本的重要变更都记录在此文件中。  
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，  
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 计划中
- 多文档界面（同时打开多个 .gui 文件）
- 插件/扩展系统
- 快捷键自定义
- macOS / Linux 打包支持

---

## [1.4.0] - 2026-04-05

### 新功能

- **版本更新检查**：启动后 3 秒自动在后台检查 GitHub Releases 最新版本，发现新版本时弹出提示对话框（含"前往下载"/"跳过此版本"/"稍后提醒"三个选项）；"帮助"菜单新增"检查更新"一项，支持随时手动触发；检查间隔、是否自动检查均可在设置中配置
- **精灵图库大幅重构**：
  - 标题栏新增统计徽章（显示当前显示数量 / 总数量）
  - 新增类型过滤器（全部 / 固定尺寸 spriteType / 可拉伸 quadTextureSprite）
  - 改进预览区：精灵名称、类型徽章、贴图路径、帧数信息一目了然；点击预览图可应用到选中控件
  - 智能懒加载：仅渲染当前视口内可见的缩略图，大型模组下不再卡顿
  - 右键菜单：在文件管理器中打开注册文件、复制精灵名 / GFX 注册代码 / 纹理路径
- **事件关联面板增强**：
  - 事件列表显示彩色类型标签（`[country_event]`、`[fleet_event]` 等）、事件标题与选项数
  - 新增搜索框，支持按事件 ID 或标题实时过滤
  - 双击事件条目直接应用 GUI 预览；右键菜单提供复制路径 / 事件 ID
  - 详情面板改为彩色 HTML 格式，选项、文件路径清晰展示
- **Button Effects 编辑器增强**：
  - 文件操作改为树形右键菜单（新建文件、删除文件、在文件管理器中打开）
  - 支持在模组目录直接新建 `.txt` 文件，并自动填入文件头模板
  - 原版游戏文件标记为只读，防止意外覆盖
- **欢迎向导新增语言选择步骤**：语言选择作为第 0 步显示在向导最前面；选项以各语言母语标注（简体中文 / English / …）；确认语言后其余向导页面以所选语言重新构建；支持返回修改语言并自动刷新后续页面

### 改进

- **保存时完整保留注释**（严重修复）：之前版本在修改任何控件属性后，该控件块内所有子控件的注释、格式信息均被清除；现在 patch 保存策略在节点自身属性改变时仅重写其直属属性头部，所有子节点原始文本（含注释）完整保留
- **属性面板修改正确写入文件**：`_set_prop` 现在在修改属性后立即调用 `mark_source_modified()`，确保通过面板编辑的字体、文本、精灵名等属性在保存时不再被忽略（之前只有通过位置/尺寸 setter 修改的属性才会写入）
- **旋转参数移入"位置与大小"区块**：旋转属性现对 `iconType`、`buttonType`、`effectButtonType` 等使用精灵图的控件可见，并统一放置在位置区块而非末尾的"其它"折叠区
- **旋转方向修正**：编辑器画布中旋转方向与游戏内一致（正值逆时针），之前方向相反
- **代码视图默认开启实时同步**：新建窗口时"实时同步"默认启用，代码编辑即时同步到画布，无需手动点击应用
- **画布状态跨重载保留**：属性修改、撤销操作触发画布刷新时保留摄像机位置、图层可见性、虚拟编组可见性，不再跳回默认视图
- **属性刷新精准化**：属性修改后只重绘受影响的节点及其祖先，不再触发全画布刷新，提升大型文件下的编辑流畅度
- **跨平台文件管理器支持**：所有"在文件管理器中打开"操作统一为跨平台实现（Windows Explorer / macOS Finder / Linux xdg-open）
- **精灵图来源文件追踪**：`SpriteInfo` 新增 `source_file` 字段，记录定义该精灵的 `.gfx` 文件路径，供精灵图库右键菜单使用
- **主题颜色 API 扩展**：`ThemeManager` 新增 `bg_color()`、`base_color()`、`border_color()`、`input_bg_color()`、`is_dark()`、`secondary_bg_color()`、`selection_bg_color()` 等静态方法，UI 组件可获取更精细的主题颜色值
- **数学表达式解析增强**：`@[expr]` 块内现支持裸标识符变量语法（如 `@[ radius / 2 ]`），与显式 `@varname` 写法兼容，修复部分使用标准写法的 Mod 文件解析报错
- **GUIDocument 存储变量表**：解析时记录文件内所有 `@变量 = 值` 定义，供后续 round-trip 保存和表达式求值使用
- **英文翻译条目补充**：新增 47 条英文翻译，覆盖文件操作、精灵图库、事件关联等模块

### 内部

- 新增模块：`src/core/update_checker.py`（GitHub Releases API 检查）
- `src/codegen/gui_writer.py`：新增 `_write_widget_header()` 辅助函数，实现属性头部与子节点原始文本的分离 patch 策略
- `src/ui/dialogs.py`：新增 `UpdateDialog` 更新提示对话框类

---

## [1.2.0] - 2026-04-02

> ⚠️ **重要提示：本工具会直接修改 `.gui` 文件。在使用前，请务必备份所有原始资源文件。**  
> 建议在独立的测试 Mod 目录中操作，切勿在未备份的游戏原版文件上直接编辑。

### 新功能

- **智能吸附对齐**（`SnapEngine`）：拖拽控件时显示实时辅助线，支持边缘对齐、中轴对齐；吸附阈值、颜色、间距可在设置中调整
- **线性阵列**（`编辑 → 阵列与镜像 → 线性阵列`）：指定副本数和 X/Y 偏移，批量生成均匀分布的副本，所有副本自动获得唯一名称
- **圆形阵列**（两种模式，含实时预览）：
  - **圆心模式**：以选中控件为圆心，副本均匀分布在外环
  - **环上模式**：选中控件作为环上起点（angle=0），其余副本等间距闭合成环
  - 对话框内嵌 200×200 实时预览画布，模式与参数变化即时可见
  - 中心坐标自动以选中控件几何中心为默认值，不再依赖画布中心（旧版本存在 ~800px 偏差的 bug）
- **镜像**（`编辑 → 阵列与镜像 → 镜像`）：以选中控件集合的边界中心为轴，支持垂直轴（左右翻转）和水平轴（上下翻转）；可选"保留原件"模式（镜像复制）或纯翻转
- **对齐工具**（`编辑 → 对齐`）：
  - 对齐系列：左对齐、右对齐、顶对齐、底对齐、水平居中、垂直居中
  - 均匀分布：水平间距均匀、垂直间距均匀
  - 相同尺寸：相同宽度、相同高度、相同尺寸
  - 所有对齐操作可撤销
- **自动唯一命名**：所有复制操作（Ctrl+D、线性/圆形阵列、镜像复制、撤销重放）均自动为副本追加 `_1`、`_2` 等序号后缀，彻底消除重复名称；序号剥离现有后缀后重新计算，不会产生 `button_1_1_2` 等叠加
- **重复名称警告面板**（底部停靠，与代码视图同排）：实时扫描文档内所有重复 `name` 值，IDE 风格展示；点击条目自动选中并滚动到对应控件；文档每次修改后自动刷新
- **SVG 图标系统**（`IconProvider`）：全部工具栏/面板图标改为路径填充 SVG，支持任意颜色染色；图标随主题切换自动刷新（之前版本图标颜色固定不变）
- **虚拟编组：从选中控件建组**：在虚拟编组面板工具栏新增"从选中建组"按钮，一键将画布当前选中的已命名控件打包为新编组
- **默认显示图层面板**：启动后底部标签默认激活"图层"标签页，而非虚拟编组

### 改进

- **主题感知文字颜色**（30+ 处变更）：所有 UI 文件的次要说明文字、提示文字、标签颜色从硬编码 `#888`/`#666`/`#aaa` 统一改为 `ThemeManager.muted_color()`，在浅色主题下不再显示为不可见的灰色；强调色同理改用 `ThemeManager.accent_color()`。语义性状态色（红色错误、绿色成功、橙色警告）保留不变。
- **"关于"对话框重设计**：采用强调色顶部横幅（应用名称、英文名、版本标签、构建日期）；正文区块包含功能列表双列网格、作者信息、GitHub/发布页/反馈/许可证四个外链；彻底移除旧版堆砌式布局
- **`ThemeManager` 静态辅助方法**：新增 `muted_color()`、`accent_color()`、`fg_color()` 三个静态方法，UI 层无需持有 `ThemeManager` 实例即可获取当前主题颜色值；`apply()` 执行时同步写入类级别缓存

### 修复

- **圆形阵列坐标错误**：旧版本"圆心模式"默认使用画布坐标中心（960, 540），当选中控件位于其他位置时副本出现在距目标数百像素之外的位置。现在圆心模式自动计算选中控件的几何中心点作为圆心，无需手动输入坐标。
- **圆形阵列对话框崩溃**（`AttributeError: 'QGraphicsView' has no attribute 'RenderHints'`）：`setRenderHint()` 参数应为 `QPainter.RenderHint.Antialiasing` 枚举值，而非字符串；已修复，预览正常显示。
- **对齐菜单 `make_same_size` 崩溃**（`AttributeError: 'GUICanvas' object has no attribute 'make_same_size'`）：`make_same_size()` 方法属于 `GUIScene`，菜单槽函数错误通过 `self._canvas` 调用；已改为 `self._canvas.gui_scene.make_same_size(...)`。
- **图标主题切换后不刷新**：主题切换时 `IconProvider` 会清空缓存，但已装入 `QAction` 的 `QIcon` 对象不会随缓存失效而更新。现在主题切换后统一调用各面板的 `refresh_icons()` 方法，重新染色所有图标。

### 已知妥协与潜在风险

- **圆形阵列"环上模式"不移动原件**：当前实现中，选中控件不会被移动到环上的 angle=0 位置，仅在其余角度生成副本。如需原件也在环上，需手动将其移至目标位置后再执行阵列。原因：移动原件需要额外的 `MoveWidgetCommand`，与坐标系转换细节耦合，暂以此行为为妥协。
- **吸附辅助线在高密度画布下性能**：每次拖拽移动均重新计算所有控件的边界进行吸附比较；当画布控件数量超过 ~200 时，拖拽帧率可能轻微下降。
- **重复名称警告面板不追踪跨文件重复**：目前仅扫描当前打开的单个 `.gui` 文件。群星允许同名控件存在于不同文件（通过 `overwrite` 机制），此类跨文件重名不在警告范围内。
- **SVG 图标颜色使用主题快照**：图标颜色在主题切换时刷新，但若通过自定义强调色修改颜色后未重启对话框，对话框内的图标可能保持旧颜色，重新打开后正常。

### 内部

- 新增模块：`src/core/snap_engine.py`、`src/core/array_mirror.py`、`src/ui/snap_guide_overlay.py`、`src/ui/array_dialogs.py`、`src/ui/icon_provider.py`、`src/ui/name_warnings_panel.py`
- `src/core/gui_model.py` 新增 `generate_unique_name()`、`make_names_unique()` 辅助函数，供 undo、canvas 各克隆入口统一调用
- `src/core/array_mirror.py`：`compute_circular_array()` 增加 `mode` 参数，返回 `(copies, original_moves)` 元组，支持 `center` / `on_ring` 双模式
- `src/core/undo.py`：`DuplicateWidgetCommand.execute()` 现在在插入前调用 `make_names_unique()` 确保名称不冲突
- `src/core/theme_manager.py`：`apply()` 写入 `_current_muted`、`_current_accent`、`_current_fg` 三个类级别变量
- `.gitignore` 新增 `.claude/`、`_tmp_*.py`、`*.groups.json`、构建产物排除规则

---

## [1.1.0] - 2026-04-01

### 修复

- **加载卡死（严重）**：`_index_gfx_directory` 会递归扫描 `gfx/models/`、`gfx/fonts/`、`gfx/particles/` 等从不含精灵图定义的 3D 资源目录，导致在某些大型模组（如含数百个 .gfx 网格定义的目录）上解析器长时间挂起（实测单文件挂起 91 秒）。现已将这些目录加入跳过列表，并增加 512 KB 文件大小上限作为第二道防护。
- **取消加载无响应**：取消检测点仅存在于各加载阶段之间，若线程卡在单个文件的解析内部则永远无法响应取消。上述卡死修复同时解决了此问题。
- **启动时 UI 双重刷新**：`_ResourceLoaderThread` 将自定义信号命名为 `finished`，与 QThread 内建的 C++ `finished` 信号冲突，导致 PySide6 在线程结束时触发两次槽函数，每次启动均执行两遍精灵图库重建和文件浏览器刷新。已将自定义信号重命名为 `load_finished`，`_GuiLoadThread` 中同名问题一并修复。
- **事件选项按钮位置错误**：当事件同时满足以下条件时，选项按钮容器（如 `ae_dialogue_button`）显示在画布默认位置（0,0）而非 `option_list` 容器内：事件有 `custom_gui` 但无 `custom_gui_option`，且各选项也未设置 `custom_gui` 属性（这是群星模组中的常见写法）。现通过扫描当前 GUI 文件的顶层节点自动检测选项按钮模板（含 `option_button` 子部件或 `OPTION_TEXT` 占位文本），在事件上下文激活时将模板隐藏并在 `option_list` 内按选项顺序重新渲染；最后一个选项优先使用名称含 `last` 的模板变体。
- **崩溃：`ev.desc` 为列表类型**：Stellaris 事件文件允许同一块内出现多个 `desc = ...` 条目（用于条件描述），`_parse_block` 会将其积累为列表，后续传入 `rm.get_loc()` 时调用 `str.strip()` 崩溃。已通过 `_str_or_first()` 辅助函数和 `get_loc()` 的防御性类型检查修复，同样适用于 `id`、`title` 字段。

### 改进

- **运行日志全面增强**：
  - 日志格式新增线程名字段（`[MainThread]` / `[Dummy-N]`），便于区分 UI 线程与后台加载线程
  - 所有主要加载阶段（游戏目录、模组目录、GFX 扫描、本地化解析）均添加计时日志
  - 单文件解析超过 1 秒时输出 WARNING 日志并附带文件路径
  - 日志文件大小上限从 2 MB 提升至 5 MB
- **文件浏览器性能**：刷新时仅扫描模组目录下的 `interface/` 子目录，不再递归遍历整个模组根目录，大幅减少刷新耗时（由数秒降至 30 ms 以内）
- **GFX 目录扫描**：新增循环目录联接点检测（基于 `st_dev + st_ino`），防止 Windows NTFS 联接点导致的无限递归
- **设置对话框**：新增"显示日志文件路径"标签和"清除上次加载的模组路径"按钮，方便排查问题

### 内部

- `_ResourceLoaderThread` 和 `_GuiLoadThread` 的自定义完成信号统一重命名为 `load_finished`，消除与 QThread 内建信号的命名冲突
- `event_parser.scan_event_dirs` 切换为 `_safe_walk`，统一循环目录防护逻辑
- `GUIScene` 新增 `_node_contains_option_button()` 和 `_find_option_template_names()` 辅助方法，支持无 `custom_gui_option` 时的选项 GUI 自动推断

---

## [1.0.0] - 2026-03-26

首个公开发布版本。从零构建，历经多轮迭代完成。

### 核心解析引擎

- **PDX Script 完整解析器**：词法分析器（Tokenizer）+ 语法解析器（Parser），支持嵌套块、变量定义（`@VAR = value`）、注释、布尔值、字符串/数字混合格式
- **双精灵图系统**：`spriteType`（固定尺寸，`scale` 调整大小）与 `quadTextureSprite` / `corneredTileSpriteType`（9 块可拉伸，`size` 控制实际尺寸）完全分开处理
- **完整 orientation + origo 定位系统**：精确还原群星双锚点坐标系，渲染位置与游戏内一致；支持 `UPPER_LEFT`、`CENTER`、`LOWER_RIGHT` 等全部 9 个方向值
- **隐式容器尺寸计算**：未声明 `size` 的容器自动以子控件包围盒确定编辑器显示尺寸；以 `(0,0)` 为子控件锚点参考避免 `orientation=center` 子控件的错误偏移
- **多格式图像解码**：通过 `pydds`、Pillow、imageio 多后端支持 DDS/DXT1/DXT3/DXT5/BC7/TGA/PNG

### 支持的控件类型

`containerWindowType`、`iconType`、`buttonType`、`effectButtonType`、`instantTextBoxType`、`textBoxType`、`editBoxType`、`checkBoxType`、`scrollAreaType`、`background`（作为 containerWindowType 子属性）、`extendedScrollbarType`（含子元素）

### 可视化画布

- QGraphicsScene / QGraphicsView 实现，1920×1080 参考分辨率（可配置）
- 鼠标滚轮缩放（25%–400%），中键拖拽平移，Ctrl+0 适应画布
- 选择手柄（拖拽移动，8 向调整大小），网格对齐
- 控件类型彩色框架标注，精灵图渲染（带占位棋盘格）
- 预览模式（Ctrl+P）：隐藏框线、标签、选择手柄

### 属性面板

- 动态生成，覆盖所有常用属性字段
- **原始属性编辑器**：以键值表格形式编辑任意属性，未知属性不丢失
- 本地化键实时查询显示翻译文本
- 属性修改即时同步到画布和代码视图

### 代码视图

- PDX Script 语法高亮（关键字、字符串、数字、注释分色）
- 在画布中选中控件时，代码视图**按结构路径精准滚动高亮**，避免同名控件混淆
- 直接在代码视图编辑，回写到数据模型

### 图层面板

- 树形展示控件层次，支持多选
- 点击节点即选中并高亮画布中的对应控件
- 可见性开关（与虚拟编组可见性完全解耦）

### 虚拟编组系统

- 独立于 `.gui` 文件结构的分组管理
- 以侧车文件 `*.groups.json` 持久化，不修改 `.gui` 文件
- 编组可见性与图层面板可见性互不干扰

### 资源管理系统

- **Steam 注册表自动检测**：Windows 下自动定位群星安装目录
- 扫描并索引游戏原版及全部模组的 `.gfx` 精灵图定义（已验证：原版 7900+ 精灵图）
- 解析 `.yml` 本地化文件（UTF-8 BOM，已验证：140,937+ 条目）
- 解析事件文件（`.txt`）获取 `custom_gui` 引用关联
- **异步后台线程加载**：启动时不卡顿，进度条实时提示

### 撤销/重做

- 命令模式（Command Pattern）实现，最多 100 步
- 支持：移动控件、修改属性、添加控件、删除控件、复制控件
- 复合操作作为单条历史记录

### 主题系统

- 深色（默认）、浅色、深海蓝三套主题
- QPalette + QSS 双轨实现，全界面主题感知（含画布、代码视图、精灵预览等）
- 自定义强调色

### 首次启动向导

- 三步引导：游戏目录配置 → 主题选择 → 完成
- 包含快速上手提示

### 其他功能

- **事件关联面板**：自动扫描事件文件中的 `custom_gui` 引用
- **Button Effects 编辑器**：可视化编辑 `common/button_effects/*.txt`
- **GFX 精灵注册生成器**：快速生成 `.gfx` 代码块
- **精灵图库**：7900+ 精灵图浏览、搜索、预览、一键应用
- **预设系统**：保存/加载控件模板

### 日志与调试

- 轮转日志写入 `~/.stellaris_gui_editor/logs/`
- 全局异常捕获，崩溃前写入日志

### 打包与分发

- PyInstaller 打包配置（`StellarisGUIEditor.spec`）
- Windows 一键构建脚本（`build.bat`）：自动安装依赖、生成图标、编译、打包 ZIP
- **VC++ 运行时 DLL 随包分发**（`vcruntime140.dll` 等），解决目标机器缺少 Visual C++ Redistributable 导致的启动失败
- 构建脚本自动回退到 `py launcher`（兼容未将 Python 加入 PATH 的用户）

---

[Unreleased]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/compare/v1.2.0...v1.4.0
[1.2.0]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases/tag/v1.0.0
