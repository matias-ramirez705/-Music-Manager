/* ============================================
   local.js - Pestana "Mi Musica"
   ============================================
   Maneja:
     - Seleccion de carpeta (input + dialogo nativo)
     - Escaneo via /api/scan
     - Renderizado de la tabla con todos los archivos
     - Busqueda, filtro por formato y ordenamiento
     - Mostrar/ocultar columna de calidad
*/

// Estado local de la pagina
let allFiles = [];        // todos los archivos del ultimo escaneo
let filteredFiles = [];   // archivos despues de aplicar filtros
let showQuality = false;  // toggle de columna calidad

// Referencias a elementos del DOM
const folderInput   = document.getElementById('folder-input');
const btnBrowse     = document.getElementById('btn-browse');
const btnScan       = document.getElementById('btn-scan');
const statsBar      = document.getElementById('stats-bar');
const filterBar     = document.getElementById('filter-bar');
const searchInput   = document.getElementById('search-input');
const filterFormat  = document.getElementById('filter-format');
const sortBy        = document.getElementById('sort-by');
const btnToggleQ    = document.getElementById('btn-toggle-quality');
const musicTable    = document.getElementById('music-table');
const musicTbody    = document.getElementById('music-tbody');
const emptyState    = document.getElementById('empty-state');
const loadingState  = document.getElementById('loading-state');

// ------------------------------------------------------------------
// AL CARGAR LA PAGINA
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    // Cargar el ultimo escaneo (si existe en memoria del servidor)
    try {
        const data = await getJSON('/api/last-scan');
        if (data.count > 0) {
            allFiles = data.files;
            renderTable();
            renderStats(data);
            showTable();
        }
    } catch (e) {
        // Sin escaneo previo, mostrar empty state
    }

    bindEvents();
});

// ------------------------------------------------------------------
// Eventos
// ------------------------------------------------------------------
function bindEvents() {
    btnBrowse.addEventListener('click', browseFolder);
    btnScan.addEventListener('click', scanFolder);
    searchInput.addEventListener('input', applyFilters);
    filterFormat.addEventListener('change', applyFilters);
    sortBy.addEventListener('change', applyFilters);
    btnToggleQ.addEventListener('click', toggleQuality);

    // Enter en el input de carpeta dispara escaneo
    folderInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') scanFolder();
    });
}

// ------------------------------------------------------------------
// Abrir dialogo nativo de Windows para elegir carpeta
// ------------------------------------------------------------------
async function browseFolder() {
    btnBrowse.disabled = true;
    try {
        const data = await getJSON('/api/browse');
        if (data.folder) {
            folderInput.value = data.folder;
        }
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

    // Mostrar loading
    emptyState.classList.add('hidden');
    musicTable.classList.add('hidden');
    loadingState.classList.remove('hidden');

    try {
        const data = await postJSON('/api/scan', { folder });
        allFiles = data.files;
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
// Renderizar estadisticas
// ------------------------------------------------------------------
function renderStats(data) {
    document.getElementById('stat-folder').textContent = data.folder;
    document.getElementById('stat-count').textContent = data.count;
    document.getElementById('stat-size').textContent = data.total_size_str || '—';

    // Formatos: "FLAC: 23, MP3: 145"
    const formats = Object.entries(data.stats || {})
        .map(([ext, count]) => `${ext.replace('.', '').toUpperCase()}: ${count}`)
        .join(', ');
    document.getElementById('stat-formats').textContent = formats || '—';

    // Llenar select de filtros
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

// ------------------------------------------------------------------
// Mostrar tabla (ocultar empty / loading)
// ------------------------------------------------------------------
function showTable() {
    loadingState.classList.add('hidden');
    emptyState.classList.add('hidden');
    statsBar.classList.remove('hidden');
    filterBar.classList.remove('hidden');
    musicTable.classList.remove('hidden');
}

// ------------------------------------------------------------------
// Aplicar filtros + orden y renderizar
// ------------------------------------------------------------------
function applyFilters() {
    const query = searchInput.value.toLowerCase().trim();
    const format = filterFormat.value;
    const sort = sortBy.value;

    // Filtrar
    filteredFiles = allFiles.filter(f => {
        // Filtro por formato
        if (format && f.ext !== format) return false;
        // Filtro por texto (busca en nombre, artista, album)
        if (query) {
            const haystack = `${f.name} ${f.artist} ${f.album}`.toLowerCase();
            if (!haystack.includes(query)) return false;
        }
        return true;
    });

    // Ordenar
    filteredFiles.sort((a, b) => {
        let va = a[sort], vb = b[sort];
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return -1;
        if (va > vb) return 1;
        return 0;
    });

    renderRows();
}

// ------------------------------------------------------------------
// Renderizar tabla completa
// ------------------------------------------------------------------
function renderTable() {
    applyFilters();
}

// ------------------------------------------------------------------
// Renderizar filas (tbody)
// ------------------------------------------------------------------
function renderRows() {
    musicTbody.innerHTML = '';

    if (filteredFiles.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="9" style="text-align:center; padding:32px; color:var(--text-muted);">
            No se encontraron archivos con esos filtros.
        </td>`;
        musicTbody.appendChild(tr);
        return;
    }

    filteredFiles.forEach((file, index) => {
        const tr = document.createElement('tr');

        // Columna calidad (badge con clase CSS segun categoria)
        const q = file.quality;
        const qualityHtml = q
            ? `<span class="quality-badge quality-${q.category}" title="${escapeHtml(q.description)}">${escapeHtml(q.label)}</span>`
            : '';

        // Construir fila
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${escapeHtml(file.name)}</strong>${file.has_error ? ' <span style="color:var(--warning)" title="No se pudo leer metadata completa">⚠</span>' : ''}</td>
            <td>${escapeHtml(file.artist || '—')}</td>
            <td>${escapeHtml(file.album || '—')}</td>
            <td>${escapeHtml(file.duration_str)}</td>
            <td><span class="format-badge ${escapeHtml(file.ext)}">${escapeHtml(file.ext.toUpperCase())}</span></td>
            <td class="quality-col ${showQuality ? '' : 'hidden'}">${qualityHtml}</td>
            <td>${escapeHtml(file.size_str)}</td>
            <td title="${escapeHtml(file.path)}">${escapeHtml(file.path)}</td>
        `;

        // Hacer clic en la fila abre el editor con ese archivo
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', () => {
            // Pasamos la ruta via query string al editor
            window.location.href = `/editor?path=${encodeURIComponent(file.path)}`;
        });

        musicTbody.appendChild(tr);
    });

    // Actualizar visibilidad de columna calidad
    document.querySelectorAll('.quality-col').forEach(col => {
        col.classList.toggle('hidden', !showQuality);
    });
}

// ------------------------------------------------------------------
// Toggle columna de calidad
// ------------------------------------------------------------------
function toggleQuality() {
    showQuality = !showQuality;
    btnToggleQ.textContent = showQuality ? 'Ocultar calidad' : 'Mostrar calidad';
    renderRows();
}
