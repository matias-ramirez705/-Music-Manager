"""
app/download_sites.py
=====================
Gestiona el archivo data/download_sites.txt que contiene un indice
de paginas y programas para descargar musica FLAC.

Formato del archivo (tabla separada por |):
  | NOMBRE | LINK | DESCRIPCION | ESTADO |

Donde:
  - NOMBRE: nombre del sitio o programa
  - LINK: URL
  - DESCRIPCION: formato/servicio (ej: "Deezer / FLAC")
  - ESTADO: "OK" o "CAIDO" (lo edita el usuario)

El archivo se crea automaticamente al arrancar la app si no existe,
con una lista predefinida de sitios extraidos de https://fmhy.net/audio
que ofrecen descargas en FLAC.
"""

import os
from pathlib import Path


# Ruta del archivo
DATA_DIR = Path(__file__).parent.parent / 'data'
SITES_FILE = DATA_DIR / 'download_sites.txt'


# Lista predefinida de sitios/herramientas que ofrecen FLAC
# Extraida de https://fmhy.net/audio (secciones Audio Ripping y Download Sites)
DEFAULT_SITES = [
    # === Audio Ripping Sites (sitios web) ===
    ("lucida", "https://lucida.to/", "Multi-Site / 320kb / MP3 / FLAC", "OK"),
    ("DoubleDouble", "https://doubledouble.top/", "Multi-Site / 320kb / FLAC", "OK"),
    ("squid.wtf", "https://squid.wtf/", "KHInsider / JioSaavn / FLAC", "OK"),

    # === Audio Ripping Tools (programas) ===
    ("Firehawk52", "https://github.com/Firehawk52/Firehawk52", "Deezer / Qobuz / Tidal / Requiere registro / FLAC", "OK"),
    ("OnTheSpot", "https://github.com/justin025/onthespot", "Apple Music / Bandcamp / Deezer / Qobuz / Spotify / Tidal / FLAC", "OK"),
    ("Antra", "https://github.com/antra-antra/antra", "Qobuz / Tidal / Amazon Music / Soulseek / Convierte desde multiples sitios / FLAC", "OK"),
    ("streamrip", "https://github.com/nathom/streamrip", "Deezer / Tidal / Qobuz / 128kb Free / FLAC / Usar Firehawk52", "OK"),
    ("OrpheusDL", "https://github.com/OrfiTeam/OrpheusDL", "Deezer / Qobuz / 128kb Free / FLAC / Usar Firehawk52", "OK"),
    ("SpotiFLAC", "https://github.com/spotbye/SpotiFLAC", "Qobuz / Tidal / Amazon Music / FLAC / Playlists / Convierte desde Spotify", "OK"),
    ("DeemixFix", "https://gitlab.com/deeplydrumming/DeemixFix", "Deezer / FLAC", "OK"),
    ("Deemix Revival", "https://github.com/bambanah/deemix", "Deezer / FLAC", "OK"),
    ("SaturnMusic", "https://github.com/SaturnMusic/SaturnMusic", "Deezer / FLAC", "OK"),
    ("QobuzDownloaderX-MOD", "https://github.com/DJDoubleD/QobuzDownloaderX-MOD", "Qobuz / 128kb Free / 256 AAC Premium / FLAC / Usar Firehawk52", "OK"),
    ("qobuz-dl", "https://github.com/vitiko98/qobuz-dl", "Qobuz / 128kb Free / FLAC / Usar Firehawk52", "OK"),

    # === Telegram Bots ===
    ("DeezerMusicBot", "https://t.me/DeezerMusicBot", "Deezer / SoundCloud / VK / 320kb MP3 / FLAC", "OK"),
    ("BeatSpotBot", "https://t.me/BeatSpotBot", "Spotify / Apple / YouTube / FLAC / 25 diarias", "OK"),

    # === Download Sites (sitios de descarga directa) ===
    ("FLAC Attack", "https://flacattack.net/", "FLAC", "OK"),
    ("Lossless-Music", "https://lossless-music.org/", "FLAC", "OK"),
    ("FlacMusic", "https://www.flacmusic.info/", "FLAC", "OK"),
    ("DiscogC", "https://discogc.com/", "FLAC", "OK"),
    ("LosslessAlbums", "https://losslessalbums.club/", "FLAC", "OK"),
    ("Music and Books", "https://musicandbooks.org/", "MP3 / FLAC", "OK"),
    ("IntMusic", "https://intmusic.net/", "MP3 / FLAC", "OK"),
    ("Gangster", "https://gangster.cc/", "MP3 / FLAC", "OK"),
    ("GetRockMusic", "https://getrockmusic.net/", "MP3 / FLAC", "OK"),
    ("Core Radio", "https://coreradio.ru/", "MP3 / FLAC", "OK"),
    ("AlterPortal", "https://alterportal.com/", "MP3 / FLAC", "OK"),
    ("ShareMania", "https://www.sharemania.us/", "FLAC / MP3 / M4A", "OK"),
    ("Exystence", "https://exystence.net/", "MP3 / FLAC", "OK"),
    ("ThemFire", "https://themfire.net/", "MP3 / FLAC", "OK"),
    ("Canna", "https://canna.to/", "MP3 / FLAC", "OK"),
    ("Music Rider", "https://musicrider.cc/", "MP3 / FLAC", "OK"),

    # === Sitios por genero ===
    ("GetMetal Club", "https://getmetal.club/", "Metal / MP3 / FLAC", "OK"),
    ("Nuclear Holocaust", "https://nuclearholocaust.net/", "Metal / FLAC", "OK"),
    ("We Need Match", "https://weneedmatch.com/", "Metal / FLAC / M4A", "OK"),
    ("Ektoplazm", "https://ektoplazm.com/", "Electronica / MP3 / FLAC", "OK"),
    ("KTI Music", "https://ktimusic.net/", "Electronica / MP3 / FLAC", "OK"),
    ("Bluegrass Archive", "https://bluegrassarchive.com/", "Bluegrass / FLAC", "OK"),
    ("BurningTheGround", "https://burningtheground.com/", "80s / 90s / FLAC", "OK"),
    ("Classical Music Download", "https://classicalmusicdownload.com/", "Clasica / FLAC", "OK"),
    ("FoggyNotion", "https://foggynotion.com/", "Musica clasica / MP3 / FLAC", "OK"),
    ("FlatblackAndClassical", "https://flatblackandclassical.com/", "Musica clasica india / FLAC", "OK"),
    ("GoldHipHop", "https://goldhiphop.com/", "Hip Hop / MP3 / FLAC", "OK"),
    ("MusicRepublic", "https://musicrepublic.net/", "World / MP3 / FLAC", "OK"),
    ("KPopFLAC", "https://www.kpopflac.xyz/", "K-Pop / FLAC", "OK"),
    ("The T-SQUARE Plaza", "https://t-squareplaza.com/", "Jazz Fusion / City Pop / FLAC", "OK"),
]


def ensure_files():
    """
    Crea la carpeta data/ y los archivos por defecto si no existen.
    Se llama al arrancar la aplicacion.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not SITES_FILE.exists():
        write_default_sites()


def write_default_sites():
    """Escribe el archivo download_sites.txt con la lista predefinida."""
    lines = [
        "# ============================================",
        "# Sitios y programas para descargar musica FLAC",
        "# ============================================",
        "# Formato: | NOMBRE | LINK | DESCRIPCION | ESTADO |",
        "# ESTADO puede ser: OK o CAIDO",
        "# Las lineas con # son comentarios",
        "# Edita este archivo libremente para anadir/quitar sitios.",
        "# Extraido de https://fmhy.net/audio",
        "#",
    ]
    lines.append("")
    lines.append("# | NOMBRE | LINK | DESCRIPCION | ESTADO |")
    lines.append("# |--------|------|-------------|--------|")
    for name, link, desc, status in DEFAULT_SITES:
        lines.append(f"| {name} | {link} | {desc} | {status} |")

    with open(SITES_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def load_sites():
    """
    Lee el archivo download_sites.txt y devuelve una lista de sitios.

    Returns:
        list[dict]: cada elemento tiene:
            {name, link, description, status}
    """
    if not SITES_FILE.exists():
        ensure_files()

    sites = []
    with open(SITES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Parsear linea: | NOMBRE | LINK | DESCRIPCION | ESTADO |
            if line.startswith('|'):
                parts = [p.strip() for p in line.split('|')]
                # parts[0] es vacio (antes del primer |), parts[-1] es vacio
                if len(parts) >= 5:
                    sites.append({
                        'name': parts[1],
                        'link': parts[2],
                        'description': parts[3],
                        'status': parts[4],
                    })
    return sites


def save_sites(sites):
    """
    Guarda la lista de sitios en el archivo.

    Args:
        sites (list[dict]): lista de sitios con {name, link, description, status}
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ============================================",
        "# Sitios y programas para descargar musica FLAC",
        "# ============================================",
        "# Formato: | NOMBRE | LINK | DESCRIPCION | ESTADO |",
        "# ESTADO puede ser: OK o CAIDO",
        "# Las lineas con # son comentarios",
        "# Edita este archivo libremente para anadir/quitar sitios.",
        "# Extraido de https://fmhy.net/audio",
        "#",
        "",
        "| NOMBRE | LINK | DESCRIPCION | ESTADO |",
        "|--------|------|-------------|--------|",
    ]
    for s in sites:
        lines.append(f"| {s['name']} | {s['link']} | {s['description']} | {s['status']} |")

    with open(SITES_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
