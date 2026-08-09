"""
app/playlist_youtube.py
=======================
Lee playlists PUBLICAS de YouTube Music usando yt-dlp.

yt-dlp es una libreria/herramienta que permite descargar y
extraer informacion de videos y playlists de YouTube sin
necesidad de iniciar sesion (para contenido publico).

URLs soportadas:
  - https://music.youtube.com/playlist?list=PLxxxxx
  - https://www.youtube.com/playlist?list=PLxxxxx
  - https://youtube.com/playlist?list=PLxxxxx

NO requiere:
  - Cuenta de Google
  - API key
  - Cookies

Limitaciones:
  - Solo funciona con playlists PUBLICAS (no privadas ni
    "no listadas" / unlisted).
  - Si YouTube cambia su interfaz, yt-dlp podria fallar hasta
    ser actualizado (se actualiza con frecuencia, ejecuta
    `pip install --upgrade yt-dlp` si falla).
"""

import re
import yt_dlp


# ------------------------------------------------------------------
# Opciones de yt-dlp: solo extraer info, no descargar el audio.
# ------------------------------------------------------------------
# download=False  -> no descarga archivos
# quiet=True      -> no imprime progreso en consola
# no_warnings=True -> suprime advertencias
# extract_flat='in_playlist' -> lista los videos sin bajar detalle
#   de cada uno (mas rapido), pero luego pedimos mas info por cancion.
# ------------------------------------------------------------------
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,        # Solo lista los items, no profundiza
    'skip_download': True,       # No descargar audio
}


def extract_playlist_id(url):
    """
    Extrae el ID de la playlist (parametro 'list=') de una URL.

    Acepta URLs de YouTube Music y YouTube normales.

    Args:
        url (str): URL completa.

    Returns:
        str | None: el ID de la playlist o None si no se encontro.
    """
    # Patron: list=PL... o list=OLAK... o list=RD...
    match = re.search(r'[?&]list=([A-Za-z0-9_-]+)', url)
    if match:
        return match.group(1)
    # Si el usuario solo pego el ID
    if re.match(r'^[A-Za-z0-9_-]{10,}$', url.strip()):
        return url.strip()
    return None


def fetch_youtube_playlist(url):
    """
    Descarga la lista de canciones de una playlist publica de
    YouTube Music / YouTube.

    Args:
        url (str): URL de la playlist o solo el ID.

    Returns:
        dict con:
          - 'title'    (str): titulo de la playlist
          - 'uploader' (str): autor de la playlist
          - 'count'    (int): numero de canciones
          - 'tracks'   (list[dict]): canciones con:
                'title', 'artist', 'duration', 'url', 'video_id'
          - 'error'    (str | None): mensaje si fallo
    """
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return {
            'title': '',
            'uploader': '',
            'count': 0,
            'tracks': [],
            'error': 'URL invalida. Debe contener ?list=... o ser un ID de playlist.'
        }

    # Construir URL canonica para yt-dlp
    canonical_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    try:
        # yt-dlp se usa como context manager para no dejar ficheros abiertos
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(canonical_url, download=False)

        if info is None:
            return _error('No se pudo extraer informacion de la playlist.')

        # Si la playlist es privada o no listada, yt-dlp devuelve error
        if 'entries' not in info:
            return _error('La respuesta no contiene canciones. ¿Es una playlist publica?')

        tracks = []
        for entry in info['entries']:
            if entry is None:
                continue  # Skipear entradas vacias (videos eliminados)

            # En modo extract_flat, 'entries' tiene info basica.
            # Cada entry tiene: title, url, duration, uploader, etc.
            title = entry.get('title', 'Desconocido')
            uploader = entry.get('uploader') or entry.get('channel') or 'Desconocido'
            duration = entry.get('duration') or 0
            video_url = entry.get('url') or entry.get('id', '')
            video_id = entry.get('id', '')

            # A veces yt-dlp devuelve url como 'https://www.youtube.com/watch?v=ID'
            # y otras solo el ID. Normalizamos:
            if video_id and not video_url.startswith('http'):
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            tracks.append({
                'title': title,
                'artist': uploader,
                'duration': float(duration) if duration else 0,
                'url': video_url,
                'video_id': video_id,
            })

        return {
            'title': info.get('title', 'Playlist sin titulo'),
            'uploader': info.get('uploader') or info.get('channel') or '',
            'count': len(tracks),
            'tracks': tracks,
            'error': None,
        }

    except yt_dlp.utils.DownloadError as e:
        return _error(f'YouTube no permitio leer la playlist: {str(e)[:200]}')
    except Exception as e:
        return _error(f'Error inesperado: {str(e)[:200]}')


def _error(msg):
    """Helper para devolver un dict de error con la misma estructura."""
    return {
        'title': '',
        'uploader': '',
        'count': 0,
        'tracks': [],
        'error': msg,
    }
