"""
app/duplicates.py
=================
Deteccion de canciones repetidas en la biblioteca local.

Considera que dos archivos son "duplicados" cuando coinciden en:
  - Titulo normalizado (sin acentos, minusculas, sin parentesis)
  - Y artista normalizado

Opcionalmente, se puede usar coincidencia solo por titulo si el
usuario quiere detectar mas aggressiveamente (muchas veces el
artista varia un poco entre versiones).

Salida:
  Agrupa los archivos en clusters. Cada cluster es una lista de
  archivos que son el mismo tema. Si un cluster tiene 2+ archivos
  es un grupo de duplicados.

  Para cada archivo del cluster se incluye:
    - path
    - ext (formato)
    - size
    - bitrate
    - bits_per_sample
    - sample_rate
    - quality_label (ej. "24-bit / 96 kHz")
    - quality_category (ej. "lossless-hires")

  Ademas se marca cual es la "mejor calidad" del cluster (para
  sugerir cual conservar).
"""

from collections import defaultdict
import unicodedata
import re


def normalize_text(s):
    """
    Normaliza un string para comparacion:
      - Quitar acentos
      - Minusculas
      - Quitar texto entre parentesis y corchetes
      - Quitar "feat.", "ft."
      - Quitar puntuacion
      - Colapsar espacios
    """
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


def find_duplicates(files, match_by='title_artist'):
    """
    Encuentra grupos de archivos duplicados.

    Args:
        files (list[dict]): lista de archivos del escaneo (con campos
                            'name', 'artist', 'ext', 'size', 'path',
                            'quality', etc.).
        match_by (str): 'title_artist' (default) o 'title_only'.

    Returns:
        dict con:
          - 'groups': lista de grupos duplicados. Cada grupo:
              {
                'key': 'titulo - artista',
                'count': 3,
                'files': [archivo, archivo, ...]  # ordenados por calidad desc
              }
          - 'total_duplicates': numero de archivos que estan en algun grupo
          - 'total_groups': numero de grupos
          - 'space_reclaimable': bytes que se liberarian si se conservara
                                 solo la mejor version de cada grupo
    """
    # Indexar archivos por clave de comparacion
    clusters = defaultdict(list)
    for f in files:
        title_n = normalize_text(f.get('name', ''))
        artist_n = normalize_text(f.get('artist', ''))

        if match_by == 'title_only':
            key = title_n
        else:
            key = f"{title_n}||{artist_n}"

        if not key or key == '||':
            continue  # sin info suficiente para agrupar

        clusters[key].append(f)

    # Filtrar solo clusters con 2+ archivos (duplicados reales)
    duplicate_groups = []
    total_dup_files = 0
    space_reclaimable = 0

    # Prioridad de calidad para ordenar dentro de un cluster:
    #   1. lossless-hires (24-bit o >48kHz)
    #   2. lossless-cd (16-bit/44.1kHz)
    #   3. lossless (otros lossless)
    #   4. lossy-high (>=256kbps)
    #   5. lossy-standard (<256kbps)
    #   6. unknown
    QUALITY_PRIORITY = {
        'lossless-hires': 5,
        'lossless-cd': 4,
        'lossless': 3,
        'lossy-high': 2,
        'lossy-standard': 1,
        'unknown': 0,
    }

    for key, group in clusters.items():
        if len(group) < 2:
            continue

        # Ordenar el grupo por calidad descendente (mejor primero)
        sorted_group = sorted(
            group,
            key=lambda f: QUALITY_PRIORITY.get(
                f.get('quality', {}).get('category', 'unknown'), 0
            ),
            reverse=True
        )

        # La mejor version es la primera; el resto son "redundantes"
        best = sorted_group[0]
        for f in sorted_group[1:]:
            space_reclaimable += f.get('size', 0)

        # Construir la etiqueta legible de la clave
        title_n, _, artist_n = key.partition('||')
        label = title_n
        if artist_n and match_by == 'title_artist':
            label = f"{title_n} - {artist_n}"

        duplicate_groups.append({
            'key': label,
            'count': len(group),
            'best_index': 0,  # indice dentro de files del mejor
            'files': sorted_group,
            'best_format': best.get('ext', '').upper(),
            'best_quality': best.get('quality', {}).get('label', 'N/A'),
        })

        total_dup_files += len(group)

    # Ordenar grupos por cantidad de duplicados (mayor primero)
    duplicate_groups.sort(key=lambda g: g['count'], reverse=True)

    return {
        'groups': duplicate_groups,
        'total_duplicates': total_dup_files,
        'total_groups': len(duplicate_groups),
        'space_reclaimable': space_reclaimable,
    }
