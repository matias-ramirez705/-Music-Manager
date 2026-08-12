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
const statsBar      = document.getElementById('stats-bar');
const filterBar     = document.getElementById('filter-bar');
const searchInput   = document.getElementById('search-input');
const filterFormat  = document.getElementById('filter-format');
const filterPlaylist = document.getElementById('filter-playlist');
const filterDup     = document.getElementById('filter-dup');
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
        if (data.count > 0) {
            // Si cambiaron las playlists, re-escanear automaticamente
            if (playlistsChanged && data.folder) {
                folderInput.value = data.folder;
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
    searchInput.addEventListener('input', applyFilters);
    filterFormat.addEventListener('change', applyFilters);
    filterPlaylist.addEventListener('change', applyFilters);
    filterDup.addEventListener('change', applyFilters);
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

    filteredFiles = allFiles.filter(f => {
        if (format && f.ext !== format) return false;
        if (playlistId && !(f.playlists || []).some(p => p.id === playlistId)) return false;
        if (dupFilter === 'duplicates' && !duplicatePaths.has(f.path)) return false;
        if (dupFilter === 'unique' && duplicatePaths.has(f.path)) return false;
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
        tr.innerHTML = `<td colspan="11" style="text-align:center; padding:32px; color:var(--text-muted);">
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

        const playlistsHtml = (file.playlists && file.playlists.length > 0)
            ? `<div class="playlist-badges">${file.playlists.map(p =>
                `<span class="playlist-dot ${p.platform}" data-name="${escapeHtml(p.name)}" title="${escapeHtml(p.name)}"></span>`
              ).join('')}</div>`
            : '<span style="color:var(--text-muted)">—</span>';

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

        // Celda de ruta: clickable para abrir explorador
        const pathCell = document.createElement('td');
        pathCell.className = 'path-cell';
        pathCell.title = file.path + ' — clic para abrir en explorador';
        pathCell.textContent = file.path;
        pathCell.style.cursor = 'pointer';
        pathCell.addEventListener('click', (e) => {
            e.stopPropagation();
            revealInExplorer(encodeURIComponent(file.path));
        });

        tr.innerHTML = `
            <td>${index + 1}</td>
            <td></td>
            <td><strong>${escapeHtml(file.name)}</strong>${file.has_error ? ' <span style="color:var(--warning)" title="No se pudo leer metadata completa">⚠</span>' : ''}</td>
            <td>${escapeHtml(file.artist || '—')}</td>
            <td>${escapeHtml(file.album || '—')}</td>
            <td>${escapeHtml(file.duration_str)}</td>
            <td><span class="format-badge ${escapeHtml(file.ext)}">${escapeHtml(file.ext.toUpperCase())}</span></td>
            <td class="quality-col ${showQuality ? '' : 'hidden'}">${qualityHtml}</td>
            <td>${playlistsHtml}</td>
            <td class="size-cell">${escapeHtml(file.size_str)}${dupHtml}</td>
        `;
        // Insertar el boton play en la segunda celda (td vacio)
        tr.children[1].appendChild(playBtn);
        // Insertar la celda de ruta al final
        tr.appendChild(pathCell);

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
