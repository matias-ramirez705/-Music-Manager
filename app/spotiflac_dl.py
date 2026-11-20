"""
app/spotiflac_dl.py (v4.0)
==========================
Wrapper del módulo SpotiFLAC (PyPI: `SpotiFLAC`) para integrarlo como
pestaña de descargas en Music Manager.

DISEÑO AUTÓNOMO:
  - Este módulo NO importa ni modifica ningún otro .py de Music Manager.
  - Solo lee LAST_SCAN desde web_app de forma defensiva (try/except)
    para no romper nada si la estructura cambia.
  - Toda la lógica de descargas corre en un hilo aparte para no
    bloquear el servidor Flask.
  - El progreso se reporta vía una cola en memoria que el frontend
    consulta por polling.

Funciones principales:
  - check_module_status(): ¿SpotiFLAC está instalado? ¿Qué versión?
  - install_module(): pip install SpotiFLAC (o upgrade)
  - check_for_updates(): compara versión local vs PyPI
  - search_tracks(query): busca canciones por nombre/artista vía Spotify
  - download_track(url, output_dir): descarga una canción
  - download_batch(urls, output_dir): descarga varias
  - list_extensions(): extensiones instaladas
  - fetch_registry(): lista extensiones disponibles en el registry configurado
  - install_extension(ext_id): instala una extensión
  - get_job_status(job_id): estado de un trabajo de descarga
"""

import os
import sys
import json
import time
import queue
import threading
import importlib
import importlib.metadata
import subprocess
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------
# Estado de trabajos de descarga (en memoria, NO toca otros módulos)
# ------------------------------------------------------------------
# Estructura: { job_id: { 'status', 'progress', 'total', 'done', 'logs': [] } }
_DOWNLOAD_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


# ------------------------------------------------------------------
# Detección del módulo SpotiFLAC
# ------------------------------------------------------------------

SPOTIFLAC_PACKAGE = 'SpotiFLAC'


# ------------------------------------------------------------------
# v4.5: soporte para modo .exe (PyInstaller)
# ------------------------------------------------------------------
# Cuando Music Manager corre como MusicManager.exe, NO puede hacer
# 'pip install' dentro de sí mismo (un .exe no tiene pip ni
# site-packages). Solución: usar un Python real del sistema para
# instalar SpotiFLAC en la carpeta <exe>/pylibs/ con --target y
# --python-version (la MISMA versión de Python que lleva el exe, para
# que las ruedas binarias de numpy/cryptography/etc. sean compatibles).


def _frozen_base_dir():
    """Carpeta del exe si corre compilado con PyInstaller, o None si
    corre desde fuente (python main.py / run.bat)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return None


def _ensure_pylibs_on_path():
    """v4.5: en modo exe, añade <exe>/pylibs al sys.path si existe.
    Así importlib.metadata y import_module encuentran SpotiFLAC."""
    base = _frozen_base_dir()
    if base is None:
        return
    pylibs = base / 'pylibs'
    if pylibs.is_dir() and str(pylibs) not in sys.path:
        sys.path.insert(0, str(pylibs))


def _system_python():
    """v4.5: devuelve el comando para ejecutar un Python REAL del sistema.

    - Modo fuente: el propio sys.executable (tiene pip y site-packages).
    - Modo exe: busca py.exe / python.exe / python3.exe, o la ruta
      guardada en la variable de entorno MM_PYTHON_EXE.
      Descarta el propio exe y los alias falsos de la Microsoft Store.

    Returns:
        list tipo ['py'] o [ruta], o None si no hay Python usable.
    """
    if _frozen_base_dir() is None:
        return [sys.executable]

    import shutil

    exe_real = Path(sys.executable).resolve()

    # 1) Ruta personalizada (el launcher puede exportarla)
    custom = os.environ.get('MM_PYTHON_EXE', '').strip()
    if custom:
        cand = Path(custom)
        if cand.is_file() and cand.resolve() != exe_real:
            return [str(cand)]

    # 2) Buscar en PATH y validar que sea un Python 3 real
    for name in ('py', 'python3', 'python'):
        found = shutil.which(name)
        if not found:
            continue
        if Path(found).resolve() == exe_real:
            continue  # es el propio exe, no sirve
        try:
            probe = subprocess.run(
                [found, '--version'], capture_output=True, text=True,
                timeout=15,
            )
            out = (probe.stdout or '') + (probe.stderr or '')
            # El alias de la Microsoft Store devuelve exit code 9009 o
            # abre la tienda; un Python real imprime 'Python 3.x.y'
            if probe.returncode == 0 and 'Python 3' in out:
                return [found]
        except Exception:
            continue
    return None


def check_module_status() -> dict:
    """
    Verifica si el módulo SpotiFLAC está instalado y devuelve su versión.

    Returns:
        dict con:
            - 'installed': bool
            - 'version': str o None
            - 'latest_version': str o None (de PyPI)
            - 'update_available': bool
            - 'error': str o None
    """
    _ensure_pylibs_on_path()  # v4.5: en modo exe, mirar también pylibs/

    result = {
        'installed': False,
        'version': None,
        'latest_version': None,
        'update_available': False,
        'error': None,
    }

    # Verificar si está instalado
    try:
        version = importlib.metadata.version(SPOTIFLAC_PACKAGE)
        result['installed'] = True
        result['version'] = version
    except importlib.metadata.PackageNotFoundError:
        result['installed'] = False
        return result
    except Exception as e:
        result['error'] = f'Error al verificar instalación: {e}'
        return result

    # Verificar última versión en PyPI
    try:
        import requests
        resp = requests.get(
            f'https://pypi.org/pypi/{SPOTIFLAC_PACKAGE}/json',
            timeout=5,
        )
        if resp.status_code == 200:
            latest = resp.json()['info']['version']
            result['latest_version'] = latest
            # Comparar versiones
            try:
                from packaging.version import Version
                if Version(version) < Version(latest):
                    result['update_available'] = True
            except Exception:
                # Fallback: comparación de strings
                if version != latest:
                    result['update_available'] = True
    except Exception as e:
        result['error'] = f'No se pudo verificar PyPI: {e}'

    return result


def install_module(upgrade: bool = False) -> dict:
    """
    Instala o actualiza el módulo SpotiFLAC vía pip.

    Args:
        upgrade: si True, usa --upgrade para actualizar a la última versión.

    Returns:
        dict con 'success', 'output', 'error'.
    """
    # v4.5: en modo exe hay que usar un Python real del sistema (el exe
    # no puede hacer pip dentro de sí mismo). Si no lo hay, error claro.
    py_cmd = _system_python()
    if py_cmd is None:
        return {
            'success': False,
            'output': '',
            'error': ('No se encontró un Python 3 instalado en el sistema. '
                      'Instálalo desde python.org (activa "Add python.exe to '
                      'PATH") y vuelve a intentarlo. La pestana Spotiflac DL '
                      'lo necesita para instalar el módulo en pylibs/.'),
        }

    base = _frozen_base_dir()
    cmd = list(py_cmd)
    cmd += ['-m', 'pip', 'install']
    if upgrade:
        cmd.append('--upgrade')
    if base is not None:
        # v4.5: instalar en <exe>/pylibs con la MISMA versión de Python
        # del exe y solo ruedas binarias compatibles (numpy, cryptography,
        # pydantic-core... son específicas por versión de Python).
        cmd += [
            '--target', str(base / 'pylibs'),
            '--python-version', f'{sys.version_info[0]}.{sys.version_info[1]}',
            '--implementation', 'cp',
            '--only-binary=:all:',
        ]
    cmd.append(SPOTIFLAC_PACKAGE)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutos máximo
        )
        # v4.5: Invalidar cache de importlib.metadata para que el próximo
        # check_module_status() detecte la nueva instalación sin necesidad
        # de reiniciar el servidor Python.
        try:
            _ensure_pylibs_on_path()  # v4.5: que pylibs/ sea importable YA
            importlib.invalidate_caches()
            # v4.4: Si el módulo ya estaba importado en sys.modules, lo eliminamos
            # para que la próxima llamada lo recargue con la versión nueva.
            # Esto es seguro porque AsyncSpotiFLAC se instancia por descarga,
            # no queda referencediado entre llamadas.
            for key in list(sys.modules.keys()):
                if key == SPOTIFLAC_PACKAGE or key.startswith(SPOTIFLAC_PACKAGE + '.'):
                    del sys.modules[key]
        except Exception:
            pass
        # v4.4: verificar que la instalación funcionó de verdad
        # (importlib.metadata.version puede seguir devolviendo la vieva versión
        # en algunos entornos, así que forzamos la verificación)
        verify_version = None
        try:
            importlib.invalidate_caches()
            verify_version = importlib.metadata.version(SPOTIFLAC_PACKAGE)
        except importlib.metadata.PackageNotFoundError:
            verify_version = None
        return {
            'success': result.returncode == 0 and verify_version is not None,
            'output': result.stdout[-3000:] if result.stdout else '',
            'error': result.stderr[-3000:] if result.stderr else '',
            'returncode': result.returncode,
            'installed_version': verify_version,
            # v4.4: flag para que el JS sepa que debe recargar la página
            'needs_page_reload': result.returncode == 0 and verify_version is not None,
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Timeout: la instalación tardó más de 5 minutos.',
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': f'Error: {e}',
        }


# ------------------------------------------------------------------
# Acceso al módulo SpotiFLAC (importación diferida)
# ------------------------------------------------------------------

def _get_spotiflac_module():
    """Importa el módulo SpotiFLAC de forma diferida.
    Lanza ImportError si no está instalado."""
    _ensure_pylibs_on_path()  # v4.5: en modo exe, mirar también pylibs/
    try:
        # importlib.import_module evita problemas de path
        mod = importlib.import_module('SpotiFLAC')
        # v4.4: silenciar el logger de SpotiFLAC para que no inunde el CMD
        # con logs de debug que hacen que la página se demore al recargar.
        try:
            import logging
            logging.getLogger('SpotiFLAC').setLevel(logging.WARNING)
            # También silenciar sub-loggers comunes
            for name in ['SpotiFLAC.downloader', 'SpotiFLAC.extensions',
                         'SpotiFLAC.core', 'SpotiFLAC.client']:
                logging.getLogger(name).setLevel(logging.WARNING)
        except Exception:
            pass
        return mod
    except ImportError as e:
        raise ImportError(
            f'El módulo SpotiFLAC no está instalado. '
            f'Ejecuta: pip install {SPOTIFLAC_PACKAGE}'
        ) from e


def _get_async_client(output_dir: str, services: list = None, quality: str = 'LOSSLESS'):
    """Crea una instancia de AsyncSpotiFLAC.
    Returns el cliente (NO entra al context manager todavía)."""
    mod = _get_spotiflac_module()
    client_cls = getattr(mod, 'AsyncSpotiFLAC')
    kwargs = {
        'output_dir': output_dir,
        'services': services or ['ext:tidal-web'],
        'quality': quality,
        'embed_lyrics': True,
        'enrich_metadata': True,
    }
    return client_cls(**kwargs)


# ------------------------------------------------------------------
# Búsqueda de canciones
# ------------------------------------------------------------------

def search_tracks(query: str, limit: int = 20) -> dict:
    """
    Busca canciones en Spotify por nombre/artista.

    Args:
        query: texto a buscar (ej: "After Hours Poorchoice")
        limit: máximo de resultados (default 20)

    Returns:
        dict con 'results' (lista de tracks) y 'error'.
    """
    try:
        mod = _get_spotiflac_module()
        # SpotifyMetadataClient es el cliente de búsqueda
        # Lo importamos del submódulo core.spotify_metadata
        try:
            from SpotiFLAC.core.spotify_metadata import SpotifyMetadataClient
        except ImportError:
            # Fallback: intentar importarlo como atributo del módulo
            client_cls = getattr(mod, 'SpotifyMetadataClient', None)
            if client_cls is None:
                return {
                    'results': [],
                    'error': 'SpotifyMetadataClient no disponible en esta versión de SpotiFLAC.'
                }
            client = client_cls()
        else:
            client = SpotifyMetadataClient()

        # search_async es el método asíncrono
        import asyncio
        async def _do_search():
            return await client.search_async(query, limit=limit)
        results = asyncio.run(_do_search())

        # Normalizar: results es dict con 'tracks', 'albums', etc.
        tracks = results.get('tracks', []) if isinstance(results, dict) else []
        # Convertir a dict simple para JSON
        out = []
        for t in tracks:
            # TrackMetadata es un pydantic Model, usar model_dump o dict()
            try:
                d = t.model_dump() if hasattr(t, 'model_dump') else t.__dict__
            except Exception:
                d = {'title': str(t)}
            # Limpiar campos para JSON
            clean = {
                'id': d.get('id', ''),
                'title': d.get('title', ''),
                'artists': d.get('artists', d.get('artist', '')),
                'album': d.get('album', ''),
                'duration_ms': d.get('duration_ms', 0),
                'isrc': d.get('isrc', ''),
                'cover_url': d.get('cover_url', ''),
                'external_url': d.get('external_url', ''),
                'preview_url': d.get('preview_url', ''),
                'is_explicit': d.get('is_explicit', False),
            }
            out.append(clean)

        return {'results': out, 'error': None}

    except ImportError as e:
        return {'results': [], 'error': str(e)}
    except Exception as e:
        return {'results': [], 'error': f'Error inesperado: {e}'}


# ------------------------------------------------------------------
# Gestión de extensiones
# ------------------------------------------------------------------

def list_extensions() -> dict:
    """
    Lista las extensiones instaladas en el sistema.

    Returns:
        dict con 'extensions' (lista) y 'error'.
    """
    try:
        from SpotiFLAC.extensions import ExtensionManager
        em = ExtensionManager()
        installed = em.list_installed()
        out = []
        for ext in installed:
            out.append({
                'id': ext.name,
                'display_name': ext.display_name,
                'version': ext.version,
                'description': ext.description,
                'runtime': getattr(ext, 'runtime', 'javascript'),
                'types': getattr(ext, 'types', []),
            })
        return {'extensions': out, 'error': None}
    except ImportError as e:
        return {'extensions': [], 'error': str(e)}
    except Exception as e:
        return {'extensions': [], 'error': f'Error: {e}'}


def fetch_registry() -> dict:
    """
    Lista las extensiones disponibles en el registry configurado.

    Returns:
        dict con 'extensions' (lista) y 'error'.
    """
    try:
        from SpotiFLAC.extensions import ExtensionManager
        em = ExtensionManager()
        entries = em.fetch_registry()
        out = []
        for e in entries:
            out.append({
                'id': e.id,
                'display_name': e.display_name,
                'version': e.version,
                'description': e.description,
                'category': e.category,
                'tags': e.tags,
                'download_url': e.download_url,
                'icon_url': e.icon_url,
            })
        return {'extensions': out, 'error': None}
    except ImportError as e:
        return {'extensions': [], 'error': str(e)}
    except Exception as e:
        return {'extensions': [], 'error': f'Error: {e}'}


def install_extension(ext_id: str) -> dict:
    """
    Instala una extensión por ID desde el registry configurado.

    Args:
        ext_id: ID de la extensión (ej: 'tidal-web').

    Returns:
        dict con 'success', 'extension', 'error'.
    """
    try:
        from SpotiFLAC.extensions import ExtensionManager
        em = ExtensionManager()
        installed = em.install(ext_id)
        return {
            'success': True,
            'extension': {
                'id': installed.name,
                'display_name': installed.display_name,
                'version': installed.version,
            },
            'error': None,
        }
    except ImportError as e:
        return {'success': False, 'extension': None, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'extension': None, 'error': f'Error: {e}'}


def remove_extension(ext_id: str) -> dict:
    """Elimina una extensión instalada."""
    try:
        from SpotiFLAC.extensions import ExtensionManager
        em = ExtensionManager()
        # v4.4: el método se llama uninstall, no remove.
        # Antes llamábamos em.remove(ext_id) que lanzaba AttributeError.
        em.uninstall(ext_id)
        return {'success': True, 'error': None}
    except ImportError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': f'Error: {e}'}


# ------------------------------------------------------------------
# Descargas (asíncronas con tracking de progreso)
# ------------------------------------------------------------------

def start_download_job(urls: list, output_dir: str,
                       services: list = None,
                       quality: str = 'LOSSLESS') -> dict:
    """
    Inicia un trabajo de descarga en un hilo aparte.

    Args:
        urls: lista de URLs de Spotify (track/album/playlist).
        output_dir: carpeta de destino.
        services: lista de servicios (ej: ['ext:tidal-web']).
        quality: calidad solicitada.

    Returns:
        dict con 'job_id' y 'error'.
    """
    # v4.4: verificar explícitamente que SpotiFLAC está instalado ANTES de
    # crear el job. Si no, el job se creaba pero fallaba silenciosamente.
    try:
        importlib.metadata.version(SPOTIFLAC_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return {
            'job_id': None,
            'error': 'El módulo SpotiFLAC no está instalado. Hacé clic en "Instalar" en la parte superior.',
        }
    # v4.4: verificar que se pueda importar el módulo (no solo que esté en metadata)
    try:
        _get_spotiflac_module()
    except ImportError as e:
        return {
            'job_id': None,
            'error': f'No se pudo importar SpotiFLAC: {e}',
        }

    import uuid
    job_id = str(uuid.uuid4())[:8]

    with _JOBS_LOCK:
        _DOWNLOAD_JOBS[job_id] = {
            'status': 'pending',
            'progress': 0,
            'total': len(urls),
            'done': 0,
            'failed': 0,
            'logs': [f'Trabajo creado: {len(urls)} URL(s) a descargar'],
            'output_dir': output_dir,
            'started_at': time.time(),
            'finished_at': None,
            'results': [],  # lista de {url, success, file_path, error}
        }

    # Arrancar hilo
    thread = threading.Thread(
        target=_run_download_job,
        args=(job_id, urls, output_dir, services, quality),
        daemon=True,
    )
    thread.start()

    return {'job_id': job_id, 'error': None}


def _run_download_job(job_id: str, urls: list, output_dir: str,
                      services: list, quality: str):
    """Ejecuta el trabajo de descarga en un hilo. No devuelve nada;
    actualiza el estado en _DOWNLOAD_JOBS."""
    def log(msg):
        with _JOBS_LOCK:
            job = _DOWNLOAD_JOBS.get(job_id)
            if job:
                job['logs'].append(f'[{time.strftime("%H:%M:%S")}] {msg}')
                # Mantener solo las últimas 200 líneas
                if len(job['logs']) > 200:
                    job['logs'] = job['logs'][-200:]

    try:
        with _JOBS_LOCK:
            _DOWNLOAD_JOBS[job_id]['status'] = 'running'

        log(f'Iniciando descarga en {output_dir}')
        log(f'Servicios: {services or ["ext:tidal-web"]}')
        log(f'Calidad: {quality}')

        # Importar AsyncSpotiFLAC
        mod = _get_spotiflac_module()
        async_client_cls = getattr(mod, 'AsyncSpotiFLAC')

        import asyncio

        async def _do_download():
            async with async_client_cls(
                output_dir=output_dir,
                services=services or ['ext:tidal-web'],
                quality=quality,
                embed_lyrics=True,
                enrich_metadata=True,
                # v4.3: configuración más robusta para evitar timeouts
                timeout_s=240,              # 4 minutos por track (antes era ilimitado pero la extensión tenía 120s interno)
                track_max_retries=2,        # 2 reintentos por track si falla
                use_extensions_fallback=True,  # probar otra extensión si una falla
                max_concurrent_downloads=1, # 1 a la vez para no saturar la red
            ) as client:
                for i, url in enumerate(urls):
                    log(f'[{i+1}/{len(urls)}] Descargando: {url}')
                    try:
                        failed = await client.download_track(url)
                        with _JOBS_LOCK:
                            job = _DOWNLOAD_JOBS.get(job_id)
                            if job:
                                job['done'] += 1
                                job['progress'] = int((job['done'] / job['total']) * 100)
                                if failed:
                                    job['failed'] += len(failed)
                                    job['results'].append({
                                        'url': url,
                                        'success': False,
                                        'error': f'{len(failed)} track(s) fallaron',
                                    })
                                    log(f'  ⚠ {len(failed)} track(s) fallaron')
                                else:
                                    job['results'].append({
                                        'url': url,
                                        'success': True,
                                        'file_path': output_dir,
                                    })
                                    log(f'  ✓ Descarga completada')
                    except Exception as e:
                        log(f'  ✗ Error: {e}')
                        with _JOBS_LOCK:
                            job = _DOWNLOAD_JOBS.get(job_id)
                            if job:
                                job['done'] += 1
                                job['failed'] += 1
                                job['results'].append({
                                    'url': url,
                                    'success': False,
                                    'error': str(e),
                                })

        asyncio.run(_do_download())

        with _JOBS_LOCK:
            job = _DOWNLOAD_JOBS.get(job_id)
            if job:
                job['status'] = 'completed'
                job['finished_at'] = time.time()
                log(f'Trabajo completado: {job["done"]}/{job["total"]} ({job["failed"]} fallidos)')

    except ImportError as e:
        with _JOBS_LOCK:
            job = _DOWNLOAD_JOBS.get(job_id)
            if job:
                job['status'] = 'error'
                job['error'] = str(e)
                job['finished_at'] = time.time()
                log(f'Error: {e}')
    except Exception as e:
        with _JOBS_LOCK:
            job = _DOWNLOAD_JOBS.get(job_id)
            if job:
                job['status'] = 'error'
                job['error'] = str(e)
                job['finished_at'] = time.time()
                log(f'Error inesperado: {e}')


def get_job_status(job_id: str) -> dict:
    """Devuelve el estado actual de un trabajo de descarga."""
    with _JOBS_LOCK:
        job = _DOWNLOAD_JOBS.get(job_id)
        if not job:
            return {'error': 'Trabajo no encontrado'}
        # Devolver copia para no mutar mientras se serializa
        return {
            'job_id': job_id,
            'status': job['status'],
            'progress': job['progress'],
            'total': job['total'],
            'done': job['done'],
            'failed': job['failed'],
            'logs': job['logs'][-50:],  # últimas 50 líneas
            'results': job['results'],
            'output_dir': job['output_dir'],
            'started_at': job['started_at'],
            'finished_at': job['finished_at'],
            'error': job.get('error'),
        }


def list_jobs() -> dict:
    """Lista todos los trabajos (activos y completados)."""
    with _JOBS_LOCK:
        jobs = []
        for jid, job in _DOWNLOAD_JOBS.items():
            jobs.append({
                'job_id': jid,
                'status': job['status'],
                'progress': job['progress'],
                'total': job['total'],
                'done': job['done'],
                'failed': job['failed'],
                'started_at': job['started_at'],
                'finished_at': job['finished_at'],
                'output_dir': job['output_dir'],
            })
        # Ordenar por started_at descendente
        jobs.sort(key=lambda j: j['started_at'], reverse=True)
        return {'jobs': jobs}


def clear_completed_jobs() -> dict:
    """Elimina de la memoria los trabajos que ya terminaron (completed o error).
    Los trabajos activos (pending/running) NO se eliminan."""
    with _JOBS_LOCK:
        before = len(_DOWNLOAD_JOBS)
        to_remove = [
            jid for jid, job in _DOWNLOAD_JOBS.items()
            if job['status'] in ('completed', 'error')
        ]
        for jid in to_remove:
            del _DOWNLOAD_JOBS[jid]
        after = len(_DOWNLOAD_JOBS)
        return {'success': True, 'removed': before - after, 'remaining': after}


# ------------------------------------------------------------------
# Acceso al LAST_SCAN de web_app (defensivo, no rompe nada)
# ------------------------------------------------------------------

def get_last_scan_files() -> list:
    """
    Obtiene la lista de archivos del último escaneo de Mi Música.
    Importación defensiva: si web_app no tiene LAST_SCAN o cambia de
    estructura, devolvemos lista vacía en vez de romper.

    Returns:
        list[dict]: lista de archivos del escaneo.
    """
    try:
        # web_app está en sys.modules si la app ya está corriendo
        web_app = sys.modules.get('web_app')
        if web_app is None:
            return []
        last_scan = getattr(web_app, 'LAST_SCAN', None)
        if last_scan is None:
            return []
        return list(last_scan.get('files', []))
    except Exception:
        return []


def get_saved_playlists() -> list:
    """
    Obtiene la lista de playlists guardadas (de saved_playlists.py).
    Importación defensiva.

    Returns:
        list[dict]: [{id, name, platform, track_count, url}, ...]
    """
    try:
        from saved_playlists import list_playlists
        playlists = list_playlists()
        out = []
        for p in playlists:
            out.append({
                'id': p.get('id', ''),
                'name': p.get('name', ''),
                'platform': p.get('platform', ''),
                'track_count': len(p.get('tracks', [])),
                'url': p.get('url', ''),
                'uploader': p.get('uploader', ''),
            })
        return out
    except Exception as e:
        return []


def get_playlist_tracks(playlist_id: str) -> dict:
    """
    Obtiene las canciones de una playlist guardada y las cruza con
    la música local para saber cuáles faltan descargar.

    Returns:
        dict con 'tracks', 'missing', 'matched', 'total', 'error'.
    """
    try:
        from saved_playlists import get_playlist
        from duplicates import normalize_text
        p = get_playlist(playlist_id)
        if not p:
            return {'error': 'Playlist no encontrada'}

        tracks = p.get('tracks', [])
        # Cruzar con música local
        local_files = get_last_scan_files()
        local_index = {}
        for f in local_files:
            key = normalize_text(f.get('name', ''))
            if key:
                local_index.setdefault(key, []).append(f)

        out_tracks = []
        missing = 0
        matched = 0
        for t in tracks:
            t_norm = normalize_text(t.get('title', ''))
            is_downloaded = bool(local_index.get(t_norm))
            if is_downloaded:
                matched += 1
            else:
                missing += 1
            out_tracks.append({
                'title': t.get('title', ''),
                'artist': t.get('artist', ''),
                'album': t.get('album', ''),
                'duration': t.get('duration', 0),
                'url': t.get('url', ''),
                'isrc': t.get('isrc', ''),
                'is_downloaded': is_downloaded,
            })

        return {
            'playlist': {
                'id': p.get('id', ''),
                'name': p.get('name', ''),
                'platform': p.get('platform', ''),
                'url': p.get('url', ''),
                'track_count': len(tracks),
            },
            'tracks': out_tracks,
            'missing': missing,
            'matched': matched,
            'total': len(tracks),
            'error': None,
        }
    except Exception as e:
        return {'error': f'Error: {e}'}


# ------------------------------------------------------------------
# Gestión del archivo .env (configuración de registry)
# ------------------------------------------------------------------

# Registry oficial de SpotiFLAC (compatible con módulo Python)
DEFAULT_REGISTRY_URL = 'https://raw.githubusercontent.com/spotiflacapp/SpotiFLAC-Extension/main/registry.json'


def _get_env_path() -> Path:
    """Devuelve la ruta del archivo .env en la carpeta del proyecto.
    SpotiFLAC busca .env en Path.cwd() (directorio de trabajo actual)."""
    # Path.cwd() es la carpeta desde donde se ejecuta python main.py
    # Que debería ser la carpeta raíz de music_manager
    return Path.cwd() / '.env'


def get_registry_config() -> dict:
    """
    Devuelve el estado de la configuración del registry.

    Returns:
        dict con:
            - 'env_exists': bool
            - 'env_path': str (ruta absoluta del .env)
            - 'registries': list[str] (URLs configuradas, vacío si ninguna)
            - 'is_configured': bool (True si hay al menos 1 registry)
            - 'env_content': str (contenido completo del .env, para mostrar en UI)
            - 'error': str o None
    """
    env_path = _get_env_path()
    result = {
        'env_exists': env_path.exists(),
        'env_path': str(env_path),
        'registries': [],
        'is_configured': False,
        'env_content': '',
        'default_registry': DEFAULT_REGISTRY_URL,
        'error': None,
    }

    # También leer SPOTIFLAC_REGISTRIES del entorno del SO (por si lo setearon así)
    env_var = os.environ.get('SPOTIFLAC_REGISTRIES', '')
    if env_var:
        urls = [u.strip() for u in env_var.split(',') if u.strip()]
        result['registries'] = urls
        result['is_configured'] = len(urls) > 0
        result['env_content'] = f'# (Variable de entorno del SO)\nSPOTIFLAC_REGISTRIES={env_var}'
        return result

    if not env_path.exists():
        return result

    try:
        content = env_path.read_text(encoding='utf-8')
        result['env_content'] = content
        # Parsear el archivo buscando SPOTIFLAC_REGISTRIES=
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('SPOTIFLAC_REGISTRIES='):
                _, val = line.split('=', 1)
                urls = [u.strip() for u in val.split(',') if u.strip()]
                result['registries'] = urls
                result['is_configured'] = len(urls) > 0
                break
    except Exception as e:
        result['error'] = f'Error al leer .env: {e}'

    return result


def save_registry_config(registries: list, extra_config: str = '') -> dict:
    """
    Guarda la configuración del registry en el archivo .env.

    Args:
        registries: lista de URLs de registry.
        extra_config: texto adicional para añadir al .env (opcional).

    Returns:
        dict con 'success', 'env_path', 'error'.
    """
    env_path = _get_env_path()
    try:
        content = f'''# ============================================
# Configuración de SpotiFLAC para Music Manager
# ============================================
# Este archivo .env es leído automáticamente por el módulo SpotiFLAC
# cuando se ejecuta desde esta carpeta.

# Registry de extensiones (puedes poner varios separados por comas)
SPOTIFLAC_REGISTRIES={','.join(registries)}

# ============================================
# Configuración opcional (descomenta lo que necesites)
# ============================================

# Carpeta personalizada para extensiones (por defecto: ~/.spotiflac/extensions)
# SPOTIFLAC_EXT_DIR=C:\\Users\\TU_USUARIO\\.spotiflac\\extensions

# Qobuz local API (si tienes una instancia propia):
# QOBUZ_LOCAL_API_URL=http://localhost:8000

'''
        if extra_config:
            content += f'\n# Configuración adicional\n{extra_config}\n'

        env_path.write_text(content, encoding='utf-8')
        return {
            'success': True,
            'env_path': str(env_path),
            'error': None,
        }
    except Exception as e:
        return {
            'success': False,
            'env_path': str(env_path),
            'error': f'Error al guardar .env: {e}',
        }


def save_default_registry() -> dict:
    """Guarda el registry oficial de SpotiFLAC en el .env.
    Atajo para el botón "Configurar automáticamente" de la UI."""
    return save_registry_config([DEFAULT_REGISTRY_URL])
