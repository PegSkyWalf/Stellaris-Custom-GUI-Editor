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

[Unreleased]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases/tag/v1.0.0
