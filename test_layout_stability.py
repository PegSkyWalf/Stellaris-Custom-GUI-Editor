"""Regression tests for implicit-container coordinate stability."""
from src.core.gui_model import (
    WidgetNode,
    compute_widget_topleft,
    effective_origo,
    reverse_compute_position,
)
from src.ui.main_window import MainWindow


def test_implicit_container_children_use_zero_anchor_reference():
    parent = WidgetNode('containerWindowType', properties={'name': 'implicit'})
    parent._editor_layout_size = (300, 200)
    parent._editor_resolved_size = (300, 200)
    child = WidgetNode(
        'iconType',
        properties={
            'name': 'child',
            'position': {'x': 10, 'y': 20},
            'size': {'width': 40, 'height': 30},
            'orientation': 'CENTER',
            'origo': 'CENTER',
        },
    )
    parent.add_child(child)

    tl_x, tl_y = compute_widget_topleft(
        0.0, 0.0, 40, 30,
        child.orientation, effective_origo(child),
        child.position[0], child.position[1],
    )
    recovered = reverse_compute_position(
        tl_x, tl_y, 0.0, 0.0, 40, 30,
        child.orientation, effective_origo(child),
    )

    assert recovered == child.position


def test_insertion_parent_prefers_current_selection_over_cached_container():
    old_parent = WidgetNode('containerWindowType', properties={'name': 'old'})
    new_parent = WidgetNode('containerWindowType', properties={'name': 'new'})
    child = WidgetNode('iconType', properties={'name': 'child'})
    new_parent.add_child(child)

    assert MainWindow._insertion_parent_for_node(old_parent) is old_parent
    assert MainWindow._insertion_parent_for_node(child) is new_parent


if __name__ == '__main__':
    test_implicit_container_children_use_zero_anchor_reference()
    test_insertion_parent_prefers_current_selection_over_cached_container()
    print('layout stability tests: PASS')
