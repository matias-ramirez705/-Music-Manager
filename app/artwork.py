"""
app/artwork.py
==============
Manejo de caratulas (cover art) de archivos de audio:

  - extract_artwork(file_path): extrae la caratula embebida
  - save_artwork(file_path, image_bytes, mime): incrusta caratula
  - resize_image(image_bytes, max_size, fmt): redimensiona
  - download_image(url): descarga imagen desde URL

Soporta los principales formatos:
  - MP3  (ID3 APIC frame)
  - FLAC (PICTURE block)
  - M4A/MP4 (covr atom)
  - OGG  (METADATA_BLOCK_PICTURE base64)
"""

import io
import base64
import requests
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3, APIC, error as ID3Error
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis


# MIME types soportados para guardar
SUPPORTED_MIME = {'image/jpeg', 'image/png', 'image/webp'}


# ------------------------------------------------------------------
# EXTRACCION
# ------------------------------------------------------------------
def extract_artwork(file_path):
    """
    Extrae la caratula embebida en un archivo de audio.

    Args:
        file_path (str): ruta del archivo.

    Returns:
        dict | None:
            {
                'data': bytes,
                'mime': 'image/jpeg',
                'width': 600,        # si se conoce
                'height': 600,
                'size_kb': 45,
            }
        o None si no tiene caratula o no se pudo leer.
    """
    try:
        ext = Path(file_path).suffix.lower()

        if ext == '.mp3':
            return _extract_mp3(file_path)
        elif ext == '.flac':
            return _extract_flac(file_path)
        elif ext in ('.m4a', '.alac', '.aac'):
            return _extract_mp4(file_path)
        elif ext == '.ogg':
            return _extract_ogg(file_path)
        else:
            # Intentar generico con mutagen.File
            return _extract_generic(file_path)
    except Exception as e:
        print(f"Error extrayendo caratula de {file_path}: {e}")
        return None


def _extract_mp3(file_path):
    """Extrae APIC frame de MP3."""
    try:
        audio = ID3(file_path)
        for key in audio:
            if key.startswith('APIC:'):
                apic = audio[key]
                return _build_artwork_result(apic.data, apic.mime)
    except ID3Error:
        pass
    return None


def _extract_flac(file_path):
    """Extrae PICTURE block de FLAC."""
    audio = FLAC(file_path)
    if audio.pictures:
        pic = audio.pictures[0]
        return _build_artwork_result(pic.data, pic.mime,
                                     pic.width, pic.height)
    return None


def _extract_mp4(file_path):
    """Extrae covr atom de M4A/MP4."""
    audio = MP4(file_path)
    if 'covr' in audio:
        covr_list = audio['covr']
        if covr_list:
            covr = covr_list[0]
            # MP4Cover no tiene MIME directo; imageformat indica JPEG/PNG
            mime = 'image/jpeg'  # por defecto
            if hasattr(covr, 'imageformat'):
                # 0x0D = JPEG, 0x0E = PNG en atom MP4
                if covr.imageformat == MP4Cover.FMT_PNG:
                    mime = 'image/png'
            return _build_artwork_result(bytes(covr), mime)
    return None


def _extract_ogg(file_path):
    """Extrae METADATA_BLOCK_PICTURE de OGG Vorbis."""
    audio = OggVorbis(file_path)
    if 'metadata_block_picture' in audio:
        b64 = audio['metadata_block_picture'][0]
        data = base64.b64decode(b64)
        # El formato Picture de FLAC empieza con headers binarios.
        # El contenido binario de la imagen esta despues de 32 bytes.
        # Simplificamos: parsear como Picture de FLAC.
        try:
            pic = Picture(data)
            return _build_artwork_result(pic.data, pic.mime,
                                         pic.width, pic.height)
        except Exception:
            pass
    return None


def _extract_generic(file_path):
    """Fallback generico usando mutagen.File."""
    audio = File(file_path)
    if audio is None:
        return None
    if hasattr(audio, 'pictures') and audio.pictures:
        pic = audio.pictures[0]
        return _build_artwork_result(pic.data, pic.mime,
                                     pic.width, pic.height)
    # Para MP3 el tag APIC esta en audio.tags
    if audio.tags:
        for key in audio.tags:
            if str(key).startswith('APIC'):
                apic = audio.tags[key]
                return _build_artwork_result(apic.data, apic.mime)
    return None


def _build_artwork_result(data, mime, width=0, height=0):
    """
    Construye el dict de respuesta a partir de bytes de imagen.

    Si width/height son 0 (tipico de MP3 APIC que no los guarda),
    intenta leer las dimensiones reales decodificando la imagen
    con Pillow.
    """
    # Si no tenemos dimensiones, intentar leerlas de la imagen
    if (not width or not height) and data:
        try:
            from PIL import Image
            import io as _io
            img = Image.open(_io.BytesIO(data))
            width, height = img.size
            img.close()
        except Exception:
            # Pillow no instalado o imagen corrupta
            pass

    return {
        'data': data,
        'mime': mime or 'image/jpeg',
        'width': width,
        'height': height,
        'size_kb': round(len(data) / 1024, 1),
    }


# ------------------------------------------------------------------
# DESCARGA DE URL
# ------------------------------------------------------------------
def download_image(url, timeout=15):
    """
    Descarga una imagen desde una URL.

    Args:
        url (str): URL de la imagen.
        timeout (int): timeout en segundos.

    Returns:
        dict | None:
            {'data': bytes, 'mime': str, 'size_kb': float}
            o None si fallo.
    """
    if not url:
        return None
    try:
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'),
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.content
        mime = resp.headers.get('Content-Type', 'image/jpeg')
        # A veces viene con charset: image/jpeg; charset=utf-8
        mime = mime.split(';')[0].strip()
        return {
            'data': data,
            'mime': mime,
            'size_kb': round(len(data) / 1024, 1),
        }
    except requests.RequestException as e:
        print(f"Error descargando imagen {url}: {e}")
        return None


# ------------------------------------------------------------------
# REDIMENSIONAR
# ------------------------------------------------------------------
def resize_image(image_bytes, max_size=600, fmt='JPEG', quality=85):
    """
    Redimensiona una imagen para que quepa en max_size x max_size
    manteniendo el aspect ratio.

    Requiere Pillow (PIL). Si no esta instalada, devuelve la
    imagen original sin modificar.

    Args:
        image_bytes (bytes): imagen original.
        max_size (int): tamano maximo en pixels (ancho o alto).
        fmt (str): formato de salida ('JPEG', 'PNG', 'WEBP').
        quality (int): calidad (1-100) para JPEG/WEBP.

    Returns:
        bytes: imagen redimensionada, o la original si fallo.
    """
    try:
        from PIL import Image
    except ImportError:
        # Pillow no instalada: devolver original
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Convertir a RGB si es RGBA/P para JPEG
        if fmt.upper() == 'JPEG' and img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')

        # Redimensionar manteniendo aspect ratio
        w, h = img.size
        if max(w, h) > max_size:
            if w >= h:
                new_w = max_size
                new_h = int(h * (max_size / w))
            else:
                new_h = max_size
                new_w = int(w * (max_size / h))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format=fmt, quality=quality, optimize=True)
        return out.getvalue()
    except Exception as e:
        print(f"Error redimensionando: {e}")
        return image_bytes


# ------------------------------------------------------------------
# GUARDAR EN ARCHIVO
# ------------------------------------------------------------------
def save_artwork(file_path, image_bytes, mime='image/jpeg'):
    """
    Incrusta una caratula en un archivo de audio.

    Args:
        file_path (str): ruta del archivo a modificar.
        image_bytes (bytes): contenido binario de la imagen.
        mime (str): MIME type ('image/jpeg' o 'image/png').

    Returns:
        tuple: (success: bool, message: str)
    """
    if mime not in SUPPORTED_MIME:
        # Convertir a JPEG por defecto
        try:
            image_bytes = resize_image(image_bytes, max_size=1000, fmt='JPEG')
            mime = 'image/jpeg'
        except Exception:
            return (False, 'Formato de imagen no soportado.')

    ext = Path(file_path).suffix.lower()

    try:
        if ext == '.mp3':
            return _save_mp3(file_path, image_bytes, mime)
        elif ext == '.flac':
            return _save_flac(file_path, image_bytes, mime)
        elif ext in ('.m4a', '.alac', '.aac'):
            return _save_mp4(file_path, image_bytes, mime)
        elif ext == '.ogg':
            return _save_ogg(file_path, image_bytes, mime)
        else:
            return (False, f'Formato {ext} no soportado para caratulas.')
    except Exception as e:
        return (False, f'Error: {str(e)}')


def _save_mp3(file_path, image_bytes, mime):
    """Guarda APIC frame en MP3."""
    try:
        try:
            audio = ID3(file_path)
        except ID3Error:
            audio = ID3()
        # Eliminar APIC existentes
        keys_to_del = [k for k in audio if k.startswith('APIC:')]
        for k in keys_to_del:
            del audio[k]
        # Agregar nuevo
        audio.add(APIC(
            encoding=3,          # UTF-8
            mime=mime,
            type=3,              # Cover (front)
            desc='Cover',
            data=image_bytes,
        ))
        audio.save(file_path)
        return (True, 'Caratula guardada en MP3.')
    except Exception as e:
        return (False, f'Error MP3: {e}')


def _save_flac(file_path, image_bytes, mime):
    """Guarda PICTURE block en FLAC."""
    audio = FLAC(file_path)
    # Eliminar pictures existentes
    audio.clear_pictures()
    pic = Picture()
    pic.data = image_bytes
    pic.type = 3
    pic.mime = mime
    pic.desc = 'Cover'
    # Intentar dimensiones (requiere PIL)
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        pic.width, pic.height = img.size
    except Exception:
        pass
    audio.add_picture(pic)
    audio.save()
    return (True, 'Caratula guardada en FLAC.')


def _save_mp4(file_path, image_bytes, mime):
    """Guarda covr atom en M4A/MP4."""
    audio = MP4(file_path)
    if mime == 'image/png':
        cover = MP4Cover(image_bytes, imageformat=MP4Cover.FMT_PNG)
    else:
        cover = MP4Cover(image_bytes, imageformat=MP4Cover.FMT_JPEG)
    audio['covr'] = [cover]
    audio.save()
    return (True, 'Caratula guardada en M4A.')


def _save_ogg(file_path, image_bytes, mime):
    """Guarda METADATA_BLOCK_PICTURE en OGG Vorbis."""
    audio = OggVorbis(file_path)
    pic = Picture()
    pic.data = image_bytes
    pic.type = 3
    pic.mime = mime
    pic.desc = 'Cover'
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        pic.width, pic.height = img.size
    except Exception:
        pass

    # OGG requiere codificar el Picture en base64
    pic_data = pic.write()
    encoded = base64.b64encode(pic_data).decode('ascii')

    # Eliminar anteriores y agregar nuevo
    if 'metadata_block_picture' in audio:
        del audio['metadata_block_picture']
    audio['metadata_block_picture'] = [encoded]
    audio.save()
    return (True, 'Caratula guardada en OGG.')


def remove_artwork(file_path):
    """
    Elimina la caratula embebida de un archivo.

    Returns:
        tuple: (success, message)
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext == '.mp3':
            try:
                audio = ID3(file_path)
            except ID3Error:
                return (True, 'Sin caratula previa.')
            keys_to_del = [k for k in audio if k.startswith('APIC:')]
            for k in keys_to_del:
                del audio[k]
            audio.save(file_path)
            return (True, 'Caratula eliminada de MP3.')
        elif ext == '.flac':
            audio = FLAC(file_path)
            audio.clear_pictures()
            audio.save()
            return (True, 'Caratula eliminada de FLAC.')
        elif ext in ('.m4a', '.alac', '.aac'):
            audio = MP4(file_path)
            if 'covr' in audio:
                del audio['covr']
                audio.save()
            return (True, 'Caratula eliminada de M4A.')
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
            if 'metadata_block_picture' in audio:
                del audio['metadata_block_picture']
                audio.save()
            return (True, 'Caratula eliminada de OGG.')
        else:
            return (False, f'Formato {ext} no soportado.')
    except Exception as e:
        return (False, f'Error: {e}')
