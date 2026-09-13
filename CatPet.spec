# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/CatAdventage/CatPet/desktop_pet.py'],
    pathex=['D:/CatAdventage/CatPet'],
    binaries=[],
    datas=[('D:/CatAdventage/Materials', 'Materials')],
    hiddenimports=['item_catalog', 'content_repository', 'emoticon_config', 'expression_config', 'colors', 'letters', 'special_events', 'animations', 'warehouse_window', 'market_window', 'adventure_window', 'adventure_page', 'renderer', 'interaction_animations', 'render_cache', 'animation_controller', 'action_catalog', 'animation_state_machine', 'services', 'services.models', 'services.save', 'services.inventory', 'services.progression', 'services.treasure', 'services.adventure', 'services.market', 'editor_enhancements', 'stats', 'achievements', 'ui_theme', 'openpyxl'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CatPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/CatAdventage/cat.ico'],
)
