"""Regression tests for widget type changes and iconType sprite rules."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from src.codegen.gui_writer import write_document, write_document_preserving
from src.core.gui_model import WidgetNode, parse_gui_text
from src.core.resource_manager import ResourceManager, SpriteInfo


def test_icon_type_ignores_quad_texture_sprite():
    rm = ResourceManager()
    info = SpriteInfo(
        'GFX_scalable',
        'gfx/interface/tiles/scalable.dds',
        sprite_type='corneredTileSpriteType',
    )
    rm._sprites = {info.name: info}

    node = WidgetNode(
        'iconType',
        properties={
            'name': 'bad_icon',
            'quadTextureSprite': 'GFX_scalable',
            'size': {'width': 100, 'height': 100},
        },
    )

    assert node.get_sprite_name() is None
    assert node.is_quad_sprite() is False
    assert rm.get_widget_render_mode(node) == 'none'

    node.properties['spriteType'] = 'GFX_scalable'
    assert node.get_sprite_name() == 'GFX_scalable'
    assert rm.get_widget_render_mode(node) == 'fixed'


def test_change_widget_type_marks_source_modified_and_preserves_writer_output():
    from PySide6.QtWidgets import QApplication
    from src.ui.canvas import GUICanvas

    _app = QApplication.instance() or QApplication([])
    doc = parse_gui_text('''guiTypes = {
    buttonType = {
        name = "change_me"
        position = { x = 1 y = 2 }
        quadTextureSprite = "GFX_scalable"
        size = { width = 120 height = 40 }
    }
}
''')
    canvas = GUICanvas()
    canvas.load_document(doc)
    node = doc.roots[0]

    canvas._change_widget_type(node, 'iconType')
    out = write_document_preserving(doc)

    assert node.widget_type == 'iconType'
    assert node._source_modified is True
    assert node.properties.get('spriteType') == 'GFX_scalable'
    assert 'quadTextureSprite' not in node.properties
    assert 'iconType = {' in out
    assert 'buttonType = {' not in out
    assert 'spriteType = "GFX_scalable"' in out


def test_generated_icon_type_uses_sprite_type_when_quad_property_remains():
    doc = parse_gui_text('''guiTypes = {
    iconType = {
        name = "legacy_bad_icon"
        quadTextureSprite = "GFX_scalable"
    }
}
''')
    doc.roots[0].mark_source_modified()

    out = write_document(doc)
    preserved = write_document_preserving(doc)

    assert 'quadTextureSprite' not in out
    assert 'spriteType = "GFX_scalable"' in out
    assert 'quadTextureSprite' not in preserved
    assert 'spriteType = "GFX_scalable"' in preserved


if __name__ == '__main__':
    test_icon_type_ignores_quad_texture_sprite()
    test_change_widget_type_marks_source_modified_and_preserves_writer_output()
    test_generated_icon_type_uses_sprite_type_when_quad_property_remains()
    print('widget type sprite rule tests: PASS')
