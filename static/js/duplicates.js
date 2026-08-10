/* ============================================
   duplicates.js - Pestana "Duplicados"
   ============================================
   Maneja:
     - Calcular y mostrar grupos de duplicados
     - Filtrar (modo de coincidencia, busqueda)
     - Exportar CSV
     - Mostrar info de espacio recuperable
*/

// Estado
let dupGroups = [];
let filteredGroups = [];
let totalLocal = 0;
let loading = false;

// DOM
const dupStats = document.getElementById('dup-stats');
const dupOptions = document.getElementById('dup-options');
const dupList = document.getElementById('dup-list');
const dupEmpty = document.getElementById('dup-empty');
const dupMatchBy = document.getElementById('dup-match-by');
const dupSearch = document.getElementById('dup-search');
const btnRefreshDup = document.getElementById('btn-refresh-dup');
const btnExportDup = document.getElementById('btn-export-dup');

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadDuplicates();
});

function bindEvents() {
    if (dupMatchBy) dupMatchBy.addEventListener('change', loadDuplicates);
    if (dupSearch) dupSearch.addEventListener('input', applyFilter);
    if (btnRefreshDup) btnRefreshDup.addEventListener('click', loadDuplicates);
    if (btnExportDup) btnExportDup.addEventListener('click', exportDuplicates);
}

async function loadDuplicates() {
    if (loading) return;
    loading = true;

    // Mostrar estado de carga
    dupList.innerHTML = `
        <div class="empty-state" style="padding: 40px;">
            <div class="spinner"></div>
            <h3>Calculando duplicados...</h3>
            <p>Esto puede tardar unos segundos en bibliotecas grandes.</p>
        </div>
    `;
    dupEmpty.classList.add('hidden');

    try {
        const matchBy = dupMatchBy ? dupMatchBy.value : 'title_artist';
        const data = await postJSON('/api/duplicates', { match_by: matchBy });

        dupGroups = data.groups || [];
        filteredGroups = [...dupGroups];
        totalLocal = data.total_local || 0;

        // Actualizar stats
        const totalFiles = dupGroups.reduce((s, g) => s + g.count, 0);
        document.getElementById('dup-groups-count').textContent = dupGroups.length;
        document.getElementById('dup-files-count').textContent = totalFiles;
        document.getElementById('dup-reclaimable').textContent = data.space_reclaimable_str || '0 B';
        document.getElementById('dup-total-local').textContent = totalLocal;

        // Si no hay escaneo local, mostrar empty state
        if (totalLocal === 0) {
            dupStats.classList.add('hidden');
            dupOptions.classList.add('hidden');
            dupList.innerHTML = '';
            dupEmpty.classList.remove('hidden');
            loading = false;
            return;
        }

        dupStats.classList.remove('hidden');
        dupOptions.classList.remove('hidden');
        dupEmpty.classList.add('hidden');

        renderGroups();
    } catch (e) {
        dupList.innerHTML = `
            <div class="empty-state" style="padding: 40px;">
                <div class="empty-icon" style="font-size: 48px; opacity: 0.4;">⚠</div>
                <h3>Error al cargar duplicados</h3>
                <p>${escapeHtml(e.message)}</p>
            </div>
        `;
    } finally {
        loading = false;
    }
}

function applyFilter() {
    const q = dupSearch.value.toLowerCase().trim();
    if (!q) {
        filteredGroups = [...dupGroups];
    } else {
        filteredGroups = dupGroups.filter(g =>
            g.key.toLowerCase().includes(q) ||
            g.files.some(f => (f.path || '').toLowerCase().includes(q) ||
                              (f.name || '').toLowerCase().includes(q))
        );
    }
    renderGroups();
}

function renderGroups() {
    if (filteredGroups.length === 0) {
        if (dupGroups.length === 0) {
            dupList.innerHTML = `
                <div class="empty-state" style="padding: 40px;">
                    <div class="empty-icon" style="font-size: 48px; opacity: 0.4;">✓</div>
                    <h3>No hay canciones duplicadas</h3>
                    <p>Tu biblioteca no tiene canciones repetidas según el criterio actual.<br>
                       Prueba a cambiar el modo de coincidencia arriba si quieres ser más estricto.</p>
                </div>
            `;
        } else {
            dupList.innerHTML = `
                <div class="empty-state" style="padding: 40px;">
                    <div class="empty-icon" style="font-size: 48px; opacity: 0.4;">🔍</div>
                    <h3>Sin resultados</h3>
                    <p>No hay grupos que coincidan con la búsqueda.</p>
                </div>
            `;
        }
        return;
    }

    let html = '';
    filteredGroups.forEach((group, groupIdx) => {
        const best = group.files[0];
        html += `<div class="dup-group">
            <div class="dup-group-header">
                <span class="dup-group-title">${escapeHtml(group.key)}</span>
                <span class="dup-group-count">${group.count} versiones</span>
            </div>`;

        group.files.forEach((f, idx) => {
            const isBest = idx === 0;
            const qLabel = (f.quality && f.quality.label) ? f.quality.label : 'N/A';
            const qDesc = (f.quality && f.quality.description) ? f.quality.description : '';
            const encodedPath = encodeURIComponent(f.path);
            const safeName = (f.name || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
            const safeArtist = (f.artist || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');

            // Badge de formato con color (como en Mi Musica)
            const ext = (f.ext || '').toLowerCase();
            const formatBadge = `<span class="format-badge ${escapeHtml(ext)}">${escapeHtml(ext.toUpperCase())}</span>`;

            const playBtn = `<button class="play-btn" data-path="${escapeHtml(f.path)}"
                onclick="event.stopPropagation(); playFile(decodeURIComponent('${encodedPath}'), '${safeName}', '${safeArtist}');"
                title="Reproducir">▶</button>`;
            const editBtn = `<a href="/editor?path=${encodedPath}" class="action-btn action-editar" title="Editar metadata" style="padding:4px 8px;font-size:11px;">✎</a>`;
            // Boton borrar (con confirmacion para evitar miss-click)
            // Usamos encodeURIComponent para evitar problemas con backslashes de Windows
            const deleteBtn = `<button class="action-btn action-eliminar" title="Borrar archivo"
                onclick="event.stopPropagation(); deleteDuplicateFile(decodeURIComponent('${encodedPath}'), ${groupIdx}, ${idx});"
                style="padding:4px 8px;font-size:11px;">🗑</button>`;
            html += `<div class="dup-file-row ${isBest ? 'best' : ''}">
                ${playBtn}
                <span class="dup-best-tag">${isBest ? 'MEJOR' : ''}</span>
                <span class="dup-file-path" title="${escapeHtml(f.path)} — clic para abrir en explorador" onclick="event.stopPropagation(); revealInExplorer('${encodedPath}');" style="cursor:pointer;">${escapeHtml(f.path)}</span>
                <span class="dup-file-format">${formatBadge}</span>
                <span class="dup-file-quality" title="${escapeHtml(qDesc)}">${escapeHtml(qLabel)}</span>
                <span class="dup-file-size">${escapeHtml(f.size_str || '')}</span>
                ${editBtn}
                ${deleteBtn}
            </div>`;
        });
        html += '</div>';
    });
    dupList.innerHTML = html;
}

/**
 * Elimina un archivo duplicado con doble confirmacion.
 */
async function deleteDuplicateFile(path, groupIdx, fileIdx) {
    // Buscar el archivo en los grupos para info extra
    const group = filteredGroups[groupIdx];
    if (!group) return;
    const file = group.files[fileIdx];
    if (!file) return;
    const isBest = fileIdx === 0;

    // Primera confirmacion
    const warning = isBest
        ? '⚠️ ATENCIÓN: esta es la versión marcada como MEJOR.\nSi la borras, la siguiente mejor versión se convertirá en la principal.\n\n'
        : '';
    const confirm1 = confirm(
        `${warning}¿Eliminar este archivo?\n\n` +
        `Ruta: ${file.path}\n` +
        `Formato: ${(file.ext || '').toUpperCase()}\n` +
        `Tamaño: ${file.size_str || 'N/A'}\n\n` +
        `El archivo se enviará a la papelera de reciclaje.`
    );
    if (!confirm1) return;

    // Segunda confirmacion para evitar miss-click
    const confirm2 = confirm('¿Estás seguro? Esta acción no se puede deshacer (aunque puedes restaurar desde la papelera).');
    if (!confirm2) return;

    try {
        const data = await postJSON('/api/delete-file', { path: path });
        if (data.success) {
            showToast(data.message, 'success');
            // Recargar duplicados
            await loadDuplicates();
        } else {
            showToast(data.message || 'No se pudo eliminar.', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function exportDuplicates() {
    if (dupGroups.length === 0) {
        showToast('No hay duplicados para exportar.', 'error');
        return;
    }
    // Generar CSV local
    const rows = [['Grupo', 'Mejor', 'Ruta', 'Formato', 'Calidad', 'Tamaño']];
    dupGroups.forEach(group => {
        group.files.forEach((f, idx) => {
            rows.push([
                group.key,
                idx === 0 ? 'SI' : '',
                f.path,
                (f.ext || '').toUpperCase(),
                (f.quality && f.quality.label) ? f.quality.label : 'N/A',
                f.size_str || ''
            ]);
        });
    });
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'duplicados.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('CSV exportado.', 'success');
}
