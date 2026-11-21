"""
launcher.py - Punto de entrada del ejecutable MusicManager.exe
==============================================================
Este archivo es el que compila PyInstaller para generar el .exe.

Diferencias con main.py (modo fuente):
  - Detecta la carpeta del .exe (no la de Python) y hace cd a ella,
    para que .env, data/ y los archivos temporales queden junto al exe.
  - Anade la carpeta app/ al sys.path para que los modulos .py se carguen
    DESDE EL DISCO (asi puedes editarlos sin recompilar el exe).
  - Elige un puerto libre (5000, 5001... si 5000 esta ocupado).
  - Abre el navegador automaticamente cuando el servidor esta listo.

El .exe SOLO contiene el runtime de Python + las librerias de pip
(flask, mutagen, yt-dlp, spotipy...). Los modulos de app/, templates/,
static/ y data/ van SIEMPRE al lado del exe (ver LEEME-PORTABLE.txt).
"""

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def get_base_dir() -> Path:
    """Carpeta base: junto al .exe si esta compilado, o junto a este .py."""
    if getattr(sys, 'frozen', False):  # True cuando corre como MusicManager.exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_free_port(start: int = 5000, end: int = 5020):
    """Devuelve el primer puerto libre del rango, o None si no hay ninguno."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return None


def wait_for_server(port: int, timeout: float = 20.0) -> bool:
    """Espera (maximo `timeout` segundos) a que Flask acepte conexiones."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.25)
    return False


def main():
    base_dir = get_base_dir()
    # cd a la carpeta del exe: asi Path.cwd()/.env y las rutas relativas
    # siempre apuntan a la carpeta del programa, no a System32 etc.
    os.chdir(base_dir)

    # app/ contiene los modulos .py de la app (se cargan del disco)
    sys.path.insert(0, str(base_dir / 'app'))

    # Crear data/ y archivos por defecto si no existen
    try:
        from download_sites import ensure_files
        ensure_files()
        from deleted_songs import ensure_file
        ensure_file()
    except Exception as exc:
        print(f"[WARN] No se pudo crear data/: {exc}")

    from web_app import create_app
    app = create_app()

    port = find_free_port()
    if port is None:
        print("[ERROR] No hay puertos libres entre 5000 y 5020.")
        input("Presiona Enter para salir...")
        return

    print()
    print("=" * 56)
    print("   MUSIC MANAGER")
    print("   Carpeta: " + str(base_dir))
    print("   Servidor: http://127.0.0.1:{}".format(port))
    print("   Cierra esta ventana (o Ctrl+C) para salir.")
    print("=" * 56)
    print()

    # Flask en un hilo de segundo plano
    server_thread = threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port,
                               debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # Cuando el servidor responde, abrir el navegador
    if wait_for_server(port):
        url = 'http://127.0.0.1:{}'.format(port)
        try:
            if not webbrowser.open_new(url):
                print("[INFO] No se pudo abrir el navegador automaticamente.")
                print("       Abre manualmente: " + url)
        except Exception:
            print("[INFO] Abre manualmente en tu navegador: " + url)
    else:
        print("[WARN] El servidor tardo demasiado en responder.")

    # Mantener el proceso vivo hasta que el usuario cierre la ventana.
    # time.sleep() en el hilo principal es interrumpible con Ctrl+C.
    try:
        while server_thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    print()
    print("[OK] Music Manager cerrado.")


if __name__ == '__main__':
    main()
