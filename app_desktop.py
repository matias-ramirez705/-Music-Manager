"""
app_desktop.py - Music Manager como app de escritorio (v3.36)
==============================================================
Punto de entrada para el ejecutable .exe (PyInstaller).
También funciona sin PyInstaller (ejecutando desde fuente).

Diseño:
  - Detecta si está "frozen" (PyInstaller) o desde fuente
  - Ajusta rutas de templates/, static/, app/ según el modo
  - Inicia Flask en un hilo de fondo (daemon)
  - Abre ventana nativa con pywebview
  - Al cerrar la ventana, Flask se cierra automáticamente

En el .exe:
  MusicManager/
  |-- MusicManager.exe     <- Python runtime + dependencias compiladas
  |-- app/*.py             <- módulos cargados desde disco (editables)
  |-- templates/*.html     <- plantillas HTML
  |-- static/              <- CSS, JS, favicon
  |-- data/                <- datos de la app (se crea solo)

Los módulos .py NO están compilados dentro del .exe:
se cargan desde el disco para que el usuario pueda editarlos
sin necesidad de recompilar. El .exe solo contiene el
intérprete de Python + las librerías pip.
"""

import sys
import os
import threading
import time
import tempfile


def get_base_dir():
    """
    Devuelve el directorio base de la aplicación.

    - Si está congelado (PyInstaller): el directorio donde está el .exe
    - Si está desde fuente: el directorio de este script
    """
    if getattr(sys, 'frozen', False):
        # Ejecutándose desde un .exe de PyInstaller
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        # Ejecutándose desde Python (source)
        return os.path.dirname(os.path.abspath(__file__))


def setup_paths():
    """
    Configura sys.path para encontrar los módulos de app/.
    En modo frozen, los módulos NO están en el PYZ del exe,
    se cargan desde el disco.
    """
    base = get_base_dir()

    # Añadir app/ al path para que los imports funcionen
    app_dir = os.path.join(base, 'app')
    if os.path.isdir(app_dir):
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)

    # Añadir el directorio base también (para data/, etc.)
    if base not in sys.path:
        sys.path.insert(0, base)

    return base


# Configurar rutas ANTES de cualquier import de la app
BASE_DIR = setup_paths()


def get_flask_paths():
    """Devuelve las rutas de templates/ y static/ para Flask."""
    base = get_base_dir()
    return (
        os.path.join(base, 'templates'),
        os.path.join(base, 'static'),
    )


def start_flask(app):
    """Inicia Flask en un hilo daemon. Espera hasta que responda."""
    import requests

    thread = threading.Thread(
        target=lambda: app.run(
            host='127.0.0.1',
            port=5000,
            debug=False,
            use_reloader=False,  # crítico: sin reloader en hilo
        ),
        daemon=True,
    )
    thread.start()

    # Esperar hasta que Flask responda (máximo 15 segundos)
    print("[...] Esperando servidor Flask...")
    for _ in range(30):
        try:
            requests.get('http://127.0.0.1:5000/', timeout=1)
            print("[OK] Servidor Flask listo en http://127.0.0.1:5000")
            return True
        except requests.RequestException:
            time.sleep(0.5)

    print("[ERROR] Flask no respondió a tiempo.")
    return False


def open_webview():
    """Abre la ventana nativa con pywebview. Bloquea hasta cerrar."""
    import webview
    print("[OK] Abriendo ventana de Music Manager...")
    webview.create_window(
        title='Music Manager',
        url='http://127.0.0.1:5000',
        width=1400,
        height=900,
        min_size=(1000, 600),
    )
    webview.start()  # bloquea hasta cerrar


def open_browser_fallback():
    """Fallback: abre en navegador si pywebview falla."""
    import webbrowser
    print("[WARN] pywebview no disponible. Abriendo en navegador...")
    webbrowser.open('http://127.0.0.1:5000')


def main():
    """Punto de entrada principal."""
    base = get_base_dir()

    # Obtener rutas de templates/ y static/
    templates_dir, static_dir = get_flask_paths()

    # Verificar que las carpetas existan
    if not os.path.isdir(templates_dir):
        print(f"[ERROR] No se encontró templates/ en: {templates_dir}")
        print("Asegúrate de ejecutar el .exe desde la carpeta MusicManager/")
        input("Presiona Enter para salir...")
        return

    # Inicializar la app Flask con las rutas correctas
    from web_app import create_app
    app = create_app(
        template_folder=templates_dir,
        static_folder=static_dir,
    )

    # Inicializar datos
    try:
        from download_sites import ensure_files
        ensure_files()
        from deleted_songs import ensure_file as ensure_deleted_file
        ensure_deleted_file()
        print("[OK] Carpeta data/ verificada.")
    except Exception as e:
        print(f"[WARN] data/: {e}")

    # Iniciar Flask
    print("=" * 50)
    print("  MUSIC MANAGER - App de escritorio")
    print(f"  Directorio: {base}")
    print("=" * 50)

    if not start_flask(app):
        input("Presiona Enter para salir...")
        return

    # Abrir ventana nativa (o navegador como fallback)
    try:
        open_webview()
        print("[OK] Aplicación cerrada correctamente.")
    except ImportError:
        open_browser_fallback()
        # Mantener Flask corriendo hasta Ctrl+C
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Aplicación detenida.")
    except Exception as e:
        print(f"[ERROR] {e}")
        open_browser_fallback()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
