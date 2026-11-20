# -*- mode: python ; coding: utf-8 -*-
# ============================================================================
#  MusicManager-portable.spec - variante portable de CARPETA (onedir)
#
#  Compila la app como una CARPETA (no autoextraíble):
#      pyinstaller MusicManager-portable.spec --noconfirm
#
#  Resultado: dist/MusicManager/MusicManager.exe + dependencias
#
#  Por qué existe: el .exe de archivo único (onefile) se autodescomprime
#  en %TEMP% al arrancar y muchos antivirus lo marcan. La variante de
#  carpeta NO se autodescomprime y suele pasar los escaneos limpia.
# ============================================================================

import os

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
    excludes=app_modules + [
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'pytest',
    ],
    hiddenimports=[
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
    [],
    exclude_binaries=True,
    name='MusicManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MusicManager',
)
