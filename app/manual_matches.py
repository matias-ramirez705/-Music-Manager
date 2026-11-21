"""
app/manual_matches.py (v3.28)
=============================
Persistencia de matches manuales entre tracks de playlists y archivos locales.

Cuando la comparación automática no detecta que una canción está en Mi Música
(por nombres muy distintos), el usuario puede marcarla manualmente como
"descargada" desde el modal de playlist.

Almacenamiento: data/manual_matches.json

Estructura:
{
    "matches": [
        {
            "playlist_id": "abc123",
            "track_title": "Metal: Hellsinger — Dissolution ft. ...",
            "track_artist": "Two Feathers",
            "local_name": "Dissolution",
            "local_artist": "Two Feathers",
            "local_path": "C:\\Music\\Dissolution - Two Feathers.flac",
            "created_at": "2026-09-02T22:00:00"
        },
        ...
    ]
}

Para buscar: se indexa por (playlist_id + track_title normalizado).
"""

import json
from pathlib import Path
from datetime import datetime


DATA_DIR = Path(__file__).parent.parent / 'data'
MATCHES_FILE = DATA_DIR / 'manual_matches.json'


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_all():
    if not MATCHES_FILE.exists():
        return {'matches': []}
    try:
        with open(MATCHES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'matches' not in data:
            data = {'matches': []}
        return data
    except (json.JSONDecodeError, OSError):
        return {'matches': []}


def _save_all(data):
    _ensure_dir()
    tmp = MATCHES_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(MATCHES_FILE)


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
    s = re.sub(r'\s*-\s*topic\s*$', '', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = s.replace('_', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def add_manual_match(playlist_id, track_title, track_artist='',
                     local_name='', local_artist='', local_path=''):
    """
    Marca manualmente que un track de una playlist está descargado
    en Mi Música, aunque la comparación automática no lo detecte.

    Args:
        playlist_id: ID de la playlist.
        track_title: título del track en la playlist.
        track_artist: artista del track en la playlist.
        local_name: nombre del archivo local (opcional, informativo).
        local_artist: artista del archivo local (opcional).
        local_path: ruta del archivo local (opcional).
    """
    data = _load_all()
    # Verificar si ya existe (mismo playlist_id + track_title normalizado)
    title_norm = _normalize(track_title)
    for m in data['matches']:
        if (m.get('playlist_id') == playlist_id and
                _normalize(m.get('track_title', '')) == title_norm):
            # Actualizar
            m['track_artist'] = track_artist
            m['local_name'] = local_name
            m['local_artist'] = local_artist
            m['local_path'] = local_path
            m['updated_at'] = datetime.now().isoformat(timespec='seconds')
            _save_all(data)
            return m

    new_match = {
        'playlist_id': playlist_id,
        'track_title': track_title,
        'track_artist': track_artist,
        'local_name': local_name,
        'local_artist': local_artist,
        'local_path': local_path,
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    data['matches'].append(new_match)
    _save_all(data)
    return new_match


def remove_manual_match(playlist_id, track_title):
    """
    Quita un match manual (desmarcar como descargada).

    Args:
        playlist_id: ID de la playlist.
        track_title: título del track.

    Returns:
        bool: True si se eliminó, False si no existía.
    """
    data = _load_all()
    title_norm = _normalize(track_title)
    before = len(data['matches'])
    data['matches'] = [
        m for m in data['matches']
        if not (m.get('playlist_id') == playlist_id and
                _normalize(m.get('track_title', '')) == title_norm)
    ]
    if len(data['matches']) < before:
        _save_all(data)
        return True
    return False


def get_manual_matches_for_playlist(playlist_id):
    """
    Devuelve todos los matches manuales para una playlist específica.

    Returns:
        dict: { track_title_normalized: match_info }
    """
    data = _load_all()
    result = {}
    for m in data['matches']:
        if m.get('playlist_id') == playlist_id:
            key = _normalize(m.get('track_title', ''))
            if key:
                result[key] = m
    return result


def get_all_manual_matches():
    """
    Devuelve todos los matches manuales (para integrar con count_local_in_playlists).

    Returns:
        dict: { (playlist_id, track_title_normalized): match_info }
    """
    data = _load_all()
    result = {}
    for m in data['matches']:
        pid = m.get('playlist_id', '')
        key = _normalize(m.get('track_title', ''))
        if pid and key:
            result[(pid, key)] = m
    return result


def is_manually_matched(playlist_id, track_title):
    """
    Verifica si un track está marcado manualmente como descargado.

    Returns:
        bool
    """
    data = _load_all()
    title_norm = _normalize(track_title)
    for m in data['matches']:
        if (m.get('playlist_id') == playlist_id and
                _normalize(m.get('track_title', '')) == title_norm):
            return True
    return False
