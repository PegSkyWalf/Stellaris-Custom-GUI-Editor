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
    """Save a GUIDocument to file, preserving original source where possible.

    Uses patch-based approach: only regenerates modified widget blocks,
    preserving comments, @variable definitions, @[expr] expressions,
    and all original formatting in unmodified sections.
    """
    target = path or doc.file_path
    if not target:
        raise ValueError('No file path specified')
    content = write_document_preserving(doc)
    with open(target, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    doc.file_path = target
    doc.modified = False
    return target


def write_document_preserving(doc: GUIDocument) -> str:
    """Serialize a GUIDocument, preserving original source for unmodified parts.

    策略：
    1. 如果没有原始源码（新文件），使用传统的完全生成方式
    2. 如果有原始源码，采用 patch 方式：
       - 收集所有需要替换的 (start, end, replacement) 补丁
       - 未修改的 widget 保留原始文本
       - 已修改的 widget 用 gui_writer 重新生成
       - 新增的 widget 插入到 guiTypes 块末尾
       - 被删除的 widget 从源码中移除
       - 所有 widget 之外的内容（注释、@变量、空行等）完整保留
    """
    if not doc._raw_source:
        return write_document(doc)

    raw = doc._raw_source

    # 如果没有 guiTypes span 信息，回退到传统方式
    if not doc._guitypes_inner_span:
        return write_document(doc)

    inner_start = doc._guitypes_inner_span.start
    inner_end = doc._guitypes_inner_span.end

    # 收集所有根 widget 的 span 和修改状态
    # 按 span 起始位置排序，以便按顺序处理
    root_entries = []
    for root in doc.roots:
        if root._source_span:
            root_entries.append((root._source_span.start, root._source_span.end, root))
        else:
            # 新增的 widget，没有原始 span
            root_entries.append((None, None, root))

    # 分离有 span 和没有 span 的 widget
    existing_roots = [(s, e, r) for s, e, r in root_entries if s is not None]
    new_roots = [r for s, e, r in root_entries if s is None]

    # 按 span 位置排序
    existing_roots.sort(key=lambda x: x[0])

    # 收集原始源码中的所有 widget span（可能包含已被删除的）
    # 使用已知的 span 信息
    original_spans = set()
    for s, e, r in existing_roots:
        original_spans.add((s, e))

    # 构建 patch 列表
    patches = []  # (start, end, replacement)

    for start, end, root in existing_roots:
        if root.is_subtree_modified():
            indent_level = _detect_indent_level(raw, start)
            adjusted_start = _line_indent_start(raw, start)
            # _patch_widget_recursive 根据修改情况返回适当的文本
            new_text = _patch_widget_recursive(root, raw, indent_level)
            if root._source_modified or not root._source_span:
                # 自身被修改或新节点 → 替换含缩进，write_widget 输出已包含缩进
                patches.append((adjusted_start, end, new_text))
            else:
                # 自身未修改但子树有修改 → 只替换关键字起始位置
                patches.append((start, end, new_text))
        # 未修改的 widget 不需要 patch，原文保留

    # 如果有新增的 widget，在 guiTypes 块末尾插入
    if new_roots:
        insert_text_parts = []
        for root in new_roots:
            new_lines = write_widget(root, level=1)
            insert_text_parts.append('\n'.join(new_lines))
        insert_text = '\n\n' + '\n\n'.join(insert_text_parts) + '\n'
        # 在 guiTypes 内部末尾插入（闭合 } 之前）
        patches.append((inner_end, inner_end, insert_text))

    # 检查是否有被删除的 widget（在原始源码中有 span，但不在 doc.roots 中）
    # 通过比较 existing_roots 的 span 和 doc.roots 关联的 span 来判断
    current_spans = set((s, e) for s, e, r in existing_roots)
    # 扫描 raw_source 中 guiTypes 块内的所有 widget 块来找到被删除的
    # 但由于我们已经只跟踪了 doc.roots 中的 span，被删除的 widget 的 span
    # 信息已经不在 doc.roots 中了。我们需要从 _raw_source 识别它们。
    # 简单做法：被删除的 widget 不在 existing_roots 里，它们的 span 也不会被 patch。
    # 它们的原文会被保留在输出中 —— 这实际上不正确，但删除 widget 后
    # 整个文件会被标记为 modified，此时应该使用 find-and-remove 策略。
    # 更好的方案：在解析时记录所有 widget span，即使删除后也能追踪。
    # 目前采用保守策略：如果有任何 widget 被删除，回退到完全重写模式。
    if _has_deleted_widgets(doc, raw, inner_start, inner_end, existing_roots):
        return write_document(doc)

    if not patches:
        # 没有任何修改，返回原始源码
        return raw

    # 按位置降序排列 patches（从后往前应用，不影响前面的偏移量）
    patches.sort(key=lambda p: p[0] if p[0] is not None else float('inf'), reverse=True)

    result = raw
    for start, end, replacement in patches:
        result = result[:start] + replacement + result[end:]

    return result


def _patch_widget_recursive(node: WidgetNode, raw: str, level: int) -> str:
    """递归 patch 一个 widget：仅重新生成自身被修改的部分。

    策略：
    - 如果节点自身被修改（_source_modified=True）→ 完全重新生成
    - 如果节点自身未修改但有子节点被修改 → 在原始源码中只 patch 被修改的子节点
    - 如果节点没有 source_span → 完全生成（新节点）
    """
    if not node._source_span:
        # 新节点，没有原始源码
        return '\n'.join(write_widget(node, level=level))

    if node._source_modified:
        # 自身属性被修改，完全重新生成
        return '\n'.join(write_widget(node, level=level))

    # 自身未修改，但子树中有修改 — 递归 patch 子节点
    span_start = node._source_span.start
    span_end = node._source_span.end
    widget_source = raw[span_start:span_end]

    # 收集需要 patch 的子节点
    child_patches = []  # (relative_start, relative_end, replacement)
    new_children = []  # 没有 source_span 的新子节点

    for child in node.children:
        if child._source_span:
            if child.is_subtree_modified():
                # 子节点需要 patch
                child_start = child._source_span.start
                child_end = child._source_span.end
                child_level = _detect_indent_level(raw, child_start)
                # 递归 patch 子节点
                child_text = _patch_widget_recursive(child, raw, child_level)
                # 转换为相对于 widget_source 的偏移。
                # 关键：_patch_widget_recursive 有两种返回值格式：
                #   - child._source_modified=True  → write_widget() 输出，带缩进前缀
                #     此时替换起点需从行首开始（含原始缩进字符），由新生成的缩进替换
                #   - child._source_modified=False → widget_source（从关键字开头，无前缀空白）
                #     此时替换起点从关键字本身开始，原始行首缩进字符保留在 result 中不被覆盖
                if child._source_modified:
                    rel_start = _line_indent_start(raw, child_start) - span_start
                else:
                    rel_start = child_start - span_start
                rel_end = child_end - span_start
                child_patches.append((rel_start, rel_end, child_text))
        else:
            new_children.append(child)

    # 如果有被删除的子节点，需要检测并移除它们
    # （已被删除的子节点不在 node.children 中，但它们的原始文本还在 widget_source 中）
    existing_child_spans = set()
    for child in node.children:
        if child._source_span:
            existing_child_spans.add((child._source_span.start, child._source_span.end))

    # 检查原始源码中是否有不再存在的子 widget
    # 如果有删除，回退到完全重新生成
    # （因为找出被删除子节点的 span 需要额外的元数据）
    # 简化处理：如果子节点数量变了且非新增，回退重新生成
    original_child_count = sum(1 for c in node.children if c._source_span)
    if len(new_children) > 0:
        # 有新增子节点，需要在合适位置插入
        pass  # 后面处理

    if not child_patches and not new_children:
        # 没有需要改的，返回原始文本
        return widget_source

    # 应用子节点 patch（从后往前）
    result = widget_source
    child_patches.sort(key=lambda p: p[0], reverse=True)
    for rel_start, rel_end, replacement in child_patches:
        result = result[:rel_start] + replacement + result[rel_end:]

    # 插入新子节点（在最后一个 } 之前）
    if new_children:
        insert_parts = []
        child_level = level + 1
        for child in new_children:
            insert_parts.append('\n'.join(write_widget(child, level=child_level)))
        insert_text = '\n\n' + '\n\n'.join(insert_parts) + '\n'
        # 在 widget 源码的最后一个 } 所在行的行首之前插入。
        # 注意：不能只在 } 字符前插入，那样会把行首缩进留在插入内容之前，
        # 导致 } 被顶到下一行列0（缩进丢失）。必须从 \n 前插入，让整行保持原位。
        last_brace = result.rfind('}')
        if last_brace >= 0:
            line_start = result.rfind('\n', 0, last_brace)
            insert_pos = line_start if line_start >= 0 else last_brace
            result = result[:insert_pos] + insert_text + result[insert_pos:]

    return result


def _detect_indent_level(text: str, offset: int) -> int:
    """检测原始源码中指定位置的缩进级别。"""
    line_start = text.rfind('\n', 0, offset)
    if line_start < 0:
        line_start = 0
    else:
        line_start += 1
    indent_str = text[line_start:offset]
    # 计算 tab 数量（混合缩进按 tab 优先）
    tabs = indent_str.count('\t')
    if tabs > 0:
        return tabs
    # 纯空格缩进
    spaces = len(indent_str) - len(indent_str.lstrip(' '))
    if spaces >= 4:
        return spaces // 4
    return spaces // 2 if spaces >= 2 else (1 if spaces > 0 else 1)


def _line_indent_start(text: str, offset: int) -> int:
    """返回 offset 所在行的行首位置（包含缩进）。

    如果 offset 前面到行首都是空白字符，则返回行首位置，
    这样替换时可以包含原始缩进，由 write_widget 重新生成正确缩进。
    """
    line_start = text.rfind('\n', 0, offset)
    if line_start < 0:
        line_start = 0
    else:
        line_start += 1
    between = text[line_start:offset]
    if between.strip() == '':
        return line_start
    return offset


def _has_deleted_widgets(doc: GUIDocument, raw: str,
                          inner_start: int, inner_end: int,
                          existing_roots: list) -> bool:
    """检查是否有 widget 从文件中被删除。

    通过快速扫描 guiTypes 块内部的顶层 widget 关键字数量，
    和当前 doc.roots 数量比较来判断。
    """
    import re
    # 提取 guiTypes 块内部文本
    inner_text = raw[inner_start:inner_end]
    # 统计顶层 widget 块数量（简单启发式：在深度 0 处出现的 widget 关键字 = {）
    widget_keywords = {
        'containerwindowtype', 'icontype', 'buttontype', 'effectbuttontype',
        'instanttextboxtype', 'textboxtype', 'editboxtype', 'checkboxtype',
        'listboxtype', 'scrollareatype', 'overlappingelementsboxtype',
        'gridboxtype', 'smoothlistboxtype', 'extendedscrollbartype',
        'scrollbartype', 'dropdownboxtype', 'guibuttontype', 'spinnertype',
        'windowtype', 'positiontype',
    }
    # 计算在 depth=0 处出现的 widget 定义
    depth = 0
    count = 0
    i = 0
    while i < len(inner_text):
        ch = inner_text[i]
        if ch == '#':
            # 跳过注释行
            nl = inner_text.find('\n', i)
            i = nl + 1 if nl >= 0 else len(inner_text)
            continue
        elif ch == '"':
            j = inner_text.find('"', i + 1)
            i = j + 1 if j >= 0 else len(inner_text)
            continue
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        elif depth == 0 and ch == '=' and i > 0:
            # 回溯找到 = 前面的关键字
            pre = inner_text[:i].rstrip()
            # 提取最后一个 word
            parts = pre.split()
            if parts:
                kw = parts[-1].lower().strip()
                if kw in widget_keywords:
                    count += 1
        i += 1

    # 如果原始文件中的 widget 数量大于当前 doc.roots 数量，说明有删除
    return count > len(doc.roots)


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
