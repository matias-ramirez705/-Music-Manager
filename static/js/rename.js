/*
 * static/js/rename.js (v3.11)
 * ===========================
 * Lógica de la sub-pestaña "Renombrar" (Analizador de Nombres)
 * dentro de la pestaña Metadatos.
 *
 * Funcionalidades:
 *  - Carga la lista de archivos del último escaneo (GET /api/analyze-names)
 *  - Muestra tabla: # | Nombre del archivo | Nombre canción (metadata) | Artista | Renombrar
 *  - Buscador en tiempo real
 *  - Filtro por estado (Todas / Solo las que necesitan renombrar / Solo las OK)
 *  - Botón renombrar en cada fila con protección anti-colisión (_1, _2, ...)
 *  - Click en fila abre el archivo en la sub-pestaña "Editar Metadata"
 *
 * Dependencias (de app.js):
 *  - getJSON(url) / postJSON(url, body) -> fetch wrappers
 *  - showToast(msg, type)               -> notificaciones
 *  - escapeHtml(s)                       -> escape de HTML
 */

// ------------------------------------------------------------------
// Estado
// ------------------------------------------------------------------
var anAllFiles = [];
var anFiltered = [];

// ------------------------------------------------------------------
// Refs al DOM (pueden ser null si la sub-pestaña no está activa)
// ------------------------------------------------------------------
var anStatus = document.getElementById('an-status');
var anStatusText = document.getElementById('an-status-text');
var anFilterBar = document.getElementById('an-filter-bar');
var anSearch = document.getElementById('an-search');
var anFilterNeed = document.getElementById('an-filter-need');
var btnAnRefresh = document.getElementById('btn-an-refresh');
var anCountBadge = document.getElementById('an-count-badge');
var anTableContainer = document.getElementById('an-table-container');
var anTbody = document.getElementById('an-tbody');
var anEmpty = document.getElementById('an-empty');
var anLoading = document.getElementById('an-loading');

// ------------------------------------------------------------------
// Init: solo si estamos en la sub-pestaña renombrar (anTbody existe)
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function() {
    if (!anTbody) return; // No estamos en la sub-pestaña renombrar

    if (btnAnRefresh) btnAnRefresh.addEventListener('click', loadAnalyzeNames);
    if (anSearch) anSearch.addEventListener('input', renderAnalyzeRows);
    if (anFilterNeed) anFilterNeed.addEventListener('change', renderAnalyzeRows);

    // Cargar automáticamente al entrar a la sub-pestaña
    loadAnalyzeNames();
});

// ------------------------------------------------------------------
// Cargar lista desde el backend
// ------------------------------------------------------------------
async function loadAnalyzeNames() {
    if (!anTbody) return;
    if (anLoading) anLoading.classList.remove('hidden');
    if (anEmpty) anEmpty.classList.add('hidden');
    if (anTableContainer) anTableContainer.classList.add('hidden');
    if (anFilterBar) anFilterBar.classList.add('hidden');
    if (anStatus) anStatus.style.display = 'none';

    try {
        var resp = await fetch('/api/analyze-names');
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            throw new Error(err.error || 'Error al cargar');
        }
        var data = await resp.json();
        anAllFiles = data.files || [];
        if (anAllFiles.length === 0) {
            if (anStatusText) anStatusText.textContent = 'No hay archivos escaneados. Ve a "Mi Música" y escanea tu biblioteca.';
            if (anStatus) anStatus.style.display = 'flex';
            if (anEmpty) anEmpty.classList.remove('hidden');
        } else {
            if (anStatus) anStatus.style.display = 'none';
            if (anFilterBar) anFilterBar.classList.remove('hidden');
            if (anTableContainer) anTableContainer.classList.remove('hidden');
            renderAnalyzeRows();
        }
    } catch (e) {
        if (anStatusText) anStatusText.textContent = 'Error: ' + e.message;
        if (anStatus) anStatus.style.display = 'flex';
    } finally {
        if (anLoading) anLoading.classList.add('hidden');
    }
}

// ------------------------------------------------------------------
// Render de filas
// ------------------------------------------------------------------
function renderAnalyzeRows() {
    if (!anTbody) return;
    anTbody.innerHTML = '';
    var q = (anSearch && anSearch.value || '').toLowerCase().trim();
    var needFilter = anFilterNeed ? anFilterNeed.value : '';

    anFiltered = anAllFiles.filter(function(f) {
        // Filtro de búsqueda
        if (q) {
            var hay = (f.filename + ' ' + f.title + ' ' + f.artist).toLowerCase();
            if (hay.indexOf(q) === -1) return false;
        }
        // Filtro de "needs rename"
        if (needFilter === 'need' && !f.needs_rename) return false;
        if (needFilter === 'ok' && f.needs_rename) return false;
        return true;
    });

    if (anCountBadge) anCountBadge.textContent = anFiltered.length + ' canciones';

    if (anFiltered.length === 0) {
        anTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:32px; color:var(--text-muted);">' +
            'No hay archivos que coincidan con los filtros.' +
            '</td></tr>';
        return;
    }

    anFiltered.forEach(function(f, idx) {
        var tr = document.createElement('tr');

        var badge = f.needs_rename
            ? '<span class="needs-rename-badge">⚠ Revisar</span>'
            : '<span class="rename-ok-badge">✓ OK</span>';

        var filenameDisplay = escapeHtml(f.filename);
        if (f.needs_rename) {
            filenameDisplay = '<span style="color:var(--warning);">' + filenameDisplay + '</span>';
        }

        tr.innerHTML =
            '<td>' + (idx + 1) + '</td>' +
            '<td>' + filenameDisplay + '</td>' +
            '<td>' + badge + ' <strong>' + escapeHtml(f.title || '—') + '</strong></td>' +
            '<td>' + escapeHtml(f.artist || '—') + '</td>' +
            '<td></td>';

        // Botón renombrar
        var renameCell = tr.children[4];
        var renameBtn = document.createElement('button');
        renameBtn.className = 'btn btn-secondary btn-sm';
        renameBtn.title = 'Renombrar archivo a "' + (f.title || '') + ' - ' + (f.artist || '') + '.' + (f.ext || '') + '"';
        renameBtn.innerHTML = '📄 Renombrar';
        renameBtn.style.padding = '4px 8px';
        renameBtn.style.fontSize = '11px';
        renameBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            renameFromAnalyzer(f);
        });
        renameCell.appendChild(renameBtn);

        // Click en fila abre el archivo en "Editar Metadata"
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', function() {
            window.location.href = '/editor?sub=edit&path=' + encodeURIComponent(f.path);
        });

        anTbody.appendChild(tr);
    });
}

// ------------------------------------------------------------------
// Renombrar desde el analizador (con protección anti-colisión del backend)
// ------------------------------------------------------------------
async function renameFromAnalyzer(fileInfo) {
    var title = (fileInfo.title || '').trim();
    var artist = (fileInfo.artist || '').trim();
    var ext = fileInfo.ext || '';
    var path = fileInfo.path;

    if (!title) {
        showToast('El archivo no tiene título de metadata. Edítalo primero en "Editar Metadata".', 'error');
        return;
    }
    if (!ext) {
        var lastDot = path.lastIndexOf('.');
        var lastSep = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        if (lastDot > lastSep) ext = path.substring(lastDot);
    } else {
        ext = '.' + ext;
    }

    var lastSep = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
    var dir = lastSep >= 0 ? path.substring(0, lastSep + 1) : '';

    var sanitize = function(s) {
        return s.replace(/[<>:"\/\\|?*]/g, '_').replace(/\s+/g, ' ').trim().substring(0, 100);
    };

    var safeTitle = sanitize(title);
    var safeArtist = sanitize(artist);
    var newName = safeArtist ? (safeTitle + ' - ' + safeArtist + ext) : (safeTitle + ext);
    var newPath = dir + newName;

    if (newPath === path) {
        showToast('El archivo ya tiene ese nombre.', 'info');
        return;
    }

    if (!confirm('¿Renombrar archivo?\n\nDe:\n' + path + '\n\nA:\n' + newPath +
                 '\n\n(Si ya existe un archivo con ese nombre, se añadirá automáticamente _1, _2, ...)')) {
        return;
    }

    try {
        var data = await postJSON('/api/rename-file', {
            old_path: path,
            new_path: newPath,
        });
        if (data.success) {
            showToast(data.message || 'Archivo renombrado.', 'success');
            // Actualizar el filename en el estado local y re-renderizar
            fileInfo.filename = data.renamed_to || newName;
            fileInfo.path = data.new_path || newPath;
            renderAnalyzeRows();
            sessionStorage.setItem('metadata_changed', '1');
        } else {
            showToast(data.message || 'No se pudo renombrar.', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
