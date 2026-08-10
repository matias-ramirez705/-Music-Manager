"""
app/spotify_official.py
=======================
Lee playlists PUBLICAS de Spotify usando la API oficial a traves
de la libreria `spotipy`.

Tres modos de autenticacion (en orden de preferencia):

1. **User login (OAuth Authorization Code)**:
   Si el usuario configuro sus credenciales Y autorizo la app via
   navegador, spotipy guarda un cache de token en `data/.spotify_cache`.
   Esto permite leer TODAS las canciones de cualquier playlist
   publica (sin limites practicos para uso personal).
   Se configura con `setup_spotify_login.bat`.

2. **Client Credentials**:
   Si solo hay Client ID + Client Secret en .env (sin login de
   usuario), se usa este flujo. Lee TODAS las canciones de playlists
   publicas, pero con rate limits ligeramente mayores.

3. **Sin credenciales**:
   Devuelve None y el llamador cae al fallback del embed (100 canciones).

Archivo de configuracion:
    <proyecto>/.env
  con:
    SPOTIPY_CLIENT_ID=tu_client_id
    SPOTIPY_CLIENT_SECRET=tu_client_secret
    SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
"""

import os
import json
from pathlib import Path

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


# Cache del cliente spotipy
_sp_client = None
_sp_mode = None  # 'user' | 'client' | None


def is_configured():
    """Verifica si hay Client ID + Client Secret configurados."""
    cid = os.environ.get('SPOTIPY_CLIENT_ID', '').strip()
    csec = os.environ.get('SPOTIPY_CLIENT_SECRET', '').strip()
    return bool(cid) and bool(csec)


def has_user_login():
    """Verifica si hay un cache de token de usuario (login via navegador)."""
    cache_path = Path(__file__).parent.parent / 'data' / '.spotify_cache'
    if not cache_path.exists():
        return False
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Token de usuario tiene 'access_token' y 'refresh_token'
        return bool(data.get('access_token')) and bool(data.get('refresh_token'))
    except (json.JSONDecodeError, OSError):
        return False


def get_auth_mode():
    """Devuelve el modo de autenticacion actual: 'user', 'client' o None."""
    global _sp_mode
    if _sp_mode is not None:
        return _sp_mode
    if has_user_login():
        _sp_mode = 'user'
        return _sp_mode
    if is_configured():
        _sp_mode = 'client'
        return _sp_mode
    return None


def get_client():
    """
    Crea (o devuelve cacheado) un cliente spotipy autenticado.

    Modo preferido: user login (OAuth Authorization Code) si hay cache.
    Fallback: Client Credentials si solo hay Client ID/Secret.
    """
    global _sp_client, _sp_mode

    if _sp_client is not None:
        return _sp_client

    if not is_configured():
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

        # 1. Intentar OAuth con cache de usuario
        if has_user_login():
            try:
                cache_path = str(Path(__file__).parent.parent / 'data' / '.spotify_cache')
                redirect_uri = os.environ.get(
                    'SPOTIPY_REDIRECT_URI',
                    'http://127.0.0.1:8888/callback'
                )
                auth_manager = SpotifyOAuth(
                    client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
                    client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
                    redirect_uri=redirect_uri,
                    scope='playlist-read-private playlist-read-collaborative user-library-read',
                    cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path=cache_path),
                )
                _sp_client = spotipy.Spotify(auth_manager=auth_manager)
                # Verificar que el token es valido
                _sp_client.current_user()
                _sp_mode = 'user'
                return _sp_client
            except Exception as e:
                print(f"Login de usuario invalido, cayendo a client credentials: {e}")
                _sp_mode = None  # reset para intentar client credentials

        # 2. Client Credentials Flow
        auth_manager = SpotifyClientCredentials(
            client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
            client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
        )
        _sp_client = spotipy.Spotify(auth_manager=auth_manager)
        _sp_mode = 'client'
        return _sp_client

    except ImportError:
        return None
    except Exception as e:
        print(f"Error inicializando spotipy: {e}")
        return None


def start_user_login():
    """
    Inicia el flujo de OAuth Authorization Code.
    Devuelve la URL de autorizacion a la que el usuario debe ir
    en su navegador.

    Returns:
        dict: {'url': 'https://...', 'success': True} o {'error': '...'}
    """
    if not is_configured():
        return {'error': 'Faltan SPOTIPY_CLIENT_ID o SPOTIPY_CLIENT_SECRET en .env'}

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        cache_path = Path(__file__).parent.parent / 'data'
        cache_path.mkdir(parents=True, exist_ok=True)
        cache_file = str(cache_path / '.spotify_cache')

        # El redirect URI DEBE coincidir exactamente con el configurado en
        # Spotify Developer Dashboard. Por defecto usamos http://127.0.0.1:8888
        # (sin /callback) porque es lo que pide el setup_spotify.bat.
        redirect_uri = os.environ.get(
            'SPOTIPY_REDIRECT_URI',
            'http://127.0.0.1:8888'
        )

        auth_manager = SpotifyOAuth(
            client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
            client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
            redirect_uri=redirect_uri,
            scope='playlist-read-private playlist-read-collaborative user-library-read',
            cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path=cache_file),
            open_browser=False,
        )
        url = auth_manager.get_authorize_url()
        return {'url': url, 'success': True, 'redirect_uri': redirect_uri}

    except ImportError:
        return {'error': 'spotipy no esta instalado'}
    except Exception as e:
        return {'error': str(e)}


def finish_user_login(callback_url):
    """
    Completa el flujo OAuth despues de que el usuario autorizo la app.

    IMPORTANTE: Spotify redirige a la URL configurada como Redirect URI
    en el Dashboard. Si configuro http://127.0.0.1:8888, Spotify
    redirige a http://127.0.0.1:8888/?code=XXX (sin /callback).
    Si configuro http://127.0.0.1:8888/callback, redirige a
    http://127.0.0.1:8888/callback?code=XXX.

    El codigo spotipy extrae el parametro 'code' de la URL completa,
    sin importar el path. Por eso solo necesitamos pasar la URL tal
    cual la devuelve el navegador.

    Args:
        callback_url: URL completa de redireccion (con ?code=...).

    Returns:
        dict: {'success': True, 'username': '...'} o {'error': '...'}
    """
    if not is_configured():
        return {'error': 'Faltan credenciales en .env'}

    # Validar que la URL tenga el parametro code
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)
    if 'code' not in params:
        return {'error': f'La URL no contiene el parametro "code". URL recibida: {callback_url[:100]}'}

    code = params['code'][0]

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        cache_path = Path(__file__).parent.parent / 'data'
        cache_file = str(cache_path / '.spotify_cache')

        redirect_uri = os.environ.get(
            'SPOTIPY_REDIRECT_URI',
            'http://127.0.0.1:8888'
        )

        auth_manager = SpotifyOAuth(
            client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
            client_secret=os.environ.get('SPOTIPY_CLIENT_SECRET'),
            redirect_uri=redirect_uri,
            scope='playlist-read-private playlist-read-collaborative user-library-read',
            cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path=cache_file),
        )

        # Usar get_access_token con el code extraido
        token = auth_manager.get_access_token(code)
        if not token:
            return {'error': 'No se pudo obtener el token. Verifica que el Redirect URI en .env coincida exactamente con el configurado en Spotify Developer Dashboard.'}

        # Resetear el cliente para que se re cree con el nuevo token
        global _sp_client, _sp_mode
        _sp_client = None
        _sp_mode = 'user'

        # Verificar identidad del usuario
        sp = get_client()
        if sp:
            try:
                user_info = sp.current_user()
                return {'success': True, 'username': user_info.get('display_name', 'desconocido')}
            except Exception as e:
                return {'success': True, 'username': 'desconocido', 'warning': str(e)}
        return {'success': True, 'username': 'desconocido'}

    except Exception as e:
        return {'error': str(e)}


def logout_user():
    """Elimina el cache de token de usuario (vuelve a client credentials)."""
    global _sp_client, _sp_mode
    cache_path = Path(__file__).parent.parent / 'data' / '.spotify_cache'
    if cache_path.exists():
        try:
            cache_path.unlink()
        except OSError:
            pass
    _sp_client = None
    _sp_mode = None
    return True


def fetch_playlist_official(playlist_id):
    """
    Lee TODAS las canciones de una playlist usando la API oficial
    de Spotify con paginacion automatica via sp.next().

    Funciona con cualquier playlist publica. Si el usuario hizo
    login, tambien funciona con playlists privadas a las que tenga
    acceso.

    Returns:
        dict | None: playlist completa o None si fallo.
    """
    sp = get_client()
    if sp is None:
        return None

    try:
        # 1. Metadata de la playlist
        meta = sp.playlist(playlist_id, market='from_token')
        title = meta.get('name', 'Playlist sin titulo')
        owner = (meta.get('owner', {}) or {}).get('display_name', '') \
                or (meta.get('owner', {}) or {}).get('id', '')
        total = (meta.get('tracks', {}) or {}).get('total', 0)

        # 2. Paginar todas las canciones (100 por pagina)
        results = sp.playlist_items(
            playlist_id,
            limit=100,
            offset=0,
            market='from_token',
            additional_types=('track',),
        )

        tracks = []
        while results:
            for item in results.get('items', []):
                if not item:
                    continue
                track = item.get('track')
                if not track or not isinstance(track, dict):
                    continue

                t_title = track.get('name', 'Desconocido')
                artists_list = track.get('artists', []) or []
                t_artist = ', '.join(
                    a.get('name', '') for a in artists_list if a
                ) or 'Desconocido'

                album = track.get('album', {}) or {}
                t_album = album.get('name', '') if isinstance(album, dict) else ''

                duration_ms = track.get('duration_ms', 0) or 0
                t_duration = duration_ms / 1000.0

                t_url = ''
                ext_url = track.get('external_urls', {}) or {}
                if ext_url and 'spotify' in ext_url:
                    t_url = ext_url['spotify']
                elif track.get('uri'):
                    # Convertir 'spotify:track:ID' a 'https://open.spotify.com/track/ID'
                    uri = track['uri']
                    if uri.startswith('spotify:'):
                        parts = uri.split(':')
                        if len(parts) >= 3:
                            t_url = f"https://open.spotify.com/{parts[1]}/{parts[2]}"
                        else:
                            t_url = uri
                    else:
                        t_url = uri

                tracks.append({
                    'title': t_title,
                    'artist': t_artist,
                    'album': t_album,
                    'duration': t_duration,
                    'url': t_url,
                })

            if results.get('next'):
                results = sp.next(results)
            else:
                break

        if not tracks:
            return {
                'title': title,
                'uploader': owner,
                'count': 0,
                'tracks': [],
                'error': 'La playlist no tiene canciones visibles.',
            }

        return {
            'title': title,
            'uploader': owner,
            'count': len(tracks),
            'tracks': tracks,
            'error': None,
            'warning': None,
            'total_expected': total,
        }

    except Exception as e:
        print(f"Error en fetch_playlist_official: {e}")
        return None
