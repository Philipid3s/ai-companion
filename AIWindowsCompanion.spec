# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_dir = Path.cwd()
assets_dir = project_dir / "assets"

block_cipher = None
hiddenimports = [
    'qasync',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'wmi',
    'ai.base',
    'ai.gemini_client',
    'ai.groq_client',
    'ai.ollama_client',
    'ai.service',
    'comms.telegram_bot',
    'core.keepalive',
    'core.monitor',
    'core.presence',
    'core.scheduler',
    'integrations.autostart',
    'memory.context',
    'memory.db',
    'ui.bubble_widget',
    'ui.cli_panel',
    'ui.companion_window',
    'ui.settings_window',
    'ui.sprite_widget',
]

a = Analysis(
    ['main.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[(str(assets_dir), 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AIWindowsCompanion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIWindowsCompanion',
)
