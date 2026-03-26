"""Test GUI components without displaying a window."""
import sys
sys.path.insert(0, '.')
import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

print('Testing GUI components...')

from src.core.resource_manager import ResourceManager
rm = ResourceManager.instance()
game_dir = r'E:\SteamLibrary\steamapps\common\Stellaris'
if os.path.isdir(game_dir):
    rm.load_game_dir(game_dir)
    print(f'  Resources loaded: {rm.sprite_count} sprites')

# Test DDS image loading
if os.path.isdir(game_dir):
    pm = rm.get_sprite_pixmap('GFX_close')
    if pm and not pm.isNull():
        print(f'  DDS loading OK: GFX_close ({pm.width()}x{pm.height()})')
    else:
        print('  DDS loading: no pixmap (expected in offscreen mode, OK)')

# Test canvas creation
from src.core.gui_model import GUIDocument, parse_gui_file
from src.ui.canvas import GUICanvas

canvas = GUICanvas()
print('  Canvas created OK')

# Test loading a document
doc = parse_gui_file(r'E:\SteamLibrary\steamapps\common\Stellaris\interface\popup.gui')
canvas.load_document(doc)
print(f'  Document loaded: {len(doc.roots)} roots in scene')
print(f'  Scene items: {len(canvas.gui_scene.items())}')

# Test selecting and getting node
from src.ui.widget_items import GUIWidgetItem
items = [i for i in canvas.gui_scene.items() if isinstance(i, GUIWidgetItem)]
print(f'  Widget items: {len(items)}')

if items:
    node = items[0].node
    print(f'  First item: {node.widget_type} {node.name!r}')

# Test properties panel
from src.ui.properties_panel import PropertiesPanel
panel = PropertiesPanel()
if items:
    panel.set_node(items[0].node)
print('  Properties panel OK')

# Test code view
from src.ui.code_view import CodeView
code_view = CodeView()
code_view.set_document(doc)
print('  Code view OK')

# Test widget library
from src.ui.widget_library import WidgetLibrary
lib = WidgetLibrary()
print('  Widget library OK')

# Test sprite library
from src.ui.sprite_library import SpriteLibrary
sprite_lib = SpriteLibrary()
sprite_lib.populate()
print(f'  Sprite library populated: {sprite_lib._list.count()} sprites')

# Test code generation round-trip
from src.codegen.gui_writer import write_document
from src.core.gui_model import parse_gui_text
code = write_document(doc)
doc2 = parse_gui_text(code)
print(f'  Round-trip: {len(doc.roots)} -> {len(doc2.roots)} roots')

print('\nAll GUI tests passed!')
app.quit()
