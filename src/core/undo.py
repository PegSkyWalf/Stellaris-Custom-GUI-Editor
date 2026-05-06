"""
Undo/redo command system for the Stellaris GUI editor.
Uses the Command pattern.
"""
from __future__ import annotations
import copy
from typing import Any, Callable, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .gui_model import WidgetNode, GUIDocument


class Command:
    """Base class for undoable commands."""
    def __init__(self, description: str = ''):
        self.description = description

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError


class MoveWidgetCommand(Command):
    def __init__(self, node: 'WidgetNode', old_pos: Tuple[int, int], new_pos: Tuple[int, int]):
        super().__init__(f'移动控件 {node.name!r}')
        self.node = node
        self.old_pos = old_pos
        self.new_pos = new_pos

    def execute(self):
        self.node.position = self.new_pos
        self.node._source_modified = True

    def undo(self):
        self.node.position = self.old_pos
        self.node._source_modified = True


class ResizeWidgetCommand(Command):
    def __init__(self, node: 'WidgetNode', old_size: Tuple[int, int], new_size: Tuple[int, int]):
        super().__init__(f'调整控件大小 {node.name!r}')
        self.node = node
        self.old_size = old_size
        self.new_size = new_size

    def execute(self):
        self.node.size = self.new_size
        self.node._source_modified = True

    def undo(self):
        self.node.size = self.old_size
        self.node._source_modified = True


class SetPropertyCommand(Command):
    def __init__(self, node: 'WidgetNode', key: str, old_val: Any, new_val: Any):
        super().__init__(f'修改属性 {key!r}')
        self.node = node
        self.key = key
        self.old_val = old_val
        self.new_val = new_val

    def execute(self):
        if self.new_val is None:
            self.node.properties.pop(self.key, None)
        else:
            self.node.properties[self.key] = self.new_val
        self.node._source_modified = True

    def undo(self):
        if self.old_val is None:
            self.node.properties.pop(self.key, None)
        else:
            self.node.properties[self.key] = self.old_val
        self.node._source_modified = True


class AddWidgetCommand(Command):
    def __init__(
        self,
        doc: 'GUIDocument',
        node: 'WidgetNode',
        parent: Optional['WidgetNode'],
        insert_index: int = -1,
    ):
        super().__init__(f'添加控件 {node.widget_type}')
        self.doc = doc
        self.node = node
        self.parent = parent
        self.insert_index = insert_index

    def execute(self):
        self.node._source_modified = True
        if self.parent:
            self.parent._source_modified = True
            if self.node in self.parent.children:
                self.node.parent = self.parent
                return
            if self.insert_index >= 0:
                idx = min(self.insert_index, len(self.parent.children))
                self.parent.insert_child(idx, self.node)
            else:
                self.parent.add_child(self.node)
        else:
            if self.node in self.doc.roots:
                self.node.parent = None
                return
            if self.insert_index >= 0:
                idx = min(self.insert_index, len(self.doc.roots))
                self.doc.roots.insert(idx, self.node)
            else:
                self.doc.roots.append(self.node)
            self.node.parent = None

    def undo(self):
        if self.parent:
            self.parent._source_modified = True
            while self.node in self.parent.children:
                self.parent.remove_child(self.node)
        else:
            while self.node in self.doc.roots:
                self.doc.roots.remove(self.node)
        self.node.parent = None


class DeleteWidgetCommand(Command):
    def __init__(self, doc: 'GUIDocument', node: 'WidgetNode'):
        super().__init__(f'删除控件 {node.name!r}')
        self.doc = doc
        self.node = node
        self.parent = node.parent
        self.index = -1

    def execute(self):
        if self.parent:
            self.parent._source_modified = True
            try:
                self.index = self.parent.children.index(self.node)
            except ValueError:
                self.index = -1
            while self.node in self.parent.children:
                self.parent.remove_child(self.node)
        elif self.node in self.doc.roots:
            try:
                self.index = self.doc.roots.index(self.node)
            except ValueError:
                self.index = -1
            while self.node in self.doc.roots:
                self.doc.roots.remove(self.node)
            self.node.parent = None

    def undo(self):
        if self.parent:
            self.parent._source_modified = True
            if self.index >= 0:
                self.parent.insert_child(self.index, self.node)
            else:
                self.parent.add_child(self.node)
        else:
            if self.index >= 0:
                self.doc.roots.insert(self.index, self.node)
            else:
                self.doc.roots.append(self.node)


class DuplicateWidgetCommand(Command):
    def __init__(self, doc: 'GUIDocument', original: 'WidgetNode'):
        super().__init__(f'复制控件 {original.name!r}')
        self.doc = doc
        self.original = original
        self.clone: Optional['WidgetNode'] = None

    def execute(self):
        from .gui_model import make_names_unique
        if self.clone is None:
            self.clone = self.original.clone()
            # 自动生成唯一名称
            existing = {w.name for w in self.doc.all_widgets() if w.name}
            make_names_unique(self.clone, existing)
            x, y = self.clone.position
            self.clone.position = (x + 16, y + 16)
        self.clone._source_modified = True
        if self.original.parent:
            self.original.parent._source_modified = True
            if self.clone not in self.original.parent.children:
                self.original.parent.add_child(self.clone)
            else:
                self.clone.parent = self.original.parent
        else:
            if self.clone not in self.doc.roots:
                self.doc.roots.append(self.clone)
            self.clone.parent = None

    def undo(self):
        if self.clone:
            if self.clone.parent:
                parent = self.clone.parent
                parent._source_modified = True
                while self.clone in parent.children:
                    parent.remove_child(self.clone)
            else:
                while self.clone in self.doc.roots:
                    self.doc.roots.remove(self.clone)
                self.clone.parent = None


class CompoundCommand(Command):
    """Groups multiple commands into one undoable action."""
    def __init__(self, commands: List[Command], description: str = '复合操作'):
        super().__init__(description)
        self.commands = commands

    def execute(self):
        for cmd in self.commands:
            cmd.execute()

    def undo(self):
        for cmd in reversed(self.commands):
            cmd.undo()


class UndoStack:
    """
    Manages an undo/redo history stack.
    Commands are pushed after execution.
    """
    MAX_SIZE = 100

    def __init__(self, on_change: Optional[Callable] = None):
        self._undo: List[Command] = []
        self._redo: List[Command] = []
        self._on_change = on_change

    def push(self, command: Command, execute: bool = True):
        """Push a command. If execute=True, run it first."""
        if execute:
            command.execute()
        self._undo.append(command)
        if len(self._undo) > self.MAX_SIZE:
            self._undo.pop(0)
        self._redo.clear()
        if self._on_change:
            self._on_change()

    def undo(self) -> Optional[str]:
        """Undo the last command. Returns description or None."""
        if not self._undo:
            return None
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)
        if self._on_change:
            self._on_change()
        return cmd.description

    def redo(self) -> Optional[str]:
        """Redo the last undone command. Returns description or None."""
        if not self._redo:
            return None
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)
        if self._on_change:
            self._on_change()
        return cmd.description

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo_description(self) -> str:
        return self._undo[-1].description if self._undo else ''

    def redo_description(self) -> str:
        return self._redo[-1].description if self._redo else ''

    def clear(self):
        self._undo.clear()
        self._redo.clear()
        if self._on_change:
            self._on_change()
