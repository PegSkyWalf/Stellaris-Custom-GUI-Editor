"""Comprehensive tests including 9-patch, sprite detection, position commit, and full app."""
import sys, os
sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.core.resource_manager import ResourceManager
rm = ResourceManager.instance()
game_dir = r'E:\SteamLibrary\steamapps\common\Stellaris'
if os.path.isdir(game_dir):
    rm.load_game_dir(game_dir)
    print(f'Loaded {rm.sprite_count} sprites')

print('\n=== Test 1: 9-patch detection ===')
# corneredTileSpriteType should be nine_patch
from src.core.gui_model import create_widget

node_q = create_widget('containerWindowType', 'bg_test')
node_q.properties['quadTextureSprite'] = 'GFX_tile_outliner_bg'

mode = rm.get_widget_render_mode(node_q)
info = rm.get_sprite('GFX_tile_outliner_bg')
if info:
    print(f'GFX_tile_outliner_bg type: {info.sprite_type}, is_scalable: {info.is_scalable()}, mode: {mode}')

# spriteType should be fixed
node_s = create_widget('iconType', 'icon_test')
node_s.properties['spriteType'] = 'GFX_close'
mode_s = rm.get_widget_render_mode(node_s)
print(f'GFX_close (spriteType attr): mode={mode_s}')
assert mode_s == 'fixed', f"Expected fixed, got {mode_s}"

# Check a sprite that may be quad but actually spriteType in registry
node_q2 = create_widget('buttonType', 'btn_test')
node_q2.properties['quadTextureSprite'] = 'GFX_close'  # GFX_close is spriteType
mode_q2 = rm.get_widget_render_mode(node_q2)
close_info = rm.get_sprite('GFX_close')
print(f'GFX_close (quadTextureSprite attr) - is_scalable: {close_info.is_scalable() if close_info else "N/A"}, mode: {mode_q2}')
assert mode_q2 == 'fixed', f"quadTextureSprite pointing to spriteType should be fixed, got {mode_q2}"
print('9-patch detection: PASS')

print('\n=== Test 2: 9-patch rendering ===')
from src.ui.widget_items import draw_nine_patch
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor

# Create a small test pixmap (3x3 9-patch)
pm = QPixmap(30, 30)
pm.fill(QColor('#ff0000'))

# Draw to a target pixmap
target = QPixmap(100, 80)
target.fill(QColor('#000000'))
painter = QPainter(target)
draw_nine_patch(painter, pm, 8, 8, QRectF(0, 0, 100, 80))
painter.end()
print(f'9-patch draw OK: {target.width()}x{target.height()}')

print('\n=== Test 3: Position reverse calculation ===')
from src.core.gui_model import compute_widget_topleft, reverse_compute_position

# Test: widget with center/center at position (0,0) in 1920x1080
w, h = 660, 300
px, py = compute_widget_topleft(1920, 1080, w, h, 'center', 'center', 0, 0)
print(f'Forward: position=(0,0) → Qt pos ({px},{py})')
# Reverse
sx, sy = reverse_compute_position(px, py, 1920, 1080, w, h, 'center', 'center')
print(f'Reverse: Qt ({px},{py}) → Stellaris pos ({sx},{sy})')
assert sx == 0 and sy == 0, f"Reverse calc failed: ({sx},{sy}) != (0,0)"

# Test with offset
px2, py2 = compute_widget_topleft(1920, 1080, w, h, 'center', 'UPPER_LEFT', -200, -116)
sx2, sy2 = reverse_compute_position(px2, py2, 1920, 1080, w, h, 'center', 'UPPER_LEFT')
print(f'center/UPPER_LEFT pos=(-200,-116) → Qt ({px2},{py2}) → back ({sx2},{sy2})')
assert sx2 == -200 and sy2 == -116

# Test UPPER_RIGHT/UPPER_RIGHT
px3, py3 = compute_widget_topleft(450, 180, 38, 38, 'UPPER_RIGHT', 'UPPER_LEFT', -42, 12)
sx3, sy3 = reverse_compute_position(px3, py3, 450, 180, 38, 38, 'UPPER_RIGHT', 'UPPER_LEFT')
print(f'UPPER_RIGHT/UPPER_LEFT pos=(-42,12) → Qt ({px3},{py3}) → back ({sx3},{sy3})')
assert sx3 == -42 and sy3 == 12
print('Position reverse calculation: PASS')

print('\n=== Test 4: Full GUI app startup ===')
from src.ui.main_window import MainWindow
win = MainWindow()
print(f'Window created: {win.windowTitle()}')
assert hasattr(win, '_layer_panel'), 'LayerPanel missing'
assert hasattr(win, '_undo_stack'), 'UndoStack missing'
assert hasattr(win, '_saved_doc_copy'), 'Reset support missing'
print('MainWindow features: PASS')

print('\n=== Test 5: Load and render guicore with 9-patch ===')
from src.ui.canvas import GUICanvas
from src.core.gui_model import parse_gui_file

canvas = GUICanvas()
guicore_path = os.environ.get('TEST_GUICORE_PATH', '')
if guicore_path and os.path.isfile(guicore_path):
    doc = parse_gui_file(guicore_path)
    canvas.load_document(doc)
    items = [i for i in canvas.gui_scene.items() if hasattr(i, 'node')]
    print(f'Loaded guicore: {len(doc.roots)} roots, {len(items)} items')
    modes = {}
    for item in items:
        if hasattr(item, '_render_mode'):
            modes[item._render_mode] = modes.get(item._render_mode, 0) + 1
    print(f'Render mode distribution: {modes}')
else:
    print('guicore not specified (set TEST_GUICORE_PATH env var), skipping')

print('\nAll comprehensive tests PASSED!')
app.quit()
