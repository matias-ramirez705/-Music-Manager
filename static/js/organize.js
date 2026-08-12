/* ============================================
   organize.js - Pestana "Organizar por Playlist" (v1.13)
   ============================================
   Modos de uso:
     - Individual: cada fila tiene un boton "Mover" que abre un
       selector de playlist. Al elegir, se mueve esa cancion.
     - Plan: genera un plan masivo y lo ejecuta de golpe.
*/

let currentPlan = null;
let allPlaylists = [];  // cache de playlists guardadas [{id, name, platform}]

// DOM
const baseDirInput = document.getElementById('base-dir-input');
const btnBrowseBase = document.getElementById('btn-browse-base');
const btnPreview = document.getElementById('btn-preview');
const duplicatePolicy = document.getElementById('duplicate-policy');
const moveUnmatched = document.getElementById('move-unmatched');
const planSummary = document.getElementById('plan-summary');
const conflictsSection = document.getElementById('conflicts-section');
const conflictsList = document.getElementById('conflicts-list');
const movesSection = document.getElementById('moves-section');
const movesTbody = document.getElementById('moves-tbody');
const btnExecute = document.getElementById('btn-execute');
const resultSection = document.getElementById('result-section');
const resultContent = document.getElementById('result-content');
const emptyOrganize = document.getElementById('empty-organize');
const localStatusText = document.getElementById('local-status-text');

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    checkLocalStatus();
    loadAllPlaylists();
});

function bindEvents() {
    if (btnBrowseBase) btnBrowseBase.addEventListener('click', browseBaseDir);
    if (btnPreview) btnPreview.addEventListener('click', generatePlan);
    if (btnExecute) btnExecute.addEventListener('click', executeMoves);
}

async function checkLocalStatus() {
    try {
        const data = await getJSON('/api/last-scan');
        if (data.count > 0) {
            localStatusText.textContent =
                `Música local cargada: ${data.count} archivos en ${data.folder}`;
            // Auto-rellenar el directorio base si esta vacio
            if (!baseDirInput.value && data.folder) {
                // Sugerir una subcarpeta "Orden" dentro de la carpeta escaneada
                const sep = data.folder.includes('\\') ? '\\' : '/';
                baseDirInput.value = data.folder + sep + 'Orden';
            }
        } else {
            localStatusText.textContent =
                'No has escaneado tu música local. Ve a "Mi Música" primero.';
        }
    } catch (e) {
        localStatusText.textContent = 'No se pudo verificar el estado local.';
    }
}

async function loadAllPlaylists() {
    try {
        const data = await getJSON('/api/saved-playlists');
        allPlaylists = data.playlists || [];
    } catch (e) {
        allPlaylists = [];
    }
}

async function browseBaseDir() {
    btnBrowseBase.disabled = true;
    try {
        const data = await getJSON('/api/browse');
        if (data.folder) baseDirInput.value = data.folder;
    } catch (e) {
        showToast('No se pudo abrir el diálogo: ' + e.message, 'error');
    } finally {
        btnBrowseBase.disabled = false;
    }
}

async function generatePlan() {
    const baseDir = baseDirInput.value.trim();
    if (!baseDir) {
        showToast('Indica un directorio base.', 'error');
        return;
    }

    btnPreview.disabled = true;
    btnPreview.textContent = 'Generando...';

    try {
        const options = {
            move_unmatched: moveUnmatched ? moveUnmatched.checked : false,
            duplicate_policy: duplicatePolicy ? duplicatePolicy.value : 'ask',
        };
        const plan = await postJSON('/api/organizer/preview', {
            base_dir: baseDir,
            options: options,
        });

        if (plan.error) {
            showToast(plan.error, 'error', 5000);
            return;
        }

        currentPlan = plan;
        renderPlan(plan);
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        btnPreview.disabled = false;
        btnPreview.textContent = 'Generar plan';
    }
}

function renderPlan(plan) {
    // Mostrar resumen
    document.getElementById('stat-total').textContent = plan.total_files;
    document.getElementById('stat-single').textContent = plan.single_playlist_count;
    document.getElementById('stat-multi').textContent = plan.multi_playlist_count;
    document.getElementById('stat-unmatched').textContent = plan.unmatched_count;
    planSummary.classList.remove('hidden');

    // Render TODAS las canciones en la tabla (modo individual + plan)
    renderMovesTable(plan.moves);

    if (plan.total_files > 0) {
        movesSection.classList.remove('hidden');
        emptyOrganize.classList.add('hidden');
    } else {
        movesSection.classList.add('hidden');
        emptyOrganize.classList.remove('hidden');
    }
}

function renderMovesTable(moves) {
    movesTbody.innerHTML = '';

    if (moves.length === 0) {
        movesTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:32px; color:var(--text-muted);">
            No hay movimientos para mostrar.
        </td></tr>`;
        return;
    }

    moves.forEach((m, idx) => {
        const tr = document.createElement('tr');
        const file = m.file || {};
        const fileName = file.name || '';
        const artist = file.artist || 'Desconocido';
        const encodedPath = encodeURIComponent(m.current_path);

        // Columna "Playlist destino": dots de color + selector
        let playlistCellHtml = '';
        if (m.playlists && m.playlists.length > 0) {
            // Dots de color como en Mi Musica
            const dotsHtml = m.playlists.map(p => {
                const color = p.platform === 'youtube' ? 'youtube' : 'spotify';
                return `<span class="playlist-dot ${color}" data-name="${escapeHtml(p.name)}" title="${escapeHtml(p.name)}"></span>`;
            }).join('');

            // Si hay mas de 1 playlist, mostrar selector
            if (m.playlists.length > 1) {
                const options = m.playlists.map(p =>
                    `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)} (${p.platform === 'youtube' ? 'YT' : 'SP'})</option>`
                ).join('');
                playlistCellHtml = `
                    <div class="playlist-badges">${dotsHtml}</div>
                    <select class="playlist-select" data-path="${encodedPath}" onchange="updateMoveTarget(this)">
                        <option value="">— Elegir —</option>
                        ${options}
                    </select>
                `;
            } else {
                // 1 sola playlist: mostrar nombre + dot
                playlistCellHtml = `
                    <div class="playlist-badges">
                        ${dotsHtml}
                        <span style="font-size:11px; color:var(--text-secondary); margin-left:4px;">${escapeHtml(m.playlists[0].name)}</span>
                    </div>
                `;
            }
        } else {
            playlistCellHtml = '<span style="color:var(--text-muted); font-size:11px;">Sin playlist</span>';
        }

        // Columna "Acción": boton mover individual + estado del plan
        let actionHtml = '';
        const plannedAction = m.action;  // 'move', 'copy', 'skip', 'ask'
        if (plannedAction === 'move') {
            actionHtml = `<span class="move-action action-move">🔄 Plan: mover</span>`;
        } else if (plannedAction === 'copy') {
            actionHtml = `<span class="move-action action-copy">📄 Plan: copiar</span>`;
        } else if (plannedAction === 'skip' && m.playlists.length === 0) {
            actionHtml = `<span class="move-action action-skip">⏭ Sin playlist</span>`;
        } else if (plannedAction === 'ask') {
            actionHtml = `<span class="move-action action-pending">⚠ Elige playlist</span>`;
        } else {
            actionHtml = `<span class="move-action action-skip">⏭ Saltar</span>`;
        }

        // Boton mover individual (siempre visible, permite mover 1 a la vez)
        const moveOneBtn = `<button class="btn btn-secondary btn-sm btn-move-one"
            data-path="${encodedPath}"
            data-name="${escapeHtml(fileName).replace(/'/g, '&#39;').replace(/"/g, '&quot;')}"
            data-artist="${escapeHtml(artist).replace(/'/g, '&#39;').replace(/"/g, '&quot;')}"
            onclick="openMoveOneDialog(this)"
            title="Mover esta canción individualmente">📁 Mover</button>`;

        // Origen (truncado)
        const srcShort = m.current_path.length > 40 ?
            '...' + m.current_path.substring(m.current_path.length - 37) : m.current_path;

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td>
                <strong>${escapeHtml(fileName)}</strong><br>
                <span style="color:var(--text-muted); font-size:11px;">${escapeHtml(artist)}</span>
            </td>
            <td>${playlistCellHtml}</td>
            <td>
                <div style="display:flex; flex-direction:column; gap:4px;">
                    ${actionHtml}
                    ${moveOneBtn}
                </div>
            </td>
            <td class="path-cell" title="${escapeHtml(m.current_path)}">${escapeHtml(srcShort)}</td>
            <td class="path-cell move-target" data-path="${encodedPath}">—</td>
        `;
        movesTbody.appendChild(tr);

        // Si el plan ya tiene un new_path, mostrarlo
        if (m.new_path && m.new_path !== m.current_path) {
            const targetCell = tr.querySelector('.move-target');
            if (targetCell) {
                const dstShort = m.new_path.length > 40 ?
                    '...' + m.new_path.substring(m.new_path.length - 37) : m.new_path;
                targetCell.textContent = dstShort;
                targetCell.title = m.new_path;
            }
        }
    });
}

// ------------------------------------------------------------------
// Selector de playlist destino (para conflictos en modo plan)
// ------------------------------------------------------------------
window.updateMoveTarget = function(selectEl) {
    const encodedPath = selectEl.dataset.path;
    const path = decodeURIComponent(encodedPath);
    const playlistId = selectEl.value;
    if (!playlistId) return;

    // Buscar la playlist en allPlaylists
    const pl = allPlaylists.find(p => p.id === playlistId);
    if (!pl) return;

    // Actualizar el movimiento en currentPlan
    if (currentPlan) {
        for (let m of currentPlan.moves) {
            if (m.current_path === path) {
                const baseDir = baseDirInput.value.trim();
                const filename = path.split(/[\\/]/).pop();
                m.action = 'move';
                m.new_path = baseDir.replace(/[\\/]+$/, '') +
                             (baseDir.includes('\\') ? '\\' : '/') +
                             sanitizeFolderName(pl.name) +
                             (baseDir.includes('\\') ? '\\' : '/') +
                             filename;

                // Actualizar celda destino
                const row = selectEl.closest('tr');
                if (row) {
                    const targetCell = row.querySelector('.move-target');
                    if (targetCell) {
                        const dstShort = m.new_path.length > 40 ?
                            '...' + m.new_path.substring(m.new_path.length - 37) : m.new_path;
                        targetCell.textContent = dstShort;
                        targetCell.title = m.new_path;
                    }
                    // Actualizar badge de accion
                    const actionCell = row.querySelector('td:nth-child(4)');
                    if (actionCell) {
                        const moveOneBtn = actionCell.querySelector('.btn-move-one');
                        actionCell.innerHTML = `
                            <div style="display:flex; flex-direction:column; gap:4px;">
                                <span class="move-action action-move">✓ Listo para mover</span>
                                ${moveOneBtn ? moveOneBtn.outerHTML : ''}
                            </div>
                        `;
                    }
                }
                break;
            }
        }
    }
};

// ------------------------------------------------------------------
// Dialogo de mover una sola cancion (modo individual)
// ------------------------------------------------------------------
window.openMoveOneDialog = function(btn) {
    const encodedPath = btn.dataset.path;
    const path = decodeURIComponent(encodedPath);
    const name = btn.dataset.name || '';
    const artist = btn.dataset.artist || '';

    // Crear modal con selector de playlist
    const modalId = 'move-one-modal';
    // Eliminar si ya existe
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const playlistsOptions = allPlaylists.map(p =>
        `<option value="${p.id}">${escapeHtml(p.name)} (${p.platform === 'youtube' ? 'YouTube Music' : 'Spotify'})</option>`
    ).join('');

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h2>Mover canción</h2>
                <button class="modal-close" onclick="document.getElementById('${modalId}').remove()">✕</button>
            </div>
            <div class="modal-body">
                <p><strong>${escapeHtml(name)}</strong></p>
                <p style="color:var(--text-muted); font-size:12px; margin-bottom:16px;">${escapeHtml(artist)}</p>
                <div class="form-group">
                    <label>Mover a playlist:</label>
                    <select id="move-one-playlist" class="form-input">
                        <option value="">— Elegir playlist —</option>
                        ${playlistsOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>O subcarpeta personalizada:</label>
                    <input type="text" id="move-one-folder" class="form-input"
                        placeholder="Nombre de subcarpeta (ej: Mis favoritas)">
                </div>
                <p style="font-size:11px; color:var(--text-muted); margin-top:8px;">
                    Se moverá a: <code id="move-one-preview" style="word-break:break-all;">—</code>
                </p>
                <button id="btn-move-one-confirm" class="btn btn-primary" style="margin-top:12px;">Mover archivo</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Actualizar preview cuando cambia la seleccion
    const playlistSel = document.getElementById('move-one-playlist');
    const folderInput = document.getElementById('move-one-folder');
    const previewEl = document.getElementById('move-one-preview');
    const baseDir = baseDirInput.value.trim();

    const updatePreview = () => {
        const plId = playlistSel.value;
        const folder = folderInput.value.trim();
        let targetFolder = '';
        if (plId) {
            const pl = allPlaylists.find(p => p.id === plId);
            if (pl) targetFolder = sanitizeFolderName(pl.name);
        } else if (folder) {
            targetFolder = sanitizeFolderName(folder);
        }
        if (targetFolder) {
            const sep = baseDir.includes('\\') ? '\\' : '/';
            const filename = path.split(/[\\/]/).pop();
            previewEl.textContent = baseDir + sep + targetFolder + sep + filename;
        } else {
            previewEl.textContent = '—';
        }
    };
    playlistSel.addEventListener('change', updatePreview);
    folderInput.addEventListener('input', updatePreview);

    // Confirmar movimiento
    document.getElementById('btn-move-one-confirm').addEventListener('click', async () => {
        const plId = playlistSel.value;
        const folder = folderInput.value.trim();
        let targetFolder = '';
        if (plId) {
            const pl = allPlaylists.find(p => p.id === plId);
            if (pl) targetFolder = sanitizeFolderName(pl.name);
        } else if (folder) {
            targetFolder = sanitizeFolderName(folder);
        }
        if (!targetFolder) {
            showToast('Elige una playlist o escribe un nombre de carpeta.', 'error');
            return;
        }

        const sep = baseDir.includes('\\') ? '\\' : '/';
        const filename = path.split(/[\\/]/).pop();
        const newPath = baseDir + sep + targetFolder + sep + filename;

        try {
            const data = await postJSON('/api/organizer/move', {
                base_dir: baseDir,
                moves: [{
                    current_path: path,
                    new_path: newPath,
                    action: 'move',
                }],
            });
            if (data.error) {
                showToast(data.error, 'error');
                return;
            }
            showToast(`Movido a "${targetFolder}" (${data.success_count} OK)`, 'success');
            document.getElementById(modalId).remove();
            // Quitar la fila de la tabla (o marcar como movido)
            const row = btn.closest('tr');
            if (row) {
                row.style.opacity = '0.4';
                row.querySelector('.btn-move-one').disabled = true;
                row.querySelector('.btn-move-one').textContent = '✓ Movido';
                const actionCell = row.querySelector('td:nth-child(4)');
                if (actionCell) {
                    const span = actionCell.querySelector('.move-action');
                    if (span) {
                        span.className = 'move-action action-move';
                        span.textContent = '✓ Movido';
                    }
                }
                const targetCell = row.querySelector('.move-target');
                if (targetCell) {
                    targetCell.textContent = newPath.length > 40 ?
                        '...' + newPath.substring(newPath.length - 37) : newPath;
                    targetCell.title = newPath;
                }
            }
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    });
};

function sanitizeFolderName(name) {
    if (!name) return 'Sin nombre';
    return name.replace(/[<>:"/\\|?*]/g, '_').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '').substring(0, 100);
}

async function executeMoves() {
    if (!currentPlan) {
        showToast('Genera un plan primero.', 'error');
        return;
    }

    // Verificar que no haya conflictos pendientes (action=ask sin resolver)
    const pending = currentPlan.moves.filter(m =>
        m.action === 'ask' ||
        (m.action === 'move' && (!m.new_path || m.new_path === m.current_path))
    );
    if (pending.length > 0) {
        showToast(`Hay ${pending.length} canciones sin destino. Elige playlist en cada una o usa "Mover" individual.`, 'error', 5000);
        return;
    }

    // Filtrar solo los que tienen accion move o copy
    const movesToExecute = currentPlan.moves.filter(m =>
        (m.action === 'move' || m.action === 'copy') &&
        m.new_path && m.new_path !== m.current_path
    );

    if (movesToExecute.length === 0) {
        showToast('No hay movimientos para ejecutar. Usa los botones "Mover" individuales o elige playlists para los conflictos.', 'error', 5000);
        return;
    }

    const moveCount = movesToExecute.filter(m => m.action === 'move').length;
    const copyCount = movesToExecute.filter(m => m.action === 'copy').length;
    if (!confirm(`Se ejecutarán:\n${moveCount} movimientos\n${copyCount} copias\n\n¿Continuar?`)) return;

    btnExecute.disabled = true;
    btnExecute.textContent = 'Ejecutando...';

    try {
        const data = await postJSON('/api/organizer/move', {
            base_dir: baseDirInput.value.trim(),
            moves: movesToExecute,
        });

        if (data.error) {
            showToast(data.error, 'error', 5000);
            return;
        }

        let html = `<div class="result-summary">
            <div class="result-stat success">
                <span class="result-num">${data.success_count}</span>
                <span class="result-label">Exitosos</span>
            </div>
            <div class="result-stat skipped">
                <span class="result-num">${data.skipped_count}</span>
                <span class="result-label">Saltados</span>
            </div>
            <div class="result-stat error">
                <span class="result-num">${data.error_count}</span>
                <span class="result-label">Errores</span>
            </div>
        </div>`;

        if (data.created_folders && data.created_folders.length > 0) {
            html += `<h4>Carpetas creadas (${data.created_folders.length}):</h4><ul>`;
            data.created_folders.forEach(f => {
                html += `<li><code>${escapeHtml(f)}</code></li>`;
            });
            html += '</ul>';
        }

        if (data.errors && data.errors.length > 0) {
            html += `<h4>Errores:</h4><ul>`;
            data.errors.forEach(e => {
                html += `<li><code>${escapeHtml(e.path)}</code>: ${escapeHtml(e.error)}</li>`;
            });
            html += '</ul>';
        }

        resultContent.innerHTML = html;
        resultSection.classList.remove('hidden');
        resultSection.scrollIntoView({ behavior: 'smooth' });

        showToast(`Completado: ${data.success_count} OK, ${data.error_count} errores`, 'success', 5000);
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        btnExecute.disabled = false;
        btnExecute.textContent = '▶ Ejecutar plan masivo';
    }
}
