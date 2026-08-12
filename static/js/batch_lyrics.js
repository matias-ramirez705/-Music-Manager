/* ============================================
   batch_lyrics.js - Sub-pestaña "Letras" (v2.5)
   ============================================
   Una sola tabla con columnas:
   #, Nombre, Artista, Duracion, Letra, Ver letra, Reproducir, Buscar letra
*/

let allLyricsData = [];

document.addEventListener('DOMContentLoaded', () => {
    const btnCheck = document.getElementById('btn-ly-check');
    const btnDownload = document.getElementById('btn-ly-download');
    if (btnCheck) btnCheck.addEventListener('click', checkLyrics);
    if (btnDownload) btnDownload.addEventListener('click', downloadMissing);
});

async function checkLyrics() {
    const btn = document.getElementById('btn-ly-check');
    const resultsDiv = document.getElementById('ly-results');
    if (btn) { btn.disabled = true; btn.textContent = 'Analizando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<div class="spinner"></div><p style="text-align:center;color:var(--text-secondary);">Analizando letras...</p>';

    try {
        const data = await postJSON('/api/batch/lyrics-status', {});
        if (data.error) {
            if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(data.error)}</p>`;
            return;
        }
        document.getElementById('ly-total').textContent = data.total;
        document.getElementById('ly-has').textContent = data.has_count;
        document.getElementById('ly-missing').textContent = data.missing_count;
        document.getElementById('lyrics-stats').classList.remove('hidden');
        document.getElementById('btn-ly-download').disabled = data.missing_count === 0;

        allLyricsData = data.all || [];
        renderLyricsTable('all');
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔍 Analizar letras'; }
    }
}

function renderLyricsTable(filter) {
    const resultsDiv = document.getElementById('ly-results');
    if (!resultsDiv) return;

    let items = allLyricsData;
    if (filter === 'has') items = allLyricsData.filter(f => f.has_lyrics);
    else if (filter === 'missing') items = allLyricsData.filter(f => !f.has_lyrics);

    if (items.length === 0) {
        resultsDiv.innerHTML = '<p class="empty-hint">No hay archivos para mostrar.</p>';
        return;
    }

    let html = `
        <div class="filter-bar" style="margin-bottom:12px;">
            <select id="ly-filter" class="filter-select" onchange="renderLyricsTable(this.value)">
                <option value="all" ${filter === 'all' ? 'selected' : ''}>Todas (${allLyricsData.length})</option>
                <option value="has" ${filter === 'has' ? 'selected' : ''}>Con letra (${allLyricsData.filter(f => f.has_lyrics).length})</option>
                <option value="missing" ${filter === 'missing' ? 'selected' : ''}>Sin letra (${allLyricsData.filter(f => !f.has_lyrics).length})</option>
            </select>
            <input type="text" id="ly-search" class="search-input" placeholder="Buscar..." oninput="filterLyricsTable('${filter}')">
        </div>
        <div class="table-container">
        <table class="music-table">
            <thead><tr>
                <th style="width:3%;">#</th>
                <th style="width:20%;">Nombre</th>
                <th style="width:15%;">Artista</th>
                <th style="width:6%;">Formato</th>
                <th style="width:7%;">Duracion</th>
                <th style="width:6%;">Letra</th>
                <th style="width:7%;">Ver letra</th>
                <th style="width:7%;">Reproducir</th>
                <th style="width:7%;">Buscar</th>
            </tr></thead>
            <tbody id="ly-tbody"></tbody>
        </table>
        </div>
    `;
    resultsDiv.innerHTML = html;
    renderLyricsRows(items, filter);
}

function filterLyricsTable(filter) {
    const query = (document.getElementById('ly-search')?.value || '').toLowerCase().trim();
    let items = allLyricsData;
    if (filter === 'has') items = items.filter(f => f.has_lyrics);
    else if (filter === 'missing') items = items.filter(f => !f.has_lyrics);
    if (query) {
        items = items.filter(f => (f.name + ' ' + f.artist).toLowerCase().includes(query));
    }
    renderLyricsRows(items, filter);
}

function renderLyricsRows(items, filter) {
    const tbody = document.getElementById('ly-tbody');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:16px;color:var(--text-muted);">Sin resultados.</td></tr>';
        return;
    }

    items.forEach((f, idx) => {
        const tr = document.createElement('tr');

        const letraHtml = f.has_lyrics
            ? '<span class="match-status status-matched">✓ Si</span>'
            : '<span class="match-status status-missing">✗ No</span>';

        const verHtml = f.has_lyrics
            ? `<button class="btn btn-secondary btn-sm btn-view-ly" data-idx="${idx}">📖</button>`
            : '—';

        const buscarHtml = `<button class="btn btn-secondary btn-sm btn-search-ly" data-idx="${idx}">🔍</button>`;
        const fmtHtml = `<span class="format-badge ${escapeHtml((f.ext||'').toLowerCase())}">${escapeHtml((f.ext||'—').toUpperCase())}</span>`;

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(f.name)}</strong></td>
            <td>${escapeHtml(f.artist || '—')}</td>
            <td style="text-align:center;">${fmtHtml}</td>
            <td style="text-align:center;">${escapeHtml(f.duration_str || '0:00')}</td>
            <td style="text-align:center;">${letraHtml}</td>
            <td style="text-align:center;">${verHtml}</td>
            <td style="text-align:center;"></td>
            <td style="text-align:center;">${buscarHtml}</td>
        `;

        // Boton reproducir (DOM API)
        const playCell = tr.children[7];
        const playBtn = document.createElement('button');
        playBtn.className = 'play-btn';
        playBtn.title = 'Reproducir';
        playBtn.textContent = '▶';
        playBtn.dataset.path = f.path;
        playBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            playFile(f.path, f.name, f.artist || '');
        });
        playCell.appendChild(playBtn);

        tbody.appendChild(tr);
    });

    // Vincular botones ver y buscar
    tbody.querySelectorAll('.btn-view-ly').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.idx);
            const f = items[idx];
            viewLyrics(f.path, f.name, f.artist || '');
        });
    });
    tbody.querySelectorAll('.btn-search-ly').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.idx);
            const f = items[idx];
            searchLyricsModal(f.path, f.name, f.artist || '', f.duration || 0);
        });
    });
}

// ------------------------------------------------------------------
// Modal: Ver letra + reproductor + borrar
// ------------------------------------------------------------------
async function viewLyrics(filePath, name, artist) {
    const modalId = 'lyrics-view-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:700px;">
            <div class="modal-header">
                <h2>📖 ${escapeHtml(name)}</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body">
                <div class="lyrics-player-bar">
                    <button id="lyrics-play-btn" class="btn btn-primary btn-sm">▶ Reproducir</button>
                    <span style="color:var(--text-muted);font-size:12px;margin-left:8px;">${escapeHtml(artist)}</span>
                    <button id="lyrics-delete-btn" class="btn btn-ghost btn-sm" style="margin-left:auto;" title="Borrar letra">🗑 Borrar</button>
                </div>
                <div class="lyrics-text" id="lyrics-text-content"><p class="empty-hint">Cargando...</p></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    const playBtn = document.getElementById('lyrics-play-btn');

    const closeModal = () => { modal.remove(); };
    modal.querySelector('.modal-close').addEventListener('click', closeModal);

    // Usar el reproductor principal (playFile) en vez de crear Audio separado
    playBtn.addEventListener('click', () => {
        playFile(filePath, name, artist);
        playBtn.textContent = '▶ Reproducir (barra inferior)';
        playBtn.disabled = true;
        setTimeout(() => { playBtn.disabled = false; }, 2000);
    });

    // Borrar letra
    document.getElementById('lyrics-delete-btn').addEventListener('click', async () => {
        if (!confirm('¿Borrar la letra de esta canción?')) return;
        try {
            const data = await postJSON('/api/lyrics/remove', { path: filePath });
            showToast(data.message, 'success');
            closeModal();
            checkLyrics(); // Recargar
        } catch (e) { showToast('Error: ' + e.message, 'error'); }
    });

    // Cargar letra
    try {
        const data = await postJSON('/api/lyrics/read', { path: filePath });
        const content = document.getElementById('lyrics-text-content');
        if (data.has_lyrics && data.lyrics) {
            const text = data.lyrics;
            if (text.includes('[') && text.match(/\[\d{2}:\d{2}/)) {
                content.innerHTML = formatLrcLyrics(text);
            } else {
                content.innerHTML = `<pre class="lyrics-plain">${escapeHtml(text)}</pre>`;
            }
        } else {
            content.innerHTML = '<p class="empty-hint">Sin letra.</p>';
        }
    } catch (e) {
        document.getElementById('lyrics-text-content').innerHTML = `<p style="color:var(--danger);">${escapeHtml(e.message)}</p>`;
    }
}

// ------------------------------------------------------------------
// Modal: Buscar letra con preview + reproducir
// ------------------------------------------------------------------
function searchLyricsModal(filePath, name, artist, duration) {
    const modalId = 'lyrics-search-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:700px;">
            <div class="modal-header">
                <h2>🔍 Buscar letra</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body">
                <div class="lyrics-player-bar">
                    <button id="ly-search-play" class="btn btn-primary btn-sm">▶ Reproducir</button>
                    <span style="color:var(--text-muted);font-size:12px;margin-left:8px;">${escapeHtml(name)} — ${escapeHtml(artist)}</span>
                </div>
                <div class="form-group"><label>Titulo</label><input type="text" id="ly-search-title" class="form-input" value="${escapeHtml(name)}"></div>
                <div class="form-group"><label>Artista</label><input type="text" id="ly-search-artist" class="form-input" value="${escapeHtml(artist)}"></div>
                <button id="btn-ly-do-search" class="btn btn-primary">🔍 Buscar en lrclib.net</button>
                <div id="ly-search-results" style="margin-top:16px;"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    const closeModal = () => { modal.remove(); };
    modal.querySelector('.modal-close').addEventListener('click', closeModal);

    // Usar el reproductor principal
    document.getElementById('ly-search-play').addEventListener('click', () => {
        playFile(filePath, name, artist);
        const btn = document.getElementById('ly-search-play');
        btn.textContent = '▶ En barra inferior';
        btn.disabled = true;
        setTimeout(() => { btn.disabled = false; btn.textContent = '▶ Reproducir'; }, 2000);
    });

    document.getElementById('btn-ly-do-search').addEventListener('click', () => doLyricsSearch(filePath, duration));
    document.getElementById('ly-search-title').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doLyricsSearch(filePath, duration);
    });
}

async function doLyricsSearch(filePath, duration) {
    const title = document.getElementById('ly-search-title').value.trim();
    const artist = document.getElementById('ly-search-artist').value.trim();
    const resultsDiv = document.getElementById('ly-search-results');
    const btn = document.getElementById('btn-ly-do-search');
    if (!title) { showToast('Escribe un titulo.', 'error'); return; }
    if (btn) { btn.disabled = true; btn.textContent = 'Buscando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<p class="empty-hint">Buscando...</p>';

    try {
        const data = await postJSON('/api/lyrics/search', { title, artist, duration });
        if (data.error) { if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(data.error)}</p>`; return; }
        if (!data.found || !data.lyrics) { if (resultsDiv) resultsDiv.innerHTML = '<p class="empty-hint">No se encontro.</p>'; return; }

        const lyrics = data.lyrics;
        const plainText = lyrics.plain || '(sin letra plana)';
        const syncedText = lyrics.synced || '';
        const source = lyrics.track_name ? `${escapeHtml(lyrics.track_name)} - ${escapeHtml(lyrics.artist_name)}` : '';

        let html = `<div style="margin-bottom:12px;"><strong style="color:var(--accent);">Encontrada</strong>${source ? ' — ' + source : ''}</div>`;
        if (syncedText) {
            html += '<details style="margin-bottom:8px;"><summary style="cursor:pointer;color:var(--text-secondary);font-size:12px;">Letra sincronizada (LRC)</summary>';
            html += `<pre class="lyrics-plain" style="max-height:200px;">${escapeHtml(syncedText)}</pre></details>`;
        }
        html += '<details open style="margin-bottom:12px;"><summary style="cursor:pointer;color:var(--text-secondary);font-size:12px;">Letra plana</summary>';
        html += `<pre class="lyrics-plain" style="max-height:250px;">${escapeHtml(plainText)}</pre></details>`;
        html += `<div style="display:flex;gap:8px;">
            <button id="btn-ly-save-plain" class="btn btn-primary">💾 Guardar</button>
            <button class="btn btn-ghost" onclick="document.getElementById('lyrics-search-modal').remove()">Cancelar</button>
        </div>`;
        if (resultsDiv) resultsDiv.innerHTML = html;

        const saveBtn = document.getElementById('btn-ly-save-plain');
        if (saveBtn) saveBtn.addEventListener('click', () => saveLyricsToFile(filePath, plainText, 'lyrics-search-modal'));
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔍 Buscar en lrclib.net'; }
    }
}

async function saveLyricsToFile(filePath, lyrics, modalId) {
    try {
        const data = await postJSON('/api/lyrics/save', { path: filePath, lyrics });
        if (data.success) {
            showToast('Letra guardada.', 'success');
            const modal = document.getElementById(modalId);
            if (modal) { modal.remove(); }
            checkLyrics();
        } else { showToast(data.message || 'Error', 'error'); }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

function formatLrcLyrics(text) {
    const lines = text.split('\n');
    let html = '<div class="lyrics-synced">';
    lines.forEach(line => {
        const clean = line.replace(/\[\d{2}:\d{2}\.\d{2,3}\]/g, '').trim();
        html += `<div class="lyrics-line">${clean ? escapeHtml(clean) : '&nbsp;'}</div>`;
    });
    html += '</div>';
    return html;
}

async function downloadMissing() {
    const btn = document.getElementById('btn-ly-download');
    const resultsDiv = document.getElementById('ly-results');
    if (btn) { btn.disabled = true; btn.textContent = 'Descargando...'; }
    if (resultsDiv) resultsDiv.innerHTML = '<div class="spinner"></div><p style="text-align:center;color:var(--text-secondary);">Descargando...</p>';
    try {
        const data = await postJSON('/api/batch/download-lyrics', {});
        let html = `<div class="result-summary"><div class="result-stat success"><span class="result-num">${data.success_count}</span><span class="result-label">OK</span></div><div class="result-stat skipped"><span class="result-num">${data.not_found_count}</span><span class="result-label">No encontradas</span></div><div class="result-stat error"><span class="result-num">${data.error_count}</span><span class="result-label">Errores</span></div></div>`;
        if (resultsDiv) resultsDiv.innerHTML = html;
        showToast(`Descargadas ${data.success_count} letras.`, 'success');
    } catch (e) {
        if (resultsDiv) resultsDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(e.message)}</p>`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '⬇ Descargar faltantes'; }
    }
}
