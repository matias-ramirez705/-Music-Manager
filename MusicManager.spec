# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# MusicManager.spec - genera MusicManager.exe (onefile)
# ============================================================
# ARQUITECTURA (importante):
#   El .exe SOLO contiene el runtime de Python + las librerias de pip
#   (flask, mutagen, yt-dlp, spotipy, Pillow...).
#   Los modulos de app/, templates/, static/ y data/ NO van dentro del
#   exe: se cargan DESDE EL DISCO (al lado del exe), asi se pueden
#   editar y actualizar sin recompilar.
#   Por eso:
#     - hiddenimports = solo librerias externas (pip) + collect_submodules
#     - excludes      = todos los modulos de app/ (van en el ZIP portable)
#     - datas         = vacio (templates/static viajan en el ZIP)
# ============================================================

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

APP_MODULES = [
    '__init__',
    'artwork',
    'audio_quality',
    'auto_metadata',
    'batch_artwork',
    'csv_playlist',
    'deleted_songs',
    'download_sites',
    'duplicates',
    'folder_compare',
    'lyrics',
    'm3u_generator',
    'manual_matches',
    'metadata_reader',
    'organizer',
    'playlist_spotify',
    'playlist_youtube',
    'saved_playlists',
    'scanner',
    'spotiflac_dummy',
    'spotify_official',
    'txt_playlist',
    'web_app',
]

# Recoger submodulos y data files de las librerias externas.
# Esto asegura que TODO flask, mutagen, yt_dlp, etc. quede dentro del exe
# aunque launcher.py no los importe directamente (los importa app/web_app.py,
# que esta excluido del bundle y se carga del disco).
EXTERNAL_LIBS = [
    'flask',
    'jinja2',
    'werkzeug',
    'click',
    'itsdangerous',
    'markupsafe',
    'blinker',
    'mutagen',
    'yt_dlp',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    'brotli',
    'packaging',
    'PIL',
    'spotipy',
    'dotenv',
    'send2trash',
    'Cryptodome',
]

hidden = []
datas = []
for lib in EXTERNAL_LIBS:
    try:
        hidden.extend(collect_submodules(lib))
    except Exception:
        # Si collect_submodules falla para algun paquete, al menos el
        # nombre del paquete raiz queda declarado abajo.
        pass
    try:
        datas.extend(collect_data_files(lib))
    except Exception:
        pass

# Eliminar duplicados preservando orden
hidden = list(dict.fromkeys(hidden))

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden + EXTERNAL_LIBS + [
        # Submodulos de mutagen que se importan por dentro segun el formato
        # (aseguramos los mas usados por si el hook no los pilla)
        'mutagen.id3',
        'mutagen.flac',
        'mutagen.mp3',
        'mutagen.mp4',
        'mutagen.ogg',
        'mutagen.oggopus',
        'mutagen.oggvorbis',
        'mutagen.oggspeex',
        'mutagen.oggtheora',
        'mutagen.wave',
        'mutagen.aiff',
        'mutagen.apev2',
        'mutagen.asf',
        'mutagen.aac',
        'mutagen.monkeysaudio',
        'mutagen.trueaudio',
        'mutagen.wv',
        'mutagen.dsf',
        'mutagen.easyid3',
        # Plugins de PIL
        'PIL.Image',
        'PIL.ImageOps',
        'PIL.ImageDraw',
        'PIL.ImageFilter',
        'PIL.ImageEnhance',
    ],
    excludes=APP_MODULES + [
        # Stdlib pesada que la app no usa (reduce tamano y falsos positivos)
        'tkinter',
        'curses',
        'unittest',
        'pydoc_data',
        'lib2to3',
    ],
    noarchive=False,
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
    console=True,          # ventana de consola con logs (Ctrl+C para salir)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version='version.txt',
)
