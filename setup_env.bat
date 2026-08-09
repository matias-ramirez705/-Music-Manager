@echo off
REM ============================================
REM  Music Manager - Configuracion del entorno
REM ============================================
REM  Este script:
REM    1. Crea un entorno virtual de Python (.venv)
REM    2. Instala las dependencias necesarias
REM
REM  Deteccion automatica: opera en la carpeta
REM  donde se encuentre este archivo .bat
REM ============================================

chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   MUSIC MANAGER - Configuracion inicial
echo   Carpeta del proyecto: %cd%
echo ============================================
echo.

REM Verificar que Python este instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo.
    echo Descargalo gratis desde: https://www.python.org/downloads/
    echo Durante la instalacion, marca la casilla:
    echo   "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python detectado:
python --version
echo.

REM Si ya existe el entorno virtual, eliminarlo para reconfigurar
if exist ".venv" (
    echo Se encontro un entorno virtual existente.
    set /p confirm="Deseas eliminarlo y recrearlo? (S/N): "
    if /i "%confirm%"=="S" (
        echo Eliminando entorno virtual anterior...
        rmdir /s /q ".venv"
    ) else (
        echo Usando entorno existente. Si faltan librerias, ejecuta:
        echo   pip install -r requirements.txt
        goto activate
    )
)

echo Creando entorno virtual en .venv ...
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    pause
    exit /b 1
)
echo [OK] Entorno virtual creado.
echo.

:activate
call .venv\Scripts\activate.bat
echo [OK] Entorno virtual activado.

echo.
echo Instalando dependencias desde requirements.txt ...
echo --------------------------------------------
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Hubo problemas instalando dependencias.
    echo Intenta ejecutar manualmente:
    echo   pip install flask mutagen yt-dlp requests
    pause
    exit /b 1
)
echo --------------------------------------------
echo [OK] Dependencias instaladas correctamente.

echo.
echo ============================================
echo   CONFIGURACION COMPLETADA
echo ============================================
echo   Ya puedes ejecutar: run.bat
echo   Se abrira la interfaz en tu navegador.
echo ============================================
echo.
pause
