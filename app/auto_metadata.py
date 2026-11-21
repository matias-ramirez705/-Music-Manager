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
  4. SoundCloud (v3.20) - via yt-dlp
     - Usa yt-dlp con scsearch: para buscar en SoundCloud.
     - GRATUITA, sin API key (yt-dlp ya está instalado).
     - Cobertura: excelente para remixes, musica independiente,
       DJs, y canciones que no estan en plataformas comerciales.
  5. osu! (v3.20) - beatmap search
     - Usa el endpoint publico de busqueda de beatmapsets.
     - GRATUITA, sin API key.
     - Cobertura: excelente para musica de juegos de ritmo,
       remixes de anime, y musica comunitaria de internet.

Todas las fuentes devuelven el mismo formato (ver search_track()).
"""

import os
import json
import subprocess
import requests


# Endpoint publico de iTunes Search API
ITUNES_ENDPOINT = "https://itunes.apple.com/search"

# Endpoint publico de MusicBrainz
MUSICBRAINZ_ENDPOINT = "https://musicbrainz.org/ws/2/recording"

# Last.fm public search (HTML)
LASTFM_SEARCH = "https://www.last.fm/search"

# osu! beatmap search endpoint (publico, sin API key)
OSU_SEARCH_ENDPOINT = "https://osu.ppy.sh/beatmapsets/search/"


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
# SOUNDCLOUD (v3.20) - via yt-dlp scsearch
# ==================================================================
def _upgrade_soundcloud_thumbnail(url):
    """
    v3.21: SoundCloud sirve thumbnails en varios tamaños.
    yt-dlp en --flat-playlist suele devolver el más chico (t50x50 o t67x67).
    Reescribimos la URL para pedir el tamaño más grande disponible.

    Patrones comunes en URLs de SoundCloud:
    - https://i1.sndcdn.com/artworks-XXX-t50x50.jpg
    - https://i1.sndcdn.com/artworks-XXX-t120x120.jpg
    - https://i1.sndcdn.com/artworks-XXX-t300x300.jpg
    - https://i1.sndcdn.com/artworks-XXX-t500x500.jpg
    - https://i1.sndcdn.com/artworks-XXX-original.jpg

    Reemplazamos cualquier -tNNxNN por -t500x500, y si ya es original lo dejamos.
    """
    import re
    if not url:
        return ''
    # Reemplazar -tNNxNN por -t500x500
    upgraded = re.sub(r'-t\d+x\d+\.(jpg|jpeg|png|webp)', r'-t500x500.\1', url)
    # Si la URL no tenía patrón -tNNxNN, intentar con -large o -t300x300
    if upgraded == url:
        upgraded = url.replace('-large.', '-t500x500.')
        if upgraded == url:
            upgraded = url.replace('-t300x300.', '-t500x500.')
    return upgraded


def _pick_best_thumbnail(thumbs_list):
    """
    v3.21: de una lista de thumbnails de yt-dlp, devuelve la URL
    del más grande disponible. yt-dlp devuelve una lista ordenada
    de menor a mayor normalmente, pero no siempre.
    """
    if not isinstance(thumbs_list, list) or not thumbs_list:
        return ''
    best_url = ''
    best_pref = -1
    for t in thumbs_list:
        if not isinstance(t, dict):
            continue
        url = t.get('url', '') or t.get('id', '')
        if not url:
            continue
        # Preferir las que dicen "original" o tienen t500x500
        pref = 0
        if 'original' in url:
            pref = 100
        elif 't500x500' in url:
            pref = 90
        elif 't300x300' in url:
            pref = 80
        elif 't120x120' in url:
            pref = 50
        elif 't67x67' in url or 't50x50' in url:
            pref = 10
        # Si tiene campo 'preference' de yt-dlp, usarlo
        if t.get('preference'):
            pref += t.get('preference')
        if pref > best_pref:
            best_pref = pref
            best_url = url
    return best_url


def _fetch_soundcloud_thumbnail(url):
    """
    v3.21: hace una segunda pasada con yt-dlp SIN --flat-playlist
    para obtener el thumbnail en alta resolución de una canción
    específica de SoundCloud. Es más lento pero trae la carátula grande.

    Solo se llama como fallback si la primera pasada dio thumbnail chico.
    """
    if not url:
        return ''
    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-warnings', '--no-playlist', url],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ''
        item = json.loads(result.stdout.strip().split('\n')[0])
        thumbs = item.get('thumbnails')
        if isinstance(thumbs, list) and thumbs:
            return _pick_best_thumbnail(thumbs)
        if item.get('thumbnail'):
            return _upgrade_soundcloud_thumbnail(item.get('thumbnail'))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return ''


def _search_soundcloud(title, artist='', limit=5):
    """
    Busca en SoundCloud usando yt-dlp (scsearch:).
    No requiere API key. yt-dlp ya esta instalado en el proyecto.

    Cobertura: excelente para remixes, musica independiente, DJs,
    y canciones que no estan en plataformas comerciales.

    v3.21: mejora el manejo de thumbnails para no devolver caratulas
    de 16x16. Estrategia:
    1. En la primera pasada (--flat-playlist), buscar el thumbnail más
       grande de la lista de thumbnails.
    2. Si el thumbnail sigue siendo chico (t50x50, t67x67), reescribir
       la URL a t500x500 (SoundCloud los sirve si existen).
    3. Como último recurso, hacer una segunda pasada sin --flat-playlist
       para esa canción específica (más lento pero trae thumbnail grande).
    """
    query = f"{title} {artist}".strip()
    if not query:
        return []

    search_query = f"scsearch{limit}:{query}"

    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-warnings', '--flat-playlist', search_query],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ['yt-dlp', '--dump-json', '--no-warnings', search_query],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    results = []
    for line in result.stdout.strip().split('\n'):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        sc_title = item.get('title', '')
        sc_artist = item.get('uploader', item.get('uploader_id', item.get('channel', '')))
        sc_url = item.get('url', item.get('webpage_url', item.get('id', '')))
        if sc_url and not sc_url.startswith('http'):
            sc_url = f"https://soundcloud.com/{sc_url}"
        sc_duration = item.get('duration', 0) or 0

        # v3.21: mejor manejo de thumbnails
        # 1. Intentar con la lista de thumbnails (buscar el más grande)
        sc_thumbnail = _pick_best_thumbnail(item.get('thumbnails'))
        # 2. Si no hay lista, usar el campo 'thumbnail' directo
        if not sc_thumbnail and item.get('thumbnail'):
            sc_thumbnail = item.get('thumbnail')
        # 3. Si el thumbnail es chico, reescribir la URL a t500x500
        if sc_thumbnail and ('t50x50' in sc_thumbnail or 't67x67' in sc_thumbnail
                              or 't120x120' in sc_thumbnail or 'large' in sc_thumbnail):
            sc_thumbnail = _upgrade_soundcloud_thumbnail(sc_thumbnail)
        # 4. Si no hay thumbnail o sigue siendo chico, hacer segunda pasada
        #    (solo para los primeros 3 resultados para no demorar demasiado)
        if (not sc_thumbnail or 't50x50' in sc_thumbnail or 't67x67' in sc_thumbnail) \
                and sc_url and len(results) < 3:
            fetched = _fetch_soundcloud_thumbnail(sc_url)
            if fetched:
                sc_thumbnail = fetched

        results.append({
            'source': 'SoundCloud',
            'title':        sc_title,
            'artist':       sc_artist,
            'album':        '',
            'year':         '',
            'genre':        '',
            'track_number': '',
            'duration':     sc_duration,
            'artwork_url':  sc_thumbnail,
            'preview_url':  '',
            'external_url': sc_url,
        })

    return results[:limit]


# ==================================================================
# osu! (v3.20) - beatmap search
# ==================================================================
def _search_osu(title, artist='', limit=5):
    """
    Busca en la base de datos de beatmaps de osu! (juego de ritmo).
    Usa el endpoint publico de busqueda del sitio web.

    Cobertura: excelente para musica de juegos de ritmo, remixes de
    anime, y musica comunitaria de internet. Incluye BPM.
    """
    query = f"{title} {artist}".strip()
    if not query:
        return []

    params = {
        'q': query,
        'mode': 'any',
        's': 'any',
    }

    try:
        resp = requests.get(OSU_SEARCH_ENDPOINT, params=params,
                            headers=_headers({
                                'Accept': 'application/json',
                            }), timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    beatmapsets = data.get('beatmapsets', [])
    for bs in beatmapsets[:limit]:
        beatmaps = bs.get('beatmaps', [])
        bpm = 0
        if beatmaps:
            bpm = beatmaps[0].get('bpm', 0) or 0

        osu_title = bs.get('title', '')
        osu_artist = bs.get('artist', '')
        osu_creator = bs.get('creator', '')
        osu_source = bs.get('source', '')
        osu_album = osu_source if osu_source else f"osu! beatmap by {osu_creator}"
        osu_year = ''
        submitted = bs.get('submitted_date', '')
        if submitted:
            osu_year = submitted[:4]
        osu_covers = bs.get('covers', {})
        osu_artwork = osu_covers.get('list', osu_covers.get('cover', ''))
        osu_id = bs.get('id', '')
        osu_url = f"https://osu.ppy.sh/beatmapsets/{osu_id}" if osu_id else ''

        results.append({
            'source': 'osu!',
            'title':        osu_title,
            'artist':       osu_artist,
            'album':        osu_album,
            'year':         osu_year,
            'genre':        '',
            'track_number': '',
            'duration':     0,
            'artwork_url':  osu_artwork,
            'preview_url':  '',
            'external_url': osu_url,
            'bpm':          bpm,
            'mapper':       osu_creator,
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
    elif source == 'soundcloud':
        return _search_soundcloud(title, artist, limit)
    elif source == 'osu':
        return _search_osu(title, artist, limit)
    elif source == 'all':
        # Buscar en todas las fuentes
        all_results = []
        all_results.extend(_search_itunes(title, artist, limit))
        all_results.extend(_search_musicbrainz(title, artist, limit))
        all_results.extend(_search_soundcloud(title, artist, limit))
        all_results.extend(_search_osu(title, artist, limit))
        return all_results[:limit * 3]
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
