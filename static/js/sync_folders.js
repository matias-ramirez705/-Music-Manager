/* ============================================================
   sync_folders.js - v3.7-sync
   ============================================================
   Lógica de la pestaña "Sincronizar Carpetas".

   Flujo:
     1) Analizar: POST /api/sync/preview con folder_a, folder_b y options
        → Devuelve plan con lista de cambios (add/delete/move/metadata)
     2) Revisar: tabla con pills de colores, filtros por tipo, búsqueda,
        checkboxes para seleccionar qué aplicar.
     3) Confirmar: modal con resumen, al aceptar → POST /api/sync/apply
   ============================================================ */

(function () {
    'use strict';

    // ----------------------------------------------------------------
    // Estado en memoria
    // ----------------------------------------------------------------
    const state = {
        plan: null,          // último plan generado (completo)
        filtered: [],        // cambios filtrados (lo que se muestra en la tabla)
        selected: new Set(), // ids de cambios seleccionados para aplicar
    };

    // Helpers globales de la app (definidos en app.js)
    const getJSON = window.getJSON;
    const postJSON = window.postJSON;
    const showToast = window.showToast;
    const escapeHtml = window.escapeHtml;

    // ----------------------------------------------------------------
    // Helpers locales
    // ----------------------------------------------------------------
    function $(id) { return document.getElementById(id); }

    function uid(change) {
        // Identificador único estable para cada cambio (para selección)
        return change.type + '::' + (change.match_key || '') + '::' +
               (change.source_path || change.target_path || '');
    }

    function pillHTML(type) {
        const map = {
            'add':      '<span class="sync-pill sync-pill-add">+ Copiar</span>',
            'delete':   '<span class="sync-pill sync-pill-delete">− Borrar</span>',
            'move':     '<span class="sync-pill sync-pill-move">→ Mover</span>',
            'metadata': '<span class="sync-pill sync-pill-metadata">✎ Metadatos</span>',
        };
        return map[type] || '<span class="sync-pill">' + escapeHtml(type) + '</span>';
    }

    function detailHTML(change) {
        if (change.type === 'move') {
            const meta = change.metadata_also_changed ? ' <em>+ metadatos</em>' : '';
            return escapeHtml(change.target_rel_path || '') +
                ' → <strong>' + escapeHtml(change.new_target_rel_path || '') + '</strong>' + meta;
        }
        if (change.type === 'metadata') {
            const changes = change.metadata_changes || [];
            return 'Cambios: ' + changes.map(c => '<em>' + escapeHtml(c) + '</em>').join(', ');
        }
        if (change.type === 'add') {
            return 'Nuevo en B: <strong>' + escapeHtml(change.source_rel_path || '') + '</strong>';
        }
        if (change.type === 'delete') {
            return 'Ya no está en A: <strong>' + escapeHtml(change.target_rel_path || '') + '</strong>';
        }
        return '';
    }

    // ----------------------------------------------------------------
    // 1) Analizar (preview)
    // ----------------------------------------------------------------
    function analyze() {
        const folderA = $('sync-folder-a').value.trim();
        const folderB = $('sync-folder-b').value.trim();
        if (!folderA || !folderB) {
            showToast('Indica las dos carpetas.', 'error');
            return;
        }

        const options = {
            compare_metadata: $('sync-opt-metadata').checked,
            compare_artwork: $('sync-opt-artwork').checked,
            detect_moves: $('sync-opt-moves').checked,
        };

        $('sync-empty').classList.add('hidden');
        $('sync-results').classList.add('hidden');
        $('sync-loading').classList.remove('hidden');

        postJSON('/api/sync/preview', {
            folder_a: folderA,
            folder_b: folderB,
            options: options,
        }).then(data => {
            $('sync-loading').classList.add('hidden');
            if (data.error) {
                showToast(data.error, 'error');
                $('sync-empty').classList.remove('hidden');
                return;
            }
            state.plan = data;
            state.selected = new Set(data.changes.map(c => uid(c)));
            renderStats(data.stats);
            renderTable();
            $('sync-results').classList.remove('hidden');
            $('sync-stats').classList.remove('hidden');
            $('sync-filters').classList.remove('hidden');
            updateSummary();
        }).catch(err => {
            $('sync-loading').classList.add('hidden');
            $('sync-empty').classList.remove('hidden');
            showToast('Error al analizar: ' + err, 'error');
        });
    }

    // ----------------------------------------------------------------
    // 2) Render tabla con filtros
    // ----------------------------------------------------------------
    function getActiveTypeFilters() {
        const filters = document.querySelectorAll('.sync-pill-filter input[type=checkbox]');
        const active = new Set();
        filters.forEach(cb => {
            if (cb.checked) active.add(cb.dataset.filter);
        });
        return active;
    }

    function getSearchTerm() {
        return ($('sync-search').value || '').toLowerCase().trim();
    }

    function computeFiltered() {
        if (!state.plan) { state.filtered = []; return; }
        const types = getActiveTypeFilters();
        const q = getSearchTerm();
        state.filtered = state.plan.changes.filter(c => {
            if (!types.has(c.type)) return false;
            if (q) {
                const hay = [c.title, c.artist, c.album,
                             c.source_rel_path, c.target_rel_path,
                             c.new_target_rel_path].join(' ').toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        });
    }

    function renderStats(stats) {
        $('sync-stat-a-total').textContent = stats.a_total;
        $('sync-stat-b-total').textContent = stats.b_total;
        $('sync-stat-add').textContent = stats.add;
        $('sync-stat-delete').textContent = stats.delete;
        $('sync-stat-move').textContent = stats.move;
        $('sync-stat-metadata').textContent = stats.metadata;
    }

    function renderTable() {
        computeFiltered();
        const tbody = $('sync-tbody');
        if (state.filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:24px;">No hay cambios que coincidan con los filtros.</td></tr>';
            return;
        }
        const rows = state.filtered.map(c => {
            const id = uid(c);
            const checked = state.selected.has(id) ? ' checked' : '';
            const rowClass = 'sync-row sync-row-' + c.type;
            return [
                '<tr class="' + rowClass + '" data-uid="' + escapeHtml(id) + '">',
                '<td><input type="checkbox" class="sync-row-check"' + checked + '></td>',
                '<td>' + pillHTML(c.type) + '</td>',
                '<td>' + escapeHtml(c.title || '—') + '</td>',
                '<td>' + escapeHtml(c.artist || '—') + '</td>',
                '<td>' + escapeHtml(c.ext || '') + '</td>',
                '<td>' + escapeHtml(c.duration_str || '—') + '</td>',
                '<td class="sync-path">' + escapeHtml(c.source_rel_path || '—') + '</td>',
                '<td class="sync-path">' + escapeHtml(c.target_rel_path || c.new_target_rel_path || '—') + '</td>',
                '<td class="sync-detail">' + detailHTML(c) + '</td>',
                '</tr>',
            ].join('');
        });
        tbody.innerHTML = rows.join('');

        // Sincronizar checkboxes con state.selected
        tbody.querySelectorAll('.sync-row-check').forEach(cb => {
            cb.addEventListener('change', e => {
                const tr = e.target.closest('tr');
                const id = tr.dataset.uid;
                if (e.target.checked) state.selected.add(id);
                else state.selected.delete(id);
                updateSummary();
            });
        });

        $('sync-check-all').checked = state.filtered.every(c => state.selected.has(uid(c)));
        updateSummary();
    }

    // ----------------------------------------------------------------
    // 3) Selección masiva
    // ----------------------------------------------------------------
    function selectAllVisible(select) {
        if (!state.plan) return;
        state.filtered.forEach(c => {
            const id = uid(c);
            if (select) state.selected.add(id);
            else state.selected.delete(id);
        });
        renderTable();
    }

    function selectOnlyType(type) {
        if (!state.plan) return;
        // Limpiar selección actual y marcar solo los del tipo dado
        state.selected.clear();
        state.plan.changes.forEach(c => {
            if (c.type === type) state.selected.add(uid(c));
        });
        renderTable();
    }

    // ----------------------------------------------------------------
    // 4) Resumen + botón Aplicar
    // ----------------------------------------------------------------
    function updateSummary() {
        if (!state.plan) return;
        const selectedChanges = state.plan.changes.filter(c => state.selected.has(uid(c)));
        const counts = { add: 0, delete: 0, move: 0, metadata: 0 };
        selectedChanges.forEach(c => { counts[c.type] = (counts[c.type] || 0) + 1; });

        $('sync-sum-add').textContent = counts.add;
        $('sync-sum-delete').textContent = counts.delete;
        $('sync-sum-move').textContent = counts.move;
        $('sync-sum-metadata').textContent = counts.metadata;

        const total = selectedChanges.length;
        $('sync-apply').disabled = (total === 0);
        $('sync-apply').textContent = total === 0
            ? '✓ Aplicar cambios seleccionados'
            : '✓ Aplicar ' + total + ' cambio' + (total === 1 ? '' : 's');

        if (total > 0) {
            $('sync-summary').classList.remove('hidden');
        } else {
            $('sync-summary').classList.add('hidden');
        }
    }

    // ----------------------------------------------------------------
    // 5) Confirmar y aplicar
    // ----------------------------------------------------------------
    function openConfirmModal() {
        if (!state.plan) return;
        const selectedChanges = state.plan.changes.filter(c => state.selected.has(uid(c)));
        if (selectedChanges.length === 0) return;

        $('sync-confirm-folder-b').textContent = state.plan.folder_b;
        const counts = { add: 0, delete: 0, move: 0, metadata: 0 };
        selectedChanges.forEach(c => { counts[c.type] = (counts[c.type] || 0) + 1; });
        const list = [
            counts.add > 0      ? '<li>' + counts.add + ' canción(es) copiadas A → B</li>' : '',
            counts.delete > 0   ? '<li>' + counts.delete + ' canción(es) borradas de B</li>' : '',
            counts.move > 0     ? '<li>' + counts.move + ' canción(es) movidas en B</li>' : '',
            counts.metadata > 0 ? '<li>' + counts.metadata + ' canción(es) con metadatos actualizados en B</li>' : '',
        ].filter(Boolean).join('');
        $('sync-confirm-list').innerHTML = list;

        const willDelete = counts.delete > 0 || counts.move > 0;
        const useTrash = $('sync-opt-trash').checked;
        $('sync-confirm-warn').textContent = willDelete
            ? (useTrash
                ? 'Los archivos borrados irán a la papelera de reciclaje.'
                : '⚠ Los archivos borrados se ELIMINARÁN DEFINITIVAMENTE.')
            : '';

        $('sync-confirm-modal').classList.remove('hidden');
    }

    function closeConfirmModal() {
        $('sync-confirm-modal').classList.add('hidden');
    }

    function applyChanges() {
        closeConfirmModal();
        if (!state.plan) return;
        const selectedChanges = state.plan.changes.filter(c => state.selected.has(uid(c)));
        if (selectedChanges.length === 0) return;

        const options = {
            use_trash: $('sync-opt-trash').checked,
            overwrite_target: $('sync-opt-overwrite').checked,
        };
        const filteredPlan = {
            changes: selectedChanges,
            folder_a: state.plan.folder_a,
            folder_b: state.plan.folder_b,
        };

        $('sync-apply').disabled = true;
        $('sync-apply').textContent = 'Aplicando...';

        postJSON('/api/sync/apply', {
            plan: filteredPlan,
            options: options,
        }).then(result => {
            $('sync-apply').disabled = false;
            $('sync-apply').textContent = '✓ Aplicar cambios seleccionados';
            if (result.error) {
                showToast(result.error, 'error');
                return;
            }
            showResultModal(result);
        }).catch(err => {
            $('sync-apply').disabled = false;
            $('sync-apply').textContent = '✓ Aplicar cambios seleccionados';
            showToast('Error al aplicar: ' + err, 'error');
        });
    }

    function showResultModal(result) {
        const summary = $('sync-result-summary');
        const details = $('sync-result-details');
        const totalApplied = result.applied || 0;
        const totalSkipped = result.skipped || 0;
        const errors = result.errors || [];

        let html = '<div class="sync-result-stats">';
        html += '<div class="sync-result-stat ok">✓ Aplicados: <strong>' + totalApplied + '</strong></div>';
        if (totalSkipped > 0) {
            html += '<div class="sync-result-stat warn">⚠ Saltados: <strong>' + totalSkipped + '</strong></div>';
        }
        if (errors.length > 0) {
            html += '<div class="sync-result-stat err">✗ Errores: <strong>' + errors.length + '</strong></div>';
        }
        html += '</div>';

        if (result.success) {
            html += '<p style="margin-top: 12px; color: var(--accent);">Sincronización completada con éxito.</p>';
        } else if (errors.length > 0) {
            html += '<p style="margin-top: 12px; color: var(--danger);">Algunos cambios no se pudieron aplicar:</p>';
        }
        summary.innerHTML = html;

        // Detalles (máx 50 en la UI)
        if (result.details && result.details.length > 0) {
            const visible = result.details.slice(0, 50);
            const rows = visible.map(d => {
                const cls = d.status === 'ok' ? 'sync-detail-ok'
                          : d.status === 'error' ? 'sync-detail-err'
                          : 'sync-detail-skip';
                const icon = d.status === 'ok' ? '✓'
                           : d.status === 'error' ? '✗'
                           : '↷';
                return '<div class="sync-result-row ' + cls + '">' +
                       '<span class="sync-result-icon">' + icon + '</span>' +
                       '<span class="sync-result-type">' + pillHTML(d.type) + '</span>' +
                       '<span class="sync-result-title">' + escapeHtml(d.title || '—') + '</span>' +
                       '<span class="sync-result-msg">' + escapeHtml(d.msg || '') + '</span>' +
                       '</div>';
            });
            details.innerHTML = rows.join('') +
                (result.details.length > 50
                    ? '<p style="margin-top:8px; color:var(--text-muted); font-size:12px;">+' + (result.details.length - 50) + ' más...</p>'
                    : '');
        } else {
            details.innerHTML = '';
        }

        $('sync-result-modal').classList.remove('hidden');
    }

    // ----------------------------------------------------------------
    // 6) Browse folders (delegado al endpoint /api/browse existente)
    // ----------------------------------------------------------------
    function browseFolder(inputId) {
        if (!getJSON) return;
        getJSON('/api/browse').then(data => {
            if (data && data.folder) {
                $(inputId).value = data.folder;
            }
        }).catch(() => {
            showToast('No se pudo abrir el explorador.', 'error');
        });
    }

    // ----------------------------------------------------------------
    // 7) Limpiar
    // ----------------------------------------------------------------
    function clearAll() {
        state.plan = null;
        state.filtered = [];
        state.selected.clear();
        $('sync-folder-a').value = '';
        $('sync-folder-b').value = '';
        $('sync-search').value = '';
        $('sync-results').classList.add('hidden');
        $('sync-stats').classList.add('hidden');
        $('sync-filters').classList.add('hidden');
        $('sync-empty').classList.remove('hidden');
    }

    // ----------------------------------------------------------------
    // Bind events
    // ----------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', function () {
        $('sync-browse-a').addEventListener('click', () => browseFolder('sync-folder-a'));
        $('sync-browse-b').addEventListener('click', () => browseFolder('sync-folder-b'));
        $('sync-analyze').addEventListener('click', analyze);
        $('sync-clear').addEventListener('click', clearAll);

        // Filtros
        $('sync-search').addEventListener('input', renderTable);
        document.querySelectorAll('.sync-pill-filter input[type=checkbox]').forEach(cb => {
            cb.addEventListener('change', renderTable);
        });

        // Selección masiva
        $('sync-select-all').addEventListener('click', () => selectAllVisible(true));
        $('sync-select-none').addEventListener('click', () => selectAllVisible(false));
        $('sync-select-add').addEventListener('click', () => selectOnlyType('add'));
        $('sync-select-del').addEventListener('click', () => selectOnlyType('delete'));

        // Check-all de la cabecera
        $('sync-check-all').addEventListener('change', e => {
            selectAllVisible(e.target.checked);
        });

        // Aplicar
        $('sync-apply').addEventListener('click', openConfirmModal);
        $('sync-confirm-ok').addEventListener('click', applyChanges);
        $('sync-confirm-cancel').addEventListener('click', closeConfirmModal);
        $('sync-confirm-close').addEventListener('click', closeConfirmModal);

        // Result modal
        $('sync-result-ok').addEventListener('click', () => {
            $('sync-result-modal').classList.add('hidden');
            // Re-analizar para mostrar el nuevo estado
            if ($('sync-folder-a').value && $('sync-folder-b').value) {
                analyze();
            }
        });
        $('sync-result-close').addEventListener('click', () => {
            $('sync-result-modal').classList.add('hidden');
        });

        // Enter en input de carpeta dispara análisis
        ['sync-folder-a', 'sync-folder-b'].forEach(id => {
            $(id).addEventListener('keypress', e => {
                if (e.key === 'Enter') analyze();
            });
        });
    });
})();
