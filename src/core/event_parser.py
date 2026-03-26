"""
Stellaris event file parser.

Parses country_event / ship_event / etc. blocks from *.txt files in events/ directories,
extracting GUI-relevant fields:
  - custom_gui        → which GUI key this event uses
  - custom_gui_option → which button widget handles the exit option
  - desc              → event body text (localization key)
  - title             → event title (localization key)
  - picture_event_data.room → room image name
  - options           → list of EventOption (name, custom_gui)
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class EventOption:
    name: str = ''
    custom_gui: str = ''
    desc: str = ''
    hidden: bool = False


@dataclass
class EventInfo:
    id: str = ''
    title: str = ''
    desc: str = ''
    event_type: str = ''   # 'country_event', 'fleet_event', etc.
    custom_gui: str = ''
    custom_gui_option: str = ''
    room: str = ''                         # from picture_event_data.room
    is_scope_room: bool = False            # True if room is a scope (root/this/event_target:...)
    options: List[EventOption] = field(default_factory=list)
    file_path: str = ''


# ------------------------------------------------------------------
# Lightweight tokeniser (not using PDXParser to keep this standalone)
# ------------------------------------------------------------------

_EVENT_TYPES = {
    'country_event', 'fleet_event', 'ship_event', 'pop_event',
    'planet_event', 'pop_faction_event', 'leader_event',
    'army_event', 'espionage_operation',
}

_SCOPE_KEYWORDS = frozenset({'root', 'this', 'from', 'fromfrom', 'prev', 'prevprev'})


def _is_scope(val: str) -> bool:
    v = val.lower()
    return v in _SCOPE_KEYWORDS or v.startswith('event_target:')


def _tokenise(text: str) -> List[str]:
    """Very fast tokeniser: splits on whitespace and braces."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '#':
            # skip to end of line
            while i < n and text[i] != '\n':
                i += 1
        elif c in ('{', '}', '='):
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            tokens.append(text[i:j+1])
            i = j + 1
        elif c in (' ', '\t', '\n', '\r'):
            i += 1
        else:
            j = i
            while j < n and text[j] not in (' ', '\t', '\n', '\r', '{', '}', '=', '#', '"'):
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def _parse_block(tokens: List[str], pos: int) -> tuple[dict, int]:
    """
    Parse a { ... } block starting after the '{' token at pos.
    Returns (dict of key→value or key→subdict, next_pos).
    """
    result: dict = {}
    while pos < len(tokens):
        tok = tokens[pos]
        if tok == '}':
            return result, pos + 1
        if pos + 1 < len(tokens) and tokens[pos + 1] == '=':
            key = tok.lower()
            pos += 2
            if pos < len(tokens):
                if tokens[pos] == '{':
                    sub, pos = _parse_block(tokens, pos + 1)
                    if key in result:
                        # multiple values for same key (options): accumulate as list
                        existing = result[key]
                        if not isinstance(existing, list):
                            result[key] = [existing]
                        result[key].append(sub)
                    else:
                        result[key] = sub
                else:
                    val = _strip_quotes(tokens[pos])
                    if key in result:
                        existing = result[key]
                        if not isinstance(existing, list):
                            result[key] = [existing]
                        result[key].append(val)
                    else:
                        result[key] = val
                    pos += 1
        else:
            pos += 1  # bare token, skip
    return result, pos


def _parse_events_from_tokens(tokens: List[str], file_path: str) -> List[EventInfo]:
    events: List[EventInfo] = []
    pos = 0
    n = len(tokens)
    while pos < n:
        tok = tokens[pos].lower()
        if tok in _EVENT_TYPES and pos + 1 < n and tokens[pos + 1] == '=':
            evt_type = tok
            pos += 2
            if pos < n and tokens[pos] == '{':
                block, pos = _parse_block(tokens, pos + 1)
                evt = _build_event_info(block, evt_type, file_path)
                if evt.custom_gui:
                    events.append(evt)
        else:
            pos += 1
    return events


def _build_event_info(block: dict, evt_type: str, file_path: str) -> EventInfo:
    evt = EventInfo(file_path=file_path, event_type=evt_type)
    evt.id = block.get('id', '')
    evt.title = block.get('title', '')
    evt.desc = block.get('desc', '')
    evt.custom_gui = block.get('custom_gui', '')
    evt.custom_gui_option = block.get('custom_gui_option', '')

    # picture_event_data = { room = ... }
    ped = block.get('picture_event_data', {})
    if isinstance(ped, dict):
        room_val = ped.get('room', '')
        if room_val:
            evt.room = room_val
            evt.is_scope_room = _is_scope(room_val)

    # options
    opts = block.get('option', [])
    if isinstance(opts, dict):
        opts = [opts]
    if isinstance(opts, list):
        for opt in opts:
            if isinstance(opt, dict):
                eo = EventOption(
                    name=opt.get('name', ''),
                    custom_gui=opt.get('custom_gui', ''),
                    desc=opt.get('desc', ''),
                    hidden=opt.get('default_hide_option', '') == 'yes',
                )
                evt.options.append(eo)

    return evt


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def parse_event_file(path: str) -> List[EventInfo]:
    """Parse a single event .txt file, return events with custom_gui set."""
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc, errors='strict') as f:
                text = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        except Exception:
            return []

    tokens = _tokenise(text)
    return _parse_events_from_tokens(tokens, path)


def scan_event_dirs(search_dirs: List[str]) -> Dict[str, List[EventInfo]]:
    """
    Scan events/ folders under each directory in search_dirs.
    Returns a dict: custom_gui_name → [EventInfo, ...]
    Deduplicates by event id.
    """
    result: Dict[str, List[EventInfo]] = {}
    seen_ids: set = set()

    for base in search_dirs:
        evt_dir = os.path.join(base, 'events')
        if not os.path.isdir(evt_dir):
            continue
        for root, dirs, files in os.walk(evt_dir):
            for fname in files:
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    events = parse_event_file(fpath)
                except Exception:
                    continue
                for ev in events:
                    key = (ev.custom_gui, ev.id)
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)
                    result.setdefault(ev.custom_gui, []).append(ev)

    return result
