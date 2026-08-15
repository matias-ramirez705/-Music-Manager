# Music Manager v3.2

Aplicacion web local para gestionar tu biblioteca musical: ver todos tus
archivos de audio, compararlos con playlists publicas de YouTube Music o
Spotify, guardar accesos directos a playlists, detectar duplicados,
reproducir canciones, editar metadata + caratulas, organizar por
carpetas, acceder a un indice de sitios para descargar musica FLAC,
gestionar caratulas y letras masivamente.

## Novedades en v3.2

- **Boton "↻ Actualizar" en Mi Musica**: re-escanea la ultima carpeta
  usada sin tener que volver a seleccionarla. La carpeta se mantiene
  entre pestanas (guardada en localStorage).
- **Scroll solo en la tabla**: la cabecera, filtros, buscador y titulos
  de columnas se mantienen visibles. Solo la lista hace scroll vertical.
- **Scroll en modal de playlist**: el buscador y los titulos de columnas
  se mantienen fijos; solo la lista de canciones hace scroll.
- **Buscador en Playlists Guardadas**: filtra playlists por nombre o
  plataforma en tiempo real.
- **Filtro de metadata con error** en Mi Musica: nuevo dropdown para
  ver solo las canciones que no pudieron cargar metadatos (⚠).
- **Error具体 visible**: al pasar el raton sobre el ⚠ se ve el mensaje
  de error具体 (formato no soportado, archivo corrupto, etc.).
- **Dots de playlist clicables**: al hacer clic en un dot de color en
  la columna Playlists de Mi Musica, se abre el detalle de esa playlist
  con todas sus canciones y un buscador integrado.
- **Columna Copiar (📋)** en Mi Musica y Comparar Playlist: copia
  "titulo - artista" al portapapeles para buscar facilmente.
- **Alineacion y anchos corregidos** en Mi Musica, Comparar Playlist y
  modal de playlist:
  - Mi Musica: duracion, formato y copiar centrados; artista reducido;
    ruta mas ancha.
  - Comparar: titulo alineado a la izquierda; bug de columna Copiar/
    Abrir online intercambiados corregido.
  - Modal de playlist: titulo a la izquierda; album y duracion
    centrados; columnas redimensionadas.

## Novedades en v3.0–v3.1

- **Pestana "Metadatos" con 3 sub-pestañas**: Editar Metadata,
  Caratulas (masivo) y Letras (masivo).
- **Caratulas masivo**: analizar, redimensionar todas, descargar
  faltantes desde iTunes, busqueda manual con multiple fuente.
- **Letras masivo**: analizar, descargar faltantes desde lrclib.net,
  ver letra con reproductor integrado, busqueda manual con preview.
- **Seguidor de letra sincronizada** (LRC) en el reproductor principal.

Aplicacion web local para gestionar tu biblioteca musical: ver todos tus
archivos de audio, compararlos con playlists publicas de YouTube Music o
Spotify, guardar accesos directos a playlists, detectar duplicados,
reproducir canciones, editar metadata + caratulas, organizar por
carpetas y acceder a un indice de sitios para descargar musica FLAC.

## Novedades en v2.1

- **Agregar enlaces a la lista de Descargas FLAC**: nuevo boton
  "➕ Agregar enlace" en la pestana Descargas FLAC que abre un modal
  con campos para Nombre, Enlace, Descripcion y Estado. Verifica
  automaticamente si el enlace ya existe para evitar duplicados.

## Novedades en v2.0

- **Nueva pestana "⬇ Descargas FLAC"**: indice de 48 sitios y programas
  para descargar musica en FLAC, extraidos de https://fmhy.net/audio.
  Incluye:
  - Audio Ripping Sites (lucida, DoubleDouble, squid.wtf)
  - Audio Ripping Tools (streamrip, OrpheusDL, SpotiFLAC, DeemixFix,
    Deemix Revival, SaturnMusic, qobuz-dl, etc.)
  - Telegram Bots (DeezerMusicBot, BeatSpotBot)
  - Download Sites (FLAC Attack, Lossless-Music, FlacMusic, etc.)
  - Sitios por genero (Metal, Electronica, Clasica, Hip Hop, K-Pop, etc.)
- **Archivo `data/download_sites.txt`**: se crea automaticamente al
  arrancar la app si no existe. Formato tabla:
  `| NOMBRE | LINK | DESCRIPCION | ESTADO |`
- **Buscador y filtros** en la tabla de sitios.
- **Editor del archivo TXT** integrado en la UI.
- **Toggle de estado** (OK/Caido) por cada sitio.

## Novedades en v1.16

- **Cargar playlists desde TXT**: nuevo boton "📝 Cargar desde TXT" en
  Playlists Guardadas que abre un modal con editor de texto. Permite
  pegar multiples URLs de playlists (una por linea) con comentarios
  (lineas que empiezan con `#`).
- **Archivo `data/playlists.txt`**: se puede guardar/cargar desde la UI.
  Soporta URLs de YouTube Music, Spotify y rutas a archivos CSV locales.
- **Importacion masiva**: procesa todas las URLs del texto de golpe y
  muestra un resumen con exitosas/errores por linea.

## Novedades en v1.15

- **Bug corregido: canciones con apostrofos**: las canciones con
  apostrofos en el nombre o artista (como "Can't Stop", "Don't Know
  What To Say", "It's Freaking Christmas") ahora funcionan
  correctamente al hacer clic en reproducir o abrir carpeta. Se
  reescribieron los botones usando DOM API + event listeners en vez
  de `onclick` inline.

## Novedades en v1.14

- **Anchos de columna en Comparar Playlist**: la tabla de comparacion
  ahora usa `table-layout: fixed` con anchos personalizados segun el
  wireframe del usuario:
  - # (3%), Titulo (24%), Artista (16%), Duracion (7%), Estado (8%),
    Calidad local (9%), Formato (8%), Escuchar local (10%),
    Abrir online (15%).

## Novedades en v1.13

- **Organizar rediseñado**: cada fila tiene un boton "📁 Mover" para
  mover esa cancion individualmente a la playlist elegida. Ademas del
  modo plan masivo existente.
- **Dots de color en Organizar**: la columna "Playlist destino" muestra
  puntos de color (rojo = YouTube Music, verde = Spotify) como en
  Mi Musica.
- **Selector de playlist en conflictos**: cuando una cancion esta en
  varias playlists, aparece un `<select>` para elegir a cual moverla.
- **Bug de "Can't Stop" corregido**: los apostrofos en nombres ya no
  rompen los botones.

## Novedades en v1.12

- **Nueva pestana "📁 Organizar"**: mueve tus canciones a subcarpetas
  segun las playlists en las que aparecen. Directorio base configurable.
  Opciones para canciones en varias playlists (preguntar, primera,
  copiar a todas, dejar). Las canciones sin playlist se pueden mover
  a "Sin playlist" o dejar donde estan.

## Novedades en v1.11

- **Duplicados: al eliminar, se actualiza el registro**: el archivo
  eliminado se quita de LAST_SCAN inmediatamente, sin necesidad de
  re-escanear.
- **Reproductor: restaura y auto-reproduce al volver**: al cambiar de
  pestana y volver, el reproductor se restaura desde la posicion
  guardada y continua reproduciendo.
- **Favicon**: nota musical sobre fondo verde en la pestana del
  navegador.

## Novedades en v1.10

- **Bug delete-file 400 corregido**: los paths Windows con backslashes
  se pasaban corruptos al endpoint. Ahora se usa `encodeURIComponent`.
- **Warning de Spotify actualizado**: el mensaje ahora sugiere usar
  Exportify en vez de configurar credenciales.

## Novedades en v1.9

- **Control de volumen en el reproductor**: barra horizontal deslizable
  entre la barra de progreso y el boton X. Icono 🔊/🔉/🔇 que al hacer
  clic silencia/activa. El volumen se mantiene entre canciones.
- **Reproductor persistente entre pestanas**: al cambiar de pestana, la
  musica se restaura al volver con la posicion correcta.
- **Bug corregido: comparar playlists CSV guardadas**: el endpoint
  ahora reconoce URLs `csv://`.
- **Playlists CSV en archivos JSON individuales**: cada playlist
  importada desde CSV se guarda en `data/Spotify/<nombre>.json`.
- **Clic en ruta abre explorador**: en Mi Musica y Duplicados, clic en
  la columna Ruta abre el explorador de archivos del sistema.

## Caracteristicas principales

### 7 pestañas:

1. **♪ Mi Música** — escanea carpetas, muestra tabla con nombre, artista,
   álbum, duración, formato, calidad (bits/kHz), playlists, tamaño y ruta.
   Reproductor integrado, filtros, búsqueda, badges de duplicados.

2. **⧉ Duplicados** — detecta canciones repetidas en diferentes
   formatos/calidades. Marca la mejor versión. Botón borrar con doble
   confirmación. Exportar CSV.

3. **★ Playlists Guardadas** — guarda enlaces de playlists públicas de
   YouTube Music o importa playlists de Spotify desde CSV (Exportify).
   Carga masiva desde TXT. Cada playlist CSV se guarda en su propio JSON.

4. **⇄ Comparar Playlist** — compara tu música local con una playlist.
   Muestra faltantes, coincidencias, calidad local, formato, botón
   reproducir local, y enlace a la plataforma con color. Exporta CSV.
   Persiste entre pestañas.

5. **✎ Editar Metadata** — edita tags (título, artista, álbum, año,
   pista, género). Busca metadata en iTunes, MusicBrainz, Last.fm.
   Gestiona carátulas (ver, redimensionar, descargar desde URL,
   cargar desde archivo). Renombrar archivo.

6. **📁 Organizar** — mueve canciones a subcarpetas por playlist.
   Modo individual (botón por fila) o plan masivo. Resolución de
   conflictos cuando una canción está en varias playlists.

7. **⬇ Descargas FLAC** — índice de 48 sitios/programas para descargar
   música FLAC. Agregar enlaces, editar TXT, toggle de estado.
   Extraído de fmhy.net/audio.

### Reproductor flotante:
- Carátula miniatura, controles play/pausa/skip, barra de progreso
  personalizada con gradiente verde, control de volumen.
- Persiste entre pestañas (restaura posición al volver).
- Solo se cierra al pulsar la X.

### Soporte de formatos:
- **Audio**: MP3, FLAC, WAV, M4A, AAC, OGG, Opus, AIFF, ALAC, APE, WavPack
- **Playlists**: YouTube Music (completo), Spotify (100 por URL o CSV
  ilimitado via Exportify)
- **Metadata**: iTunes, MusicBrainz, Last.fm
- **CSV**: Exportify (español e inglés)

## Requisitos

- **Python 3.10 o superior** (https://www.python.org/downloads/)
  - Marca "Add Python to PATH" durante la instalacion.
- Navegador moderno (Chrome, Firefox, Edge).
- Conexion a internet para leer playlists y buscar metadata.

## Instalacion en Windows

1. Copia la carpeta del proyecto donde quieras tenerlo.
2. Haz **doble clic en `setup_env.bat`**.
   - Crea entorno virtual `.venv` e instala todas las dependencias.
   - Solo se hace la primera vez.
3. Si vienes de una version anterior: ejecuta `setup_env.bat` de nuevo
   (responde "S" para recrear el entorno).
4. Ejecuta `run.bat`.
5. Se abre el navegador en http://127.0.0.1:5000.
6. Para detener: cierra la ventana CMD o presiona `Ctrl+C`.

## Estructura del proyecto

```
music_manager/
|-- main.py                  <- arranca la aplicacion
|-- setup_env.bat            <- configura el entorno (ejecutar 1 vez)
|-- run.bat                  <- ejecuta la aplicacion
|-- requirements.txt         <- librerias necesarias
|-- .gitignore
|-- data/                    <- se crea automaticamente al arrancar
|   |-- saved_playlists.json <- indice de playlists guardadas
|   |-- playlists.txt        <- URLs para carga masiva de playlists
|   |-- download_sites.txt   <- indice de sitios para descargar FLAC
|   `-- Spotify/             <- playlists CSV en JSON individuales
|-- app/                     <- codigo Python modular
|   |-- scanner.py           -> escanea carpetas
|   |-- metadata_reader.py   -> lee/escribe tags (mutagen)
|   |-- audio_quality.py     -> interpreta calidad (bits, kHz, etc.)
|   |-- playlist_youtube.py  -> lee playlists YT Music
|   |-- playlist_spotify.py  -> lee playlists Spotify
|   |-- spotify_official.py  -> API oficial via spotipy (opcional)
|   |-- auto_metadata.py     -> busca metadata en iTunes/MusicBrainz/Last.fm
|   |-- csv_playlist.py      -> parsea CSV de Exportify
|   |-- txt_playlist.py      -> parsea TXT con URLs de playlists
|   |-- saved_playlists.py   -> persiste playlists en JSON
|   |-- duplicates.py        -> detecta canciones repetidas
|   |-- artwork.py           -> caratulas: ver/redimensionar/descargar
|   |-- organizer.py         -> mueve canciones por playlist
|   |-- download_sites.py    -> gestiona indice de sitios FLAC
|   `-- web_app.py           -> servidor Flask con todas las rutas
|-- templates/               <- HTML de las 7 pestañas
|   |-- base.html, index.html, duplicates.html
|   |-- saved_playlists.html, compare.html
|   |-- editor.html, organize.html, downloads.html
`-- static/                  <- CSS y JS
    |-- favicon.svg          -> icono de nota musical
    |-- css/style.css        -> estilo oscuro tipo Spotify
    `-- js/
        |-- app.js, player.js, local.js, compare.js
        |-- editor.js, duplicates.js, saved_playlists.js
        |-- organize.js, downloads.js
```

## Solucion de problemas

| Problema | Solucion |
|---|---|
| Error al actualizar desde v1.x | Borra `.venv` y vuelve a ejecutar `setup_env.bat`. |
| YouTube Music no carga | `pip install --upgrade yt-dlp` dentro de `.venv`. |
| Spotify solo carga 100 canciones | Usa Exportify (https://exportify.app/) para exportar como CSV e importalo. |
| Los botones no funcionan | Presiona `Ctrl+Shift+R` en el navegador para limpiar cache. |
| Las caratulas no aparecen | mutagen cubre MP3/FLAC/M4A/OGG. Algun formato puede no soportarse. |
| Audio no reproduce | Prueba con Chrome/Firefox/Edge actualizados. |
| Pestaña Duplicados vacia | Escanea tu musica en "Mi Musica" primero. |
| El reproductor se detiene al cambiar de pestana | Es normal: hay una pausa breve. Al volver, se restaura desde la posicion guardada. |

## Actualizar dependencias

```bat
cd music_manager
.venv\Scripts\activate
pip install --upgrade flask mutagen yt-dlp requests Pillow spotipy python-dotenv Send2Trash
```
