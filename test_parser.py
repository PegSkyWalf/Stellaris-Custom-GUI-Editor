"""Test the PDX parser and GUI model."""
import sys
sys.path.insert(0, '.')

from src.core.pdx_parser import parse_text, pairs_to_dict

# Test parser
test_gui = r"""
guiTypes = {
    containerWindowType = {
        name = "TestWindow"
        position = { x = 100 y = 200 }
        size = { width = 400 height = 300 }
        orientation = center
        moveable = yes
        
        iconType = {
            name = "test_icon"
            spriteType = "GFX_test"
            position = { x = 10 y = 10 }
        }
        
        buttonType = {
            name = "close_button"
            quadTextureSprite = "GFX_close"
            position = { x = -30 y = 5 }
            orientation = UPPER_RIGHT
        }
    }
}
"""

pairs = parse_text(test_gui)
print('Parse result:', len(pairs), 'root entries')

from src.core.gui_model import parse_gui_text
doc = parse_gui_text(test_gui)
print('Document roots:', len(doc.roots))
root = doc.roots[0]
print('Root type:', root.widget_type)
print('Root name:', root.name)
print('Root position:', root.position)
print('Root size:', root.size)
print('Root children:', len(root.children))
for child in root.children:
    print(f'  Child: {child.widget_type} {child.name!r}')
print()

from src.codegen.gui_writer import write_document
code = write_document(doc)
print('Generated code:')
print(code[:500])

# Test parse a real game file
print('\n--- Testing real game file ---')
from src.core.gui_model import parse_gui_file
game_file = r"E:\SteamLibrary\steamapps\common\Stellaris\interface\popup.gui"
import os
if os.path.exists(game_file):
    doc2 = parse_gui_file(game_file)
    print(f'Parsed {game_file}')
    print(f'Root widgets: {len(doc2.roots)}')
    for r in doc2.roots:
        print(f'  {r.widget_type}: {r.name!r}  pos={r.position}  size={r.size}  children={len(r.children)}')
else:
    print('Game file not found, skipping')

print('\nAll tests passed!')
