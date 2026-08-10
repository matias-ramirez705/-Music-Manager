/* ============================================
   editor.js - Pestana "Editar Metadata" (v1.9)
   ============================================
   REESCRITO para maxima robustez:
   - Todas las referencias DOM se obtienen DENTRO de cada funcion
     con document.getElementById(), no al nivel top-level.
   - Esto evita que un elemento faltante rompa todo el script.
   - Si un elemento no existe, solo esa funcion falla, no las demas.
*/

// Estado (no depende del DOM)
var currentFilePath = '';
var currentItunesResults = [];

// Helper local para obtener elementos
function $(id) {
    return document.getElementById(id);
}

// ------------------------------------------------------------------
// INICIALIZACION
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function() {
    // Vincular eventos
    var btnBrowse = $('btn-browse-file');
    var btnLoad = $('btn-load-file');
    var btnSave = $('btn-save-meta');
    var btnRename = $('btn-rename-file');
    var btnSearch = $('btn-auto-search');
    var btnResize = $('btn-artwork-resize');
    var btnRemoveArt = $('btn-artwork-remove');
    var btnLocalArt = $('btn-artwork-local');
    var inputArtFile = $('artwork-file-input');
    var btnDlArt = $('btn-artwork-download');
    var btnResizeOk = $('btn-resize-confirm');
    var btnResizeCancel = $('btn-resize-cancel');
    var inputFile = $('file-input');

    if (btnBrowse) btnBrowse.addEventListener('click', browseFile);
    if (btnLoad) btnLoad.addEventListener('click', loadFile);
    if (btnSave) btnSave.addEventListener('click', saveMetadata);
    if (btnRename) btnRename.addEventListener('click', renameFile);
    if (btnSearch) btnSearch.addEventListener('click', autoSearch);
    if (btnResize) btnResize.addEventListener('click', toggleResizePanel);
    if (btnRemoveArt) btnRemoveArt.addEventListener('click', removeArtwork);
    if (btnLocalArt) btnLocalArt.addEventListener('click', function() {
        if (inputArtFile) inputArtFile.click();
    });
    if (inputArtFile) inputArtFile.addEventListener('change', handleLocalArtwork);
    if (btnDlArt) btnDlArt.addEventListener('click', downloadArtworkFromUrl);
    if (btnResizeOk) btnResizeOk.addEventListener('click', confirmResize);
    if (btnResizeCancel) btnResizeCancel.addEventListener('click', function() {
        var panel = $('artwork-resize-panel');
        if (panel) panel.classList.add('hidden');
    });
    if (inputFile) inputFile.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') loadFile();
    });

    // Si venimos con ?path=... (desde Mi Musica), cargar el archivo
    var params = new URLSearchParams(window.location.search);
    var path = params.get('path');
    if (path && inputFile) {
        inputFile.value = path;
        // Cargar inmediatamente
        loadFile();
    }
});

// ------------------------------------------------------------------
// Renombrar archivo local
// ------------------------------------------------------------------
async function renameFile() {
    if (!currentFilePath) {
        showToast('Carga un archivo primero.', 'error');
        return;
    }
    var inputTitle = $('meta-title');
    var inputArtist = $('meta-artist');
    if (!inputTitle || !inputArtist) return;

    var title = inputTitle.value.trim();
    var artist = inputArtist.value.trim();
    if (!title) {
        showToast('El título está vacío. Edita el título primero.', 'error');
        return;
    }

    var lastDot = currentFilePath.lastIndexOf('.');
    var lastSep = Math.max(currentFilePath.lastIndexOf('/'), currentFilePath.lastIndexOf('\\'));
    var ext = lastDot > lastSep ? currentFilePath.substring(lastDot) : '';
    var dir = lastSep >= 0 ? currentFilePath.substring(0, lastSep + 1) : '';

    var sanitize = function(s) {
        return s.replace(/[<>:"\/\\|?*]/g, '_').replace(/\s+/g, ' ').trim().substring(0, 100);
    };

    var safeTitle = sanitize(title);
    var safeArtist = sanitize(artist);
    var newName = safeArtist ? (safeTitle + ' - ' + safeArtist + ext) : (safeTitle + ext);
    var newPath = dir + newName;

    if (newPath === currentFilePath) {
        showToast('El archivo ya tiene ese nombre.', '');
        return;
    }

    if (!confirm('¿Renombrar archivo?\n\nDe:\n' + currentFilePath + '\n\nA:\n' + newPath)) return;

    try {
        var data = await postJSON('/api/rename-file', {
            old_path: currentFilePath,
            new_path: newPath,
        });
        if (data.success) {
            showToast('Archivo renombrado.', 'success');
            currentFilePath = newPath;
            var fi = $('file-input');
            if (fi) fi.value = newPath;
            var fp = $('current-file-path');
            if (fp) fp.textContent = newPath;
        } else {
            showToast(data.message || 'No se pudo renombrar.', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Dialogo nativo (selector de archivo)
// ------------------------------------------------------------------
async function browseFile() {
    var btn = $('btn-browse-file');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Abriendo...';
    }
    showToast('Abriendo diálogo... revisa si aparece detrás del navegador.', '', 4000);
    try {
        var data = await getJSON('/api/browse-file');
        if (data.error) {
            showToast('Error: ' + data.error, 'error');
        } else if (data.path) {
            var fi = $('file-input');
            if (fi) fi.value = data.path;
            loadFile();
        }
    } catch (e) {
        showToast('No se pudo abrir el diálogo: ' + e.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Explorar';
        }
    }
}

// ------------------------------------------------------------------
// Cargar archivo
// ------------------------------------------------------------------
async function loadFile() {
    var fi = $('file-input');
    if (!fi) {
        showToast('Error: no se encontró el campo de ruta.', 'error');
        return;
    }
    var path = fi.value.trim();
    if (!path) {
        showToast('Indica la ruta de un archivo.', 'error');
        return;
    }

    var btnLoad = $('btn-load-file');
    if (btnLoad) {
        btnLoad.disabled = true;
        btnLoad.textContent = 'Cargando...';
    }

    try {
        var data = await postJSON('/api/file-metadata', { path: path });
        currentFilePath = path;

        // Llenar formulario
        var fields = {
            'meta-title': data.title || '',
            'meta-artist': data.artist || '',
            'meta-album': data.album || '',
            'meta-date': data.date || '',
            'meta-track': data.track || '',
            'meta-genre': data.genre || '',
        };
        for (var fid in fields) {
            var el = $(fid);
            if (el) el.value = fields[fid];
        }

        // Mostrar ruta
        var fp = $('current-file-path');
        if (fp) fp.textContent = path;

        // Info tecnica
        renderTechInfo(data.quality, data);

        // Caratula
        await loadArtwork();

        // Mostrar panel, ocultar empty state
        var panel = $('editor-panel');
        var empty = $('empty-editor');
        if (panel) panel.classList.remove('hidden');
        if (empty) empty.classList.add('hidden');

        // Limpiar resultados de busqueda
        var results = $('itunes-results');
        if (results) results.innerHTML = '<p class="empty-hint">Sin resultados aún. Pulsa "Buscar".</p>';
        currentItunesResults = [];

        showToast('Archivo cargado.', 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        if (btnLoad) {
            btnLoad.disabled = false;
            btnLoad.textContent = 'Cargar';
        }
    }
}

// ------------------------------------------------------------------
// Caratula
// ------------------------------------------------------------------
async function loadArtwork() {
    var preview = $('artwork-preview');
    var placeholder = $('artwork-placeholder');
    var info = $('artwork-info');
    try {
        var data = await postJSON('/api/artwork/info', { path: currentFilePath });
        if (data.has_artwork) {
            if (preview) {
                preview.src = '/api/artwork?path=' + encodeURIComponent(currentFilePath) + '&_t=' + Date.now();
                preview.classList.add('has-image');
            }
            if (placeholder) placeholder.style.display = 'none';
            var dim = (data.width && data.height) ? (data.width + 'x' + data.height + ' • ') : '';
            if (info) info.textContent = dim + data.size_kb + ' KB • ' + data.mime;
        } else {
            if (preview) {
                preview.classList.remove('has-image');
                preview.src = '';
            }
            if (placeholder) placeholder.style.display = 'block';
            if (info) info.textContent = 'Sin carátula embebida';
        }
    } catch (e) {
        if (info) info.textContent = 'Error al leer carátula';
    }
}

async function handleLocalArtwork(event) {
    var file = event.target.files[0];
    if (!file) return;
    if (!currentFilePath) {
        showToast('Carga un archivo de audio primero.', 'error');
        return;
    }
    var reader = new FileReader();
    reader.onload = async function(e) {
        var base64 = e.target.result.split(',')[1];
        try {
            var data = await postJSON('/api/artwork/save', {
                path: currentFilePath,
                image_data: base64,
                mime: file.type || 'image/jpeg',
            });
            showToast(data.message, data.success ? 'success' : 'error');
            if (data.success) await loadArtwork();
        } catch (err) {
            showToast('Error: ' + err.message, 'error');
        }
    };
    reader.readAsDataURL(file);
    event.target.value = '';
}

function toggleResizePanel() {
    var panel = $('artwork-resize-panel');
    if (panel) panel.classList.toggle('hidden');
}

async function confirmResize() {
    var sizeEl = $('resize-size');
    var fmtEl = $('resize-fmt');
    var btn = $('btn-resize-confirm');
    if (!sizeEl || !fmtEl) return;

    var size = parseInt(sizeEl.value, 10);
    var fmt = fmtEl.value;
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Redimensionando...';
    }
    try {
        var data = await postJSON('/api/artwork/resize', {
            path: currentFilePath,
            max_size: size,
            fmt: fmt,
        });
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            await loadArtwork();
            var panel = $('artwork-resize-panel');
            if (panel) panel.classList.add('hidden');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Aplicar';
        }
    }
}

async function removeArtwork() {
    if (!confirm('¿Eliminar la carátula embebida de este archivo?')) return;
    var btn = $('btn-artwork-remove');
    if (btn) btn.disabled = true;
    try {
        var data = await postJSON('/api/artwork/remove', { path: currentFilePath });
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) await loadArtwork();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function downloadArtworkFromUrl() {
    var urlInput = $('artwork-url-input');
    var btn = $('btn-artwork-download');
    if (!urlInput) return;
    var url = urlInput.value.trim();
    if (!url) {
        showToast('Pega una URL de imagen primero.', 'error');
        return;
    }
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Descargando...';
    }
    try {
        var data = await postJSON('/api/artwork/save', {
            path: currentFilePath,
            image_url: url,
        });
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            await loadArtwork();
            urlInput.value = '';
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '⬇ URL';
        }
    }
}

// ------------------------------------------------------------------
// Info tecnica
// ------------------------------------------------------------------
function renderTechInfo(quality, data) {
    var grid = $('tech-grid');
    if (!grid) return;
    if (!quality) {
        grid.innerHTML = '<div class="tech-item"><span class="tech-item-label">Sin info</span></div>';
        return;
    }
    var d = quality.details;
    grid.innerHTML =
        '<div class="tech-item"><span class="tech-item-label">Profundidad</span><span class="tech-item-value">' + escapeHtml(d.bit_depth) + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Sample rate</span><span class="tech-item-value">' + escapeHtml(d.sample_rate) + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Bitrate</span><span class="tech-item-value">' + escapeHtml(d.bitrate) + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Canales</span><span class="tech-item-value">' + escapeHtml(d.channels) + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Duración</span><span class="tech-item-value">' + escapeHtml(d.duration) + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Clasificación</span><span class="tech-item-value">' + escapeHtml(quality.description) + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Tamaño</span><span class="tech-item-value">' + escapeHtml(data.size_str || '—') + '</span></div>' +
        '<div class="tech-item"><span class="tech-item-label">Formato</span><span class="tech-item-value">' + escapeHtml((data.ext || '').toUpperCase()) + '</span></div>';
}

// ------------------------------------------------------------------
// Busqueda multi-fuente
// ------------------------------------------------------------------
async function autoSearch() {
    var titleEl = $('meta-title');
    var artistEl = $('meta-artist');
    var sourceEl = $('source-select');
    var resultsEl = $('itunes-results');
    var btn = $('btn-auto-search');
    if (!titleEl) return;

    var title = titleEl.value.trim();
    var artist = artistEl ? artistEl.value.trim() : '';
    var source = sourceEl ? sourceEl.value : 'itunes';

    if (!title) {
        showToast('Se necesita al menos el título.', 'error');
        return;
    }
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Buscando...';
    }
    if (resultsEl) resultsEl.innerHTML = '<p class="empty-hint">Buscando...</p>';

    try {
        var data = await postJSON('/api/auto-search', { title: title, artist: artist, source: source });
        if (data.message) {
            if (resultsEl) resultsEl.innerHTML = '<p class="empty-hint">' + escapeHtml(data.message) + '</p>';
            return;
        }
        currentItunesResults = data.results;
        renderResults(data.results, data.best);
    } catch (e) {
        if (resultsEl) resultsEl.innerHTML = '<p class="empty-hint">Error: ' + escapeHtml(e.message) + '</p>';
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔍 Buscar';
        }
    }
}

function renderResults(results, best) {
    var resultsEl = $('itunes-results');
    if (!resultsEl) return;
    if (!results || results.length === 0) {
        resultsEl.innerHTML = '<p class="empty-hint">Sin resultados.</p>';
        return;
    }
    resultsEl.innerHTML = '';
    results.forEach(function(r, idx) {
        var div = document.createElement('div');
        div.className = 'itunes-result';
        if (best && r.title === best.title && r.artist === best.artist && r.source === best.source) {
            div.style.borderColor = 'var(--accent)';
        }

        var thumb = r.artwork_url
            ? '<img class="itunes-result-thumb" src="' + escapeHtml(r.artwork_url) + '" alt="" onerror="this.style.display=\'none\'">'
            : '<div class="itunes-result-thumb" style="display:flex;align-items:center;justify-content:center;color:var(--text-muted);">♪</div>';

        var sourceClass = (r.source || 'itunes').toLowerCase().replace(/\./g, '');
        var sourceBadge = '<span class="itunes-result-source ' + sourceClass + '">' + escapeHtml(r.source || 'iTunes') + '</span>';

        div.innerHTML =
            thumb +
            '<div class="itunes-result-body">' +
                '<div class="itunes-result-title">' + sourceBadge + escapeHtml(r.title) + '</div>' +
                '<div class="itunes-result-meta">' + escapeHtml(r.artist) + (r.year ? ' • ' + escapeHtml(r.year) : '') + '</div>' +
                (r.album ? '<div class="itunes-result-album">' + escapeHtml(r.album) + '</div>' : '') +
                (r.artwork_url ? '<button class="btn btn-ghost btn-sm" style="margin-top:4px;" onclick="event.stopPropagation(); applyArtworkFromResult(' + idx + ');">Usar esta carátula</button>' : '') +
            '</div>';
        div.addEventListener('click', function() { applyResult(r); });
        resultsEl.appendChild(div);
    });
}

function applyResult(r) {
    var fields = {
        'meta-title': r.title,
        'meta-artist': r.artist,
        'meta-album': r.album,
        'meta-date': r.year,
        'meta-genre': r.genre,
        'meta-track': r.track_number,
    };
    for (var fid in fields) {
        var el = $(fid);
        if (el && fields[fid]) el.value = fields[fid];
    }
    showToast('Rellenado: ' + r.title + ' - ' + r.artist, 'success');
}

async function applyArtworkFromResult(idx) {
    var r = currentItunesResults[idx];
    if (!r || !r.artwork_url) {
        showToast('Este resultado no tiene carátula.', 'error');
        return;
    }
    try {
        var data = await postJSON('/api/artwork/save', {
            path: currentFilePath,
            image_url: r.artwork_url,
        });
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) await loadArtwork();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Guardar metadata
// ------------------------------------------------------------------
async function saveMetadata() {
    if (!currentFilePath) {
        showToast('Carga un archivo primero.', 'error');
        return;
    }
    var titleEl = $('meta-title');
    var artistEl = $('meta-artist');
    var albumEl = $('meta-album');
    var dateEl = $('meta-date');
    var trackEl = $('meta-track');
    var genreEl = $('meta-genre');

    var metadata = {
        title:  titleEl ? titleEl.value.trim() : '',
        artist: artistEl ? artistEl.value.trim() : '',
        album:  albumEl ? albumEl.value.trim() : '',
        date:   dateEl ? dateEl.value.trim() : '',
        track:  trackEl ? trackEl.value.trim() : '',
        genre:  genreEl ? genreEl.value.trim() : '',
    };
    var btn = $('btn-save-meta');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Guardando...';
    }
    try {
        var data = await postJSON('/api/save-metadata', {
            path: currentFilePath,
            metadata: metadata,
        });
        showToast(data.message, 'success');
    } catch (e) {
        showToast('Error al guardar: ' + e.message, 'error', 5000);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Guardar cambios';
        }
    }
}
