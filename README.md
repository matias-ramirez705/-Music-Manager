# Music Manager v3.16

Aplicacion web local para gestionar tu biblioteca musical: ver todos tus
archivos de audio, compararlos con playlists publicas de YouTube Music o
Spotify, comparar carpetas (PC vs DAP), generar dummies para Spotiflac,
guardar accesos directos a playlists, detectar duplicados, reproducir
canciones, editar metadata + caratulas + letras masivamente, ver
canciones eliminadas, organizar por carpetas, acceder a un indice de
sitios para descargar musica FLAC.

## Novedades en v3.16

- **Nueva pestana "📦 Spotiflac"**: genera archivos dummy (senuelo) tiny
  a partir de tu musica real para enganar a Spotiflac y que marque como
  duplicadas las canciones que ya pasaste al Hiby R1, sin ocupar espacio
  real. Incluye:
  - Tracking de canciones ya generadas (en `data/spotiflac_dummies.json`):
    la proxima vez solo genera las nuevas, no todo desde cero.
  - Soporta 11 formatos: FLAC, OPUS, OGG, M4A/MP4, AAC, MP3, WAV, AIFF,
    APE, WV, WMA.
  - FLAC con metadata real (VORBIS_COMMENT con titulo/artista/album/
    genero/ISRC). Los demas formatos son stubs minimos.
  - Preview antes de generar: ver que archivos se van a generar, con que
    nombre y formato.
  - Modo de nombres: original del archivo o formato Spotiflac
    (`Titulo - Artista.ext`).
  - Historial completo con fecha, opcion de vaciarlo.
  - Descarga directa del ZIP desde el navegador.
  - Instrucciones integradas (ruta del telefono, pasos a seguir).

## Novedades en v3.15

- **Bug arreglado: info tecnica N/A en archivos Opus**: mutagen no expone
  sample_rate ni bitrate para Opus (es lossy con sample_rate nativo fijo
  de 48000 Hz). Ahora se reporta 48000 Hz como sample rate y se estima
  el bitrate desde `(tamano * 8) / duracion`.
- **Nuevo filtro "⚠ Falta info tecnica" en Mi Musica**: detecta
  rapidamente que canciones tienen metadata tecnica incompleta
  (duration=0 OR bitrate=0 OR sample_rate=0 OR channels=0).
- **Bug arreglado: borrados desde Duplicados no aparecian en Eliminados**:
  ahora `/api/delete-file` captura la metadata ANTES de borrar y la
  registra en `data/deleted_songs.json` automaticamente. No hace falta
  re-escanear Mi Musica para que aparezcan en la pestana Eliminados.

## Novedades en v3.14

- **Bug arreglado: sub-pestana Caratulas solo mostraba 363 de 809
  canciones**: el endpoint `/api/batch/artwork-status` truncaba la lista
  a `[:300]` por categoria (con caratula + sin caratula = max 600).
  Quitado el limite, ahora muestra TODAS las canciones.
- Mismo bug arreglado en `/api/batch/lyrics-status` (tambien tenia
  `[:300]`).

## Novedades en v3.13

- **Bug arreglado: sub-pestana Caratulas perdia el buscador al cambiar
  una caratula**: antes, al guardar una caratula nueva se llamaba
  `checkArtwork()` que re-escaneaba todo y reconstrucia el HTML,
  perdiendo el texto del buscador, el filtro seleccionado y la posicion
  de scroll. Ahora se preserva todo automaticamente:
  - Texto del buscador se mantiene
  - Filtro (Todas / Con caratula / Sin caratula) se mantiene
  - Filtro por extension se mantiene
  - Posicion de scroll se mantiene
  - Bonus: la fila del archivo recien modificado se resalta en verde
    por 1.2 segundos para que sepas donde estabas.

## Novedades en v3.12

- **Nueva pestana "⇄ Comparar Carpetas"**: compara los archivos de audio
  de dos carpetas distintas (ej: tu PC vs tu DAP Hiby R1) para ver que
  canciones te faltan pasar. Incluye:
  - 2 paneles en paralelo (PC | DAP) con columnas: #, Nombre del
    archivo, Formato, Duracion, Peso.
  - Colores para identificar facilmente: rojo (solo en A, faltan en B),
    naranja (solo en B, faltan en A), verde (comunes).
  - Click en cualquier fila abre el explorador de archivos de Windows
    con ese archivo seleccionado.
  - Buscador en tiempo real + checkboxes para mostrar/ocultar comunes
    o faltantes.
  - Coincidencia por titulo normalizado (sin acentos, lowercase, sin
    parentesis, sin feat/ft) para que funcione aunque tengas formatos
    distintos (MP3 vs FLAC) o nombres ligeramente distintos.

## Novedades en v3.11

- **Correccion de v3.10**: la pestaña Metadatos YA tenia 3 sub-pestanas
  (Editar Metadata, Caratulas, Letras) que se rompieron al reescribir
  `editor.html`. Ahora restauradas correctamente.
- **Cuarta sub-pestana "🔤 Renombrar" (Analizador de Nombres)**: compara
  el nombre del archivo en disco con el titulo/artista de la metadata.
  Las canciones marcadas con ⚠ podrian necesitar renombrarse. Incluye:
  - Tabla: #, Nombre del archivo, Nombre cancion (metadata), Artista,
    Renombrar.
  - Buscador en tiempo real + filtro por estado (Todas / Solo las que
    necesitan renombrar / Solo las OK).
  - Boton renombrar en cada fila con proteccion anti-colision
    (automaticamente anade _1, _2, _3, ... si ya existe un archivo con
    ese nombre).
  - Click en fila abre el archivo en "Editar Metadata".
  - Badge visual naranja (Revisar) o verde (OK) para identificar
    rapidamente que falta arreglar.

## Novedades en v3.10

- **Volumen del Preview en Editar Metadata**: el preview de 30s desde
  iTunes ahora respeta el volumen del reproductor principal (antes
  sonaba al 100% sin importar el slider). Se sincroniza en tiempo real:
  si moves el slider mientras suena el preview, el volumen se actualiza
  al instante.
- **Renombrado anti-colision**: si al renombrar ya existe un archivo con
  ese nombre, NO falla: automaticamente anade _1, _2, _3, ... hasta
  encontrar uno libre. Limpieza inteligente de sufijos previos (no apila
  _1_1_1).

## Novedades en v3.9

- **Boton "↻ Recargar" de Eliminados tambien re-escanea Mi Musica**:
  antes solo refrescaba la lista actual, no detectaba nuevas
  eliminaciones. Ahora consulta la carpeta previa, llama a `/api/scan`
  (que dispara la deteccion de eliminados en el backend) y recarga la
  lista. Muestra toast con cuantas eliminadas nuevas se detectaron.
- **Anchos y alineaciones de tabla Eliminados** (#deleted-table):
  Nombre agrandado 2.5x, Formato y Playlists centrados, Eliminar
  achicado a la mitad y centrado.
- **Centrar boton play en "Escuchar local" de Comparar con Playlist**:
  el boton .play-btn tiene `display:flex` que ignora `text-align:center`
  del td. Anadido `margin: 0 auto` especifico.
- **Modal de playlist guardada (pestaña Playlists Guardadas)**: Titulo
  agrandado y alineado a izquierda, "Ir a cancion" achicado y centrado,
  Duracion centrada.

## Novedades en v3.8

- **Nueva pestana "🗑 Eliminados"**: canciones que borraste del disco.
  Se detectan automaticamente al re-escanear tu biblioteca. Incluye:
  - Columnas: #, Nombre, Artista, Formato, Playlists (dots clickeables
    como en Mi Musica), Comentario (clic para editar), Eliminar (boton
    de quitar de la lista, no toca el disco).
  - Modal de comentario con presets "No me gusto" / "Repetida" o
    comentario libre.
  - Filtro por tipo de comentario (sin comentario / "No me gusto" /
    "Repetida" / personalizado).
  - Persistencia en `data/deleted_songs.json`.
  - Deteccion automatica: al re-escanear Mi Musica, compara con el
    escaneo anterior y registra las canciones que ya no estan en el disco.
  - Exclusion automatica: las canciones eliminadas NO aparecen como
    "faltantes" en Comparar con Playlist (el usuario ya decidio borrarlas
    a proposito).

## Novedades en v3.6 - v3.7

- **Headers anti-cache en Flask**: fuerza al navegador a siempre pedir
  HTML/JS/CSS frescos. Evita el bug de "veo la version vieja del codigo"
  tras editar.
- **Alineaciones y anchos corregidos** en Mi Musica, Comparar Playlist y
  modal de playlist:
  - Mi Musica: duracion, formato y copiar centrados; Artista ancha para
    que no se corte el nombre; Ruta mas compacta.
  - Comparar: bug de columna Copiar/Abrir online intercambiados corregido
    (el boton 📋 Copiar ahora cae en su columna, no en "Abrir online").
  - Modal de playlist: titulo a la izquierda; album y duracion centrados;
    columnas redimensionadas.

## Novedades en v3.0–v3.5

- **Pestana "Metadatos" con sub-pestanas**: Editar Metadata, Caratulas
  (masivo) y Letras (masivo).
- **Caratulas masivo**: analizar, redimensionar todas, descargar
  faltantes desde iTunes, busqueda manual con multiple fuente.
- **Letras masivo**: analizar, descargar faltantes desde lrclib.net,
  ver letra con reproductor integrado, busqueda manual con preview.
- **Seguidor de letra sincronizada** (LRC) en el reproductor principal.
- **Reproductor flotante persistente**: al cambiar de pestana, la musica
  se restaura al volver con la posicion correcta.
- **Control de volumen** en el reproductor con icono 🔊/🔉/🔇.
- **Clic en ruta abre explorador** en Mi Musica y Duplicados.
- **Playlists CSV en archivos JSON individuales**: cada playlist
  importada desde CSV se guarda en `data/Spotify/<nombre>.json`.
- **Bug corregido: canciones con apostrofos** (Can't Stop, Don't Know
  What To Say, etc.) ahora funcionan correctamente.

## Novedades en v2.0–v2.1

- **Pestana "⬇ Descargas FLAC"**: indice de 48 sitios y programas para
  descargar musica en FLAC, extraidos de https://fmhy.net/audio.
  - Audio Ripping Sites, Audio Ripping Tools (streamrip, OrpheusDL,
    SpotiFLAC, DeemixFix, etc.), Telegram Bots, Download Sites, sitios
    por genero.
  - Archivo `data/download_sites.txt` editable desde la UI.
  - Buscador, filtros, toggle de estado (OK/Caido).
- **Agregar enlaces a la lista de Descargas FLAC** con verificacion
  automatica de duplicados.

## Novedades en v1.12–v1.16

- **Pestana "📁 Organizar"**: mueve canciones a subcarpetas por playlist.
  Modo individual (boton por fila) o plan masivo. Resolucion de
  conflictos cuando una cancion esta en varias playlists.
- **Cargar playlists desde TXT**: importacion masiva de URLs de
  playlists con comentarios.
- **Anchos de columna en Comparar Playlist** con `table-layout: fixed`.
- **Dots de color en Organizar** (rojo = YouTube Music, verde = Spotify).

## Caracteristicas principales

### 9 pestanas:

1. **♪ Mi Música** — escanea carpetas, muestra tabla con nombre, artista,
   álbum, duración, formato, calidad (bits/kHz), playlists, tamaño y ruta.
   Reproductor integrado, filtros (formato, playlist, duplicados,
   metadata con error, falta info técnica), búsqueda, badges de
   duplicados. Clic en ruta abre explorador.

2. **⧉ Duplicados** — detecta canciones repetidas en diferentes
   formatos/calidades. Marca la mejor versión. Botón borrar con doble
   confirmación (envia a papelera de reciclaje). Las canciones borradas
   se registran automáticamente en la pestaña Eliminados. Exportar CSV.

3. **★ Playlists Guardadas** — guarda enlaces de playlists públicas de
   YouTube Music o importa playlists de Spotify desde CSV (Exportify).
   Carga masiva desde TXT. Cada playlist CSV se guarda en su propio JSON.
   Modal de detalle con tabla y buscador integrado.

4. **⇄ Comparar Playlist** — compara tu música local con una playlist.
   Muestra faltantes, coincidencias, calidad local, formato, botón
   reproducir local, y enlace a la plataforma con color. Las canciones
   en la pestaña Eliminados se excluyen automáticamente de los
   faltantes. Exporta CSV. Persiste entre pestañas.

5. **✎ Metadatos** — con 4 sub-pestañas:
   - **Editar Metadata**: edita tags (título, artista, álbum, año,
     pista, género). Busca metadata en iTunes, MusicBrainz, Last.fm con
     preview de 30s que respeta el volumen del reproductor. Gestiona
     carátulas. Renombrar archivo con protección anti-colisión.
   - **🖼 Carátulas** (masivo): analizar, redimensionar todas, descargar
     faltantes desde iTunes. Preserva el buscador y scroll al cambiar
     una carátula. Muestra TODAS las canciones (sin límite).
   - **📝 Letras** (masivo): analizar, descargar faltantes desde
     lrclib.net, ver letra con reproductor integrado.
   - **🔤 Renombrar** (Analizador de Nombres): compara el nombre del
     archivo en disco con el título/artista de la metadata. Botón
     renombrar con anti-colisión.

6. **📁 Organizar** — mueve canciones a subcarpetas por playlist.
   Modo individual (botón por fila) o plan masivo. Resolución de
   conflictos cuando una canción está en varias playlists.

7. **⬇ Descargas FLAC** — índice de 48 sitios/programas para descargar
   música FLAC. Agregar enlaces, editar TXT, toggle de estado.
   Extraído de fmhy.net/audio.

8. **🗑 Eliminados** — canciones que borraste del disco. Se detectan
   automáticamente al re-escanear o al borrar desde Duplicados.
   Comentarios con presets ("No me gustó", "Repetida") o texto libre.
   Dots de playlist para ver en qué playlists estaba. Botón quitar de
   la lista (no toca el disco).

9. **⇄ Comparar Carpetas** — compara archivos de audio de 2 carpetas
   (ej: PC vs DAP Hiby R1). 2 paneles en paralelo con colores: rojo
   (solo en A), naranja (solo en B), verde (comunes). Click en fila
   abre explorador.

10. **📦 Spotiflac** — genera archivos dummy tiny para engañar a
    Spotiflac y que marque como duplicadas las canciones que ya pasaste
    al Hiby R1. Tracking de generados, soporta 11 formatos, FLAC con
    metadata real. Descarga directa del ZIP.

### Reproductor flotante:
- Carátula miniatura, controles play/pausa/skip, barra de progreso
  personalizada con gradiente verde, control de volumen.
- Persiste entre pestañas (restaura posición al volver).
- Volumen sincronizado con el preview de iTunes en Editar Metadata.
- Seguidor de letra sincronizada (LRC).
- Solo se cierra al pulsar la X.

### Soporte de formatos:
- **Audio**: MP3, FLAC, WAV, M4A, AAC, OGG, Opus, AIFF, ALAC, APE, WavPack
- **Opus**: info técnica con sample_rate 48000 nativo y bitrate estimado
- **Playlists**: YouTube Music (completo), Spotify (100 por URL o CSV
  ilimitado via Exportify)
- **Metadata**: iTunes, MusicBrainz, Last.fm
- **CSV**: Exportify (español e inglés)
- **Dummies Spotiflac**: FLAC, OPUS, OGG, M4A/MP4, AAC, MP3, WAV, AIFF,
  APE, WV, WMA

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
|-- data/                    <- se crea automaticamente al arrancar
|   |-- saved_playlists.json <- indice de playlists guardadas
|   |-- deleted_songs.json   <- registro de canciones eliminadas
|   |-- spotiflac_dummies.json <- tracking de dummies generados
|   |-- playlists.txt        <- URLs para carga masiva de playlists
|   |-- download_sites.txt   <- indice de sitios para descargar FLAC
|   `-- Spotify/             <- playlists CSV en JSON individuales
|-- app/                     <- codigo Python modular
|   |-- scanner.py           -> escanea carpetas
|   |-- metadata_reader.py   -> lee/escribe tags (mutagen) + workaround Opus
|   |-- audio_quality.py     -> interpreta calidad (bits, kHz, etc.)
|   |-- playlist_youtube.py  -> lee playlists YT Music
|   |-- playlist_spotify.py  -> lee playlists Spotify
|   |-- spotify_official.py  -> API oficial via spotipy (opcional)
|   |-- auto_metadata.py     -> busca metadata en iTunes/MusicBrainz/Last.fm
|   |-- csv_playlist.py      -> parsea CSV de Exportify
|   |-- txt_playlist.py      -> parsea TXT con URLs de playlists
|   |-- saved_playlists.py   -> persiste playlists en JSON
|   |-- duplicates.py        -> detecta canciones repetidas
|   |-- deleted_songs.py     -> persiste canciones eliminadas
|   |-- artwork.py           -> caratulas: ver/redimensionar/descargar
|   |-- batch_artwork.py     -> caratulas masivo
|   |-- lyrics.py            -> letras: leer/descargar/lrc
|   |-- batch_lyrics.py      -> letras masivo
|   |-- organizer.py         -> mueve canciones por playlist
|   |-- download_sites.py    -> gestiona indice de sitios FLAC
|   |-- folder_compare.py    -> compara 2 carpetas (PC vs DAP)
|   |-- spotiflac_dummy.py   -> genera dummies para Spotiflac
|   `-- web_app.py           -> servidor Flask con todas las rutas
|-- templates/               <- HTML de las pestanas
|   |-- base.html, index.html, duplicates.html
|   |-- saved_playlists.html, compare.html
|   |-- metadata_master.html (sub-pestanas Metadatos)
|   |-- editor.html, organize.html, downloads.html
|   |-- deleted.html, folder_compare.html, spotiflac.html
`-- static/                  <- CSS y JS
    |-- favicon.svg          -> icono de nota musical
    |-- css/style.css        -> estilo oscuro tipo Spotify
    `-- js/
        |-- app.js, player.js, local.js, compare.js
        |-- editor.js, rename.js (Analizador de Nombres)
        |-- duplicates.js, saved_playlists.js
        |-- organize.js, downloads.js
        |-- deleted.js, folder_compare.js, spotiflac.js
        |-- batch_artwork.js, batch_lyrics.js
```

## Solucion de problemas

| Problema | Solucion |
|---|---|
| Error al actualizar desde v1.x/v2.x/v3.x | Borra `.venv` y vuelve a ejecutar `setup_env.bat`. |
| Veo la version vieja del codigo tras actualizar | Los headers anti-cache (v3.6+) deberian prevenirlo. Si pasa: Ctrl+Shift+R en el navegador. |
| YouTube Music no carga | `pip install --upgrade yt-dlp` dentro de `.venv`. |
| Spotify solo carga 100 canciones | Usa Exportify (https://exportify.app/) para exportar como CSV e importalo. |
| Los botones no funcionan | Presiona `Ctrl+Shift+R` en el navegador para limpiar cache. |
| Las caratulas no aparecen | mutagen cubre MP3/FLAC/M4A/OGG. Algun formato puede no soportarse. |
| Audio no reproduce | Prueba con Chrome/Firefox/Edge actualizados. |
| Pestaña Duplicados vacia | Escanea tu musica en "Mi Musica" primero. |
| Pestaña Eliminados vacia | Se llena automaticamente al borrar canciones (desde Duplicados o borrando archivos del disco y re-escaneando). |
| Pestaña Renombrar vacia | Escanea tu musica en "Mi Musica" primero. |
| Pestaña Spotiflac vacia | Escanea tu musica en "Mi Musica" primero. |
| Info tecnica N/A en Opus | Normal en v3.14 y anteriores. Actualiza a v3.15+ que tiene workaround. |
| Caratulas solo muestra 363 canciones | Bug de v3.13 y anteriores. Actualiza a v3.14+. |
| El reproductor se detiene al cambiar de pestana | Es normal: hay una pausa breve. Al volver, se restaura desde la posicion guardada. |

## Actualizar dependencias

```bat
cd music_manager
.venv\Scripts\activate
pip install --upgrade flask mutagen yt-dlp requests Pillow spotipy python-dotenv Send2Trash
```

## Flujo de trabajo tipico (PC → Hiby R1 → Spotiflac)

1. **Descargar en Spotiflac** (Android): descarga las canciones que quieras.
2. **Pasar al PC**: copia los archivos de audio del telefono a una carpeta
   del PC.
3. **Escanear en Mi Musica**: abre Music Manager → Mi Musica → escanea
   la carpeta donde copiaste las canciones.
4. **Arreglar metadata**: ve a Metadatos → Editar Metadata. Corrige
   titulo, artista, album. Busca metadata en iTunes si hace falta.
5. **Ajustar caratulas**: ve a Metadatos → Caratulas. Analiza, descarga
   faltantes, redimensiona.
6. **Revisar letras**: ve a Metadatos → Letras. Analiza, descarga
   faltantes.
7. **Renombrar archivos**: ve a Metadatos → Renombrar. Revisa que
   nombres esten OK y renombra los que tengan ⚠.
8. **Pasar al Hiby R1**: copia los archivos arreglados al DAP via USB.
9. **Comparar carpetas**: ve a Comparar Carpetas. Carpeta A = tu musica
   en PC, Carpeta B = la musica en el Hiby R1. Verifica que no te falte
   pasar ninguna cancion.
10. **Borrar del telefono**: borra las canciones del telefono para
    liberar espacio.
11. **Generar dummies para Spotiflac**: ve a Spotiflac. Genera el ZIP de
    dummies, pasalo al telefono, descomprime en
    `/storage/emulated/0/Music/SpotyFlac/`. Escanea la biblioteca en
    Spotiflac. Ahora las canciones que ya pasaste al Hiby R1 aparecen
    como duplicadas al buscar, evitando que las descargues de nuevo.
