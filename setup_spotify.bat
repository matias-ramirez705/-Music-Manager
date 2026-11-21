@echo off
REM ============================================
REM  Music Manager - Playlists grandes de Spotify
REM ============================================
REM  Este bat ya NO configura credenciales de Spotify.
REM  El flujo de OAuth nunca funcionó para +100 canciones.
REM  Usar Exportify para playlists grandes.
REM ============================================

chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   PLAYLISTS GRANDES DE SPOTIFY (+100 CANCIONES)
echo ============================================
echo.
echo Spotify no permite leer mas de 100 canciones
echo por link sin credenciales. El flujo de OAuth
echo nunca funciono correctamente, por lo que se
echo recomienda usar Exportify.
echo.
echo ============================================
echo   COMO USAR EXPORTIFY
echo ============================================
echo.
echo 1. Abre https://exportify.app/ en tu navegador
echo 2. Inicia sesion con tu cuenta de Spotify
echo 3. Veras la lista de todas tus playlists
echo 4. Haz clic en "Export" en la que quieras
echo 5. Se descargara un archivo .csv
echo 6. Abre Music Manager (run.bat)
echo 7. Ve a "Playlists Guardadas"
echo 8. Haz clic en "Importar CSV"
echo 9. Selecciona el archivo .csv descargado
echo 10. La playlist se carga completa (todas las canciones)
echo.
echo Abriendo exportify.app...
start https://exportify.app/
echo.
pause
