# 免责声明 / Disclaimer

**中文** | [English](#english)

---

## 项目声明

**群星自定义GUI编辑器**（Stellaris Custom-GUI Editor）是一个由个人开发者独立发起的开源工具项目，旨在为《群星》（Stellaris）模组制作者提供可视化的自定义 GUI 编辑环境。

---

## 一、与 Paradox Interactive 的关系

本项目与 Paradox Interactive 及其旗下所有品牌、产品、商标**无任何官方关联、授权、背书或合作关系**。

- 《群星》（Stellaris）是 Paradox Interactive AB 的注册商标。
- 本项目仅作为社区工具，用于辅助理解和编辑《群星》模组的 `.gui` 脚本格式。
- 本项目不包含、不分发任何属于 Paradox Interactive 的游戏资产（贴图、音频、文本等）。

---

## 二、项目开发方式

本项目**完全由人工智能辅助创建**，具体使用了以下工具和模型：

- **开发环境**：[Cursor IDE](https://www.cursor.com/)
- **AI 模型**：Anthropic Claude（包含 claude-sonnet-4.5、claude-sonnet-4.6-medium-thinking、claude-opus-4 等多个版本）及其他 Cursor 内置模型
- **编程语言**：Python 3.10+
- **GUI 框架**：[PySide6](https://doc.qt.io/qtforpython/)（Qt for Python，LGPL 许可）
- **打包工具**：[PyInstaller](https://pyinstaller.org/)
- **图像处理**：[Pillow](https://pillow.readthedocs.io/)、[imageio](https://imageio.readthedocs.io/)
- **DDS 解码**：[pydds](https://github.com/kcat/pydds)（GPL-3.0 许可）
- **版本控制**：[Git](https://git-scm.com/) / [GitHub](https://github.com/)

项目发起人（伞折帆 / 方显申 / SanZheFan）本人并不具备完整的软件工程专业背景，全部代码逻辑均由上述 AI 工具生成与维护。**因此，项目中可能存在未经充分测试的边缘情况、不完善的实现或潜在的技术债务。** 欢迎社区开发者参与审查和改进。

---

## 三、许可证与使用权利

本项目以 **GNU General Public License v3.0（GPL-3.0）** 授权发布。

### 你可以：
- ✅ **下载并免费使用**本软件
- ✅ **查看、研究和修改**源代码
- ✅ **重新打包**并在遵守 GPL-3.0 条款的前提下**再分发**
- ✅ **基于本项目创建衍生作品**

### 你必须：
- 📋 **保留原始版权声明**和许可证文本
- 📋 **标注原始作者**：伞折帆（SanZheFan），GitHub：[@PegSkyWalf](https://github.com/PegSkyWalf)
- 📋 **以相同的 GPL-3.0 许可证**发布任何衍生作品
- 📋 **公开修改后的源代码**（若再分发二进制）

### 你不得：
- ❌ **将本软件用于商业盈利目的**（包括但不限于销售、收费服务、内置广告等）
- ❌ **移除或隐藏版权声明和作者信息**
- ❌ **以封闭源码形式再分发**

> 选用 GPL-3.0 的原因：本项目依赖 [pydds](https://github.com/kcat/pydds)（GPL-3.0 许可），根据 GPL 的传染性条款，整体需采用 GPL-3.0 授权。详细条款见 [LICENSE](LICENSE) 文件和 [GPL-3.0 官方文本](https://www.gnu.org/licenses/gpl-3.0.html)。

---

## 四、第三方依赖声明

本项目使用了以下第三方库，各自遵循其对应许可证：

| 库名 | 许可证 | 用途 |
|------|--------|------|
| PySide6 | LGPL-3.0 | GUI 框架（Qt for Python） |
| pydds | GPL-3.0 | DDS 贴图解码 |
| Pillow | HPND（MIT 类） | 图像处理 |
| imageio | BSD-2-Clause | 多格式图像读写 |
| PyInstaller | GPL-2.0+ | Windows 打包 |
| numpy | BSD-3-Clause | 数值计算（可选） |

---

## 五、免责条款

1. **软件按"现状"（AS IS）提供**，不附带任何明示或暗示的保证，包括但不限于适销性、特定用途适用性或不侵权性的保证。

2. **作者不对以下情况承担任何责任**：
   - 使用本软件导致的模组文件损坏或数据丢失
   - 因错误解析游戏文件格式引起的任何问题
   - 游戏更新导致本工具与最新版本不兼容
   - 第三方在未经授权的情况下修改再分发本软件所造成的问题

3. **本工具不修改游戏本体**，所有操作仅影响模组的 `.gui`、`.gfx` 等脚本文件。使用本工具编辑 Mod 文件时，请自行做好**备份**。

4. 本项目由 AI 工具生成，**不保证所有功能均按预期工作**。如遇问题，请在 [Issues](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/issues) 页面反馈，社区将尽力协助。

---

## 六、版权信息

```
Stellaris Custom-GUI Editor（群星自定义GUI编辑器）
版权所有 (C) 2026  伞折帆（方显申 / SanZheFan）
联系方式：2776215672@qq.com
GitHub：https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor

本程序为自由软件：你可以根据自由软件基金会发布的 GNU 通用公共许可证
（第 3 版或更高版本）重新分发和/或修改它。
本程序的发布是希望它能有用，但不提供任何担保；
甚至没有对适销性或特定用途适用性的暗示担保。
详情参阅 GNU 通用公共许可证。
```

---

<a id="english"></a>

## English

### Project Statement

**Stellaris Custom-GUI Editor** is an independent, community-driven open-source tool designed to help Stellaris mod creators build and preview custom GUI layouts visually.

### Relationship with Paradox Interactive

This project has **no official affiliation, authorization, endorsement, or partnership** with Paradox Interactive or any of its brands and products.

- *Stellaris* is a registered trademark of Paradox Interactive AB.
- This tool is a community utility for working with Stellaris mod `.gui` script files only.
- No game assets owned by Paradox Interactive are included or distributed.

### Development Method

This project was **created entirely with AI assistance**, using:
- **IDE**: Cursor IDE
- **AI Models**: Anthropic Claude (multiple versions including claude-sonnet-4.5, claude-sonnet-4.6, claude-opus-4) and other Cursor built-in models
- **Language**: Python 3.10+, PySide6 (Qt for Python), PyInstaller, Pillow, pydds, imageio

The project initiator (SanZheFan / PegSkyWalf) does not have a formal software engineering background. All code logic was generated and maintained by AI tools. The project may contain untested edge cases or imperfect implementations. Community review and contributions are welcome.

### License & Usage Rights

Licensed under **GPL-3.0**. See [LICENSE](LICENSE) for full terms.

**You may:**
- ✅ Download and use this software for free
- ✅ View, study, and modify the source code
- ✅ Repackage and redistribute under GPL-3.0 terms
- ✅ Create derivative works

**You must:**
- 📋 Retain original copyright notices and license text
- 📋 Credit the original author: SanZheFan (伞折帆), GitHub: [@PegSkyWalf](https://github.com/PegSkyWalf)
- 📋 Release any derivative works under GPL-3.0
- 📋 Provide source code if distributing binaries

**You may not:**
- ❌ Use this software for commercial profit (sale, paid services, embedded advertising, etc.)
- ❌ Remove or hide copyright notices and author attribution
- ❌ Distribute in closed-source form

### Disclaimer

This software is provided "AS IS" without warranty of any kind. The authors are not liable for any data loss, file corruption, or incompatibility issues arising from use of this tool. Always **back up your mod files** before editing.

### Copyright

```
Stellaris Custom-GUI Editor
Copyright (C) 2026  SanZheFan (伞折帆 / 方显申)
Contact: 2776215672@qq.com
GitHub: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor
```
