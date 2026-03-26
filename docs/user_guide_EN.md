# Stellaris Custom-GUI Editor — User Manual (English)

**Version**: 1.0.0 | **Date**: 2026-03-26

---

## Table of Contents

1. [Installation](#1-installation)
2. [First-Run Wizard](#2-first-run-wizard)
3. [Interface Overview](#3-interface-overview)
4. [Basic Workflow](#4-basic-workflow)
5. [Canvas Controls](#5-canvas-controls)
6. [Widget Types](#6-widget-types)
7. [Properties Panel](#7-properties-panel)
8. [Themes & Appearance](#8-themes--appearance)
9. [Keyboard Shortcuts](#9-keyboard-shortcuts)
10. [FAQ](#10-faq)

---

## 1. Installation

### Option A: Pre-built EXE (Recommended for most users)

1. Download the latest ZIP from [GitHub Releases](https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor/releases)
2. Extract to any folder (e.g. `C:\Tools\StellarisGUIEditor\`)
3. Double-click `StellarisGUIEditor.exe`

### Option B: From source (Developers)

```bash
# Requires Python 3.10+
git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
cd StellarisGUIEditor
pip install -r requirements.txt
python main.py
```

---

## 2. First-Run Wizard

On first launch, a three-step wizard guides you through basic setup:

1. **Game Directory** — Click "Auto-detect" or browse manually to your Stellaris install folder  
   *(Steam: right-click Stellaris → Manage → Browse local files)*
2. **Theme** — Choose Dark / Light / Dark Blue
3. **Done** — Quick-start tips

You can always change settings via **Tools → Settings**.

---

## 3. Interface Overview

| Panel | Location | Purpose |
|-------|----------|---------|
| Widget Library | Left tab | All available Stellaris widget types |
| Preset Library | Left tab | Saved widget templates |
| File Browser | Left tab | Navigate .gui/.gfx files |
| Layer Panel | Left tab | Widget hierarchy, visibility, Z-order |
| Groups Panel | Left tab | Virtual grouping (hide/show sets of widgets) |
| **Canvas** | Center | Visual editing area |
| Properties | Right tab | Edit selected widget's attributes |
| Sprite Library | Right tab | Browse 7900+ game sprites |
| Event Links | Right tab | Events referencing this GUI |
| Code View | Bottom dock | Live .gui code with PDX syntax highlighting |
| Button Effects | Bottom dock | Edit common/button_effects/*.txt |

---

## 4. Basic Workflow

1. **File → Open Mod Directory** — select your mod root folder
2. **File → New GUI File** — enter filename and GUI key name  
   *(The key name is what you use in `custom_gui = "..."` in events)*
3. **Double-click** a widget in the Widget Library to add it
4. **Click** a widget on canvas → edit in Properties Panel
5. **Ctrl+S** to save

---

## 5. Canvas Controls

| Action | Input |
|--------|-------|
| Select widget | Left-click |
| Multi-select | Ctrl+click or drag-select on empty area |
| Move widget | Drag |
| Nudge (1px) | Arrow keys |
| Nudge (8px) | Shift + Arrow keys |
| Resize | Drag blue handles on selection |
| Pan view | Middle-mouse drag or Alt+drag |
| Zoom | Ctrl + scroll wheel |
| Fit all | Ctrl+0 |
| Duplicate | Ctrl+D |
| Delete | Delete key |
| Right-click | Context menu |

---

## 6. Widget Types

| Type | Color | Purpose |
|------|-------|---------|
| containerWindowType | Blue | Container / top-level GUI window |
| iconType | Green | Static image (fixed-size sprite) |
| buttonType | Orange | Clickable button (hardcoded action) |
| effectButtonType | Red | Button linked to a button_effect script |
| instantTextBoxType | Purple | Non-scrolling text |
| textBoxType | Gray | Scrollable text |
| editBoxType | Teal | Text input field |
| checkBoxType | Orange | Toggle checkbox |
| listboxType | Cyan | Scrollable list |
| scrollAreaType | Blue | Scrollable container |
| gridBoxType | Red | Grid layout container |

---

## 7. Properties Panel

Properties are grouped into sections:

| Section | Key Properties |
|---------|---------------|
| Identity | name (unique ID) |
| Geometry | position, size, orientation, origo |
| Appearance | spriteType, quadTextureSprite, scale |
| Text | buttonText, text, font, maxWidth/Height |
| Interaction | effect (button_effect name), tooltipText |
| Background | background sprite (containers only) |
| Extra | clipping, scrollbar, rotation |
| **Raw Properties Editor** | All other attributes — editable, addable, deletable |

The **Raw Properties Editor** (collapsed by default) shows all properties not covered by the forms above, preventing data loss when working with unknown attributes.

---

## 8. Themes & Appearance

**Tools → Settings → Appearance**

| Option | Description |
|--------|-------------|
| Theme | Dark / Light / Dark Blue |
| Accent Color | Color for highlights, selections, and links |
| Font Size | UI panel text size |

Changes apply immediately when you click OK — no restart needed.

---

## 9. Keyboard Shortcuts

| Category | Action | Shortcut |
|----------|--------|----------|
| File | New | Ctrl+N |
| | Open | Ctrl+O |
| | Save | Ctrl+S |
| | Save As | Ctrl+Shift+S |
| Edit | Undo | Ctrl+Z |
| | Redo | Ctrl+Y |
| | Select All | Ctrl+A |
| | Duplicate | Ctrl+D |
| | Delete | Delete |
| | Find widget | Ctrl+F |
| View | Fit canvas | Ctrl+0 |
| | Zoom in/out | Ctrl++ / Ctrl+- |
| | Toggle grid | Ctrl+G |
| | Preview mode | Ctrl+P |
| | Refresh canvas | Ctrl+Shift+F5 |
| | Refresh resources | Ctrl+Shift+R |
| Align | Left/Right/Center H | Ctrl+Alt+1/2/3 |
| | Top/Bottom/Center V | Ctrl+Alt+4/5/6 |

Full list: **Help → Keyboard Shortcuts**

---

## 10. FAQ

**Q: Sprites show as checkerboard patterns**  
A: Check that your game directory is set correctly (should contain `interface/`). BC7 DDS files may require ffmpeg or texconv.exe on PATH.

**Q: Saved .gui file not recognized by the game**  
A: Ensure the file is in your mod's `interface/` directory and encoded as UTF-8.

**Q: Where are the log files?**  
A: `%USERPROFILE%\.stellaris_gui_editor\logs\` on Windows.  
Quick access: Tools → Settings → Advanced → Open Log Directory.

**Q: The EXE is flagged by antivirus**  
A: UPX compression is disabled in our builds to minimize false positives. If still flagged, add the folder to your antivirus whitelist.
