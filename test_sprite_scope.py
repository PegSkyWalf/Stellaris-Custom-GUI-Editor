"""Regression tests for sprite library source scope filtering."""
from src.core.resource_manager import ResourceManager, SpriteInfo


def test_get_all_sprites_filters_by_source_scope():
    rm = ResourceManager()
    vanilla = SpriteInfo('GFX_vanilla', 'gfx/a.dds')
    vanilla.source_scope = 'vanilla'
    current = SpriteInfo('GFX_current', 'gfx/b.dds')
    current.source_scope = 'current_mod'
    dependency = SpriteInfo('GFX_dependency', 'gfx/c.dds')
    dependency.source_scope = 'dependency'
    rm._sprites = {
        vanilla.name: vanilla,
        current.name: current,
        dependency.name: dependency,
    }

    primary = {s.name for s in rm.get_all_sprites({'vanilla', 'current_mod'})}
    current_only = {s.name for s in rm.get_all_sprites({'current_mod'})}
    all_sprites = {s.name for s in rm.get_all_sprites()}

    assert primary == {'GFX_vanilla', 'GFX_current'}
    assert current_only == {'GFX_current'}
    assert all_sprites == {'GFX_vanilla', 'GFX_current', 'GFX_dependency'}


if __name__ == '__main__':
    test_get_all_sprites_filters_by_source_scope()
    print('sprite scope tests: PASS')
