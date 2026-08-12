"""
app/lyrics.py
=============
Busca y descarga letras (lyrics) de canciones desde internet.

Fuentes usadas:
  1. lrclib.net (API publica, gratis, sin registro)
     - Busca por nombre + artista
     - Devuelve letras sincronizadas (LRC) o planas

Funciones:
  - detect_missing_lyrics(files): lista archivos sin letra embebida
  - search_lyrics(title, artist): busca letra en lrclib.net
  - save_lyrics(file_path, lyrics): guarda letra en el archivo
  - batch_download_lyrics(files): descarga letras para todos los faltantes
"""

import os
import json
import requests
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3, USLT, error as ID3Error
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis


# API de lrclib.net (gratis, sin registro)
LRCLIB_SEARCH = "https://lrclib.net/api/search"
LRCLIB_GET = "https://lrclib.net/api/get"


def detect_missing_lyrics(files):
    """
    Recorre la lista de archivos y devuelve los que NO tienen letra embebida.

    Args:
        files (list[dict]): lista de archivos del escaneo.

    Returns:
        dict con:
          - 'missing': lista de archivos sin letra
          - 'has_lyrics': lista de archivos con letra
          - 'total': total
          - 'missing_count': cuantos faltan
          - 'has_count': cuantos tienen
    """
    missing = []
    has_lyrics = []

    for f in files:
        path = f.get('path', '')
        if not path or not os.path.exists(path):
            continue

        has = _has_lyrics(path)
        if has:
            has_lyrics.append(f)
        else:
            missing.append(f)

    return {
        'missing': missing,
        'has_lyrics': has_lyrics,
        'total': len(files),
        'missing_count': len(missing),
        'has_count': len(has_lyrics),
    }


def _has_lyrics(file_path):
    """Verifica si un archivo tiene letra embebida."""
    try:
        ext = Path(file_path).suffix.lower()
        if ext == '.mp3':
            try:
                audio = ID3(file_path)
                for key in audio:
                    if key.startswith('USLT:'):
                        return True
            except ID3Error:
                pass
        elif ext == '.flac':
            audio = FLAC(file_path)
            if 'lyrics' in audio or 'unsyncedlyrics' in audio:
                return True
        elif ext in ('.m4a', '.alac', '.aac'):
            audio = MP4(file_path)
            if '©lyr' in audio:
                return True
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
            if 'lyrics' in audio or 'unsyncedlyrics' in audio:
                return True
        # Verificacion generica
        audio = File(file_path, easy=True)
        if audio and ('lyrics' in audio or 'unsyncedlyrics' in audio):
            return True
    except Exception:
        pass
    return False


def read_lyrics(file_path):
    """
    Lee la letra embebida de un archivo de audio.

    Args:
        file_path (str): ruta del archivo.

    Returns:
        str | None: texto de la letra, o None si no tiene.
    """
    try:
        ext = Path(file_path).suffix.lower()
        if ext == '.mp3':
            try:
                audio = ID3(file_path)
                for key in audio:
                    if key.startswith('USLT:'):
                        frame = audio[key]
                        return frame.text if hasattr(frame, 'text') else str(frame)
            except ID3Error:
                pass
        elif ext == '.flac':
            audio = FLAC(file_path)
            if 'lyrics' in audio:
                return audio['lyrics'][0]
            if 'unsyncedlyrics' in audio:
                return audio['unsyncedlyrics'][0]
        elif ext in ('.m4a', '.alac', '.aac'):
            audio = MP4(file_path)
            if '©lyr' in audio:
                val = audio['©lyr']
                return val[0] if isinstance(val, list) and val else str(val)
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
            if 'lyrics' in audio:
                return audio['lyrics'][0]
            if 'unsyncedlyrics' in audio:
                return audio['unsyncedlyrics'][0]
        # Intento generico
        audio = File(file_path, easy=True)
        if audio:
            if 'lyrics' in audio:
                val = audio['lyrics']
                return val[0] if isinstance(val, list) and val else str(val)
            if 'unsyncedlyrics' in audio:
                val = audio['unsyncedlyrics']
                return val[0] if isinstance(val, list) and val else str(val)
    except Exception as e:
        print(f"Error leyendo letra de {file_path}: {e}")
    return None


def remove_lyrics(file_path):
    """
    Elimina la letra embebida de un archivo de audio.

    Returns:
        tuple: (success: bool, message: str)
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext == '.mp3':
            try:
                audio = ID3(file_path)
                keys_to_del = [k for k in audio if k.startswith('USLT:')]
                if not keys_to_del:
                    return (True, 'Sin letra previa.')
                for k in keys_to_del:
                    del audio[k]
                audio.save(file_path)
                return (True, 'Letra eliminada de MP3.')
            except ID3Error:
                return (True, 'Sin letra previa.')
        elif ext == '.flac':
            audio = FLAC(file_path)
            changed = False
            if 'lyrics' in audio:
                del audio['lyrics']
                changed = True
            if 'unsyncedlyrics' in audio:
                del audio['unsyncedlyrics']
                changed = True
            if changed:
                audio.save()
                return (True, 'Letra eliminada de FLAC.')
            return (True, 'Sin letra previa.')
        elif ext in ('.m4a', '.alac', '.aac'):
            audio = MP4(file_path)
            if '©lyr' in audio:
                del audio['©lyr']
                audio.save()
                return (True, 'Letra eliminada de M4A.')
            return (True, 'Sin letra previa.')
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
            changed = False
            if 'lyrics' in audio:
                del audio['lyrics']
                changed = True
            if 'unsyncedlyrics' in audio:
                del audio['unsyncedlyrics']
                changed = True
            if changed:
                audio.save()
                return (True, 'Letra eliminada de OGG.')
            return (True, 'Sin letra previa.')
        else:
            return (False, f'Formato {ext} no soportado.')
    except Exception as e:
        return (False, f'Error: {str(e)}')


def search_lyrics(title, artist='', album='', duration=0):
    """
    Busca letra de una cancion en lrclib.net.

    Args:
        title (str): titulo de la cancion.
        artist (str): artista.
        album (str): album (opcional).
        duration (float): duracion en segundos (opcional, mejora precision).

    Returns:
        dict | None:
            {
                'plain': 'letra completa...',
                'synced': '[00:01.00]Linea 1\n...',
                'source': 'lrclib.net',
                'track_name': '...',
                'artist_name': '...',
            }
            o None si no se encontro.
    """
    params = {
        'track_name': title,
        'artist_name': artist,
    }
    if album:
        params['album_name'] = album
    if duration and duration > 0:
        params['duration'] = int(duration)

    try:
        resp = requests.get(LRCLIB_SEARCH, params=params, timeout=15,
                           headers={'User-Agent': 'MusicManager/2.0'})
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data or not isinstance(data, list):
            return None

        # Tomar el primer resultado
        item = data[0]
        return {
            'plain': item.get('plainLyrics', ''),
            'synced': item.get('syncedLyrics', ''),
            'source': 'lrclib.net',
            'track_name': item.get('trackName', ''),
            'artist_name': item.get('artistName', ''),
            'album_name': item.get('albumName', ''),
        }
    except Exception as e:
        print(f"Error buscando letra: {e}")
        return None


def save_lyrics(file_path, lyrics, synced=False):
    """
    Guarda letra en un archivo de audio.

    Args:
        file_path (str): ruta del archivo.
        lyrics (str): texto de la letra.
        synced (bool): si True, guarda como letra sincronizada.

    Returns:
        tuple: (success: bool, message: str)
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext == '.mp3':
            return _save_lyrics_mp3(file_path, lyrics)
        elif ext == '.flac':
            return _save_lyrics_flac(file_path, lyrics)
        elif ext in ('.m4a', '.alac', '.aac'):
            return _save_lyrics_mp4(file_path, lyrics)
        elif ext == '.ogg':
            return _save_lyrics_ogg(file_path, lyrics)
        else:
            return (False, f'Formato {ext} no soportado para letras.')
    except Exception as e:
        return (False, f'Error: {str(e)}')


def _save_lyrics_mp3(file_path, lyrics):
    """Guarda letra en MP3 via USLT frame."""
    try:
        try:
            audio = ID3(file_path)
        except ID3Error:
            audio = ID3()
        # Eliminar USLT existentes
        keys_to_del = [k for k in audio if k.startswith('USLT:')]
        for k in keys_to_del:
            del audio[k]
        audio.add(USLT(encoding=3, lang='spa', desc='', text=lyrics))
        audio.save(file_path)
        return (True, 'Letra guardada en MP3.')
    except Exception as e:
        return (False, f'Error MP3: {e}')


def _save_lyrics_flac(file_path, lyrics):
    """Guarda letra en FLAC via Vorbis comments."""
    audio = FLAC(file_path)
    if 'lyrics' in audio:
        del audio['lyrics']
    if 'unsyncedlyrics' in audio:
        del audio['unsyncedlyrics']
    audio['lyrics'] = lyrics
    audio['unsyncedlyrics'] = lyrics
    audio.save()
    return (True, 'Letra guardada en FLAC.')


def _save_lyrics_mp4(file_path, lyrics):
    """Guarda letra en M4A/MP4 via ©lyr atom."""
    audio = MP4(file_path)
    audio['©lyr'] = lyrics
    audio.save()
    return (True, 'Letra guardada en M4A.')


def _save_lyrics_ogg(file_path, lyrics):
    """Guarda letra en OGG via Vorbis comments."""
    audio = OggVorbis(file_path)
    if 'lyrics' in audio:
        del audio['lyrics']
    if 'unsyncedlyrics' in audio:
        del audio['unsyncedlyrics']
    audio['lyrics'] = lyrics
    audio['unsyncedlyrics'] = lyrics
    audio.save()
    return (True, 'Letra guardada en OGG.')


def batch_download_lyrics(files):
    """
    Descarga letras para todos los archivos que no las tienen.

    Args:
        files (list[dict]): lista de archivos sin letra.

    Returns:
        dict con:
          - 'success_count': cuantos se descargaron y guardaron
          - 'error_count': cuantos fallaron
          - 'not_found_count': cuantos no se encontraron
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
        duration = f.get('duration', 0)

        if not path or not os.path.exists(path):
            continue

        # Buscar letra
        lyrics_data = search_lyrics(title, artist, duration=duration)
        if not lyrics_data or not lyrics_data.get('plain'):
            not_found += 1
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': False,
                'reason': 'No encontrada en lrclib.net',
            })
            continue

        # Guardar
        ok, msg = save_lyrics(path, lyrics_data['plain'])
        if ok:
            success += 1
            results.append({
                'path': path,
                'title': title,
                'artist': artist,
                'success': True,
                'source': f"lrclib.net: {lyrics_data.get('track_name', '')}",
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
