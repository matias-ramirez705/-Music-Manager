"""
app/spotiflac_dummy.py (v3.16)
==============================
Genera archivos dummy (señuelo) tiny a partir de tu biblioteca musical real.

Estos archivos engañan a Spotiflac para que detecte canciones como
"ya descargadas" en la biblioteca local, mostrando la etiqueta de
duplicado al buscar.

Mejoras respecto al script original:
  - Tracking de qué canciones ya se generaron como dummy (en
    data/spotiflac_dummies.json) para que la próxima vez solo se
    generen las nuevas.
  - Integrado en Music Manager: usa el último escaneo de Mi Música
    para no tener que re-escanear.
  - Devuelve el ZIP al navegador directamente (descarga).

El ZIP debe descomprimirse en:
  /storage/emulated/0/Music/SpotyFlac/
en tu teléfono Android.
"""

import os
import json
import struct
import zipfile
import io
from pathlib import Path
from datetime import datetime


# Ruta del archivo de tracking: <proyecto>/data/spotiflac_dummies.json
DATA_DIR = Path(__file__).parent.parent / 'data'
TRACKING_FILE = DATA_DIR / 'spotiflac_dummies.json'

# Extensiones de audio soportadas
AUDIO_EXTENSIONS = {
    '.flac', '.opus', '.ogg', '.m4a', '.mp4', '.aac',
    '.mp3', '.wma', '.wav', '.aiff', '.ape', '.wv'
}


def _ensure_dir():
    """Crea la carpeta data/ si no existe."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_tracking():
    """Carga el JSON de tracking. Estructura:
        {
            "generated": [
                {
                    "path": "C:\\Music\\cancion.flac",
                    "filename": "cancion.flac",
                    "name": "Cancion",
                    "artist": "Artista",
                    "ext": "flac",
                    "generated_at": "2026-08-15T22:00:00"
                },
                ...
            ],
            "by_path": {  # índice para acceso rápido
                "C:\\Music\\cancion.flac": true,
                ...
            }
        }
    """
    if not TRACKING_FILE.exists():
        return {'generated': [], 'by_path': {}}
    try:
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'generated' not in data:
            data = {'generated': [], 'by_path': {}}
        if 'by_path' not in data:
            data['by_path'] = {g['path']: True for g in data['generated']}
        return data
    except (json.JSONDecodeError, OSError):
        return {'generated': [], 'by_path': {}}


def _save_tracking(data):
    """Guarda el JSON de tracking (escritura atómica)."""
    _ensure_dir()
    tmp = TRACKING_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(TRACKING_FILE)


def _sanitize_filename(name):
    """Limpia caracteres inválidos para nombres de archivo."""
    if not name:
        return ''
    for char, repl in [('/', '_'), ('\\', '_'), (':', '_'), ('*', '_'),
                       ('?', '_'), ('"', "'"), ('<', '_'), ('>', '_'),
                       ('|', '_')]:
        name = name.replace(char, repl)
    return name.strip(' .')


# ------------------------------------------------------------------
# Generadores de dummies por formato (adaptados del script original)
# ------------------------------------------------------------------

def _make_flac_dummy(title, artist, album=None, genre=None, isrc=None):
    """Crea un FLAC mínimo válido con metadatos VORBIS_COMMENT.
    Tamaño aprox: 200-500 bytes."""
    flac_magic = b'fLaC'

    streaminfo_header = bytes([0x00, 0x00, 0x00, 0x22])
    si = bytearray(34)
    si[0] = (4096 >> 8) & 0xFF
    si[1] = 4096 & 0xFF
    si[2] = (4096 >> 8) & 0xFF
    si[3] = 4096 & 0xFF
    val = (44100 << 12) | (1 << 9) | (15 << 4)
    si[10] = (val >> 16) & 0xFF
    si[11] = (val >> 8) & 0xFF
    si[12] = val & 0xFF
    si[17] = 0x01
    streaminfo_data = bytes(si)

    vendor = b'SpotiFLAC Dummy Generator'
    comments = []
    if title:
        comments.append(f'TITLE={title}')
    if artist:
        comments.append(f'ARTIST={artist}')
    if album:
        comments.append(f'ALBUM={album}')
    if genre:
        comments.append(f'GENRE={genre}')
    if isrc:
        comments.append(f'ISRC={isrc}')

    vc_data = struct.pack('<I', len(vendor)) + vendor
    vc_data += struct.pack('<I', len(comments))
    for c in comments:
        c_bytes = c.encode('utf-8')
        vc_data += struct.pack('<I', len(c_bytes)) + c_bytes

    vc_len = len(vc_data)
    vc_header = bytes([0x84]) + struct.pack('>I', vc_len)[1:]

    return flac_magic + streaminfo_header + streaminfo_data + vc_header + vc_data


def _make_opus_dummy():
    """Crea un stub OGG/Opus mínimo (~80 bytes)."""
    ogg = b'OggS'
    version = bytes([0])
    header_type = bytes([0x02])
    granule = struct.pack('<Q', 0)
    serial = struct.pack('<I', 0xDEAD)
    page_seq = struct.pack('<I', 0)
    crc = struct.pack('<I', 0)
    segments = bytes([1, 27])
    opus_id = b'OpusHead' + bytes([1, 2])
    opus_id += struct.pack('<H', 44100)
    opus_id += struct.pack('<I', 44100)
    opus_id += struct.pack('<H', 0)
    opus_id += bytes([0])
    opus_id += b'\x00' * (27 - len(opus_id))
    return ogg + version + header_type + granule + serial + page_seq + crc + segments + opus_id


def _make_aac_dummy():
    """Crea un stub ADTS/AAC mínimo (~23 bytes)."""
    return bytes([0xFF, 0xF1, 0x50, 0x00, 0x1F, 0xFC]) + b'\x00' * 16


def _make_m4a_dummy():
    """Crea un stub M4A/MP4 mínimo (ftyp + moov vacíos)."""
    ftyp_body = b'isom' + struct.pack('>I', 0x200) + b'isomiso2mp41'
    ftyp = struct.pack('>I', 8 + len(ftyp_body)) + b'ftyp' + ftyp_body
    moov = struct.pack('>I', 8) + b'moov'
    return ftyp + moov


def _make_mp3_dummy(title=None, artist=None):
    """Crea un stub MP3 mínimo con tag ID3v2."""
    frames = b''
    if title or artist:
        frames_data = b''
        if title:
            t = f'\x00{title}'.encode('utf-16-be')
            frame = b'TIT2' + struct.pack('>I', len(t)) + b'\x00\x00' + t
            frames_data += frame
        if artist:
            a = f'\x00{artist}'.encode('utf-16-be')
            frame = b'TPE1' + struct.pack('>I', len(a)) + b'\x00\x00' + a
            frames_data += frame
        size = len(frames_data)
        sync_size = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F,
                          (size >> 7) & 0x7F, size & 0x7F])
        id3 = b'ID3\x03\x00\x00' + sync_size + frames_data
        frames += id3
    mp3_frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + b'\x00' * 413
    return frames + mp3_frame


def _make_wav_dummy():
    """WAV header stub."""
    return (b'RIFF' + struct.pack('<I', 36) + b'WAVE' +
            b'fmt ' + struct.pack('<I', 16) + struct.pack('<H', 1) +
            struct.pack('<H', 2) + struct.pack('<I', 44100) +
            struct.pack('<I', 176400) + struct.pack('<H', 4) +
            struct.pack('<H', 16) + b'data' + struct.pack('<I', 0))


def _make_aiff_dummy():
    """AIFF header stub."""
    return (b'FORM' + struct.pack('>I', 38) + b'AIFF' +
            b'COMM' + struct.pack('>I', 18) + struct.pack('>h', 2) +
            struct.pack('>I', 1) + struct.pack('>h', 16) +
            b'\x00' * 10 + b'SSND' + struct.pack('>I', 8) +
            b'\x00' * 8)


def _make_wma_dummy():
    """ASF/WMA header stub."""
    guid = b'\x30\x26\xB2\x75\x8E\x66\xCF\x11\xA6\xD9\x00\xAA\x00\x62\xCE\x6C'
    return (guid + struct.pack('<Q', 30) + b'\x00' * 14)


def _make_ape_dummy():
    """APE header stub."""
    return (b'APETAGEX' + struct.pack('<I', 2000) + struct.pack('<I', 32) +
            struct.pack('<I', 0) + struct.pack('<I', 0x80000000) + b'\x00' * 16)


def _make_wv_dummy():
    """WavPack header stub."""
    return b'wvpk' + struct.pack('<I', 24) + struct.pack('>I', 0x0410) + b'\x00' * 14


def _make_dummy_for_file(file_info):
    """Genera los bytes dummy correspondientes según la extensión.

    Args:
        file_info (dict): debe tener 'ext', 'name', 'artist' y opcionalmente
                          'album', 'genre', 'isrc'.
    Returns:
        bytes: el contenido del archivo dummy.
    """
    ext = ('.' + file_info.get('ext', '')).lower()
    title = file_info.get('name', '')
    artist = file_info.get('artist', '')
    album = file_info.get('album')
    genre = file_info.get('genre')
    isrc = file_info.get('isrc')

    if ext == '.flac':
        return _make_flac_dummy(title, artist, album, genre, isrc)
    elif ext == '.opus':
        return _make_opus_dummy()
    elif ext == '.ogg':
        return _make_opus_dummy()
    elif ext == '.aac':
        return _make_aac_dummy()
    elif ext in ('.m4a', '.mp4'):
        return _make_m4a_dummy()
    elif ext == '.mp3':
        return _make_mp3_dummy(title, artist)
    elif ext == '.wav':
        return _make_wav_dummy()
    elif ext == '.aiff':
        return _make_aiff_dummy()
    elif ext == '.wma':
        return _make_wma_dummy()
    elif ext == '.ape':
        return _make_ape_dummy()
    elif ext == '.wv':
        return _make_wv_dummy()
    else:
        return _make_flac_dummy(title, artist)


# ------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------

def preview_generation(files, only_new=True):
    """
    Previsualiza qué archivos se generarían como dummy.

    Args:
        files (list[dict]): lista de archivos del último escaneo
                            (con path, name, artist, ext).
        only_new (bool): si True, excluye los ya generados (según tracking).

    Returns:
        dict con:
            - 'to_generate': lista de archivos a generar
            - 'already_generated': cuántos ya estaban
            - 'total': total en el escaneo
            - 'by_format': conteo por extensión
    """
    tracking = _load_tracking()
    by_path = tracking.get('by_path', {})

    to_generate = []
    already = 0
    for f in files:
        path = f.get('path', '')
        if only_new and path in by_path:
            already += 1
            continue
        ext = f.get('ext', '').lower()
        if ('.' + ext) not in AUDIO_EXTENSIONS:
            continue
        to_generate.append({
            'path': path,
            'filename': Path(path).name if path else '',
            'name': f.get('name', ''),
            'artist': f.get('artist', ''),
            'ext': ext,
            'album': f.get('album', ''),
        })

    # Conteo por formato
    by_format = {}
    for f in to_generate:
        ext = f['ext']
        by_format[ext] = by_format.get(ext, 0) + 1

    return {
        'to_generate': to_generate,
        'already_generated': already,
        'total': len(files),
        'by_format': by_format,
    }


def generate_dummy_zip(files, only_new=True, naming_mode='original'):
    """
    Genera el ZIP con archivos dummy.

    Args:
        files (list[dict]): lista de archivos del último escaneo.
        only_new (bool): si True, solo genera los que no están en tracking.
        naming_mode (str): 'original' (mantiene nombre) o 'spotiflac'
                           ('{titulo} - {artista}.ext').

    Returns:
        tuple: (zip_bytes, stats)
            - zip_bytes: contenido del ZIP como bytes
            - stats: dict con count, by_format, errors, total_processed
    """
    preview = preview_generation(files, only_new=only_new)
    to_generate = preview['to_generate']

    # Buffer en memoria para el ZIP
    buf = io.BytesIO()
    used_names = {}
    errors = []
    generated_entries = []  # para actualizar el tracking

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in to_generate:
            try:
                # Construir nombre
                if naming_mode == 'spotiflac':
                    title = _sanitize_filename(f.get('name', '')) or 'unknown'
                    artist = _sanitize_filename(f.get('artist', '')) or 'unknown'
                    ext = '.' + f.get('ext', 'flac')
                    base_name = f"{title} - {artist}{ext}"
                else:
                    base_name = f.get('filename', '') or Path(f.get('path', '')).name

                # Evitar colisiones de nombre dentro del ZIP
                if base_name in used_names:
                    stem = Path(base_name).stem
                    ext = Path(base_name).suffix
                    base_name = f"{stem}_{used_names[base_name]}{ext}"
                used_names[base_name] = used_names.get(base_name, 0) + 1

                dummy_bytes = _make_dummy_for_file(f)
                zf.writestr(base_name, dummy_bytes)

                # Registrar para tracking
                generated_entries.append({
                    'path': f['path'],
                    'filename': base_name,
                    'name': f.get('name', ''),
                    'artist': f.get('artist', ''),
                    'ext': f.get('ext', ''),
                    'generated_at': datetime.now().isoformat(timespec='seconds'),
                })
            except Exception as e:
                errors.append({
                    'path': f.get('path', ''),
                    'filename': f.get('filename', ''),
                    'error': str(e),
                })

    # Actualizar tracking
    if generated_entries:
        tracking = _load_tracking()
        tracking['generated'].extend(generated_entries)
        for entry in generated_entries:
            tracking['by_path'][entry['path']] = True
        _save_tracking(tracking)

    stats = {
        'count': len(generated_entries),
        'by_format': preview['by_format'],
        'errors': errors,
        'total_processed': len(to_generate),
        'already_generated': preview['already_generated'],
    }
    return buf.getvalue(), stats


def get_history():
    """Devuelve el historial de dummies generados."""
    tracking = _load_tracking()
    return {
        'generated': tracking.get('generated', []),
        'count': len(tracking.get('generated', [])),
    }


def clear_history():
    """Vacía el historial de dummies generados.
    Útil si el usuario quiere regenerar todo desde cero."""
    tracking = {'generated': [], 'by_path': {}}
    _save_tracking(tracking)
    return len(tracking['generated'])


def remove_from_history(path):
    """Quita una canción específica del historial de dummies.
    Así la próxima vez se volverá a generar."""
    tracking = _load_tracking()
    before = len(tracking['generated'])
    tracking['generated'] = [g for g in tracking['generated']
                             if g.get('path') != path]
    tracking['by_path'].pop(path, None)
    _save_tracking(tracking)
    return before - len(tracking['generated'])
