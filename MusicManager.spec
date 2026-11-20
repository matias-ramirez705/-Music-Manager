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
#     - hiddenimports = solo librerias externas (pip)
#     - excludes      = todos los modulos de app/ (van en el ZIP portable)
#     - datas         = vacio (templates/static viajan en el ZIP)
# ============================================================

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
    'metadata_reader',
    'organizer',
    'playlist_spotify',
    'playlist_youtube',
    'saved_playlists',
    'scanner',
    'spotiflac_dl',
    'spotiflac_dummy',
    'spotify_official',
    'txt_playlist',
    'web_app',
]

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # --- Flask y sus dependencias ---
        'flask',
        'jinja2',
        'werkzeug',
        'click',
        'itsdangerous',
        'markupsafe',
        'blinker',
        # --- Metadata de audio (mutagen carga estos submodulos por dentro) ---
        'mutagen',
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
        # --- Playlists de YouTube (yt-dlp) ---
        'yt_dlp',
        # --- Red / HTTP ---
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'brotli',
        'packaging',
        # --- Imagenes (caratulas) ---
        'PIL',
        'PIL.Image',
        'PIL.ImageOps',
        'PIL.ImageDraw',
        'PIL.ImageFilter',
        'PIL.ImageEnhance',
        # --- Spotify / config / papelera ---
        'spotipy',
        'dotenv',
        'send2trash',
        # --- Extras de yt-dlp que mejoran compatibilidad ---
        # (pycryptodomex es la distribucion pip; el paquete importable
        #  se llama Cryptodome)
        'Cryptodome',
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
