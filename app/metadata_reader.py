"""
app/metadata_reader.py
======================
Lee metadatos (tags) de archivos de audio usando la libreria mutagen.

mutagen es la libreria estandar de Python para leer/escribir tags en
archivos de audio. Soporta:
  - MP3   (tags ID3v1, ID3v2)
  - FLAC  (comentarios Vorbis)
  - M4A   (atoms MP4/iTunes)
  - OGG   (comentarios Vorbis)
  - WAV   (limitado)
  - AIFF, APE, WV, etc.

Para cada archivo se extrae:
  - Tags:      titulo, artista, album, anio, genero, pista
  - Tecnicos:  duracion (s), bitrate (bps), sample_rate (Hz),
               bits_per_sample (bits), channels (1=mono, 2=stereo)
"""

from pathlib import Path
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE


# ------------------------------------------------------------------
# Mapeo de nombres de tags segun formato.
# Cada formato usa nombres distintos para el mismo concepto.
# ------------------------------------------------------------------
TAG_KEYS = {
    'title':  ['title', 'TIT2', '\xa9nam', 'Name'],
    'artist': ['artist', 'TPE1', '\xa9ART', 'Author', 'Artist'],
    'album':  ['album', 'TALB', '\xa9alb', 'Album'],
    'date':   ['date', 'TDRC', '\xa9day', 'Year', 'DATE'],
    'genre':  ['genre', 'TCON', '\xa9gen', 'Genre'],
    'track':  ['tracknumber', 'TRCK', 'trkn', 'Track'],
}


def _get_first_tag(mutagen_file, possible_keys):
    """
    Busca el primer tag que exista en el archivo.

    mutagen almacena los tags como un diccionario. Las claves
    dependen del formato (ID3 usa 'TIT2', FLAC usa 'title', etc.).
    Recorremos la lista de claves posibles y devolvemos la primera
    que exista.

    Args:
        mutagen_file: objeto devuelto por mutagen.File()
        possible_keys (list[str]): claves a probar en orden.

    Returns:
        str | None: valor del tag como texto, o None si no existe.
    """
    if mutagen_file is None:
        return None
    for key in possible_keys:
        if key in mutagen_file:
            value = mutagen_file[key]
            # Algunos tags son listas (FLAC, MP4), otros son strings (MP3)
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            # Para MP4 trkn viene como tupla (numero, total)
            if isinstance(value, tuple) and len(value) > 0:
                value = value[0]
            return str(value)
    return None


def _empty_metadata(file_path, error=None):
    """
    Devuelve un diccionario con valores por defecto cuando no
    se pudo leer la metadata de un archivo.

    Se mantiene el nombre del archivo como titulo para que al
    menos se muestre algo en la lista.
    """
    return {
        'title': Path(file_path).stem,
        'artist': 'Desconocido',
        'album': '',
        'date': '',
        'genre': '',
        'track': '',
        'duration': 0,
        'bitrate': 0,
        'sample_rate': 0,
        'bits_per_sample': 0,
        'channels': 0,
        'file_path': file_path,
        'error': error,
    }


def read_metadata(file_path):
    """
    Lee todos los metadatos de un archivo de audio.

    Args:
        file_path (str): ruta absoluta del archivo.

    Returns:
        dict con los campos descritos en la documentacion del modulo.
        Si ocurre un error, devuelve _empty_metadata() con el campo
        'error' lleno.
    """
    try:
        # mutagen.File() detecta el formato automaticamente
        # y devuelve el objeto adecuado (MP3, FLAC, MP4, etc.)
        audio = File(file_path, easy=True)

        if audio is None:
            # Formato no reconocido por mutagen
            return _empty_metadata(file_path, 'Formato no soportado')

        # ---------- Tags (texto) ----------
        title  = _get_first_tag(audio, TAG_KEYS['title'])
        artist = _get_first_tag(audio, TAG_KEYS['artist'])
        album  = _get_first_tag(audio, TAG_KEYS['album'])
        date   = _get_first_tag(audio, TAG_KEYS['date'])
        genre  = _get_first_tag(audio, TAG_KEYS['genre'])
        track  = _get_first_tag(audio, TAG_KEYS['track'])

        # Si no hay titulo, usar el nombre del archivo
        if not title:
            title = Path(file_path).stem

        # ---------- Info tecnica (del objeto .info) ----------
        # mutagen expone .info con atributos como length, bitrate, etc.
        info = audio.info
        duration = float(getattr(info, 'length', 0) or 0)
        bitrate  = int(getattr(info, 'bitrate', 0) or 0)
        sample_rate = int(getattr(info, 'sample_rate', 0) or 0)
        channels = int(getattr(info, 'channels', 0) or 0)
        bits_per_sample = int(getattr(info, 'bits_per_sample', 0) or 0)

        return {
            'title': title,
            'artist': artist or 'Desconocido',
            'album': album or '',
            'date': date or '',
            'genre': genre or '',
            'track': track or '',
            'duration': duration,
            'bitrate': bitrate,
            'sample_rate': sample_rate,
            'bits_per_sample': bits_per_sample,
            'channels': channels,
            'file_path': file_path,
            'error': None,
        }

    except Exception as e:
        return _empty_metadata(file_path, str(e))


def write_metadata(file_path, metadata):
    """
    Escribe metadatos en un archivo de audio.

    mutagen con easy=True permite asignar tags como diccionario
    usando claves genericas ('title', 'artist', etc.) y el se
    encarga de traducir al formato correcto (ID3, Vorbis, MP4...).

    Args:
        file_path (str): ruta del archivo a modificar.
        metadata (dict): campos a escribir. Solo se escriben los
            que no sean None.

    Returns:
        bool: True si se guardo correctamente, False si hubo error.
    """
    try:
        # easy=True activa el modo simplificado: claves genericas
        audio = File(file_path, easy=True)
        if audio is None:
            return False

        # Mapear nuestros campos a las claves easy de mutagen
        field_map = {
            'title':  'title',
            'artist': 'artist',
            'album':  'album',
            'date':   'date',
            'genre':  'genre',
            'track':  'tracknumber',
        }

        for our_field, mutagen_key in field_map.items():
            if our_field in metadata and metadata[our_field] is not None:
                value = metadata[our_field]
                # En modo easy, los valores se asignan como lista
                audio[mutagen_key] = str(value)

        audio.save()
        return True

    except Exception as e:
        print(f"Error escribiendo metadata en {file_path}: {e}")
        return False
