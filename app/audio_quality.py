"""
app/audio_quality.py
====================
Interpreta la calidad de un archivo de audio a partir de los
campos tecnicos leidos por mutagen (sample_rate, bits_per_sample,
bitrate, channels).

Genera etiquetas legibles como:
  - "CD Quality (16-bit / 44.1 kHz)"
  - "Hi-Res (24-bit / 96 kHz)"
  - "MP3 320 kbps"
  - "Lossy (compressed)"

Tambien clasifica la calidad en categorias para facilitar la
comparacion y mostrar iconos en la interfaz.
"""

from metadata_reader import read_metadata


# ------------------------------------------------------------------
# Umbrales para clasificar la calidad
# ------------------------------------------------------------------
# CD estandar:        16-bit / 44.1 kHz
# Hi-Res (comun):     24-bit / 48 kHz, 88.2 kHz, 96 kHz, 192 kHz
# Ultra Hi-Res:       32-bit float o > 192 kHz
# ------------------------------------------------------------------


def format_duration(seconds):
    """
    Convierte segundos a formato MM:SS o HH:MM:SS.

    Args:
        seconds (float | int): duracion en segundos.

    Returns:
        str: ej. "3:45", "1:02:30"
    """
    if not seconds or seconds <= 0:
        return "0:00"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_sample_rate(hz):
    """
    Convierte Hz a kHz legible.

    Args:
        hz (int): frecuencia de muestreo en Hz.

    Returns:
        str: ej. "44.1 kHz", "48 kHz", "96 kHz"
    """
    if not hz or hz <= 0:
        return "N/A"
    khz = hz / 1000
    # Si es entero (48, 96, 192) mostrar sin decimales
    if khz == int(khz):
        return f"{int(khz)} kHz"
    return f"{khz:.1f} kHz"


def format_bitrate(bps):
    """
    Convierte bits/segundo a kbps legible.

    Args:
        bps (int): bitrate en bits por segundo.

    Returns:
        str: ej. "320 kbps", "1411 kbps"
    """
    if not bps or bps <= 0:
        return "N/A"
    kbps = bps // 1000
    return f"{kbps} kbps"


def format_bit_depth(bits):
    """
    Formatea la profundidad de bits.

    Args:
        bits (int): bits por muestra (16, 24, 32, etc.)

    Returns:
        str: ej. "16-bit", "24-bit", "N/A"
    """
    if not bits or bits <= 0:
        return "N/A"
    return f"{bits}-bit"


def format_channels(channels):
    """
    Convierte numero de canales a etiqueta legible.

    Returns:
        str: "Mono", "Stereo", "5.1", "7.1", o "N canales"
    """
    if not channels or channels <= 0:
        return "N/A"
    mapping = {1: 'Mono', 2: 'Stereo', 6: '5.1', 8: '7.1'}
    return mapping.get(channels, f"{channels} canales")


def classify_quality(meta):
    """
    Clasifica la calidad general del archivo en una categoria.

    Categorias:
      - 'lossless-hires' : FLAC/WAV 24-bit o > 48 kHz
      - 'lossless-cd'    : FLAC/WAV 16-bit / 44.1 kHz (calidad CD)
      - 'lossless'       : FLAC/WAV sin info de bits
      - 'lossy-high'     : MP3/M4A/OGG >= 256 kbps
      - 'lossy-standard' : MP3/M4A/OGG < 256 kbps
      - 'unknown'        : no se pudo determinar

    Args:
        meta (dict): salida de read_metadata()

    Returns:
        tuple: (categoria, descripcion_larga)
    """
    ext = ''
    if 'file_path' in meta:
        from pathlib import Path
        ext = Path(meta['file_path']).suffix.lower()

    bits = meta.get('bits_per_sample', 0) or 0
    sr = meta.get('sample_rate', 0) or 0
    br = meta.get('bitrate', 0) or 0

    lossless_exts = {'.flac', '.wav', '.alac', '.ape', '.wv', '.aiff'}

    if ext in lossless_exts:
        if bits >= 24 or sr >= 96000:
            return ('lossless-hires',
                    f"Hi-Res Lossless ({format_bit_depth(bits)} / {format_sample_rate(sr)})")
        elif bits == 16 or sr == 44100:
            return ('lossless-cd',
                    f"CD Quality ({format_bit_depth(bits)} / {format_sample_rate(sr)})")
        elif bits > 0 or sr > 0:
            return ('lossless',
                    f"Lossless ({format_bit_depth(bits)} / {format_sample_rate(sr)})")
        else:
            return ('lossless', 'Lossless')
    else:
        # Formato lossy
        if br >= 256000:
            return ('lossy-high', f"Alta calidad ({format_bitrate(br)})")
        elif br > 0:
            return ('lossy-standard', f"Calidad estandar ({format_bitrate(br)})")
        else:
            return ('unknown', 'Calidad desconocida')


def build_quality_summary(meta):
    """
    Construye un resumen completo de la calidad para mostrar
    en la columna "Calidad" de la tabla.

    Args:
        meta (dict): salida de read_metadata()

    Returns:
        dict con:
            - 'label'      : texto corto (ej. "24-bit / 96 kHz")
            - 'category'   : categoria (ver classify_quality)
            - 'description': texto largo explicativo
            - 'details'    : dict con todos los campos tecnicos formateados
    """
    category, description = classify_quality(meta)

    # Etiqueta corta (combinacion bits / sample rate o bitrate)
    bits = meta.get('bits_per_sample', 0) or 0
    sr = meta.get('sample_rate', 0) or 0
    br = meta.get('bitrate', 0) or 0

    if bits > 0 or sr > 0:
        label_parts = []
        if bits > 0:
            label_parts.append(format_bit_depth(bits))
        if sr > 0:
            label_parts.append(format_sample_rate(sr))
        label = ' / '.join(label_parts)
    elif br > 0:
        label = format_bitrate(br)
    else:
        label = "N/A"

    return {
        'label': label,
        'category': category,
        'description': description,
        'details': {
            'bit_depth': format_bit_depth(bits),
            'sample_rate': format_sample_rate(sr),
            'bitrate': format_bitrate(br),
            'channels': format_channels(meta.get('channels', 0)),
            'duration': format_duration(meta.get('duration', 0)),
        }
    }
