/*
 * static/js/deleted.js
 * ===================
 * Lógica de la pestaña "Canciones Eliminadas".
 *
 * Funciones principales:
 *  - Cargar la lista desde /api/deleted-songs
 *  - Renderizar tabla con columnas: #, Nombre, Artista, Formato,
 *    Playlists (dots como en Mi Música), Comentario (clicable),
 *    Eliminar (botón de quitar de la lista).
 *  - Filtrado por búsqueda y por tipo de comentario.
 *  - Modal para editar el comentario con presets ("No me gustó",
 *    "Repetida") o comentario libre.
 *
 * Dependencias (de app.js):
 *  - getJSON(url, options)  -> fetch wrapper
 *  - showToast(msg, type)   -> notificaciones
 *  - escapeHtml(s)          -> escape de HTML
 */

// ------------------------------------------------------------------
// Estado
// ------------------------------------------------------------------
let allDeleted = [];          // lista cruda desde el backend
let currentEditingId = null;  // id de la canción cuyo comentario se está editando

// ------------------------------------------------------------------
// Referencias al DOM
// ------------------------------------------------------------------
const delStats          = document.getElementById('del-stats');
const delCount          = document.getElementById('del-count');
const delCommented      = document.getElementById('del-commented');
const delStillInPl      = document.getElementById('del-still-in-pl');
const delOptions        = document.getElementById('del-options');
const delSearch         = document.getElementById('del-search');
const delFilterComment  = document.getElementById('del-filter-comment');
const btnRefreshDel     = document.getElementById('btn-refresh-del');
const btnClearDel       = document.getElementById('btn-clear-del');
const delTableContainer = document.getElementById('del-table-container');
const delTbody          = document.getElementById('del-tbody');
const delEmpty          = document.getElementById('del-empty');
const delLoading        = document.getElementById('del-loading');

// Modal
const commentModal        = document.getElementById('comment-modal');
const commentModalClose   = document.getElementById('comment-modal-close');
const commentSongName     = document.getElementById('comment-song-name');
const commentSongArtist   = document.getElementById('comment-song-artist');
const commentInput        = document.getElementById('comment-input');
const commentPreview      = document.getElementById('comment-preview');
const commentPreviewText  = document.getElementById('comment-preview-text');
const commentClearBtn     = document.getElementById('comment-clear-btn');
const commentSaveBtn      = document.getElementById('comment-save-btn');
const commentPresets      = document.querySelectorAll('.comment-preset');

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    loadDeleted();

    btnRefreshDel.addEventListener('click', refreshDeletedAndScan);
    btnClearDel.addEventListener('click', confirmClearAll);
    delSearch.addEventListener('input', renderRows);
    delFilterComment.addEventListener('change', renderRows);

    // Modal
    commentModalClose.addEventListener('click', closeCommentModal);
    commentModal.addEventListener('click', (e) => {
        if (e.target === commentModal) closeCommentModal();
    });
    commentInput.addEventListener('input', updateCommentPreview);
    commentPresets.forEach(btn => {
        btn.addEventListener('click', () => {
            commentInput.value = btn.dataset.comment;
            updateCommentPreview();
            commentInput.focus();
        });
    });
    commentClearBtn.addEventListener('click', () => {
        commentInput.value = '';
        updateCommentPreview();
    });
    commentSaveBtn.addEventListener('click', saveComment);
});

// ------------------------------------------------------------------
// Recargar: re-escanea Mi Música (para detectar nuevos eliminados)
// y luego recarga la lista de Eliminados.
// Si no hay carpeta previa, solo recarga la lista.
// ------------------------------------------------------------------
async function refreshDeletedAndScan() {
    // Cambiar el icono del botón a spinner
    const originalText = btnRefreshDel.innerHTML;
    btnRefreshDel.disabled = true;
    btnRefreshDel.innerHTML = '⏳ Escaneando...';

    try {
        // 1. Verificar si hay un escaneo previo (carpeta guardada)
        const lastScanResp = await fetch('/api/last-scan');
        const lastScan = await lastScanResp.json();
        const folder = lastScan.folder;

        if (folder) {
            // 2. Re-escanear la misma carpeta
            //    Esto dispara la detección de eliminados en el backend.
            const scanResp = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder: folder }),
            });
            if (!scanResp.ok) {
                const err = await scanResp.json().catch(() => ({}));
                throw new Error(err.error || 'Error al escanear');
            }
            const scanData = await scanResp.json();
            if (scanData.deleted_detected > 0) {
                showToast(`Escaneo completo. ${scanData.deleted_detected} nueva(s) eliminada(s) detectada(s).`, 'success');
            } else {
                showToast(`Escaneo completo. Sin nuevas eliminaciones.`, 'info');
            }
        } else {
            // No hay carpeta previa: solo recargamos la lista
            showToast('No hay carpeta escaneada previamente. Solo recargando lista...', 'info');
        }
        // 3. Recargar la lista de eliminados
        await loadDeleted();
    } catch (e) {
        showToast('Error al recargar: ' + e.message, 'error');
    } finally {
        btnRefreshDel.disabled = false;
        btnRefreshDel.innerHTML = originalText;
    }
}

// ------------------------------------------------------------------
// Cargar desde el backend
// ------------------------------------------------------------------
async function loadDeleted() {
    delLoading.classList.remove('hidden');
    delEmpty.classList.add('hidden');
    delTableContainer.classList.add('hidden');
    delOptions.classList.add('hidden');
    delStats.classList.add('hidden');

    try {
        const data = await getJSON('/api/deleted-songs');
        allDeleted = data.songs || [];
        renderStats();
        renderRows();
        delOptions.classList.remove('hidden');
        delStats.classList.remove('hidden');
    } catch (e) {
        showToast('Error al cargar eliminados: ' + e.message, 'error');
        delEmpty.classList.remove('hidden');
    } finally {
        delLoading.classList.add('hidden');
    }
}

// ------------------------------------------------------------------
// Stats
// ------------------------------------------------------------------
function renderStats() {
    delCount.textContent = allDeleted.length;
    delCommented.textContent = allDeleted.filter(s => s.comment && s.comment.trim()).length;
    delStillInPl.textContent = allDeleted.filter(s => s.still_in_playlists && s.still_in_playlists.length).length;
}

// ------------------------------------------------------------------
// Render de filas
// ------------------------------------------------------------------
function renderRows() {
    delTbody.innerHTML = '';

    // Filtrado
    const q = delSearch.value.toLowerCase().trim();
    const commentFilter = delFilterComment.value;

    let filtered = allDeleted.filter(s => {
        // Filtro de búsqueda
        if (q) {
            const hay = (s.name + ' ' + (s.artist || '') + ' ' + (s.comment || '')).toLowerCase();
            if (!hay.includes(q)) return false;
        }
        // Filtro de comentario
        if (commentFilter === 'none') {
            if (s.comment && s.comment.trim()) return false;
        } else if (commentFilter === 'custom') {
            // Comentario personalizado = no vacío Y no es uno de los presets
            if (!s.comment || !s.comment.trim()) return false;
            if (s.comment === 'No me gustó' || s.comment === 'Repetida') return false;
        } else if (commentFilter) {
            // Filtro por preset exacto
            if (s.comment !== commentFilter) return false;
        }
        return true;
    });

    if (filtered.length === 0) {
        delTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">
            No hay canciones eliminadas con esos filtros.
        </td></tr>`;
        delTableContainer.classList.remove('hidden');
        delEmpty.classList.add('hidden');
        return;
    }

    delEmpty.classList.add('hidden');
    delTableContainer.classList.remove('hidden');

    filtered.forEach((song, idx) => {
        const tr = document.createElement('tr');

        // Playlists (dots como en Mi Música)
        const playlistsCell = document.createElement('div');
        playlistsCell.className = 'playlist-badges';
        const inPls = song.playlists || [];
        const stillInPls = song.still_in_playlists || [];
        if (inPls.length > 0) {
            inPls.forEach(p => {
                const dot = document.createElement('span');
                dot.className = 'playlist-dot ' + p.platform;
                // Si la canción todavía está en la playlist (el usuario la re-agregó),
                // mostramos un check; si no, una X tenue
                const stillThere = stillInPls.find(sp => sp.id === p.id);
                if (stillThere) {
                    dot.title = p.name + ' — canción presente (re-agregada)';
                    dot.style.opacity = '1';
                } else {
                    dot.title = p.name + ' — ya no está en esta playlist';
                    dot.style.opacity = '0.4';
                }
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

        // Comentario
        const comment = song.comment || '';
        const commentBadge = comment
            ? `<span class="quality-badge quality-lossless" style="background:rgba(180,180,180,0.1); color:var(--text-secondary); border-color:var(--border);">${escapeHtml(comment)}</span>`
            : '<span style="color:var(--text-muted); font-size:11px;">Sin comentario — clic para agregar</span>';

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(song.name || '—')}</strong></td>
            <td>${escapeHtml(song.artist || '—')}</td>
            <td style="text-align:center;">${song.ext ? `<span class="format-badge ${escapeHtml(song.ext.toLowerCase())}">${escapeHtml(song.ext.toUpperCase())}</span>` : '—'}</td>
            <td></td>
            <td class="comment-cell" style="cursor:pointer; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="Clic para editar comentario">${commentBadge}</td>
            <td style="text-align:center;"></td>
        `;
        tr.children[4].appendChild(playlistsCell);

        // Click en celda de comentario abre el modal
        const commentCell = tr.children[5];
        commentCell.addEventListener('click', (e) => {
            e.stopPropagation();
            openCommentModal(song.id, song.name, song.artist, song.comment || '');
        });

        // Botón eliminar de la lista
        const removeCell = tr.children[6];
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-ghost btn-sm';
        removeBtn.title = 'Quitar "' + (song.name || '') + '" de la lista de eliminados';
        removeBtn.textContent = '✕';
        removeBtn.style.color = 'var(--warning)';
        removeBtn.style.padding = '2px 8px';
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            confirmRemove(song);
        });
        removeCell.appendChild(removeBtn);

        delTbody.appendChild(tr);
    });
}

// ------------------------------------------------------------------
// Abrir playlist desde dot (igual que en Mi Música)
// ------------------------------------------------------------------
async function openPlaylistById(playlistId) {
    try {
        const p = await getJSON('/api/saved-playlist/' + playlistId);
        // Reutilizamos la misma función de Mi Música si está disponible
        if (typeof showPlaylistDetailModal === 'function') {
            showPlaylistDetailModal(p);
        } else {
            // Fallback: abrir la playlist en /saved
            window.location.href = '/saved';
        }
    } catch (e) {
        showToast('Error al abrir playlist: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Modal de comentario
// ------------------------------------------------------------------
function openCommentModal(songId, name, artist, currentComment) {
    currentEditingId = songId;
    commentSongName.textContent = name || '—';
    commentSongArtist.textContent = artist || '';
    commentInput.value = currentComment || '';
    updateCommentPreview();
    commentModal.classList.remove('hidden');
    commentInput.focus();
    commentInput.select();
}

function closeCommentModal() {
    commentModal.classList.add('hidden');
    currentEditingId = null;
    commentInput.value = '';
    updateCommentPreview();
}

function updateCommentPreview() {
    const v = commentInput.value.trim();
    if (v) {
        commentPreview.style.display = 'block';
        commentPreviewText.textContent = v;
    } else {
        commentPreview.style.display = 'none';
    }
}

async function saveComment() {
    if (!currentEditingId) return;
    const comment = commentInput.value.trim();
    try {
        const resp = await fetch(`/api/deleted-songs/${currentEditingId}/comment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment: comment }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || 'Error al guardar comentario');
        }
        // Actualizar el estado local sin recargar todo
        const song = allDeleted.find(s => s.id === currentEditingId);
        if (song) song.comment = comment;
        closeCommentModal();
        renderStats();
        renderRows();
        showToast('Comentario guardado.', 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Eliminar de la lista
// ------------------------------------------------------------------
function confirmRemove(song) {
    if (!confirm(`¿Quitar "${song.name || '—'}" de la lista de eliminados?\n\nEsto NO borra ningún archivo del disco. Solo la saca de esta lista.`)) {
        return;
    }
    removeSongFromList(song.id);
}

async function removeSongFromList(songId) {
    try {
        const resp = await fetch(`/api/deleted-songs/${songId}`, { method: 'DELETE' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || 'Error al eliminar');
        }
        allDeleted = allDeleted.filter(s => s.id !== songId);
        renderStats();
        renderRows();
        showToast('Canción quitada de la lista.', 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Vaciar toda la lista
// ------------------------------------------------------------------
function confirmClearAll() {
    if (allDeleted.length === 0) {
        showToast('La lista ya está vacía.', 'info');
        return;
    }
    if (!confirm(`¿Vaciar toda la lista de eliminados?\n\nSe eliminarán ${allDeleted.length} canciones de esta lista. Esto NO borra archivos del disco.`)) {
        return;
    }
    clearAll();
}

async function clearAll() {
    try {
        const resp = await fetch('/api/deleted-songs/clear', { method: 'POST' });
        if (!resp.ok) throw new Error('Error al vaciar lista');
        const data = await resp.json();
        allDeleted = [];
        renderStats();
        renderRows();
        showToast(`Lista vaciada. ${data.removed} canciones quitadas.`, 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
