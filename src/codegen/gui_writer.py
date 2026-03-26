"""
GUI Code Generator — serialize WidgetNode tree back to Stellaris .gui format.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from ..core.gui_model import WidgetNode, GUIDocument


# ---------------------------------------------------------------------------
# Value that should NOT be quoted in output
# ---------------------------------------------------------------------------

_UNQUOTED_KEYWORDS = {
    'yes', 'no',
    # orientations
    'center', 'upper_left', 'upper_right', 'lower_left', 'lower_right',
    'center_up', 'center_down', 'left_up', 'right_up', 'left_down', 'right_down',
    'center_left', 'center_right',
    'UPPER_LEFT', 'UPPER_RIGHT', 'LOWER_LEFT', 'LOWER_RIGHT',
    'CENTER_UP', 'CENTER_DOWN', 'LEFT_UP', 'RIGHT_UP', 'CENTER',
    'CENTER_LEFT', 'CENTER_RIGHT',
    # text formats
    'left', 'right', 'centre', 'justified',
    # boolean words
    'overlay', 'add', 'multiply', 'scrolling', 'rotating', 'pulsing',
}


def _indent(level: int) -> str:
    return '\t' * level


def _format_value(val: Any, level: int = 0) -> str:
    """Format a Python value to PDX script representation."""
    if isinstance(val, bool):
        return 'yes' if val else 'no'
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        s = f'{val:.4f}'.rstrip('0').rstrip('.')
        return s
    if isinstance(val, str):
        if val in _UNQUOTED_KEYWORDS:
            return val
        # Don't quote pure numbers
        try:
            float(val)
            return val
        except ValueError:
            pass
        # Quote everything else (safer for Stellaris)
        return f'"{val}"'
    if isinstance(val, dict):
        return _format_block_inline(val)
    if isinstance(val, list):
        if val and isinstance(val[0], tuple):
            return _format_block_inline(dict(val))
        return '{ ' + ' '.join(_format_value(v) for v in val) + ' }'
    return str(val)


def _format_size_component(val: Any) -> str:
    """
    Single width or height for size = { }.
    Supports integers, negatives, and Stellaris percentages as unquoted N% (not int('85%')).
    """
    if val is None:
        return '0'
    if isinstance(val, bool):
        return 'yes' if val else 'no'
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        s = f'{val:.4f}'.rstrip('0').rstrip('.')
        return s
    if isinstance(val, str):
        s = val.strip()
        if s.endswith('%'):
            return s
        try:
            v = float(s)
            if v == int(v):
                return str(int(v))
            return f'{v:.4f}'.rstrip('0').rstrip('.')
        except ValueError:
            return _format_value(val)
    return _format_value(val)


def _format_size_block(val: Any) -> str:
    """
    Format a size block always as { width = N height = M }.
    Stellaris requires width/height for background to inherit container size correctly.
    Accepts dict with width/height or x/y keys.
    """
    if isinstance(val, dict):
        w = val.get('width', val.get('x', 0))
        h = val.get('height', val.get('y', 0))
        return f'{{ width = {_format_size_component(w)} height = {_format_size_component(h)} }}'
    return _format_block_inline(val) if isinstance(val, dict) else str(val)


def _format_block_inline(d: Dict[str, Any]) -> str:
    parts = []
    for k, v in d.items():
        parts.append(f'{k} = {_format_value(v)}')
    return '{ ' + ' '.join(parts) + ' }'


# Properties to write in preferred order
_PROPERTY_ORDER = [
    'name', 'position', 'size', 'orientation', 'Orientation', 'origo',
    'moveable', 'clipping', 'smooth_scrolling', 'verticalScrollbar',
    'spriteType', 'quadTextureSprite', 'textureFile', 'textureFilePath',
    'buttonText', 'buttonFont', 'text', 'appendText',
    'font', 'maxWidth', 'maxHeight', 'format', 'vertical_alignment',
    'borderSize', 'fixedSize', 'fixedsize', 'text_color_code', 'text_offset',
    'scale', 'alwaysTransparent', 'alwaystransparent',
    'clicksound', 'oversound', 'shortcut', 'actionShortcut',
    'pdx_tooltip', 'tooltipText', 'custom_tooltip', 'effect',
    'noOfFrames', 'instantTextBoxType', 'scrollbartype',
    'spacing', 'offset', 'startValue',
]

# Sub-block property keys (stored as dicts, written as blocks)
_PROPERTY_BLOCK_KEYS = {
    'background', 'track', 'slider', 'increaseButton', 'decreaseButton',
    'animation', 'expandButton', 'expandedWindow',
}

# Keys that ARE child widget types (not property blocks)
_CHILD_WIDGET_KEYS = {
    'containerWindowType', 'iconType', 'buttonType', 'effectButtonType',
    'instantTextBoxType', 'textBoxType', 'editBoxType', 'checkBoxType',
    'listboxType', 'scrollAreaType', 'overlappingElementsBoxType',
    'gridBoxType', 'smoothListboxType', 'extendedScrollbarType',
    'scrollbarType', 'dropDownBoxType', 'positionType',
    'OverlappingElementsBoxType',
}


def write_property_block(key: str, val: Dict[str, Any], level: int) -> List[str]:
    """Write a property sub-block (background, track, slider, etc.)."""
    ind = _indent(level)
    ind1 = _indent(level + 1)
    lines = [f'{ind}{key} = {{']
    # Write sub-properties in order
    written = set()
    for k in _PROPERTY_ORDER:
        if k in val:
            lines.append(f'{ind1}{k} = {_format_value(val[k], level + 1)}')
            written.add(k)
    for k in sorted(val.keys()):
        if k not in written:
            lines.append(f'{ind1}{k} = {_format_value(val[k], level + 1)}')
    lines.append(f'{ind}}}')
    return lines


def write_widget(node: WidgetNode, level: int = 1) -> List[str]:
    """Serialize a WidgetNode to lines of GUI script."""
    lines = []
    ind = _indent(level)
    ind1 = _indent(level + 1)

    lines.append(f'{ind}{node.widget_type} = {{')

    props = node.properties
    written = set()

    # Write in order
    for key in _PROPERTY_ORDER:
        if key in props:
            val = props[key]
            if key in ('orientation', 'Orientation', 'origo', 'origin'):
                if val is None or (isinstance(val, str) and not str(val).strip()):
                    continue
            if key == 'size' and isinstance(val, dict):
                # Always width/height form; supports % and negatives from parsed mods
                lines.append(f'{ind1}size = {_format_size_block(val)}')
            elif key in _PROPERTY_BLOCK_KEYS and isinstance(val, dict):
                block_lines = write_property_block(key, val, level + 1)
                lines.extend(block_lines)
            else:
                lines.append(f'{ind1}{key} = {_format_value(val, level + 1)}')
            written.add(key)

    # Write remaining properties (alphabetical)
    for key in sorted(props.keys()):
        if key in written:
            continue
        val = props[key]
        if key in ('orientation', 'Orientation', 'origo', 'origin'):
            if val is None or (isinstance(val, str) and not str(val).strip()):
                continue
        if key == 'size' and isinstance(val, dict):
            lines.append(f'{ind1}size = {_format_size_block(val)}')
        elif key in _PROPERTY_BLOCK_KEYS and isinstance(val, dict):
            block_lines = write_property_block(key, val, level + 1)
            lines.extend(block_lines)
        elif key not in _CHILD_WIDGET_KEYS:
            lines.append(f'{ind1}{key} = {_format_value(val, level + 1)}')

    # Write child widgets
    if node.children:
        lines.append('')
        for child in node.children:
            child_lines = write_widget(child, level + 1)
            lines.extend(child_lines)
            lines.append('')

    lines.append(f'{ind}}}')
    return lines


def write_document(doc: GUIDocument) -> str:
    """Serialize a GUIDocument to a .gui file string."""
    lines = ['guiTypes = {']
    lines.append('')

    for i, root in enumerate(doc.roots):
        root_lines = write_widget(root, level=1)
        lines.extend(root_lines)
        if i < len(doc.roots) - 1:
            lines.append('')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def write_widget_to_string(node: WidgetNode) -> str:
    """Serialize a single widget to string (without guiTypes wrapper)."""
    return '\n'.join(write_widget(node, level=0))


def save_document(doc: GUIDocument, path: Optional[str] = None) -> str:
    """Save a GUIDocument to file. Returns the path."""
    target = path or doc.file_path
    if not target:
        raise ValueError('No file path specified')
    content = write_document(doc)
    with open(target, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    doc.file_path = target
    doc.modified = False
    return target


def generate_gfx_file(sprite_registrations: List[Dict[str, Any]]) -> str:
    """Generate a .gfx file with sprite registrations."""
    lines = ['spriteTypes = {', '']
    for reg in sprite_registrations:
        st = reg.get('sprite_type', 'spriteType')
        name = reg.get('sprite_name', '')
        tex = reg.get('texture_path', '')
        nof = int(reg.get('no_of_frames', 1))
        border = reg.get('border_size')

        ind1 = '\t'
        ind2 = '\t\t'
        lines.append(f'{ind1}{st} = {{')
        lines.append(f'{ind2}name = "{name}"')
        lines.append(f'{ind2}texturefile = "{tex}"')
        if nof > 1:
            lines.append(f'{ind2}noOfFrames = {nof}')
        if border and st == 'corneredTileSpriteType':
            lines.append(f'{ind2}borderSize = {{ x={border[0]} y={border[1]} }}')
        lines.append(f'{ind1}}}')
        lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
