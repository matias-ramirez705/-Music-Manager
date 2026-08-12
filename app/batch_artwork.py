"""
app/batch_artwork.py
====================
Operaciones masivas sobre caratulas de archivos de audio:
  - detect_missing_artwork(files): lista archivos sin caratula
  - batch_resize(files, max_size, fmt): redimensiona todas las caratulas
  - batch_download_artwork(files): busca y descarga caratulas faltantes
    desde iTunes Search API
"""

import os
from pathlib import Path
from artwork import extract_artwork, save_artwork, resize_image, download_image
from auto_metadata import search_track, best_match
from audio_quality import build_quality_summary


def detect_missing_artwork(files):
    """
    Recorre la lista de archivos y devuelve los que NO tienen caratula.

    Args:
        files (list[dict]): lista de archivos del escaneo (LAST_SCAN['files']).

    Returns:
        dict con:
          - 'missing': lista de archivos sin caratula
          - 'has_artwork': lista de archivos con caratula
          - 'total': total de archivos
          - 'missing_count': cuantos faltan
          - 'has_count': cuantos tienen
    """
    missing = []
    has_artwork = []

    for f in files:
        path = f.get('path', '')
        if not path or not os.path.exists(path):
            continue
        try:
            artwork = extract_artwork(path)
        except Exception as e:
            print(f"Error extrayendo caratula de {path}: {e}")
            artwork = None
        if artwork and artwork.get('data'):
            has_artwork.append({
                **f,
                'artwork_size_kb': artwork.get('size_kb', 0),
                'artwork_dimensions': f"{artwork.get('width', '?')}x{artwork.get('height', '?')}",
                'artwork_mime': artwork.get('mime', ''),
                'artwork_ext': _mime_to_ext(artwork.get('mime', '')),
            })
        else:
            missing.append(f)

    return {
        'missing': missing,
        'has_artwork': has_artwork,
        'total': len(files),
        'missing_count': len(missing),
        'has_count': len(has_artwork),
    }


def _mime_to_ext(mime):
    """Convierte MIME type a extension de archivo."""
    mapping = {
        'image/jpeg': 'JPEG',
        'image/png': 'PNG',
        'image/webp': 'WEBP',
        'image/gif': 'GIF',
    }
    return mapping.get(mime, mime or '—')


def batch_resize(files, max_size=600, fmt='JPEG', quality=85):
    """
    Redimensiona las caratulas de todos los archivos que tienen una.

    Args:
        files (list[dict]): lista de archivos del escaneo.
        max_size (int): tamano maximo en pixels.
        fmt (str): formato de salida ('JPEG', 'PNG', 'WEBP').
        quality (int): calidad (1-100).

    Returns:
        dict con:
          - 'success_count': cuantos se redimensionaron
          - 'error_count': cuantos fallaron
          - 'skipped_count': cuantos no tenian caratula
          - 'errors': lista de errores
    """
    success = 0
    errors = []
    skipped = 0

    for f in files:
        path = f.get('path', '')
        if not path or not os.path.exists(path):
            continue

        artwork = extract_artwork(path)
        if not artwork or not artwork.get('data'):
            skipped += 1
            continue

        # Si la caratula ya es mas pequena que max_size, saltar
        w = artwork.get('width', 0)
        h = artwork.get('height', 0)
        if w > 0 and h > 0 and max(w, h) <= max_size:
            skipped += 1
            continue

        try:
            resized = resize_image(artwork['data'], max_size=max_size,
                                   fmt=fmt, quality=quality)
            mime = 'image/jpeg' if fmt.upper() == 'JPEG' else f'image/{fmt.lower()}'
            ok, msg = save_artwork(path, resized, mime)
            if ok:
                success += 1
            else:
                errors.append({'path': path, 'error': msg})
        except Exception as e:
            errors.append({'path': path, 'error': str(e)})

    return {
        'success_count': success,
        'error_count': len(errors),
        'skipped_count': skipped,
        'errors': errors[:20],
    }


def batch_download_artwork(files):
    """
    Busca y descarga caratulas para archivos que no tienen.
    Usa iTunes Search API para encontrar la caratula.

    Args:
        files (list[dict]): lista de archivos sin caratula.

    Returns:
        dict con:
          - 'success_count': cuantos se descargaron y guardaron
          - 'error_count': cuantos fallaron
          - 'not_found_count': cuantos no se encontraron en iTunes
          - 'results': lista detallada
    """
    success = 0
    errors = []
    not_found = 0
    results = []

    for f in files:
        path = f.get('path', '')
        title = f.get('name', '')
        artist = f.get('artist', '')

        if not path or not os.path.exists(path):
            continue

        # Buscar en iTunes
        search_results = search_track(title, artist, limit=1)
        if not search_results:
            not_found += 1
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': False,
                'reason': 'No encontrado en iTunes',
            })
            continue

        best = best_match(search_results, target_title=title, target_artist=artist)
        if not best or not best.get('artwork_url'):
            not_found += 1
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': False,
                'reason': 'Sin caratula en iTunes',
            })
            continue

        # Descargar la caratula
        downloaded = download_image(best['artwork_url'])
        if not downloaded:
            errors.append({'path': path, 'error': 'Error descargando imagen'})
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': False,
                'reason': 'Error de descarga',
            })
            continue

        # Guardar en el archivo
        ok, msg = save_artwork(path, downloaded['data'], downloaded['mime'])
        if ok:
            success += 1
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': True,
                'source': f"iTunes: {best.get('title', '')} - {best.get('artist', '')}",
            })
        else:
            errors.append({'path': path, 'error': msg})
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': False,
                'reason': msg,
            })

    return {
        'success_count': success,
        'error_count': len(errors),
        'not_found_count': not_found,
        'results': results[:50],
    }
