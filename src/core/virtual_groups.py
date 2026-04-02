"""
Virtual group system — independent of the GUI widget tree.

Groups can contain widgets from any hierarchy level. Groups can nest.
Group membership is stored in a sidecar JSON file: <gui_file>.groups.json

This system NEVER modifies the .gui script content.
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class VirtualGroup:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = 'New Group'
    node_names: List[str] = field(default_factory=list)   # widget names (stable identifiers)
    children: List['VirtualGroup'] = field(default_factory=list)
    visible: bool = True
    color: str = '#5dade2'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'node_names': self.node_names,
            'children': [c.to_dict() for c in self.children],
            'visible': self.visible,
            'color': self.color,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'VirtualGroup':
        g = cls(
            id=d.get('id', str(uuid.uuid4())[:8]),
            name=d.get('name', 'Group'),
            node_names=d.get('node_names', []),
            visible=d.get('visible', True),
            color=d.get('color', '#5dade2'),
        )
        g.children = [cls.from_dict(c) for c in d.get('children', [])]
        return g

    def all_node_names(self) -> Set[str]:
        """All widget names covered by this group and its descendants."""
        result: Set[str] = set(self.node_names)
        for child in self.children:
            result |= child.all_node_names()
        return result


class VirtualGroupManager:
    """Manages a set of virtual groups for one GUI document."""

    def __init__(self):
        self.groups: List[VirtualGroup] = []
        self._sidecar_path: str = ''

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self, gui_path: str):
        self._sidecar_path = gui_path + '.groups.json'
        self.groups = []
        if os.path.isfile(self._sidecar_path):
            try:
                with open(self._sidecar_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.groups = [VirtualGroup.from_dict(g) for g in data.get('groups', [])]
            except Exception:
                self.groups = []

    def save(self):
        if not self._sidecar_path:
            return
        data = {'groups': [g.to_dict() for g in self.groups]}
        try:
            with open(self._sidecar_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    def create_group(self, name: str, parent: Optional[VirtualGroup] = None) -> VirtualGroup:
        g = VirtualGroup(name=name)
        if parent is None:
            self.groups.append(g)
        else:
            parent.children.append(g)
        return g

    def find_by_id(self, gid: str) -> Optional[VirtualGroup]:
        def _search(lst: List[VirtualGroup]) -> Optional[VirtualGroup]:
            for g in lst:
                if g.id == gid:
                    return g
                found = _search(g.children)
                if found:
                    return found
            return None
        return _search(self.groups)

    def find_parent(self, gid: str) -> Optional[VirtualGroup]:
        """Return the parent group of the group with given id, or None if at root."""
        def _search(lst: List[VirtualGroup], parent: Optional[VirtualGroup]):
            for g in lst:
                if g.id == gid:
                    return parent
                found = _search(g.children, g)
                if found is not None:
                    return found
            return None
        return _search(self.groups, None)

    def delete_group(self, gid: str):
        parent = self.find_parent(gid)
        lst = parent.children if parent else self.groups
        lst[:] = [g for g in lst if g.id != gid]

    def add_nodes_to_group(self, group: VirtualGroup, names: List[str]):
        for name in names:
            if name and name not in group.node_names:
                group.node_names.append(name)

    def remove_nodes_from_group(self, group: VirtualGroup, names: List[str]):
        group.node_names = [n for n in group.node_names if n not in names]

    def rename_widget(self, old_name: str, new_name: str):
        """将所有组内对 old_name 的引用替换为 new_name。"""
        def _rename(lst: List[VirtualGroup]):
            for g in lst:
                g.node_names = [new_name if n == old_name else n for n in g.node_names]
                _rename(g.children)
        _rename(self.groups)

    def clean_stale_names(self, valid_names: Set[str]):
        """从所有组中删除不在 valid_names 中的控件名（控件已被删除）。"""
        def _clean(lst: List[VirtualGroup]):
            for g in lst:
                g.node_names = [n for n in g.node_names if n in valid_names]
                _clean(g.children)
        _clean(self.groups)

    def get_groups_for_node(self, node_name: str) -> List[VirtualGroup]:
        """Return all groups (at any level) that directly contain this widget."""
        result: List[VirtualGroup] = []
        def _search(lst: List[VirtualGroup]):
            for g in lst:
                if node_name in g.node_names:
                    result.append(g)
                _search(g.children)
        _search(self.groups)
        return result

    def is_node_hidden_by_group(self, node_name: str) -> bool:
        """Return True if any group containing this node is hidden."""
        for g in self.get_groups_for_node(node_name):
            if not g.visible:
                return True
        return False

    def set_visibility(self, group: VirtualGroup, visible: bool):
        group.visible = visible
