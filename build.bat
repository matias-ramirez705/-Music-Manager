@echo off
REM ============================================
REM  Music Manager - Compilar exe localmente
REM ============================================
REM  Solo necesario si querés compilar en tu PC.
REM  GitHub Actions lo hace automáticamente en cada push.
REM
REM  Requisitos:
REM    - Python 3.12 instalado y en PATH
REM    - pyinstaller: pip install pyinstaller
REM ============================================

chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   COMPILAR MUSIC MANAGER.EXE
echo ============================================
echo.

REM Verificar PyInstaller
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando PyInstaller...
    pip install pyinstaller
)

echo [INFO] Compilando versión portable (carpeta)...
python -m PyInstaller MusicManager-portable.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] Fallo la compilación portable.
    pause
    exit /b 1
)

echo [INFO] Compilando versión de archivo único...
python -m PyInstaller MusicManager.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] Fallo la compilación onefile.
    pause
    exit /b 1
)

echo [INFO] Copiando código fuente al dist portable...
xcopy /E /Y /I app dist\MusicManager\app >nul
xcopy /E /Y /I templates dist\MusicManager\templates >nul
xcopy /E /Y /I static dist\MusicManager\static >nul
if exist run_desktop.bat copy /Y run_desktop.bat dist\MusicManager\ >nul
if exist main.py copy /Y main.py dist\MusicManager\ >nul
if not exist dist\MusicManager\data mkdir dist\MusicManager\data

echo.
echo ============================================
echo   COMPILACIÓN COMPLETADA
echo ============================================
echo.
echo Archivos generados:
echo   dist\MusicManager.exe              (archivo único, solo runtime)
echo   dist\MusicManager\MusicManager.exe (portable, con código fuente)
echo   dist\MusicManager-portable-win64.zip (si lo empaquetas)
echo.
echo IMPORTANTE: El .exe portable incluye app/, templates/, static/
echo para que puedas editar los .py sin recompilar.
echo.
pause
