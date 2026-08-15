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
    // Boton reproducir
    var btnPlay = $('btn-editor-play');
    if (btnPlay) btnPlay.addEventListener('click', function() {
        if (!currentFilePath) { showToast('Carga un archivo primero.', 'error'); return; }
        var title = $('meta-title') ? $('meta-title').value : '';
        var artist = $('meta-artist') ? $('meta-artist').value : '';
        playFile(currentFilePath, title, artist);
    });
    // Boton ver letra
    var btnLyrics = $('btn-editor-lyrics');
    if (btnLyrics) btnLyrics.addEventListener('click', function() {
        if (!currentFilePath) { showToast('Carga un archivo primero.', 'error'); return; }
        showEditorLyrics();
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
            // Marcar flag para que Mi Musica se actualice
            sessionStorage.setItem('metadata_changed', '1');
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
                '<div class="itunes-result-actions" style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;">' +
                    (r.preview_url ? '<button class="btn btn-ghost btn-sm btn-preview-result" data-url="' + escapeHtml(r.preview_url) + '" title="Escuchar preview (30s)">▶ Preview</button>' : '') +
                    '<button class="btn btn-ghost btn-sm btn-yt-result" data-title="' + escapeHtml(r.title) + '" data-artist="' + escapeHtml(r.artist) + '" title="Buscar en YouTube">▶ YouTube</button>' +
                    (r.artwork_url ? '<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); applyArtworkFromResult(' + idx + ');">🖼 Carátula</button>' : '') +
                '</div>' +
            '</div>';
        div.addEventListener('click', function() { applyResult(r); });

        // Boton preview
        var previewBtn = div.querySelector('.btn-preview-result');
        if (previewBtn) {
            previewBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                togglePreview(previewBtn, previewBtn.dataset.url);
            });
        }
        // Boton YouTube
        var ytBtn = div.querySelector('.btn-yt-result');
        if (ytBtn) {
            ytBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                var q = ytBtn.dataset.title + ' ' + ytBtn.dataset.artist;
                window.open('https://www.youtube.com/results?search_query=' + encodeURIComponent(q), '_blank');
            });
        }

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
        // Marcar flag para que Mi Musica sepa que hay que actualizar
        sessionStorage.setItem('metadata_changed', '1');
    } catch (e) {
        showToast('Error al guardar: ' + e.message, 'error', 5000);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Guardar cambios';
        }
    }
}

// ------------------------------------------------------------------
// Ver letra desde el editor
// ------------------------------------------------------------------
async function showEditorLyrics() {
    var title = $('meta-title') ? $('meta-title').value : '';
    var artist = $('meta-artist') ? $('meta-artist').value : '';

    var modalId = 'editor-lyrics-modal';
    var existing = document.getElementById(modalId);
    if (existing) existing.remove();

    var modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = '<div class="modal-content" style="max-width:700px;">' +
        '<div class="modal-header"><h2>📖 ' + escapeHtml(title) + '</h2>' +
        '<button class="modal-close">✕</button></div>' +
        '<div class="modal-body">' +
        '<div class="lyrics-text" id="editor-lyrics-content"><p class="empty-hint">Cargando...</p></div>' +
        '<div id="editor-lyrics-actions" style="margin-top:12px;"></div>' +
        '</div></div>';
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', function() { modal.remove(); });

    try {
        var data = await postJSON('/api/lyrics/read', { path: currentFilePath });
        var content = document.getElementById('editor-lyrics-content');
        var actions = document.getElementById('editor-lyrics-actions');

        if (data.has_lyrics && data.lyrics) {
            var text = data.lyrics;
            if (text.indexOf('[') >= 0 && text.match(/\[\d{2}:\d{2}/)) {
                content.innerHTML = '<p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">✓ Letra sincronizada.</p>' + formatEditorLrc(text);
            } else {
                content.innerHTML = '<p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">⚠ Letra sin sincronización.</p>' + formatEditorPlain(text);
            }
            actions.innerHTML = '<button id="btn-ed-ly-search" class="btn btn-secondary btn-sm">🔄 Buscar otra</button> ' +
                '<button id="btn-ed-ly-delete" class="btn btn-ghost btn-sm">🗑 Borrar</button>';
            document.getElementById('btn-ed-ly-search').addEventListener('click', function() {
                modal.remove();
                searchEditorLyrics(currentFilePath, title, artist);
            });
            document.getElementById('btn-ed-ly-delete').addEventListener('click', async function() {
                if (!confirm('¿Borrar la letra?')) return;
                var r = await postJSON('/api/lyrics/remove', { path: currentFilePath });
                showToast(r.message, 'success');
                modal.remove();
            });
        } else {
            content.innerHTML = '<p class="empty-hint">Sin letra embebida.</p>';
            actions.innerHTML = '<button id="btn-ed-ly-search" class="btn btn-primary btn-sm">🔍 Buscar en lrclib.net</button>';
            document.getElementById('btn-ed-ly-search').addEventListener('click', function() {
                modal.remove();
                searchEditorLyrics(currentFilePath, title, artist);
            });
        }
    } catch (e) {
        document.getElementById('editor-lyrics-content').innerHTML =
            '<p style="color:var(--danger);">' + escapeHtml(e.message) + '</p>';
    }
}

async function searchEditorLyrics(filePath, title, artist) {
    var modalId = 'editor-lyrics-search-modal';
    var existing = document.getElementById(modalId);
    if (existing) existing.remove();

    var modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = '<div class="modal-content" style="max-width:700px;">' +
        '<div class="modal-header"><h2>🔍 Buscar letra</h2>' +
        '<button class="modal-close">✕</button></div>' +
        '<div class="modal-body">' +
        '<div class="form-group"><label>Titulo</label><input type="text" id="ed-ly-title" class="form-input" value="' + escapeHtml(title) + '"></div>' +
        '<div class="form-group"><label>Artista</label><input type="text" id="ed-ly-artist" class="form-input" value="' + escapeHtml(artist) + '"></div>' +
        '<button id="btn-ed-ly-do-search" class="btn btn-primary">🔍 Buscar</button>' +
        '<div id="ed-ly-results" style="margin-top:16px;"></div>' +
        '</div></div>';
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', function() { modal.remove(); });

    document.getElementById('btn-ed-ly-do-search').addEventListener('click', async function() {
        var t = document.getElementById('ed-ly-title').value.trim();
        var a = document.getElementById('ed-ly-artist').value.trim();
        var rDiv = document.getElementById('ed-ly-results');
        rDiv.innerHTML = '<p class="empty-hint">Buscando...</p>';
        try {
            var data = await postJSON('/api/lyrics/search', { title: t, artist: a });
            if (!data.found || !data.lyrics) {
                rDiv.innerHTML = '<p class="empty-hint">No encontrada.</p>';
                return;
            }
            var ly = data.lyrics;
            var plain = ly.plain || '(sin letra)';
            var synced = ly.synced || '';
            var html = '<div style="margin-bottom:8px;"><strong style="color:var(--accent);">Encontrada</strong></div>';
            if (synced) {
                html += '<details style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">Sincronizada (LRC) — recomendada</summary>';
                html += '<pre class="lyrics-plain" style="max-height:200px;">' + escapeHtml(synced) + '</pre></details>';
            }
            if (plain && plain !== '(sin letra)') {
                html += '<details open style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">Letra plana</summary>';
                html += '<pre class="lyrics-plain" style="max-height:250px;">' + escapeHtml(plain) + '</pre></details>';
            }
            html += '<div style="display:flex;gap:8px;flex-wrap:wrap;">';
            if (synced) {
                html += '<button id="btn-ed-ly-save-sync" class="btn btn-primary">💾 Guardar sync</button>';
            }
            if (plain && plain !== '(sin letra)') {
                html += '<button id="btn-ed-ly-save-plain" class="btn btn-secondary">💾 Guardar plana</button>';
            }
            html += '</div>';
            rDiv.innerHTML = html;
            var saveSyncEd = document.getElementById('btn-ed-ly-save-sync');
            if (saveSyncEd) saveSyncEd.addEventListener('click', async function() {
                var r = await postJSON('/api/lyrics/save', { path: filePath, lyrics: synced });
                if (r.success) { showToast('Letra sincronizada guardada.', 'success'); modal.remove(); }
            });
            var savePlainEd = document.getElementById('btn-ed-ly-save-plain');
            if (savePlainEd) savePlainEd.addEventListener('click', async function() {
                var r = await postJSON('/api/lyrics/save', { path: filePath, lyrics: plain });
                if (r.success) { showToast('Letra plana guardada.', 'success'); modal.remove(); }
            });
        } catch (e) {
            rDiv.innerHTML = '<p style="color:var(--danger);">' + escapeHtml(e.message) + '</p>';
        }
    });
}

function formatEditorLrc(text) {
    var lines = text.split('\n');
    var html = '<div class="lyrics-synced">';
    lines.forEach(function(line) {
        var clean = line.replace(/\[\d{2}:\d{2}\.\d{2,3}\]/g, '').trim();
        html += '<div class="lyrics-line">' + (clean ? escapeHtml(clean) : '&nbsp;') + '</div>';
    });
    html += '</div>';
    return html;
}

function formatEditorPlain(text) {
    var lines = text.split('\n');
    var html = '<div class="lyrics-synced">';
    lines.forEach(function(line) {
        var clean = line.trim();
        html += '<div class="lyrics-line">' + (clean ? escapeHtml(clean) : '&nbsp;') + '</div>';
    });
    html += '</div>';
    return html;
}

// ------------------------------------------------------------------
// Preview de cancion (30s desde iTunes)
// ------------------------------------------------------------------
var previewAudio = null;

function togglePreview(btn, url) {
    // Si ya hay un preview sonando, detenerlo
    if (previewAudio) {
        previewAudio.pause();
        previewAudio = null;
        _detachPreviewVolSync();
        // Restaurar todos los botones
        document.querySelectorAll('.btn-preview-result').forEach(function(b) {
            b.textContent = '▶ Preview';
        });
        // Si es el mismo boton, solo detener
        if (btn.dataset.url === url) return;
    }
    // Crear nuevo audio
    previewAudio = new Audio(url);
    // Aplicar el volumen del reproductor principal (v3.10)
    // lastVolume está definido en player.js y va de 0 a 1.
    try {
        if (typeof lastVolume === 'number') {
            // Si está muteado, lastMuted=true, usamos volumen 0
            var effectiveVol = (typeof lastMuted === 'boolean' && lastMuted) ? 0 : lastVolume;
            previewAudio.volume = Math.max(0, Math.min(1, effectiveVol));
        }
    } catch (e) {
        // Si por alguna razón no podemos acceder a lastVolume, dejamos volumen default
        previewAudio.volume = 0.5;
    }
    // Escuchar cambios de volumen del reproductor mientras suena el preview
    // para que se actualice en tiempo real
    var volSlider = document.getElementById('player-volume');
    if (volSlider) {
        volSlider.addEventListener('input', _previewVolSync);
    }
    previewAudio.addEventListener('ended', function() {
        btn.textContent = '▶ Preview';
        previewAudio = null;
        _detachPreviewVolSync();
    });
    previewAudio.addEventListener('error', function() {
        btn.textContent = '▶ Preview';
        previewAudio = null;
        showToast('No se pudo cargar el preview.', 'error');
        _detachPreviewVolSync();
    });
    previewAudio.play();
    btn.textContent = '❚❚ Stop';
}

// Funciones auxiliares para sincronizar volumen del preview con el slider del reproductor
function _previewVolSync(e) {
    if (previewAudio) {
        var v = parseInt(e.target.value, 10) / 100;
        previewAudio.volume = Math.max(0, Math.min(1, v));
    }
}
function _detachPreviewVolSync() {
    var volSlider = document.getElementById('player-volume');
    if (volSlider) {
        volSlider.removeEventListener('input', _previewVolSync);
    }
}

