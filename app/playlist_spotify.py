"""
app/playlist_spotify.py
=======================
Lee playlists PUBLICAS de Spotify sin necesidad de iniciar sesion
ni registrar una aplicacion en Spotify Developer.

Mecanismo:
  Spotify ofrece una URL "embed" publica para cada playlist:
      https://open.spotify.com/embed/playlist/PLAYLIST_ID

  Esa pagina contiene un bloque <script id="__NEXT_DATA__"> con un
  JSON que incluye la lista completa de canciones. Lo descargamos
  con requests y parseamos el JSON.

NO requiere:
  - Cuenta de Spotify
  - Client ID / Client Secret
  - OAuth token

Limitaciones:
  - Solo playlists PUBLICAS.
  - Spotify podria cambiar el formato del embed en cualquier momento.
    Si deja de funcionar, revisa la version de requests y este script.
  - Para playlists muy grandes (>100 canciones) puede requerir
    paginacion adicional. Aqui se extraen las primeras 100-300
    dependiendo del payload inicial.
"""

import re
import json
import requests
from urllib.parse import quote


# Cabeceras para parecer un navegador normal (evita bloqueos basicos).
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/120.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
}


def extract_playlist_id(url):
    """
    Extrae el ID de una playlist de Spotify desde la URL.

    Acepta:
      - https://open.spotify.com/playlist/XXXXX
      - https://open.spotify.com/playlist/XXXXX?si=abc
      - https://open.spotify.com/embed/playlist/XXXXX
      - Solo el ID (22 caracteres alfanumericos)

    Args:
        url (str): URL o ID.

    Returns:
        str | None: ID de la playlist o None si no es valido.
    """
    # Patron 1: URL de playlist
    match = re.search(r'spotify\.com/(?:embed/)?playlist/([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    # Patron 2: URI de Spotify (spotify:playlist:ID)
    match = re.search(r'spotify:playlist:([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    # Patron 3: ID suelto (22 chars base62)
    if re.match(r'^[A-Za-z0-9]{22}$', url.strip()):
        return url.strip()
    return None


def fetch_spotify_playlist(url):
    """
    Descarga la lista de canciones de una playlist publica de Spotify.

    Args:
        url (str): URL de la playlist o ID.

    Returns:
        dict con:
          - 'title'    (str): nombre de la playlist
          - 'uploader' (str): autor
          - 'count'    (int): numero de canciones
          - 'tracks'   (list[dict]): canciones con:
                'title', 'artist', 'album', 'duration', 'url'
          - 'error'    (str | None)
    """
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return _error('URL invalida. Debe ser una URL de playlist de Spotify.')

    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"

    try:
        resp = requests.get(embed_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        return _error(f'No se pudo conectar con Spotify: {str(e)[:200]}')

    # Buscar el bloque <script id="__NEXT_DATA__">...</script>
    # Spotify usa Next.js y aqui mete todo el estado inicial como JSON.
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        resp.text,
        re.DOTALL
    )
    if not match:
        return _error('No se encontro el bloque de datos en la pagina de Spotify. '
                      'Es posible que la playlist sea privada o que Spotify haya '
                      'cambiado su formato.')

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        return _error(f'Error parseando JSON de Spotify: {str(e)[:200]}')

    # El JSON tiene una estructura anidada que puede variar.
    # Buscamos recursivamente la primera clave 'playlist' que tenga 'tracks'.
    playlist = _find_playlist_node(data)

    if not playlist:
        return _error('No se encontro la playlist en los datos de Spotify.')

    # Extraer informacion basica de la playlist
    title = playlist.get('name', 'Playlist sin titulo')
    owner = (playlist.get('owner', {}) or {}).get('name', '')

    # Las canciones estan en playlist['trackList'] o playlist['tracks']['items']
    track_items = _extract_track_items(playlist)

    tracks = []
    for item in track_items:
        if not item:
            continue
        # Cada item tiene 'track' (en API real) o directamente los campos
        track = item.get('track', item) if isinstance(item, dict) else None
        if not track or not isinstance(track, dict):
            continue

        # Titulo
        t_title = track.get('name', 'Desconocido')

        # Artistas: lista de dict con 'name'
        artists_list = track.get('artists', []) or []
        t_artist = ', '.join(a.get('name', '') for a in artists_list if a)

        # Album
        album = track.get('album', {}) or {}
        t_album = album.get('name', '') if isinstance(album, dict) else ''

        # Duracion en ms -> convertir a segundos
        duration_ms = track.get('duration_ms', 0) or 0
        t_duration = duration_ms / 1000.0

        # URL de la cancion
        t_url = ''
        if 'uri' in track:
            uri = track['uri']  # spotify:track:ID
            t_url = uri.replace('spotify:', 'https://open.spotify.com/').replace(':', '/')
        elif 'id' in track:
            t_url = f"https://open.spotify.com/track/{track['id']}"

        tracks.append({
            'title': t_title,
            'artist': t_artist or 'Desconocido',
            'album': t_album,
            'duration': t_duration,
            'url': t_url,
        })

    if not tracks:
        return _error('La playlist no tiene canciones visibles (¿es privada?).')

    return {
        'title': title,
        'uploader': owner,
        'count': len(tracks),
        'tracks': tracks,
        'error': None,
    }


# ------------------------------------------------------------------
# Helpers internos para recorrer el JSON de Spotify
# ------------------------------------------------------------------
def _find_playlist_node(data):
    """
    Busca recursivamente el primer nodo que tenga 'trackList' o
    'tracks' con 'items'. Esto es necesario porque Spotify cambia
    la estructura exacta entre versiones de su sitio.
    """
    if isinstance(data, dict):
        # Caso 1: el nodo tiene 'name' y 'trackList'
        if 'name' in data and ('trackList' in data or 'tracks' in data):
            return data
        # Caso 2: tiene clave 'playlist' explicita
        if 'playlist' in data and isinstance(data['playlist'], dict):
            return data['playlist']
        # Buscar en todos los valores
        for v in data.values():
            found = _find_playlist_node(v)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_playlist_node(item)
            if found:
                return found
    return None


def _extract_track_items(playlist):
    """
    Extrae la lista de items de pistas desde el nodo de playlist.
    Spotify usa diferentes claves segun el contexto.
    """
    # Caso A: playlist['trackList'] (formato embed, sin detalles de album)
    if 'trackList' in playlist and isinstance(playlist['trackList'], list):
        items = []
        for t in playlist['trackList']:
            # En trackList del embed, cada item tiene: uid, uri, title, subtitle
            items.append({
                'track': {
                    'name': t.get('title', ''),
                    'uri': t.get('uri', ''),
                    'artists': [{'name': t.get('subtitle', '')}] if t.get('subtitle') else [],
                    'album': {},
                    'duration_ms': 0,
                }
            })
        return items

    # Caso B: playlist['tracks']['items'] (formato API completa)
    tracks_node = playlist.get('tracks', {})
    if isinstance(tracks_node, dict) and 'items' in tracks_node:
        return tracks_node['items']
    if isinstance(tracks_node, list):
        return tracks_node

    return []


def _error(msg):
    """Helper para devolver un dict de error con la misma estructura."""
    return {
        'title': '',
        'uploader': '',
        'count': 0,
        'tracks': [],
        'error': msg,
    }
