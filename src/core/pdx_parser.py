"""
PDX Script parser for Stellaris .gui and .gfx files.
Handles the Clausewitz engine script format.

Supports:
- Key = value pairs (quoted/unquoted strings, numbers, yes/no)
- Nested blocks { }
- Comments (# ...)
- @variable = value definitions and @variable references
- Multiple values with same key (stored as lists)
- position/size shorthand: { x = N y = M } or { N M }
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Source span tracking for roundtrip preservation
# ---------------------------------------------------------------------------

@dataclass
class SourceSpan:
    """Character offset range [start, end) in original source text."""
    start: int
    end: int


@dataclass
class WidgetSpanInfo:
    """Source span info for a parsed widget block.

    Tracks the full span (including 'widgetType = { ... }') and inner span
    (between { and }). Children spans are tracked recursively.
    """
    widget_type: str
    name: str  # widget name if found, else ''
    full_span: SourceSpan  # 从 widget_type 关键字到闭合 } (inclusive)
    children: List['WidgetSpanInfo'] = field(default_factory=list)


@dataclass
class ParseResultWithSpans:
    """Parser result that includes source span mapping for roundtrip support."""
    pairs: List[Tuple[str, Any]]
    raw_source: str
    widget_spans: List[WidgetSpanInfo]  # 顶层 widget 的 span 信息
    # guiTypes 块的 span 信息（如有）
    guitypes_span: Optional[SourceSpan] = None
    # guiTypes 块内部（{ 之后到 } 之前）的 span
    guitypes_inner_span: Optional[SourceSpan] = None
    # 文件内 @变量 定义表（供 GUIDocument 保存）
    variables: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TOKEN_PATTERNS = [
    ('COMMENT',  r'#[^\n]*'),
    ('EXPR',     r'@\[[^\]]*\]'),        # @[ math expression ] — must come before IDENT
    ('STRING',   r'"(?:[^"\\]|\\.)*"'),
    # Trailing % is one token so size = { width = 100% } preserves percentage (Stellaris GUI).
    ('NUMBER',   r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?%?'),
    ('IDENT',    r'[A-Za-z_@][A-Za-z0-9_.\-/\\:]*'),
    ('EQUALS',   r'='),
    ('LBRACE',   r'\{'),
    ('RBRACE',   r'\}'),
    ('NEWLINE',  r'\n'),
    ('SKIP',     r'[ \t\r]+'),
    ('MISMATCH', r'.'),
]

_TOKEN_RE = re.compile(
    '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_PATTERNS)
)


class Token:
    __slots__ = ('type', 'value', 'line', 'offset')

    def __init__(self, type_: str, value: str, line: int, offset: int = -1):
        self.type = type_
        self.value = value
        self.line = line
        self.offset = offset  # 字符偏移量（在原始文本中的位置）

    def __repr__(self):
        return f'Token({self.type}, {self.value!r}, line={self.line}, off={self.offset})'


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    line = 1
    bom_offset = 0
    # Strip UTF-8 BOM if present
    if text.startswith('\ufeff'):
        text = text[1:]
        bom_offset = 1
    for mo in _TOKEN_RE.finditer(text):
        kind = mo.lastgroup
        value = mo.group()
        offset = mo.start() + bom_offset
        if kind == 'NEWLINE':
            line += 1
        elif kind in ('SKIP', 'COMMENT'):
            # Count newlines in comments/whitespace
            line += value.count('\n')
        elif kind == 'MISMATCH':
            pass  # Ignore unexpected chars
        else:
            tokens.append(Token(kind, value, line, offset))
    tokens.append(Token('EOF', '', line, len(text) + bom_offset))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    pass


class PDXParser:
    """
    Parses PDX script into a nested Python structure.

    The returned value for parse() is a list of (key, value) pairs
    at the top level. This preserves multiple values with same key.

    Values can be:
      - str (unquoted identifier or quoted string, quotes stripped)
      - int / float (numeric)
      - bool (yes/no → True/False)
      - list of (key, value) pairs (for blocks {})
    """

    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.pos = 0
        self.variables: Dict[str, Any] = {}
        self._source_text = text

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def consume(self, expected_type: Optional[str] = None) -> Token:
        tok = self.tokens[self.pos]
        if expected_type and tok.type != expected_type:
            raise ParseError(
                f'Line {tok.line}: Expected {expected_type}, got {tok.type} ({tok.value!r})'
            )
        self.pos += 1
        return tok

    def parse(self) -> List[Tuple[str, Any]]:
        """Parse the entire file, return list of (key, value) pairs."""
        result = []
        while self.peek().type != 'EOF':
            pairs = self._parse_pairs()
            result.extend(pairs)
        return result

    def parse_with_spans(self) -> ParseResultWithSpans:
        """Parse the file and return results with source span info for roundtrip."""
        result = []
        widget_spans: List[WidgetSpanInfo] = []
        guitypes_span: Optional[SourceSpan] = None
        guitypes_inner_span: Optional[SourceSpan] = None

        while self.peek().type != 'EOF':
            tok = self.peek()
            # 检测 guiTypes = { ... } 块
            if tok.type == 'IDENT' and tok.value.lower() == 'guitypes':
                gt_start = tok.offset
                key_tok = self.consume('IDENT')
                if self.peek().type == 'EQUALS':
                    self.consume('EQUALS')
                    if self.peek().type == 'LBRACE':
                        lbrace = self.consume('LBRACE')
                        inner_start = lbrace.offset + 1
                        # 解析 guiTypes 块内容，同时追踪每个 widget 的 span
                        pairs_in_gt = []
                        while self.peek().type not in ('RBRACE', 'EOF'):
                            child_spans = self._parse_pairs_with_spans(pairs_in_gt)
                            widget_spans.extend(child_spans)
                        rbrace_tok = self.peek()
                        inner_end = rbrace_tok.offset
                        if rbrace_tok.type == 'RBRACE':
                            self.consume('RBRACE')
                            guitypes_span = SourceSpan(gt_start, rbrace_tok.offset + 1)
                            guitypes_inner_span = SourceSpan(inner_start, inner_end)
                        result.append((key_tok.value, pairs_in_gt))
                    else:
                        val = self._parse_value()
                        result.append((key_tok.value, val))
                else:
                    result.append(('_value', key_tok.value))
            else:
                pairs = self._parse_pairs()
                result.extend(pairs)

        return ParseResultWithSpans(
            pairs=result,
            raw_source=self._source_text,
            widget_spans=widget_spans,
            guitypes_span=guitypes_span,
            guitypes_inner_span=guitypes_inner_span,
            variables=dict(self.variables),
        )

    def _parse_pairs_with_spans(self, out_pairs: list) -> List[WidgetSpanInfo]:
        """Parse pairs within guiTypes block, tracking widget source spans."""
        spans: List[WidgetSpanInfo] = []
        tok = self.peek()
        if tok.type == 'EOF' or tok.type == 'RBRACE':
            return spans

        if tok.type == 'IDENT' and tok.value.startswith('@'):
            # Variable definition: @VAR = value
            key_tok = self.consume('IDENT')
            if self.peek().type == 'EQUALS':
                self.consume('EQUALS')
                val = self._parse_value()
                self.variables[key_tok.value] = val
                return spans
            else:
                return spans

        if tok.type in ('IDENT', 'STRING', 'NUMBER'):
            key_start_offset = tok.offset
            key = self._parse_scalar()
            if isinstance(key, str) and self.peek().type == 'EQUALS':
                self.consume('EQUALS')
                if self.peek().type == 'LBRACE':
                    # 可能是 widget 块
                    block_val, child_spans = self._parse_block_with_spans()
                    out_pairs.append((str(key), block_val))
                    # 确定闭合 } 的位置 — 上一个已消费的 token
                    end_offset = self.tokens[self.pos - 1].offset + 1
                    # 提取 widget name
                    wname = ''
                    for k, v in block_val:
                        if k == 'name' and isinstance(v, str):
                            wname = v
                            break
                    span_info = WidgetSpanInfo(
                        widget_type=str(key),
                        name=wname,
                        full_span=SourceSpan(key_start_offset, end_offset),
                        children=child_spans,
                    )
                    spans.append(span_info)
                else:
                    val = self._parse_value()
                    out_pairs.append((str(key), val))
            else:
                out_pairs.append(('_value', key))
        elif tok.type == 'LBRACE':
            val = self._parse_block()
            out_pairs.append(('_block', val))
        else:
            self.consume()

        return spans

    def _parse_block_with_spans(self) -> Tuple[List[Tuple[str, Any]], List[WidgetSpanInfo]]:
        """Parse a { ... } block, returning both pairs and child widget spans."""
        self.consume('LBRACE')
        pairs: List[Tuple[str, Any]] = []
        child_spans: List[WidgetSpanInfo] = []
        while self.peek().type not in ('RBRACE', 'EOF'):
            new_spans = self._parse_pairs_with_spans(pairs)
            child_spans.extend(new_spans)
        if self.peek().type == 'RBRACE':
            self.consume('RBRACE')
        return pairs, child_spans

    def _parse_pairs(self) -> List[Tuple[str, Any]]:
        """Parse key=value pairs until end of current block or EOF."""
        pairs = []
        tok = self.peek()
        if tok.type == 'EOF' or tok.type == 'RBRACE':
            return pairs

        if tok.type == 'IDENT' and tok.value.startswith('@'):
            # Variable definition: @VAR = value
            key_tok = self.consume('IDENT')
            if self.peek().type == 'EQUALS':
                self.consume('EQUALS')
                val = self._parse_value()
                self.variables[key_tok.value] = val
                return pairs
            else:
                # Standalone @VAR reference (unusual at top level)
                return pairs

        if tok.type in ('IDENT', 'STRING', 'NUMBER'):
            key = self._parse_scalar()
            if isinstance(key, str) and self.peek().type == 'EQUALS':
                self.consume('EQUALS')
                val = self._parse_value()
                pairs.append((str(key), val))
            else:
                # Lone value (e.g., inside animation block)
                pairs.append(('_value', key))
        elif tok.type == 'LBRACE':
            # Anonymous block
            val = self._parse_block()
            pairs.append(('_block', val))
        else:
            # Skip unexpected token
            self.consume()

        return pairs

    def _parse_value(self) -> Any:
        tok = self.peek()
        if tok.type == 'LBRACE':
            return self._parse_block()
        elif tok.type == 'EXPR':
            # @[ math expression ] — evaluate and return numeric result
            expr_tok = self.consume('EXPR')
            return self._eval_expr(expr_tok.value)
        elif tok.type == 'IDENT' and tok.value.startswith('@'):
            # Variable reference: @VAR_NAME
            ref_tok = self.consume('IDENT')
            return self.variables.get(ref_tok.value, ref_tok.value)
        else:
            return self._parse_scalar()

    def _eval_expr(self, expr_str: str) -> Any:
        """Evaluate a @[ ... ] math expression.

        Inside @[ ] Stellaris uses bare variable names (without @), e.g.
        @[ shroudPlaneRadius / 2 ].  Also supports @name syntax inside brackets.
        """
        # Strip "@[" and "]"
        inner = expr_str[2:-1].strip()

        def _replace_var(m):
            name = m.group(1)  # identifier text (no leading @)
            # Look up with @name first (how parser stores them), then bare name
            val = self.variables.get('@' + name, self.variables.get(name, None))
            if val is not None:
                try:
                    return str(float(val))
                except (TypeError, ValueError):
                    pass
            return '0'

        # Pass 1: explicit @varname syntax inside brackets
        inner = re.sub(r'@([A-Za-z_][A-Za-z0-9_]*)', _replace_var, inner)
        # Pass 2: bare identifier syntax (Stellaris standard: @[ varName / 2 ])
        inner = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', _replace_var, inner)

        # Evaluate safely using only basic arithmetic
        try:
            # Only allow digits, spaces, and arithmetic operators
            if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', inner):
                result = eval(inner, {"__builtins__": {}})  # noqa: S307
                v = float(result)
                return int(v) if v == int(v) else v
        except Exception:
            pass
        return 0

    def _parse_scalar(self) -> Any:
        tok = self.peek()
        if tok.type == 'NUMBER':
            self.consume()
            s = tok.value
            if s.endswith('%'):
                return s  # e.g. "100%", "85%" — resolved against parent in gui_model layout
            return float(s) if '.' in s or 'e' in s.lower() else int(s)
        elif tok.type == 'STRING':
            self.consume()
            # Strip surrounding quotes, unescape
            return tok.value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        elif tok.type == 'IDENT':
            self.consume()
            v = tok.value
            if v.lower() == 'yes':
                return True
            elif v.lower() == 'no':
                return False
            elif v.startswith('@'):
                return self.variables.get(v, v)
            return v
        else:
            raise ParseError(f'Line {tok.line}: Unexpected token {tok.type} ({tok.value!r})')

    def _parse_block(self) -> List[Tuple[str, Any]]:
        self.consume('LBRACE')
        pairs = []
        while self.peek().type not in ('RBRACE', 'EOF'):
            new_pairs = self._parse_pairs()
            pairs.extend(new_pairs)
        if self.peek().type == 'RBRACE':
            self.consume('RBRACE')
        return pairs


# ---------------------------------------------------------------------------
# Helper: convert list-of-pairs to dict (merging duplicates into lists)
# ---------------------------------------------------------------------------

def pairs_to_dict(pairs: List[Tuple[str, Any]], *, recursive: bool = True) -> Dict[str, Any]:
    """
    Convert a list of (key, value) pairs to a dict.
    When a key appears multiple times, its values are gathered into a list.
    If recursive=True, nested pair-lists are also converted.
    """
    result: Dict[str, Any] = {}
    for key, val in pairs:
        if recursive and isinstance(val, list) and val and isinstance(val[0], tuple):
            val = pairs_to_dict(val, recursive=True)
        if key in result:
            existing = result[key]
            if not isinstance(existing, list):
                result[key] = [existing]
            result[key].append(val)
        else:
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_ENCODINGS_TO_TRY = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']


def parse_file(path: str, encoding: str = '') -> List[Tuple[str, Any]]:
    """Parse a PDX script file, return list of (key, value) pairs.

    Tries multiple encodings (UTF-8 BOM, UTF-8, CP-1252, Latin-1) to handle
    the wide variety of encodings found in Stellaris mod files.
    """
    text = None
    encodings = [encoding] if encoding else _ENCODINGS_TO_TRY
    last_err = None
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc, errors='strict') as f:
                text = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
        except Exception as e:
            last_err = e
            break
    if text is None:
        # Final fallback with replacement characters
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        except Exception as e:
            raise ParseError(f'Cannot read file {path!r}: {last_err or e}')

    return _parse_text_with_recovery(text, path)


def parse_text(text: str) -> List[Tuple[str, Any]]:
    """Parse PDX script text, return list of (key, value) pairs."""
    return _parse_text_with_recovery(text)


def _parse_text_with_recovery(text: str, source: str = '<text>') -> List[Tuple[str, Any]]:
    """Parse with error recovery: on failure, try to skip offending sections."""
    try:
        parser = PDXParser(text)
        return parser.parse()
    except ParseError:
        # Error recovery: try splitting at top-level braces and parsing each section
        results: List[Tuple[str, Any]] = []
        _try_partial_parse(text, results)
        return results
    except Exception:
        return []


def _try_partial_parse(text: str, results: list):
    """Best-effort recovery parser: extract as many valid top-level blocks as possible."""
    # Find top-level blocks by matching outermost braces
    depth = 0
    block_start = -1
    key_start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '#':
            # Skip comment line
            i = text.find('\n', i)
            if i < 0:
                break
        elif ch == '"':
            # Skip quoted string
            j = text.find('"', i + 1)
            i = j if j >= 0 else len(text)
        elif ch == '{':
            if depth == 0:
                block_start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and block_start >= 0:
                # Extract the key before this block
                prefix = text[key_start:block_start].strip()
                block_text = text[block_start:i + 1]
                key_end = prefix.rfind('=')
                if key_end >= 0:
                    key = prefix[key_end - len(prefix.split()[-1] if prefix.split() else ''):key_end].strip()
                    if not key:
                        key = prefix[:key_end].split()[-1] if prefix[:key_end].split() else '_block'
                    full_section = f'{key} = {block_text}'
                else:
                    full_section = block_text
                try:
                    partial = PDXParser(full_section)
                    results.extend(partial.parse())
                except Exception:
                    pass
                key_start = i + 1
                block_start = -1
        i += 1


def parse_file_with_spans(path: str, encoding: str = '') -> ParseResultWithSpans:
    """Parse a PDX script file, return results with source span info for roundtrip.

    Tries multiple encodings (UTF-8 BOM, UTF-8, CP-1252, Latin-1).
    """
    text = None
    detected_encoding = 'utf-8'
    encodings = [encoding] if encoding else _ENCODINGS_TO_TRY
    last_err = None
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc, errors='strict') as f:
                text = f.read()
            detected_encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
        except Exception as e:
            last_err = e
            break
    if text is None:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            detected_encoding = 'utf-8'
        except Exception as e:
            raise ParseError(f'Cannot read file {path!r}: {last_err or e}')

    try:
        parser = PDXParser(text)
        result = parser.parse_with_spans()
        return result
    except Exception:
        # Fallback: 返回基础结果，不含 span 信息
        pairs = _parse_text_with_recovery(text, path)
        return ParseResultWithSpans(
            pairs=pairs,
            raw_source=text,
            widget_spans=[],
            guitypes_span=None,
            guitypes_inner_span=None,
        )


def parse_file_as_dict(path: str) -> Dict[str, Any]:
    """Parse a PDX script file, return merged dict."""
    pairs = parse_file(path)
    return pairs_to_dict(pairs)


# ---------------------------------------------------------------------------
# Utility: extract vec2 from a block like {x=10 y=20} or {10 20}
# ---------------------------------------------------------------------------

def extract_vec2(val: Any, key1: str = 'x', key2: str = 'y') -> Tuple[int, int]:
    """Extract a 2D vector from a PDX block value."""
    if isinstance(val, dict):
        x = val.get(key1, val.get('x', 0))
        y = val.get(key2, val.get('y', 0))
        return int(x), int(y)
    if isinstance(val, list):
        if val and isinstance(val[0], tuple):
            d = pairs_to_dict(val)
            x = d.get(key1, d.get('x', 0))
            y = d.get(key2, d.get('y', 0))
            return int(x), int(y)
        nums = [v for v in val if isinstance(v, (int, float))]
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
    return 0, 0


def extract_size(val: Any) -> Tuple[int, int]:
    """Extract width/height from a size block. Tries width/height first, then x/y."""
    if isinstance(val, dict):
        if 'width' in val or 'height' in val:
            return int(val.get('width', 0)), int(val.get('height', 0))
        return int(val.get('x', 0)), int(val.get('y', 0))
    if isinstance(val, list) and val and isinstance(val[0], tuple):
        d = pairs_to_dict(val)
        if 'width' in d or 'height' in d:
            return int(d.get('width', 0)), int(d.get('height', 0))
        return int(d.get('x', 0)), int(d.get('y', 0))
    return 0, 0
