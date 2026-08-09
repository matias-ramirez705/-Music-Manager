"""
app/web_app.py
==============
Servidor web con Flask que expone la interfaz de Music Manager
en http://127.0.0.1:5000

Rutas:
  GET  /                  -> Pestaña 1: Lista de musica local
  GET  /compare           -> Pestaña 2: Comparar con playlist
  GET  /editor            -> Pestaña 3: Editor de metadata

  POST /api/scan          -> Escanea una carpeta y devuelve JSON con la lista
  POST /api/fetch-playlist-> Descarga playlist de YT Music o Spotify
  POST /api/compare       -> Compara lista local con playlist
  POST /api/auto-search   -> Busca metadata en iTunes para un archivo
  POST /api/save-metadata -> Guarda metadata en un archivo
  GET  /api/browse        -> Abre dialogo nativo para seleccionar carpeta

La aplicacion mantiene el estado en memoria (variable global LAST_SCAN)
para no tener que re-escanear entre pestañas.
"""

import os
import csv
import io
import threading
from pathlib import Path

from flask import Flask, request, jsonify, render_template, send_file

# Importar nuestros modulos
from scanner import scan_folder, count_by_format, human_size
from metadata_reader import read_metadata, write_metadata
from audio_quality import build_quality_summary, format_duration
from playlist_youtube import fetch_youtube_playlist
from playlist_spotify import fetch_spotify_playlist
from auto_metadata import search_track, best_match


# ------------------------------------------------------------------
# Estado global en memoria.
# En una app multi-usuario esto seria un problema, pero como es
# una herramienta personal local, esta bien.
# ------------------------------------------------------------------
LAST_SCAN = {
    'folder': '',           # ultima carpeta escaneada
    'files': [],            # lista de archivos con metadata
    'count_by_format': {},  # ej: {'.flac': 23, '.mp3': 145}
    'total_size': 0,        # bytes totales
}


def create_app():
    """
    Fabrica de la aplicacion Flask.
    Configura rutas y devuelve la instancia lista para arrancar.
    """
    # template_folder y static_folder son relativos a este archivo.
    # Como web_app.py esta en app/, subimos un nivel con ../
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent / 'templates'),
        static_folder=str(Path(__file__).parent.parent / 'static'),
    )

    # ---------------- RUTAS DE PAGINAS ----------------

    @app.route('/')
    def index():
        """Pestaña 1: Lista de musica local."""
        return render_template('index.html', active_tab='local')

    @app.route('/compare')
    def compare():
        """Pestaña 2: Comparacion con playlist."""
        return render_template('compare.html', active_tab='compare')

    @app.route('/editor')
    def editor():
        """Pestaña 3: Editor de metadata."""
        return render_template('editor.html', active_tab='editor')

    # ---------------- API: ESCANEO ----------------

    @app.route('/api/scan', methods=['POST'])
    def api_scan():
        """
        Escanea una carpeta y devuelve la lista de archivos.

        Body JSON:
            { "folder": "C:\\Music\\..." }

        Returns:
            JSON con:
              - 'count': numero total
              - 'files': lista de archivos con metadata
              - 'stats': conteo por formato
              - 'total_size': bytes totales
        """
        data = request.get_json(silent=True) or {}
        folder = data.get('folder', '').strip()

        if not folder:
            return jsonify({'error': 'Debes indicar una carpeta.'}), 400

        if not os.path.exists(folder):
            return jsonify({'error': f'La carpeta no existe: {folder}'}), 400

        if not os.path.isdir(folder):
            return jsonify({'error': f'No es una carpeta: {folder}'}), 400

        # 1. Escanear archivos
        raw_files = scan_folder(folder)

        # 2. Leer metadata + calidad para cada archivo
        enriched = []
        total_size = 0
        for f in raw_files:
            meta = read_metadata(f['path'])
            quality = build_quality_summary(meta)
            total_size += f['size']
            enriched.append({
                'path': f['path'],
                'name': meta['title'] or f['name'],
                'artist': meta['artist'],
                'album': meta['album'],
                'duration': meta['duration'],
                'duration_str': format_duration(meta['duration']),
                'ext': f['ext'].lstrip('.'),   # 'flac' en vez de '.flac'
                'size': f['size'],
                'size_str': human_size(f['size']),
                'parent': f['parent'],
                'quality': quality,
                'has_error': meta.get('error') is not None,
            })

        # 3. Guardar estado para otras rutas (comparacion, editor)
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
        """Devuelve el ultimo escaneo realizado (sin re-escanear)."""
        return jsonify({
            'folder': LAST_SCAN['folder'],
            'count': len(LAST_SCAN['files']),
            'files': LAST_SCAN['files'],
            'stats': LAST_SCAN['count_by_format'],
            'total_size': LAST_SCAN['total_size'],
            'total_size_str': human_size(LAST_SCAN['total_size']),
        })

    # ---------------- API: BROWSE CARPETA ----------------

    @app.route('/api/browse', methods=['GET'])
    def api_browse():
        """
        Abre el dialogo nativo de Windows para seleccionar carpeta.
        Usa tkinter que viene incluido con Python en Windows.

        Returns:
            JSON: { 'folder': 'C:\\...' } o { 'folder': '' } si cancelo.
        """
        try:
            # Import diferido: tkinter no esta en todos los entornos Linux
            import tkinter as tk
            from tkinter import filedialog

            # Crear ventana oculta (no aparece en pantalla)
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)

            # Mostrar dialogo nativo
            folder = filedialog.askdirectory(
                title='Selecciona la carpeta de musica',
                initialdir=os.path.expanduser('~')
            )

            root.destroy()

            return jsonify({'folder': folder or ''})

        except Exception as e:
            return jsonify({'error': str(e), 'folder': ''}), 500

    # ---------------- API: PLAYLIST ----------------

    @app.route('/api/fetch-playlist', methods=['POST'])
    def api_fetch_playlist():
        """
        Descarga una playlist desde YouTube Music o Spotify.
        Detecta automaticamente la plataforma segun la URL.

        Body JSON:
            { "url": "https://..." }

        Returns:
            JSON con la playlist (titulo, autor, canciones).
        """
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()

        if not url:
            return jsonify({'error': 'Debes indicar una URL.'}), 400

        # Detectar plataforma
        if 'spotify.com' in url or 'spotify:' in url:
            result = fetch_spotify_playlist(url)
        elif 'youtube.com' in url or 'youtu.be' in url:
            result = fetch_youtube_playlist(url)
        elif url.startswith('PL') or url.startswith('OLAK') or url.startswith('RD'):
            # Asumir YouTube Music si es solo un ID
            result = fetch_youtube_playlist(url)
        else:
            return jsonify({'error': 'URL no reconocida. Debe ser de YouTube Music o Spotify.'}), 400

        return jsonify(result)

    # ---------------- API: COMPARAR ----------------

    @app.route('/api/compare', methods=['POST'])
    def api_compare():
        """
        Compara la lista local (ultimo escaneo) con una playlist.

        Body JSON:
            { "url": "https://..." }

        Returns:
            JSON con:
              - 'missing': canciones de la playlist que NO estan localmente
              - 'matched': canciones que SI estan localmente
              - 'playlist': info de la playlist
              - 'total_local': cantidad de archivos locales
        """
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()

        if not url:
            return jsonify({'error': 'Debes indicar una URL.'}), 400

        if not LAST_SCAN['files']:
            return jsonify({'error': 'Primero escanea tu musica local en la pestana "Mi Musica".'}), 400

        # 1. Descargar playlist
        if 'spotify.com' in url or 'spotify:' in url:
            playlist = fetch_spotify_playlist(url)
        else:
            playlist = fetch_youtube_playlist(url)

        if playlist.get('error'):
            return jsonify({'error': playlist['error']}), 400

        # 2. Normalizar nombres locales para comparacion
        #    (minusculas, sin acentos, sin parentesis, sin "feat.")
        def normalize(s):
            import unicodedata
            if not s:
                return ''
            # Quitar acentos: NFD + eliminar diacriticos
            s = unicodedata.normalize('NFD', s)
            s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
            # Minusculas
            s = s.lower()
            # Quitar texto entre parentesis
            import re
            s = re.sub(r'\([^)]*\)', '', s)
            s = re.sub(r'\[[^)]*\]', '', s)
            # Quitar "feat.", "ft.", "&"
            s = re.sub(r'\b(feat|ft)\b\.?', '', s)
            # Quitar puntuacion y espacios extra
            s = re.sub(r'[^a-z0-9\s]', '', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        local_keys = set()
        local_index = {}
        for f in LAST_SCAN['files']:
            # Clave compuesta: titulo + artista (ambos normalizados)
            key = (normalize(f['name']), normalize(f['artist']))
            local_keys.add(key)
            # Tambien guardar solo por titulo (por si el artista difiere)
            local_index.setdefault(normalize(f['name']), []).append(f)

        missing = []
        matched = []

        for track in playlist['tracks']:
            t_norm = normalize(track['title'])
            a_norm = normalize(track['artist'])

            # Coincidencia exacta (titulo + artista)
            if (t_norm, a_norm) in local_keys:
                matched.append({**track, 'match_type': 'exact'})
                continue

            # Coincidencia por titulo solo
            if t_norm and t_norm in local_index:
                # Verificar similitud de artista
                candidates = local_index[t_norm]
                local_artists = [normalize(c['artist']) for c in candidates]
                # Coincidencia parcial: el artista local contiene o esta contenido
                artist_match = any(
                    a_norm and (a_norm in la or la in a_norm)
                    for la in local_artists
                )
                if artist_match:
                    matched.append({**track, 'match_type': 'artist_partial'})
                else:
                    matched.append({**track, 'match_type': 'title_only'})
                continue

            # No encontrado -> falta
            missing.append(track)

        return jsonify({
            'playlist': {
                'title': playlist['title'],
                'uploader': playlist['uploader'],
                'count': playlist['count'],
            },
            'missing': missing,
            'matched': matched,
            'total_local': len(LAST_SCAN['files']),
            'progress': round(len(matched) / max(1, playlist['count']) * 100, 1),
        })

    @app.route('/api/export-missing', methods=['POST'])
    def api_export_missing():
        """
        Exporta la lista de canciones faltantes como archivo CSV.
        El navegador lo descarga automaticamente.

        Body JSON:
            { "missing": [ {title, artist, ...}, ... ] }
        """
        data = request.get_json(silent=True) or {}
        missing = data.get('missing', [])

        if not missing:
            return jsonify({'error': 'No hay canciones faltantes para exportar.'}), 400

        # Crear CSV en memoria
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Titulo', 'Artista', 'Album', 'Duracion (s)', 'URL'])
        for t in missing:
            writer.writerow([
                t.get('title', ''),
                t.get('artist', ''),
                t.get('album', ''),
                round(t.get('duration', 0), 1),
                t.get('url', ''),
            ])

        # Convertir a bytes para enviar como archivo
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig'))  # BOM para Excel
        mem.seek(0)

        return send_file(
            mem,
            as_attachment=True,
            download_name='canciones_faltantes.csv',
            mimetype='text/csv'
        )

    # ---------------- API: EDITOR METADATA ----------------

    @app.route('/api/auto-search', methods=['POST'])
    def api_auto_search():
        """
        Busca metadata en iTunes para un archivo local.

        Body JSON:
            { "title": "...", "artist": "...", "path": "..." }

        Returns:
            JSON con lista de coincidencias y la mejor.
        """
        data = request.get_json(silent=True) or {}
        title = data.get('title', '')
        artist = data.get('artist', '')

        if not title:
            return jsonify({'error': 'Se necesita al menos el titulo.'}), 400

        results = search_track(title, artist, limit=5)
        if not results:
            return jsonify({'results': [], 'best': None,
                            'message': 'No se encontraron coincidencias en iTunes.'})

        best = best_match(results, target_title=title, target_artist=artist)
        return jsonify({'results': results, 'best': best})

    @app.route('/api/save-metadata', methods=['POST'])
    def api_save_metadata():
        """
        Guarda metadata en un archivo de audio.

        Body JSON:
            {
              "path": "C:\\Music\\cancion.flac",
              "metadata": { "title": "...", "artist": "...", ... }
            }

        Returns:
            JSON: { 'success': true/false, 'message': '...' }
        """
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')
        metadata = data.get('metadata', {})

        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False,
                            'message': 'Archivo no encontrado.'}), 400

        ok = write_metadata(file_path, metadata)
        if ok:
            return jsonify({'success': True,
                            'message': 'Metadata guardada correctamente.'})
        else:
            return jsonify({'success': False,
                            'message': 'No se pudo escribir la metadata.'}), 500

    @app.route('/api/file-metadata', methods=['POST'])
    def api_file_metadata():
        """
        Lee la metadata actual de un archivo (para el editor).
        Body: { "path": "..." }
        """
        data = request.get_json(silent=True) or {}
        file_path = data.get('path', '')

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Archivo no encontrado.'}), 400

        meta = read_metadata(file_path)
        quality = build_quality_summary(meta)
        return jsonify({**meta, 'quality': quality})

    return app
