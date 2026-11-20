@echo off
REM ============================================
REM  Music Manager - Compilar MusicManager.exe
REM  (igual que hace GitHub Actions, pero local)
REM ============================================
REM  Requisitos: Python 3.10+ instalado y en PATH.
REM  Resultado:  dist\MusicManager.exe
REM              dist\MusicManager-v4.5-windows-portable.zip
REM ============================================

chcp 65001 >nul
cd /d "%~dp0"

echo [1/5] Instalando dependencias...
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error
python -m pip install -r requirements-build.txt || goto :error

echo.
echo [2/5] Compilando exe (PyInstaller)...
python -m PyInstaller MusicManager.spec --noconfirm --clean || goto :error

if not exist "dist\MusicManager.exe" (
    echo [ERROR] dist\MusicManager.exe no se genero.
    pause
    exit /b 1
)

echo.
echo [3/5] Armando carpeta portable...
if exist "dist\portable" rmdir /s /q "dist\portable"
mkdir "dist\portable\MusicManager"
copy /y "dist\MusicManager.exe" "dist\portable\MusicManager\" >nul
xcopy "app"       "dist\portable\MusicManager\app\"       /e /i /q >nul
xcopy "templates" "dist\portable\MusicManager\templates\" /e /i /q >nul
xcopy "static"    "dist\portable\MusicManager\static\"    /e /i /q >nul
xcopy "data"      "dist\portable\MusicManager\data\"      /e /i /q >nul
copy /y "README.md"          "dist\portable\MusicManager\" >nul
copy /y "LEEME-PORTABLE.txt" "dist\portable\MusicManager\" >nul
copy /y "requirements.txt"   "dist\portable\MusicManager\" >nul
copy /y "setup_spotify.bat"  "dist\portable\MusicManager\" >nul

echo.
echo [4/5] Creando ZIP portable...
set VER=4.5
powershell -NoProfile -Command "tar -a -c -f 'dist/MusicManager-v%VER%-windows-portable.zip' -C 'dist/portable' MusicManager"

echo.
echo [5/5] Listo. Archivos generados:
echo    dist\MusicManager.exe
echo    dist\MusicManager-v%VER%-windows-portable.zip
echo.
echo Prueba el exe con doble clic ANTES de publicar un Release.
pause
exit /b 0

:error
echo.
echo [ERROR] Fallo un paso de la compilacion. Revisa el mensaje de arriba.
pause
exit /b 1
