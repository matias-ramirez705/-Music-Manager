"""
app/m3u_generator.py (v3.22)
============================
Genera y edita archivos M3U para el Hiby R1 (y otros DAPs compatibles).

Formato M3U del Hiby R1:
- Cabecera: #EXTM3U
- Líneas #EXTINF:duracion,Titulo - Artista (opcional pero recomendado)
- Rutas: RELATIVAS con ../Musica/... (el M3U está en /playlist_data/ y la música en /Musica/)
- Codificación: UTF-8
- Ubicación: /playlist_data/ en la raíz de la SD del Hiby

Estructura de la SD del Hiby:
  /Musica/                  <- música
    /Artista/Album/cancion.flac
  /playlist_data/           <- playlists M3U
    mi_playlist.m3u
    otra_playlist.m3u

Las rutas en el M3U son relativas desde /playlist_data/:
  ../Musica/Artista/Album/cancion.flac
  (subir un nivel desde playlist_data → raíz, bajar a Musica → archivo)

El Hiby muestra el nombre del archivo .m3u como nombre de playlist.
"""

import os
import re
from pathlib import Path
from datetime import datetime


# Normalización de títulos (igual que saved_playlists.py para coincidir)
def _normalize(s):
    """Normaliza un string para comparación (sin acentos, lowercase, etc.)."""
    import unicodedata
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
# Generación de M3U
# ------------------------------------------------------------------

def generate_m3u(playlist_tracks, hiby_files, hiby_music_folder='Musica'):
    """
    Genera el contenido de un archivo M3U a partir de las canciones
    de una playlist guardada, cruzando con los archivos del Hiby.

    Args:
        playlist_tracks (list[dict]): canciones de la playlist guardada.
            Cada track tiene: title, artist, duration, url, isrc.
        hiby_files (list[dict]): archivos escaneados del Hiby (resultado
            de scanner.scan_folder). Cada archivo tiene: path, name, ext,
            size, parent, y metadata enriquecida (artist, duration, etc.)
        hiby_music_folder (str): nombre de la carpeta de música en el Hiby
            (default: 'Musica'). Las rutas relativas serán ../Musica/...

    Returns:
        dict con:
            - 'm3u_content': str (contenido del archivo M3U)
            - 'matched': int (cuántas canciones se encontraron en el Hiby)
            - 'missing': int (cuántas no se encontraron)
            - 'total': int (total de canciones en la playlist)
            - 'missing_tracks': list[dict] (canciones que faltan)
    """
    # Construir índice de archivos del Hiby por título normalizado
    hiby_by_title = {}
    for f in hiby_files:
        # El 'name' ya viene enriquecido con metadata (title) por /api/scan
        title_norm = _normalize(f.get('name', ''))
        if title_norm:
            hiby_by_title.setdefault(title_norm, []).append(f)

    m3u_lines = ['#EXTM3U']
    matched = 0
    missing_tracks = []

    for track in playlist_tracks:
        title = track.get('title', '')
        artist = track.get('artist', '')
        duration = track.get('duration', 0) or 0

        title_norm = _normalize(title)
        if not title_norm:
            continue

        # Buscar en el Hiby
        hiby_match = hiby_by_title.get(title_norm, [])

        if hiby_match:
            # Tomar el primer match
            hiby_file = hiby_match[0]
            # Construir ruta relativa: ../Musica/ruta/del/archivo.ext
            # El path del Hiby es absoluto (ej: G:\Musica\Artista\Album\cancion.flac)
            # Necesitamos extraer la parte relativa a la raíz del Hiby
            hiby_path = hiby_file.get('path', '')
            # La carpeta de música está en la raíz, así que la ruta relativa
            # es todo lo que viene después de la carpeta hiby_music_folder
            rel_path = _extract_relative_path(hiby_path, hiby_music_folder)
            if rel_path:
                # Formato M3U: ../Musica/ruta/del/archivo.ext (con forward slashes)
                # El Hiby usa Linux, así que forward slashes funcionan
                m3u_path = f"../{hiby_music_folder}/{rel_path}"
                # EXTINF: duración en segundos, Título - Artista
                extinf = f"#EXTINF:{int(duration)},{title}"
                if artist:
                    extinf += f" - {artist}"
                m3u_lines.append(extinf)
                m3u_lines.append(m3u_path)
                matched += 1
        else:
            missing_tracks.append({
                'title': title,
                'artist': artist,
                'duration': duration,
                'url': track.get('url', ''),
            })

    m3u_content = '\n'.join(m3u_lines) + '\n'
    total = len(playlist_tracks)

    return {
        'm3u_content': m3u_content,
        'matched': matched,
        'missing': len(missing_tracks),
        'total': total,
        'missing_tracks': missing_tracks,
    }


def _extract_relative_path(full_path, music_folder='Musica'):
    """
    Extrae la ruta relativa a la carpeta de música desde una ruta absoluta.

    Ejemplo:
        full_path = 'G:\\Musica\\Artista\\Album\\cancion.flac'
        music_folder = 'Musica'
        → 'Artista/Album/cancion.flac'

    Funciona con backslashes (Windows) y forward slashes (Linux/Mac).
    """
    if not full_path:
        return ''

    # Normalizar separadores a forward slash
    normalized = full_path.replace('\\', '/')

    # Buscar la carpeta de música en la ruta
    # Puede ser /Musica/ o \Musica\
    patterns = [
        f'/{music_folder}/',
        f'\\{music_folder}\\',
        f'/{music_folder}',
        f'\\{music_folder}',
    ]

    for pattern in patterns:
        idx = normalized.lower().find(pattern.lower())
        if idx >= 0:
            # Todo lo que viene después de la carpeta de música
            rel = normalized[idx + len(pattern):]
            # Limpiar backslashes dobles o slashes mixtos
            rel = rel.replace('\\', '/')
            # Quitar slash inicial si lo hay
            rel = rel.lstrip('/')
            return rel

    # Si no encontramos la carpeta de música, devolver solo el nombre del archivo
    return os.path.basename(full_path).replace('\\', '/')


# ------------------------------------------------------------------
# Edición de M3U existentes
# ------------------------------------------------------------------

def parse_m3u(m3u_content):
    """
    Parsea un archivo M3U y devuelve una lista de tracks.

    Args:
        m3u_content (str): contenido del archivo M3U.

    Returns:
        list[dict]: cada track tiene: path, title, artist, duration, extinf_line.
    """
    tracks = []
    lines = m3u_content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('#EXTM3U'):
            i += 1
            continue

        # Si es #EXTINF, leer la siguiente línea como path
        if line.startswith('#EXTINF:'):
            # Formato: #EXTINF:duracion,Titulo - Artista
            extinf = line
            duration = 0
            title = ''
            artist = ''
            # Extraer duración y título
            match = re.match(r'#EXTINF:(-?\d+),(.*)', line)
            if match:
                duration_str = match.group(1)
                try:
                    duration = int(duration_str)
                    if duration < 0:
                        duration = 0
                except ValueError:
                    duration = 0
                title_artist = match.group(2).strip()
                # Separar "Titulo - Artista" si hay guión
                if ' - ' in title_artist:
                    parts = title_artist.rsplit(' - ', 1)
                    title = parts[0].strip()
                    artist = parts[1].strip()
                else:
                    title = title_artist

            # La siguiente línea es el path
            i += 1
            if i < len(lines):
                path = lines[i].strip()
                if path and not path.startswith('#'):
                    tracks.append({
                        'path': path,
                        'title': title,
                        'artist': artist,
                        'duration': duration,
                        'extinf_line': extinf,
                    })
        elif not line.startswith('#'):
            # Línea de path sin EXTINF previo
            tracks.append({
                'path': line,
                'title': '',
                'artist': '',
                'duration': 0,
                'extinf_line': '',
            })
        i += 1

    return tracks


def save_m3u(m3u_content, file_path):
    """
    Guarda el contenido M3U en un archivo.

    Args:
        m3u_content (str): contenido del M3U.
        file_path (str): ruta donde guardar.

    Returns:
        dict con 'success' y 'error'.
    """
    try:
        # Asegurar que el directorio existe
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        # Guardar en UTF-8
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        return {'success': True, 'file_path': file_path, 'error': None}
    except Exception as e:
        return {'success': False, 'file_path': file_path, 'error': str(e)}


def rebuild_m3u_from_tracks(tracks):
    """
    Reconstruye el contenido M3U a partir de una lista de tracks.
    Útil para editar un M3U (añadir/quitar canciones) y guardarlo.

    Args:
        tracks (list[dict]): cada track tiene: path, title, artist, duration.

    Returns:
        str: contenido M3U listo para guardar.
    """
    lines = ['#EXTM3U']
    for t in tracks:
        path = t.get('path', '')
        if not path:
            continue
        title = t.get('title', '')
        artist = t.get('artist', '')
        duration = t.get('duration', 0) or 0
        # EXTINF
        extinf = f"#EXTINF:{int(duration)},{title}"
        if artist:
            extinf += f" - {artist}"
        lines.append(extinf)
        lines.append(path)
    return '\n'.join(lines) + '\n'


def list_m3u_files(folder_path):
    """
    Lista todos los archivos .m3u y .m3u8 en una carpeta.

    Args:
        folder_path (str): ruta de la carpeta (ej: G:\playlist_data).

    Returns:
        list[dict]: cada item tiene: filename, path, size, track_count, modified.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return []

    result = []
    try:
        for entry in sorted(os.listdir(folder_path)):
            if entry.lower().endswith(('.m3u', '.m3u8')):
                full_path = os.path.join(folder_path, entry)
                try:
                    size = os.path.getsize(full_path)
                    content = Path(full_path).read_text(encoding='utf-8', errors='replace')
                    tracks = parse_m3u(content)
                    mod_time = os.path.getmtime(full_path)
                    mod_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
                    result.append({
                        'filename': entry,
                        'path': full_path,
                        'size': size,
                        'track_count': len(tracks),
                        'modified': mod_str,
                    })
                except Exception:
                    result.append({
                        'filename': entry,
                        'path': full_path,
                        'size': 0,
                        'track_count': 0,
                        'modified': '',
                    })
    except Exception:
        pass
    return result


def read_m3u_file(file_path):
    """
    Lee un archivo M3U y devuelve su contenido parseado.

    Returns:
        dict con 'content', 'tracks', 'filename', 'error'.
    """
    try:
        content = Path(file_path).read_text(encoding='utf-8', errors='replace')
        tracks = parse_m3u(content)
        filename = os.path.basename(file_path)
        return {
            'content': content,
            'tracks': tracks,
            'filename': filename,
            'path': file_path,
            'error': None,
        }
    except Exception as e:
        return {
            'content': '',
            'tracks': [],
            'filename': os.path.basename(file_path),
            'path': file_path,
            'error': str(e),
        }
