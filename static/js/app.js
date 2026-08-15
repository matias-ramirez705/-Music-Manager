/* ============================================
   app.js - Utilidades compartidas
   ============================================ */

/**
 * Muestra un toast (notificacion temporal).
 * @param {string} message - Texto a mostrar.
 * @param {string} type    - 'success' | 'error' | '' (info).
 * @param {number} duration - Milisegundos (default 3000).
 */
function showToast(message, type = '', duration = 3000) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    setTimeout(() => {
        toast.className = 'toast';
    }, duration);
}

/**
 * Hace una peticion POST al servidor con JSON.
 * @param {string} url  - Ruta de la API.
 * @param {object} data - Cuerpo JSON.
 * @returns {Promise<object>} - Respuesta parseada como JSON.
 */
async function postJSON(url, data = {}) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    const result = await resp.json();
    if (!resp.ok) {
        throw new Error(result.error || `Error ${resp.status}`);
    }
    return result;
}

/**
 * Hace una peticion GET al servidor.
 */
async function getJSON(url) {
    const resp = await fetch(url);
    const result = await resp.json();
    if (!resp.ok) {
        throw new Error(result.error || `Error ${resp.status}`);
    }
    return result;
}

/**
 * Formatea segundos como M:SS o H:MM:SS.
 * (Duplicado del backend por si acaso.)
 */
function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '0:00';
    seconds = Math.floor(seconds);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
}

/**
 * Escapa HTML para evitar inyeccion al construir strings.
 */
function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Crea un elemento con clase y contenido.
 */
function el(tag, className, textContent) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (textContent != null) e.textContent = textContent;
    return e;
}

/**
 * Abre el explorador de archivos del sistema en la carpeta del archivo.
 * @param {string} encodedPath - ruta codificada con encodeURIComponent.
 */
async function revealInExplorer(encodedPath) {
    const path = decodeURIComponent(encodedPath);
    try {
        const data = await postJSON('/api/reveal-in-explorer', { path: path });
        if (data.success) {
            showToast('Abriendo explorador...', '', 2000);
        } else {
            showToast('Error: ' + (data.message || 'No se pudo abrir'), 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

/**
 * Copia "titulo - artista" al portapapeles.
 * @param {string} name - nombre/titulo de la cancion.
 * @param {string} artist - artista.
 */
async function copySongInfo(name, artist) {
    const text = artist ? name + ' - ' + artist : name;
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copiado: ' + text, 'success', 2000);
    } catch (e) {
        // Fallback
        const tmp = document.createElement('input');
        tmp.value = text;
        document.body.appendChild(tmp);
        tmp.select();
        try {
            document.execCommand('copy');
            showToast('Copiado: ' + text, 'success', 2000);
        } catch (err) {
            showToast('No se pudo copiar.', 'error');
        }
        document.body.removeChild(tmp);
    }
}
