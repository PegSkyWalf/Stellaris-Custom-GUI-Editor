"""Regression tests for layer reordering and preserving writer order."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from src.core.gui_model import create_widget, parse_gui_text
from src.codegen.gui_writer import write_document_preserving


def _first_index(text: str, name: str) -> int:
    idx = text.find(f'name = "{name}"')
    assert idx >= 0, f'{name} not found in generated text'
    return idx


def test_root_reorder_preserving_text_matches_model_order():
    raw = '''guiTypes = {
    containerWindowType = {
        name = "A"
        iconType = { name = "A_child" position = { x = 1 y = 1 } }
    }
    containerWindowType = {
        name = "B"
        iconType = { name = "B_child" position = { x = 2 y = 2 } }
    }
}
'''
    doc = parse_gui_text(raw)
    doc.roots = [doc.roots[1], doc.roots[0]]
    for root in doc.roots:
        root._source_modified = True

    out = write_document_preserving(doc)
    assert _first_index(out, 'B') < _first_index(out, 'A')


def test_child_reorder_preserving_text_matches_model_order():
    raw = '''guiTypes = {
    containerWindowType = {
        name = "Root"
        iconType = { name = "A" position = { x = 1 y = 1 } }
        iconType = { name = "B" position = { x = 2 y = 2 } }
    }
}
'''
    doc = parse_gui_text(raw)
    root = doc.roots[0]
    root.children = [root.children[1], root.children[0]]
    root._source_modified = True
    for child in root.children:
        child.parent = root

    out = write_document_preserving(doc)
    assert _first_index(out, 'B') < _first_index(out, 'A')


def test_new_root_inserted_between_existing_roots_keeps_model_order():
    raw = '''guiTypes = {
    containerWindowType = {
        name = "A"
    }
    containerWindowType = {
        name = "B"
    }
}
'''
    doc = parse_gui_text(raw)
    new_root = create_widget('containerWindowType', 'C')
    doc.roots = [doc.roots[0], new_root, doc.roots[1]]

    out = write_document_preserving(doc)
    assert _first_index(out, 'A') < _first_index(out, 'C') < _first_index(out, 'B')


def test_new_child_inserted_between_existing_children_keeps_model_order():
    raw = '''guiTypes = {
    containerWindowType = {
        name = "Root"
        iconType = { name = "A" position = { x = 1 y = 1 } }
        iconType = { name = "B" position = { x = 2 y = 2 } }
    }
}
'''
    doc = parse_gui_text(raw)
    root = doc.roots[0]
    new_child = create_widget('iconType', 'C')
    root.children = [root.children[0], new_child, root.children[1]]
    for child in root.children:
        child.parent = root

    out = write_document_preserving(doc)
    assert _first_index(out, 'A') < _first_index(out, 'C') < _first_index(out, 'B')


def test_layer_panel_tree_roundtrip_preserves_model_order(qapp=None):
    from PySide6.QtWidgets import QApplication
    from src.ui.layer_panel import LayerPanel
    _app = QApplication.instance() or QApplication([])
    doc = parse_gui_text('''guiTypes = {
    containerWindowType = {
        name = "A"
    }
    containerWindowType = {
        name = "B"
    }
}
''')
    panel = LayerPanel()
    panel.populate(doc)
    panel._sync_model_from_tree()
    assert [root.name for root in doc.roots] == ['A', 'B']


if __name__ == '__main__':
    test_root_reorder_preserving_text_matches_model_order()
    test_child_reorder_preserving_text_matches_model_order()
    test_new_root_inserted_between_existing_roots_keeps_model_order()
    test_new_child_inserted_between_existing_children_keeps_model_order()
    test_layer_panel_tree_roundtrip_preserves_model_order()
    print('layer roundtrip order tests: PASS')
