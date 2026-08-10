# Music Manager v1.11

Aplicacion web local para gestionar tu biblioteca musical: ver todos tus
archivos de audio, compararlos con playlists publicas de YouTube Music o
Spotify, guardar accesos directos a playlists, detectar duplicados,
reproducir canciones y editar metadata + caratulas.

## Novedades en v1.11
- ** Correcciones en la UI
## Novedades en v1.10
- ** Correcciones en la UI
## Novedades en v1.9

- **Control de volumen en el reproductor**: barra horizontal deslizable
  entre la barra de progreso y el boton X. Incluye icono 🔊/🔉/🔇 que
  al hacer clic silencia/activa el sonido. El volumen se mantiene entre
  canciones y entre recargas de pagina.
- **Reproductor persistente entre pestanas**: si cambias de pestana
  (por ejemplo, vas a Mi Musica mientras suena una cancion), la musica
  sigue sonando. Al volver, el reproductor se restaura con la posicion
  correcta. Solo se cierra al pulsar la X.
- **Bug corregido: comparar playlists CSV guardadas**: antes, al pulsar
  "Comparar" en una playlist importada desde CSV, fallaba porque el
  endpoint no reconocia URLs `csv://`. Ahora funciona correctamente.
- **Playlists CSV en archivos JSON individuales**: las playlists
  importadas desde CSV ahora se guardan cada una en su propio archivo
  JSON en `data/Spotify/<nombre>.json` (en vez de todas mezcladas en
  `saved_playlists.json`). Asi puedes verlas en el explorador de
  archivos, copiarlas, respaldarlas, etc. El indice
  `saved_playlists.json` sigue existiendo pero solo con metadatos.
- **Clic en ruta abre explorador**: en Mi Musica y en Duplicados, al
  hacer clic en la columna Ruta se abre el explorador de archivos del
  sistema (Windows Explorer en Windows) con el archivo seleccionado.
- **Icono 💡 en banner de Spotify**: cambia el ℹ por 💡 para que se
  vea mas como una sugerencia.

## Novedades en v1.8 (heredadas)

- **Editor completamente reescrito (v1.9 del JS)**: el editor se rompio
  en v1.6 por el cambio de layout. Lo reescribi desde cero con un
  enfoque mas robusto:
  - Todas las referencias al DOM se obtienen DENTRO de cada funcion con
    `document.getElementById()`, no al nivel top-level.
  - Esto evita que un elemento faltante rompa TODO el script.
  - Si un elemento no existe, solo esa funcion falla, las demas siguen
    funcionando.
  - Se eliminaron las constantes top-level que podian ser null.
- **Cache-busting en todos los JS y CSS**: todas las referencias a
  archivos estaticos ahora incluyen `?v=19` para forzar al navegador
  a cargar la version nueva y no usar cache viejo. **IMPORTANTE: si
  ya tenias una version anterior, despues de actualizar haz
  Ctrl+Shift+R (o Ctrl+F5) en el navegador para limpiar cache.**
- **Banner de Spotify simplificado**: se elimino toda la configuracion
  de credenciales de Spotify (Client ID, Client Secret, login OAuth,
  setup_spotify.bat). En su lugar, ahora hay un banner claro que
  explica como usar https://exportify.app/ para exportar playlists de
  Spotify como CSV e importarlas completas. Es mas simple y no requiere
  configurar nada.
- **Soporte para CSV de Exportify**: importa playlists de Spotify
  exportadas como CSV desde https://exportify.app/. Resuelve el
  problema de playlists grandes (+100 canciones) que Spotify bloquea.
  - En "Playlists Guardadas": boton "📄 Importar CSV".
  - En "Comparar Playlist": boton "📄 CSV".
  - Soporta CSV en español e inglés.
- **Carga automatica desde Mi Musica**: al hacer clic en una cancion,
  el editor la carga automaticamente (sin necesidad de pulsar "Cargar").

## Novedades en v1.7 (heredadas)

- **Comparar con Playlist: nuevas columnas**:
  - **Calidad local**: muestra la calidad del archivo local coincidente
    (16-bit/44.1 kHz, 24-bit/96 kHz, MP3 320 kbps, etc.)
  - **Formato**: badge de extension con color (FLAC verde, MP3 naranja, etc.)
  - **Escuchar local**: boton play para reproducir el archivo local
    directamente desde la comparacion
  - **Quitar columna Album**: se elimino porque casi nunca aporta info
    util en el contexto de comparacion.
- **Comparar: "Abrir online" con icono de plataforma**:
  - YouTube Music: `Abrir ▶` en rojo (#ff0000)
  - Spotify: `Abrir ♫` en verde (#1db954)
- **Comparar: persistencia al cambiar de pestana**: la comparacion
  se guarda en `sessionStorage` y se restaura al volver a la pestana
  Comparar. Ya no se pierde al ir a Mi Musica y volver.
- **Editor corregido**: el panel ahora tiene `hidden` inicialmente
  (antes se mostraba vacio). Al hacer clic en una cancion desde Mi
  Musica, el editor carga correctamente la cancion para editar.
- **Boton Explorar con feedback**: ahora muestra "Abriendo..." mientras
  se abre el dialogo nativo, y un toast recordando revisar si aparece
  detras del navegador.
- **Mi Musica: auto-rescan al volver**: si cargaste, refrescaste o
  eliminaste playlists en "Playlists Guardadas", al volver a Mi Musica
  se re-escanea automaticamente la ultima carpeta para actualizar las
  columnas de playlist de cada cancion.
- **Mi Musica: bug de canciones duplicadas en playlist corregido**:
  si una cancion aparecia varias veces en la misma playlist de
  YouTube Music (yt-dlp a veces lista el mismo video multiples veces),
  se mostraba 2+ puntos del mismo color. Ahora se cuenta una sola vez
  por playlist.
- **Iconos del reproductor actualizados**: ⏪⏩ cambiados a ◀◀ ▶▶.

## Novedades en v1.6 (heredadas)

- **Bug corregido: links de Spotify**: las URLs de las canciones de
  Spotify ahora se generan correctamente como
  `https://open.spotify.com/track/...` (antes salian como
  `https//open.spotify.com/...` sin los dos puntos, lo que hacia que
  el navegador los tratara como rutas relativas y se rompieran).
- **Bug corregido: pestaña Duplicados vacia**: ahora el endpoint
  devuelve `total_local` correctamente y la UI muestra los grupos.
  Ademas, hay estado de carga visible y mensajes claros cuando no
  hay duplicados.
- **Tabla de Mi Música aprovecha todo el ancho**: la tabla ahora
  ocupa todo el espacio disponible. La columna Nombre tiene ancho
  minimo amplio (200-350px) y permite multi-linea (rompe palabras
  largas). La columna Tamaño ya no se sale del cuadro.
- **Botón "Buscar" movido al header**: en el Editor de Metadata, el
  boton "Buscar en internet" ahora esta junto al titulo "Busqueda de
  metadata" (arriba a la derecha), mas comodo que abajo.
- **Renombrar archivo local**: nuevo boton "Renombrar archivo" en el
  editor. Convierte el nombre del archivo a `titulo - artista.ext`
  usando los metadatos editados. Sanea caracteres invalidos
  (`<>:"/\|?*` se reemplazan por `_`). Util para limpiar nombres
  como `[YoutubeConverter.Me]_cancion.mp3`.
- **Iconos de plataforma en "Ir a cancion"**: en el detalle de
  playlist guardada, la columna "Ir a cancion" ahora muestra un
  icono de color segun la plataforma:
  - **▶ rojo** para YouTube Music
  - **♫ verde** para Spotify
- **setup_spotify.bat corregido**: instrucciones actualizadas con el
  flujo correcto basado en AniTail:
  - Redirect URI: `http://127.0.0.1:8888` (no `:1`)
  - Marcar "Web API" en Which API/SDKs
  - El `.env` ahora incluye `SPOTIPY_REDIRECT_URI`
- **Etiquetas "YouTube Music" completas**: en vez de "YT Music" ahora
  se muestra "YouTube Music" en todas partes.

## Novedades en v1.4 (heredadas)

- **Botones de accion con colores en "Playlists Guardadas"**: cada boton
  tiene su color para identificarlo rapido:
  - ♪ Abrir (azul)
  - ⇄ Comparar (verde) - **NUEVO**: manda la playlist a la pestana
    Comparar para ver que te falta.
  - ↻ Refrescar (morado)
  - ⧉ Copiar enlace (cyan) - **NUEVO**: copia la URL al portapapeles
    para pegarla donde quieras.
  - ✎ Renombrar (naranja)
  - 🗑 Eliminar (rojo)
- **Comparar con URL precargada**: al hacer clic en "Comparar" desde
  Playlists Guardadas, se abre la pestana Compare con la URL ya cargada
  y se ejecuta la comparacion automaticamente.
- **Mejora en manejo de Spotify**:
  - Ahora intenta primero la Spotify Web API con token anonimo para
    obtener TODAS las canciones (paginacion en paralelo).
  - Si Spotify bloquea por rate-limit (HTTP 429 con quota), cae
    rapidamente al fallback del embed (100 canciones) y muestra
    advertencia clara al usuario.
  - Recomendacion: si Spotify solo carga 100, usa la misma playlist
    en YouTube Music (carga completa, 600+ canciones).

## Novedades en v1.1 (heredadas)

- **Nueva pestaña "Playlists Guardadas"**: guarda enlaces de playlists
  publicas para acceso rapido sin volver a pegar el link. Las canciones
  se cachean localmente.
- **Columna "Playlists" en "Mi Musica"**: cada cancion local muestra
  puntos de color indicando en que playlists guardadas aparece
  (rojo = YouTube Music, verde = Spotify).
- **Columna "Reproducir"**: boton play en cada fila; reproductor
  flotante con seek que funciona con todos los formatos.
- **Deteccion de duplicados**: encuentra canciones repetidas (mismo
  titulo + artista) en diferentes formatos/calidades. Marca cual es la
  mejor version para conservar y calcula el espacio recuperable.
- **Editor de caratulas**: ver, redimensionar (300/500/600/1000/1500px,
  JPEG/PNG/WEBP), descargar desde URL y eliminar caratulas embebidas
  en MP3, FLAC, M4A, OGG.
- **Multi-fuente de metadata**: busca en iTunes, MusicBrainz, Last.fm
  o todas a la vez. Cada resultado muestra miniatura de caratula y
  boton "Usar esta caratula".
- **Guardar playlist desde "Comparar"**: boton para mandar la playlist
  que estas comparando directamente a favoritos.

## Caracteristicas heredadas (v1.0)

- Escaneo local recursivo (subcarpetas). Soporta MP3, FLAC, WAV, M4A,
  AAC, OGG, Opus, AIFF, ALAC, APE, WavPack.
- Deteccion de calidad: 16-bit/44.1kHz (CD), 24-bit/96kHz (Hi-Res),
  bitrate, canales.
- Comparacion con playlists publicas de YouTube Music y Spotify sin
  iniciar sesion ni registrar apps.
- Exportar faltantes como CSV.
- Editor de metadata manual.

## Requisitos

- **Python 3.10 o superior** (https://www.python.org/downloads/)
  - Marca "Add Python to PATH" durante la instalacion.
- **ffmpeg** (opcional, solo necesario para reproducir algunos formatos
  en el navegador; la mayoria de navegadores ya soportan MP3, FLAC, WAV,
  M4A y OGG nativamente).
- Navegador moderno (Chrome, Firefox, Edge).
- Conexion a internet para leer playlists y buscar metadata.

## Importar playlists grandes de Spotify (con Exportify)

Spotify no permite leer mas de 100 canciones de una playlist publica sin
credenciales oficiales. En lugar de configurar credenciales, lo mas
simple es exportar la playlist como CSV desde https://exportify.app/ e
importarla aqui. Asi se cargan TODAS las canciones sin limite.

### Pasos

1. Entra a https://exportify.app/ en tu navegador.
2. Pulsa "Get Started" e inicia sesion con tu cuenta de Spotify
   (alli si puedes, es la app oficial de Exportify).
3. Veras la lista de todas tus playlists.
4. Pulsa "Export" en la playlist que quieres importar.
5. Se descargara un archivo `.csv`.
6. En Music Manager, ve a "Playlists Guardadas" y pulsa
   "📄 Importar CSV". Selecciona el archivo descargado.
7. La playlist se guarda con todas sus canciones.

Tambien puedes importar un CSV directamente en "Comparar Playlist"
con el boton "📄 CSV" sin guardarla en favoritos.

## Instalacion en Windows

1. Copia la carpeta `music_manager/` donde quieras tener el proyecto.
2. Haz **doble clic en `setup_env.bat`**.
   - Crea entorno virtual `.venv` e instala Flask, mutagen, yt-dlp,
     requests, Pillow, spotipy y python-dotenv.
   - Solo se hace la primera vez.
3. Si vienes de una version anterior: ejecuta `setup_env.bat` de nuevo
   (responde "S" para recrear el entorno) para instalar todas las
   dependencias nuevas.
4. **No necesitas configurar Spotify**: para playlists grandes usa
   Exportify (ver seccion anterior).

## Uso

1. **Doble clic en `run.bat`**.
2. Se abre el navegador en http://127.0.0.1:5000.
3. Para detener: cierra la ventana negra (CMD) o presiona `Ctrl+C`.

## Estructura del proyecto

```
music_manager/
|-- main.py              <- arranca la aplicacion
|-- setup_env.bat        <- configura el entorno (ejecutar 1 vez)
|-- setup_spotify.bat    <- configura credenciales Spotify  (NUEVO v1.3)
|-- run.bat              <- ejecuta la aplicacion
|-- requirements.txt     <- librerias necesarias
|-- .env                 <- credenciales Spotify (NUEVO v1.3, no se sube a git)
|-- data/                <- se crea automaticamente
|   `-- saved_playlists.json  <- playlists guardadas (cache)
|-- app/                 <- codigo Python modular
|   |-- scanner.py           -> escanea carpetas
|   |-- metadata_reader.py   -> lee/escribe tags
|   |-- audio_quality.py     -> interpreta calidad
|   |-- playlist_youtube.py  -> lee playlists YT Music
|   |-- playlist_spotify.py  -> lee playlists Spotify (con cascada de fallback)
|   |-- spotify_official.py  -> API oficial via spotipy  (NUEVO v1.3)
|   |-- auto_metadata.py     -> busca metadata en iTunes/MusicBrainz/Last.fm
|   |-- saved_playlists.py   -> persiste playlists en JSON
|   |-- duplicates.py        -> detecta canciones repetidas
|   |-- artwork.py           -> caratulas: ver/redimensionar/descargar
|   `-- web_app.py           -> servidor Flask con todas las rutas
|-- templates/           <- HTML de las 4 pestañas
|   |-- base.html            -> layout comun (sidebar + reproductor)
|   |-- index.html           -> pestana 1: Mi Musica
|   |-- saved_playlists.html -> pestana 2: Playlists Guardadas
|   |-- compare.html         -> pestana 3: Comparar playlist
|   `-- editor.html          -> pestana 4: Editor de metadata
`-- static/              <- CSS y JS
    |-- css/style.css       -> estilo oscuro tipo Spotify
    `-- js/
        |-- app.js          -> utilidades compartidas
        |-- player.js       -> reproductor flotante
        |-- local.js        -> pestana 1 (con playlists, play, dup)
        |-- saved_playlists.js -> pestana 2
        |-- compare.js      -> pestana 3 (con guardar en favoritos)
        `-- editor.js       -> pestana 4 (caratulas + multi-fuente)
```

## Como usar cada pestana

### 1. Mi Musica

- Escribe la ruta o pulsa **Explorar** para elegir carpeta.
- Pulsa **Escanear**. Se leen todos los archivos de audio
  (incluyendo subcarpetas) y se muestra la tabla.
- Columnas: # / Play / Nombre / Artista / Album / Duracion / Formato /
  Calidad (opcional) / Playlists / Tamano / Ruta.
- Los puntos de color en "Playlists" indican en que playlists guardadas
  aparece esa cancion (rojo = YouTube Music, verde = Spotify). Pasa el
  raton para ver el nombre.
- El badge **DUP** en "Tamano" indica que esa cancion esta repetida. La
  estrella (★) marca la version de mejor calidad (la que deberias
  conservar). Haz clic en el badge para abrir el modal de duplicados.
- Boton play en cada fila reproduce la cancion en el reproductor
  flotante inferior.
- Filtros: buscar, formato, playlist, duplicadas/unicas, ordenar.
- Clic en una fila abre el editor con ese archivo.

### 2. Playlists Guardadas

- Pega el link de una playlist publica de YouTube Music o Spotify.
- Pulsa **Guardar playlist**. Se descarga y se almacena localmente.
- Cada playlist aparece como una tarjeta con icono de plataforma
  (rojo YT Music, verde Spotify), nombre, autor, numero de canciones
  y fecha de ultimo acceso.
- Acciones por playlist:
  - **Abrir**: ver detalle con todas las canciones.
  - **↻**: refrescar (volver a descargar desde internet).
  - **✎**: renombrar.
  - **🗑**: eliminar de favoritos (no borra archivos locales).

### 3. Comparar Playlist

- Asegurate de haber escaneado tu musica en pestana 1.
- Pega el link de una playlist publica.
- Pulsa **Cargar Playlist**. Se comparan las canciones con tu
  biblioteca local.
- Botones:
  - **Ver faltantes**: las que no tienes.
  - **Ver coincidencias**: las que ya tienes.
  - **Exportar faltantes (CSV)**: descarga para buscarlas luego.
  - **Guardar en favoritos**: anade la playlist a la pestana 2.

### 4. Editar Metadata

- Escribe la ruta o pulsa **Explorar** (dialogo nativo de archivo).
- Edita los campos manualmente o pulsa **Buscar en internet**.
- Selector de fuente:
  - **iTunes** (recomendado, mejor cobertura comercial).
  - **MusicBrainz** (buena para albumes clasicos/indie, devuelve
    caratulas via Cover Art Archive).
  - **Last.fm** (scraping ligero de la pagina publica).
  - **Todas** (combina las 3 fuentes).
- Cada resultado muestra: fuente, titulo, artista, album, año, y
  miniatura de caratula. Botones:
  - Click en la fila: rellenar formulario.
  - **Usar esta caratula**: descargar la caratula y embeberla en el
    archivo.
- Panel de caratula:
  - Vista previa + info (dimensiones, tamano, MIME).
  - **Redimensionar**: elegir tamano (300-1500px) y formato
    (JPEG/PNG/WEBP).
  - **Eliminar**: quitar caratula embebida.
  - **Pegar URL de caratula**: descargar y embeber desde internet.

## Limitaciones conocidas

- **YouTube Music y Spotify**: solo playlists **publicas**.
- **Last.fm**: funciona via scraping del HTML. Si Last.fm cambia su
  pagina, podria fallar (las otras fuentes siguen funcionando).
- **Reproductor**: depende del navegador. La mayoria soporta MP3,
  FLAC, WAV, M4A y OGG. Para Opus/APE/WV necesitas convertir primero.
- **Spotify embed**: si Spotify cambia el formato, podria fallar.
- **yt-dlp**: ejecuta `pip install --upgrade yt-dlp` en `.venv` si
  YouTube Music deja de funcionar.

## Solucion de problemas

| Problema | Solucion |
|---|---|
| `Pillow no se instala` | Ejecuta `setup_env.bat` de nuevo; si persiste, `pip install Pillow` manual. |
| `spotipy no se instala` | Ejecuta `setup_env.bat` de nuevo (v1.3+); si persiste, `pip install spotipy python-dotenv` manual. |
| Spotify solo carga 100 canciones | Usa Exportify (https://exportify.app/) para exportar la playlist como CSV e importala con "📄 Importar CSV" en Playlists Guardadas. |
| Spotify login no completa | Ya no se necesita login. Usa Exportify para exportar tus playlists como CSV. |
| Pestaña Duplicados vacia | Asegurate de haber escaneado tu musica en "Mi Musica" primero. Despues pulsa "↻ Recalcular" en la pestaña Duplicados. |
| Error al actualizar desde v1.x | Borra `.venv` y vuelve a ejecutar `setup_env.bat`. |
| YouTube Music no carga | `pip install --upgrade yt-dlp` dentro de `.venv`. |
| Spotify no carga | Verifica que la playlist sea publica. Si configuraste credenciales y aun falla, revisa que el Client ID/Secret en `.env` sean correctos. |
| Las caratulas no aparecen | Algun formato puede no soportarse; mutagen cubre MP3/FLAC/M4A/OGG. |
| Audio no reproduce en navegador | Prueba con Chrome/Firefox/Edge actualizados. |
| Banner sigue apareciendo tras configurar | Reinicia `run.bat` (las credenciales se cargan al arrancar). |

## Actualizar dependencias

```bat
cd music_manager
.venv\Scripts\activate
pip install --upgrade flask mutagen yt-dlp requests Pillow
```
