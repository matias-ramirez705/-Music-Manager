"""
app/organizer.py
================
Logica para organizar canciones locales en subcarpetas segun la
playlist en la que aparecen.

Flujo:
  1. El usuario escanea su musica local (LAST_SCAN).
  2. El usuario selecciona un directorio base (ej: C:\\Users\\Matias\\Music\\Orden).
  3. Para cada cancion local, se busca en que playlists guardadas aparece.
  4. Se genera un "plan" de movimientos:
     - Si la cancion esta en 1 playlist: mover a <base>/<playlist>/
     - Si esta en varias: el usuario decide a cual (o "multiples"
       crea accesos directos / copia).
     - Si no esta en ninguna: dejar donde esta (o mover a <base>/Sin playlist/).
  5. El usuario revisa el plan y confirma.
  6. Se ejecutan los movimientos (shutil.move).

Funciones principales:
  - build_move_plan(base_dir): analiza LAST_SCAN + playlists guardadas
    y devuelve un plan con los movimientos propuestos.
  - execute_move_plan(plan): ejecuta los movimientos.
"""

import os
import shutil
import re
from pathlib import Path
from saved_playlists import build_local_playlist_index, list_playlists


def _sanitize_folder_name(name):
    """Convierte un nombre en un nombre de carpeta valido."""
    if not name:
        return 'Sin nombre'
    # Quitar caracteres invalidos para carpetas (Windows + Linux)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Quitar puntos y espacios al final (Windows no los permite)
    name = name.rstrip('. ')
    return name[:100] if len(name) > 100 else name


def _normalize_text(s):
    """Normaliza texto para comparacion (sin acentos, minusculas)."""
    import unicodedata
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


def build_move_plan(base_dir, options=None):
    """
    Construye un plan de movimientos para organizar canciones locales
    segun las playlists en las que aparecen.

    Args:
        base_dir (str): directorio base donde se crearan las subcarpetas.
        options (dict): opciones del plan:
            - 'move_unmatched' (bool): si True, las canciones que no
              estan en ninguna playlist se mueven a <base>/Sin playlist/.
              Si False, se dejan donde estan.
            - 'duplicate_policy' (str): que hacer con canciones en varias
              playlists:
                - 'ask': marcar para que el usuario decida (default)
                - 'first': mover a la primera playlist
                - 'all': copiar a todas las playlists
                - 'none': dejar donde esta

    Returns:
        dict con:
          - 'moves': lista de movimientos propuestos
              [{file, current_path, new_path, playlists: [{id,name,platform}],
                action: 'move'|'copy'|'skip'|'ask', conflict: bool}]
          - 'unmatched_count': cuantas no estan en ninguna playlist
          - 'single_playlist_count': cuantas estan en 1 playlist
          - 'multi_playlist_count': cuantas estan en 2+ playlists
          - 'total_files': total de archivos locales
          - 'error': None o mensaje
    """
    # Importar LAST_SCAN desde web_app (lo pasamos via options para
    # evitar dependencia circular)
    if not options:
        options = {}
    move_unmatched = options.get('move_unmatched', False)
    duplicate_policy = options.get('duplicate_policy', 'ask')

    # Necesitamos acceso a LAST_SCAN. Lo recibimos como argumento.
    files = options.get('files', [])
    if not files:
        return {
            'moves': [],
            'unmatched_count': 0,
            'single_playlist_count': 0,
            'multi_playlist_count': 0,
            'total_files': 0,
            'error': 'No hay musica escaneada. Ve a "Mi Musica" y escanea primero.',
        }

    if not base_dir:
        return {
            'moves': [],
            'unmatched_count': 0,
            'single_playlist_count': 0,
            'multi_playlist_count': 0,
            'total_files': len(files),
            'error': 'Debes indicar un directorio base.',
        }

    # Construir indice de playlists: {titulo_normalizado -> [playlist_info]}
    # playlist_info = {id, name, platform}
    playlist_index = build_local_playlist_index()

    # Tambien necesitamos un mapa id -> {name, platform} para resolver
    playlists_map = {}
    for p in list_playlists():
        playlists_map[p['id']] = p

    moves = []
    unmatched_count = 0
    single_count = 0
    multi_count = 0

    for f in files:
        title_norm = _normalize_text(f.get('name', ''))
        playlists = playlist_index.get(title_norm, [])

        # Filtrar playlists que sigan existiendo (por si se borraron)
        valid_playlists = []
        seen_ids = set()
        for p in playlists:
            if p['id'] in playlists_map and p['id'] not in seen_ids:
                valid_playlists.append(p)
                seen_ids.add(p['id'])

        current_path = f.get('path', '')
        filename = os.path.basename(current_path)

        if not valid_playlists:
            # No esta en ninguna playlist
            unmatched_count += 1
            if move_unmatched:
                target_dir = os.path.join(base_dir, 'Sin playlist')
                new_path = os.path.join(target_dir, filename)
                moves.append({
                    'file': f,
                    'current_path': current_path,
                    'new_path': new_path,
                    'playlists': [],
                    'action': 'move',
                    'conflict': False,
                })
            else:
                moves.append({
                    'file': f,
                    'current_path': current_path,
                    'new_path': current_path,
                    'playlists': [],
                    'action': 'skip',
                    'conflict': False,
                })
        elif len(valid_playlists) == 1:
            # Esta en 1 playlist: mover directo
            single_count += 1
            pl = valid_playlists[0]
            target_dir = os.path.join(base_dir, _sanitize_folder_name(pl['name']))
            new_path = os.path.join(target_dir, filename)
            moves.append({
                'file': f,
                'current_path': current_path,
                'new_path': new_path,
                'playlists': [{'id': pl['id'], 'name': pl['name'], 'platform': pl['platform']}],
                'action': 'move',
                'conflict': False,
            })
        else:
            # Esta en varias playlists
            multi_count += 1
            pl_infos = [{'id': p['id'], 'name': p['name'], 'platform': p['platform']}
                        for p in valid_playlists]

            if duplicate_policy == 'first':
                pl = valid_playlists[0]
                target_dir = os.path.join(base_dir, _sanitize_folder_name(pl['name']))
                new_path = os.path.join(target_dir, filename)
                moves.append({
                    'file': f,
                    'current_path': current_path,
                    'new_path': new_path,
                    'playlists': pl_infos,
                    'action': 'move',
                    'conflict': False,
                })
            elif duplicate_policy == 'all':
                # Copiar a todas las playlists (la primera es move, el resto copy)
                first = True
                for pl in valid_playlists:
                    target_dir = os.path.join(base_dir, _sanitize_folder_name(pl['name']))
                    new_path = os.path.join(target_dir, filename)
                    moves.append({
                        'file': f,
                        'current_path': current_path,
                        'new_path': new_path,
                        'playlists': pl_infos,
                        'action': 'copy' if not first else 'move',
                        'conflict': False,
                    })
                    first = False
            elif duplicate_policy == 'none':
                moves.append({
                    'file': f,
                    'current_path': current_path,
                    'new_path': current_path,
                    'playlists': pl_infos,
                    'action': 'skip',
                    'conflict': False,
                })
            else:  # 'ask'
                moves.append({
                    'file': f,
                    'current_path': current_path,
                    'new_path': None,  # se decidira despues
                    'playlists': pl_infos,
                    'action': 'ask',
                    'conflict': True,
                })

    return {
        'moves': moves,
        'unmatched_count': unmatched_count,
        'single_playlist_count': single_count,
        'multi_playlist_count': multi_count,
        'total_files': len(files),
        'error': None,
    }


def execute_move_plan(moves, base_dir):
    """
    Ejecuta los movimientos del plan.

    Args:
        moves (list): lista de movimientos (cada uno con current_path,
                      new_path, action).
        base_dir (str): directorio base (se crea si no existe).

    Returns:
        dict con:
          - 'success_count': cuantos se movieron/copiaron OK
          - 'error_count': cuantos fallaron
          - 'skipped_count': cuantos se saltaron (action=skip)
          - 'errors': lista de errores [{path, error}]
          - 'created_folders': lista de carpetas creadas
    """
    # Crear directorio base si no existe
    try:
        os.makedirs(base_dir, exist_ok=True)
    except OSError as e:
        return {
            'success_count': 0,
            'error_count': 0,
            'skipped_count': 0,
            'errors': [{'path': base_dir, 'error': f'No se pudo crear directorio base: {e}'}],
            'created_folders': [],
        }

    success = 0
    errors = []
    skipped = 0
    created_folders = set()

    for m in moves:
        action = m.get('action', 'skip')
        src = m.get('current_path', '')
        dst = m.get('new_path', '')

        if action == 'skip' or not dst:
            skipped += 1
            continue

        if src == dst:
            skipped += 1
            continue

        # Verificar que el source exista
        if not os.path.exists(src):
            errors.append({'path': src, 'error': 'Archivo origen no existe'})
            continue

        # Crear carpeta destino si no existe
        dst_dir = os.path.dirname(dst)
        try:
            os.makedirs(dst_dir, exist_ok=True)
            created_folders.add(dst_dir)
        except OSError as e:
            errors.append({'path': dst, 'error': f'No se pudo crear carpeta: {e}'})
            continue

        # Si el destino ya existe, anadir sufijo numerico
        final_dst = dst
        counter = 1
        while os.path.exists(final_dst) and final_dst != src:
            name, ext = os.path.splitext(dst)
            final_dst = f"{name}_{counter}{ext}"
            counter += 1

        try:
            if action == 'copy':
                shutil.copy2(src, final_dst)
            else:  # move
                shutil.move(src, final_dst)
            success += 1
        except OSError as e:
            errors.append({'path': src, 'error': str(e)})

    return {
        'success_count': success,
        'error_count': len(errors),
        'skipped_count': skipped,
        'errors': errors[:20],  # limitar a 20 errores para no saturar
        'created_folders': sorted(list(created_folders)),
    }
