# 项目主人操作指引
## 群星 GUI 编辑器 — 零基础 GitHub 上传与日常管理手册

> 本文档专为不熟悉 GitHub 的项目负责人编写，使用最简单的步骤完成每一项操作。

---

## 目录

1. [项目现在是什么状态](#1-项目现在是什么状态)
2. [上传项目到 GitHub（首次）](#2-上传项目到-github首次)
3. [日常更新代码（有修改时）](#3-日常更新代码有修改时)
4. [打包发布 EXE 给用户](#4-打包发布-exe-给用户)
5. [在 GitHub 发布新版本](#5-在-github-发布新版本)
6. [回应社区 Issues（问题反馈）](#6-回应社区-issues问题反馈)
7. [合并社区贡献的代码（Pull Request）](#7-合并社区贡献的代码pull-request)
8. [修改 GitHub 地址（替换 YOUR_ORG）](#8-修改-github-地址替换-your_org)
9. [常见问题与解决方案](#9-常见问题与解决方案)

---

## 1. 项目现在是什么状态

经过本次重构，项目已具备：

| 已完成 | 说明 |
|--------|------|
| ✅ 主题系统 | 深色/浅色/深海蓝三套主题，可在设置中切换 |
| ✅ 首次启动向导 | 新用户首次打开自动引导配置游戏目录 |
| ✅ Steam 路径自动检测 | 通过注册表自动找到游戏安装目录 |
| ✅ 日志系统 | 崩溃/错误自动记录到文件，便于用户提交 Bug |
| ✅ 原始属性编辑器 | 属性面板可编辑任何自定义属性，不再遗漏 |
| ✅ 状态栏指示器 | 实时显示游戏/模组加载状态 |
| ✅ 快捷键对话框 | 帮助→快捷键列表 |
| ✅ .gitignore | 正确排除不该上传的文件 |
| ✅ LICENSE | GPL-3.0 开源许可证 |
| ✅ 贡献指南 | CONTRIBUTING.md |
| ✅ GitHub 模板 | Bug 报告、功能请求、PR 模板 |
| ✅ 完整文档 | 中英文用户手册、开发者指南、群星脚本速查 |
| ✅ 打包脚本 | 一键生成 Windows EXE |

**还需要你做的事：**
1. 上传到 GitHub（见第 2 节）
2. 将文档中的 `YOUR_ORG` 替换为你的 GitHub 用户名（见第 8 节）
3. （可选）生成并上传第一个 EXE 发布版（见第 4、5 节）

---

## 2. 上传项目到 GitHub（首次）

### 第一步：安装 Git

1. 打开浏览器，访问 https://git-scm.com/download/win
2. 下载并安装（全部选项保持默认，一路点 Next）
3. 安装完成后，按 `Win+R`，输入 `cmd`，回车
4. 输入 `git --version`，看到版本号说明安装成功

### 第二步：在 GitHub 创建仓库

1. 打开 https://github.com 并登录你的账号
2. 点击右上角 **"+"** → **"New repository"**
3. 填写信息：
   - **Repository name**：`StellarisGUIEditor`（建议用这个名字）
   - **Description**：`群星GUI可视化编辑器 / Visual GUI Editor for Stellaris Mods`
   - **Public** 选项（让所有人都能看到）：✓ 选中
   - **不要**勾选 "Add a README file"（我们已有自己的）
4. 点击 **"Create repository"**
5. 页面会显示一些命令，先**不要操作**，我们用下面的步骤

### 第三步：在电脑上配置 Git 身份

打开 PowerShell（在任务栏搜索"PowerShell"），依次输入（每行回车一次）：

```
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

（这两行只需执行一次，以后不用再设置）

### 第四步：上传代码

在 PowerShell 中依次输入（每行回车一次）：

```powershell
cd "c:\Users\陈\PycharmProjects\StellarisGUIEditor"

git init

git add .

git commit -m "feat: 初始版本 v1.0.0"

git branch -M main

git remote add origin https://github.com/你的用户名/StellarisGUIEditor.git

git push -u origin main
```

> **注意**：把 `你的用户名` 替换为你的 GitHub 用户名（不是邮箱）。

第一次推送时，会弹出 GitHub 登录窗口，用浏览器登录授权即可。

### 上传成功后

刷新 GitHub 页面，你的代码已经在线了！  
仓库地址类似：`https://github.com/你的用户名/StellarisGUIEditor`

---

## 3. 日常更新代码（有修改时）

每次让 AI 修改了代码，想把更新上传到 GitHub：

```powershell
cd "c:\Users\陈\PycharmProjects\StellarisGUIEditor"

git add .

git commit -m "修改说明（写你改了什么）"

git push
```

**提交说明的格式建议：**
- 新功能：`feat: 添加了XX功能`
- 修 Bug：`fix: 修复了XX问题`
- 改文档：`docs: 更新了使用手册`

---

## 4. 打包发布 EXE 给用户

### 前提条件

确保已安装：
- Python 3.10+（在 PowerShell 输入 `python --version` 检查）
- 项目依赖（已安装则跳过）

### 执行打包

**方法一（最简单）：** 双击 `packaging\build_windows.bat`

等待 1-5 分钟，完成后会自动弹出 `dist\StellarisGUIEditor\` 文件夹。

**方法二（PowerShell）：**

```powershell
cd "c:\Users\陈\PycharmProjects\StellarisGUIEditor"
packaging\build_windows.bat
```

### 打包产物

`dist\StellarisGUIEditor\` 文件夹就是给用户的完整程序。

**打包为 ZIP 分发：**
1. 右键 `dist\StellarisGUIEditor` 文件夹
2. 选择"压缩为 ZIP 文件"（或用 7-Zip）
3. 命名为 `StellarisGUIEditor_v1.0.0_Windows.zip`

---

## 5. 在 GitHub 发布新版本

1. 打开你的仓库页面
2. 右侧找到 **"Releases"** → 点击 **"Create a new release"**
3. 填写：
   - **Tag version**：`v1.0.0`（点击 "Create new tag"）
   - **Release title**：`群星 GUI 编辑器 v1.0.0`
   - **描述**：从 `CHANGELOG.md` 复制对应版本的内容
4. 将 ZIP 文件拖拽到下方的 **"Attach binaries"** 区域
5. 点击 **"Publish release"**

用户可以在 Releases 页面直接下载 ZIP，解压后运行 EXE。

---

## 6. 回应社区 Issues（问题反馈）

当有用户在 GitHub 提交了 Bug 报告或功能请求：

1. 在仓库页面点击 **"Issues"** 标签
2. 点击对应的 Issue 查看详情
3. 在底部评论框回复（可以用中文，GitHub 全平台）
4. 如果是已知 Bug，可以贴上标签 `bug`；功能请求贴 `enhancement`

**常用回复模板：**

- 感谢反馈：`感谢您的反馈！我们会尽快处理这个问题。`
- 需要更多信息：`请提供日志文件内容和操作系统版本，帮助我们复现问题。`
- 已修复：`此问题已在最新版本中修复，请下载 vX.X.X。`
- 关闭 Issue：点击底部 **"Close issue"** 按钮

---

## 7. 合并社区贡献的代码（Pull Request）

当有开发者为项目提交了代码贡献（Pull Request，简称 PR）：

1. 在仓库页面点击 **"Pull requests"** 标签
2. 点击 PR 查看改动
3. 如果改动合理，点击绿色 **"Merge pull request"** 按钮
4. 确认后点击 **"Confirm merge"**

**注意事项：**
- 如果不确定代码是否安全，可以先评论请原作者解释
- 合并后运行一次程序，确认没有引入新问题

---

## 8. 修改 GitHub 地址（替换 YOUR_ORG）

目前代码中有几处 `YOUR_ORG` 占位符，需要替换为你的 GitHub 用户名：

### 需要修改的文件

**文件 1：** `src/core/__version__.py`  
第 10 行：`GITHUB_URL = "https://github.com/YOUR_ORG/StellarisGUIEditor"`

**文件 2：** `CONTRIBUTING.md`  
第 13 行：`git clone https://github.com/YOUR_ORG/StellarisGUIEditor.git`  
多处有 `YOUR_ORG`，搜索替换即可

**文件 3：** `CHANGELOG.md`  
最后几行的链接

**文件 4：** `README.md`  
多处有 `YOUR_ORG`

### 替换方法（最简单）

1. 在项目根目录打开 PowerShell
2. 输入以下命令（把 `你的用户名` 改为实际用户名）：

```powershell
$oldText = "YOUR_ORG"
$newText = "你的用户名"
$files = Get-ChildItem -Recurse -Include "*.py","*.md","*.txt" | Where-Object { $_.FullName -notmatch '\.venv' }
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    if ($content -match [regex]::Escape($oldText)) {
        $content -replace [regex]::Escape($oldText), $newText | Set-Content $file.FullName -Encoding UTF8 -NoNewline
        Write-Host "已替换: $($file.Name)"
    }
}
```

3. 替换完成后，重新上传：
```powershell
git add .
git commit -m "docs: 更新GitHub仓库地址"
git push
```

---

## 9. 常见问题与解决方案

### Q：`git push` 时报错 "Authentication failed"

**解决方案：**
1. 打开 https://github.com → 头像 → Settings → Developer settings
2. Personal access tokens → Tokens (classic) → Generate new token
3. 勾选 `repo` 权限 → Generate token
4. 复制 token，在 push 时用 token 代替密码

### Q：`packaging\build_windows.bat` 报错 "Python not found"

**解决方案：**
1. 从 https://www.python.org/downloads/ 下载 Python 3.10+
2. 安装时勾选 **"Add Python to PATH"**（最下面那个选项）
3. 重新打开 PowerShell 再试

### Q：打包时报错 "ModuleNotFoundError: No module named 'dds'"

**解决方案：**
```powershell
pip install pydds
```

### Q：EXE 启动后立刻崩溃（白屏闪退）

**解决方案：**
1. 找到 EXE 所在文件夹，按住 Shift 右键 → 打开 PowerShell
2. 运行 `.\StellarisGUIEditor.exe`（在 PowerShell 中会显示错误信息）
3. 将错误信息截图提交 Issue

### Q：用户说找不到游戏目录

**解决方案：**
引导用户：
1. 打开 Steam
2. 右键"群星"→ 管理 → 浏览本地文件
3. 复制地址栏中的路径
4. 粘贴到"工具→设置→路径→游戏安装目录"

### Q：想更改版本号

修改 `src/core/__version__.py` 第 6 行：
```python
VERSION = "1.1.0"  # 改成新版本号
```
同时更新 `packaging/version_info.txt` 中的版本号，然后重新打包。

### Q：日志文件在哪里？

Windows：`C:\Users\用户名\.stellaris_gui_editor\logs\stellaris_gui_editor.log`

程序内快捷访问：工具 → 设置 → 高级 → 打开日志目录

### Q：GitHub 上有人提了奇怪的 PR，怎么办？

如果不确定，先评论 `感谢贡献！请问这个改动的目的是什么？` 询问清楚，
再决定是否合并。**永远不要合并你看不懂且无人解释的代码。**

---

## 附录：项目文件结构速查

```
StellarisGUIEditor/
├── main.py                 ← 程序入口，日常不用改
├── requirements.txt        ← Python 依赖列表
├── README.md               ← GitHub 主页展示的介绍
├── LICENSE                 ← 开源许可证（不要删）
├── CHANGELOG.md            ← 版本更新记录
├── CONTRIBUTING.md         ← 贡献者指南
├── .gitignore              ← 告诉 Git 哪些文件不用上传
├── assets/                 ← 图标等资源（可替换 app_icon.ico）
├── packaging/              ← 打包相关文件
│   └── build_windows.bat  ← 双击这个打包 EXE
├── docs/                   ← 各类文档
│   └── OWNER_GUIDE.md     ← 就是这个文件
├── .github/                ← GitHub 自动使用的模板文件
└── src/                    ← 全部源代码（让 AI 修改的地方）
```

---

*本文档由 AI 生成，如有疑问可随时向 AI 提问或在 GitHub Issues 反馈。*
