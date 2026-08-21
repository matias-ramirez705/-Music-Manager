"""
app/deleted_songs.py
====================
Persistencia de canciones eliminadas del disco.

Cuando el usuario borra un archivo de audio de su biblioteca local,
Music Manager lo detecta en el siguiente escaneo y lo registra aquí
para que:
  - Aparezca en la pestaña "Eliminados" con su metadata previa
    (nombre, artista, formato, playlists en las que estaba).
  - No aparezca como "faltante" en la pestaña Comparar con Playlist
    (porque el usuario ya decidió borrarlo a propósito).

Almacenamiento:
    <proyecto>/data/deleted_songs.json

Estructura del JSON:
    {
        "songs": [
            {
                "id": "uuid",
                "path": "C:\\Users\\...\\cancion.mp3",
                "name": "Cancion",
                "artist": "Artista",
                "album": "Album",
                "ext": "mp3",
                "size": 5000000,
                "size_str": "4.8 MB",
                "playlists": [{"id": "...", "name": "...", "platform": "..."}],
                "comment": "No me gustó" | "Repetida" | "comentario libre",
                "deleted_at": "2024-08-14T10:30:00",
                "detected_at_scan": "C:\\Users\\...\\Music",
                "duration": 240,
                "duration_str": "4:00"
            },
            ...
        ]
    }
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path


# Ruta del archivo de datos: <proyecto>/data/deleted_songs.json
DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_FILE = DATA_DIR / 'deleted_songs.json'


def _ensure_dir():
    """Crea la carpeta data/ si no existe."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_all():
    """Carga el JSON completo. Si no existe, devuelve estructura vacía."""
    if not DATA_FILE.exists():
        return {'songs': []}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'songs' not in data:
            data = {'songs': []}
        return data
    except (json.JSONDecodeError, OSError):
        return {'songs': []}


def _save_all(data):
    """Guarda el JSON completo (escritura atómica via tmp + rename)."""
    _ensure_dir()
    tmp = DATA_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)


def ensure_file():
    """Crea la carpeta data/ y el archivo deleted_songs.json si no existen."""
    _ensure_dir()
    if not DATA_FILE.exists():
        _save_all({'songs': []})


# ------------------------------------------------------------------
# Normalización (igual que saved_playlists.py para que las claves
# coincidan con las que usa build_local_playlist_index)
# ------------------------------------------------------------------
def _normalize(s):
    import unicodedata
    import re
    if not s:
        return ''
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\[[^]]*\]', '', s)
    s = re.sub(r'\b(feat|ft)\b\.?', '', s)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------
def list_deleted_songs():
    """
    Devuelve la lista de canciones eliminadas, ordenada por fecha
    de detección (más reciente primero).

    Returns:
        list[dict]: cada dict tiene id, path, name, artist, album,
                    ext, size_str, playlists, comment, deleted_at, etc.
    """
    data = _load_all()
    songs = data.get('songs', [])
    # Ordenar por deleted_at descendente (más nuevo primero)
    songs.sort(key=lambda s: s.get('deleted_at', ''), reverse=True)
    return songs


def add_deleted_song(song_data):
    """
    Agrega una canción a la lista de eliminados.

    Args:
        song_data (dict): debe contener al menos 'path', 'name', 'artist',
                          'ext'. Opcional: 'album', 'size', 'size_str',
                          'duration', 'duration_str', 'playlists', 'comment'.

    Returns:
        dict: la canción guardada (con id y deleted_at).
    """
    data = _load_all()

    # Si ya existe una canción con el mismo path, no la duplicamos
    existing = next((s for s in data['songs']
                     if s.get('path') == song_data.get('path')), None)
    if existing:
        # Actualizamos metadata preservando el comment previo
        existing.update({
            'name': song_data.get('name', existing.get('name', '')),
            'artist': song_data.get('artist', existing.get('artist', '')),
            'album': song_data.get('album', existing.get('album', '')),
            'ext': song_data.get('ext', existing.get('ext', '')),
            'size': song_data.get('size', existing.get('size', 0)),
            'size_str': song_data.get('size_str', existing.get('size_str', '')),
            'duration': song_data.get('duration', existing.get('duration', 0)),
            'duration_str': song_data.get('duration_str',
                                          existing.get('duration_str', '')),
            'playlists': song_data.get('playlists',
                                       existing.get('playlists', [])),
            'deleted_at': datetime.now().isoformat(timespec='seconds'),
        })
        _save_all(data)
        return existing

    new_song = {
        'id': str(uuid.uuid4()),
        'path': song_data.get('path', ''),
        'name': song_data.get('name', ''),
        'artist': song_data.get('artist', ''),
        'album': song_data.get('album', ''),
        'ext': song_data.get('ext', ''),
        'size': song_data.get('size', 0),
        'size_str': song_data.get('size_str', ''),
        'duration': song_data.get('duration', 0),
        'duration_str': song_data.get('duration_str', ''),
        'playlists': song_data.get('playlists', []),
        'comment': song_data.get('comment', ''),
        'deleted_at': datetime.now().isoformat(timespec='seconds'),
        'detected_at_scan': song_data.get('detected_at_scan', ''),
    }
    data['songs'].append(new_song)
    _save_all(data)
    return new_song


def update_comment(song_id, comment):
    """
    Actualiza el comentario de una canción eliminada.

    Args:
        song_id (str): ID de la canción.
        comment (str): nuevo comentario (puede ser '', 'No me gustó',
                       'Repetida', o texto libre).

    Returns:
        dict|None: la canción actualizada, o None si no se encontró.
    """
    data = _load_all()
    for s in data['songs']:
        if s.get('id') == song_id:
            s['comment'] = comment or ''
            _save_all(data)
            return s
    return None


def remove_deleted_song(song_id):
    """
    Elimina una canción de la lista de eliminados (el usuario ya no
    quiere verla en la pestaña).

    Args:
        song_id (str): ID de la canción a remover.

    Returns:
        bool: True si se eliminó, False si no se encontró.
    """
    data = _load_all()
    before = len(data['songs'])
    data['songs'] = [s for s in data['songs'] if s.get('id') != song_id]
    if len(data['songs']) < before:
        _save_all(data)
        return True
    return False


def remove_deleted_by_title(title, artist=''):
    """
    Elimina de la lista de eliminados cualquier canción cuyo título
    normalizado coincida con el dado (y opcionalmente el artista).

    Caso de uso: cuando el usuario renombra un archivo, el archivo
    "viejo" técnicamente desaparece del disco y aparece en Eliminados
    al re-escanear. Pero como el usuario lo renombró a propósito (no
    lo borró), no debería estar en Eliminados. Esta función limpia
    esa entrada espuria.

    Args:
        title (str): título de la canción (se normaliza internamente).
        artist (str): artista (opcional, para no borrar canciones
                      homónimas de otros artistas).

    Returns:
        int: cuántas entradas se eliminaron.
    """
    if not title:
        return 0
    title_norm = _normalize(title)
    artist_norm = _normalize(artist) if artist else ''

    data = _load_all()
    before = len(data['songs'])
    kept = []
    for s in data['songs']:
        s_title_norm = _normalize(s.get('name', ''))
        s_artist_norm = _normalize(s.get('artist', ''))
        # Coincide si el título normalizado es igual
        title_match = (title_norm == s_title_norm)
        # Y si dimos artista, que también coincida (o contenga)
        artist_match = True
        if artist_norm:
            if not (s_artist_norm == artist_norm
                    or artist_norm in s_artist_norm
                    or s_artist_norm in artist_norm):
                artist_match = False
        if title_match and artist_match:
            # Esta entrada coincide → la eliminamos de la lista
            continue
        kept.append(s)
    data['songs'] = kept
    removed = before - len(kept)
    if removed > 0:
        _save_all(data)
    return removed


def clear_all_deleted():
    """Vacía la lista de eliminados. Devuelve cuántos se eliminaron."""
    data = _load_all()
    count = len(data['songs'])
    data['songs'] = []
    _save_all(data)
    return count


def detect_deleted_from_scan(current_files, scan_folder=''):
    """
    Compara la lista de archivos del escaneo actual con la lista
    de canciones conocidas del escaneo anterior, y agrega a la lista
    de eliminados las que ya no están presentes.

    IMPORTANTE: Esta función NO se llama automáticamente al escanear.
    La invoca el endpoint /api/scan solo cuando hay un escaneo previo
    (LAST_SCAN['files'] no vacío) para detectar qué se borró entre
    escaneos.

    Args:
        current_files (list[dict]): lista de archivos del escaneo actual
                                     (con campo 'path').
        scan_folder (str): carpeta escaneada (para metadata informativa).

    Returns:
        list[dict]: las canciones que se detectaron como eliminadas y
                    se agregaron a la lista (vacía si no hubo cambios).
    """
    if not current_files:
        # Si el nuevo escaneo está vacío, no marcamos todo como eliminado
        # porque puede ser que el usuario cambió de carpeta. Solo detectamos
        # eliminaciones cuando hay un escaneo previo con archivos y un
        # escaneo nuevo también con archivos (caso normal: borró algunos).
        return []

    current_paths = {f['path'] for f in current_files}

    # Importación diferida para evitar circular import
    # (web_app importa deleted_songs y viceversa sería problemático)
    deleted = []
    for prev_file in _get_previous_scan_files():
        if prev_file['path'] not in current_paths:
            # Esta canción estaba antes y ya no está -> eliminada
            song_data = {
                'path': prev_file['path'],
                'name': prev_file.get('name', ''),
                'artist': prev_file.get('artist', ''),
                'album': prev_file.get('album', ''),
                'ext': prev_file.get('ext', ''),
                'size': prev_file.get('size', 0),
                'size_str': prev_file.get('size_str', ''),
                'duration': prev_file.get('duration', 0),
                'duration_str': prev_file.get('duration_str', ''),
                'playlists': prev_file.get('playlists', []),
                'comment': '',
                'detected_at_scan': scan_folder or '',
            }
            added = add_deleted_song(song_data)
            deleted.append(added)

    return deleted


def _get_previous_scan_files():
    """
    Obtiene los archivos del escaneo anterior desde el estado global
    de web_app. Se hace de forma diferida para evitar imports circulares.

    Returns:
        list[dict]: lista de archivos del LAST_SCAN previo, o [] si no
                   hay escaneo previo.
    """
    try:
        # Importar el estado global de web_app
        import sys
        # Buscar el módulo web_app en sys.modules
        web_app_mod = sys.modules.get('web_app')
        if web_app_mod is None:
            return []
        # LAST_SCAN es un dict en el módulo
        last_scan = getattr(web_app_mod, 'LAST_SCAN', None)
        if last_scan is None:
            return []
        return list(last_scan.get('files', []))
    except Exception:
        return []


def build_deleted_index():
    """
    Construye un índice {titulo_normalizado -> [canción_eliminada]}
    para que la pestaña Comparar con Playlist pueda excluir las
    canciones eliminadas de la lista de faltantes.

    Returns:
        dict: {'titulo_normalizado': [canción_eliminada, ...], ...}
    """
    data = _load_all()
    index = {}
    for s in data['songs']:
        key = _normalize(s.get('name', ''))
        if not key:
            continue
        index.setdefault(key, []).append(s)
    return index


def is_song_deleted(title, artist=''):
    """
    Verifica si una canción (por título normalizado) está en la lista
    de eliminados. Si se pasa artista, se chequea también que coincida
    (para no excluir falsos positivos cuando hay canciones con el
    mismo título de artistas distintos).

    Args:
        title (str): título de la canción.
        artist (str): artista (opcional).

    Returns:
        bool: True si está en eliminados, False si no.
    """
    index = build_deleted_index()
    key = _normalize(title)
    if not key:
        return False
    candidates = index.get(key, [])
    if not candidates:
        return False
    if not artist:
        # Si no hay artista para comparar, basta con el título
        return True
    # Normalizar artista y comparar
    a_norm = _normalize(artist)
    for c in candidates:
        c_artist_norm = _normalize(c.get('artist', ''))
        # Coincidencia si uno contiene al otro (igual que en api/compare)
        if a_norm and c_artist_norm and (
            a_norm in c_artist_norm or c_artist_norm in a_norm
        ):
            return True
    # Si hubo candidatos pero ninguno coincidió en artista, no la consideramos eliminada
    return False
