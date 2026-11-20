# -*- mode: python ; coding: utf-8 -*-
# ============================================================================
#  MusicManager.spec - configuración de PyInstaller (archivo único)
#
#  Compila la app como UN SOLO ejecutable:
#      pyinstaller MusicManager.spec --noconfirm
#
#  IMPORTANTE: Los módulos de app/ NO se incluyen en el bundle.
#  Se cargan desde el disco junto al .exe para que el usuario
#  pueda editarlos sin recompilar.
#
#  El .exe solo contiene: Python runtime + librerías pip compiladas.
#
#  Resultado: dist/MusicManager.exe
# ============================================================================

import os

# Lista de módulos de la app que NO deben incluirse en el bundle
# (se cargan desde el disco en runtime)
app_modules = [
    'scanner', 'metadata_reader', 'audio_quality',
    'playlist_youtube', 'playlist_spotify', 'spotify_official',
    'auto_metadata', 'csv_playlist', 'txt_playlist',
    'saved_playlists', 'duplicates', 'deleted_songs',
    'artwork', 'batch_artwork', 'lyrics', 'batch_lyrics',
    'organizer', 'download_sites', 'folder_compare',
    'spotiflac_dummy', 'm3u_generator', 'manual_matches',
    'web_app',
]

a = Analysis(
    ['app_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[],
    # v3.36: NO incluir los módulos de app/ - se cargan desde disco
    excludes=app_modules + [
        'tkinter',           # no lo usamos
        'matplotlib',        # no lo usamos
        'numpy',             # no lo usamos
        'pandas',            # no lo usamos
        'scipy',             # no lo usamos
        'IPython',           # no lo usamos
        'pytest',            # no lo usamos
    ],
    hiddenimports=[
        # Dependencias externas que DEBEN estar en el bundle
        'flask',
        'flask.json',
        'jinja2',
        'werkzeug',
        'markupsafe',
        'itsdangerous',
        'click',
        'blinker',
        'mutagen',
        'mutagen.flac',
        'mutagen.mp3',
        'mutagen.mp4',
        'mutagen.oggopus',
        'mutagen.oggvorbis',
        'mutagen.wave',
        'requests',
        'PIL',
        'PIL.Image',
        'pywebview',
        'send2trash',
        'dotenv',
        'spotipy',
        'certifi',
        'charset_normalizer',
        'urllib3',
        'packaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name='MusicManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # mostrar consola para logs de debug
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
    icon='icon.ico',
)
