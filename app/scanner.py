"""
app/scanner.py
==============
Escanea una carpeta (y todas sus subcarpetas) en busca de
archivos de audio soportados.

Lista de formatos soportados:
  - Lossless : .flac, .wav, .alac, .ape, .wv, .aiff
  - Lossy    : .mp3, .m4a, .aac, .ogg, .opus

Funcion principal:
    scan_folder(path) -> lista de archivos de audio encontrados
"""

import os
from pathlib import Path


# ------------------------------------------------------------------
# Extensiones de archivo reconocidas como audio.
# Se usan en minusculas para comparar con Path.suffix.lower()
# ------------------------------------------------------------------
AUDIO_EXTENSIONS = {
    # Lossy (con compresion con perdida)
    '.mp3', '.m4a', '.aac', '.ogg', '.opus',
    # Lossless (sin perdida)
    '.flac', '.wav', '.alac', '.ape', '.wv', '.aiff',
}


def is_audio_file(file_path):
    """
    Verifica si un archivo es de audio segun su extension.

    Args:
        file_path (str | Path): Ruta del archivo.

    Returns:
        bool: True si la extension esta en AUDIO_EXTENSIONS.
    """
    return Path(file_path).suffix.lower() in AUDIO_EXTENSIONS


def scan_folder(folder_path):
    """
    Recorre recursivamente una carpeta y devuelve todos los
    archivos de audio encontrados.

    Usa os.walk() para entrar en subcarpetas automaticamente.

    Args:
        folder_path (str): Ruta de la carpeta a escanear.

    Returns:
        list[dict]: Cada elemento tiene:
            - 'path'  (str): ruta absoluta del archivo
            - 'name'  (str): nombre sin extension
            - 'ext'   (str): extension en minusculas (ej: '.flac')
            - 'size'  (int): tamano en bytes
            - 'parent'(str): carpeta padre (util para mostrar en UI)

    Returns lista vacia si la carpeta no existe o esta vacia.
    """
    results = []
    folder = Path(folder_path)

    # Validar que exista y sea carpeta
    if not folder.exists() or not folder.is_dir():
        return results

    # os.walk recorre carpeta y subcarpetas automaticamente.
    # 'root' es la carpeta actual, 'files' los archivos en esa carpeta.
    for root, dirs, files in os.walk(folder):
        for file in files:
            if is_audio_file(file):
                full_path = Path(root) / file
                try:
                    size = full_path.stat().st_size
                except OSError:
                    # Archivo inaccesible (permisos, bloqueo, etc.)
                    size = 0

                results.append({
                    'path': str(full_path),
                    'name': Path(file).stem,            # nombre sin extension
                    'ext': Path(file).suffix.lower(),   # .flac, .mp3, etc.
                    'size': size,
                    'parent': str(Path(root)),
                })

    return results


def count_by_format(files):
    """
    Cuenta cuantos archivos hay por cada formato.
    Util para mostrar estadisticas en la interfaz.

    Args:
        files (list[dict]): lista devuelta por scan_folder()

    Returns:
        dict: {'.flac': 23, '.mp3': 145, ...}
    """
    counts = {}
    for f in files:
        ext = f['ext']
        counts[ext] = counts.get(ext, 0) + 1
    return counts


def human_size(num_bytes):
    """
    Convierte bytes a formato legible (KB, MB, GB).

    Args:
        num_bytes (int): tamano en bytes.

    Returns:
        str: ej. "3.2 MB", "1.1 GB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"
