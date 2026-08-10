"""
app/csv_playlist.py
===================
Lee playlists de Spotify exportadas como CSV desde https://exportify.app/

Exportify genera un CSV con estas columnas (en español):
  - URI de la cancion
  - Nombre de la cancion
  - URI(s) del artista
  - Nombre(s) del artista
  - URI del album
  - Nombre del album
  - URI(s) del artista del album
  - Nombre(s) del artista del album
  - Fecha de lanzamiento del album
  - URL de la imagen del album
  - Numero de disco
  - Numero de la cancion
  - Duracion de la cancion (ms)
  - URL de vista previa de la cancion
  - Explicito
  - Popularidad
  - ISRC
  - Anadido por
  - Anadido en

Este modulo parsea el CSV y devuelve una estructura compatible con
la que usan los fetch_youtube_playlist / fetch_spotify_playlist:

    {
        'title': 'Nombre (del archivo o "Playlist CSV")',
        'uploader': 'Importado desde CSV',
        'count': N,
        'tracks': [
            {
                'title': '...',
                'artist': '...',
                'album': '...',
                'duration': 123.4,  # segundos
                'url': 'https://open.spotify.com/track/...',
            },
            ...
        ],
        'error': None,
        'warning': None,
    }

Tambien soporta CSVs en ingles (Exportify en ingles usa nombres
de columna distintos).
"""

import csv
import io
import os
from pathlib import Path


# Mapeo de nombres de columna (espanol e ingles) a nuestros campos
COLUMN_MAP_ES = {
    'URI de la canción': 'uri',
    'URI de la cancion': 'uri',
    'Nombre de la canción': 'title',
    'Nombre de la cancion': 'title',
    'Nombre(s) del artista': 'artist',
    'URI(s) del artista': 'artist_uri',
    'Nombre del álbum': 'album',
    'Nombre del album': 'album',
    'Duración de la canción (ms)': 'duration_ms',
    'Duracion de la cancion (ms)': 'duration_ms',
    'URL de vista previa de la canción': 'preview_url',
    'URL de vista previa de la cancion': 'preview_url',
    'URL de la imagen del álbum': 'artwork_url',
    'URL de la imagen del album': 'artwork_url',
    'Número de disco': 'disc',
    'Numero de disco': 'disc',
    'Número de la canción': 'track_number',
    'Numero de la cancion': 'track_number',
    'Fecha de lanzamiento del álbum': 'release_date',
    'Popularidad': 'popularity',
    'ISRC': 'isrc',
}

COLUMN_MAP_EN = {
    'Track URI': 'uri',
    'Track Name': 'title',
    'Artist URI(s)': 'artist_uri',
    'Artist Name(s)': 'artist',
    'Album URI': 'album_uri',
    'Album Name': 'album',
    'Album Artist URI(s)': 'album_artist_uri',
    'Album Artist Name(s)': 'album_artist',
    'Album Release Date': 'release_date',
    'Album Image URL': 'artwork_url',
    'Disc Number': 'disc',
    'Track Number': 'track_number',
    'Track Duration (ms)': 'duration_ms',
    'Track Preview URL': 'preview_url',
    'Explicit': 'explicit',
    'Popularity': 'popularity',
    'ISRC': 'isrc',
    'Added By': 'added_by',
    'Added At': 'added_at',
}


def parse_exportify_csv(file_path_or_content, name='Playlist CSV'):
    """
    Parsea un CSV exportado desde Exportify (espanol o ingles).

    Args:
        file_path_or_content: ruta al archivo CSV (str) O contenido
                              del CSV como str.
        name (str): nombre a usar para la playlist (por defecto
                    "Playlist CSV"; si se pasa el nombre del archivo
                    sin extension, se usa ese).

    Returns:
        dict con la misma estructura que fetch_spotify_playlist().
    """
    # Leer contenido
    if isinstance(file_path_or_content, (str, os.PathLike)) and os.path.exists(file_path_or_content):
        with open(file_path_or_content, 'r', encoding='utf-8-sig', newline='') as f:
            content = f.read()
        # Usar nombre del archivo si no se especifico uno
        if name == 'Playlist CSV':
            name = Path(file_path_or_content).stem
    else:
        content = str(file_path_or_content)

    # Parsear CSV
    # Usar utf-8-sig para quitar BOM si existe
    reader = csv.DictReader(io.StringIO(content))

    # Detectar si es CSV en espanol o ingles segun los headers
    headers_lower = [h.strip().lower() for h in reader.fieldnames if h]
    is_spanish = any('canci' in h or 'canc' in h for h in headers_lower)

    column_map = COLUMN_MAP_ES if is_spanish else COLUMN_MAP_EN

    # Mapear headers reales a nuestras claves (case-insensitive, sin acentos)
    import unicodedata
    def normalize_header(h):
        if not h:
            return ''
        h = unicodedata.normalize('NFD', h)
        h = ''.join(c for c in h if unicodedata.category(c) != 'Mn')
        return h.strip().lower()

    # Construir mapeo case-insensitive
    column_map_normalized = {normalize_header(k): v for k, v in column_map.items()}

    tracks = []
    for row in reader:
        # Convertir row a dict con claves normalizadas
        row_normalized = {}
        for k, v in row.items():
            if k is None:
                continue
            nk = normalize_header(k)
            if nk in column_map_normalized:
                row_normalized[column_map_normalized[nk]] = v

        # Extraer campos
        title = (row_normalized.get('title') or '').strip()
        artist = (row_normalized.get('artist') or '').strip()
        album = (row_normalized.get('album') or '').strip()
        duration_ms_str = (row_normalized.get('duration_ms') or '0').strip()
        uri = (row_normalized.get('uri') or '').strip()

        if not title:
            continue  # fila vacia

        # Duracion ms -> segundos
        try:
            duration_ms = int(duration_ms_str)
        except (ValueError, TypeError):
            duration_ms = 0
        duration = duration_ms / 1000.0

        # URL: convertir URI a URL de Spotify
        # spotify:track:32ymjP2XIGKTj2dIXURWzT -> https://open.spotify.com/track/32ymjP2XIGKTj2dIXURWzT
        url = ''
        if uri.startswith('spotify:'):
            parts = uri.split(':')
            if len(parts) >= 3:
                url = f"https://open.spotify.com/{parts[1]}/{parts[2]}"
        elif uri.startswith('https://'):
            url = uri

        tracks.append({
            'title': title,
            'artist': artist or 'Desconocido',
            'album': album,
            'duration': duration,
            'url': url,
        })

    if not tracks:
        return {
            'title': name,
            'uploader': 'Importado desde CSV',
            'count': 0,
            'tracks': [],
            'error': 'El CSV no contiene canciones validas. Verifica que sea un CSV exportado desde https://exportify.app/',
            'warning': None,
        }

    return {
        'title': name,
        'uploader': 'Importado desde CSV',
        'count': len(tracks),
        'tracks': tracks,
        'error': None,
        'warning': None,
        'method': 'csv',
    }
