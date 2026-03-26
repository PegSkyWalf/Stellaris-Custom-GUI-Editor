# 贡献指南 / Contributing Guide

感谢你有兴趣为群星 GUI 编辑器做出贡献！  
Thank you for your interest in contributing to the Stellaris GUI Editor!

---

## 开发环境搭建

### 前提条件

- Python 3.10 或更高版本
- Git

### 克隆与安装

```bash
git clone https://github.com/YOUR_ORG/StellarisGUIEditor.git
cd StellarisGUIEditor

# 创建虚拟环境（推荐）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py
```

### 目录结构

```
StellarisGUIEditor/
├── main.py                     # 入口
├── requirements.txt
├── StellarisGUIEditor.spec     # PyInstaller 配置
├── assets/                     # 图标等静态资源
├── packaging/                  # 构建脚本
├── docs/                       # 文档
└── src/
    ├── core/                   # 核心逻辑（解析、模型、资源、设置）
    ├── ui/                     # 界面层（PySide6）
    └── codegen/                # 代码生成器
```

详细说明见 `docs/development.md`。

---

## 分支策略

| 分支 | 用途 |
|------|------|
| `main` | 稳定发布版本 |
| `develop` | 开发集成分支 |
| `feature/xxx` | 新功能开发 |
| `fix/xxx` | Bug 修复 |

**工作流程：**
1. Fork 本仓库
2. 从 `develop` 创建 `feature/your-feature` 分支
3. 完成开发，提交时遵循下方提交规范
4. 提交 Pull Request 到 `develop` 分支

---

## 提交规范（Conventional Commits）

```
<类型>(<范围>): <简短描述>

[可选详细说明]

[可选关联 Issue]
```

**类型：**
| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 仅文档变更 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（非新功能、非 Bug 修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建、依赖等杂项 |

**示例：**
```
feat(canvas): 添加对齐参考线功能

当拖动控件时显示智能对齐参考线，帮助精确定位。

Closes #42
```

---

## 如何报告 Bug

请使用 [Bug 报告模板](.github/ISSUE_TEMPLATE/bug_report.md)，
尽量包含以下信息：
- 操作系统与版本
- Python 版本
- 复现步骤
- 日志文件（位于 `~/.stellaris_gui_editor/logs/`）

---

## 如何提交功能请求

请使用 [功能请求模板](.github/ISSUE_TEMPLATE/feature_request.md)，
描述你的使用场景和期望的功能效果。

---

## 代码规范

- 遵循 PEP 8，最大行宽 110 字符
- 所有公开函数/类需有 docstring
- 中文注释、英文变量名
- 新功能必须不破坏现有功能（运行 `python test_advanced.py` 和 `python test_comprehensive.py` 验证）

---

## Pull Request 审核标准

- [ ] 代码通过现有测试
- [ ] 新增/修改功能有对应文档更新
- [ ] 提交历史清晰（必要时 squash）
- [ ] 没有引入新的硬编码路径或 magic number

---

## 许可证

提交代码即表示你同意以 GPL-3.0 许可证授权你的贡献。
