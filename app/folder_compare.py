"""
app/folder_compare.py
=====================
Compara los archivos de audio de dos carpetas distintas.

Caso de uso típico: comparar la música del PC con la del DAP (Hiby R1)
para detectar qué canciones faltan en cada lado.

Función principal:
    compare_folders(folder_a, folder_b) -> dict con:
      - 'a_only':  archivos presentes solo en A (faltan en B)
      - 'b_only':  archivos presentes solo en B (faltan en A)
      - 'common':  archivos presentes en ambos (coincidencia por título+artista)
      - 'stats':   totales

Criterio de coincidencia:
    Normaliza título (sin acentos, lowercase, sin paréntesis, sin
    "feat"/"ft") y compara. Si dos archivos tienen el mismo título
    normalizado, se consideran la "misma canción" aunque estén en
    formatos distintos (mp3 vs flac) o con nombres ligeramente
    distintos en disco.
"""

import os
import unicodedata
import re
from pathlib import Path

# Reutilizamos el scanner para no duplicar la lógica de extensión
from scanner import scan_folder, AUDIO_EXTENSIONS
from metadata_reader import read_metadata
from audio_quality import format_duration
from scanner import human_size


def _normalize(s):
    """Normaliza un string para comparación (sin acentos, lowercase, etc.)."""
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


def _enrich_file(f):
    """
    Toma un archivo del scanner y le añade metadata + campos
    útiles para la comparación.
    """
    meta = read_metadata(f['path'])
    title = meta.get('title') or f['name']
    artist = meta.get('artist', '')
    duration = meta.get('duration', 0) or 0
    return {
        'path': f['path'],
        'filename': Path(f['path']).name,
        'name': title,
        'artist': artist,
        'album': meta.get('album', ''),
        'ext': f['ext'].lstrip('.'),
        'size': f['size'],
        'size_str': human_size(f['size']),
        'duration': duration,
        'duration_str': format_duration(duration) if duration else '—',
        'title_norm': _normalize(title),
        'artist_norm': _normalize(artist),
    }


def compare_folders(folder_a, folder_b):
    """
    Compara archivos de audio de dos carpetas.

    Args:
        folder_a (str): ruta de la carpeta A (ej: música del PC)
        folder_b (str): ruta de la carpeta B (ej: DAP Hiby R1)

    Returns:
        dict con:
            'a_files':    [lista enriquecida de archivos en A]
            'b_files':    [lista enriquecida de archivos en B]
            'a_only':     [archivos presentes solo en A]
            'b_only':     [archivos presentes solo en B]
            'common':     [archivos coincidentes (con info de ambos lados)]
            'stats': {
                'a_total': int,
                'b_total': int,
                'a_only_count': int,
                'b_only_count': int,
                'common_count': int,
            }
            'folder_a': str,
            'folder_b': str,
    """
    # Validar carpetas
    if not folder_a or not os.path.isdir(folder_a):
        return {'error': f'Carpeta A no existe o no es válida: {folder_a}'}
    if not folder_b or not os.path.isdir(folder_b):
        return {'error': f'Carpeta B no existe o no es válida: {folder_b}'}

    # Escanear ambas carpetas
    raw_a = scan_folder(folder_a)
    raw_b = scan_folder(folder_b)

    # Enriquecer con metadata
    a_files = [_enrich_file(f) for f in raw_a]
    b_files = [_enrich_file(f) for f in raw_b]

    # Construir índices por título normalizado
    a_by_title = {}
    for f in a_files:
        if f['title_norm']:
            a_by_title.setdefault(f['title_norm'], []).append(f)
    b_by_title = {}
    for f in b_files:
        if f['title_norm']:
            b_by_title.setdefault(f['title_norm'], []).append(f)

    # Encontrar coincidencias (títulos presentes en ambos)
    common_titles = set(a_by_title.keys()) & set(b_by_title.keys())
    common = []
    for title in common_titles:
        a_match = a_by_title[title][0]  # primer match en A
        b_match = b_by_title[title][0]  # primer match en B
        common.append({
            'title': a_match['name'],
            'artist': a_match['artist'],
            'a': a_match,
            'b': b_match,
        })

    # Solo en A: títulos que están en A pero no en B
    a_only_titles = set(a_by_title.keys()) - set(b_by_title.keys())
    a_only = []
    for title in a_only_titles:
        for f in a_by_title[title]:
            a_only.append(f)
    # También incluir archivos sin título (no se pudieron normalizar)
    for f in a_files:
        if not f['title_norm']:
            a_only.append(f)

    # Solo en B: títulos que están en B pero no en A
    b_only_titles = set(b_by_title.keys()) - set(a_by_title.keys())
    b_only = []
    for title in b_only_titles:
        for f in b_by_title[title]:
            b_only.append(f)
    for f in b_files:
        if not f['title_norm']:
            b_only.append(f)

    return {
        'a_files': a_files,
        'b_files': b_files,
        'a_only': a_only,
        'b_only': b_only,
        'common': common,
        'stats': {
            'a_total': len(a_files),
            'b_total': len(b_files),
            'a_only_count': len(a_only),
            'b_only_count': len(b_only),
            'common_count': len(common),
        },
        'folder_a': folder_a,
        'folder_b': folder_b,
    }
