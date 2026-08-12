/* ============================================
   batch_artwork.js - Sub-pestaña "Carátulas" (v2.5)
   ============================================
   Una sola tabla con columnas:
   #, Nombre, Artista, Carátula, Ext, Resolución, Peso, Buscar
*/

let allArtworkData = [];

document.addEventListener('DOMContentLoaded', () => {
    const btnCheck = document.getElementById('btn-aw-check');
    const btnDownload = document.getElementById('btn-aw-download');
    const btnResize = document.getElementById('btn-aw-resize');
    if (btnCheck) btnCheck.addEventListener('click', checkArtwork);
    if (btnDownload) btnDownload.addEventListener('click', downloadMissing);
    if (btnResize) btnResize.addEventListener('click', resizeAll);
});

async function checkArtwork() {
    const btn = document.getElementById('btn-aw-check');
    const resultsDiv = document.getElementById('aw-results');
    if (btn) { btn.disabled = true; btn.textContent = 'Analizando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<div class="spinner"></div><p style="text-align:center;color:var(--text-secondary);">Analizando...</p>';

    try {
        const data = await postJSON('/api/batch/artwork-status', {});
        if (data.error) {
            if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(data.error)}</p>`;
            return;
        }
        document.getElementById('aw-total').textContent = data.total;
        document.getElementById('aw-has').textContent = data.has_count;
        document.getElementById('aw-missing').textContent = data.missing_count;
        document.getElementById('artwork-stats').classList.remove('hidden');
        document.getElementById('btn-aw-download').disabled = data.missing_count === 0;
        document.getElementById('btn-aw-resize').disabled = data.has_count === 0;

        allArtworkData = data.all || [];
        renderArtworkTable('all');
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔍 Analizar carátulas'; }
    }
}

function renderArtworkTable(filter) {
    const resultsDiv = document.getElementById('aw-results');
    if (!resultsDiv) return;

    let items = allArtworkData;
    if (filter === 'has') items = allArtworkData.filter(f => f.has_artwork);
    else if (filter === 'missing') items = allArtworkData.filter(f => !f.has_artwork);

    // Collectar extensiones unicas para el filtro
    const exts = [...new Set(allArtworkData.filter(f => f.has_artwork).map(f => f.artwork_ext))].filter(e => e && e !== '—');

    let html = `
        <div class="filter-bar" style="margin-bottom:12px;">
            <select id="aw-filter" class="filter-select" onchange="renderArtworkTable(this.value)">
                <option value="all" ${filter === 'all' ? 'selected' : ''}>Todas (${allArtworkData.length})</option>
                <option value="has" ${filter === 'has' ? 'selected' : ''}>Con carátula (${allArtworkData.filter(f => f.has_artwork).length})</option>
                <option value="missing" ${filter === 'missing' ? 'selected' : ''}>Sin carátula (${allArtworkData.filter(f => !f.has_artwork).length})</option>
            </select>
            <select id="aw-filter-ext" class="filter-select" onchange="filterArtworkTable('${filter}')">
                <option value="">Todas las extensiones</option>
                ${exts.map(e => `<option value="${escapeHtml(e)}">${escapeHtml(e)}</option>`).join('')}
            </select>
            <input type="text" id="aw-search" class="search-input" placeholder="Buscar..." oninput="filterArtworkTable('${filter}')">
        </div>
        <div class="table-container">
        <table class="music-table">
            <thead><tr>
                <th style="width:3%;">#</th>
                <th style="width:18%;">Nombre</th>
                <th style="width:13%;">Artista</th>
                <th style="width:6%;">Formato</th>
                <th style="width:7%;">Carátula</th>
                <th style="width:6%;">Ext</th>
                <th style="width:9%;">Resolución</th>
                <th style="width:7%;">Peso</th>
                <th style="width:6%;">Buscar</th>
            </tr></thead>
            <tbody id="aw-tbody"></tbody>
        </table>
        </div>
    `;
    resultsDiv.innerHTML = html;
    filterArtworkTable(filter);
}

function filterArtworkTable(filter) {
    const query = (document.getElementById('aw-search')?.value || '').toLowerCase().trim();
    const extFilter = document.getElementById('aw-filter-ext')?.value || '';
    let items = allArtworkData;
    if (filter === 'has') items = items.filter(f => f.has_artwork);
    else if (filter === 'missing') items = items.filter(f => !f.has_artwork);
    if (extFilter) items = items.filter(f => f.artwork_ext === extFilter);
    if (query) items = items.filter(f => (f.name + ' ' + f.artist).toLowerCase().includes(query));
    renderArtworkRows(items);
}

function renderArtworkRows(items) {
    const tbody = document.getElementById('aw-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:16px;color:var(--text-muted);">Sin resultados.</td></tr>';
        return;
    }
    items.forEach((f, idx) => {
        const tr = document.createElement('tr');

        const caratulaHtml = f.has_artwork
            ? '<span class="match-status status-matched">✓</span>'
            : '<span class="match-status status-missing">✗</span>';

        const extHtml = f.has_artwork ? `<span class="format-badge">${escapeHtml(f.artwork_ext || '—')}</span>` : '—';
        const resHtml = f.has_artwork ? escapeHtml(f.artwork_dimensions || '—') : '—';
        const pesoHtml = f.has_artwork ? `${escapeHtml(String(f.artwork_size_kb))} KB` : '—';
        const fmtHtml = `<span class="format-badge ${escapeHtml((f.ext||'').toLowerCase())}">${escapeHtml((f.ext||'—').toUpperCase())}</span>`;

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(f.name)}</strong></td>
            <td>${escapeHtml(f.artist || '—')}</td>
            <td style="text-align:center;">${fmtHtml}</td>
            <td style="text-align:center;">${caratulaHtml}</td>
            <td style="text-align:center;">${extHtml}</td>
            <td style="text-align:center;font-family:var(--font-mono);font-size:11px;">${resHtml}</td>
            <td style="text-align:center;font-size:11px;">${pesoHtml}</td>
            <td style="text-align:center;"></td>
        `;

        // Celda caratula: clickeable para ver (DOM API, no onclick inline)
        if (f.has_artwork) {
            const caratulaCell = tr.children[4];
            caratulaCell.style.cursor = 'pointer';
            caratulaCell.addEventListener('click', () => viewArtwork(f.path));
        }

        // Boton buscar (DOM API)
        const searchCell = tr.children[8];
        const searchBtn = document.createElement('button');
        searchBtn.className = 'btn btn-secondary btn-sm';
        searchBtn.title = 'Buscar carátula';
        searchBtn.textContent = '🔍';
        searchBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openArtworkSearchModal(encodeURIComponent(f.path), f.name, f.artist || '');
        });
        searchCell.appendChild(searchBtn);

        tbody.appendChild(tr);
    });
}

// ------------------------------------------------------------------
// Ver caratula
// ------------------------------------------------------------------
function viewArtwork(filePath) {
    const modalId = 'artwork-view-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:400px;">
            <div class="modal-header">
                <h2>🖼 Carátula</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body" style="text-align:center;">
                <img src="/api/artwork?path=${encodeURIComponent(filePath)}&_t=${Date.now()}"
                    style="max-width:100%;border-radius:8px;" alt="Carátula">
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
}

// ------------------------------------------------------------------
// Modal: Buscar caratula manual
// ------------------------------------------------------------------
function openArtworkSearchModal(encodedPath, name, artist) {
    const path = decodeURIComponent(encodedPath);
    const modalId = 'artwork-search-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:600px;">
            <div class="modal-header">
                <h2>🔍 Buscar carátula</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body">
                <p style="color:var(--text-muted);font-size:11px;margin-bottom:8px;">Edita si es necesario.</p>
                <div class="form-group"><label>Título</label><input type="text" id="aw-search-title" class="form-input" value="${escapeHtml(name)}"></div>
                <div class="form-group"><label>Artista</label><input type="text" id="aw-search-artist" class="form-input" value="${escapeHtml(artist)}"></div>
                <div class="form-group"><label>Buscar en:</label>
                    <select id="aw-search-source" class="filter-select">
                        <option value="itunes" selected>iTunes</option>
                        <option value="musicbrainz">MusicBrainz</option>
                        <option value="lastfm">Last.fm</option>
                        <option value="all">Todas</option>
                    </select>
                </div>
                <button id="btn-aw-do-search" class="btn btn-primary">🔍 Buscar</button>
                <div id="aw-search-results" style="margin-top:16px;"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
    document.getElementById('btn-aw-do-search').addEventListener('click', () => doArtworkSearch(path));
    document.getElementById('aw-search-title').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doArtworkSearch(path);
    });
}

async function doArtworkSearch(filePath) {
    const title = document.getElementById('aw-search-title').value.trim();
    const artist = document.getElementById('aw-search-artist').value.trim();
    const source = document.getElementById('aw-search-source').value;
    const resultsDiv = document.getElementById('aw-search-results');
    const btn = document.getElementById('btn-aw-do-search');
    if (!title) { showToast('Escribe un título.', 'error'); return; }
    if (btn) { btn.disabled = true; btn.textContent = 'Buscando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<p class="empty-hint">Buscando...</p>';

    try {
        const data = await postJSON('/api/artwork/search', { title, artist, source });
        if (data.error) { if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(data.error)}</p>`; return; }
        if (data.message || !data.results || data.results.length === 0) {
            if (resultsDiv) resultsDiv.innerHTML = `<p class="empty-hint">${escapeHtml(data.message || 'Sin resultados.')}</p>`;
            return;
        }
        let html = `<p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">${data.results.length} resultados — clic para guardar</p>`;
        data.results.forEach((r, idx) => {
            const thumb = r.artwork_url
                ? `<img src="${escapeHtml(r.artwork_url)}" style="width:56px;height:56px;border-radius:4px;object-fit:cover;" onerror="this.style.display='none'">`
                : '<div style="width:56px;height:56px;background:var(--bg-card);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--text-muted);">♪</div>';
            html += `<div class="search-result-item" data-idx="${idx}" style="display:flex;gap:10px;align-items:center;padding:8px;background:var(--bg-card);border-radius:4px;margin-bottom:6px;cursor:pointer;border:1px solid transparent;">
                ${thumb}
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;font-size:13px;">${escapeHtml(r.title)}</div>
                    <div style="font-size:11px;color:var(--text-secondary);">${escapeHtml(r.artist)} ${r.album ? '• ' + escapeHtml(r.album) : ''}</div>
                </div>
                <button class="btn btn-primary btn-sm btn-apply-artwork" data-idx="${idx}">⬇ Guardar</button>
            </div>`;
        });
        if (resultsDiv) resultsDiv.innerHTML = html;

        window._artworkSearchResults = data.results;
        window._artworkSearchFilePath = filePath;

        document.querySelectorAll('.btn-apply-artwork').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.idx);
                const r = window._artworkSearchResults[idx];
                if (!r || !r.artwork_url) return;
                btn.disabled = true; btn.textContent = 'Guardando...';
                try {
                    const data = await postJSON('/api/artwork/save', { path: window._artworkSearchFilePath, image_url: r.artwork_url });
                    if (data.success) {
                        btn.textContent = '✓'; showToast('Carátula guardada.', 'success');
                        // Recargar tabla
                        const modal = document.getElementById('artwork-search-modal');
                        if (modal) modal.remove();
                        checkArtwork();
                    } else { btn.textContent = '⬇'; btn.disabled = false; showToast(data.message || 'Error', 'error'); }
                } catch (err) { btn.textContent = '⬇'; btn.disabled = false; showToast('Error: ' + err.message, 'error'); }
            });
        });
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔍 Buscar'; }
    }
}

async function downloadMissing() {
    const btn = document.getElementById('btn-aw-download');
    const resultsDiv = document.getElementById('aw-results');
    if (btn) { btn.disabled = true; btn.textContent = 'Descargando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<div class="spinner"></div><p style="text-align:center;color:var(--text-secondary);">Descargando...</p>';
    try {
        const data = await postJSON('/api/batch/download-artwork', {});
        let html = `<div class="result-summary"><div class="result-stat success"><span class="result-num">${data.success_count}</span><span class="result-label">OK</span></div><div class="result-stat skipped"><span class="result-num">${data.not_found_count}</span><span class="result-label">No encontradas</span></div><div class="result-stat error"><span class="result-num">${data.error_count}</span><span class="result-label">Errores</span></div></div>`;
        if (resultsDiv) resultsDiv.innerHTML = html;
        showToast(`Descargadas ${data.success_count} carátulas.`, 'success');
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '⬇ Descargar faltantes'; }
    }
}

async function resizeAll() {
    const size = document.getElementById('aw-resize-size').value;
    const fmt = document.getElementById('aw-resize-fmt').value;
    if (!confirm(`¿Redimensionar TODAS las carátulas a ${size}px (${fmt})?`)) return;
    const btn = document.getElementById('btn-aw-resize');
    const resultsDiv = document.getElementById('aw-results');
    if (btn) { btn.disabled = true; btn.textContent = 'Redimensionando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<div class="spinner"></div><p style="text-align:center;color:var(--text-secondary);">Redimensionando...</p>';
    try {
        const data = await postJSON('/api/batch/resize', { max_size: parseInt(size), fmt });
        let html = `<div class="result-summary"><div class="result-stat success"><span class="result-num">${data.success_count}</span><span class="result-label">OK</span></div><div class="result-stat skipped"><span class="result-num">${data.skipped_count}</span><span class="result-label">Saltadas</span></div><div class="result-stat error"><span class="result-num">${data.error_count}</span><span class="result-label">Errores</span></div></div>`;
        if (resultsDiv) resultsDiv.innerHTML = html;
        showToast(`Redimensionadas ${data.success_count}.`, 'success');
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '⤢ Redimensionar'; }
    }
}
