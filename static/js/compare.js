/* ============================================
   compare.js - Pestana "Comparar con Playlist"
   ============================================
   Maneja:
     - Estado de la musica local (cargada o no)
     - Carga de playlist via /api/fetch-playlist
     - Comparacion via /api/compare
     - Mostrar lista de faltantes / coincidentes
     - Exportar CSV
     - Circulo de progreso
*/

// Estado
let lastResult = null;  // resultado de la ultima comparacion
let currentView = 'missing';  // 'missing' | 'matched'

// DOM
const playlistUrlInput = document.getElementById('playlist-url');
const btnFetchPlaylist = document.getElementById('btn-fetch-playlist');
const playlistInfo     = document.getElementById('playlist-info');
const actionBar        = document.getElementById('action-bar');
const resultsContainer = document.getElementById('results-container');
const resultsTbody     = document.getElementById('results-tbody');
const emptyCompare     = document.getElementById('empty-compare');
const localStatusText  = document.getElementById('local-status-text');
const btnShowMissing   = document.getElementById('btn-show-missing');
const btnShowMatched   = document.getElementById('btn-show-matched');
const btnExportCsv     = document.getElementById('btn-export-csv');

// ------------------------------------------------------------------
// AL CARGAR
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    checkLocalStatus();
});

async function checkLocalStatus() {
    try {
        const data = await getJSON('/api/last-scan');
        if (data.count > 0) {
            localStatusText.textContent =
                `Musica local cargada: ${data.count} archivos en ${data.folder}`;
        } else {
            localStatusText.textContent =
                'No has escaneado tu musica local. Ve a "Mi Musica" primero.';
        }
    } catch (e) {
        localStatusText.textContent = 'No se pudo verificar el estado local.';
    }
}

function bindEvents() {
    btnFetchPlaylist.addEventListener('click', fetchPlaylist);
    btnShowMissing.addEventListener('click', () => showView('missing'));
    btnShowMatched.addEventListener('click', () => showView('matched'));
    btnExportCsv.addEventListener('click', exportCsv);

    playlistUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') fetchPlaylist();
    });
}

// ------------------------------------------------------------------
// Cargar playlist + comparar (en una sola llamada)
// ------------------------------------------------------------------
async function fetchPlaylist() {
    const url = playlistUrlInput.value.trim();
    if (!url) {
        showToast('Pega una URL de playlist primero.', 'error');
        return;
    }

    btnFetchPlaylist.disabled = true;
    btnFetchPlaylist.textContent = 'Comparando...';

    try {
        const data = await postJSON('/api/compare', { url });

        if (data.error) {
            showToast(data.error, 'error', 5000);
            return;
        }

        lastResult = data;
        renderPlaylistInfo(data);
        renderResults('missing');
        showResults();
        showToast(`Playlist cargada: ${data.playlist.title}`, 'success');

    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        btnFetchPlaylist.disabled = false;
        btnFetchPlaylist.textContent = 'Cargar Playlist';
    }
}

// ------------------------------------------------------------------
// Mostrar info de la playlist + progreso
// ------------------------------------------------------------------
function renderPlaylistInfo(data) {
    document.getElementById('playlist-title').textContent = data.playlist.title;
    document.getElementById('playlist-author').textContent =
        data.playlist.uploader || 'Autor desconocido';

    // Contadores
    document.getElementById('count-missing').textContent = data.missing.length;
    document.getElementById('count-matched').textContent = data.matched.length;

    // Circulo de progreso
    const progress = Math.min(100, Math.max(0, data.progress));
    document.getElementById('progress-path').setAttribute(
        'stroke-dasharray', `${progress}, 100`
    );
    document.getElementById('progress-text').textContent = `${progress}%`;

    playlistInfo.classList.remove('hidden');
    actionBar.classList.remove('hidden');
}

// ------------------------------------------------------------------
// Mostrar resultados
// ------------------------------------------------------------------
function showResults() {
    emptyCompare.classList.add('hidden');
    resultsContainer.classList.remove('hidden');
}

function showView(view) {
    currentView = view;
    if (!lastResult) return;
    renderResults(view);

    // Actualizar estilos de botones
    btnShowMissing.classList.toggle('btn-primary', view === 'missing');
    btnShowMissing.classList.toggle('btn-secondary', view !== 'missing');
    btnShowMatched.classList.toggle('btn-primary', view === 'matched');
    btnShowMatched.classList.toggle('btn-secondary', view !== 'matched');
}

function renderResults(view) {
    const items = (view === 'missing') ? lastResult.missing : lastResult.matched;
    resultsTbody.innerHTML = '';

    if (items.length === 0) {
        const msg = view === 'missing'
            ? '¡Tienes todas las canciones de la playlist!'
            : 'No hay coincidencias con tu biblioteca local.';
        resultsTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">${msg}</td></tr>`;
        return;
    }

    items.forEach((track, index) => {
        const tr = document.createElement('tr');

        // Estado: missing o tipo de match
        let statusHtml;
        if (view === 'missing') {
            statusHtml = '<span class="match-status status-missing">Falta</span>';
        } else {
            // match_type: 'exact' | 'artist_partial' | 'title_only'
            const type = track.match_type;
            if (type === 'exact') {
                statusHtml = '<span class="match-status status-matched">Coincidencia exacta</span>';
            } else if (type === 'artist_partial') {
                statusHtml = '<span class="match-status status-matched-partial">Coincidencia (artista similar)</span>';
            } else {
                statusHtml = '<span class="match-status status-matched-partial">Coincidencia (solo titulo)</span>';
            }
        }

        // Enlace a la cancion original
        const linkHtml = track.url
            ? `<a href="${escapeHtml(track.url)}" target="_blank" rel="noopener" style="color:var(--accent); text-decoration:none;">Abrir ↗</a>`
            : '—';

        tr.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${escapeHtml(track.title)}</strong></td>
            <td>${escapeHtml(track.artist)}</td>
            <td>${escapeHtml(track.album || '—')}</td>
            <td>${formatDuration(track.duration)}</td>
            <td>${statusHtml}</td>
            <td>${linkHtml}</td>
        `;
        resultsTbody.appendChild(tr);
    });
}

// ------------------------------------------------------------------
// Exportar CSV
// ------------------------------------------------------------------
async function exportCsv() {
    if (!lastResult || lastResult.missing.length === 0) {
        showToast('No hay canciones faltantes para exportar.', 'error');
        return;
    }

    try {
        const resp = await fetch('/api/export-missing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ missing: lastResult.missing }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'Error al exportar');
        }

        // Recibir como blob y descargar
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'canciones_faltantes.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('CSV exportado correctamente.', 'success');
    } catch (e) {
        showToast('Error al exportar: ' + e.message, 'error');
    }
}
