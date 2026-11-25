"""
app/sync_jobs.py
================
Gestor de jobs de sincronización en background (v3.7.4).

Permite que el frontend dispare un apply_sync() sin bloquear la petición
HTTP y consultar el progreso en vivo via polling.

FLUJO:
  1. Frontend llama POST /api/sync/apply -> el handler de Flask crea un
     job_id y arranca apply_sync en un hilo aparte, devolviendo el job_id
     inmediatamente.
  2. Frontend hace polling a GET /api/sync/status?job_id=... cada 500ms.
  3. apply_sync invoca el progress_callback interno tras cada cambio; este
     callback actualiza el estado del job (current_action, applied, etc).
  4. Cuando apply_sync termina, el job se marca 'done' con el resultado
     final. El frontend lo detecta y muestra el resumen.

ESTRUCTURA DEL JOB:
  {
    'job_id': str,
    'status': 'running' | 'done' | 'error',
    'total': int,
    'applied': int,
    'skipped': int,
    'errors_count': int,
    'current_change': { change o None },
    'current_action': str,  # descripción legible: "Copiando X.flac..."
    'log': [lista de eventos],
    'result': { resultado final o None },
    'started_at': float,
    'finished_at': float | None,
  }
"""

import threading
import time
import uuid
from typing import Optional


# In-memory job store (no persiste entre reinicios del server)
_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()
_MAX_LOG_EVENTS = 500  # cap para no crecer infinitamente en planes enormes


def _action_label(change):
    """Genera una descripción legible del cambio en curso."""
    if not change:
        return ''
    ctype = change.get('type')
    title = change.get('title', '?')
    if ctype == 'add':
        return f'Copiando a B: {title}'
    if ctype == 'delete':
        return f'Borrando de B: {title}'
    if ctype == 'move':
        return f'Moviendo en B: {title}'
    if ctype == 'metadata':
        return f'Actualizando metadatos: {title}'
    return f'Procesando: {title}'


def start_job(plan, options):
    """Crea un job y arranca apply_sync en un hilo aparte.
    Devuelve el job_id inmediatamente.

    Args:
        plan: plan generado por preview_sync (o filtrado por el usuario)
        options: dict con use_trash, overwrite_target

    Returns:
        str: job_id único
    """
    job_id = str(uuid.uuid4())
    total = len(plan.get('changes', []))

    job = {
        'job_id': job_id,
        'status': 'running',
        'total': total,
        'applied': 0,
        'skipped': 0,
        'errors_count': 0,
        'current_change': None,
        'current_action': 'Iniciando...' if total > 0 else 'Sin cambios',
        'log': [],
        'result': None,
        'started_at': time.time(),
        'finished_at': None,
    }

    with _JOBS_LOCK:
        # Limpiar jobs viejos (>1 hora) para no crecer infinitamente
        now = time.time()
        for jid in list(_JOBS.keys()):
            j = _JOBS[jid]
            if j.get('finished_at') and (now - j['finished_at']) > 3600:
                del _JOBS[jid]
        _JOBS[job_id] = job

    # Import perezoso para evitar import circular
    from sync_folders import apply_sync

    def progress_callback(event, change, detail):
        """Invocada por apply_sync tras cada cambio."""
        with _JOBS_LOCK:
            j = _JOBS.get(job_id)
            if j is None:
                return
            if event == 'start':
                j['current_change'] = {
                    'type': change.get('type'),
                    'title': change.get('title'),
                    'artist': change.get('artist'),
                    'source_rel_path': change.get('source_rel_path'),
                    'target_rel_path': change.get('target_rel_path') or
                                       change.get('new_target_rel_path'),
                }
                j['current_action'] = _action_label(change)
            elif event == 'ok':
                j['applied'] += 1
                j['log'].append({
                    'status': 'ok',
                    'type': detail.get('type', change.get('type')),
                    'title': detail.get('title', change.get('title')),
                    'msg': detail.get('msg', ''),
                    'ts': time.time(),
                })
                j['current_change'] = None
                j['current_action'] = ''
            elif event == 'skipped':
                j['skipped'] += 1
                j['log'].append({
                    'status': 'skipped',
                    'type': detail.get('type', change.get('type')),
                    'title': detail.get('title', change.get('title')),
                    'msg': detail.get('msg', ''),
                    'ts': time.time(),
                })
                j['current_change'] = None
                j['current_action'] = ''
            elif event == 'error':
                j['skipped'] += 1
                j['errors_count'] += 1
                j['log'].append({
                    'status': 'error',
                    'type': detail.get('type', change.get('type')),
                    'title': detail.get('title', change.get('title')),
                    'msg': detail.get('msg', ''),
                    'ts': time.time(),
                })
                j['current_change'] = None
                j['current_action'] = ''
            # Cap del log para planes enormes
            if len(j['log']) > _MAX_LOG_EVENTS:
                # Mantener los primeros 50 + últimos 450
                j['log'] = j['log'][:50] + j['log'][-450:]

    def run_in_thread():
        """Worker que ejecuta apply_sync y actualiza el job al final."""
        try:
            result = apply_sync(plan, options, progress_callback=progress_callback)
            with _JOBS_LOCK:
                j = _JOBS.get(job_id)
                if j is not None:
                    j['result'] = result
                    j['status'] = 'done' if result.get('success', False) else 'done'
                    # Siempre 'done' (aunque haya habido errores individuales),
                    # el frontend distingue via result.success
                    j['finished_at'] = time.time()
                    j['current_change'] = None
                    j['current_action'] = ''
        except Exception as exc:
            with _JOBS_LOCK:
                j = _JOBS.get(job_id)
                if j is not None:
                    j['status'] = 'error'
                    j['result'] = {
                        'success': False,
                        'applied': 0,
                        'skipped': 0,
                        'errors': [f'Error fatal en el job: {exc}'],
                        'details': [],
                    }
                    j['finished_at'] = time.time()
                    j['current_change'] = None
                    j['current_action'] = f'Error: {exc}'

    t = threading.Thread(target=run_in_thread, daemon=True)
    t.start()
    return job_id


def get_status(job_id):
    """Devuelve el estado actual del job, o None si no existe."""
    with _JOBS_LOCK:
        j = _JOBS.get(job_id)
        if j is None:
            return None
        # Devolver copia plana (sin referencias mutables)
        return {
            'job_id': j['job_id'],
            'status': j['status'],
            'total': j['total'],
            'applied': j['applied'],
            'skipped': j['skipped'],
            'errors_count': j['errors_count'],
            'current_change': j['current_change'],
            'current_action': j['current_action'],
            'log_count': len(j['log']),
            'log_tail': j['log'][-20:],  # últimos 20 eventos para el frontend
            'finished': j['status'] in ('done', 'error'),
            'result': j['result'],
            'started_at': j['started_at'],
            'finished_at': j['finished_at'],
            'elapsed': (j['finished_at'] or time.time()) - j['started_at'],
        }


def get_full_log(job_id, limit=None):
    """Devuelve el log completo del job (o los últimos N eventos)."""
    with _JOBS_LOCK:
        j = _JOBS.get(job_id)
        if j is None:
            return None
        if limit:
            return j['log'][-limit:]
        return j['log']
