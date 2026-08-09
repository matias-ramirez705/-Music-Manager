"""
app/auto_metadata.py
====================
Busca metadata de canciones en internet para rellenar
automaticamente los tags de archivos locales.

Fuente usada: iTunes Search API
  - URL: https://itunes.apple.com/search
  - Documentacion: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
  - GRATUITA, sin registro, sin API key.
  - Buenisima cobertura de musica comercial (incluye muchos
    artistas latinos e independientes).
  - Devuelve: titulo, artista, album, año, genero, caratula,
    duracion, pista numero.

Como se usa:
  1. Llama a search_track(titulo, artista) -> lista de coincidencias
  2. Toma la primera (o el usuario elige)
  3. Rellena los campos del archivo local con write_metadata()
"""

import requests


# Endpoint publico de iTunes Search API
ITUNES_ENDPOINT = "https://itunes.apple.com/search"


def search_track(title, artist='', limit=5):
    """
    Busca una cancion en iTunes por titulo (y opcionalmente artista).

    Args:
        title  (str): titulo de la cancion.
        artist (str): artista (opcional, mejora precision).
        limit  (int): maximo de resultados.

    Returns:
        list[dict]: cada elemento tiene:
            'title', 'artist', 'album', 'year', 'genre',
            'track_number', 'duration', 'artwork_url', 'preview_url',
            'itunes_url', 'country'
    """
    # Construir query: "titulo artista" si hay artista, sino solo titulo
    query = f"{title} {artist}".strip()

    params = {
        'term': query,
        'media': 'music',
        'entity': 'song',
        'limit': limit,
    }

    try:
        # No necesita cabeceras especiales ni autenticacion
        resp = requests.get(ITUNES_ENDPOINT, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return []
    except ValueError:
        # JSON invalido
        return []

    results = []
    for item in data.get('results', []):
        results.append({
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
            'itunes_url':   item.get('trackViewUrl', ''),
            'country':      item.get('country', ''),
        })

    return results


def best_match(results, target_title='', target_artist=''):
    """
    Heuristica simple: devuelve el resultado cuyo titulo y artista
    coinciden mas cercanamente con los buscados.

    Si no hay coincidencia clara, devuelve el primer resultado.

    Args:
        results        (list[dict]): salida de search_track().
        target_title   (str): titulo original del archivo.
        target_artist  (str): artista original del archivo.

    Returns:
        dict | None: el mejor resultado, o None si la lista esta vacia.
    """
    if not results:
        return None

    def normalize(s):
        return (s or '').lower().strip()

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
        if score > best_score:
            best_score = score
            best = r

    return best or results[0]
