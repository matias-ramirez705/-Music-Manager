"""
app/auto_metadata.py
====================
Busca metadata de canciones en internet para rellenar
automaticamente los tags de archivos locales.

Fuentes soportadas (selector en la UI):
  1. iTunes Search API
     - URL: https://itunes.apple.com/search
     - GRATUITA, sin registro, sin API key.
     - Cobertura: muy buena en musica comercial.
  2. MusicBrainz
     - URL: https://musicbrainz.org/ws/2/recording
     - GRATUITA, sin API key (recomiendan User-Agent).
     - Cobertura: muy buena en albumes / clasicos / indie.
  3. Last.fm (public search via web scraping ligero)
     - Sin API key: usamos el endpoint publico de busqueda.
     - Cobertura: buena para artistas y albums populares.
     - Nota: puede dejar de funcionar si Last.fm cambia la pagina.

  4. Spotify public search (via embed)
     - Experimental: Spotify no expone search publico sin
       credenciales. Lo dejamos como "no disponible" pero
       la estructura permite agregarlo facil en el futuro.

Todas las fuentes devuelven el mismo formato (ver search_track()).
"""

import requests


# Endpoint publico de iTunes Search API
ITUNES_ENDPOINT = "https://itunes.apple.com/search"

# Endpoint publico de MusicBrainz
MUSICBRAINZ_ENDPOINT = "https://musicbrainz.org/ws/2/recording"

# Last.fm public search (HTML)
LASTFM_SEARCH = "https://www.last.fm/search"


# Cabeceras comunes
def _headers(extra=None):
    h = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36'),
    }
    if extra:
        h.update(extra)
    return h


# ==================================================================
# ITUNES
# ==================================================================
def _search_itunes(title, artist='', limit=5):
    """Busca en iTunes Search API (gratis, sin registro)."""
    query = f"{title} {artist}".strip()
    params = {
        'term': query,
        'media': 'music',
        'entity': 'song',
        'limit': limit,
    }
    try:
        resp = requests.get(ITUNES_ENDPOINT, params=params,
                            headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for item in data.get('results', []):
        results.append({
            'source': 'iTunes',
            'title':        item.get('trackName', ''),
            'artist':       item.get('artistName', ''),
            'album':        item.get('collectionName', ''),
            'year':         (item.get('releaseDate', '')[:4]
                             if item.get('releaseDate') else ''),
            'genre':        item.get('primaryGenreName', ''),
            'track_number': item.get('trackNumber', ''),
            'duration':     (item.get('trackTimeMillis', 0) / 1000.0
                             if item.get('trackTimeMillis') else 0),
            'artwork_url':  (item.get('artworkUrl100', '')
                             .replace('100x100', '600x600')
                             if item.get('artworkUrl100') else ''),
            'preview_url':  item.get('previewUrl', ''),
            'external_url': item.get('trackViewUrl', ''),
        })
    return results


# ==================================================================
# MUSICBRAINZ
# ==================================================================
def _search_musicbrainz(title, artist='', limit=5):
    """
    Busca en MusicBrainz.
    MusicBrainz requiere un User-Agent descriptivo (lo incluimos en _headers).
    Formato de respuesta: JSON con 'recordings'.
    """
    query_parts = [f'recording:"{title}"']
    if artist:
        query_parts.append(f'artist:"{artist}"')
    query = ' AND '.join(query_parts)

    params = {
        'query': query,
        'limit': limit,
        'fmt': 'json',
    }
    try:
        resp = requests.get(MUSICBRAINZ_ENDPOINT, params=params,
                            headers=_headers({
                                'Accept': 'application/json'
                            }), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    for rec in data.get('recordings', []):
        # Artista: primer 'artist-credit'
        artists = []
        for ac in rec.get('artist-credit', []):
            if isinstance(ac, dict) and 'name' in ac:
                artists.append(ac['name'])
        artist_str = ', '.join(artists) if artists else ''

        # Album: primer 'release'
        album = ''
        year = ''
        track_num = ''
        if rec.get('releases'):
            r = rec['releases'][0]
            album = r.get('title', '')
            date = r.get('date', '')
            year = date[:4] if date else ''
            track_num = r.get('medium', {}).get('track', [{}])[0].get('number', '') \
                if r.get('medium') else ''

        # Genero: MusicBrainz lo guarda en 'tags' (no siempre presente)
        genre = ''
        if rec.get('tags'):
            genre = rec['tags'][0].get('name', '')

        # Caratula: MusicBrainz no devuelve caratula directamente.
        # Usamos Cover Art Archive si esta disponible.
        artwork_url = ''
        if rec.get('releases'):
            release_id = rec['releases'][0].get('id', '')
            if release_id:
                artwork_url = f"https://coverartarchive.org/release/{release_id}/front"

        results.append({
            'source': 'MusicBrainz',
            'title':        rec.get('title', ''),
            'artist':       artist_str,
            'album':        album,
            'year':         year,
            'genre':        genre,
            'track_number': track_num,
            'duration':     (rec.get('length', 0) / 1000.0
                             if rec.get('length') else 0),
            'artwork_url':  artwork_url,
            'preview_url':  '',
            'external_url': f"https://musicbrainz.org/recording/{rec.get('id', '')}",
        })
    return results


# ==================================================================
# LAST.FM (sin API key, via scraping ligero de la pagina de busqueda)
# ==================================================================
def _search_lastfm(title, artist='', limit=5):
    """
    Busca en Last.fm usando la pagina publica de busqueda.
    Nota: NO usa API key. Funciona mientras Last.fm mantenga el HTML.
    Devuelve metadata basica (titulo, artista, sin caratula directa).
    """
    import re
    from html import unescape
    query = f"{title} {artist}".strip()
    params = {'q': query, 'type': 'tracks'}
    try:
        resp = requests.get(LASTFM_SEARCH, params=params,
                            headers=_headers(), timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    # Last.fm lista resultados en <li class="search-result">
    # Cada item tiene:
    #   <a class="link-block-target" href="/music/Artist/_/Track">Track name</a>
    #   <p class="artist">...<a>Artist</a></p>
    #   <img src="...album art...">
    results = []
    # Buscar bloques de track
    track_pattern = re.compile(
        r'<h2[^>]*>\s*<a[^>]*href="(/music/[^"]+)"[^>]*>([^<]+)</a>',
        re.DOTALL
    )
    artist_pattern = re.compile(
        r'<p[^>]*class="[^"]*artist[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
        re.DOTALL
    )
    img_pattern = re.compile(
        r'<img[^>]*class="[^"]*image-list-item[^"]*"[^>]*src="([^"]+)"',
        re.DOTALL
    )

    # Buscar todos los items por separado es complejo sin parsear DOM.
    # Estrategia: dividir el HTML en bloques por "search-result" y
    # extraer de cada uno el primer match de cada patron.
    blocks = re.split(r'<li class="search-result', resp.text)
    for block in blocks[1:limit + 1]:  # saltar el primer split (pre-primer-bloque)
        title_m = re.search(r'<a[^>]*class="link-block-target"[^>]*>([^<]+)</a>', block)
        artist_m = re.search(r'<a[^>]*>([^<]+)</a>\s*</p>', block)
        img_m = re.search(r'<img[^>]*src="(https?://[^"]+)"[^>]*>', block)

        if not title_m:
            continue
        t_title = unescape(title_m.group(1)).strip()
        t_artist = unescape(artist_m.group(1)).strip() if artist_m else ''
        t_artwork = img_m.group(1) if img_m else ''
        # Last.fm sirve imagenes pequenas; forzar tamano mayor reemplazando /64s/ o /64/
        t_artwork = re.sub(r'/\d+s?/', '/300s/', t_artwork)

        results.append({
            'source': 'Last.fm',
            'title': t_title,
            'artist': t_artist,
            'album': '',  # Last.fm no lo muestra en search results
            'year': '',
            'genre': '',
            'track_number': '',
            'duration': 0,
            'artwork_url': t_artwork,
            'preview_url': '',
            'external_url': f"https://www.last.fm{track_m.group(1) if (track_m := re.search(r'href=\"(/music/[^\"]+)\"', block)) else ''}",
        })
    return results


# ==================================================================
# FUNCION PUBLICA: search_track
# ==================================================================
def search_track(title, artist='', limit=5, source='itunes'):
    """
    Busca una cancion en la fuente indicada.

    Args:
        title  (str): titulo de la cancion.
        artist (str): artista (opcional, mejora precision).
        limit  (int): maximo de resultados por fuente.
        source (str): 'itunes' | 'musicbrainz' | 'lastfm' | 'all'
                      'all' combina las 3 fuentes y devuelve los mejores.

    Returns:
        list[dict]: cada elemento tiene los campos descritos en la
        documentacion del modulo.
    """
    if not title:
        return []

    if source == 'itunes':
        return _search_itunes(title, artist, limit)
    elif source == 'musicbrainz':
        return _search_musicbrainz(title, artist, limit)
    elif source == 'lastfm':
        return _search_lastfm(title, artist, limit)
    elif source == 'all':
        # Buscar en las 3 fuentes en paralelo (secuencial por simplicidad)
        all_results = []
        all_results.extend(_search_itunes(title, artist, limit))
        all_results.extend(_search_musicbrainz(title, artist, limit))
        all_results.extend(_search_lastfm(title, artist, limit))
        return all_results[:limit * 2]
    else:
        return []


def best_match(results, target_title='', target_artist=''):
    """
    Heuristica simple: devuelve el resultado cuyo titulo y artista
    coinciden mas cercanamente con los buscados.
    """
    if not results:
        return None

    def normalize(s):
        import unicodedata
        s = (s or '').lower().strip()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        return s

    n_title = normalize(target_title)
    n_artist = normalize(target_artist)

    best = None
    best_score = -1

    for r in results:
        score = 0
        if n_title and n_title in normalize(r['title']):
            score += 2
        elif normalize(r['title']) and normalize(r['title']) in n_title:
            score += 1
        if n_artist and n_artist in normalize(r['artist']):
            score += 2
        elif normalize(r['artist']) and normalize(r['artist']) in n_artist:
            score += 1
        # Bonus: iTunes tiene mejor cobertura
        if r.get('source') == 'iTunes':
            score += 0.5
        if score > best_score:
            best_score = score
            best = r

    return best or results[0]
