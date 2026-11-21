/*
 * static/js/m3u_hiby.js (v3.22)
 * =================================
 * Lógica de la pestaña "M3U para Hiby".
 * 2 sub-pestañas: Generar | Editar
 */

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function $(id) { return document.getElementById(id); }
function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}
async function postJSON(url, body) {
    const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
    });
    return r.json();
}

let lastGeneratedM3U = '';
let editingTracks = [];
let editingFilePath = '';

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // Sub-pestañas
    document.querySelectorAll('[data-m3u-subtab]').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const target = tab.dataset.m3uSubtab;
            document.querySelectorAll('[data-m3u-subtab]').forEach(t => t.classList.toggle('active', t === tab));
            $('m3u-subtab-generate').classList.toggle('hidden', target !== 'generate');
            $('m3u-subtab-edit').classList.toggle('hidden', target !== 'edit');
            if (target === 'edit') {
                // Cargar playlists en el selector
                loadPlaylistsForSelect();
            }
        });
    });

    // Generar
    $('btn-m3u-browse-hiby').addEventListener('click', () => browseFolder('m3u-hiby-folder'));
    $('btn-m3u-browse-save').addEventListener('click', () => browseFolder('m3u-save-folder'));
    $('btn-m3u-preview').addEventListener('click', generateM3U);
    $('btn-m3u-save').addEventListener('click', saveM3UFile);
    $('m3u-filename').addEventListener('input', updateSaveButton);
    $('m3u-save-folder').addEventListener('input', updateSaveButton);

    // Cargar playlists en el selector
    loadPlaylistsForSelect();

    // Editar
    $('btn-m3u-edit-browse').addEventListener('click', () => browseFolder('m3u-edit-folder'));
    $('btn-m3u-edit-list').addEventListener('click', listM3UFiles);
    $('btn-m3u-add-track').addEventListener('click', () => $('m3u-add-track-modal').classList.remove('hidden'));
    $('m3u-add-cancel').addEventListener('click', () => $('m3u-add-track-modal').classList.add('hidden'));
    document.querySelector('#m3u-add-track-modal .modal-close').addEventListener('click', () => $('m3u-add-track-modal').classList.add('hidden'));
    $('m3u-add-confirm').addEventListener('click', confirmAddTrack);
    $('btn-m3u-save-edit').addEventListener('click', saveEditedM3U);
    $('btn-m3u-cancel-edit').addEventListener('click', () => {
        $('m3u-editor-container').classList.add('hidden');
        editingTracks = [];
        editingFilePath = '';
    });
});

async function browseFolder(inputId) {
    try {
        const data = await getJSON('/api/browse');
        if (data.folder) $(inputId).value = data.folder;
    } catch (e) {
        if (typeof showToast === 'function') showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Sub-pestaña 1: Generar M3U
// ------------------------------------------------------------------
async function loadPlaylistsForSelect() {
    try {
        const data = await getJSON('/api/saved-playlists?sort_by=name');
        const select = $('m3u-playlist-select');
        const current = select.value;
        select.innerHTML = '<option value="">Selecciona una playlist guardada...</option>';
        (data.playlists || []).forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            const platformLabel = p.platform === 'youtube' ? 'YT Music' : 'Spotify';
            opt.textContent = `${p.name} | ${p.track_count} canciones | ${platformLabel}`;
            select.appendChild(opt);
        });
        if (current) select.value = current;
    } catch (e) {
        console.error('Error cargando playlists:', e);
    }
}

async function generateM3U() {
    const playlistId = $('m3u-playlist-select').value;
    const hibyFolder = $('m3u-hiby-folder').value.trim();
    if (!playlistId) { showToast('Selecciona una playlist.', 'error'); return; }
    if (!hibyFolder) { showToast('Indica la carpeta raíz del Hiby.', 'error'); return; }

    $('btn-m3u-preview').disabled = true;
    $('btn-m3u-preview').textContent = 'Generando...';

    try {
        const data = await postJSON('/api/m3u/preview', {
            playlist_id: playlistId,
            hiby_folder: hibyFolder,
            music_folder: 'Musica',
        });
        if (data.error) {
            showToast('Error: ' + data.error, 'error', 6000);
            return;
        }
        lastGeneratedM3U = data.m3u_content;
        // Stats
        $('m3u-total').textContent = data.total;
        $('m3u-matched').textContent = data.matched;
        $('m3u-missing').textContent = data.missing;
        $('m3u-stats').classList.remove('hidden');
        // Preview
        $('m3u-preview-content').value = data.m3u_content;
        $('m3u-preview-container').classList.remove('hidden');
        $('m3u-empty').classList.add('hidden');
        // Sugerir nombre de archivo
        const plName = $('m3u-playlist-select').options[$('m3u-playlist-select').selectedIndex].text.split(' |')[0];
        if (!$('m3u-filename').value) {
            $('m3u-filename').value = plName + '.m3u';
        }
        // Sugerir carpeta de guardado
        if (!$('m3u-save-folder').value) {
            $('m3u-save-folder').value = hibyFolder.replace(/\\$/, '') + '\\playlist_data\\';
        }
        updateSaveButton();
        // Faltantes
        renderMissingTracks(data.missing_tracks || []);
        showToast(`M3U generado: ${data.matched}/${data.total} encontradas en el Hiby.`, 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        $('btn-m3u-preview').disabled = false;
        $('btn-m3u-preview').textContent = '🔍 Generar M3U';
    }
}

function renderMissingTracks(tracks) {
    const tbody = $('m3u-missing-tbody');
    if (tracks.length === 0) {
        $('m3u-missing-container').classList.add('hidden');
        return;
    }
    $('m3u-missing-container').classList.remove('hidden');
    tbody.innerHTML = '';
    tracks.forEach((t, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td><strong>${escapeHtml(t.title)}</strong></td>
            <td>${escapeHtml(t.artist)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function updateSaveButton() {
    const has = lastGeneratedM3U && $('m3u-save-folder').value.trim() && $('m3u-filename').value.trim();
    $('btn-m3u-save').disabled = !has;
}

async function saveM3UFile() {
    const folder = $('m3u-save-folder').value.trim();
    const filename = $('m3u-filename').value.trim();
    if (!folder || !filename) { showToast('Indica carpeta y nombre de archivo.', 'error'); return; }
    if (!lastGeneratedM3U) { showToast('Genera el M3U primero.', 'error'); return; }

    try {
        const data = await postJSON('/api/m3u/save', {
            content: lastGeneratedM3U,
            folder: folder,
            filename: filename,
        });
        if (data.success) {
            showToast(`M3U guardado en: ${data.file_path}`, 'success', 5000);
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error', 6000);
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Sub-pestaña 2: Editar M3U
// ------------------------------------------------------------------
async function listM3UFiles() {
    const folder = $('m3u-edit-folder').value.trim();
    if (!folder) { showToast('Indica la carpeta de M3U.', 'error'); return; }
    try {
        const data = await postJSON('/api/m3u/list', { folder });
        if (data.error) { showToast('Error: ' + data.error, 'error'); return; }
        renderM3UList(data.files || []);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function renderM3UList(files) {
    const tbody = $('m3u-edit-tbody');
    if (files.length === 0) {
        $('m3u-edit-list-container').classList.remove('hidden');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:16px; color:var(--text-muted);">No hay archivos M3U en esa carpeta.</td></tr>';
        return;
    }
    $('m3u-edit-list-container').classList.remove('hidden');
    tbody.innerHTML = '';
    files.forEach(f => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${escapeHtml(f.filename)}</strong></td>
            <td>${f.track_count}</td>
            <td>${escapeHtml(f.modified)}</td>
            <td></td>
        `;
        const actionsCell = tr.children[3];
        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-secondary btn-sm';
        editBtn.textContent = '✎ Editar';
        editBtn.addEventListener('click', () => loadM3UForEdit(f.path));
        actionsCell.appendChild(editBtn);

        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-ghost btn-sm';
        delBtn.textContent = '🗑';
        delBtn.title = 'Eliminar';
        delBtn.style.marginLeft = '4px';
        delBtn.addEventListener('click', () => deleteM3U(f.path, f.filename));
        actionsCell.appendChild(delBtn);

        tbody.appendChild(tr);
    });
}

async function loadM3UForEdit(filePath) {
    try {
        const data = await postJSON('/api/m3u/read', { file_path: filePath });
        if (data.error) { showToast('Error: ' + data.error, 'error'); return; }
        editingTracks = data.tracks || [];
        editingFilePath = filePath;
        $('m3u-editor-title').textContent = `Editando: ${data.filename}`;
        $('m3u-editor-container').classList.remove('hidden');
        renderEditTracks();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function renderEditTracks() {
    const tbody = $('m3u-edit-tracks-tbody');
    tbody.innerHTML = '';
    if (editingTracks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:16px; color:var(--text-muted);">El M3U está vacío.</td></tr>';
        return;
    }
    editingTracks.forEach((t, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td><input type="text" value="${escapeHtml(t.path)}" style="width:100%; background:var(--bg-elevated); border:1px solid var(--border); border-radius:3px; padding:2px 4px; color:var(--text-primary); font-family:var(--font-mono); font-size:11px;" data-idx="${i}" data-field="path"></td>
            <td><input type="text" value="${escapeHtml(t.title)}" style="width:100%; background:var(--bg-elevated); border:1px solid var(--border); border-radius:3px; padding:2px 4px; color:var(--text-primary); font-size:11px;" data-idx="${i}" data-field="title"></td>
            <td><input type="text" value="${escapeHtml(t.artist)}" style="width:100%; background:var(--bg-elevated); border:1px solid var(--border); border-radius:3px; padding:2px 4px; color:var(--text-primary); font-size:11px;" data-idx="${i}" data-field="artist"></td>
            <td><button class="btn btn-ghost btn-sm" data-del-idx="${i}" title="Quitar">✕</button></td>
        `;
        tbody.appendChild(tr);
    });

    // Event listeners para inputs
    tbody.querySelectorAll('input[data-idx]').forEach(inp => {
        inp.addEventListener('change', () => {
            const idx = parseInt(inp.dataset.idx);
            const field = inp.dataset.field;
            if (editingTracks[idx]) editingTracks[idx][field] = inp.value;
        });
    });
    // Botones eliminar
    tbody.querySelectorAll('button[data-del-idx]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.delIdx);
            editingTracks.splice(idx, 1);
            renderEditTracks();
        });
    });
}

function confirmAddTrack() {
    const path = $('m3u-add-path').value.trim();
    if (!path) { showToast('La ruta es obligatoria.', 'error'); return; }
    editingTracks.push({
        path: path,
        title: $('m3u-add-title').value.trim(),
        artist: $('m3u-add-artist').value.trim(),
        duration: 0,
    });
    $('m3u-add-path').value = '';
    $('m3u-add-title').value = '';
    $('m3u-add-artist').value = '';
    $('m3u-add-track-modal').classList.add('hidden');
    renderEditTracks();
}

async function saveEditedM3U() {
    if (!editingFilePath) { showToast('No hay M3U cargado.', 'error'); return; }
    // Reconstruir contenido
    let lines = ['#EXTM3U'];
    editingTracks.forEach(t => {
        if (!t.path) return;
        let extinf = `#EXTINF:${t.duration || 0}`;
        if (t.title) extinf += `,${t.title}`;
        if (t.artist) extinf += ` - ${t.artist}`;
        lines.push(extinf);
        lines.push(t.path);
    });
    const content = lines.join('\n') + '\n';
    try {
        const data = await postJSON('/api/m3u/save', {
            content: content,
            file_path: editingFilePath,
        });
        if (data.success) {
            showToast('M3U guardado correctamente.', 'success');
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function deleteM3U(filePath, filename) {
    if (!confirm(`¿Eliminar "${filename}"?\nEsto borra el archivo del disco.`)) return;
    try {
        const data = await postJSON('/api/m3u/delete', { file_path: filePath });
        if (data.success) {
            showToast('M3U eliminado.', 'success');
            listM3UFiles();
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
