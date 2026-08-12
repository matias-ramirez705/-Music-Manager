@echo off
REM ============================================
REM  Music Manager - Configurar Spotify API
REM ============================================
REM  Te guia para obtener credenciales GRATIS de
REM  Spotify Developer y guardarlas en .env
REM  Basado en el flujo probado de AniTail.
REM ============================================

chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   CONFIGURAR CREDENCIALES DE SPOTIFY
echo ============================================
echo.
echo Esto te permite leer TODAS las canciones de
echo tus playlists de Spotify (no solo 100).
echo.
echo PASO 1: Abrir Spotify Developer Dashboard
echo --------------------------------------------
echo Tu navegador abrira:
echo    https://developer.spotify.com/dashboard
echo.
echo Si no tienes cuenta de Spotify, crea una gratis.
echo Inicia sesion y luego vuelve aqui.
echo.
pause

start https://developer.spotify.com/dashboard

echo.
echo PASO 2: Crear una App
echo --------------------------------------------
echo 1. En el dashboard, haz clic en "Create app"
echo 2. App name:        Music Manager
echo 3. App description: Local music manager
echo 4. Website:         http://127.0.0.1:8888
echo 5. Redirect URI:    http://127.0.0.1:8888
echo.
echo    IMPORTANTE:
echo    - Escribe exactamente esa URI con el puerto 8888
echo    - Haz clic en "Add" para agregar la URI
echo    - Si pide otra, NO agregues nada mas
echo.
echo 6. Which API/SDKs are you planning to use?
echo    MARCA "Web API" (la casilla debe estar activada)
echo    No marques ninguna otra.
echo.
echo 7. Acepta los terminos del servicio
echo 8. Haz clic en "Save"
echo.
pause

echo.
echo PASO 3: Copiar credenciales
echo --------------------------------------------
echo 1. Seras redirigido a la pagina de la app.
echo 2. Haz clic en "Settings" (boton arriba a la derecha).
echo 3. Copia el "Client ID"
echo 4. Haz clic en "View client secret"
echo 5. Copia el "Client secret"
echo.
echo Pegalos cuando se te pida a continuacion.
echo.

set /p client_id="Client ID: "
if "%client_id%"=="" (
    echo [ERROR] Client ID vacio. Abortando.
    pause
    exit /b 1
)

set /p client_secret="Client Secret: "
if "%client_secret%"=="" (
    echo [ERROR] Client Secret vacio. Abortando.
    pause
    exit /b 1
)

REM Escribir archivo .env (sobrescribe si existe)
echo SPOTIPY_CLIENT_ID=%client_id%> .env
echo SPOTIPY_CLIENT_SECRET=%client_secret%>> .env
echo SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888>> .env

echo.
echo [OK] Credenciales guardadas en .env
echo.

REM Verificar que el archivo se escribio bien
if not exist ".env" (
    echo [ERROR] No se pudo crear .env
    pause
    exit /b 1
)

echo.
echo ============================================
echo   CONFIGURACION COMPLETADA
echo ============================================
echo.
echo Ya puedes cerrar esta ventana y ejecutar run.bat
echo.
echo IMPORTANTE - PARA LEER PLAYLISTS COMPLETAS:
echo.
echo 1. Abre la app con run.bat
echo 2. Ve a "Playlists Guardadas"
echo 3. Veras un banner con "Iniciar sesion con Spotify"
echo 4. Haz clic en el boton
echo 5. Se abrira una ventana modal con un enlace
echo 6. Abre el enlace, inicia sesion con tu Spotify
echo 7. Autoriza los permisos
echo 8. Spotify te redirige a una URL que empieza con
echo    http://127.0.0.1:8888/?code=...
echo    (la pagina dara error 404, eso es NORMAL)
echo 9. Copia la URL COMPLETA del navegador
echo 10. Pegala en el campo del modal
echo 11. Haz clic en "Completar login"
echo.
echo Tu token se guarda localmente en data/.spotify_cache
echo y se usara automaticamente cada vez que abras la app.
echo.
pause
