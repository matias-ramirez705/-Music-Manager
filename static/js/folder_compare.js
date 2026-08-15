/*
 * static/js/folder_compare.js (v3.12)
 * ===================================
 * Lógica de la pestaña "Comparar Carpetas".
 *
 * - Carga 2 carpetas, las escanea, compara archivos por título normalizado
 * - Muestra ambas listas en paralelo (panel A | panel B)
 * - Marca en color:
 *     Rojo:   canciones solo en A (faltan en B)
 *     Naranja: canciones solo en B (faltan en A)
 *     Verde:   canciones comunes (presentes en ambos lados)
 * - Click en cualquier fila → abre el archivo en el explorador de archivos
 *
 * Dependencias (de app.js):
 *  - getJSON(url, options) / postJSON(url, body)
 *  - showToast(msg, type)
 *  - escapeHtml(s)
 */

// ------------------------------------------------------------------
// Estado
// ------------------------------------------------------------------
var fcResult = null;       // último resultado completo de la comparación
var fcFolderA = '';
var fcFolderB = '';

// ------------------------------------------------------------------
// Refs al DOM
// ------------------------------------------------------------------
var folderAInput   = document.getElementById('folder-a-input');
var folderBInput   = document.getElementById('folder-b-input');
var btnBrowseA     = document.getElementById('btn-browse-a');
var btnBrowseB     = document.getElementById('btn-browse-b');
var btnCompare     = document.getElementById('btn-compare-folders');
var btnClear       = document.getElementById('btn-clear-folders');
var fcStats        = document.getElementById('fc-stats');
var fcATotal       = document.getElementById('fc-a-total');
var fcBTotal       = document.getElementById('fc-b-total');
var fcCommon       = document.getElementById('fc-common');
var fcAOnly        = document.getElementById('fc-a-only');
var fcBOnly        = document.getElementById('fc-b-only');
var fcOptions      = document.getElementById('fc-options');
var fcSearch       = document.getElementById('fc-search');
var fcShowCommon   = document.getElementById('fc-show-common');
var fcShowOnly     = document.getElementById('fc-show-only');
var btnRefreshFc   = document.getElementById('btn-refresh-fc');
var fcPanels       = document.getElementById('fc-panels');
var fcFolderAPath  = document.getElementById('fc-folder-a-path');
var fcFolderBPath  = document.getElementById('fc-folder-b-path');
var fcTbodyA       = document.getElementById('fc-tbody-a');
var fcTbodyB       = document.getElementById('fc-tbody-b');
var fcEmpty        = document.getElementById('fc-empty');
var fcLoading      = document.getElementById('fc-loading');

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function() {
    btnBrowseA.addEventListener('click', function() { browseFolder(folderAInput); });
    btnBrowseB.addEventListener('click', function() { browseFolder(folderBInput); });
    btnCompare.addEventListener('click', compareFoldersAction);
    btnClear.addEventListener('click', clearAll);
    btnRefreshFc.addEventListener('click', compareFoldersAction);
    fcSearch.addEventListener('input', renderBoth);
    fcShowCommon.addEventListener('change', renderBoth);
    fcShowOnly.addEventListener('change', renderBoth);

    // Enter en los inputs dispara comparar
    [folderAInput, folderBInput].forEach(function(inp) {
        inp.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') compareFoldersAction();
        });
    });
});

// ------------------------------------------------------------------
// Diálogo nativo de selección de carpeta
// ------------------------------------------------------------------
async function browseFolder(inputEl) {
    try {
        var resp = await getJSON('/api/browse');
        if (resp.folder) {
            inputEl.value = resp.folder;
        }
    } catch (e) {
        showToast('Error al abrir explorador: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Acción principal: comparar carpetas
// ------------------------------------------------------------------
async function compareFoldersAction() {
    var a = folderAInput.value.trim();
    var b = folderBInput.value.trim();
    if (!a || !b) {
        showToast('Indica las dos carpetas.', 'error');
        return;
    }
    fcFolderA = a;
    fcFolderB = b;

    fcLoading.classList.remove('hidden');
    fcEmpty.classList.add('hidden');
    fcPanels.classList.add('hidden');
    fcStats.classList.add('hidden');
    fcOptions.classList.add('hidden');

    try {
        var data = await postJSON('/api/folder-compare', {
            folder_a: a,
            folder_b: b,
        });
        if (data.error) {
            throw new Error(data.error);
        }
        fcResult = data;
        renderStats();
        renderBoth();
        fcStats.classList.remove('hidden');
        fcOptions.classList.remove('hidden');
        fcPanels.classList.remove('hidden');
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 6000);
        fcEmpty.classList.remove('hidden');
    } finally {
        fcLoading.classList.add('hidden');
    }
}

// ------------------------------------------------------------------
// Stats
// ------------------------------------------------------------------
function renderStats() {
    if (!fcResult) return;
    var s = fcResult.stats;
    fcATotal.textContent = s.a_total;
    fcBTotal.textContent = s.b_total;
    fcCommon.textContent = s.common_count;
    fcAOnly.textContent = s.a_only_count;
    fcBOnly.textContent = s.b_only_count;
    fcFolderAPath.textContent = fcResult.folder_a;
    fcFolderBPath.textContent = fcResult.folder_b;
    fcFolderAPath.title = fcResult.folder_a;
    fcFolderBPath.title = fcResult.folder_b;
}

// ------------------------------------------------------------------
// Render de ambos paneles
// ------------------------------------------------------------------
function renderBoth() {
    if (!fcResult) return;
    renderPanel('a', fcTbodyA, fcResult.a_files, fcResult.a_only, fcResult.common);
    renderPanel('b', fcTbodyB, fcResult.b_files, fcResult.b_only, fcResult.common);
}

function renderPanel(side, tbody, allFiles, onlyFiles, commonFiles) {
    tbody.innerHTML = '';

    // Construir set de títulos "comunes" para marcar verde
    var commonTitles = {};
    commonFiles.forEach(function(c) {
        commonTitles[c.title] = true;
    });
    // Construir set de "solo en este lado" para marcar rojo/naranja
    var onlyTitles = {};
    onlyFiles.forEach(function(f) {
        onlyTitles[f.title || f.name] = true;
    });

    // Filtro de búsqueda
    var q = fcSearch.value.toLowerCase().trim();

    // Filtrar según checkboxes
    var showCommon = fcShowCommon.checked;
    var showOnly = fcShowOnly.checked;

    var visible = allFiles.filter(function(f) {
        var title = f.name || '';
        var isCommon = !!commonTitles[title];
        var isOnly = !!onlyTitles[title];
        if (isCommon && !showCommon) return false;
        if (isOnly && !showOnly) return false;
        if (!isCommon && !isOnly && !showCommon) return false; // fallback
        if (q) {
            var hay = (f.filename + ' ' + f.name + ' ' + f.artist + ' ' + f.ext).toLowerCase();
            if (hay.indexOf(q) === -1) return false;
        }
        return true;
    });

    if (visible.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--text-muted);">' +
            'Sin archivos para mostrar con los filtros actuales.' +
            '</td></tr>';
        return;
    }

    visible.forEach(function(f, idx) {
        var tr = document.createElement('tr');

        var title = f.name || '';
        var isCommon = !!commonTitles[title];
        var isOnly = !!onlyTitles[title];

        // Aplicar color de fondo según estado
        if (isOnly) {
            // Rojo (solo en A) o naranja (solo en B)
            var color = (side === 'a') ? 'rgba(255, 107, 107, 0.12)' : 'rgba(255, 165, 0, 0.12)';
            tr.style.background = color;
            // Borde izquierdo de color para más visibilidad
            var borderColor = (side === 'a') ? 'var(--danger)' : 'var(--warning)';
            tr.style.boxShadow = 'inset 3px 0 0 ' + borderColor;
        } else if (isCommon) {
            tr.style.background = 'rgba(29, 185, 84, 0.08)';
            tr.style.boxShadow = 'inset 3px 0 0 var(--accent)';
        }

        // Badge de estado (para facilitar la lectura)
        var statusBadge = '';
        if (isOnly) {
            if (side === 'a') {
                statusBadge = ' <span class="fc-badge fc-badge-missing-b" title="Falta en carpeta B">⚠ Falta en B</span>';
            } else {
                statusBadge = ' <span class="fc-badge fc-badge-missing-a" title="Falta en carpeta A">⚠ Falta en A</span>';
            }
        } else if (isCommon) {
            statusBadge = ' <span class="fc-badge fc-badge-common" title="Presente en ambas carpetas">✓ Común</span>';
        }

        tr.innerHTML =
            '<td>' + (idx + 1) + '</td>' +
            '<td>' + escapeHtml(f.filename) + statusBadge + '</td>' +
            '<td style="text-align:center;">' + (f.ext ? '<span class="format-badge ' + escapeHtml(f.ext.toLowerCase()) + '">' + escapeHtml(f.ext.toUpperCase()) + '</span>' : '—') + '</td>' +
            '<td style="text-align:center; font-family:var(--font-mono); font-size:11px;">' + escapeHtml(f.duration_str) + '</td>' +
            '<td style="text-align:right; font-family:var(--font-mono); font-size:11px;">' + escapeHtml(f.size_str) + '</td>';

        // Click en fila → abrir en explorador
        tr.style.cursor = 'pointer';
        tr.title = 'Clic para abrir en el explorador de archivos:\n' + f.path;
        tr.addEventListener('click', function(e) {
            e.stopPropagation();
            revealInExplorer(f.path);
        });

        tbody.appendChild(tr);
    });
}

// ------------------------------------------------------------------
// Abrir en explorador (reutiliza el endpoint compartido)
// ------------------------------------------------------------------
async function revealInExplorer(filePath) {
    try {
        var resp = await postJSON('/api/reveal-in-explorer', { path: filePath });
        if (resp.success) {
            showToast('Abriendo en explorador...', 'info', 2000);
        } else {
            showToast(resp.message || 'No se pudo abrir.', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Limpiar todo
// ------------------------------------------------------------------
function clearAll() {
    folderAInput.value = '';
    folderBInput.value = '';
    fcResult = null;
    fcTbodyA.innerHTML = '';
    fcTbodyB.innerHTML = '';
    fcStats.classList.add('hidden');
    fcOptions.classList.add('hidden');
    fcPanels.classList.add('hidden');
    fcEmpty.classList.remove('hidden');
}
