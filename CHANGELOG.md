# Changelog

所有版本的重要变更都记录在此文件中。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 计划中
- 多文档界面（同时打开多个 .gui 文件）
- 插件/扩展系统
- 导出为不同格式
- 快捷键自定义

---

## [1.0.0] - 2026-03-26

### 新增
- 可视化画布编辑器：拖拽控件、调整大小、对齐工具
- 正确实现 Stellaris `orientation` + `origo` 定位系统
- DDS/BC7 贴图渲染（通过 pydds、Pillow、imageio、ffmpeg 多后端）
- 9 块（corneredTileSpriteType）精灵图渲染
- PDX 脚本语法高亮代码视图，支持实时编辑回写
- 属性面板：支持所有常用属性，新增**原始属性编辑器**可编辑任意属性
- 精灵图库：7900+ 原版精灵图浏览与预览，支持类型筛选
- 图层面板：可见性/锁定/Z 轴排序
- 虚拟编组系统（独立于 .gui 脚本）
- 事件关联面板：自动扫描事件文件中的 `custom_gui` 引用
- Button Effects 编辑器：可视化编辑 `common/button_effects/*.txt`
- GFX 精灵注册文件生成器
- 预设系统：保存/加载控件模板
- 撤销/重做（100 步，可在设置中调整）
- 自动保存（可配置间隔）
- 本地化预览：解析 `.yml` 文件并在属性面板显示翻译文本
- 多语言本地化切换（工具栏语言选择器）
- **首次启动向导**：引导配置游戏目录与界面主题
- **主题系统**：深色（默认）、浅色、深海蓝，支持自定义强调色
- **Steam 注册表自动检测**：Windows 下自动查找游戏安装路径
- **日志系统**：写入 `~/.stellaris_gui_editor/logs/`，便于排查问题
- 状态栏游戏/模组加载状态指示器
- 帮助菜单快捷键列表对话框
- 工作区文件夹管理（快速切换模组）
- 跨平台支持：Windows / macOS / Linux

### 技术架构
- `src/core/` — PDX 解析器、GUI 数据模型、资源管理器、设置、撤销系统
- `src/ui/` — PySide6 界面层，各功能模块解耦
- `src/codegen/` — .gui/.gfx 脚本生成器
- PyInstaller 打包配置，Windows 一键构建脚本
- GPL-3.0 开源许可证

---

[Unreleased]: https://github.com/YOUR_ORG/StellarisGUIEditor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/YOUR_ORG/StellarisGUIEditor/releases/tag/v1.0.0
