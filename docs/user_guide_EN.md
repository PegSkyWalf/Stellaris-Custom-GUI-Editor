# Stellaris Custom-GUI Editor — User Manual (English)

**Version**: 1.2.0 | **Date**: 2026-04-02

---

> ⚠️ **Safety Warning — Please read before use**
>
> This tool **directly modifies `.gui` files**. Always **back up all your original resource files** before using this editor.  
> It is strongly recommended to work on an isolated copy of your mod. **Never edit unbackedup game files or already-published mod files.**  
> There is no automatic backup or undo for file-level writes — once saved, the original is overwritten.

---

## Table of Contents

1. [Installation](#1-installation)
2. [First-Run Wizard](#2-first-run-wizard)
3. [Interface Overview](#3-interface-overview)
4. [Basic Workflow](#4-basic-workflow)
5. [Canvas Controls](#5-canvas-controls)
6. [Stellaris Coordinate System](#6-stellaris-coordinate-system)
7. [Widget Types Reference](#7-widget-types-reference)
8. [Properties Panel](#8-properties-panel)
9. [Layer Panel](#9-layer-panel)
10. [Virtual Groups](#10-virtual-groups)
11. [Sprite Library](#11-sprite-library)
12. [Code View](#12-code-view)
13. [Event Link Panel](#13-event-link-panel)
14. [Button Effects Editor](#14-button-effects-editor)
15. [GFX Generator](#15-gfx-generator)
16. [Themes & Appearance](#16-themes--appearance)
17. [Keyboard Shortcuts](#17-keyboard-shortcuts)
18. [FAQ & Troubleshooting](#18-faq--troubleshooting)

---

## 1. Installation

### Option A: Pre-built EXE (Recommended)

1. Download the latest ZIP from the [GitHub Releases page](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases)
2. **Extract the entire ZIP** to a folder (e.g. `C:\Tools\StellarisGUIEditor\`)
3. Double-click `StellarisGUIEditor.exe`

> ⚠️ **You must extract the ZIP before running — do not run the EXE from inside the archive.**  
> The `_internal\` folder next to the EXE contains all required runtime libraries. Removing it will prevent the application from starting.

### Option B: From Source (Developers)

```bash
# Requires Python 3.10+
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd Stellaris-Custom-GUI-Editor
pip install -r requirements.txt
python main.py
```

### Option C: Build EXE Yourself

1. Clone the repository
2. Double-click **`build.bat`** in the project root
3. Wait ~5 minutes; the script auto-installs dependencies, compiles, and creates `StellarisCustomGUIEditor_Windows.zip`

---

## 2. First-Run Wizard

On first launch, a three-step wizard guides you through basic setup:

### Step 1: Game Directory

Click **Auto-detect** — the editor reads the Steam registry to locate your Stellaris installation automatically.

If auto-detect fails, click **Browse…** and navigate to your Stellaris folder manually:
- Steam users: right-click Stellaris in Steam → Manage → Browse local files
- Example path: `E:\SteamLibrary\steamapps\common\Stellaris`
- **Validation**: the folder should contain an `interface\` subdirectory

You can also optionally add one or more **Mod directories** to load mod sprites, localizations, and button effects.

### Step 2: Theme

| Theme | Best for |
|-------|---------|
| Dark (default) | Extended use, eye-friendly |
| Light | High-ambient-light environments |
| Dark Blue | Professional blue palette |

### Step 3: Done

Click **Start**. The editor loads game resources in a background thread — the status bar shows progress, and the UI remains responsive.

You can revisit all settings at any time via **Tools → Settings**.

---

## 3. Interface Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  Menu bar: File / Edit / Tools / Help                                 │
├────────────────┬────────────────────────────┬────────────────────────┤
│   Left Panel   │                            │     Right Panel        │
│                │      Visual Canvas         │                        │
│  ┌───────────┐ │  (1920×1080 reference)     │  ┌──────────────────┐  │
│  │ Widget    │ │  Zoom: 25% – 400%          │  │  Properties      │  │
│  │ Library   │ │  Pan: middle-click drag    │  │  Panel           │  │
│  │           │ │                            │  ├──────────────────┤  │
│  │ Sprite    │ │                            │  │  Code View       │  │
│  │ Library   │ │                            │  ├──────────────────┤  │
│  │           │ │                            │  │  Event Links     │  │
│  │ File Tree │ │                            │  └──────────────────┘  │
│  └───────────┘ │                            │                        │
├────────────────┴────────────────────────────┴────────────────────────┤
│   Layer Panel (widget tree) / Virtual Groups Panel                    │
├──────────────────────────────────────────────────────────────────────┤
│   Status bar: game path · resource loading status · selected widget  │
└──────────────────────────────────────────────────────────────────────┘
```

### Panel Summary

| Panel | Location | Purpose |
|-------|----------|---------|
| Widget Library | Left, Tab 1 | All Stellaris widget types; double-click or drag to add |
| Sprite Library | Left, Tab 2 | Browse loaded sprites; search, preview, apply |
| File Browser | Left, Tab 3 | `.gui`/`.gfx` file tree for game & mods; double-click to open |
| Visual Canvas | Center | Main editing area |
| Properties Panel | Right, Tab 1 | Edit all properties of the selected widget |
| Code View | Right, Tab 2 | Live PDX Script code with syntax highlighting |
| Event Links | Right, Tab 3 | Events that reference this GUI via `custom_gui` |
| Layer Panel | Bottom, Tab 1 | Widget hierarchy tree; visibility control |
| Virtual Groups | Bottom, Tab 2 | Logical grouping independent of file structure |

---

## 4. Basic Workflow

### 4.1 Create a New GUI File

1. **File → New GUI File**
2. Enter the filename (e.g. `my_window.gui`) and top-level container name
3. The editor creates an empty `containerWindowType` as the root

### 4.2 Open an Existing File

- **File → Open** and choose a `.gui` file, or
- Double-click a file in the **File Browser** panel

### 4.3 Add Widgets

1. Find the widget type in the **Widget Library** panel
2. Double-click it, or drag it onto the canvas into the target container
3. The widget appears on the canvas and in the Layer Panel tree

### 4.4 Select and Edit Widgets

- Click a widget on the canvas to select it
- Or click the corresponding node in the **Layer Panel**
- The **Properties Panel** on the right displays all editable attributes

### 4.5 Move Widgets

- **Drag** the selected widget on the canvas
- **Arrow keys**: nudge 1 pixel; **Shift+Arrow**: move 10 pixels
- **Properties Panel**: directly edit `position` → `x` / `y` values

### 4.6 Resize Widgets

- **Drag handles**: 8 resize handles appear when a widget is selected
- **Properties Panel**: directly edit `size` → `width` / `height` values

### 4.7 Save

- **Ctrl+S** — save to the current file
- **File → Save As** — save to a new path

The saved `.gui` file is fully compatible with the game. Place it in your mod's `interface\` directory.

---

## 5. Canvas Controls

### 5.1 Viewport Navigation

| Action | Method |
|--------|--------|
| Zoom | Ctrl + mouse wheel (centered on cursor) |
| Pan | Middle-click drag / Alt + left-click drag |
| Fit canvas | Ctrl+0 |
| 100% zoom | View → Actual Size |

Zoom range: **25% – 400%**

### 5.2 Selecting Widgets

| Action | Method |
|--------|--------|
| Single select | Click widget |
| Multi-select | Ctrl+click, or drag a selection box over empty space |
| Deselect | Click empty space |
| Select all | Ctrl+A |

### 5.3 Preview Mode

Press **Ctrl+P** to toggle preview mode:
- Hides all bounding boxes, type labels, and selection handles
- Shows only sprites and layout — approximates in-game appearance
- Editing is disabled in preview mode

### 5.4 Undo / Redo

| Action | Shortcut |
|--------|---------|
| Undo | Ctrl+Z |
| Redo | Ctrl+Y |

Supported undoable actions: move, resize, property change, add, delete, duplicate widget.

---

## 6. Stellaris Coordinate System

Understanding the coordinate system is key to correctly positioning widgets.

### 6.1 Core Concepts

| Property | Meaning | Default |
|----------|---------|---------|
| `orientation` | Where the anchor point sits on the **parent container** | `UPPER_LEFT` |
| `origo` | The widget's own reference point | `UPPER_LEFT` |
| `position` | Pixel offset from the parent anchor to the widget's reference point | `{ x=0 y=0 }` |

### 6.2 Direction Values

| Value | Meaning |
|-------|---------|
| `UPPER_LEFT` | Top-left corner (default) |
| `UPPER_RIGHT` | Top-right corner |
| `LOWER_LEFT` | Bottom-left corner |
| `LOWER_RIGHT` | Bottom-right corner |
| `CENTER` | Center |
| `CENTER_UP` | Top center |
| `CENTER_DOWN` | Bottom center |

### 6.3 Positioning Examples

**Center a widget within its parent:**
```
orientation = center
origo = center
position = { x = 0 y = 0 }
```

**Place at bottom-right with -10px margin:**
```
orientation = LOWER_RIGHT
origo = LOWER_RIGHT
position = { x = -10 y = -10 }
```

### 6.4 Sprite Size Rules

| Sprite type | Size control | Visual scaling |
|-------------|-------------|----------------|
| `spriteType` | Sprite dimensions are fixed; `size` affects click area | Use `scale` to resize visually |
| `quadTextureSprite` / `corneredTileSpriteType` | `size` directly controls display dimensions | 9-slice stretch, corners stay intact |

---

## 7. Widget Types Reference

### containerWindowType

The fundamental organizational unit. All other widgets must be placed inside a container.

- Containers can be nested to any depth
- `background` is an optional sub-property (not a standalone widget) that sets the container's background sprite
- If `size` is omitted (implicit container), the editor auto-sizes it to fit its children

---

### iconType

Displays a static sprite image. Not interactive.

- Use `spriteType` for fixed-size sprites
- Use `quadTextureSprite` for stretchable sprites (requires `size`)

---

### buttonType

A button with a hardcoded built-in game action (e.g. close window, confirm).

---

### effectButtonType

The core Custom GUI control. Binds to a `button_effect` script for custom behavior.

**Key properties:**

| Property | Description |
|----------|-------------|
| `effect` | Name of the button_effect to call |
| `buttonText` | Button label (direct text or localization key) |
| `buttonFont` | Font name |
| `format` | Text alignment: `CENTER`, `CENTER_LEFT`, `left`, `right` |
| `text_offset` | Text offset within the button: `{ x=0 y=0 }` |
| `tooltipText` | Hover tooltip (localization key) |
| `spriteType` | Visual sprite |
| `scale` | Overall scale factor |
| `alwaysTransparent` | If `yes`, button is click-through transparent |

---

### instantTextBoxType

Displays text content (supports localization keys). Single-line optimized.

---

### textBoxType

Multi-line text display.

---

### editBoxType

Allows player text input.

---

### checkBoxType

A two-state toggle control.

---

### scrollAreaType

Container with scrollbar(s) for content larger than the declared `size`.

---

## 8. Properties Panel

### 8.1 Common Properties

| Property | Description |
|----------|-------------|
| `name` | Unique name within the parent container |
| `position` | Position offset (see Chapter 6) |
| `size` | Display/interaction dimensions (width × height) |
| `orientation` | Anchor location on the parent |
| `origo` | Widget's own reference point |
| `clipping` | `yes`: clip children that extend beyond this container |
| `moveable` | `yes`: player can drag this window in-game |

### 8.2 Sprite Properties

| Property | Description |
|----------|-------------|
| `spriteType` | Reference to a `spriteType` defined in `.gfx` |
| `quadTextureSprite` | Reference to a `corneredTileSpriteType` in `.gfx` |
| `scale` | Visual scale multiplier (`1.0` = original size) |

Click the **"Select Sprite…"** button next to the field to browse and apply sprites from the Sprite Library.

### 8.3 Text Properties

| Property | Description |
|----------|-------------|
| `buttonText` | Button text (direct string or localization key) |
| `buttonFont` | Font name |
| `format` | Alignment: `CENTER`, `CENTER_LEFT`, `left`, `right` |
| `text_offset` | Text offset: `{ x=0 y=0 }` |

When the text value is a localization key and the corresponding `.yml` file is loaded, the translated text is shown below the input field.

### 8.4 Raw Properties Editor

The **Raw Properties** table at the bottom of the panel shows all key-value pairs for the selected widget, including any that don't have a dedicated UI control.

Use this to:
- View all stored attributes
- Add custom or unusual property keys
- Edit properties not covered by the main form

Raw properties are always preserved on save — unknown keys are never discarded.

---

## 9. Layer Panel

The Layer Panel shows the complete widget hierarchy of the current document as a tree.

### Operations

| Action | Method |
|--------|--------|
| Select widget | Click node (canvas syncs) |
| Expand/collapse container | Click the arrow icon |
| Toggle visibility | Click the eye icon |
| Multi-select | Ctrl+click |

### Visibility Notes

The layer panel's **visibility** (eye icon) is a **local editor-only display control** — it does not affect the exported `.gui` file, and it is completely independent from Virtual Group visibility. The two systems do not interfere with each other.

---

## 10. Virtual Groups

Virtual Groups let you organize widgets into **named logical groups**, independent of the `.gui` file structure.

### How It Works

- Group metadata is saved in a sidecar file (`*.groups.json`) — the `.gui` file is not modified
- Any widget can be added to one or more groups
- Hiding a group does not affect the individual widget visibility settings in the Layer Panel

### Usage

1. Switch to the **Virtual Groups** panel at the bottom
2. Click **New Group** and enter a name (e.g. "Background Layer", "Button Area")
3. Right-click a widget in the Layer Panel or canvas → **Add to Group**
4. Click the eye icon next to the group name to show/hide all widgets in that group

---

## 11. Sprite Library

The Sprite Library panel lists all loaded sprites (7900+ from the vanilla game, more with mods loaded).

### Features

| Feature | How |
|---------|-----|
| Search | Type a keyword in the search box |
| Preview | Click a sprite name to preview the texture on the right |
| Apply to widget | Select a widget first, then double-click the sprite name |

### Why Sprites Don't Display

- Game directory not configured correctly
- DDS file uses BC7 format without `pydds` support (included in the EXE release; `pip install pydds` for source)
- Sprite defined in a mod whose directory hasn't been added in Settings

---

## 12. Code View

The Code View shows the live PDX Script code for the current document.

### Precise Highlight Navigation

When you select a widget in the canvas or Layer Panel, the Code View **scrolls to and highlights the exact code block** for that widget.

The navigation algorithm uses a **structural path** (widget type + name + index within parent), not a simple name search. This means: even if two widgets share the same name (e.g. two `iconType` blocks both named `portrait` in different containers), the editor highlights the correct one.

### Direct Code Editing

The Code View is not read-only — you can edit the code directly:
1. Modify the code text
2. The editor parses it automatically
3. On success, the canvas updates immediately
4. On parse error, an error hint is shown and the original state is preserved

---

## 13. Event Link Panel

The Event Link Panel shows which event files reference the current GUI window via `custom_gui = "window_name"`.

When you open a `.gui` file, the editor automatically scans all event files in the configured game/mod directories and lists any events that trigger this GUI.

**Use case**: Quickly understand where your GUI window is called from, for debugging or cross-referencing.

---

## 14. Button Effects Editor

The Button Effects Editor provides a visual interface for editing `common/button_effects/*.txt` files.

Each `button_effect` block contains:
- `potential`: condition under which the button is visible
- `allow`: condition under which the button is clickable
- `effect`: the Stellaris scripted effect to execute on click

Browse all defined effects, edit their content in text boxes, and save changes back to the file.

> The `effect` property of an `effectButtonType` widget is the name of a `button_effect` block defined here.

---

## 15. GFX Generator

When using custom sprites, you need to register them in a `.gfx` file. The GFX Generator helps you quickly produce the correct syntax.

1. **Tools → GFX Generator**
2. Enter the sprite name (e.g. `GFX_my_button`)
3. Choose sprite type: `spriteType` or `corneredTileSpriteType`
4. Enter the texture file path (relative to your mod root)
5. Click **Generate** — the code is displayed and copied to clipboard

Example output (`spriteType`):
```
spriteType = {
    name = "GFX_my_button"
    texturefile = "gfx/interface/my_button.dds"
    noOfFrames = 2
}
```

---

## 16. Themes & Appearance

### Switching Themes

**Tools → Settings → Appearance**, choose:
- **Dark** — default, easy on the eyes
- **Light** — high contrast for bright environments
- **Dark Blue** — professional blue palette

### Custom Accent Color

Click the accent color swatch to open a color picker and choose a custom color for buttons, highlights, and links.

### Saving Settings

All changes take effect immediately upon clicking **OK** and are automatically saved.

---

## 17. Keyboard Shortcuts

### File

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New GUI file |
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |

### Edit

| Shortcut | Action |
|----------|--------|
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+D | Duplicate selected widget |
| Delete | Delete selected widget |
| Ctrl+A | Select all |

### View

| Shortcut | Action |
|----------|--------|
| Ctrl+scroll | Zoom canvas |
| Ctrl+0 | Fit canvas |
| Ctrl+P | Toggle preview mode |
| Middle-click drag | Pan canvas |

### Widget Movement

| Shortcut | Action |
|----------|--------|
| Arrow keys | Nudge 1 pixel |
| Shift+Arrow | Move 10 pixels |

Full shortcut list: **Help → Keyboard Shortcuts**

---

## 18. FAQ & Troubleshooting

### Startup Issues

**Q: EXE reports `Failed to load Python DLL`**  
A: You likely copied only the `.exe` without the `_internal\` folder. Extract the full ZIP and keep all files together.

**Q: "Game directory not configured" on startup**  
A: Go to **Tools → Settings → Paths**, click "Auto-detect", or browse manually to your Stellaris install folder (must contain `interface\` subdirectory).

### Sprite Issues

**Q: Sprites show as a checkerboard pattern (not loading)**  
A:
1. Verify the game directory is configured correctly
2. Some BC7-format DDS files require `pydds` — included in the EXE release; for source installs run `pip install pydds`

**Q: Sprites display with wrong proportions (stretched/squashed)**  
A: Check the sprite definition in the `.gfx` file. If the DDS uses horizontal strip animation, verify `noOfFrames` is set correctly.

### Layout Issues

**Q: Widget positions in the editor don't match in-game positions**  
A: This usually involves `orientation` and `origo` settings — refer to [Chapter 6](#6-stellaris-coordinate-system). Remember that positions are always relative to the parent container.

**Q: Widget extends visually outside its parent container in the editor**  
A: This can happen with implicit containers (no `size` declared) — the editor estimates the container size from child bounds. The exported code is still correct; this is only a display estimation.

### Save/File Issues

**Q: Saved `.gui` file doesn't appear in-game**  
A: Check:
1. File is placed in your mod's `interface\` directory
2. A game event triggers it with `custom_gui = "window_name"`
3. File encoding is UTF-8 (no BOM)

**Q: Application crashes**  
A: Find the log file at `C:\Users\YourName\.stellaris_gui_editor\logs\`. Attach the latest `.log` file when reporting an Issue on GitHub.

---

*Manual Version: 1.2.0 | 2026-04-02*  
*GitHub: https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor*
