"""
app/txt_playlist.py
===================
Lee un archivo de texto (.txt) que contiene URLs de playlists
de YouTube Music o Spotify, una por linea, con soporte para
comentarios.

Formato del TXT:
  - Lineas que empiezan con # son comentarios (se ignoran)
  - Lineas vacias se ignoran
  - Cualquier otra linea que contenga una URL de YouTube Music
    o Spotify se procesa como una playlist
  - Se pueden mezclar URLs de YouTube Music y Spotify

Ejemplo de playlists.txt:
    # ============================================
    # Mis playlists de musica
    # ============================================

    # Playlists de YouTube Music
    https://music.youtube.com/playlist?list=PLJCkad8TrnTBLg5MEivucb-DBDDy9-HGg
    https://music.youtube.com/playlist?list=PLr1-...

    # Playlists de Spotify (max 100 canciones por URL)
    # Para playlists grandes, exporta como CSV desde exportify.app
    https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
    https://open.spotify.com/playlist/6V7CD72aWvChW5AdMiY4WI

    # Playlists CSV exportadas con Exportify (rutas locales)
    # ./data/Spotify/Mi playlist.csv
    # C:\\Users\\Matias\\Music\\playlist.csv

Funciones principales:
  - parse_txt_file(content): extrae URLs y rutas CSV del texto
  - load_default_txt(): lee data/playlists.txt si existe
"""

import os
import re
from pathlib import Path


# Patrones para detectar URLs de playlists
YOUTUBE_URL_PATTERN = re.compile(
    r'(https?://(?:music\.)?youtube\.com/playlist\?list=[A-Za-z0-9_-]+|https?://youtu\.be/[A-Za-z0-9_-]+)',
    re.IGNORECASE
)
SPOTIFY_URL_PATTERN = re.compile(
    r'(https?://open\.spotify\.com/(?:embed/)?playlist/[A-Za-z0-9]+)',
    re.IGNORECASE
)
CSV_PATH_PATTERN = re.compile(
    r'^([A-Za-z]:[\\/][^\n]+\.csv|[./][^\n]+\.csv|[^\n]+\.csv)$',
    re.MULTILINE
)


def parse_txt_file(content):
    """
    Parsea el contenido de un archivo TXT y extrae todas las URLs
    de playlists y rutas a archivos CSV.

    Args:
        content (str): contenido del archivo TXT.

    Returns:
        list[dict]: cada elemento es:
            {
                'type': 'youtube' | 'spotify' | 'csv',
                'url': 'https://...' o ruta del CSV,
                'line': N (numero de linea donde se encontro)
            }
    """
    entries = []
    lines = content.split('\n')

    for i, line in enumerate(lines, 1):
        # Quitar espacios al inicio y final
        stripped = line.strip()

        # Ignorar lineas vacias
        if not stripped:
            continue

        # Ignorar comentarios (lineas que empiezan con #)
        if stripped.startswith('#'):
            continue

        # Buscar URL de YouTube Music
        yt_match = YOUTUBE_URL_PATTERN.search(stripped)
        if yt_match:
            entries.append({
                'type': 'youtube',
                'url': yt_match.group(1),
                'line': i,
            })
            continue

        # Buscar URL de Spotify
        sp_match = SPOTIFY_URL_PATTERN.search(stripped)
        if sp_match:
            entries.append({
                'type': 'spotify',
                'url': sp_match.group(1),
                'line': i,
            })
            continue

        # Buscar ruta a archivo CSV (debe terminar en .csv)
        # Solo si la linea entera (sin espacios) es una ruta .csv
        if stripped.lower().endswith('.csv') and not stripped.startswith('#'):
            # Verificar que sea una ruta plausible
            # (puede empezar con letra: en Windows, o / en Unix, o ./ o ../)
            if re.match(r'^[A-Za-z]:[\\/]', stripped) or stripped.startswith('/') or \
               stripped.startswith('./') or stripped.startswith('../') or \
               os.path.exists(stripped):
                entries.append({
                    'type': 'csv',
                    'url': stripped,
                    'line': i,
                })
                continue

        # Si la linea no matcheo ningun patron pero contiene algo,
        # podria ser una URL invalida; la ignoramos silenciosamente

    return entries


def load_default_txt():
    """
    Lee el archivo data/playlists.txt si existe.

    Returns:
        str | None: contenido del archivo o None si no existe.
    """
    txt_path = Path(__file__).parent.parent / 'data' / 'playlists.txt'
    if not txt_path.exists():
        return None
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None


def save_default_txt(content):
    """
    Guarda el contenido en data/playlists.txt.

    Args:
        content (str): contenido a guardar.

    Returns:
        bool: True si se guardo correctamente.
    """
    txt_path = Path(__file__).parent.parent / 'data' / 'playlists.txt'
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except OSError:
        return False
