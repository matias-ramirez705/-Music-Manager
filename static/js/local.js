/* ============================================
   local.js - Pestana "Mi Musica" (v1.4)
   ============================================
   Maneja:
     - Seleccion de carpeta (input + dialogo nativo)
     - Escaneo via /api/scan
     - Renderizado de la tabla con todos los archivos
     - Columna "Playlists" (puntos de color)
     - Columna "Reproducir" (boton play)
     - Badge "DUP" si la cancion esta repetida (link a pestana Duplicados)
     - Busqueda, filtros (formato, playlist, dup) y orden
*/

// Estado local
let allFiles = [];
let filteredFiles = [];
let showQuality = false;
let duplicatePaths = new Set();  // paths que aparecen en grupos duplicados

// DOM
const folderInput   = document.getElementById('folder-input');
const btnBrowse     = document.getElementById('btn-browse');
const btnScan       = document.getElementById('btn-scan');
const btnRefresh    = document.getElementById('btn-refresh');
const statsBar      = document.getElementById('stats-bar');
const filterBar     = document.getElementById('filter-bar');
const searchInput   = document.getElementById('search-input');
const filterFormat  = document.getElementById('filter-format');
const filterPlaylist = document.getElementById('filter-playlist');
const filterDup     = document.getElementById('filter-dup');
const filterMeta    = document.getElementById('filter-meta');
const sortBy        = document.getElementById('sort-by');
const btnToggleQ    = document.getElementById('btn-toggle-quality');
const musicTable    = document.getElementById('music-table');
const musicTbody    = document.getElementById('music-tbody');
const emptyState    = document.getElementById('empty-state');
const loadingState  = document.getElementById('loading-state');

// ------------------------------------------------------------------
// AL CARGAR
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();

    // Verificar si se cargaron/eliminaron playlists en otra pestana
    // Si es asi, re-escanear automaticamente para actualizar las columnas
    const playlistsChanged = sessionStorage.getItem('playlists_changed') === '1';
    if (playlistsChanged) {
        sessionStorage.removeItem('playlists_changed');
    }
    // Verificar si se cambio metadata en el editor
    const metadataChanged = sessionStorage.getItem('metadata_changed') === '1';
    if (metadataChanged) {
        sessionStorage.removeItem('metadata_changed');
    }

    // Cargar playlists guardadas para llenar el filtro de playlist
    try {
        const data = await getJSON('/api/saved-playlists');
        // Limpiar opciones existentes (excepto la primera)
        while (filterPlaylist.options.length > 1) {
            filterPlaylist.remove(1);
        }
        data.playlists.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.name} (${p.platform === 'youtube' ? 'YouTube Music' : 'Spotify'})`;
            filterPlaylist.appendChild(opt);
        });
    } catch (e) {}

    // Cargar ultimo escaneo si existe
    try {
        const data = await getJSON('/api/last-scan');
        // Restaurar carpeta del localStorage o del servidor
        const savedFolder = localStorage.getItem('last_scan_folder');
        if (savedFolder) {
            folderInput.value = savedFolder;
        } else if (data.folder) {
            folderInput.value = data.folder;
        }
        if (data.count > 0) {
            // Si cambiaron las playlists o la metadata, re-escanear automaticamente
            if ((playlistsChanged || metadataChanged) && (savedFolder || data.folder)) {
                folderInput.value = savedFolder || data.folder;
                await scanFolder();
            } else {
                allFiles = data.files;
                await loadDuplicatePaths();
                renderTable();
                renderStats(data);
                showTable();
            }
        }
    } catch (e) {}
});

function bindEvents() {
    btnBrowse.addEventListener('click', browseFolder);
    btnScan.addEventListener('click', scanFolder);
    if (btnRefresh) btnRefresh.addEventListener('click', refreshScan);
    searchInput.addEventListener('input', applyFilters);
    filterFormat.addEventListener('change', applyFilters);
    filterPlaylist.addEventListener('change', applyFilters);
    filterDup.addEventListener('change', applyFilters);
    if (filterMeta) filterMeta.addEventListener('change', applyFilters);
    sortBy.addEventListener('change', applyFilters);
    btnToggleQ.addEventListener('click', toggleQuality);
    folderInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') scanFolder();
    });
}

// ------------------------------------------------------------------
// Dialogo nativo
// ------------------------------------------------------------------
async function browseFolder() {
    btnBrowse.disabled = true;
    try {
        const data = await getJSON('/api/browse');
        if (data.folder) folderInput.value = data.folder;
    } catch (e) {
        showToast('No se pudo abrir el dialogo: ' + e.message, 'error');
    } finally {
        btnBrowse.disabled = false;
    }
}

// ------------------------------------------------------------------
// Re-escanear (usar la ultima carpeta)
// ------------------------------------------------------------------
async function refreshScan() {
    // Prioridad: input actual > localStorage > ultimo escaneo del servidor
    let folder = folderInput.value.trim();
    if (!folder) {
        folder = localStorage.getItem('last_scan_folder') || '';
    }
    if (!folder) {
        // Intentar obtener del servidor
        try {
            const data = await getJSON('/api/last-scan');
            if (data.folder) folder = data.folder;
        } catch (e) {}
    }
    if (!folder) {
        showToast('No hay carpeta para actualizar. Escanea una primero.', 'error');
        return;
    }
    folderInput.value = folder;
    await scanFolder();
}

// ------------------------------------------------------------------
// Escanear carpeta
// ------------------------------------------------------------------
async function scanFolder() {
    const folder = folderInput.value.trim();
    if (!folder) {
        showToast('Selecciona o escribe una carpeta primero.', 'error');
        return;
    }
    emptyState.classList.add('hidden');
    musicTable.classList.add('hidden');
    loadingState.classList.remove('hidden');

    try {
        const data = await postJSON('/api/scan', { folder });
        allFiles = data.files;
        // Guardar carpeta en localStorage para mantenerla entre pestanas
        localStorage.setItem('last_scan_folder', folder);
        await loadDuplicatePaths();
        renderTable();
        renderStats(data);
        showTable();
        showToast(`Se encontraron ${data.count} archivos.`, 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
        loadingState.classList.add('hidden');
        emptyState.classList.remove('hidden');
    }
}

// ------------------------------------------------------------------
// Cargar rutas duplicadas (para marcar en la tabla)
// ------------------------------------------------------------------
async function loadDuplicatePaths() {
    duplicatePaths.clear();
    try {
        const data = await postJSON('/api/duplicates', { match_by: 'title_artist' });
        data.groups.forEach(g => {
            g.files.forEach(f => duplicatePaths.add(f.path));
        });
    } catch (e) {
        // Si falla, no es critico
    }
}

// ------------------------------------------------------------------
// Estadisticas
// ------------------------------------------------------------------
function renderStats(data) {
    document.getElementById('stat-folder').textContent = data.folder;
    document.getElementById('stat-count').textContent = data.count;
    document.getElementById('stat-size').textContent = data.total_size_str || '—';

    const formats = Object.entries(data.stats || {})
        .map(([ext, count]) => `${ext.replace('.', '').toUpperCase()}: ${count}`)
        .join(', ');
    document.getElementById('stat-formats').textContent = formats || '—';

    const currentFilter = filterFormat.value;
    filterFormat.innerHTML = '<option value="">Todos los formatos</option>';
    Object.keys(data.stats || {}).forEach(ext => {
        const opt = document.createElement('option');
        opt.value = ext.replace('.', '');
        opt.textContent = `${ext.replace('.', '').toUpperCase()} (${data.stats[ext]})`;
        filterFormat.appendChild(opt);
    });
    filterFormat.value = currentFilter;
}

function showTable() {
    loadingState.classList.add('hidden');
    emptyState.classList.add('hidden');
    statsBar.classList.remove('hidden');
    filterBar.classList.remove('hidden');
    musicTable.classList.remove('hidden');
}

// ------------------------------------------------------------------
// Filtros + orden
// ------------------------------------------------------------------
function applyFilters() {
    const query = searchInput.value.toLowerCase().trim();
    const format = filterFormat.value;
    const playlistId = filterPlaylist.value;
    const dupFilter = filterDup.value;
    const metaFilter = filterMeta ? filterMeta.value : '';

    filteredFiles = allFiles.filter(f => {
        if (format && f.ext !== format) return false;
        if (playlistId && !(f.playlists || []).some(p => p.id === playlistId)) return false;
        if (dupFilter === 'duplicates' && !duplicatePaths.has(f.path)) return false;
        if (dupFilter === 'unique' && duplicatePaths.has(f.path)) return false;
        if (metaFilter === 'error' && !f.has_error) return false;
        if (metaFilter === 'ok' && f.has_error) return false;
        if (query) {
            const haystack = `${f.name} ${f.artist} ${f.album}`.toLowerCase();
            if (!haystack.includes(query)) return false;
        }
        return true;
    });

    filteredFiles.sort((a, b) => {
        let va = a[sortBy.value], vb = b[sortBy.value];
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return -1;
        if (va > vb) return 1;
        return 0;
    });

    renderRows();
}

function renderTable() {
    applyFilters();
}

// ------------------------------------------------------------------
// Render de filas
// ------------------------------------------------------------------
function renderRows() {
    musicTbody.innerHTML = '';

    if (filteredFiles.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="12" style="text-align:center; padding:32px; color:var(--text-muted);">
            No se encontraron archivos con esos filtros.
        </td>`;
        musicTbody.appendChild(tr);
        return;
    }

    filteredFiles.forEach((file, index) => {
        const tr = document.createElement('tr');

        const q = file.quality;
        const qualityHtml = q
            ? `<span class="quality-badge quality-${q.category}" title="${escapeHtml(q.description)}">${escapeHtml(q.label)}</span>`
            : '';

        // Playlists: construir con DOM API para hacer dots clicables
        const playlistsCell = document.createElement('div');
        playlistsCell.className = 'playlist-badges';
        if (file.playlists && file.playlists.length > 0) {
            file.playlists.forEach(p => {
                const dot = document.createElement('span');
                dot.className = 'playlist-dot ' + p.platform;
                dot.title = p.name + ' — clic para abrir';
                dot.dataset.name = p.name;
                dot.style.cursor = 'pointer';
                dot.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openPlaylistById(p.id);
                });
                playlistsCell.appendChild(dot);
            });
        } else {
            playlistsCell.innerHTML = '<span style="color:var(--text-muted)">—</span>';
        }

        const isDup = duplicatePaths.has(file.path);
        const dupHtml = isDup
            ? ` <a href="/duplicates" class="dup-badge" title="Ver en Duplicados">DUP</a>`
            : '';

        // Boton play: usamos data-* attributes y event listener (no onclick inline)
        // para evitar problemas con apóstrofos y comillas en nombres
        const playBtn = document.createElement('button');
        playBtn.className = 'play-btn';
        playBtn.title = 'Reproducir';
        playBtn.textContent = '▶';
        playBtn.dataset.path = file.path;
        playBtn.dataset.name = file.name || '';
        playBtn.dataset.artist = file.artist || '';
        playBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            playFile(file.path, file.name || '', file.artist || '');
        });

        // Celda de ruta: ya se incluye en el innerHTML, solo necesitamos el event listener

        tr.innerHTML = `
            <td>${index + 1}</td>
            <td></td>
            <td><strong>${escapeHtml(file.name)}</strong>${file.has_error ? ' <span style="color:var(--warning); cursor:help;" title="' + escapeHtml(file.error_msg || 'Error desconocido') + '">⚠</span>' : ''}</td>
            <td>${escapeHtml(file.artist || '—')}</td>
            <td>${escapeHtml(file.album || '—')}</td>
            <td style="text-align:center;">${escapeHtml(file.duration_str)}</td>
            <td style="text-align:center;"><span class="format-badge ${escapeHtml(file.ext)}">${escapeHtml(file.ext.toUpperCase())}</span></td>
            <td class="quality-col ${showQuality ? '' : 'hidden'}">${qualityHtml}</td>
            <td></td>
            <td class="size-cell">${escapeHtml(file.size_str)}${dupHtml}</td>
            <td style="text-align:center;"></td>
            <td class="path-cell" title="${escapeHtml(file.path)} — clic para abrir en explorador">${escapeHtml(file.path)}</td>
        `;
        // Insertar el boton play en la segunda celda (td vacio)
        tr.children[1].appendChild(playBtn);
        // Insertar los dots de playlist en la celda 8
        tr.children[8].appendChild(playlistsCell);
        // Insertar boton copiar en la penultima celda (indice 10)
        const copyCell = tr.children[10];
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn btn-ghost btn-sm';
        copyBtn.title = 'Copiar "' + (file.artist ? file.name + ' - ' + file.artist : file.name) + '"';
        copyBtn.textContent = '📋';
        copyBtn.style.padding = '2px 4px';
        copyBtn.style.fontSize = '11px';
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            copySongInfo(file.name, file.artist || '');
        });
        copyCell.appendChild(copyBtn);
        // Hacer la celda de ruta clickeable (ya esta en el innerHTML, indice 11)
        const pathCellFinal = tr.children[11];
        if (pathCellFinal) {
            pathCellFinal.style.cursor = 'pointer';
            pathCellFinal.addEventListener('click', (e) => {
                e.stopPropagation();
                revealInExplorer(encodeURIComponent(file.path));
            });
        }

        tr.style.cursor = 'pointer';
        tr.addEventListener('click', () => {
            window.location.href = `/editor?path=${encodeURIComponent(file.path)}`;
        });

        musicTbody.appendChild(tr);
    });

    document.querySelectorAll('.quality-col').forEach(col => {
        col.classList.toggle('hidden', !showQuality);
    });
}

// ------------------------------------------------------------------
// Toggle calidad
// ------------------------------------------------------------------
function toggleQuality() {
    showQuality = !showQuality;
    btnToggleQ.textContent = showQuality ? 'Ocultar calidad' : 'Mostrar calidad';
    renderRows();
}

// ------------------------------------------------------------------
// Abrir playlist desde dot de color en Mi Musica
// ------------------------------------------------------------------
async function openPlaylistById(playlistId) {
    try {
        const p = await getJSON('/api/saved-playlist/' + playlistId);
        showPlaylistDetailModal(p);
    } catch (e) {
        showToast('Error al abrir playlist: ' + e.message, 'error');
    }
}

function showPlaylistDetailModal(p) {
    const modalId = 'playlist-detail-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const platformLabel = p.platform === 'youtube' ? 'YouTube Music' : 'Spotify';
    const platformIcon = p.platform === 'youtube' ? '▶' : '♫';

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h2>${escapeHtml(p.name)}</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body" style="display:flex; flex-direction:column; max-height:calc(100vh - 200px);">
                <p style="color:var(--text-secondary); margin-bottom:12px; flex-shrink:0;">
                    ${escapeHtml(p.uploader || '')} • ${p.track_count} canciones • ${platformLabel}
                    ${p.url && !p.url.startsWith('csv://') ? `• <a href="${escapeHtml(p.url)}" target="_blank" style="color:var(--accent);">Abrir original ↗</a>` : ''}
                </p>
                <div class="filter-bar" style="margin-bottom:8px; flex-shrink:0;">
                    <input type="text" id="pl-detail-search" class="search-input"
                        placeholder="Buscar cancion en esta playlist...">
                </div>
                <div class="table-container" style="max-height:none; flex:1; overflow:auto;">
                    <table class="music-table">
                        <thead><tr>
                            <th style="width:4%; text-align:center;">#</th>
                            <th style="width:45%; text-align:left;">Titulo</th>
                            <th style="width:12%; text-align:left;">Artista</th>
                            <th style="width:20%; text-align:center;">Album</th>
                            <th style="width:8%; text-align:center;">Duracion</th>
                            <th style="width:4%; text-align:center;">Ir</th>
                        </tr></thead>
                        <tbody id="pl-detail-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());

    // Guardar tracks para el filtro
    window._playlistDetailTracks = p.tracks || [];
    renderPlaylistDetailRows(p.tracks || []);

    // Buscador
    document.getElementById('pl-detail-search').addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        const filtered = (window._playlistDetailTracks || []).filter(t =>
            (t.title + ' ' + t.artist + ' ' + (t.album || '')).toLowerCase().includes(q)
        );
        renderPlaylistDetailRows(filtered);
    });
}

function renderPlaylistDetailRows(tracks) {
    const tbody = document.getElementById('pl-detail-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (tracks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:16px;color:var(--text-muted);">Sin resultados.</td></tr>';
        return;
    }

    const platformLabel = 'Ir ↗';

    tracks.forEach((t, i) => {
        const tr = document.createElement('tr');
        const link = t.url
            ? `<a href="${escapeHtml(t.url)}" target="_blank" rel="noopener" title="Abrir" style="color:var(--accent); text-decoration:none;">${platformLabel}</a>`
            : '—';

        tr.innerHTML = `
            <td>${i + 1}</td>
            <td style="text-align:left;"><strong>${escapeHtml(t.title)}</strong></td>
            <td>${escapeHtml(t.artist)}</td>
            <td style="text-align:center;">${escapeHtml(t.album || '—')}</td>
            <td style="text-align:center;">${formatDuration(t.duration)}</td>
            <td style="text-align:center;">${link}</td>
        `;
        tbody.appendChild(tr);
    });
}

function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
}
