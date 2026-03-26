"""Advanced tests: origo/orientation, background, undo, spriteType sizing."""
import sys, os
sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.core.gui_model import (
    compute_widget_topleft, orientation_to_anchor, origo_to_offset,
    parse_gui_text, create_widget
)

print('=== Test 1: origo + orientation calculation ===')

# Widget with orientation=center, origo=center in a 1920x1080 canvas
# Should appear centered: top-left at (960-width/2, 540-height/2)
w, h = 1200, 860
px, py = compute_widget_topleft(1920, 1080, w, h, 'center', 'center', 0, 0)
expected_x = (1920 - 1200) / 2  # 360
expected_y = (1080 - 860) / 2   # 110
print(f'center/center pos=0,0: ({px:.1f}, {py:.1f}) expected ({expected_x}, {expected_y})')
assert abs(px - expected_x) < 1, f"x mismatch: {px} != {expected_x}"
assert abs(py - expected_y) < 1, f"y mismatch: {py} != {expected_y}"

# UPPER_RIGHT orientation, UPPER_RIGHT origo: top-right of widget at top-right of parent
px2, py2 = compute_widget_topleft(500, 400, 50, 30, 'UPPER_RIGHT', 'UPPER_RIGHT', -42, 12)
# anchor = (500, 0), origo_offset = (50, 0), so top-left = (500 + (-42) - 50, 0 + 12 - 0) = (408, 12)
print(f'UPPER_RIGHT/UPPER_RIGHT pos=-42,12: ({px2:.1f}, {py2:.1f})')
assert abs(px2 - 408) < 1, f"x2 mismatch: {px2} != 408"
assert abs(py2 - 12) < 1, f"y2 mismatch: {py2} != 12"

print('orientation/origo tests: PASS')

print('\n=== Test 2: background as property dict ===')
gui_text = '''
guiTypes = {
    containerWindowType = {
        name = "test_window"
        size = { width = 400 height = 300 }
        
        background = {
            name = "bg"
            quadTextureSprite = "GFX_test_bg"
        }
        
        iconType = {
            name = "test_icon"
            spriteType = "GFX_test"
        }
    }
}
'''
doc = parse_gui_text(gui_text)
root = doc.roots[0]
print(f'Root widget: {root.widget_type} {root.name!r}')
print(f'Children count: {len(root.children)}  (should be 1, iconType only)')
assert len(root.children) == 1, f"Expected 1 child, got {len(root.children)}"
assert root.children[0].widget_type == 'iconType'

bg = root.get_background()
print(f'Background dict: {bg}')
assert bg is not None, "Background should be in properties"
assert bg.get('quadTextureSprite') == 'GFX_test_bg'
print('background property test: PASS')

print('\n=== Test 3: spriteType vs quadTextureSprite ===')
sprite_node = create_widget('iconType', 'my_icon')
sprite_node.properties['spriteType'] = 'GFX_close'
assert sprite_node.is_sprite_type() == True
assert sprite_node.is_quad_sprite() == False

quad_node = create_widget('effectButtonType', 'my_btn')
quad_node.properties['quadTextureSprite'] = 'GFX_some_bg'
quad_node.properties['size'] = {'width': 200, 'height': 100}
assert quad_node.is_sprite_type() == False
assert quad_node.is_quad_sprite() == True
print('sprite type distinction: PASS')

print('\n=== Test 4: undo/redo system ===')
from src.core.undo import UndoStack, SetPropertyCommand, MoveWidgetCommand
from src.core.gui_model import GUIDocument

doc2 = GUIDocument(file_path='test.gui')
node = create_widget('containerWindowType', 'test')
doc2.roots.append(node)

changes = []
stack = UndoStack(on_change=lambda: changes.append('changed'))

# Test SetProperty command
old_name = node.name
cmd = SetPropertyCommand(node, 'name', old_name, 'new_name')
stack.push(cmd)
assert node.name == 'new_name', f"Name should be new_name, got {node.name}"
print(f'After push: name={node.name!r}')

stack.undo()
assert node.name == old_name, f"Name should be {old_name}, got {node.name}"
print(f'After undo: name={node.name!r}')

stack.redo()
assert node.name == 'new_name'
print(f'After redo: name={node.name!r}')

# Test MoveWidget
old_pos = node.position
cmd2 = MoveWidgetCommand(node, old_pos, (100, 200))
stack.push(cmd2)
assert node.position == (100, 200)
stack.undo()
assert node.position == old_pos
print('undo/redo test: PASS')

print('\n=== Test 5: guicore file parsing ===')
guicore_path = os.environ.get('TEST_GUICORE_PATH', '')
if guicore_path and os.path.exists(guicore_path):
    from src.core.gui_model import parse_gui_file
    doc3 = parse_gui_file(guicore_path)
    print(f'Parsed {os.path.basename(guicore_path)}: {len(doc3.roots)} root widgets')
    for r in doc3.roots:
        bg = r.get_background()
        print(f'  {r.widget_type} {r.name!r}: {len(r.children)} children, bg={bg is not None}')
else:
    print('guicore file not specified (set TEST_GUICORE_PATH env var), skipping')

print('\n=== Test 6: code generation with background ===')
from src.codegen.gui_writer import write_document
code = write_document(doc)
print(f'Generated code ({len(code)} chars):')
print(code[:300])
assert 'background = {' in code, "background block should be in output"
assert 'quadTextureSprite = "GFX_test_bg"' in code, "background sprite should be quoted"
print('code gen with background: PASS')

print('\nAll advanced tests PASSED!')
app.quit()
