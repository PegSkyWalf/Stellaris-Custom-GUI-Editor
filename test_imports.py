"""Test all imports work correctly."""
import sys
sys.path.insert(0, '.')

print('Testing imports...')

from src.core.pdx_parser import parse_text, parse_file, pairs_to_dict
print('  pdx_parser OK')

from src.core.gui_model import (
    WidgetNode, GUIDocument, parse_gui_file, parse_gui_text,
    create_widget, WIDGET_TYPES
)
print('  gui_model OK')

from src.core.settings import AppSettings
print('  settings OK')

from src.core.resource_manager import ResourceManager, SpriteInfo
print('  resource_manager OK')

from src.codegen.gui_writer import write_document, write_widget_to_string, save_document
print('  gui_writer OK')

# Test resource manager
rm = ResourceManager.instance()
game_dir = r'E:\SteamLibrary\steamapps\common\Stellaris'
print(f'  Loading game resources from {game_dir}...')
import os
if os.path.isdir(game_dir):
    rm.load_game_dir(game_dir)
    print(f'  Loaded {rm.sprite_count} sprites, {rm.loc_count} localizations')

    # Test sprite lookup
    info = rm.get_sprite('GFX_close')
    if info:
        print(f'  GFX_close: {info.texture_path}')
    
    info2 = rm.get_sprite('GFX_standard_button_142_34_button')
    if info2:
        print(f'  GFX_standard_button_142_34_button: {info2.texture_path}')
    
    # Test localization
    loc = rm.get_loc('OK')
    print(f'  Loc(OK): {loc!r}')
else:
    print('  Game dir not found, skipping resource load')

# Test widget creation
node = create_widget('containerWindowType', 'my_window')
node2 = create_widget('buttonType', 'close_btn')
node.add_child(node2)
print(f'  Created widget: {node.widget_type} {node.name!r} with {len(node.children)} children')

# Test code generation
from src.core.gui_model import GUIDocument
doc = GUIDocument(file_path='test.gui')
doc.roots.append(node)
code = write_document(doc)
print(f'  Generated {len(code)} chars of code')
print()
print('Code preview:')
print(code[:300])

print('\nAll imports OK!')
