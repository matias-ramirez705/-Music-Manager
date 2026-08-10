"""
app/playlist_spotify.py
=======================
Lee playlists PUBLICAS de Spotify sin necesidad de iniciar sesion
ni registrar una aplicacion en Spotify Developer.

Mecanismo (v1.2 - con paginacion completa):
  1. Obtiene un TOKEN ANONIMO desde
     https://open.spotify.com/get_access_token
     Este token lo usa el reproductor web publico de Spotify y
     permite leer datos de playlists publicas sin login.

  2. Usa la Spotify Web API con ese token para paginar TODAS las
     canciones:
        GET https://api.spotify.com/v1/playlists/{id}/tracks
            ?offset=0&limit=100&additional_types=track
     Se itera con offset+=100 hasta tener todas.

  3. Obtiene metadata de la playlist (titulo, autor, total) desde
        GET https://api.spotify.com/v1/playlists/{id}

Ventajas sobre la version anterior (que parseaba el embed):
  - Funciona con playlists de mas de 100 canciones (era el limite).
  - Mas robusto: la API JSON es estable, el HTML del embed cambia.
  - Devuelve caratula del album, ISRC, y otros campos utiles.

NO requiere:
  - Cuenta de Spotify
  - Client ID / Client Secret
  - OAuth token de usuario

Limitaciones:
  - Solo playlists PUBLICAS.
  - El token anonimo puede caducar o ser bloqueado en algunas
    regiones. Si falla, se hace fallback al metodo antiguo (embed).
"""

import re
import json
import requests
from urllib.parse import quote


# Cabeceras para parecer un navegador normal.
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/120.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
}

# Endpoints
EMBED_URL     = "https://open.spotify.com/embed/playlist/{id}"
API_PLAYLIST  = "https://api.spotify.com/v1/playlists/{id}"
API_TRACKS    = "https://api.spotify.com/v1/playlists/{id}/tracks?offset={offset}&limit=100&additional_types=track"

# Cuantas paginas maximo pedir (evitar loops infinitos si algo falla)
MAX_PAGES = 50  # 50 * 100 = 5000 canciones maximo


def extract_playlist_id(url):
    """
    Extrae el ID de una playlist de Spotify desde la URL.

    Acepta:
      - https://open.spotify.com/playlist/XXXXX
      - https://open.spotify.com/playlist/XXXXX?si=abc
      - https://open.spotify.com/embed/playlist/XXXXX
      - spotify:playlist:XXXXX
      - Solo el ID (22 caracteres alfanumericos)
    """
    match = re.search(r'spotify\.com/(?:embed/)?playlist/([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'spotify:playlist:([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    if re.match(r'^[A-Za-z0-9]{22}$', url.strip()):
        return url.strip()
    return None


def _get_anon_token(playlist_id):
    """
    Obtiene un token anonimo de Spotify.

    Estrategia:
      1. Spotify bloquea el endpoint directo /get_access_token (403 Varnish).
      2. Pero la pagina EMBED (https://open.spotify.com/embed/playlist/ID)
         contiene en su HTML un bloque JSON con el campo "accessToken".
         Ese token es valido para la Spotify Web API y permite paginar
         todas las canciones de playlists publicas.

    Returns:
        str | None: token, o None si fallo.
    """
    embed_url = EMBED_URL.format(id=playlist_id)
    try:
        resp = requests.get(embed_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    # Buscar el accessToken en el HTML (esta dentro de un script JSON)
    match = re.search(r'"accessToken":"([^"]+)"', resp.text)
    if match:
        return match.group(1)
    return None


def _api_get(url, token):
    """
    GET a la API de Spotify con cabecera Authorization.

    Maneja 429 (rate-limit) devolviendo None inmediatamente si el
    Retry-After es mayor a 60s (caso tipico de quota-exceeded global
    que bloquea por horas). Para retries cortos, espera y reintenta.
    """
    headers = {**HEADERS, 'Authorization': f'Bearer {token}'}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 401:
            # Token expirado o invalido
            return None
        if resp.status_code == 429:
            # Rate limited
            retry = int(resp.headers.get('Retry-After', '2'))
            if retry > 60:
                # Quota global: no reintentar (bloqueo de horas)
                return None
            import time
            time.sleep(min(retry + 1, 30))
            # Un solo reintento
            try:
                resp = requests.get(url, headers=headers, timeout=20)
                if resp.status_code != 200:
                    return None
            except requests.RequestException:
                return None
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def fetch_spotify_playlist(url):
    """
    Descarga TODAS las canciones de una playlist publica de Spotify.

    Estrategia (v1.3):
      1. INTENTAR PRIMERO la API OFICIAL via spotipy con Client
         Credentials (si el usuario configuro sus credenciales en .env).
         Esto da paginacion completa y sin bloqueos de rate-limit.
      2. Si no hay credenciales o fallan, intentar con token anonimo
         del embed + Web API (a veces funciona).
      3. Si todo lo anterior falla, usar el metodo del embed (limitado
         a 100 canciones) con warning claro al usuario.

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
          - 'warning'  (str | None): aviso si la playlist vino incompleta
          - 'total_expected' (int | None): total real segun Spotify
          - 'method'   (str): 'official' | 'anon_token' | 'embed'
    """
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return _error('URL invalida. Debe ser una URL de playlist de Spotify.')

    # 1. Intentar via API oficial (spotipy + client credentials)
    try:
        from spotify_official import fetch_playlist_official, is_configured
        if is_configured():
            result = fetch_playlist_official(playlist_id)
            if result and not result.get('error'):
                result['method'] = 'official'
                return result
    except ImportError:
        pass  # spotipy no instalado

    # 2. Intentar via Web API con token anonimo extraido del embed
    token = _get_anon_token(playlist_id)
    if token:
        result = _fetch_via_api(playlist_id, token)
        if result and not result.get('error'):
            result['method'] = 'anon_token'
            return result

    # 3. Fallback final: metodo del embed (limitado a 100)
    result = _fetch_via_embed(playlist_id)
    if result:
        result['method'] = 'embed'
        # Si estamos en fallback, sugerir usar Exportify (CSV)
        if result.get('warning'):
            result['warning'] = ('Spotify solo permite leer las primeras 100 '
                'canciones por link. Para cargar TODAS las canciones, exporta '
                'la playlist como CSV desde https://exportify.app/ e '
                'importala con el boton "Importar CSV" en Playlists Guardadas.')
    return result


def _fetch_via_api(playlist_id, token):
    """
    Usa la Spotify Web API con el token anonimo para paginar todas
    las canciones.

    Optimizado: descarga todas las paginas en paralelo usando hilos
    para acelerar playlists grandes (500+ canciones pasan de 60s a 10s).

    NOTA IMPORTANTE (2024+):
      Spotify ha empezado a bloquear (HTTP 429 con QUOTA_EXCEEDED) el
      acceso a /v1/playlists con tokens anonimos extraidos del embed.
      Si esto ocurre, devolvemos None y dejamos que el fallback del
      embed tome el control (limitado a 100 canciones).
    """
    import concurrent.futures

    # 1. Obtener metadata de la playlist
    pl_data = _api_get(API_PLAYLIST.format(id=playlist_id), token)
    if not pl_data:
        return None  # Fallback al embed

    # Si recibimos 429 (quota), pl_data sera None y caemos al fallback
    title = pl_data.get('name', 'Playlist sin titulo')
    owner = (pl_data.get('owner', {}) or {}).get('display_name', '') \
            or (pl_data.get('owner', {}) or {}).get('id', '')
    total = pl_data.get('tracks', {}).get('total', 0)

    if total == 0:
        return {
            'title': title, 'uploader': owner, 'count': 0,
            'tracks': [], 'error': None,
        }

    # 2. Calcular cuantas paginas necesitamos (100 canciones por pagina)
    num_pages = min(MAX_PAGES, (total + 99) // 100)
    offsets = [i * 100 for i in range(num_pages)]

    # 3. Descargar todas las paginas en paralelo (hasta 8 hilos)
    pages_data = [None] * num_pages
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_idx = {
            executor.submit(_api_get,
                            API_TRACKS.format(id=playlist_id, offset=off),
                            token): idx
            for idx, off in enumerate(offsets)
        }
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                pages_data[idx] = future.result()
            except Exception:
                pages_data[idx] = None

    # 4. Si TODAS las paginas fallaron (tipico de rate-limiting global),
    #    devolver None para que el fallback del embed tome el control.
    if all(p is None for p in pages_data):
        return None

    # 5. Procesar las paginas en orden
    tracks = []
    for page_data in pages_data:
        if not page_data:
            continue
        items = page_data.get('items', [])
        for item in items:
            track = item.get('track') if isinstance(item, dict) else None
            if not track or not isinstance(track, dict):
                continue

            t_title = track.get('name', 'Desconocido')
            artists_list = track.get('artists', []) or []
            t_artist = ', '.join(
                a.get('name', '') for a in artists_list if a
            ) or 'Desconocido'

            album = track.get('album', {}) or {}
            t_album = album.get('name', '') if isinstance(album, dict) else ''

            duration_ms = track.get('duration_ms', 0) or 0
            t_duration = duration_ms / 1000.0

            t_url = ''
            ext_url = track.get('external_urls', {}) or {}
            if ext_url and 'spotify' in ext_url:
                t_url = ext_url['spotify']
            elif track.get('uri'):
                t_url = _uri_to_url(track['uri'])

            tracks.append({
                'title': t_title,
                'artist': t_artist,
                'album': t_album,
                'duration': t_duration,
                'url': t_url,
            })

    if not tracks:
        return None

    # 6. Si el total declarado es mayor a lo que pudimos obtener, anadir
    #    advertencia para que el usuario sepa que faltan.
    warning = None
    if total > len(tracks):
        warning = (f'Solo se pudieron obtener {len(tracks)} de {total} canciones. '
                   f'Spotify esta bloqueando el acceso a la API. '
                   f'Para tener la lista completa, usa la misma playlist en YouTube Music.')

    return {
        'title': title,
        'uploader': owner,
        'count': len(tracks),
        'tracks': tracks,
        'error': None,
        'warning': warning,
        'total_expected': total,
    }


def _fetch_via_embed(playlist_id):
    """
    Fallback: extrae del HTML del embed (limitado a ~100 canciones).
    Se mantiene por si el token anonimo falla.
    """
    embed_url = EMBED_URL.format(id=playlist_id)

    try:
        resp = requests.get(embed_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        return _error(f'No se pudo conectar con Spotify: {str(e)[:200]}')

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        resp.text, re.DOTALL
    )
    if not match:
        return _error('No se encontro el bloque de datos en la pagina de Spotify.')

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        return _error(f'Error parseando JSON de Spotify: {str(e)[:200]}')

    playlist = _find_playlist_node(data)
    if not playlist:
        return _error('No se encontro la playlist en los datos de Spotify.')

    title = playlist.get('name', 'Playlist sin titulo')
    owner = (playlist.get('owner', {}) or {}).get('name', '')

    track_items = _extract_track_items(playlist)

    tracks = []
    for item in track_items:
        if not item:
            continue
        track = item.get('track', item) if isinstance(item, dict) else None
        if not track or not isinstance(track, dict):
            continue

        t_title = track.get('name', 'Desconocido')
        artists_list = track.get('artists', []) or []
        t_artist = ', '.join(a.get('name', '') for a in artists_list if a)
        album = track.get('album', {}) or {}
        t_album = album.get('name', '') if isinstance(album, dict) else ''
        duration_ms = track.get('duration_ms', 0) or 0
        t_duration = duration_ms / 1000.0

        t_url = ''
        if 'uri' in track:
            t_url = _uri_to_url(track['uri'])
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

    # El embed de Spotify siempre devuelve max 100 canciones. Si la playlist
    # tiene mas, lo indicamos al usuario con un mensaje claro.
    warning = None
    if len(tracks) == 100:
        warning = ('Spotify solo permite leer las primeras 100 canciones por '
                   'link. Para cargar TODAS las canciones, exporta la playlist '
                   'como CSV desde https://exportify.app/ e importala con el '
                   'boton "Importar CSV" en Playlists Guardadas.')

    return {
        'title': title,
        'uploader': owner,
        'count': len(tracks),
        'tracks': tracks,
        'error': None,
        'warning': warning,
    }


# ------------------------------------------------------------------
# Helpers para recorrer el JSON del embed (fallback)
# ------------------------------------------------------------------
def _find_playlist_node(data):
    """Busca recursivamente el nodo con 'trackList' o 'tracks'."""
    if isinstance(data, dict):
        if 'name' in data and ('trackList' in data or 'tracks' in data):
            return data
        if 'playlist' in data and isinstance(data['playlist'], dict):
            return data['playlist']
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
    """Extrae items de pistas del nodo de playlist (embed)."""
    if 'trackList' in playlist and isinstance(playlist['trackList'], list):
        items = []
        for t in playlist['trackList']:
            # El embed usa 'duration' (en ms), 'title', 'subtitle' (artista),
            # 'uri' (spotify:track:ID).
            items.append({
                'track': {
                    'name': t.get('title', ''),
                    'uri': t.get('uri', ''),
                    'artists': [{'name': t.get('subtitle', '')}] if t.get('subtitle') else [],
                    'album': {},
                    'duration_ms': t.get('duration', 0),  # campo correcto: 'duration'
                }
            })
        return items
    tracks_node = playlist.get('tracks', {})
    if isinstance(tracks_node, dict) and 'items' in tracks_node:
        return tracks_node['items']
    if isinstance(tracks_node, list):
        return tracks_node
    return []


def _error(msg):
    """Helper para devolver un dict de error."""
    return {
        'title': '',
        'uploader': '',
        'count': 0,
        'tracks': [],
        'error': msg,
    }


def _uri_to_url(uri):
    """
    Convierte un URI de Spotify (spotify:track:ID, spotify:album:ID, etc.)
    a una URL absoluta (https://open.spotify.com/track/ID).

    IMPORTANTE: No usar replace(':', '/') globalmente porque tambien
    rompe el 'https://' (lo convierte en 'https//'). Por eso extraemos
    el tipo y el ID manualmente.
    """
    if not uri or not uri.startswith('spotify:'):
        return uri or ''
    # 'spotify:track:32ymjP2XIGKTj2dIXURWzT' -> ['spotify', 'track', 'ID']
    parts = uri.split(':')
    if len(parts) >= 3:
        return f"https://open.spotify.com/{parts[1]}/{parts[2]}"
    return uri
