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

    dupList.innerHTML = '';
    filteredGroups.forEach((group, groupIdx) => {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'dup-group';
        const header = document.createElement('div');
        header.className = 'dup-group-header';
        header.innerHTML = `
            <span class="dup-group-title">${escapeHtml(group.key)}</span>
            <span class="dup-group-count">${group.count} versiones</span>
        `;
        groupDiv.appendChild(header);

        group.files.forEach((f, idx) => {
            const isBest = idx === 0;
            const qLabel = (f.quality && f.quality.label) ? f.quality.label : 'N/A';
            const qDesc = (f.quality && f.quality.description) ? f.quality.description : '';
            const ext = (f.ext || '').toLowerCase();

            const row = document.createElement('div');
            row.className = 'dup-file-row' + (isBest ? ' best' : '');

            // Boton play (event listener, no onclick inline)
            const playBtn = document.createElement('button');
            playBtn.className = 'play-btn';
            playBtn.title = 'Reproducir';
            playBtn.textContent = '▶';
            playBtn.dataset.path = f.path;
            playBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                playFile(f.path, f.name || '', f.artist || '');
            });
            row.appendChild(playBtn);

            // Etiqueta MEJOR
            const bestTag = document.createElement('span');
            bestTag.className = 'dup-best-tag';
            bestTag.textContent = isBest ? 'MEJOR' : '';
            row.appendChild(bestTag);

            // Path (clickable para abrir explorador)
            const pathSpan = document.createElement('span');
            pathSpan.className = 'dup-file-path';
            pathSpan.title = f.path + ' — clic para abrir en explorador';
            pathSpan.textContent = f.path;
            pathSpan.style.cursor = 'pointer';
            pathSpan.addEventListener('click', (e) => {
                e.stopPropagation();
                revealInExplorer(encodeURIComponent(f.path));
            });
            row.appendChild(pathSpan);

            // Formato
            const formatSpan = document.createElement('span');
            formatSpan.className = 'dup-file-format';
            formatSpan.innerHTML = `<span class="format-badge ${escapeHtml(ext)}">${escapeHtml(ext.toUpperCase())}</span>`;
            row.appendChild(formatSpan);

            // Calidad
            const qualitySpan = document.createElement('span');
            qualitySpan.className = 'dup-file-quality';
            qualitySpan.title = qDesc;
            qualitySpan.textContent = qLabel;
            row.appendChild(qualitySpan);

            // Tamano
            const sizeSpan = document.createElement('span');
            sizeSpan.className = 'dup-file-size';
            sizeSpan.textContent = f.size_str || '';
            row.appendChild(sizeSpan);

            // Boton editar
            const editLink = document.createElement('a');
            editLink.href = '/editor?path=' + encodeURIComponent(f.path);
            editLink.className = 'action-btn action-editar';
            editLink.title = 'Editar metadata';
            editLink.style.cssText = 'padding:4px 8px;font-size:11px;';
            editLink.textContent = '✎';
            editLink.addEventListener('click', (e) => e.stopPropagation());
            row.appendChild(editLink);

            // Boton borrar
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'action-btn action-eliminar';
            deleteBtn.title = 'Borrar archivo';
            deleteBtn.style.cssText = 'padding:4px 8px;font-size:11px;';
            deleteBtn.textContent = '🗑';
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteDuplicateFile(f.path, groupIdx, idx);
            });
            row.appendChild(deleteBtn);

            groupDiv.appendChild(row);
        });
        dupList.appendChild(groupDiv);
    });
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
