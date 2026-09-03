"""
app/saved_playlists.py
======================
Persistencia de playlists publicas (YouTube Music / Spotify) en
archivos JSON locales para tener acceso rapido sin volver a
pegar el link cada vez.

Almacenamiento:
  - Playlists de YouTube Music y Spotify (URL): se guardan en
    <proyecto>/data/saved_playlists.json (formato compacto, todas
    juntas).
  - Playlists importadas desde CSV (Exportify): cada una se guarda
    en su propio archivo JSON en <proyecto>/data/Spotify/<nombre>.json
    para que el usuario pueda identificarlas facilmente en el disco.

El indice (saved_playlists.json) siempre contiene metadatos de TODAS
las playlists (incluidas las CSV), con un campo "csv_file" que apunta
al archivo JSON individual cuando corresponde.
"""

import os
import json
import re
import uuid
from datetime import datetime
from pathlib import Path


# Ruta del archivo de datos: <proyecto>/data/saved_playlists.json
DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_FILE = DATA_DIR / 'saved_playlists.json'

# Subcarpeta para playlists importadas desde CSV
CSV_DIR = DATA_DIR / 'Spotify'


def _ensure_dir():
    """Crea la carpeta data/ si no existe."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_all():
    """Carga el JSON completo. Si no existe, devuelve estructura vacia."""
    if not DATA_FILE.exists():
        return {'playlists': []}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Si el archivo esta corrupto, empezamos de cero
        return {'playlists': []}


def _save_all(data):
    """Guarda el JSON completo."""
    _ensure_dir()
    # Escribir en un temporal y renombrar (escritura atomica)
    tmp = DATA_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)


def list_playlists(sort_by='last_accessed'):
    """
    Devuelve todas las playlists guardadas.

    Args:
        sort_by (str): criterio de ordenamiento. Opciones:
            - 'last_accessed' (default): las más recientemente accesadas primero
            - 'name': orden alfabético por nombre (A-Z)
            - 'added_at': las más recientemente agregadas primero
            - 'track_count': las que tienen más canciones primero
            - 'sort_order': orden personalizado definido por el usuario (menor a mayor)

    Returns:
        list[dict]: playlists sin el campo 'tracks' (para no pesar
                    la respuesta API). Usa get_playlist(id) para
                    obtener las canciones.
    """
    data = _load_all()
    playlists = []
    for p in data['playlists']:
        # Copiar sin tracks para aligerar
        meta = {k: v for k, v in p.items() if k != 'tracks'}
        meta['track_count'] = len(p.get('tracks', []))
        # Asegurar que todos los campos de sort existan (para evitar KeyError)
        if 'sort_order' not in meta:
            meta['sort_order'] = 0
        if 'added_at' not in meta:
            meta['added_at'] = ''
        if 'last_accessed' not in meta:
            meta['last_accessed'] = ''
        playlists.append(meta)

    # Ordenar según criterio
    if sort_by == 'name':
        playlists.sort(key=lambda x: x.get('name', '').lower())
    elif sort_by == 'added_at':
        playlists.sort(key=lambda x: x.get('added_at', ''), reverse=True)
    elif sort_by == 'track_count':
        playlists.sort(key=lambda x: x.get('track_count', 0), reverse=True)
    elif sort_by == 'sort_order':
        # Orden personalizado: por sort_order ascendente (menor primero)
        # Las que no tienen sort_order (0) van al final
        playlists.sort(key=lambda x: (x.get('sort_order', 0) == 0, x.get('sort_order', 0)))
    else:  # 'last_accessed' (default)
        playlists.sort(key=lambda x: x.get('last_accessed', ''), reverse=True)
    return playlists


def count_local_in_playlists(local_title_index):
    """
    Para cada playlist guardada, cuenta cuántas de sus canciones
    están en la biblioteca local (Mi Música).

    Args:
        local_title_index (set): conjunto de títulos normalizados de
                                  la música local. Se construye desde
                                  web_app usando build_local_playlist_index
                                  o similar.

    Returns:
        dict: { playlist_id: { 'total': int, 'downloaded': int } }
    """
    data = _load_all()
    result = {}
    for p in data['playlists']:
        tracks = p.get('tracks', [])
        total = len(tracks)
        downloaded = 0
        for t in tracks:
            title = t.get('title', '') if isinstance(t, dict) else ''
            artist = t.get('artist', '') if isinstance(t, dict) else ''
            # v3.24: probar múltiples variantes del título
            # para que "Artist - Title" coincida con "Title" y viceversa
            norm = _normalize(title)
            found = norm and norm in local_title_index
            if not found and ' - ' in title:
                # Probar partes del título dividido por " - "
                for part in title.split(' - ', 1):
                    n = _normalize(part)
                    if n and n in local_title_index:
                        found = True
                        break
            if not found and artist:
                # Probar combinaciones "title artist" y "artist title"
                norm_a = _normalize(artist)
                norm_t = _normalize(title)
                if norm_a and norm_t:
                    if f"{norm_t} {norm_a}" in local_title_index or \
                       f"{norm_a} {norm_t}" in local_title_index:
                        found = True
            if found:
                downloaded += 1
        result[p['id']] = {
            'total': total,
            'downloaded': downloaded,
        }
    return result


def _sanitize_filename(name):
    """Convierte un nombre en un nombre de archivo valido."""
    if not name:
        return 'playlist'
    # Quitar caracteres invalidos para nombres de archivo
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Limitar longitud
    return name[:80] if len(name) > 80 else name


def _save_csv_playlist_file(name, playlist_data):
    """
    Guarda una playlist CSV en su propio archivo JSON en data/Spotify/.
    Devuelve la ruta relativa del archivo creado.
    """
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_filename(name)
    file_path = CSV_DIR / f"{safe_name}.json"

    # Si ya existe, anadir sufijo numerico
    counter = 1
    while file_path.exists():
        file_path = CSV_DIR / f"{safe_name}_{counter}.json"
        counter += 1

    # Contenido del archivo: la playlist completa con tracks
    content = {
        'name': playlist_data.get('title', name),
        'uploader': playlist_data.get('uploader', 'Importado desde CSV'),
        'tracks': playlist_data.get('tracks', []),
        'track_count': len(playlist_data.get('tracks', [])),
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    # Devolver ruta relativa a data/ (para mostrar en UI)
    return file_path.name


def save_playlist(platform, url, playlist_data):
    """
    Guarda (o actualiza si ya existe la misma URL) una playlist.

    Args:
        platform      (str) : 'youtube' o 'spotify'.
        url           (str) : URL original (o 'csv://nombre' para CSV).
        playlist_data (dict): resultado de fetch_youtube_playlist()
                              o fetch_spotify_playlist(). Debe tener:
                              title, uploader, tracks.

    Returns:
        dict: la playlist guardada (con id).
    """
    data = _load_all()
    now = datetime.now().isoformat(timespec='seconds')

    # Detectar si es una playlist CSV (url empieza con csv://)
    is_csv = url.startswith('csv://')

    # Buscar si ya existe una playlist con misma plataforma+url
    existing = None
    for p in data['playlists']:
        if p['platform'] == platform and p['url'] == url:
            existing = p
            break

    if existing:
        # Actualizar en lugar de duplicar
        existing['name'] = playlist_data.get('title', existing['name'])
        existing['uploader'] = playlist_data.get('uploader', '')
        existing['tracks'] = playlist_data.get('tracks', [])
        existing['track_count'] = len(existing['tracks'])
        existing['last_accessed'] = now
        result = existing

        # Si es CSV, actualizar tambien el archivo individual
        if is_csv and existing.get('csv_file'):
            csv_path = CSV_DIR / existing['csv_file']
            if csv_path.exists():
                content = {
                    'name': existing['name'],
                    'uploader': existing['uploader'],
                    'tracks': existing['tracks'],
                    'track_count': existing['track_count'],
                }
                with open(csv_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
    else:
        csv_filename = None
        if is_csv:
            # Guardar en archivo individual en data/Spotify/
            csv_filename = _save_csv_playlist_file(
                playlist_data.get('title', url[6:]),
                playlist_data
            )

        new_pl = {
            'id': uuid.uuid4().hex[:12],
            'platform': platform,
            'name': playlist_data.get('title', 'Playlist sin titulo'),
            'uploader': playlist_data.get('uploader', ''),
            'url': url,
            'tracks': playlist_data.get('tracks', []),
            'track_count': len(playlist_data.get('tracks', [])),
            'added_at': now,
            'last_accessed': now,
        }
        if csv_filename:
            new_pl['csv_file'] = csv_filename

        data['playlists'].append(new_pl)
        result = new_pl

    _save_all(data)
    # Devolver sin tracks para aligerar
    return {k: v for k, v in result.items() if k != 'tracks'}


def get_playlist(playlist_id):
    """
    Devuelve una playlist completa (con tracks) por su ID.

    Returns:
        dict | None: playlist o None si no existe.
    """
    data = _load_all()
    for p in data['playlists']:
        if p['id'] == playlist_id:
            # Actualizar last_accessed
            p['last_accessed'] = datetime.now().isoformat(timespec='seconds')
            _save_all(data)
            return p
    return None


def delete_playlist(playlist_id):
    """
    Elimina una playlist guardada por ID.
    Si la playlist tenia un archivo CSV asociado (csv_file), tambien
    elimina ese archivo de data/Spotify/.

    Returns:
        bool: True si se elimino, False si no existia.
    """
    data = _load_all()
    playlist_to_delete = None
    for p in data['playlists']:
        if p['id'] == playlist_id:
            playlist_to_delete = p
            break

    original_len = len(data['playlists'])
    data['playlists'] = [p for p in data['playlists'] if p['id'] != playlist_id]
    if len(data['playlists']) < original_len:
        _save_all(data)
        # Si era CSV, eliminar el archivo individual
        if playlist_to_delete and playlist_to_delete.get('csv_file'):
            try:
                csv_path = CSV_DIR / playlist_to_delete['csv_file']
                if csv_path.exists():
                    csv_path.unlink()
            except OSError:
                pass  # no critico
        return True
    return False


def update_playlist(playlist_id, updates):
    """
    Actualiza campos de una playlist (por ejemplo, renombrar).
    Solo permite actualizar campos no criticos: name, sort_order.

    Args:
        playlist_id (str): ID de la playlist.
        updates (dict): campos a actualizar.

    Returns:
        dict | None: playlist actualizada o None.
    """
    data = _load_all()
    for p in data['playlists']:
        if p['id'] == playlist_id:
            if 'name' in updates:
                p['name'] = updates['name'][:200]  # limitar longitud
            # v3.17: orden personalizado
            if 'sort_order' in updates:
                try:
                    p['sort_order'] = int(updates['sort_order'])
                except (ValueError, TypeError):
                    p['sort_order'] = 0
            _save_all(data)
            return {k: v for k, v in p.items() if k != 'tracks'}
    return None


def reorder_playlists(ordered_ids):
    """
    Reordena las playlists según una lista de IDs en el orden deseado.
    Asigna sort_order secuencial (1, 2, 3, ...) a cada una.

    Args:
        ordered_ids (list[str]): IDs de playlists en el orden deseado.

    Returns:
        bool: True si se reordenó, False si hubo error.
    """
    if not ordered_ids:
        return False
    data = _load_all()
    # Construir dict para acceso rápido
    by_id = {p['id']: p for p in data['playlists']}
    # Asignar sort_order secuencial
    for i, pid in enumerate(ordered_ids, start=1):
        if pid in by_id:
            by_id[pid]['sort_order'] = i
    _save_all(data)
    return True


def refresh_playlist(playlist_id, new_data):
    """
    Refresca las canciones de una playlist guardada volviendo
    a descargarla desde la URL original.

    Args:
        playlist_id (str): ID de la playlist.
        new_data (dict): resultado fresco de fetch_*_playlist().

    Returns:
        dict | None: playlist actualizada o None.
    """
    data = _load_all()
    for p in data['playlists']:
        if p['id'] == playlist_id:
            p['name'] = new_data.get('title', p['name'])
            p['uploader'] = new_data.get('uploader', '')
            p['tracks'] = new_data.get('tracks', [])
            p['track_count'] = len(p['tracks'])
            p['last_accessed'] = datetime.now().isoformat(timespec='seconds')
            _save_all(data)
            return {k: v for k, v in p.items() if k != 'tracks'}
    return None


def build_local_playlist_index():
    """
    Construye un indice {titulo_normalizado -> [playlist_info]}
    a partir de las playlists guardadas. Esto permite a la pestana
    "Mi Musica" saber en que playlists esta cada cancion local.

    IMPORTANTE: Si una cancion aparece varias veces en la misma playlist
    (YouTube Music a veces lista el mismo video multiples veces), solo
    se cuenta una vez por playlist para evitar duplicados en la UI.

    Cada playlist_info es:
        {
            'id': 'abc123',
            'name': 'Mi playlist',
            'platform': 'youtube' | 'spotify'
        }

    Returns:
        dict: { 'nombre_normalizado': [playlist_info, ...], ... }
    """
    data = _load_all()
    index = {}
    for p in data['playlists']:
        info = {
            'id': p['id'],
            'name': p['name'],
            'platform': p['platform'],
        }
        # Trackear que canciones ya agregamos a esta playlist para
        # no duplicar (la misma cancion puede aparecer 2+ veces en
        # la misma playlist de YouTube Music)
        seen_keys_for_this_playlist = set()
        for track in p.get('tracks', []):
            # v3.24: usar variantes para que "Artist - Title" coincida con "Title"
            track_title = track.get('title', '')
            track_artist = track.get('artist', '')
            keys = set()
            keys.add(_normalize(track_title))
            # Si el título contiene " - ", también añadir las partes
            if ' - ' in track_title:
                for part in track_title.split(' - ', 1):
                    n = _normalize(part)
                    if n:
                        keys.add(n)
            # Si hay artista, añadir combinaciones
            if track_artist:
                norm_a = _normalize(track_artist)
                norm_t = _normalize(track_title)
                if norm_a and norm_t:
                    keys.add(f"{norm_t} {norm_a}".strip())
                    keys.add(f"{norm_a} {norm_t}".strip())
            for key in keys:
                if not key or key in seen_keys_for_this_playlist:
                    continue
                seen_keys_for_this_playlist.add(key)
                index.setdefault(key, []).append(info)
    return index


def _normalize(s):
    """Normaliza un string para comparacion (sin acentos, minusculas).
    v3.25: mantiene letras de todos los idiomas (cirílico, griego, etc.)
    y quita sufijo "- Topic" de YouTube Music."""
    import unicodedata
    import re
    if not s:
        return ''
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\[[^)]*\]', '', s)
    s = re.sub(r'\b(feat|ft)\b\.?', '', s)
    # v3.25: quitar "- Topic" de YT Music
    s = re.sub(r'\s*-\s*topic\s*$', '', s)
    # v3.25: mantener Unicode letters
    s = re.sub(r'[^\w\s]', ' ', s)
    s = s.replace('_', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s
