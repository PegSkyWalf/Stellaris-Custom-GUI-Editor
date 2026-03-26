# 群星 GUI 脚本速查手册

本文档是群星（Stellaris）GUI 脚本的快速参考，专为 Mod 制作者整理。

---

## 目录

1. [文件结构](#1-文件结构)
2. [控件类型速查](#2-控件类型速查)
3. [定位系统](#3-定位系统)
4. [精灵图系统](#4-精灵图系统)
5. [通用属性](#5-通用属性)
6. [各控件专有属性](#6-各控件专有属性)
7. [Custom GUI 事件集成](#7-custom-gui-事件集成)
8. [Button Effects 脚本](#8-button-effects-脚本)

---

## 1. 文件结构

### .gui 文件

```
guiTypes = {

    containerWindowType = {
        name = "my_window"
        # ... 属性 ...

        iconType = {
            name = "my_icon"
            # ... 属性 ...
        }
    }

}
```

- 每个顶层 `containerWindowType` 是一个完整的 Custom GUI 窗口
- 通过 `custom_gui = "my_window"` 在事件脚本中触发
- 文件编码必须为 UTF-8（不含 BOM）

### .gfx 文件（精灵注册）

```
spriteTypes = {

    spriteType = {
        name = "GFX_my_button"
        textureFile = "gfx/interface/buttons/my_button.dds"
        noOfFrames = 3
    }

    corneredTileSpriteType = {
        name = "GFX_my_panel"
        textureFile = "gfx/interface/tiles/my_panel.dds"
        borderSize = { x = 8 y = 8 }
    }

}
```

---

## 2. 控件类型速查

| 类型 | 用途 | 可否包含子控件 |
|------|------|--------------|
| `containerWindowType` | 容器窗口，Custom GUI 的顶层元素 | ✓ |
| `iconType` | 静态图标 | ✗ |
| `buttonType` | 普通按钮（游戏硬编码行为） | ✗ |
| `effectButtonType` | 效果按钮（链接 button_effect 脚本） | ✗ |
| `instantTextBoxType` | 单行或多行文本（不可滚动） | ✗ |
| `textBoxType` | 可滚动文本框 | ✗ |
| `editBoxType` | 玩家输入框 | ✗ |
| `checkBoxType` | 复选框 | ✗ |
| `listboxType` | 可滚动列表（项目由脚本动态填充） | ✗ |
| `scrollAreaType` | 可滚动容器区域 | ✓ |
| `gridBoxType` | 网格布局容器 | ✓ |
| `overlappingElementsBoxType` | 重叠元素容器（用于实现栏位等） | ✓ |
| `smoothListboxType` | 平滑滚动列表 | ✗ |
| `dropDownBoxType` | 下拉选择框 | 特殊 |
| `extendedScrollbarType` | 扩展滚动条（含轨道和滑块） | 特殊 |
| `positionType` | 位置锚点 | ✗ |

---

## 3. 定位系统

这是群星 GUI 最容易搞混的部分，请仔细阅读。

### 核心公式

```
控件左上角（屏幕坐标）= 锚点位置 + position偏移 - origo偏移
```

### orientation（锚点在父元素中的位置）

| 值 | 锚点位置 |
|----|----------|
| `UPPER_LEFT`（默认） | 父元素左上角 |
| `UPPER_CENTER` | 父元素顶部中心 |
| `UPPER_RIGHT` | 父元素右上角 |
| `CENTER_LEFT` | 父元素左侧中部 |
| `CENTER` | 父元素中心 |
| `CENTER_RIGHT` | 父元素右侧中部 |
| `LOWER_LEFT` | 父元素左下角 |
| `LOWER_CENTER` | 父元素底部中心 |
| `LOWER_RIGHT` | 父元素右下角 |

### origo（控件哪个点对齐到锚点）

取值与 orientation 相同。默认 `UPPER_LEFT`（左上角）。

### 示例

**居中对齐：**
```
containerWindowType = {
    name = "my_panel"
    orientation = center
    origo = center
    position = { x = 0 y = 0 }  # 精确居中
    size = { width = 400 height = 300 }
}
```

**固定右上角：**
```
buttonType = {
    name = "close"
    orientation = UPPER_RIGHT
    origo = UPPER_RIGHT
    position = { x = -42 y = 12 }  # 从右上角往内偏移
}
```

### position 负值规则

- 负的 position 值 = 反方向偏移
- `x = -42` 且 `orientation = UPPER_RIGHT`：从右边向左偏移 42px

### size 特殊值

- 负值：`size = { width = -20 height = -20 }` → 父元素大小减去 20px
- 百分比：`size = { width = 50% height = 100% }` → 父元素大小的百分比

---

## 4. 精灵图系统

### spriteType vs quadTextureSprite

| 属性 | GFX 注册类型 | 大小行为 | 缩放方式 |
|------|------------|---------|---------|
| `spriteType` | `spriteType` | 由图片决定 | `scale` 属性 |
| `quadTextureSprite` | `corneredTileSpriteType` | 由 `size` 决定 | 9 块拉伸 |

### 多帧精灵

```
# GFX 定义
spriteType = {
    name = "GFX_my_button"
    textureFile = "gfx/..."
    noOfFrames = 3  # 图片水平方向包含 3 帧
}

# GUI 使用
buttonType = {
    name = "my_btn"
    spriteType = "GFX_my_button"
    # frame = 0  # 使用第几帧（0 起始）
}
```

### 9 块拉伸（corneredTileSpriteType）

```
corneredTileSpriteType = {
    name = "GFX_my_panel"
    textureFile = "gfx/..."
    borderSize = { x = 8 y = 8 }  # 边框厚度（不拉伸）
}
```

---

## 5. 通用属性

所有控件均支持：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | string | 控件唯一名称（必填） |
| `position` | `{ x = N y = N }` | 位置偏移 |
| `size` | `{ width = N height = N }` | 尺寸 |
| `orientation` | enum | 锚点在父元素的位置 |
| `origo` | enum | 本控件对齐点 |
| `moveable` | yes/no | 玩家是否可拖动此控件 |
| `alwaysTransparent` | yes/no | 是否对鼠标事件透明 |
| `rotation` | float | 旋转角度（度） |
| `pdx_tooltip` | string | 悬浮提示本地化键 |
| `clipping` | yes/no | 是否裁剪超出边界的子控件 |

---

## 6. 各控件专有属性

### buttonType / effectButtonType

| 属性 | 说明 |
|------|------|
| `spriteType` / `quadTextureSprite` | 按钮精灵图 |
| `buttonText` | 按钮文字（本地化键） |
| `buttonFont` | 按钮字体 |
| `shortcut` | 键盘快捷键（如 `"ESCAPE"`） |
| `clicksound` | 点击音效（如 `"confirm_click"`） |
| `effect` | （仅 effectButtonType）button_effect 名称 |
| `tooltipText` | （仅 effectButtonType）提示本地化键 |

### instantTextBoxType / textBoxType

| 属性 | 说明 |
|------|------|
| `text` | 文字内容（本地化键或直接文字） |
| `font` | 字体（如 `"cg_16b"`、`"malgun_goth_24"`） |
| `maxWidth` | 最大宽度（超过换行） |
| `maxHeight` | 最大高度（超过截断或滚动） |
| `format` | 对齐方式：`left` / `right` / `center` |
| `fixedSize` | yes = 不自动调整大小 |
| `text_color_code` | 颜色代码（如 `"H"`=黄色、`"G"`=绿色） |
| `scrollbartype` | 关联滚动条名称（textBoxType） |

### containerWindowType

| 属性 | 说明 |
|------|------|
| `background` | 背景精灵图子块（见下） |
| `clipping` | 裁剪子控件 |
| `moveable` | 玩家可拖动窗口 |

**background 子块：**
```
background = {
    name = "background"
    quadTextureSprite = "GFX_tile_outliner_bg"
    alwaysTransparent = yes  # 不遮挡鼠标
}
```

---

## 7. Custom GUI 事件集成

### 触发 Custom GUI 的事件脚本

```
country_event = {
    id = my_mod.1
    title = "MY_MOD_TITLE"
    desc = "MY_MOD_DESC"
    
    custom_gui = "my_window_name"  # 对应 containerWindowType 的 name
    
    picture_event_data = {
        room = "ancrel_room"  # 背景房间图片名称
    }
    
    option = {
        name = "MY_MOD_OPTION_CLOSE"
        custom_gui = "close"  # 对应关闭按钮的 name
    }
}
```

### effectButtonType 与 button_effect

```
# GUI 文件
effectButtonType = {
    name = "my_action_btn"
    spriteType = "GFX_standard_button_..."
    buttonText = "MY_ACTION_TEXT"
    effect = "my_mod_action_effect"  # button_effect 名称
}

# common/button_effects/my_mod.txt
my_mod_action_effect = {
    potential = {
        # 显示条件（scope: 事件所在的 this/root）
        always = yes
    }
    allow = {
        # 可点击条件
        always = yes
    }
    effect = {
        # 点击后执行的效果
        add_resource = { energy = 100 }
    }
}
```

---

## 8. Button Effects 脚本

### 作用域说明

在 button_effect 中：
- `this` / `root`：触发事件的角色（通常是玩家的国家领袖）
- `from`：通常是玩家的国家
- 可使用 `event_target:xxx` 引用事件目标

### 常用条件

```
potential = {
    is_country_type = default          # 是普通国家
    NOT = { has_country_flag = flag_name }  # 没有某标记
    has_resource = { type = energy value >= 100 }  # 有足够资源
}
```

### 常用效果

```
effect = {
    add_resource = { energy = 100 }    # 增加资源
    set_country_flag = flag_name       # 设置标记
    fire_on_action = { on_action = xxx }  # 触发 on_action
    country_event = { id = my_mod.2 } # 触发后续事件
}
```

---

## 参考资料

- 群星 Modding Wiki：https://stellaris.paradoxwikis.com/Modding
- Paradox 官方论坛 Mod 版块：https://forum.paradoxplaza.com/forum/forums/stellaris-user-mods.943/
- CWTools VSCode 插件（脚本语法检查）：https://marketplace.visualstudio.com/items?itemName=tboby.cwtools-vscode
