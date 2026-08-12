"""
app/web_app.py
==============
Servidor web con Flask que expone la interfaz de Music Manager v1.1
en http://127.0.0.1:5000

Rutas (paginas):
  GET  /                  -> Pestaña 1: Lista de musica local
  GET  /saved             -> Pestaña 2: Playlists guardadas (NUEVA)
  GET  /compare           -> Pestaña 3: Comparar con playlist
  GET  /editor            -> Pestaña 4: Editor de metadata

APIs:
  POST /api/scan              -> Escanea carpeta
  GET  /api/last-scan         -> Ultimo escaneo
  GET  /api/browse            -> Dialogo nativo seleccion carpeta
  GET  /api/browse-file       -> Dialogo nativo seleccion archivo
  POST /api/fetch-playlist    -> Descarga playlist (YTMusic/Spotify)
  POST /api/compare           -> Compara local con playlist
  POST /api/export-missing    -> Exporta faltantes como CSV

  # Saved playlists (NUEVAS)
  GET  /api/saved-playlists   -> Lista playlists guardadas
  POST /api/save-playlist     -> Guarda playlist (url + data)
  POST /api/saved-playlist/<id> -> Detalle de una playlist
  POST /api/saved-playlist/<id>/refresh -> Refrescar canciones
  POST /api/saved-playlist/<id>/rename  -> Renombrar
  POST /api/saved-playlist/<id>/delete  -> Eliminar

  # Duplicados (NUEVAS)
  POST /api/duplicates        -> Encuentra canciones duplicadas

  # Metadata multi-fuente (AMPLIADA)
  POST /api/auto-search       -> Busca en iTunes/MusicBrainz/Last.fm
  POST /api/save-metadata     -> Guarda metadata en archivo
  POST /api/file-metadata     -> Lee metadata de un archivo

  # Caratulas (NUEVAS)
  GET  /api/artwork?path=...  -> Devuelve la caratula embebida como imagen
  POST /api/artwork/save      -> Incrusta caratula nueva (subida o URL)
  POST /api/artwork/resize    -> Redimensiona caratula embebida
  POST /api/artwork/remove    -> Elimina caratula
  POST /api/artwork/download  -> Descarga imagen desde URL (preview)

  # Reproductor (NUEVO)
  GET  /api/audio?path=...    -> Stream del archivo de audio
"""

import os
import csv
import io
import base64
from pathlib import Path

from flask import (Flask, request, jsonify, render_template,
                   send_file, Response, abort)

# Importar modulos de la app
from scanner import scan_folder, count_by_format, human_size
from metadata_reader import read_metadata, write_metadata
from audio_quality import build_quality_summary, format_duration
from playlist_youtube import fetch_youtube_playlist
from playlist_spotify import fetch_spotify_playlist
from auto_metadata import search_track, best_match
from saved_playlists import (
    list_playlists, save_playlist, get_playlist,
    delete_playlist, update_playlist, refresh_playlist,
    build_local_playlist_index,
)
from duplicates import find_duplicates, normalize_text
from artwork import (extract_artwork, save_artwork, resize_image,
                     download_image, remove_artwork)


# ------------------------------------------------------------------
# Estado global en memoria (ultimo escaneo).
# ------------------------------------------------------------------
LAST_SCAN = {
    'folder': '',
    'files': [],
    'count_by_format': {},
    'total_size': 0,
}


def create_app():
    """Fabrica de la aplicacion Flask."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent / 'templates'),
        static_folder=str(Path(__file__).parent.parent / 'static'),
    )

    # ==================================================================
    # RUTAS DE PAGINAS
    # ==================================================================

    @app.route('/')
    def index():
        """Pestaña 1: Lista de musica local."""
        return render_template('index.html', active_tab='local')

    @app.route('/duplicates')
    def duplicates():
        """Pestaña: Duplicados."""
        return render_template('duplicates.html', active_tab='duplicates')

    @app.route('/saved')
    def saved():
        """Pestaña 2: Playlists guardadas."""
        return render_template('saved_playlists.html', active_tab='saved')

    @app.route('/compare')
    def compare():
        """Pestaña 3: Comparacion con playlist."""
        return render_template('compare.html', active_tab='compare')

    @app.route('/editor')
    def editor():
        """Pestaña 4: Editor de metadata."""
        return render_template('editor.html', active_tab='editor')

    @app.route('/organize')
    def organize():
        """Pestaña 5: Organizar por playlist."""
        return render_template('organize.html', active_tab='organize')

    @app.route('/downloads')
    def downloads():
        """Pestaña 6: Index de sitios para descargar FLAC."""
        return render_template('downloads.html', active_tab='downloads')

    # ==================================================================
    # API: ESCANEO
    # ==================================================================

    @app.route('/api/scan', methods=['POST'])
    def api_scan():
        """Escanea carpeta y devuelve lista enriquecida."""
        data = request.get_json(silent=True) or {}
        folder = data.get('folder', '').strip()

        if not folder:
            return jsonify({'error': 'Debes indicar una carpeta.'}), 400
        if not os.path.exists(folder):
            return jsonify({'error': f'La carpeta no existe: {folder}'}), 400
        if not os.path.isdir(folder):
            return jsonify({'error': f'No es una carpeta: {folder}'}), 400

        raw_files = scan_folder(folder)

        # Construir indice de playlists guardadas para marcar en que
        # playlist esta cada cancion local.
        playlist_index = build_local_playlist_index()

        enriched = []
        total_size = 0
        for f in raw_files:
            meta = read_metadata(f['path'])
            quality = build_quality_summary(meta)
            total_size += f['size']

            # Buscar en que playlists aparece esta cancion
            title_norm = normalize_text(meta['title'] or f['name'])
            in_playlists = playlist_index.get(title_norm, [])

            enriched.append({
                'path': f['path'],
                'name': meta['title'] or f['name'],
                'artist': meta['artist'],
                'album': meta['album'],
                'duration': meta['duration'],
                'duration_str': format_duration(meta['duration']),
                'ext': f['ext'].lstrip('.'),
                'size': f['size'],
                'size_str': human_size(f['size']),
                'parent': f['parent'],
                'quality': quality,
                'has_error': meta.get('error') is not None,
                'playlists': in_playlists,  # [{id, name, platform}, ...]
            })

        LAST_SCAN['folder'] = folder
        LAST_SCAN['files'] = enriched
        LAST_SCAN['count_by_format'] = count_by_format(raw_files)
        LAST_SCAN['total_size'] = total_size

        return jsonify({
            'count': len(enriched),
            'files': enriched,
            'stats': LAST_SCAN['count_by_format'],
            'total_size': total_size,
            'total_size_str': human_size(total_size),
            'folder': folder,
        })

    @app.route('/api/last-scan', methods=['GET'])
    def api_last_scan():
        """Devuelve el ultimo escaneo sin re-escanear."""
        return jsonify({
            'folder': LAST_SCAN['folder'],
            'count': len(LAST_SCAN['files']),
            'files': LAST_SCAN['files'],
            'stats': LAST_SCAN['count_by_format'],
            'total_size': LAST_SCAN['total_size'],
            'total_size_str': human_size(LAST_SCAN['total_size']),
        })

    @app.route('/api/browse', methods=['GET'])
    def api_browse():
        """Dialogo nativo de Windows para seleccionar carpeta."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder = filedialog.askdirectory(
                title='Selecciona la carpeta de musica',
                initialdir=os.path.expanduser('~')
            )
            root.destroy()
            return jsonify({'folder': folder or ''})
        except Exception as e:
            return jsonify({'error': str(e), 'folder': ''}), 500

    @app.route('/api/browse-file', methods=['GET'])
    def api_browse_file():
        """Dialogo nativo para seleccionar archivo de audio."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            filepath = filedialog.askopenfilename(
                title='Selecciona un archivo de audio',
                filetypes=[
                    ('Audio', '*.mp3 *.flac *.wav *.m4a *.aac *.ogg *.opus *.alac *.ape *.wv *.aiff'),
                    ('Todos los archivos', '*.*'),
                ],
                initialdir=os.path.expanduser('~')
            )
            root.destroy()
            return jsonify({'path': filepath or ''})
        except Exception as e:
            return jsonify({'error': str(e), 'path': ''}), 500

    @app.route('/api/reveal-in-explorer', methods=['POST'])
    def api_reveal_in_explorer():
        """
        Abre el explorador de archivos del sistema en la carpeta que
        contiene el archivo especificado, con el archivo seleccionado.

        Body JSON:
            { "path": "C:\\Music\\cancion.mp3" }

        En Windows usa: explorer /select,"path"
        En macOS usa: open -R "path"
        En Linux usa: xdg-open "dir" (no puede pre-seleccionar archivo)
        """
        import subprocess
        import platform
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False,
                            'message': 'Archivo no existe.'}), 400

        try:
            system = platform.system()
            if system == 'Windows':
                # explorer /select abre la carpeta con el archivo seleccionado
                # Necesitamos usar el path con backslashes dobles
                # subprocess.list2cmdline maneja el escaping
                subprocess.Popen(['explorer', '/select,', file_path])
            elif system == 'Darwin':  # macOS
                subprocess.Popen(['open', '-R', file_path])
            else:  # Linux y otros
                # xdg-open no soporta pre-seleccionar, abrimos la carpeta
                folder = os.path.dirname(file_path)
                subprocess.Popen(['xdg-open', folder])
            return jsonify({'success': True,
                            'message': 'Explorador abierto.'})
        except Exception as e:
            return jsonify({'success': False,
                            'message': f'Error: {str(e)}'}), 500

    # ==================================================================
    # API: PLAYLIST (fetch directo)
    # ==================================================================

    def _fetch_playlist_by_url(url):
        """Helper: detecta plataforma y devuelve playlist_data."""
        if 'spotify.com' in url or 'spotify:' in url:
            return 'spotify', fetch_spotify_playlist(url)
        elif 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube', fetch_youtube_playlist(url)
        elif url.startswith('PL') or url.startswith('OLAK') or url.startswith('RD'):
            return 'youtube', fetch_youtube_playlist(url)
        return None, {'error': 'URL no reconocida.'}

    @app.route('/api/fetch-playlist', methods=['POST'])
    def api_fetch_playlist():
        """Descarga playlist desde YT Music o Spotify."""
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'Debes indicar una URL.'}), 400

        platform, result = _fetch_playlist_by_url(url)
        if result.get('error'):
            return jsonify(result), 400
        # Anadir platform para que el frontend lo use
        result['platform'] = platform
        return jsonify(result)

    @app.route('/api/import-csv-playlist', methods=['POST'])
    def api_import_csv_playlist():
        """
        Importa una playlist desde un CSV exportado de Exportify
        (https://exportify.app/).

        Acepta:
          - multipart/form-data con campo 'file' (upload de archivo)
          - application/json con campo 'csv_content' (contenido del CSV)

        Returns:
            JSON con la playlist parseada (mismo formato que fetch-playlist).
        """
        from csv_playlist import parse_exportify_csv

        # Caso 1: upload de archivo (multipart/form-data)
        if 'file' in request.files:
            file = request.files['file']
            if not file.filename:
                return jsonify({'error': 'No se selecciono archivo.'}), 400
            # Leer contenido
            content = file.read().decode('utf-8-sig', errors='replace')
            name = request.form.get('name') or Path(file.filename).stem
            result = parse_exportify_csv(content, name=name)
            if result.get('error'):
                return jsonify(result), 400
            result['platform'] = 'spotify'  # CSV de Exportify siempre es Spotify
            return jsonify(result)

        # Caso 2: JSON con contenido del CSV
        data = request.get_json(silent=True) or {}
        csv_content = data.get('csv_content', '')
        name = data.get('name', 'Playlist CSV')
        if not csv_content:
            return jsonify({'error': 'No se recibio contenido CSV.'}), 400
        result = parse_exportify_csv(csv_content, name=name)
        if result.get('error'):
            return jsonify(result), 400
        result['platform'] = 'spotify'
        return jsonify(result)

    @app.route('/api/compare', methods=['POST'])
    def api_compare():
        """Compara lista local con playlist (URL, CSV de Exportify, o playlist guardada)."""
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()
        csv_content = data.get('csv_content', '').strip()
        csv_name = data.get('name', 'Playlist CSV')
        if not url and not csv_content:
            return jsonify({'error': 'Debes indicar una URL o subir un CSV.'}), 400
        if not LAST_SCAN['files']:
            return jsonify({'error': 'Primero escanea tu musica local en "Mi Musica".'}), 400

        # Caso 1: CSV subido directamente (contenido del CSV)
        if csv_content:
            from csv_playlist import parse_exportify_csv
            playlist = parse_exportify_csv(csv_content, name=csv_name)
            platform = 'spotify'
        # Caso 2: URL csv:// (playlist CSV guardada previamente)
        elif url.startswith('csv://'):
            # Buscar la playlist en el storage por URL
            from saved_playlists import _load_all
            all_data = _load_all()
            playlist = None
            for p in all_data['playlists']:
                if p.get('url') == url:
                    playlist = {
                        'title': p['name'],
                        'uploader': p.get('uploader', ''),
                        'tracks': p.get('tracks', []),
                        'count': len(p.get('tracks', [])),
                        'error': None,
                    }
                    break
            if not playlist:
                return jsonify({'error': 'Playlist CSV guardada no encontrada. Puede que haya sido eliminada.'}), 400
            platform = 'spotify'
        # Caso 3: URL normal (YouTube Music o Spotify)
        else:
            platform, playlist = _fetch_playlist_by_url(url)
        if playlist.get('error'):
            return jsonify({'error': playlist['error']}), 400

        local_index = {}
        for f in LAST_SCAN['files']:
            key = normalize_text(f['name'])
            local_index.setdefault(key, []).append(f)

        missing = []
        matched = []
        for track in playlist['tracks']:
            t_norm = normalize_text(track['title'])
            a_norm = normalize_text(track['artist'])

            # Buscar coincidencia exacta (titulo + artista)
            exact_match = None
            for f in LAST_SCAN['files']:
                if t_norm == normalize_text(f['name']) and a_norm == normalize_text(f['artist']):
                    exact_match = f
                    break

            if exact_match:
                matched.append({
                    **track,
                    'match_type': 'exact',
                    'local_path': exact_match['path'],
                    'local_quality': exact_match.get('quality', {}).get('label', 'N/A'),
                    'local_format': exact_match.get('ext', '').upper(),
                    'local_name': exact_match.get('name', ''),
                    'local_artist': exact_match.get('artist', ''),
                })
                continue

            if t_norm and t_norm in local_index:
                candidates = local_index[t_norm]
                local_artists = [normalize_text(c['artist']) for c in candidates]
                artist_match = any(
                    a_norm and (a_norm in la or la in a_norm)
                    for la in local_artists
                )
                if artist_match:
                    # Tomar el primer candidato que coincida
                    local_file = next((c for c in candidates
                                       if a_norm and (a_norm in normalize_text(c['artist'])
                                                      or normalize_text(c['artist']) in a_norm)),
                                      candidates[0])
                    matched.append({
                        **track,
                        'match_type': 'artist_partial',
                        'local_path': local_file['path'],
                        'local_quality': local_file.get('quality', {}).get('label', 'N/A'),
                        'local_format': local_file.get('ext', '').upper(),
                        'local_name': local_file.get('name', ''),
                        'local_artist': local_file.get('artist', ''),
                    })
                else:
                    # title_only: hay candidatos pero no coinciden artista
                    local_file = candidates[0]
                    matched.append({
                        **track,
                        'match_type': 'title_only',
                        'local_path': local_file['path'],
                        'local_quality': local_file.get('quality', {}).get('label', 'N/A'),
                        'local_format': local_file.get('ext', '').upper(),
                        'local_name': local_file.get('name', ''),
                        'local_artist': local_file.get('artist', ''),
                    })
                continue
            missing.append(track)

        return jsonify({
            'platform': platform,
            'playlist': {
                'title': playlist['title'],
                'uploader': playlist['uploader'],
                'count': playlist['count'],
                'url': url,
                'warning': playlist.get('warning'),
                'total_expected': playlist.get('total_expected'),
            },
            'missing': missing,
            'matched': matched,
            'total_local': len(LAST_SCAN['files']),
            'progress': round(len(matched) / max(1, playlist['count']) * 100, 1),
        })

    @app.route('/api/export-missing', methods=['POST'])
    def api_export_missing():
        """Exporta lista de faltantes como CSV descargable."""
        data = request.get_json(silent=True) or {}
        missing = data.get('missing', [])
        if not missing:
            return jsonify({'error': 'No hay canciones faltantes.'}), 400

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Titulo', 'Artista', 'Album', 'Duracion (s)', 'URL'])
        for t in missing:
            writer.writerow([
                t.get('title', ''), t.get('artist', ''),
                t.get('album', ''), round(t.get('duration', 0), 1),
                t.get('url', ''),
            ])
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig'))
        mem.seek(0)
        return send_file(mem, as_attachment=True,
                         download_name='canciones_faltantes.csv',
                         mimetype='text/csv')

    # ==================================================================
    # API: PLAYLISTS GUARDADAS (NUEVAS)
    # ==================================================================

    @app.route('/api/spotify-status', methods=['GET'])
    def api_spotify_status():
        """
        Devuelve el estado de la configuracion de Spotify.
        Util para mostrar un banner en la UI si no esta configurado.
        """
        try:
            from spotify_official import is_configured, has_user_login, get_auth_mode
            return jsonify({
                'configured': is_configured(),
                'user_logged_in': has_user_login(),
                'auth_mode': get_auth_mode(),
            })
        except ImportError:
            return jsonify({
                'configured': False,
                'user_logged_in': False,
                'auth_mode': None,
            })

    @app.route('/api/spotify-login/start', methods=['POST'])
    def api_spotify_login_start():
        """Inicia el flujo de OAuth. Devuelve la URL de autorizacion."""
        from spotify_official import start_user_login
        result = start_user_login()
        return jsonify(result)

    @app.route('/api/spotify-login/finish', methods=['POST'])
    def api_spotify_login_finish():
        """Completa el flujo OAuth con la URL de callback del navegador."""
        data = request.get_json(silent=True) or {}
        callback_url = data.get('callback_url', '')
        if not callback_url:
            return jsonify({'error': 'Falta callback_url'}), 400
        from spotify_official import finish_user_login
        result = finish_user_login(callback_url)
        return jsonify(result)

    @app.route('/api/spotify-login/logout', methods=['POST'])
    def api_spotify_login_logout():
        """Elimina el cache de token de usuario."""
        from spotify_official import logout_user
        logout_user()
        return jsonify({'success': True})

    @app.route('/api/saved-playlists', methods=['GET'])
    def api_saved_list():
        """Lista todas las playlists guardadas."""
        return jsonify({'playlists': list_playlists()})

    @app.route('/api/save-playlist', methods=['POST'])
    def api_save_playlist():
        """
        Guarda una playlist desde una URL (descarga + persiste) o desde
        un CSV de Exportify (si el body incluye csv_content).
        """
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()
        csv_content = data.get('csv_content', '').strip()
        csv_name = data.get('name', 'Playlist CSV')

        # Caso CSV (Exportify)
        if csv_content:
            from csv_playlist import parse_exportify_csv
            playlist = parse_exportify_csv(csv_content, name=csv_name)
            if playlist.get('error'):
                return jsonify({'error': playlist['error']}), 400
            # Usar un "url" sintetico para identificarla en el storage
            synthetic_url = f"csv://{csv_name}"
            saved = save_playlist('spotify', synthetic_url, playlist)
            return jsonify({
                'saved': saved,
                'warning': None,
                'total_expected': playlist.get('total_expected'),
            })

        # Caso URL (YT Music o Spotify)
        if not url:
            return jsonify({'error': 'Debes indicar una URL o subir un CSV.'}), 400

        platform, playlist = _fetch_playlist_by_url(url)
        if playlist.get('error'):
            return jsonify({'error': playlist['error']}), 400

        saved = save_playlist(platform, url, playlist)
        return jsonify({
            'saved': saved,
            'warning': playlist.get('warning'),
            'total_expected': playlist.get('total_expected'),
        })

    @app.route('/api/import-txt-playlists', methods=['POST'])
    def api_import_txt_playlists():
        """
        Importa playlists desde un archivo TXT que contiene URLs
        (una por linea) con soporte para comentarios (lineas con #).

        Body JSON:
            { "content": "# comentario\nhttps://..." }

        Tambien procesa rutas a archivos CSV locales.

        Returns:
            JSON con:
                - 'results': [{url, platform, success, name, track_count, error}]
                - 'success_count': N
                - 'error_count': N
        """
        data = request.get_json(silent=True) or {}
        content = data.get('content', '')

        if not content.strip():
            return jsonify({'error': 'El archivo TXT está vacío.'}), 400

        from txt_playlist import parse_txt_file
        from csv_playlist import parse_exportify_csv

        entries = parse_txt_file(content)
        if not entries:
            return jsonify({
                'error': 'No se encontraron URLs de playlists ni rutas CSV en el archivo. Recuerda: las líneas con # son comentarios.'
            }), 400

        results = []
        success_count = 0
        error_count = 0

        for entry in entries:
            entry_type = entry['type']
            url = entry['url']
            line_num = entry['line']

            result = {
                'url': url,
                'type': entry_type,
                'line': line_num,
                'success': False,
                'name': '',
                'track_count': 0,
                'error': '',
            }

            try:
                if entry_type == 'csv':
                    # Cargar archivo CSV local
                    csv_path = url
                    if not os.path.exists(csv_path):
                        result['error'] = f'Archivo CSV no encontrado: {csv_path}'
                        error_count += 1
                        results.append(result)
                        continue

                    with open(csv_path, 'r', encoding='utf-8-sig') as f:
                        csv_content = f.read()

                    csv_name = Path(csv_path).stem
                    playlist = parse_exportify_csv(csv_content, name=csv_name)
                    if playlist.get('error'):
                        result['error'] = playlist['error']
                        error_count += 1
                        results.append(result)
                        continue

                    synthetic_url = f"csv://{csv_name}"
                    saved = save_playlist('spotify', synthetic_url, playlist)
                    result['success'] = True
                    result['name'] = saved.get('name', csv_name)
                    result['track_count'] = saved.get('track_count', 0)
                    success_count += 1

                else:
                    # URL de YouTube Music o Spotify
                    platform, playlist = _fetch_playlist_by_url(url)
                    if playlist.get('error'):
                        result['error'] = playlist['error'][:200]
                        error_count += 1
                        results.append(result)
                        continue

                    saved = save_playlist(platform, url, playlist)
                    result['success'] = True
                    result['name'] = saved.get('name', '')
                    result['track_count'] = saved.get('track_count', 0)
                    result['platform'] = platform
                    if playlist.get('warning'):
                        result['warning'] = playlist['warning']
                    success_count += 1

            except Exception as e:
                result['error'] = str(e)[:200]
                error_count += 1

            results.append(result)

        return jsonify({
            'results': results,
            'success_count': success_count,
            'error_count': error_count,
            'total': len(entries),
        })

    @app.route('/api/txt-playlists/load', methods=['GET'])
    def api_txt_playlists_load():
        """Lee el archivo data/playlists.txt si existe."""
        from txt_playlist import load_default_txt
        content = load_default_txt()
        if content is None:
            return jsonify({'exists': False, 'content': ''})
        return jsonify({'exists': True, 'content': content})

    @app.route('/api/txt-playlists/save', methods=['POST'])
    def api_txt_playlists_save():
        """Guarda el contenido en data/playlists.txt."""
        data = request.get_json(silent=True) or {}
        content = data.get('content', '')
        from txt_playlist import save_default_txt
        if save_default_txt(content):
            return jsonify({'success': True, 'message': 'Archivo guardado en data/playlists.txt'})
        return jsonify({'success': False, 'message': 'No se pudo guardar.'}), 500

    @app.route('/api/saved-playlist/<playlist_id>', methods=['GET'])
    def api_saved_detail(playlist_id):
        """Devuelve una playlist guardada completa (con tracks)."""
        p = get_playlist(playlist_id)
        if not p:
            return jsonify({'error': 'Playlist no encontrada.'}), 404
        return jsonify(p)

    @app.route('/api/saved-playlist/<playlist_id>/refresh', methods=['POST'])
    def api_saved_refresh(playlist_id):
        """Refresca las canciones de una playlist guardada."""
        p = get_playlist(playlist_id)
        if not p:
            return jsonify({'error': 'Playlist no encontrada.'}), 404
        platform, playlist = _fetch_playlist_by_url(p['url'])
        if playlist.get('error'):
            return jsonify({'error': playlist['error']}), 400
        updated = refresh_playlist(playlist_id, playlist)
        return jsonify({'saved': updated})

    @app.route('/api/saved-playlist/<playlist_id>/rename', methods=['POST'])
    def api_saved_rename(playlist_id):
        """Renombra una playlist guardada."""
        data = request.get_json(silent=True) or {}
        new_name = data.get('name', '').strip()
        if not new_name:
            return jsonify({'error': 'Nombre vacio.'}), 400
        updated = update_playlist(playlist_id, {'name': new_name})
        if not updated:
            return jsonify({'error': 'Playlist no encontrada.'}), 404
        return jsonify({'saved': updated})

    @app.route('/api/saved-playlist/<playlist_id>/delete', methods=['POST'])
    def api_saved_delete(playlist_id):
        """Elimina una playlist guardada."""
        ok = delete_playlist(playlist_id)
        if not ok:
            return jsonify({'error': 'Playlist no encontrada.'}), 404
        return jsonify({'deleted': True})

    # ==================================================================
    # API: DUPLICADOS (NUEVAS)
    # ==================================================================

    @app.route('/api/duplicates', methods=['POST'])
    def api_duplicates():
        """Encuentra canciones duplicadas en el ultimo escaneo."""
        data = request.get_json(silent=True) or {}
        match_by = data.get('match_by', 'title_artist')

        if not LAST_SCAN['files']:
            return jsonify({
                'groups': [],
                'total_duplicates': 0,
                'total_groups': 0,
                'space_reclaimable': 0,
                'space_reclaimable_str': '0 B',
                'total_local': 0,
            })

        result = find_duplicates(LAST_SCAN['files'], match_by=match_by)
        return jsonify({
            **result,
            'space_reclaimable_str': human_size(result['space_reclaimable']),
            'total_local': len(LAST_SCAN['files']),
        })

    # ==================================================================
    # API: METADATA MULTI-FUENTE (AMPLIADA)
    # ==================================================================

    @app.route('/api/auto-search', methods=['POST'])
    def api_auto_search():
        """Busca metadata en la fuente seleccionada."""
        data = request.get_json(silent=True) or {}
        title = data.get('title', '')
        artist = data.get('artist', '')
        source = data.get('source', 'itunes')  # itunes | musicbrainz | lastfm | all

        if not title:
            return jsonify({'error': 'Se necesita al menos el titulo.'}), 400

        results = search_track(title, artist, limit=5, source=source)
        if not results:
            return jsonify({'results': [], 'best': None,
                            'message': 'No se encontraron coincidencias.'})

        best = best_match(results, target_title=title, target_artist=artist)
        return jsonify({'results': results, 'best': best})

    @app.route('/api/save-metadata', methods=['POST'])
    def api_save_metadata():
        """Guarda metadata en un archivo."""
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        metadata = data.get('metadata', {})
        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False,
                            'message': 'Archivo no encontrado.'}), 400
        ok = write_metadata(file_path, metadata)
        if ok:
            return jsonify({'success': True, 'message': 'Metadata guardada correctamente.'})
        return jsonify({'success': False, 'message': 'No se pudo escribir.'}), 500

    @app.route('/api/file-metadata', methods=['POST'])
    def api_file_metadata():
        """Lee metadata actual de un archivo."""
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Archivo no encontrado.'}), 400
        meta = read_metadata(file_path)
        quality = build_quality_summary(meta)
        # Anadir size y ext para mostrar en info tecnica
        try:
            file_size = os.path.getsize(file_path)
            meta['size'] = file_size
            meta['size_str'] = human_size(file_size)
        except OSError:
            meta['size_str'] = 'N/A'
        meta['ext'] = Path(file_path).suffix.lstrip('.').lower()
        return jsonify({**meta, 'quality': quality})

    @app.route('/api/rename-file', methods=['POST'])
    def api_rename_file():
        """
        Renombra un archivo de audio en el disco.

        Body JSON:
            { "old_path": "...", "new_path": "..." }

        Returns:
            JSON: { 'success': bool, 'message': str, 'new_path': str }
        """
        import shutil
        data = request.get_json(silent=True) or {}
        old_path = data.get('old_path', '')
        new_path = data.get('new_path', '')

        if not old_path or not new_path:
            return jsonify({'success': False, 'message': 'Faltan rutas.'}), 400
        if not os.path.exists(old_path):
            return jsonify({'success': False, 'message': 'Archivo original no existe.'}), 400
        if old_path == new_path:
            return jsonify({'success': False, 'message': 'Las rutas son iguales.'}), 400
        if os.path.exists(new_path):
            return jsonify({'success': False,
                            'message': 'Ya existe un archivo con ese nombre.'}), 400

        try:
            os.rename(old_path, new_path)
            return jsonify({
                'success': True,
                'message': 'Archivo renombrado.',
                'new_path': new_path,
            })
        except OSError as e:
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

    @app.route('/api/delete-file', methods=['POST'])
    def api_delete_file():
        """
        Elimina un archivo de audio del disco (lo manda a la papelera
        si hay send2trash, sino os.remove directo).

        Tambien lo quita de LAST_SCAN para que no siga apareciendo en
        Duplicados y Mi Musica despues de recargar.

        Body JSON:
            { "path": "..." }

        Returns:
            JSON: { 'success': bool, 'message': str }
        """
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')

        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'Archivo no existe.'}), 400

        # Intentar mandar a papelera de reciclaje (mas seguro)
        deleted_method = None
        try:
            import send2trash
            send2trash.send2trash(file_path)
            deleted_method = 'recycle'
        except ImportError:
            # send2trash no instalado: borrar directo
            try:
                os.remove(file_path)
                deleted_method = 'permanent'
            except OSError as e:
                return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
        except Exception as e:
            # Si send2trash falla, intentar con os.remove
            try:
                os.remove(file_path)
                deleted_method = 'permanent'
            except OSError as e2:
                return jsonify({'success': False, 'message': f'Error: {str(e2)}'}), 500

        # Si se elimino correctamente, quitarlo de LAST_SCAN
        if deleted_method:
            before = len(LAST_SCAN['files'])
            LAST_SCAN['files'] = [f for f in LAST_SCAN['files']
                                  if f.get('path') != file_path]
            after = len(LAST_SCAN['files'])
            # Actualizar total_size
            if before != after:
                LAST_SCAN['total_size'] = sum(f.get('size', 0) for f in LAST_SCAN['files'])

            msg = ('Archivo enviado a la papelera de reciclaje.'
                   if deleted_method == 'recycle'
                   else 'Archivo eliminado.')
            return jsonify({
                'success': True,
                'message': msg,
                'method': deleted_method,
                'removed_from_scan': before != after,
            })
        return jsonify({'success': False, 'message': 'No se pudo eliminar.'}), 500

    # ==================================================================
    # API: CARATULAS (NUEVAS)
    # ==================================================================

    @app.route('/api/artwork', methods=['GET'])
    def api_artwork_get():
        """
        Devuelve la caratula embebida como imagen directa.
        Uso: <img src="/api/artwork?path=...">
        """
        file_path = request.args.get('path', '')
        if not file_path or not os.path.exists(file_path):
            abort(404)

        artwork = extract_artwork(file_path)
        if not artwork:
            # Devolver imagen placeholder 1x1 transparente
            transparent = base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
            )
            return Response(transparent, mimetype='image/png')

        return Response(artwork['data'], mimetype=artwork['mime'])

    @app.route('/api/artwork/info', methods=['POST'])
    def api_artwork_info():
        """Devuelve info de la caratula embebida (sin la imagen)."""
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Archivo no encontrado.'}), 400
        artwork = extract_artwork(file_path)
        if not artwork:
            return jsonify({'has_artwork': False})
        return jsonify({
            'has_artwork': True,
            'mime': artwork['mime'],
            'width': artwork['width'],
            'height': artwork['height'],
            'size_kb': artwork['size_kb'],
        })

    @app.route('/api/artwork/save', methods=['POST'])
    def api_artwork_save():
        """
        Guarda una caratula nueva en el archivo.
        Body JSON:
            { 'path': '...', 'image_data': '<base64>', 'mime': 'image/jpeg' }
        o
            { 'path': '...', 'image_url': 'https://...' }
        """
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'Archivo no encontrado.'}), 400

        if data.get('image_url'):
            downloaded = download_image(data['image_url'])
            if not downloaded:
                return jsonify({'success': False,
                                'message': 'No se pudo descargar la imagen.'}), 400
            image_bytes = downloaded['data']
            mime = downloaded['mime']
        elif data.get('image_data'):
            try:
                image_bytes = base64.b64decode(data['image_data'])
            except Exception:
                return jsonify({'success': False,
                                'message': 'image_data no es base64 valido.'}), 400
            mime = data.get('mime', 'image/jpeg')
        else:
            return jsonify({'success': False,
                            'message': 'Falta image_data o image_url.'}), 400

        ok, msg = save_artwork(file_path, image_bytes, mime)
        return jsonify({'success': ok, 'message': msg})

    @app.route('/api/artwork/resize', methods=['POST'])
    def api_artwork_resize():
        """Redimensiona la caratula embebida actual."""
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        max_size = int(data.get('max_size', 600))
        fmt = data.get('fmt', 'JPEG')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'Archivo no encontrado.'}), 400

        artwork = extract_artwork(file_path)
        if not artwork:
            return jsonify({'success': False, 'message': 'El archivo no tiene caratula.'}), 400

        resized = resize_image(artwork['data'], max_size=max_size, fmt=fmt, quality=85)
        mime = 'image/jpeg' if fmt.upper() == 'JPEG' else f'image/{fmt.lower()}'
        ok, msg = save_artwork(file_path, resized, mime)
        return jsonify({'success': ok, 'message': msg})

    @app.route('/api/artwork/remove', methods=['POST'])
    def api_artwork_remove():
        """Elimina la caratula embebida."""
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'Archivo no encontrado.'}), 400
        ok, msg = remove_artwork(file_path)
        return jsonify({'success': ok, 'message': msg})

    @app.route('/api/artwork/download', methods=['POST'])
    def api_artwork_download_preview():
        """
        Descarga una imagen desde URL y la devuelve como base64
        (para preview en la UI antes de guardarla).
        """
        data = request.get_json(silent=True) or {}
        url = data.get('url', '')
        if not url:
            return jsonify({'error': 'Falta url.'}), 400

        downloaded = download_image(url)
        if not downloaded:
            return jsonify({'error': 'No se pudo descargar.'}), 400

        b64 = base64.b64encode(downloaded['data']).decode('ascii')
        return jsonify({
            'image_data': b64,
            'mime': downloaded['mime'],
            'size_kb': downloaded['size_kb'],
        })

    # ==================================================================
    # API: ORGANIZADOR (NUEVO v1.12)
    # ==================================================================

    @app.route('/api/organizer/preview', methods=['POST'])
    def api_organizer_preview():
        """
        Genera un plan de movimientos para organizar canciones por playlist.

        Body JSON:
            {
                "base_dir": "C:\\Users\\Matias\\Music\\Orden",
                "options": {
                    "move_unmatched": false,
                    "duplicate_policy": "ask"  // ask|first|all|none
                }
            }

        Returns:
            JSON con el plan completo (ver organizer.build_move_plan).
        """
        data = request.get_json(silent=True) or {}
        base_dir = data.get('base_dir', '').strip()
        options = data.get('options', {}) or {}
        options['files'] = LAST_SCAN['files']

        from organizer import build_move_plan
        plan = build_move_plan(base_dir, options)
        return jsonify(plan)

    @app.route('/api/organizer/move', methods=['POST'])
    def api_organizer_move():
        """
        Ejecuta los movimientos del plan.

        Body JSON:
            {
                "base_dir": "C:\\Users\\Matias\\Music\\Orden",
                "moves": [ ... ]  // lista de movimientos con action y new_path
            }

        Returns:
            JSON con resultado (ver organizer.execute_move_plan).
        """
        data = request.get_json(silent=True) or {}
        base_dir = data.get('base_dir', '').strip()
        moves = data.get('moves', [])

        if not base_dir:
            return jsonify({'error': 'Falta base_dir.'}), 400
        if not moves:
            return jsonify({'error': 'No hay movimientos que ejecutar.'}), 400

        from organizer import execute_move_plan
        result = execute_move_plan(moves, base_dir)

        # Si se movieron archivos, actualizar LAST_SCAN quitandolos
        # (los que se copiaron siguen existiendo en su lugar original)
        moved_paths = set()
        for m in moves:
            if m.get('action') == 'move' and m.get('current_path'):
                moved_paths.add(m['current_path'])

        if moved_paths:
            before = len(LAST_SCAN['files'])
            LAST_SCAN['files'] = [f for f in LAST_SCAN['files']
                                  if f.get('path') not in moved_paths]
            after = len(LAST_SCAN['files'])
            result['removed_from_scan'] = before - after

        return jsonify(result)

    # ==================================================================
    # API: REPRODUCTOR (NUEVO)
    # ==================================================================

    @app.route('/api/audio-blob', methods=['POST'])
    def api_audio_blob():
        """
        Devuelve el archivo de audio completo como blob (POST).
        El path va en el body JSON, evitando problemas de codificacion
        de URLs con caracteres especiales (backslashes Windows,
        acentos, caracteres no Latin-1, etc.).

        Para archivos muy grandes (>50MB) esto carga todo en memoria;
        si necesitas streaming con seek, usar /api/audio (GET).
        """
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Archivo no encontrado'}), 404

        ext = Path(file_path).suffix.lower()
        mime_map = {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.opus': 'audio/opus',
        }
        mime = mime_map.get(ext, 'application/octet-stream')

        try:
            return send_file(file_path, mimetype=mime)
        except Exception as e:
            return jsonify({'error': f'No se pudo leer: {str(e)}'}), 500

    @app.route('/api/audio')
    def api_audio():
        """
        Streaming del archivo de audio con range requests para seek.
        Se mantiene para compatibilidad pero el JS usa /api/audio-blob
        por defecto (mas robusto ante caracteres especiales).
        """
        file_path = request.args.get('path', '')
        if not file_path or not os.path.exists(file_path):
            app.logger.warning(f"Audio 404 - path no existe: {file_path!r}")
            abort(404)

        # Determinar MIME segun extension
        ext = Path(file_path).suffix.lower()
        mime_map = {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.opus': 'audio/opus',
        }
        mime = mime_map.get(ext, 'application/octet-stream')

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            abort(404)

        # Range request para seek en el reproductor
        range_header = request.headers.get('Range', None)
        if range_header:
            # Parsear "bytes=start-end"
            import re
            m = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else file_size - 1
                length = end - start + 1

                def generate():
                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(64 * 1024, remaining))
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk

                resp = Response(generate(), status=206, mimetype=mime)
                resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                resp.headers['Accept-Ranges'] = 'bytes'
                resp.headers['Content-Length'] = str(length)
                return resp

        # Sin range: enviar archivo completo
        def generate_full():
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk

        resp = Response(generate_full(), status=200, mimetype=mime)
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(file_size)
        return resp

    # ==================================================================
    # API: SITIOS DE DESCARGA FLAC (NUEVO v2.0)
    # ==================================================================

    @app.route('/api/download-sites', methods=['GET'])
    def api_download_sites_list():
        """Devuelve la lista de sitios del archivo download_sites.txt."""
        from download_sites import load_sites
        return jsonify({'sites': load_sites()})

    @app.route('/api/download-sites/save', methods=['POST'])
    def api_download_sites_save():
        """Guarda la lista de sitios en download_sites.txt."""
        data = request.get_json(silent=True) or {}
        sites = data.get('sites', [])
        from download_sites import save_sites
        save_sites(sites)
        return jsonify({'success': True, 'message': 'Sitios guardados en data/download_sites.txt'})

    @app.route('/api/download-sites/file', methods=['GET'])
    def api_download_sites_file():
        """Devuelve el contenido raw del archivo download_sites.txt."""
        from download_sites import SITES_FILE
        if not SITES_FILE.exists():
            return jsonify({'exists': False, 'content': ''})
        with open(SITES_FILE, 'r', encoding='utf-8') as f:
            return jsonify({'exists': True, 'content': f.read()})

    @app.route('/api/download-sites/file', methods=['POST'])
    def api_download_sites_file_save():
        """Guarda contenido raw en download_sites.txt."""
        data = request.get_json(silent=True) or {}
        content = data.get('content', '')
        from download_sites import SITES_FILE, DATA_DIR
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SITES_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': 'Archivo guardado.'})

    @app.route('/api/download-sites/add', methods=['POST'])
    def api_download_sites_add():
        """
        Agrega un sitio nuevo al final del archivo download_sites.txt.
        Verifica que el enlace no exista ya para evitar duplicados.

        Body JSON:
            { "name": "...", "link": "...", "description": "...", "status": "OK" }
        """
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        link = data.get('link', '').strip()
        description = data.get('description', '').strip()
        status = data.get('status', 'OK').strip().upper()

        if not name or not link:
            return jsonify({'error': 'Nombre y enlace son obligatorios.'}), 400
        if status not in ('OK', 'CAIDO'):
            status = 'OK'

        from download_sites import load_sites, SITES_FILE

        # Verificar si el enlace ya existe (comparar sin trailing slashes)
        existing = load_sites()
        link_normalized = link.rstrip('/').lower()
        for s in existing:
            if s['link'].rstrip('/').lower() == link_normalized:
                return jsonify({
                    'error': f'El enlace ya existe en la lista: "{s["name"]}"'
                }), 400

        # Agregar al archivo (append)
        SITES_FILE.parent.mkdir(parents=True, exist_ok=True)
        line = f"| {name} | {link} | {description} | {status} |\n"
        with open(SITES_FILE, 'a', encoding='utf-8') as f:
            f.write(line)

        return jsonify({
            'success': True,
            'message': f'Sitio "{name}" agregado al final de la lista.',
        })

    return app
