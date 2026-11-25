"""
app/sync_folders.py
==================
Sincronización bidireccional entre dos carpetas de música.

Caso de uso típico:
  Carpeta A (origen, ej: música del PC)  →  Carpeta B (destino, ej: DAP Hiby)
  El PC es la "fuente de verdad": todo lo que cambia el usuario se hace en A,
  y B debe reflejar esos cambios.

QUÉ DETECTA (5 tipos de cambios):
  1. ADD     - Canción presente en A, falta en B  →  copiar A → B
  2. DELETE   - Canción presente en B, falta en A  →  borrar en B
  3. MOVE     - Canción presente en ambos, pero en A está en otra subcarpeta
                →  mover en B a la subcarpeta equivalente (crear si hace falta)
  4. METADATA - Canción presente en ambos, misma ruta relativa, pero los tags
                (título/artista/álbum/año/género/pista) o la carátula son
                distintos →  reemplazar B con la copia de A
  5. EQUAL    - Canción presente en ambos, misma ruta relativa y mismos
                metadatos →  sin cambios (no aparece en el plan)

CRITERIO DE MATCHING:
  Se matchea por (título normalizado + artista normalizado), igual que
  folder_compare.py. Si dos archivos coinciden por título+artista se
  consideran "la misma canción" aunque la ruta o el formato difieran.

FUNCIONES PRINCIPALES:
  - preview_sync(folder_a, folder_b, options) -> dict con plan de cambios
  - apply_sync(plan, options) -> dict con resultado de ejecución

SEGURIDAD:
  - preview_sync() NUNCA toca archivos. Solo lee y calcula.
  - apply_sync() recibe el plan generado por preview_sync() (o filtrado por
    el usuario) y lo ejecuta.
  - Las operaciones de borrado van a la papelera (Send2Trash) por defecto,
    no se borran definitivamente. configurable via options.
"""

import os
import shutil
import hashlib
import unicodedata
import re
from pathlib import Path

from scanner import scan_folder, human_size
from metadata_reader import read_metadata
from audio_quality import format_duration
from artwork import extract_artwork


# ======================================================================
# NORMALIZACIÓN (igual que folder_compare.py para consistencia)
# ======================================================================

def _normalize(s):
    """Normaliza un string para comparación.

    v3.7.5: MANTIENE caracteres Unicode (cirílico, japonés, chino, etc.).
    Antes se usaba `[^a-z0-9\\s]` que eliminaba TODO lo no-ASCII, así que
    títulos como "Тоска" o "怪物" se normalizaban a "" y el match_key
    quedaba None, haciendo que el archivo se ignorara por completo en el
    análisis (ni ADD, ni DELETE, ni MOVE, ni METADATA). Eso causaba que
    el sync reportara 0 cambios aunque hubiera canciones faltantes.
    """
    if not s:
        return ''
    s = unicodedata.normalize('NFD', s)
    # Quitar acentos/diacríticos (Mn = Mark, Nonspacing)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\[[^]]*\]', '', s)
    s = re.sub(r'\b(feat|ft)\b\.?', '', s)
    # v3.7.5: mantener letras y dígitos Unicode (NO solo ASCII).
    # \w con re.UNICODE (default en Python 3 para str) matchea [a-zA-Z0-9_]
    # + todas las letras Unicode (cirílico, CJK, árabe, etc.).
    # Solo eliminamos puntuación y símbolos.
    s = re.sub(r'[^\w\s]', '', s, flags=re.UNICODE)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _match_key(title, artist):
    """Devuelve la clave usada para identificar 'la misma canción'."""
    t = _normalize(title)
    a = _normalize(artist)
    if not t:
        return None
    if a:
        return f'{t}__{a}'
    return t


# ======================================================================
# ENRIQUECIMIENTO DE ARCHIVOS
# ======================================================================

def _enrich_file(f, root_folder):
    """Toma un archivo del scanner y le añade metadata + ruta relativa.

    Args:
        f: dict del scanner (path, name, ext, size, parent)
        root_folder: carpeta raíz usada para calcular la ruta relativa

    Returns:
        dict enriquecido con:
            - path: ruta absoluta
            - filename: nombre del archivo
            - title, artist, album, date, genre, track: tags leídos
            - duration, duration_str: duración
            - ext: extensión sin punto
            - size, size_str: tamaño
            - rel_path: ruta relativa a root_folder (con /)
            - rel_dir: carpeta relativa (sin el archivo)
            - match_key: clave para identificar "misma canción"
            - artwork_hash: hash MD5 de la carátula embebida (o None)
            - has_artwork: bool
    """
    meta = read_metadata(f['path'])
    title = meta.get('title') or f['name']
    artist = meta.get('artist', '')
    duration = meta.get('duration', 0) or 0

    # Ruta relativa a la carpeta raíz (siempre con / para consistencia)
    try:
        rel_path = str(Path(f['path']).relative_to(root_folder)).replace('\\', '/')
    except ValueError:
        rel_path = Path(f['path']).name
    rel_dir = str(Path(rel_path).parent).replace('\\', '/').strip('./').strip('.')
    if rel_dir == '.':
        rel_dir = ''

    # Hash de la carátula embebida (para detectar cambios de carátula)
    artwork_hash = None
    has_artwork = False
    try:
        art = extract_artwork(f['path'])
        if art and art.get('data'):
            has_artwork = True
            artwork_hash = hashlib.md5(art['data']).hexdigest()
    except Exception:
        pass

    return {
        'path': f['path'],
        'filename': Path(f['path']).name,
        'title': title,
        'artist': artist,
        'album': meta.get('album', ''),
        'date': meta.get('date', ''),
        'genre': meta.get('genre', ''),
        'track': meta.get('track', ''),
        'duration': duration,
        'duration_str': format_duration(duration) if duration else '—',
        'ext': f['ext'].lstrip('.'),
        'size': f['size'],
        'size_str': human_size(f['size']),
        'rel_path': rel_path,
        'rel_dir': rel_dir,
        'match_key': _match_key(title, artist),
        'artwork_hash': artwork_hash,
        'has_artwork': has_artwork,
        # Tags relevantes para comparar (como tupla hashable)
        'tags_tuple': (
            title.strip().lower(),
            artist.strip().lower(),
            (meta.get('album') or '').strip().lower(),
            (meta.get('date') or '').strip().lower(),
            (meta.get('genre') or '').strip().lower(),
            (meta.get('track') or '').strip().lower(),
        ),
    }


# ======================================================================
# DETECCIÓN DE CAMBIOS
# ======================================================================

def preview_sync(folder_a, folder_b, options=None):
    """
    Compara dos carpetas y genera un plan de sincronización A → B.

    Args:
        folder_a (str): carpeta ORIGEN (fuente de verdad, ej: música del PC)
        folder_b (str): carpeta DESTINO (ej: DAP Hiby)
        options (dict|None): opciones de sincronización:
            - 'compare_artwork' (bool, default True): comparar carátulas
            - 'compare_metadata' (bool, default True): comparar tags
            - 'detect_moves' (bool, default True): detectar movimientos

    Returns:
        dict con:
            'changes': [lista de cambios detectados]
            'stats': {totales por tipo}
            'folder_a', 'folder_b': rutas absolutas
            'options': opciones efectivas usadas
            'error': str | None
    """
    if options is None:
        options = {}

    compare_artwork = options.get('compare_artwork', True)
    compare_metadata = options.get('compare_metadata', True)
    detect_moves = options.get('detect_moves', True)

    # Validar carpetas
    if not folder_a or not os.path.isdir(folder_a):
        return {'error': f'Carpeta origen (A) no existe o no es válida: {folder_a}'}
    if not folder_b or not os.path.isdir(folder_b):
        return {'error': f'Carpeta destino (B) no existe o no es válida: {folder_b}'}
    if os.path.normpath(folder_a) == os.path.normpath(folder_b):
        return {'error': 'La carpeta origen y destino son la misma.'}

    # Escanear ambas carpetas
    raw_a = scan_folder(folder_a)
    raw_b = scan_folder(folder_b)

    a_files = [_enrich_file(f, folder_a) for f in raw_a]
    b_files = [_enrich_file(f, folder_b) for f in raw_b]

    # Índices por match_key
    a_by_key = {}
    for f in a_files:
        if f['match_key']:
            a_by_key.setdefault(f['match_key'], []).append(f)
    b_by_key = {}
    for f in b_files:
        if f['match_key']:
            b_by_key.setdefault(f['match_key'], []).append(f)

    a_keys = set(a_by_key.keys())
    b_keys = set(b_by_key.keys())
    common_keys = a_keys & b_keys
    a_only_keys = a_keys - b_keys
    b_only_keys = b_keys - a_keys

    changes = []

    # ----------------------------------------------------------------
    # 1. ADD: presentes en A, faltan en B
    # ----------------------------------------------------------------
    for key in a_only_keys:
        for a_file in a_by_key[key]:
            changes.append({
                'type': 'add',
                'match_key': key,
                'title': a_file['title'],
                'artist': a_file['artist'],
                'album': a_file['album'],
                'ext': a_file['ext'],
                'size_str': a_file['size_str'],
                'duration_str': a_file['duration_str'],
                'source_path': a_file['path'],
                'source_rel_path': a_file['rel_path'],
                'source_rel_dir': a_file['rel_dir'],
                'target_path': str(Path(folder_b) / a_file['rel_path']),
                'target_rel_dir': a_file['rel_dir'],
                'action_desc': f'Copiar a B: {a_file["rel_path"]}',
            })

    # ----------------------------------------------------------------
    # 2. DELETE: presentes en B, faltan en A
    # ----------------------------------------------------------------
    for key in b_only_keys:
        for b_file in b_by_key[key]:
            changes.append({
                'type': 'delete',
                'match_key': key,
                'title': b_file['title'],
                'artist': b_file['artist'],
                'album': b_file['album'],
                'ext': b_file['ext'],
                'size_str': b_file['size_str'],
                'duration_str': b_file['duration_str'],
                'source_path': None,
                'target_path': b_file['path'],
                'target_rel_path': b_file['rel_path'],
                'target_rel_dir': b_file['rel_dir'],
                'action_desc': f'Borrar de B: {b_file["rel_path"]}',
            })

    # ----------------------------------------------------------------
    # 3+4. Comunes: detectar MOVE y METADATA
    # ----------------------------------------------------------------
    # v3.7.2: normalizamos rutas relativas antes de comparar para evitar
    # falsos MOVE por:
    #   - Mayusculas/minusculas (Windows es case-insensitive en filesystem)
    #   - Separadores mixtos (\ vs /)
    #   - Espacios en blanco al final
    # Ademas, si hay varios archivos con el mismo match_key en B, elegimos
    # el que tenga la ruta mas parecida al de A (no siempre el [0]).

    def _norm_rel(p):
        """Normaliza ruta relativa para comparacion robusta."""
        if not p:
            return ''
        return p.replace('\\', '/').rstrip('/').lower().strip()

    def _pick_best_b_match(a_file, b_candidates):
        """De todos los candidatos en B con el mismo match_key, elige el que
        tenga la ruta relativa mas parecida al archivo de A. Si ninguno
        coincide exactamente, devuelve el de [0] (comportamiento anterior).
        """
        a_norm = _norm_rel(a_file['rel_path'])
        # 1) Mismo filename exacto
        for b in b_candidates:
            if _norm_rel(b['rel_path']) == a_norm:
                return b
        # 2) Mismo filename (ignorando carpeta)
        a_fname = a_file['filename'].lower()
        for b in b_candidates:
            if b['filename'].lower() == a_fname:
                return b
        # 3) Fallback: el primero
        return b_candidates[0]

    for key in common_keys:
        a_file = a_by_key[key][0]
        b_file = _pick_best_b_match(a_file, b_by_key[key])

        # v3.7.2: comparar rutas normalizadas (case-insensitive, separadores unificados)
        a_rel_norm = _norm_rel(a_file['rel_path'])
        b_rel_norm = _norm_rel(b_file['rel_path'])
        same_path = (a_rel_norm == b_rel_norm)

        # ¿Mismos metadatos?
        same_metadata = True
        if compare_metadata:
            same_metadata = (a_file['tags_tuple'] == b_file['tags_tuple'])

        # ¿Misma carátula?
        same_artwork = True
        if compare_artwork:
            same_artwork = (a_file['artwork_hash'] == b_file['artwork_hash'])

        if same_path and same_metadata and same_artwork:
            # Sin cambios: no entra en el plan
            continue

        if not same_path and detect_moves:
            # MOVE: misma canción, distinta ruta relativa
            # Verificar si los metadatos también cambiaron
            metadata_also_changed = (
                (compare_metadata and not same_metadata) or
                (compare_artwork and not same_artwork)
            )
            changes.append({
                'type': 'move',
                'match_key': key,
                'title': a_file['title'],
                'artist': a_file['artist'],
                'album': a_file['album'],
                'ext': a_file['ext'],
                'size_str': a_file['size_str'],
                'duration_str': a_file['duration_str'],
                'source_path': a_file['path'],
                'source_rel_path': a_file['rel_path'],
                'source_rel_dir': a_file['rel_dir'],
                'target_path': b_file['path'],
                'target_rel_path': b_file['rel_path'],
                'target_rel_dir': b_file['rel_dir'],
                'new_target_path': str(Path(folder_b) / a_file['rel_path']),
                'new_target_rel_path': a_file['rel_path'],
                'metadata_also_changed': metadata_also_changed,
                'action_desc': (
                    f'Mover en B: {b_file["rel_path"]} → {a_file["rel_path"]}'
                    + (' (+ actualizar metadatos)' if metadata_also_changed else '')
                ),
            })
        elif same_path and (not same_metadata or not same_artwork):
            # METADATA: misma ruta, pero tags o carátula distintos
            # Detallar qué cambió
            changes_list = []
            if compare_metadata and not same_metadata:
                if (a_file['title'].strip().lower() != b_file['title'].strip().lower()):
                    changes_list.append('título')
                if (a_file['artist'].strip().lower() != b_file['artist'].strip().lower()):
                    changes_list.append('artista')
                if (a_file['album'].strip().lower() != b_file['album'].strip().lower()):
                    changes_list.append('álbum')
                if (a_file['date'].strip().lower() != b_file['date'].strip().lower()):
                    changes_list.append('año')
                if (a_file['genre'].strip().lower() != b_file['genre'].strip().lower()):
                    changes_list.append('género')
                if (a_file['track'].strip().lower() != b_file['track'].strip().lower()):
                    changes_list.append('pista')
            if compare_artwork and not same_artwork:
                if a_file['has_artwork'] and not b_file['has_artwork']:
                    changes_list.append('carátula (+)')
                elif not a_file['has_artwork'] and b_file['has_artwork']:
                    changes_list.append('carátula (−)')
                else:
                    changes_list.append('carátula')

            changes.append({
                'type': 'metadata',
                'match_key': key,
                'title': a_file['title'],
                'artist': a_file['artist'],
                'album': a_file['album'],
                'ext': a_file['ext'],
                'size_str': a_file['size_str'],
                'duration_str': a_file['duration_str'],
                'source_path': a_file['path'],
                'source_rel_path': a_file['rel_path'],
                'source_rel_dir': a_file['rel_dir'],
                'target_path': b_file['path'],
                'target_rel_path': b_file['rel_path'],
                'target_rel_dir': b_file['rel_dir'],
                'metadata_changes': changes_list,
                'action_desc': (
                    f'Actualizar metadatos en B: {a_file["rel_path"]} '
                    f'({", ".join(changes_list)})'
                ),
            })

    # Estadísticas
    stats = {
        'total': len(changes),
        'add': sum(1 for c in changes if c['type'] == 'add'),
        'delete': sum(1 for c in changes if c['type'] == 'delete'),
        'move': sum(1 for c in changes if c['type'] == 'move'),
        'metadata': sum(1 for c in changes if c['type'] == 'metadata'),
        'a_total': len(a_files),
        'b_total': len(b_files),
    }

    return {
        'changes': changes,
        'stats': stats,
        'folder_a': folder_a,
        'folder_b': folder_b,
        'options': {
            'compare_artwork': compare_artwork,
            'compare_metadata': compare_metadata,
            'detect_moves': detect_moves,
        },
        'error': None,
    }


# ======================================================================
# APLICACIÓN DEL PLAN
# ======================================================================

def apply_sync(plan, options=None, progress_callback=None):
    """
    Ejecuta un plan de sincronización generado por preview_sync().

    Args:
        plan (dict): resultado de preview_sync(), potencialmente filtrado
            por el usuario (solo aplicar los cambios seleccionados).
            El campo plan['changes'] puede tener una sublist de los cambios
            originales.
        options (dict|None):
            - 'use_trash' (bool, default True): mandar borrados a papelera
              en vez de borrar definitivo. Requiere Send2Trash instalado.
            - 'overwrite_target' (bool, default True): si el destino ya
              existe (caso MOVE donde la ruta nueva ya está ocupada por
              otro archivo), sobreescribir.
        progress_callback (callable|None): v3.7.4 función invocada después
            de CADA cambio con la firma:
                callback(event_type, change, detail)
            donde event_type ∈ {'start', 'ok', 'skipped', 'error'} y
            detail es el dict del resultado. Permite reportar progreso
            en vivo desde el frontend (modal de progreso).

    Returns:
        dict con:
            'success': bool
            'applied': int (cuántos cambios se aplicaron)
            'skipped': int (cuántos se saltaron por error o ya existían)
            'errors': [lista de errores (máx 30)]
            'details': [lista de resultados por cambio]
    """
    if options is None:
        options = {}

    use_trash = options.get('use_trash', True)
    overwrite_target = options.get('overwrite_target', True)

    def _emit(event, change, detail=None):
        if progress_callback:
            try:
                progress_callback(event, change, detail or {})
            except Exception:
                pass  # el callback nunca debe romper el apply

    if not plan or 'changes' not in plan:
        return {
            'success': False,
            'applied': 0,
            'skipped': 0,
            'errors': ['Plan inválido: falta la clave "changes".'],
            'details': [],
        }

    folder_b = plan.get('folder_b')
    if not folder_b or not os.path.isdir(folder_b):
        return {
            'success': False,
            'applied': 0,
            'skipped': 0,
            'errors': [f'Carpeta destino no existe: {folder_b}'],
            'details': [],
        }

    applied = 0
    skipped = 0
    errors = []
    details = []

    for change in plan['changes']:
        ctype = change.get('type')
        _emit('start', change)  # v3.7.4: avisar al frontend qué archivo va
        try:
            if ctype == 'add':
                _apply_add(change, folder_b, overwrite_target)
                applied += 1
                detail = {
                    'type': 'add', 'title': change.get('title'),
                    'status': 'ok',
                    'msg': f'Copiado: {change["source_rel_path"]}',
                }
                details.append(detail)
                _emit('ok', change, detail)
            elif ctype == 'delete':
                _apply_delete(change, use_trash)
                applied += 1
                detail = {
                    'type': 'delete', 'title': change.get('title'),
                    'status': 'ok',
                    'msg': f'Borrado: {change["target_rel_path"]}',
                }
                details.append(detail)
                _emit('ok', change, detail)
            elif ctype == 'move':
                _apply_move(change, folder_b, overwrite_target, use_trash)
                applied += 1
                detail = {
                    'type': 'move', 'title': change.get('title'),
                    'status': 'ok',
                    'msg': (f'Movido: {change["target_rel_path"]} → '
                            f'{change["new_target_rel_path"]}'),
                }
                details.append(detail)
                _emit('ok', change, detail)
            elif ctype == 'metadata':
                _apply_metadata(change, folder_b, overwrite_target)
                applied += 1
                detail = {
                    'type': 'metadata', 'title': change.get('title'),
                    'status': 'ok',
                    'msg': f'Actualizado: {change["source_rel_path"]}',
                }
                details.append(detail)
                _emit('ok', change, detail)
            else:
                skipped += 1
                detail = {
                    'type': ctype, 'title': change.get('title'),
                    'status': 'skipped',
                    'msg': f'Tipo desconocido: {ctype}',
                }
                details.append(detail)
                _emit('skipped', change, detail)
        except Exception as exc:
            skipped += 1
            err = f'{change.get("title", "?")}: {exc}'
            errors.append(err)
            detail = {
                'type': ctype, 'title': change.get('title'),
                'status': 'error',
                'msg': str(exc),
            }
            details.append(detail)
            _emit('error', change, detail)

    return {
        'success': len(errors) == 0,
        'applied': applied,
        'skipped': skipped,
        'errors': errors[:30],
        'details': details,
    }


# ======================================================================
# OPERACIONES INDIVIDUALES (internas)
# ======================================================================

def _apply_add(change, folder_b, overwrite_target):
    """Copia source_path → target_path (crea carpetas si hace falta)."""
    src = change['source_path']
    dst = change['target_path']
    if not os.path.exists(src):
        raise FileNotFoundError(f'Origen no existe: {src}')
    # Crear carpeta destino si hace falta
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(dst):
        if not overwrite_target:
            raise FileExistsError(f'Destino ya existe: {dst}')
        _safe_remove(dst, use_trash=True)
    shutil.copy2(src, dst)


def _apply_delete(change, use_trash):
    """Borra target_path (a papelera si use_trash, si no os.remove)."""
    target = change['target_path']
    if not os.path.exists(target):
        # Idempotente: si ya no existe, considerar OK
        return
    _safe_remove(target, use_trash)


def _apply_move(change, folder_b, overwrite_target, use_trash):
    """Mueve el archivo en B a la ruta nueva (la que tiene en A).

    Casos:
      - Si metadata_also_changed: reemplazar el de B con el de A (copy2 + remove)
      - Si no: solo mover shutil.move (preserva el archivo original de B)
    """
    src_in_b = change['target_path']    # archivo actual en B
    dst_in_b = change['new_target_path']  # ruta nueva en B (igual a A)
    src_in_a = change['source_path']    # referencia en A

    if not os.path.exists(src_in_b):
        # El archivo de B ya no existe: copiar de A directamente
        Path(dst_in_b).parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(dst_in_b):
            if not overwrite_target:
                raise FileExistsError(f'Destino ya existe: {dst_in_b}')
            _safe_remove(dst_in_b, use_trash=True)
        shutil.copy2(src_in_a, dst_in_b)
        return

    Path(dst_in_b).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(dst_in_b):
        if os.path.normpath(src_in_b) == os.path.normpath(dst_in_b):
            # Misma ruta, no hay movimiento real, va por metadata
            pass
        elif not overwrite_target:
            raise FileExistsError(
                f'El destino ya existe y overwrite_target=False: {dst_in_b}'
            )
        else:
            _safe_remove(dst_in_b, use_trash=True)

    if change.get('metadata_also_changed'):
        # Reemplazar el archivo de B con el de A (preservando ruta nueva)
        shutil.copy2(src_in_a, dst_in_b)
        # Borrar el archivo viejo de B si era distinta ruta
        if os.path.normpath(src_in_b) != os.path.normpath(dst_in_b):
            _safe_remove(src_in_b, use_trash)
    else:
        # Mover el archivo de B a la nueva ruta (preserva sus propios tags)
        shutil.move(src_in_b, dst_in_b)


def _apply_metadata(change, folder_b, overwrite_target):
    """Reemplaza el archivo de B con el de A (misma ruta relativa)."""
    src = change['source_path']
    dst = change['target_path']
    if not os.path.exists(src):
        raise FileNotFoundError(f'Origen no existe: {src}')
    if not os.path.exists(dst):
        # No hay destino: copiar directamente (crea carpeta si hace falta)
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    # Sobre-escribir: mandamos el viejo a papelera y copiamos el nuevo
    _safe_remove(dst, use_trash=True)
    shutil.copy2(src, dst)


def _safe_remove(path, use_trash):
    """Borra un archivo: a papelera si use_trash=True y Send2Trash está
    disponible; si no, os.remove definitivo."""
    if use_trash:
        try:
            from send2trash import send2trash
            send2trash(path)
            return
        except Exception:
            # Si Send2Trash falla (ej: en Linux sin Trash disponible),
            # caer a borrado definitivo
            pass
    os.remove(path)
