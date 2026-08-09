@echo off
REM ============================================
REM  Music Manager - Ejecutar aplicacion
REM ============================================
REM  1. Activa el entorno virtual (.venv)
REM  2. Ejecuta main.py
REM  3. Abre el navegador en http://127.0.0.1:5000
REM
REM  Deteccion automatica: opera en la carpeta
REM  donde se encuentre este archivo .bat
REM ============================================

chcp 65001 >nul
cd /d "%~dp0"

REM Verificar que el entorno virtual exista
if not exist ".venv" (
    echo [ERROR] El entorno virtual no existe.
    echo Ejecuta primero: setup_env.bat
    pause
    exit /b 1
)

REM Verificar que main.py exista
if not exist "main.py" (
    echo [ERROR] No se encontro main.py en la carpeta actual.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo ============================================
echo   MUSIC MANAGER
echo   Abriendo navegador en http://127.0.0.1:5000
echo   Presiona Ctrl+C en esta ventana para detener.
echo ============================================
echo.

REM Abrir el navegador despues de 2 segundos (en segundo plano)
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

REM Ejecutar la aplicacion
python main.py

echo.
echo Aplicacion detenida. Presiona una tecla para salir.
pause >nul
