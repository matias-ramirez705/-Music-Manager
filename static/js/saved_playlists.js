/* ============================================
   saved_playlists.js - Pestana "Playlists Guardadas" (v1.9)
   ============================================
   Maneja:
     - Listar playlists guardadas (cards)
     - Agregar nueva playlist desde URL (YouTube Music)
       o desde CSV (Exportify para Spotify)
     - Abrir detalle de playlist (ver canciones)
     - Refrescar canciones de una playlist
     - Renombrar playlist
     - Eliminar playlist
     - Comparar playlist guardada con musica local
     - Copiar enlace de playlist al portapapeles
*/

const newPlaylistUrl = document.getElementById('new-playlist-url');
const btnSavePlaylist = document.getElementById('btn-save-playlist');
const savedList = document.getElementById('saved-list');
const savedEmpty = document.getElementById('saved-empty');

// v3.17: índice de títulos locales para el modal "¿En Mi Música?"
// Si local.js está cargado (página Mi Música), reutiliza sus funciones.
// Si no (página Playlists Guardadas), usa las propias.
// Esto es necesario porque saved_playlists.html no carga local.js.
let _spLocalTitleIndex = null;

function _spNormalizeTitle(s) {
    // Reutilizar la de local.js si existe, sino usar la propia
    if (typeof _normalizeTitle === 'function') return _normalizeTitle(s);
    if (!s) return '';
    return s.toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/\([^)]*\)/g, '')
        .replace(/\[[^]]*\]/g, '')
        .replace(/\b(feat|ft)\b\.?/g, '')
        .replace(/[^a-z0-9\s]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

async function _spBuildLocalTitleIndex() {
    // Reutilizar el índice de local.js si existe y está construido
    if (typeof _localTitleIndex !== 'undefined' && _localTitleIndex !== null) {
        _spLocalTitleIndex = _localTitleIndex;
        return;
    }
    // Reutilizar buildLocalTitleIndex de local.js si existe (lo construye y cachea)
    if (typeof buildLocalTitleIndex === 'function') {
        try {
            await buildLocalTitleIndex();
            if (typeof _localTitleIndex !== 'undefined') {
                _spLocalTitleIndex = _localTitleIndex;
                return;
            }
        } catch (e) {}
    }
    // Sino, construir el propio consultando /api/last-scan
    if (_spLocalTitleIndex !== null) return;
    try {
        const data = await getJSON('/api/last-scan');
        const files = data.files || [];
        _spLocalTitleIndex = new Set();
        for (const f of files) {
            const norm = _spNormalizeTitle(f.name || '');
            if (norm) _spLocalTitleIndex.add(norm);
        }
    } catch (e) {
        _spLocalTitleIndex = new Set();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadSavedPlaylists();
});

function bindEvents() {
    if (btnSavePlaylist) btnSavePlaylist.addEventListener('click', saveNewPlaylist);
    if (newPlaylistUrl) newPlaylistUrl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveNewPlaylist();
    });
    // Boton importar CSV
    const btnImportCsv = document.getElementById('btn-import-csv');
    const csvFileInput = document.getElementById('csv-file-input');
    if (btnImportCsv) btnImportCsv.addEventListener('click', () => csvFileInput.click());
    if (csvFileInput) csvFileInput.addEventListener('change', handleCsvImport);
    // Boton importar TXT
    const btnImportTxt = document.getElementById('btn-import-txt');
    const txtFileInput = document.getElementById('txt-file-input');
    if (btnImportTxt) btnImportTxt.addEventListener('click', () => openTxtModal());
    if (txtFileInput) txtFileInput.addEventListener('change', handleTxtFileUpload);
    // Botones del modal TXT
    const btnTxtLoad = document.getElementById('btn-txt-load-default');
    const btnTxtSave = document.getElementById('btn-txt-save-default');
    const btnTxtImport = document.getElementById('btn-txt-import');
    if (btnTxtLoad) btnTxtLoad.addEventListener('click', loadDefaultTxt);
    if (btnTxtSave) btnTxtSave.addEventListener('click', saveDefaultTxt);
    if (btnTxtImport) btnTxtImport.addEventListener('click', importFromTxt);
    // Buscador
    const searchInput = document.getElementById('saved-search');
    if (searchInput) searchInput.addEventListener('input', () => renderSavedList(window._allPlaylists || []));

    // v3.17: Selector de ordenamiento
    const sortBySelect = document.getElementById('saved-sort-by');
    if (sortBySelect) {
        sortBySelect.addEventListener('change', () => {
            localStorage.setItem('saved_playlists_sort_by', sortBySelect.value);
            loadSavedPlaylists();
        });
    }
}

// ------------------------------------------------------------------
// Modal TXT: cargar/guardar/importar playlists
// ------------------------------------------------------------------
function openTxtModal() {
    const modal = document.getElementById('txt-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    // Intentar cargar el archivo por defecto automaticamente
    loadDefaultTxt();
}

async function loadDefaultTxt() {
    const textarea = document.getElementById('txt-content');
    if (!textarea) return;
    try {
        const data = await getJSON('/api/txt-playlists/load');
        if (data.exists && data.content) {
            textarea.value = data.content;
            showToast('playlists.txt cargado.', 'success');
        } else {
            // Cargar plantilla de ejemplo
            textarea.value = '# Mis playlists\n' +
                '# Las líneas con # son comentarios\n\n' +
                '# YouTube Music\n' +
                'https://music.youtube.com/playlist?list=PL...\n\n' +
                '# Spotify (máx 100 canciones por URL)\n' +
                '# Para playlists grandes, exporta como CSV desde exportify.app\n' +
                'https://open.spotify.com/playlist/...\n\n' +
                '# CSV de Exportify (rutas locales, una por línea)\n' +
                '# C:\\Users\\Matias\\Music\\mi_playlist.csv\n';
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function saveDefaultTxt() {
    const textarea = document.getElementById('txt-content');
    if (!textarea) return;
    try {
        const data = await postJSON('/api/txt-playlists/save', { content: textarea.value });
        showToast(data.message, data.success ? 'success' : 'error');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function importFromTxt() {
    const textarea = document.getElementById('txt-content');
    if (!textarea || !textarea.value.trim()) {
        showToast('El campo está vacío.', 'error');
        return;
    }

    const btn = document.getElementById('btn-txt-import');
    const resultsDiv = document.getElementById('txt-results');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Importando...';
    }
    if (resultsDiv) resultsDiv.innerHTML = '<p class="empty-hint">Importando playlists... esto puede tardar.</p>';

    try {
        const data = await postJSON('/api/import-txt-playlists', { content: textarea.value });
        if (data.error) {
            if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(data.error)}</p>`;
            return;
        }

        // Mostrar resultados
        let html = `<div style="margin-bottom:12px;">
            <strong style="color:var(--accent);">${data.success_count}</strong> exitosas,
            <strong style="color:var(--danger);">${data.error_count}</strong> errores,
            ${data.total} total
        </div>`;

        if (data.results && data.results.length > 0) {
            html += '<div style="max-height:300px; overflow-y:auto;">';
            data.results.forEach(r => {
                const icon = r.success ? '✓' : '✗';
                const color = r.success ? 'var(--accent)' : 'var(--danger)';
                const name = r.name ? ` — ${escapeHtml(r.name)} (${r.track_count} canciones)` : '';
                const err = r.error ? ` — ${escapeHtml(r.error)}` : '';
                const warning = r.warning ? ` <span style="color:var(--warning); font-size:10px;">⚠ ${escapeHtml(r.warning.substring(0, 80))}</span>` : '';
                html += `<div style="padding:4px 0; font-size:12px; color:${color};">${icon} Línea ${r.line}: ${escapeHtml(r.url.substring(0, 60))}${name}${err}${warning}</div>`;
            });
            html += '</div>';
        }

        if (resultsDiv) resultsDiv.innerHTML = html;

        // Recargar lista de playlists guardadas
        loadSavedPlaylists();
        sessionStorage.setItem('playlists_changed', '1');

        showToast(`Importadas ${data.success_count} de ${data.total} playlists`, 'success', 5000);
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '▶ Importar todas';
        }
    }
}

async function handleTxtFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        const textarea = document.getElementById('txt-content');
        if (textarea) {
            textarea.value = e.target.result;
            openTxtModal();
        }
    };
    reader.readAsText(file);
    event.target.value = '';
}

// ------------------------------------------------------------------
// Importar CSV de Exportify
// ------------------------------------------------------------------
async function handleCsvImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Leer contenido del CSV
    const reader = new FileReader();
    reader.onload = async (e) => {
        const csvContent = e.target.result;
        const name = file.name.replace(/\.csv$/i, '');

        btnSavePlaylist.disabled = true;
        btnSavePlaylist.textContent = 'Importando CSV...';
        try {
            const data = await postJSON('/api/save-playlist', {
                csv_content: csvContent,
                name: name,
            });
            if (data.saved) {
                newPlaylistUrl.value = '';
                loadSavedPlaylists();
                sessionStorage.setItem('playlists_changed', '1');
                showToast(`CSV importado: "${data.saved.name}" (${data.saved.track_count} canciones)`, 'success');
            } else if (data.error) {
                showToast('Error: ' + data.error, 'error', 5000);
            }
        } catch (err) {
            showToast('Error al importar CSV: ' + err.message, 'error', 5000);
        } finally {
            btnSavePlaylist.disabled = false;
            btnSavePlaylist.textContent = 'Guardar playlist';
        }
    };
    reader.readAsText(file);

    // Reset del input para permitir seleccionar el mismo archivo otra vez
    event.target.value = '';
}

// ------------------------------------------------------------------
// Listar playlists guardadas
// ------------------------------------------------------------------
async function loadSavedPlaylists() {
    try {
        // v3.17: leer sort_by del select (persistido en localStorage)
        const sortBySelect = document.getElementById('saved-sort-by');
        let sortBy = 'last_accessed';
        if (sortBySelect) {
            // Restaurar de localStorage si hay
            const saved = localStorage.getItem('saved_playlists_sort_by');
            if (saved && [...sortBySelect.options].some(o => o.value === saved)) {
                sortBySelect.value = saved;
            }
            sortBy = sortBySelect.value;
        }
        // v3.19: cargar playlists y conteos de descargadas en paralelo
        const [plData, countsData] = await Promise.all([
            getJSON('/api/saved-playlists?sort_by=' + encodeURIComponent(sortBy)),
            getJSON('/api/saved-playlists/local-counts').catch(() => ({ counts: {}, has_local: false })),
        ]);
        window._allPlaylists = plData.playlists || [];
        // v3.19: guardar conteos para mostrar en las cards
        window._localCounts = countsData.counts || {};
        window._hasLocalMusic = countsData.has_local || false;
        renderSavedList(window._allPlaylists);
    } catch (e) {
        showToast('Error al cargar playlists: ' + e.message, 'error');
    }
}

function renderSavedList(playlists) {
    // Aplicar filtro del buscador
    const searchInput = document.getElementById('saved-search');
    const q = searchInput ? searchInput.value.toLowerCase().trim() : '';
    let filtered = playlists;
    if (q) {
        filtered = playlists.filter(p =>
            (p.name + ' ' + p.platform).toLowerCase().includes(q)
        );
    }

    savedList.innerHTML = '';
    if (filtered.length === 0) {
        savedList.appendChild(savedEmpty);
        return;
    }

    filtered.forEach(p => {
        const card = document.createElement('div');
        card.className = 'saved-card';
        const platformLabel = p.platform === 'youtube' ? 'YouTube Music' : 'Spotify';
        const platformIcon = p.platform === 'youtube' ? '▶' : '♫';

        // Formatear fecha
        const lastAcc = p.last_accessed
            ? new Date(p.last_accessed).toLocaleDateString('es-ES', {
                  day: 'numeric', month: 'short', year: 'numeric'
              })
            : '—';

        // v3.17: si el modo de orden es "personalizado", mostrar input numérico
        const sortBySelect = document.getElementById('saved-sort-by');
        const isCustomSort = sortBySelect && sortBySelect.value === 'sort_order';
        const sortOrderHtml = isCustomSort
            ? `<label style="display:inline-flex; align-items:center; gap:4px; font-size:11px; color:var(--text-secondary);">
                   #<input type="number" min="0" max="9999" value="${p.sort_order || 0}"
                       style="width:50px; padding:2px 4px; background:var(--bg-elevated); border:1px solid var(--border); border-radius:3px; color:var(--text-primary); font-size:11px;"
                       onclick="event.stopPropagation()"
                       onchange="setSortOrder('${p.id}', this.value)"
                       title="Orden personalizado (menor = primero)">
               </label>`
            : '';

        // v3.19: calcular "X/Y descargadas" para mostrar en la card
        let downloadedInfoHtml = '';
        if (window._hasLocalMusic && window._localCounts) {
            const c = window._localCounts[p.id];
            if (c) {
                const downloaded = c.downloaded || 0;
                const total = c.total || p.track_count || 0;
                const pct = total > 0 ? Math.round((downloaded / total) * 100) : 0;
                // Color: verde si todas, naranja si faltan, rojo si 0
                let color = 'var(--warning)';
                if (downloaded === total && total > 0) color = 'var(--accent)';
                else if (downloaded === 0) color = 'var(--danger)';
                downloadedInfoHtml = `
                    <div style="margin-top:6px; font-size:11px; color:var(--text-secondary); display:flex; align-items:center; gap:6px;">
                        <span style="color:${color}; font-weight:600;">${downloaded}</span>
                        <span>/ ${total} descargadas</span>
                        <span style="display:inline-block; width:60px; height:4px; background:var(--bg-elevated); border-radius:2px; overflow:hidden;">
                            <span style="display:block; height:100%; background:${color}; width:${pct}%;"></span>
                        </span>
                    </div>`;
            }
        }

        card.innerHTML = `
            <div class="saved-card-header">
                <div class="platform-icon ${p.platform}">${platformIcon}</div>
                <div class="saved-card-info">
                    <div class="saved-card-title" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</div>
                    <div class="saved-card-meta">${escapeHtml(p.uploader || 'Autor desconocido')} • ${platformLabel}</div>
                </div>
            </div>
            <div class="saved-card-stats">
                <span>${p.track_count} canciones</span>
                <span>Acceso: ${lastAcc}</span>
                ${sortOrderHtml}
            </div>
            ${downloadedInfoHtml}
            <div class="saved-card-actions">
                <button class="action-btn action-abrir" title="Ver canciones"
                    onclick="event.stopPropagation(); openPlaylist('${p.id}')">♪ <span>Abrir</span></button>
                <button class="action-btn action-comparar" title="Comparar con mi música local"
                    onclick="event.stopPropagation(); comparePlaylist('${escapeHtml(p.url)}')">⇄</button>
                <button class="action-btn action-refrescar" title="Volver a descargar"
                    onclick="event.stopPropagation(); refreshPlaylist('${p.id}', this)">↻</button>
                <button class="action-btn action-copiar" title="Copiar enlace"
                    onclick="event.stopPropagation(); copyLink('${escapeHtml(p.url)}', this)">⧉</button>
                <button class="action-btn action-editar" title="Renombrar"
                    onclick="event.stopPropagation(); renamePlaylist('${p.id}', '${escapeHtml(p.name).replace(/'/g, "\\'")}')">✎</button>
                <button class="action-btn action-eliminar" title="Eliminar de favoritos"
                    onclick="event.stopPropagation(); deletePlaylist('${p.id}', '${escapeHtml(p.name).replace(/'/g, "\\'")}')">🗑</button>
            </div>
        `;

        // Click en la card (no en botones) abre la playlist
        card.addEventListener('click', () => openPlaylist(p.id));
        savedList.appendChild(card);
    });
}

// v3.17: asignar orden personalizado a una playlist
async function setSortOrder(playlistId, sortOrder) {
    try {
        await postJSON(`/api/saved-playlist/${playlistId}/sort-order`, {
            sort_order: parseInt(sortOrder, 10) || 0,
        });
        // Recargar para que se reordene visualmente
        loadSavedPlaylists();
    } catch (e) {
        showToast('Error al asignar orden: ' + e.message, 'error');
    }
}
window.setSortOrder = setSortOrder;

// ------------------------------------------------------------------
// Guardar nueva playlist desde URL
// ------------------------------------------------------------------
async function saveNewPlaylist() {
    const url = newPlaylistUrl.value.trim();
    if (!url) {
        showToast('Pega un enlace primero.', 'error');
        return;
    }
    btnSavePlaylist.disabled = true;
    btnSavePlaylist.textContent = 'Descargando y guardando...';
    try {
        const data = await postJSON('/api/save-playlist', { url });
        if (data.saved) {
            newPlaylistUrl.value = '';
            loadSavedPlaylists();
            // Marcar flag para que Mi Musica re-escanee al volver
            // (asi se actualizan las columnas de playlist en cada cancion)
            sessionStorage.setItem('playlists_changed', '1');
            if (data.warning) {
                showToast(`Playlist guardada (${data.saved.track_count} canciones). Nota: ${data.warning}`, '', 8000);
            } else {
                showToast(`Playlist guardada: "${data.saved.name}" (${data.saved.track_count} canciones)`, 'success');
            }
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        btnSavePlaylist.disabled = false;
        btnSavePlaylist.textContent = 'Guardar playlist';
    }
}

// ------------------------------------------------------------------
// Abrir detalle de playlist (cargar en compare)
// ------------------------------------------------------------------
function openPlaylist(id) {
    // v3.17: NO recargar la página. Llamar directamente a showPlaylistDetail
    // que ya hace el fetch de la playlist y abre el modal.
    // Antes se hacia window.location.href = '/saved?open=...' que recargaba todo.
    showPlaylistDetail(id);
}

async function showPlaylistDetail(id) {
    try {
        const p = await getJSON(`/api/saved-playlist/${id}`);
        // Modal con la lista completa de canciones
        let html = `<div class="modal" id="detail-modal">
            <div class="modal-content modal-large">
                <div class="modal-header">
                    <h2>${escapeHtml(p.name)}</h2>
                    <button class="modal-close" onclick="document.getElementById('detail-modal').remove()">✕</button>
                </div>
                <div class="modal-body">
                    <p style="color:var(--text-secondary); margin-bottom:12px;">
                        ${escapeHtml(p.uploader || '')} • ${p.track_count} canciones •
                        ${p.platform === 'youtube' ? 'YouTube Music' : 'Spotify'} •
                        <a href="${escapeHtml(p.url)}" target="_blank" style="color:var(--accent);">Abrir original ↗</a>
                    </p>
                    <p id="sp-detail-downloaded-info" style="margin-bottom:12px; font-size:13px; color:var(--text-secondary); display:none;">
                        <span style="color:var(--accent); font-weight:600;" id="sp-detail-downloaded-count">0</span>
                        <span> descargadas de ${p.track_count}</span>
                        <span style="display:inline-block; width:120px; height:6px; background:var(--bg-elevated); border-radius:3px; margin-left:8px; vertical-align:middle; overflow:hidden;">
                            <span id="sp-detail-downloaded-bar" style="display:block; height:100%; background:var(--accent); width:0%; transition: width 0.4s ease;"></span>
                        </span>
                    </p>
                    <table class="music-table">
                        <thead><tr>
                            <th style="width:4%; text-align:center;">#</th>
                            <th style="width:40%; text-align:left;">Título</th>
                            <th style="width:18%; text-align:left;">Artista</th>
                            <th style="width:18%; text-align:center;" title="Indica si la canción está en tu biblioteca local (Mi Música)">¿En Mi Música?</th>
                            <th style="width:10%; text-align:center;">Duración</th>
                            <th style="width:10%; text-align:center;">Ir a canción</th>
                        </tr></thead>
                        <tbody id="detail-modal-tbody">
                            <tr><td colspan="6" style="text-align:center; padding:16px; color:var(--text-muted);">
                                Cargando...
                            </td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', html);

        // v3.17: renderizar las filas después de construir el índice local
        // (reutiliza _localTitleIndex de local.js si está disponible)
        renderDetailModalRows(p);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// v3.17: renderiza las filas del modal de detalle de saved_playlists
// con la columna "¿En Mi Música?" en vez de "Álbum".
async function renderDetailModalRows(p) {
    const tbody = document.getElementById('detail-modal-tbody');
    if (!tbody) return;

    // v3.17: construir índice local (propio de saved_playlists.js)
    // para que funcione incluso cuando local.js no está cargado
    // (caso de la página /saved que no incluye local.js)
    try {
        await _spBuildLocalTitleIndex();
    } catch (e) {
        // Si falla, continuar sin índice (mostrará — neutral)
    }

    tbody.innerHTML = '';
    p.tracks.forEach((t, i) => {
        // Icono de "Ir a canción" con color según plataforma
        let link = '—';
        if (t.url) {
            const isYoutube = p.platform === 'youtube';
            const icon = isYoutube ? '▶' : '♫';
            const color = isYoutube ? '#ff0000' : '#1db954';
            const tooltip = isYoutube ? 'Abrir en YouTube Music' : 'Abrir en Spotify';
            link = `<a href="${escapeHtml(t.url)}" target="_blank" rel="noopener" title="${tooltip}" class="track-link" style="color: ${color}; text-decoration: none; font-size: 16px; font-weight: bold;">${icon}</a>`;
        }

        // v3.17: determinar si está en Mi Música usando el índice propio
        let localBadge = '<span style="color:var(--text-muted); font-size:11px;">—</span>';
        if (_spLocalTitleIndex !== null) {
            const tNorm = _spNormalizeTitle(t.title || '');
            const isInLocal = _spLocalTitleIndex.has(tNorm);
            localBadge = isInLocal
                ? '<span style="color:var(--accent); font-size:16px;" title="Sí está en tu biblioteca local">✓</span>'
                : '<span style="color:var(--danger); font-size:16px;" title="No está en tu biblioteca local">✗</span>';
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="text-align:center;">${i + 1}</td>
            <td style="text-align:left;"><strong>${escapeHtml(t.title)}</strong></td>
            <td style="text-align:left;">${escapeHtml(t.artist)}</td>
            <td style="text-align:center; font-size:14px;">${localBadge}</td>
            <td style="text-align:center;">${formatDuration(t.duration)}</td>
            <td style="text-align:center;">${link}</td>
        `;
        tbody.appendChild(tr);
    });

    // v3.17: actualizar contador de descargadas
    _spUpdateDownloadedCount(p.tracks || [], p.track_count);
}

// v3.17: cuenta cuántas canciones de la playlist están en Mi Música
// y actualiza el contador + barra de progreso del modal.
function _spUpdateDownloadedCount(tracks, totalCount) {
    const countEl = document.getElementById('sp-detail-downloaded-count');
    const infoEl = document.getElementById('sp-detail-downloaded-info');
    const barEl = document.getElementById('sp-detail-downloaded-bar');
    if (!countEl || !infoEl) return;

    // Si no hay índice local, no mostrar el contador
    if (_spLocalTitleIndex === null) {
        infoEl.style.display = 'none';
        return;
    }

    let downloaded = 0;
    for (const t of tracks) {
        const tNorm = _spNormalizeTitle(t.title || '');
        if (_spLocalTitleIndex.has(tNorm)) downloaded++;
    }
    countEl.textContent = downloaded;
    infoEl.style.display = 'block';
    // Barra de progreso
    if (barEl) {
        const pct = totalCount > 0 ? Math.round((downloaded / totalCount) * 100) : 0;
        setTimeout(() => { barEl.style.width = pct + '%'; }, 50);
    }
    // Color del count
    if (downloaded === totalCount) {
        countEl.style.color = 'var(--accent)';
    } else if (downloaded === 0) {
        countEl.style.color = 'var(--danger)';
    } else {
        countEl.style.color = 'var(--warning)';
    }
}

// ------------------------------------------------------------------
// Comparar playlist con musica local
// ------------------------------------------------------------------
function comparePlaylist(url) {
    // Redirige a la pestana Compare con la URL precargada
    window.location.href = `/compare?url=${encodeURIComponent(url)}`;
}

// ------------------------------------------------------------------
// Copiar enlace al portapapeles
// ------------------------------------------------------------------
async function copyLink(url, btn) {
    try {
        await navigator.clipboard.writeText(url);
        // Feedback visual
        const originalText = btn.innerHTML;
        btn.innerHTML = '✓';
        btn.classList.add('copied');
        showToast('Enlace copiado al portapapeles.', 'success');
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.classList.remove('copied');
        }, 1500);
    } catch (e) {
        // Fallback: selecciona el texto en un input temporal
        const tmp = document.createElement('input');
        tmp.value = url;
        document.body.appendChild(tmp);
        tmp.select();
        try {
            document.execCommand('copy');
            showToast('Enlace copiado.', 'success');
        } catch (err) {
            showToast('No se pudo copiar. URL: ' + url, 'error', 5000);
        }
        document.body.removeChild(tmp);
    }
}

// ------------------------------------------------------------------
// Refrescar playlist
// ------------------------------------------------------------------
async function refreshPlaylist(id, btn) {
    btn.disabled = true;
    btn.textContent = '...';
    try {
        const data = await postJSON(`/api/saved-playlist/${id}/refresh`, {});
        if (data.saved) {
            showToast(`Refrescada: ${data.saved.track_count} canciones`, 'success');
            loadSavedPlaylists();
            sessionStorage.setItem('playlists_changed', '1');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '↻';
    }
}

// ------------------------------------------------------------------
// Renombrar playlist
// ------------------------------------------------------------------
async function renamePlaylist(id, currentName) {
    const newName = prompt('Nuevo nombre para la playlist:', currentName);
    if (!newName || newName === currentName) return;
    try {
        await postJSON(`/api/saved-playlist/${id}/rename`, { name: newName });
        showToast('Renombrada.', 'success');
        loadSavedPlaylists();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Eliminar playlist
// ------------------------------------------------------------------
async function deletePlaylist(id, name) {
    if (!confirm(`¿Eliminar "${name}" de tus playlists guardadas?\nEsto no borra ningun archivo local, solo el acceso guardado.`)) return;
    try {
        await postJSON(`/api/saved-playlist/${id}/delete`, {});
        showToast('Playlist eliminada.', 'success');
        loadSavedPlaylists();
        sessionStorage.setItem('playlists_changed', '1');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Si la URL tiene ?open=ID, abrir el detalle al cargar
// ------------------------------------------------------------------
window.addEventListener('load', () => {
    const params = new URLSearchParams(window.location.search);
    const openId = params.get('open');
    if (openId) {
        showPlaylistDetail(openId);
        // Limpiar query string
        window.history.replaceState({}, '', '/saved');
    }
});
