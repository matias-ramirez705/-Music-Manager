"""
main.py - Punto de entrada de Music Manager
===========================================
Inicia el servidor web Flask que sirve la interfaz en el navegador.

Uso:
    python main.py
    (o haz doble clic en run.bat)

Despues de arrancar, abre en tu navegador:
    http://127.0.0.1:5000

Estructura del proyecto:
    music_manager/
    |-- main.py              <- este archivo (arranca la app)
    |-- setup_env.bat        <- crea el entorno virtual (.venv)
    |-- run.bat              <- ejecuta este archivo
    |-- requirements.txt     <- dependencias de Python
    |-- app/
    |   |-- __init__.py
    |   |-- scanner.py           -> escanea carpetas en busca de audio
    |   |-- metadata_reader.py   -> lee/escribe tags (mutagen)
    |   |-- audio_quality.py     -> interpreta calidad (bits, kHz, etc.)
    |   |-- playlist_youtube.py  -> lee playlists publicas de YT Music
    |   |-- playlist_spotify.py  -> lee playlists publicas de Spotify
    |   |-- auto_metadata.py     -> busca metadata en iTunes Search API
    |   |-- web_app.py           -> servidor Flask con todas las rutas
    |-- templates/
    |   |-- base.html        <- plantilla comun (sidebar + layout)
    |   |-- index.html       <- pestana 1: Mi Musica
    |   |-- compare.html     <- pestana 2: Comparar playlist
    |   |-- editor.html      <- pestana 3: Editor de metadata
    |-- static/
        |-- css/style.css    <- estilo oscuro tipo Spotify
        |-- js/
            |-- app.js       <- utilidades compartidas
            |-- local.js     <- logica pestana 1
            |-- compare.js   <- logica pestana 2
            |-- editor.js    <- logica pestana 3
"""

import sys
from pathlib import Path

# Asegurar que la carpeta 'app/' este en el path de Python
# para que los imports como 'from scanner import ...' funcionen
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from web_app import create_app


def main():
    """Crea y arranca la aplicacion Flask."""
    # Crear carpeta data/ y archivos por defecto si no existen
    try:
        from download_sites import ensure_files
        ensure_files()
        print("[OK] Carpeta data/ y archivos verificados.")
    except Exception as e:
        print(f"[WARN] No se pudo crear data/: {e}")

    app = create_app()

    print()
    print("=" * 56)
    print("   MUSIC MANAGER")
    print("   Interfaz: http://127.0.0.1:5000")
    print("   Presiona Ctrl+C en esta ventana para detener.")
    print("=" * 56)
    print()

    # debug=False para que no se reinicie automaticamente
    # (en produccion local esto es suficiente)
    app.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == '__main__':
    main()
