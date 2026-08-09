# Music Manager

Aplicacion web local para gestionar tu biblioteca musical: ver todos tus
archivos de audio, compararlos con playlists publicas de YouTube Music o
Spotify, y editar la metadata de cada cancion.

## Caracteristicas

- **Escaneo local**: selecciona una carpeta y encuentra todos los archivos
  de audio (incluye subcarpetas). Soporta MP3, FLAC, WAV, M4A, AAC, OGG,
  Opus, AIFF, ALAC, APE, WavPack.
- **Deteccion de calidad**: muestra profundidad de bits (16/24-bit),
  frecuencia de muestreo (44.1/96/192 kHz), bitrate, canales y
  clasificacion automatica (CD Quality, Hi-Res, Lossy, etc.).
- **Comparacion con playlists**: pega el link de una playlist publica de
  YouTube Music o Spotify (sin iniciar sesion ni registrar apps) y
  muestra que canciones te faltan y cuales ya tienes.
- **Exportar faltantes**: descarga un CSV con la lista de canciones que
  faltan para buscarlas y descargarlas.
- **Editor de metadata**: modifica los tags de cualquier archivo. Boton
  de busqueda automatica en iTunes para rellenar campos.

## Requisitos

- **Python 3.10 o superior** (descarga gratis en https://www.python.org/downloads/)
  - Durante la instalacion en Windows, marca la casilla
    "Add Python to PATH".
- **Conexion a internet** para leer playlists y buscar metadata en iTunes.
- Navegador moderno (Chrome, Firefox, Edge).

## Instalacion en Windows

1. Copia toda la carpeta `music_manager/` donde quieras tener el proyecto.
2. Haz **doble clic en `setup_env.bat`**.
   - Esto crea un entorno virtual `.venv` en la misma carpeta.
   - Instala Flask, mutagen, yt-dlp y requests.
   - Solo se hace la primera vez.

## Uso

1. Haz **doble clic en `run.bat`**.
2. Se abrira automaticamente tu navegador en http://127.0.0.1:5000.
3. Para detener la aplicacion: cierra la ventana negra (CMD) o presiona
   `Ctrl+C` dentro de ella.

## Estructura del proyecto

```
music_manager/
|-- main.py              <- arranca la aplicacion
|-- setup_env.bat        <- configura el entorno (ejecutar 1 vez)
|-- run.bat              <- ejecuta la aplicacion
|-- requirements.txt     <- librerias necesarias
|-- app/                 <- codigo Python modular
|   |-- scanner.py           -> escanea carpetas en busca de audio
|   |-- metadata_reader.py   -> lee/escribe tags (mutagen)
|   |-- audio_quality.py     -> interpreta calidad (bits, kHz, etc.)
|   |-- playlist_youtube.py  -> lee playlists publicas de YT Music
|   |-- playlist_spotify.py  -> lee playlists publicas de Spotify
|   |-- auto_metadata.py     -> busca metadata en iTunes Search API
|   `-- web_app.py           -> servidor Flask con todas las rutas
|-- templates/           <- HTML de las 3 pestañas
|   |-- base.html            -> layout comun (sidebar)
|   |-- index.html           -> pestana 1: Mi Musica
|   |-- compare.html         -> pestana 2: Comparar playlist
|   `-- editor.html          -> pestana 3: Editor de metadata
`-- static/              <- CSS y JS
    |-- css/style.css       -> estilo oscuro tipo Spotify
    `-- js/
        |-- app.js          -> utilidades compartidas
        |-- local.js        -> logica pestana 1
        |-- compare.js      -> logica pestana 2
        `-- editor.js       -> logica pestana 3
```

## Como usar cada pestana

### 1. Mi Musica

- Escribe la ruta de tu carpeta de musica o pulsa **Explorar** para abrir
  el dialogo nativo de Windows.
- Pulsa **Escanear**. Se leen todos los archivos de audio (incluyendo
  subcarpetas) y se muestra la tabla.
- Columnas: # / Nombre / Artista / Album / Duracion / Formato / Tamano /
  Ruta. Pulsa **Mostrar calidad** para anadir la columna de calidad.
- Usa la barra de busqueda para filtrar por nombre, artista o album.
- Haz clic en cualquier fila para abrir el editor con ese archivo.

### 2. Comparar Playlist

- Primero asegurate de haber escaneado tu musica en la pestana 1.
- Pega el link de una playlist publica:
  - YouTube Music: `https://music.youtube.com/playlist?list=PL...`
  - Spotify: `https://open.spotify.com/playlist/...`
- Pulsa **Cargar Playlist**. Se descargara la lista de canciones y se
  comparara con tu biblioteca local.
- Veras un circulo de progreso con el porcentaje descargado.
- Botones:
  - **Ver faltantes**: canciones de la playlist que no tienes.
  - **Ver coincidencias**: las que ya tienes.
  - **Exportar faltantes (CSV)**: descarga un archivo Excel-compatible.

### 3. Editor de Metadata

- Escribe la ruta del archivo o cargalo desde la pestana 1 (clic en una
  fila).
- Edita los campos manualmente o pulsa **Buscar en iTunes** para
  rellenarlos automaticamente.
- Pulsa **Guardar cambios** para escribir los tags en el archivo.

## Limitaciones conocidas

- **YouTube Music y Spotify**: solo funcionan con playlists **publicas**.
  Las privadas o "no listadas" no son accesibles sin iniciar sesion.
- **Spotify embed**: si Spotify cambia el formato de su pagina embed,
  podria dejar de funcionar. Revisa este script si pasa.
- **yt-dlp**: si YouTube cambia algo, ejecuta
  `pip install --upgrade yt-dlp` dentro del entorno virtual.
- La aplicacion mantiene el estado en memoria: si reinicias el servidor,
  perderas el escaneo actual (tendra que re-escanear).

## Solucion de problemas

| Problema | Solucion |
|---|---|
| `python no esta instalado` | Instala Python 3.10+ y marca "Add to PATH". |
| `No se encontro .venv` | Ejecuta primero `setup_env.bat`. |
| El puerto 5000 esta ocupado | Edita `main.py` y cambia `port=5000` por otro. |
| YouTube Music no carga | `pip install --upgrade yt-dlp` dentro de `.venv`. |
| Spotify no carga | Verifica que la playlist sea publica. |
| No se leen tags | Algun formato puede no soportarse; mutagen es muy completo. |

## Actualizar dependencias

Si quieres actualizar las librerias a la ultima version:

```bat
cd music_manager
.venv\Scripts\activate
pip install --upgrade flask mutagen yt-dlp requests
```
