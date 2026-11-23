"""
app/tabs_config.py
==================
Registro central de pestañas y sub-pestañas de Music Manager.

=========================================================================
CÓMO FUNCIONA
=========================================================================
Toda la navegación visible del topbar se define AQUÍ, en una sola lista
ordenada. web_app.py registra las rutas automáticamente a partir de esto,
y base.html arma el menú leyendo esta misma estructura.

- Agregar una pestaña nueva = 1 entrada en este archivo + 1 template.
- Cambiar nombre, icono u orden = 1 edición aquí (sin tocar nada más).
- Ocultar temporalmente = 'visible: False'.
- Reagrupar sub-pestañas bajo otro grupo = mover la entrada.

El .py de la app (web_app.py) y el HTML (base.html) NO saben nada del
orden ni de los grupos: solo recorren esta lista. Eso desacopla la
lógica de rutas de la presentación del menú.

=========================================================================
ESTRUCTURA DE CADA ENTRADA
=========================================================================
Tab(
    id           = 'local'              # id interno (active_tab, logica JS)
    label        = 'Mi Música'         # texto visible
    icon         = '♪'                 # icono unicode (puede ser emoji)
    url          = '/'                 # ruta Flask
    template     = 'index.html'        # plantilla a renderizar
    group        = None                 # None = pestaña directa del topbar
                                        # str = grupo desplegable donde vive
    visible      = True                # False la oculta del menú pero la
                                        # ruta sigue existiendo (útil en beta)
    sub_tabs     = None                # lista de subpestañas (para Metadatos,
                                        # o para grupos con subpestañas internas)
                                        # Si se setea, el grupo se dibuja con
                                        # subpestañas internas como pestaña
                                        # principal + subpestañas debajo.
                                        # Si group != None y sub_tabs == None,
                                        # el item vive dentro del dropdown del
                                        # grupo pero no tiene subpestañas propias.
)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SubTab:
    """Sub-pestaña interna de una pestaña principal (ej: Metadatos → Editar)."""
    id: str            # id interno (ej: 'edit')
    label: str         # texto visible (ej: 'Editar Metadata')
    icon: str = ''     # icono unicode/emoji opcional
    # Parámetro de URL para seleccionar la subpestaña (ej: ?sub=edit).
    # Por defecto '?sub=<id>'. Si la subpestaña tiene su propia URL
    # (ej: '/saved'), no se usa sub_param.
    sub_param: str = 'sub'


@dataclass(frozen=True)
class Tab:
    """Pestaña del topbar (puede ser directa o parte de un grupo)."""
    id: str
    label: str
    icon: str
    url: str
    template: str
    group: Optional[str] = None        # None = pestaña directa en el topbar
    visible: bool = True
    sub_tabs: Optional[List[SubTab]] = None
    # Parámetro que activa la subpestaña activa al renderizar:
    # 'sub' para /editor?sub=edit; '' si no aplica
    sub_param: str = ''


# =============================================================================
# REGISTRO DE PESTAÑAS (orden = orden visible en el topbar)
# =============================================================================
# Para reagrupar, mover orden o cambiar nombre: editar SOLO esta lista.
#
# Grupo = nombre que aparece como botón desplegable en el topbar.
# Todos los Tab con el mismo group se agrupan bajo ese botón.
# =============================================================================

TABS: List[Tab] = [

    # --------------------------------------------------------------------------
    # PESTAÑA DIRECTA: Mi Música (la más usada, sale primera y sin grupo)
    # --------------------------------------------------------------------------
    Tab(
        id='local',
        label='Mi Música',
        icon='♪',
        url='/',
        template='index.html',
        group=None,
    ),

    # --------------------------------------------------------------------------
    # GRUPO: Biblioteca (gestión de la colección local)
    # --------------------------------------------------------------------------
    Tab(
        id='duplicates',
        label='Duplicados',
        icon='⧉',
        url='/duplicates',
        template='duplicates.html',
        group='Biblioteca',
    ),
    Tab(
        id='deleted',
        label='Eliminados',
        icon='🗑',
        url='/deleted',
        template='deleted.html',
        group='Biblioteca',
    ),
    Tab(
        id='organize',
        label='Organizar',
        icon='📁',
        url='/organize',
        template='organize.html',
        group='Biblioteca',
    ),
    Tab(
        id='folder-compare',
        label='Comparar Carpetas',
        icon='⇄',
        url='/folder-compare',
        template='folder_compare.html',
        group='Biblioteca',
    ),
    # v3.7-sync: nueva subpestaña de sincronización A → B
    Tab(
        id='sync-folders',
        label='Sincronizar Carpetas',
        icon='🔄',
        url='/sync-folders',
        template='sync_folders.html',
        group='Biblioteca',
    ),

    # --------------------------------------------------------------------------
    # GRUPO: Playlists (gestión de listas externas y M3U)
    # --------------------------------------------------------------------------
    Tab(
        id='saved',
        label='Playlists Guardadas',
        icon='★',
        url='/saved',
        template='saved_playlists.html',
        group='Playlists',
    ),
    Tab(
        id='compare',
        label='Comparar Playlist',
        icon='⇄',
        url='/compare',
        template='compare.html',
        group='Playlists',
    ),
    Tab(
        id='m3u-hiby',
        label='M3U Hiby',
        icon='🎵',
        url='/m3u-hiby',
        template='m3u_hiby.html',
        group='Playlists',
    ),

    # --------------------------------------------------------------------------
    # GRUPO: Metadatos (pestaña con subpestañas internas)
    # --------------------------------------------------------------------------
    # Esta pestaña sí usa subpestañas internas: una sola ruta (/editor)
    # renderiza metadata_master.html con el parámetro ?sub=<id>.
    Tab(
        id='editor',
        label='Metadatos',
        icon='✎',
        url='/editor',
        template='metadata_master.html',
        group='Metadatos',
        sub_param='sub',
        sub_tabs=[
            SubTab(id='edit',    label='Editar Metadata', icon='✎'),
            SubTab(id='artwork', label='Carátulas',       icon='🖼'),
            SubTab(id='lyrics',  label='Letras',          icon='📝'),
            SubTab(id='rename',  label='Renombrar',       icon='🔤'),
        ],
    ),

    # --------------------------------------------------------------------------
    # GRUPO: Herramientas (utilidades varias)
    # --------------------------------------------------------------------------
    Tab(
        id='spotiflac',
        label='Spotiflac Dummies',
        icon='📦',
        url='/spotiflac',
        template='spotiflac.html',
        group='Herramientas',
    ),
    Tab(
        id='downloads',
        label='Descargas FLAC',
        icon='⬇',
        url='/downloads',
        template='downloads.html',
        group='Herramientas',
    ),
]


# =============================================================================
# UTILIDADES (consumidas por web_app.py y base.html)
# =============================================================================

def get_visible_tabs() -> List[Tab]:
    """Lista de pestañas visibles (filtra visible=False)."""
    return [t for t in TABS if t.visible]


def get_tab_by_id(tab_id: str) -> Optional[Tab]:
    """Busca una pestaña por su id. Devuelve None si no existe."""
    for t in TABS:
        if t.id == tab_id:
            return t
    return None


def get_group_names() -> List[str]:
    """Lista ordenada y sin duplicados de nombres de grupo en el orden
    en que aparecen por primera vez en TABS. Las pestañas directas
    (group=None) NO aparecen aquí (van al principio del topbar)."""
    seen = set()
    ordered = []
    for t in TABS:
        if t.group and t.group not in seen:
            seen.add(t.group)
            ordered.append(t.group)
    return ordered


def get_tabs_by_group(group_name: str) -> List[Tab]:
    """Pestañas visibles de un grupo, en el orden declarado."""
    return [t for t in TABS if t.group == group_name and t.visible]


def get_direct_tabs() -> List[Tab]:
    """Pestañas visibles sin grupo (van directas en el topbar)."""
    return [t for t in TABS if t.group is None and t.visible]


def get_route_map() -> dict:
    """Devuelve {url: (tab_id, template, sub_param_default)}.
    Usado por web_app.py para registrar las rutas automáticamente."""
    out = {}
    for t in TABS:
        out[t.url] = {
            'tab_id': t.id,
            'template': t.template,
            'sub_param': t.sub_param,
            'default_sub': t.sub_tabs[0].id if t.sub_tabs else None,
        }
    return out
