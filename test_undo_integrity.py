"""Regression tests for undo/redo model integrity."""
from src.core.gui_model import GUIDocument, create_widget
from src.core.undo import AddWidgetCommand, DuplicateWidgetCommand


def _assert_unique_object_refs(doc: GUIDocument):
    widgets = doc.all_widgets()
    ids = [id(w) for w in widgets]
    assert len(ids) == len(set(ids)), 'Widget tree contains duplicate object references'


def test_add_widget_redo_does_not_duplicate():
    doc = GUIDocument()
    node = create_widget('buttonType', 'btn')
    cmd = AddWidgetCommand(doc, node, None, 0)

    cmd.execute()
    cmd.undo()
    cmd.execute()
    cmd.execute()

    assert doc.roots == [node]
    assert node.parent is None
    _assert_unique_object_refs(doc)


def test_duplicate_redo_reuses_single_clone():
    original = create_widget('buttonType', 'orig')
    doc = GUIDocument(roots=[original])
    cmd = DuplicateWidgetCommand(doc, original)

    cmd.execute()
    first_clone = cmd.clone
    cmd.undo()
    cmd.execute()
    cmd.execute()

    assert first_clone is not None
    assert doc.roots == [original, first_clone]
    assert first_clone.parent is None
    assert first_clone.name == 'orig_1'
    _assert_unique_object_refs(doc)


def test_duplicate_child_undo_redo_keeps_single_parent_ref():
    parent = create_widget('containerWindowType', 'parent')
    original = create_widget('buttonType', 'child')
    parent.add_child(original)
    doc = GUIDocument(roots=[parent])
    cmd = DuplicateWidgetCommand(doc, original)

    cmd.execute()
    first_clone = cmd.clone
    assert first_clone is not None
    assert first_clone.parent is parent
    assert parent.children == [original, first_clone]

    cmd.undo()
    assert first_clone not in parent.children
    assert first_clone.parent is None

    cmd.execute()
    cmd.execute()
    assert parent.children == [original, first_clone]
    assert first_clone.parent is parent
    _assert_unique_object_refs(doc)


if __name__ == '__main__':
    test_add_widget_redo_does_not_duplicate()
    test_duplicate_redo_reuses_single_clone()
    test_duplicate_child_undo_redo_keeps_single_parent_ref()
    print('undo integrity tests: PASS')
