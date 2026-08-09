/* ============================================
   editor.js - Pestana "Editar Metadata"
   ============================================
   Maneja:
     - Seleccion de archivo (dialogo nativo o query param ?path=)
     - Carga de metadata actual via /api/file-metadata
     - Busqueda en iTunes via /api/auto-search
     - Guardado via /api/save-metadata
*/

// Estado
let currentFilePath = '';
let currentItunesResults = [];

// DOM
const fileInput       = document.getElementById('file-input');
const btnBrowseFile   = document.getElementById('btn-browse-file');
const btnLoadFile     = document.getElementById('btn-load-file');
const editorPanel     = document.getElementById('editor-panel');
const emptyEditor     = document.getElementById('empty-editor');
const currentFilePathEl = document.getElementById('current-file-path');
const btnSaveMeta     = document.getElementById('btn-save-meta');
const btnAutoSearch   = document.getElementById('btn-auto-search');
const itunesResults   = document.getElementById('itunes-results');
const techGrid        = document.getElementById('tech-grid');

// Inputs del formulario
const metaTitle  = document.getElementById('meta-title');
const metaArtist = document.getElementById('meta-artist');
const metaAlbum  = document.getElementById('meta-album');
const metaDate   = document.getElementById('meta-date');
const metaTrack  = document.getElementById('meta-track');
const metaGenre  = document.getElementById('meta-genre');

// ------------------------------------------------------------------
// AL CARGAR
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    bindEvents();

    // Si venimos con ?path=... (desde la pestana Mi Musica), cargar
    const params = new URLSearchParams(window.location.search);
    const path = params.get('path');
    if (path) {
        fileInput.value = path;
        loadFile();
    }
});

function bindEvents() {
    btnBrowseFile.addEventListener('click', browseFile);
    btnLoadFile.addEventListener('click', loadFile);
    btnSaveMeta.addEventListener('click', saveMetadata);
    btnAutoSearch.addEventListener('click', autoSearch);

    fileInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loadFile();
    });
}

// ------------------------------------------------------------------
// Dialogo nativo para seleccionar archivo
// (Reusa el dialogo de carpeta del backend, pero el usuario puede
//  navegar hasta el archivo. Como tkinter askopenfilename filtraria
//  por extension, hacemos una version ligera: pedimos carpeta y el
//  usuario escribe/copi la ruta del archivo.
//  Alternativa mas practica: solo escribir la ruta.)
// ------------------------------------------------------------------
async function browseFile() {
    // Como tkinter askdirectory esta disponible, lo usamos para que el
    // usuario encuentre la carpeta y luego pegue el nombre del archivo.
    btnBrowseFile.disabled = true;
    try {
        const data = await getJSON('/api/browse');
        if (data.folder) {
            // Si el input esta vacio, poner la carpeta; si no, append
            if (!fileInput.value) {
                fileInput.value = data.folder;
            }
            showToast('Carpeta seleccionada. Copia el archivo completo o edita la ruta.', '', 4000);
        }
    } catch (e) {
        showToast('No se pudo abrir el dialogo: ' + e.message, 'error');
    } finally {
        btnBrowseFile.disabled = false;
    }
}

// ------------------------------------------------------------------
// Cargar metadata del archivo
// ------------------------------------------------------------------
async function loadFile() {
    const path = fileInput.value.trim();
    if (!path) {
        showToast('Indica la ruta de un archivo.', 'error');
        return;
    }

    btnLoadFile.disabled = true;
    btnLoadFile.textContent = 'Cargando...';

    try {
        const data = await postJSON('/api/file-metadata', { path });
        currentFilePath = path;

        // Rellenar formulario
        metaTitle.value  = data.title || '';
        metaArtist.value = data.artist || '';
        metaAlbum.value  = data.album || '';
        metaDate.value   = data.date || '';
        metaTrack.value  = data.track || '';
        metaGenre.value  = data.genre || '';

        // Mostrar ruta
        currentFilePathEl.textContent = path;

        // Mostrar info tecnica
        renderTechInfo(data.quality, data);

        // Mostrar panel
        editorPanel.classList.remove('hidden');
        emptyEditor.classList.add('hidden');

        // Limpiar resultados iTunes previos
        itunesResults.innerHTML = '<p class="empty-hint">Sin resultados aun. Pulsa "Buscar en iTunes".</p>';
        currentItunesResults = [];

        showToast('Archivo cargado.', 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error', 5000);
    } finally {
        btnLoadFile.disabled = false;
        btnLoadFile.textContent = 'Cargar';
    }
}

// ------------------------------------------------------------------
// Renderizar info tecnica (read-only)
// ------------------------------------------------------------------
function renderTechInfo(quality, data) {
    if (!quality) {
        techGrid.innerHTML = '<div class="tech-item"><span class="tech-item-label">Sin info</span></div>';
        return;
    }
    const d = quality.details;
    techGrid.innerHTML = `
        <div class="tech-item"><span class="tech-item-label">Profundidad</span><span class="tech-item-value">${escapeHtml(d.bit_depth)}</span></div>
        <div class="tech-item"><span class="tech-item-label">Sample rate</span><span class="tech-item-value">${escapeHtml(d.sample_rate)}</span></div>
        <div class="tech-item"><span class="tech-item-label">Bitrate</span><span class="tech-item-value">${escapeHtml(d.bitrate)}</span></div>
        <div class="tech-item"><span class="tech-item-label">Canales</span><span class="tech-item-value">${escapeHtml(d.channels)}</span></div>
        <div class="tech-item"><span class="tech-item-label">Duracion</span><span class="tech-item-value">${escapeHtml(d.duration)}</span></div>
        <div class="tech-item"><span class="tech-item-label">Clasif.</span><span class="tech-item-value">${escapeHtml(quality.description)}</span></div>
    `;
}

// ------------------------------------------------------------------
// Buscar en iTunes
// ------------------------------------------------------------------
async function autoSearch() {
    const title = metaTitle.value.trim();
    const artist = metaArtist.value.trim();

    if (!title) {
        showToast('Se necesita al menos el titulo.', 'error');
        return;
    }

    btnAutoSearch.disabled = true;
    btnAutoSearch.textContent = 'Buscando...';
    itunesResults.innerHTML = '<p class="empty-hint">Buscando en iTunes...</p>';

    try {
        const data = await postJSON('/api/auto-search', { title, artist });

        if (data.message) {
            itunesResults.innerHTML = `<p class="empty-hint">${escapeHtml(data.message)}</p>`;
            return;
        }

        currentItunesResults = data.results;
        renderItunesResults(data.results, data.best);
    } catch (e) {
        itunesResults.innerHTML = `<p class="empty-hint">Error: ${escapeHtml(e.message)}</p>`;
    } finally {
        btnAutoSearch.disabled = false;
        btnAutoSearch.textContent = 'Buscar en iTunes';
    }
}

function renderItunesResults(results, best) {
    if (!results || results.length === 0) {
        itunesResults.innerHTML = '<p class="empty-hint">Sin resultados.</p>';
        return;
    }

    itunesResults.innerHTML = '';
    results.forEach((r, idx) => {
        const div = document.createElement('div');
        div.className = 'itunes-result';
        if (best && r.title === best.title && r.artist === best.artist) {
            div.style.borderColor = 'var(--accent)';
        }

        div.innerHTML = `
            <div class="itunes-result-title">${escapeHtml(r.title)}</div>
            <div class="itunes-result-meta">${escapeHtml(r.artist)} ${r.year ? '• ' + escapeHtml(r.year) : ''}</div>
            ${r.album ? `<div class="itunes-result-album">${escapeHtml(r.album)}</div>` : ''}
        `;

        // Al hacer clic, rellenar el formulario
        div.addEventListener('click', () => {
            applyItunesResult(r);
        });

        itunesResults.appendChild(div);
    });
}

function applyItunesResult(r) {
    if (r.title)  metaTitle.value  = r.title;
    if (r.artist) metaArtist.value = r.artist;
    if (r.album)  metaAlbum.value  = r.album;
    if (r.year)   metaDate.value   = r.year;
    if (r.genre)  metaGenre.value  = r.genre;
    if (r.track_number) metaTrack.value = r.track_number;
    showToast(`Rellenado con: ${r.title} - ${r.artist}`, 'success');
}

// ------------------------------------------------------------------
// Guardar metadata
// ------------------------------------------------------------------
async function saveMetadata() {
    if (!currentFilePath) {
        showToast('Carga un archivo primero.', 'error');
        return;
    }

    const metadata = {
        title:  metaTitle.value.trim(),
        artist: metaArtist.value.trim(),
        album:  metaAlbum.value.trim(),
        date:   metaDate.value.trim(),
        track:  metaTrack.value.trim(),
        genre:  metaGenre.value.trim(),
    };

    btnSaveMeta.disabled = true;
    btnSaveMeta.textContent = 'Guardando...';

    try {
        const data = await postJSON('/api/save-metadata', {
            path: currentFilePath,
            metadata: metadata,
        });
        showToast(data.message, 'success');
    } catch (e) {
        showToast('Error al guardar: ' + e.message, 'error', 5000);
    } finally {
        btnSaveMeta.disabled = false;
        btnSaveMeta.textContent = 'Guardar cambios';
    }
}
