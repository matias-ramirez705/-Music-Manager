/* ============================================
   compare.js - Pestana "Comparar con Playlist" (v1.1)
   ============================================
   Maneja:
     - Estado de la musica local
     - Carga de playlist via /api/compare
     - Mostrar faltantes / coincidentes
     - Exportar CSV
     - Guardar playlist en favoritos (NUEVO)
     - Circulo de progreso
*/

let lastResult = null;
let currentView = 'missing';

const playlistUrlInput = document.getElementById('playlist-url');
const btnFetchPlaylist = document.getElementById('btn-fetch-playlist');
const btnSaveComparison = document.getElementById('btn-save-comparison');
const playlistInfo     = document.getElementById('playlist-info');
const actionBar        = document.getElementById('action-bar');
const resultsContainer = document.getElementById('results-container');
const resultsTbody     = document.getElementById('results-tbody');
const emptyCompare     = document.getElementById('empty-compare');
const localStatusText  = document.getElementById('local-status-text');
const btnShowMissing   = document.getElementById('btn-show-missing');
const btnShowMatched   = document.getElementById('btn-show-matched');
const btnExportCsv     = document.getElementById('btn-export-csv');

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    checkLocalStatus();

    // Si venimos con ?url=... (desde Saved Playlists), precargar y comparar
    const params = new URLSearchParams(window.location.search);
    const preloadedUrl = params.get('url');
    if (preloadedUrl) {
        playlistUrlInput.value = preloadedUrl;
        // Limpiar query string
        window.history.replaceState({}, '', '/compare');
        // Auto-disparar comparacion
        fetchPlaylist();
    } else {
        // Restaurar comparacion persistida (al volver de otra pestana)
        restorePersistedComparison();
    }
});

// ------------------------------------------------------------------
// Persistencia de la comparacion en sessionStorage
// ------------------------------------------------------------------
function persistComparison() {
    if (!lastResult) return;
    try {
        sessionStorage.setItem('compare_lastResult', JSON.stringify(lastResult));
        sessionStorage.setItem('compare_url', playlistUrlInput.value);
        sessionStorage.setItem('compare_view', currentView);
    } catch (e) {
        // sessionStorage lleno o no disponible
    }
}

function restorePersistedComparison() {
    try {
        const saved = sessionStorage.getItem('compare_lastResult');
        const savedUrl = sessionStorage.getItem('compare_url');
        const savedView = sessionStorage.getItem('compare_view');
        if (saved && savedUrl) {
            lastResult = JSON.parse(saved);
            playlistUrlInput.value = savedUrl;
            currentView = savedView || 'missing';
            renderPlaylistInfo(lastResult);
            renderResults(currentView);
            showResults();
            btnSaveComparison.classList.remove('hidden');
            // Marcar boton activo
            btnShowMissing.classList.toggle('btn-primary', currentView === 'missing');
            btnShowMissing.classList.toggle('btn-secondary', currentView !== 'missing');
            btnShowMatched.classList.toggle('btn-primary', currentView === 'matched');
            btnShowMatched.classList.toggle('btn-secondary', currentView !== 'matched');
        }
    } catch (e) {
        // JSON invalido o no disponible
    }
}

function clearPersistedComparison() {
    sessionStorage.removeItem('compare_lastResult');
    sessionStorage.removeItem('compare_url');
    sessionStorage.removeItem('compare_view');
}

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
    btnSaveComparison.addEventListener('click', saveToFavorites);
    btnShowMissing.addEventListener('click', () => showView('missing'));
    btnShowMatched.addEventListener('click', () => showView('matched'));
    btnExportCsv.addEventListener('click', exportCsv);
    playlistUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') fetchPlaylist();
    });
    // Importar CSV (Exportify)
    const btnImportCsv = document.getElementById('btn-import-csv-compare');
    const csvFileInput = document.getElementById('csv-file-input-compare');
    if (btnImportCsv) btnImportCsv.addEventListener('click', () => csvFileInput.click());
    if (csvFileInput) csvFileInput.addEventListener('change', handleCsvCompare);
}

// ------------------------------------------------------------------
// Comparar con CSV de Exportify
// ------------------------------------------------------------------
async function handleCsvCompare(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
        const csvContent = e.target.result;
        const name = file.name.replace(/\.csv$/i, '');

        btnFetchPlaylist.disabled = true;
        btnFetchPlaylist.textContent = 'Comparando CSV...';
        try {
            const data = await postJSON('/api/compare', {
                csv_content: csvContent,
                name: name,
            });
            if (data.error) {
                showToast(data.error, 'error', 5000);
                return;
            }
            lastResult = data;
            renderPlaylistInfo(data);
            renderResults('missing');
            showResults();
            btnSaveComparison.classList.remove('hidden');
            persistComparison();

            const warning = data.playlist.warning;
            if (warning) {
                showToast(warning, 'error', 8000);
            } else {
                showToast(`CSV cargado: ${data.playlist.title} (${data.playlist.count} canciones)`, 'success');
            }
        } catch (err) {
            showToast('Error: ' + err.message, 'error', 5000);
        } finally {
            btnFetchPlaylist.disabled = false;
            btnFetchPlaylist.textContent = 'Cargar Playlist';
        }
    };
    reader.readAsText(file);
    event.target.value = '';
}

// ------------------------------------------------------------------
// Cargar + comparar
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
        // Mostrar boton guardar
        btnSaveComparison.classList.remove('hidden');
        // Persistir para que se mantenga al cambiar de pestana
        persistComparison();

        // Mostrar advertencia si la playlist vino incompleta
        const warning = data.playlist.warning;
        if (warning) {
            showToast(warning, 'error', 8000);
        } else {
            showToast(`Playlist cargada: ${data.playlist.title}`, 'success');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        btnFetchPlaylist.disabled = false;
        btnFetchPlaylist.textContent = 'Cargar Playlist';
    }
}

// ------------------------------------------------------------------
// Guardar en favoritos
// ------------------------------------------------------------------
async function saveToFavorites() {
    if (!lastResult) return;
    const url = playlistUrlInput.value.trim();
    if (!url) {
        showToast('No hay URL para guardar.', 'error');
        return;
    }
    btnSaveComparison.disabled = true;
    btnSaveComparison.textContent = 'Guardando...';
    try {
        const data = await postJSON('/api/save-playlist', { url });
        if (data.saved) {
            showToast(`Guardada como "${data.saved.name}"`, 'success');
            btnSaveComparison.textContent = 'Guardada ✓';
            btnSaveComparison.disabled = true;
        }
    } catch (e) {
        showToast('Error al guardar: ' + e.message, 'error', 5000);
        btnSaveComparison.disabled = false;
        btnSaveComparison.textContent = 'Guardar en favoritos';
    }
}

// ------------------------------------------------------------------
// Render info playlist
// ------------------------------------------------------------------
function renderPlaylistInfo(data) {
    document.getElementById('playlist-title').textContent = data.playlist.title;
    document.getElementById('playlist-author').textContent =
        data.playlist.uploader || 'Autor desconocido';

    document.getElementById('count-missing').textContent = data.missing.length;
    document.getElementById('count-matched').textContent = data.matched.length;

    const progress = Math.min(100, Math.max(0, data.progress));
    document.getElementById('progress-path').setAttribute(
        'stroke-dasharray', `${progress}, 100`
    );
    document.getElementById('progress-text').textContent = `${progress}%`;

    playlistInfo.classList.remove('hidden');
    actionBar.classList.remove('hidden');
}

function showResults() {
    emptyCompare.classList.add('hidden');
    resultsContainer.classList.remove('hidden');
}

function showView(view) {
    currentView = view;
    if (!lastResult) return;
    renderResults(view);
    btnShowMissing.classList.toggle('btn-primary', view === 'missing');
    btnShowMissing.classList.toggle('btn-secondary', view !== 'missing');
    btnShowMatched.classList.toggle('btn-primary', view === 'matched');
    btnShowMatched.classList.toggle('btn-secondary', view !== 'matched');
    // Actualizar vista persistida
    persistComparison();
}

function renderResults(view) {
    const items = (view === 'missing') ? lastResult.missing : lastResult.matched;
    resultsTbody.innerHTML = '';

    if (items.length === 0) {
        const msg = view === 'missing'
            ? '¡Tienes todas las canciones de la playlist!'
            : 'No hay coincidencias con tu biblioteca local.';
        resultsTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:32px; color:var(--text-muted);">${msg}</td></tr>`;
        return;
    }

    const isYoutube = lastResult.platform === 'youtube';
    const platformIcon = isYoutube ? '▶' : '♫';
    const platformColor = isYoutube ? '#ff0000' : '#1db954';
    const platformName = isYoutube ? 'YouTube Music' : 'Spotify';

    items.forEach((track, index) => {
        const tr = document.createElement('tr');
        let statusHtml;
        if (view === 'missing') {
            statusHtml = '<span class="match-status status-missing">Falta</span>';
        } else {
            const type = track.match_type;
            if (type === 'exact') {
                statusHtml = '<span class="match-status status-matched">Exacta</span>';
            } else if (type === 'artist_partial') {
                statusHtml = '<span class="match-status status-matched-partial">Art. similar</span>';
            } else {
                statusHtml = '<span class="match-status status-matched-partial">Solo título</span>';
            }
        }

        // Columna Calidad local (solo para matched)
        const qualityHtml = (view === 'matched' && track.local_quality)
            ? `<span class="quality-badge">${escapeHtml(track.local_quality)}</span>`
            : '—';

        // Columna Formato local (solo para matched)
        const formatHtml = (view === 'matched' && track.local_format)
            ? `<span class="format-badge ${escapeHtml(track.local_format.toLowerCase())}">${escapeHtml(track.local_format)}</span>`
            : '—';

        // Columna Escuchar local (solo para matched)
        let listenLocalHtml = '—';
        if (view === 'matched' && track.local_path) {
            const encodedPath = encodeURIComponent(track.local_path);
            const safeName = (track.local_name || track.title || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
            const safeArtist = (track.local_artist || track.artist || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
            listenLocalHtml = `<button class="play-btn" title="Reproducir local"
                onclick="event.stopPropagation(); playFile(decodeURIComponent('${encodedPath}'), '${safeName}', '${safeArtist}');">▶</button>`;
        }

        // Columna Abrir online (con icono y color de plataforma)
        let onlineLinkHtml = '—';
        if (track.url) {
            onlineLinkHtml = `<a href="${escapeHtml(track.url)}" target="_blank" rel="noopener"
                title="Abrir en ${platformName}"
                style="color: ${platformColor}; text-decoration: none; font-weight: 600;">
                Abrir <span style="font-size: 14px;">${platformIcon}</span></a>`;
        }

        tr.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${escapeHtml(track.title)}</strong></td>
            <td>${escapeHtml(track.artist)}</td>
            <td>${formatDuration(track.duration)}</td>
            <td>${statusHtml}</td>
            <td>${qualityHtml}</td>
            <td>${formatHtml}</td>
            <td style="text-align:center;">${listenLocalHtml}</td>
            <td>${onlineLinkHtml}</td>
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
