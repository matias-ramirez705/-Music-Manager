/*
 * static/js/spotiflac.js (v3.16)
 * =================================
 * Lógica de la pestaña "Spotiflac Dummies".
 *
 * Funcionalidades:
 *  - Previsualiza qué archivos se generarían como dummy
 *  - Genera el ZIP de dummies y lo descarga al navegador
 *  - Muestra el historial de dummies ya generados
 *  - Permite vaciar el historial
 *
 * Dependencias (de app.js):
 *  - getJSON / postJSON
 *  - showToast(msg, type)
 *  - escapeHtml(s)
 */

// ------------------------------------------------------------------
// Refs al DOM
// ------------------------------------------------------------------
const spStatus = document.getElementById('sp-status');
const spStatusText = document.getElementById('sp-status-text');
const spStats = document.getElementById('sp-stats');
const spTotal = document.getElementById('sp-total');
const spToGenerate = document.getElementById('sp-to-generate');
const spAlready = document.getElementById('sp-already');
const spHistoryCount = document.getElementById('sp-history-count');
const spOptions = document.getElementById('sp-options');
const spOnlyNew = document.getElementById('sp-only-new');
const spNaming = document.getElementById('sp-naming');
const btnPreview = document.getElementById('btn-sp-preview');
const btnGenerate = document.getElementById('btn-sp-generate');
const btnClearHistory = document.getElementById('btn-sp-clear-history');
const spPreviewContainer = document.getElementById('sp-preview-container');
const spTbody = document.getElementById('sp-tbody');
const spEmpty = document.getElementById('sp-empty');
const spLoading = document.getElementById('sp-loading');
const spLoadingText = document.getElementById('sp-loading-text');
const spResult = document.getElementById('sp-result');
const spResultContent = document.getElementById('sp-result-content');
const spHistoryContainer = document.getElementById('sp-history-container');
const spHistoryTbody = document.getElementById('sp-history-tbody');

// Estado
let lastPreview = null;

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    btnPreview.addEventListener('click', loadPreview);
    btnGenerate.addEventListener('click', generateZip);
    btnClearHistory.addEventListener('click', confirmClearHistory);
    spOnlyNew.addEventListener('change', () => {
        // Si cambia el checkbox, recargar preview si ya estaba cargado
        if (lastPreview) loadPreview();
    });

    // Cargar historial al inicio
    loadHistory();
    // Intentar cargar preview automáticamente (si hay música escaneada)
    loadPreview();
});

// ------------------------------------------------------------------
// Preview
// ------------------------------------------------------------------
async function loadPreview() {
    spLoadingText.textContent = 'Analizando biblioteca...';
    spLoading.classList.remove('hidden');
    spEmpty.classList.add('hidden');
    spPreviewContainer.classList.add('hidden');
    spStats.classList.add('hidden');
    spOptions.classList.add('hidden');
    spStatus.style.display = 'none';

    try {
        const data = await postJSON('/api/spotiflac/preview', {
            only_new: spOnlyNew.checked,
        });
        if (data.error) {
            spStatusText.textContent = data.error;
            spStatus.style.display = 'flex';
            spEmpty.classList.remove('hidden');
            return;
        }
        lastPreview = data;
        renderStats(data);
        renderPreview(data.to_generate);
        spOptions.classList.remove('hidden');
        spStats.classList.remove('hidden');
        if (data.to_generate.length === 0 && data.already_generated === 0) {
            spEmpty.classList.remove('hidden');
        } else {
            spPreviewContainer.classList.remove('hidden');
        }
    } catch (e) {
        spStatusText.textContent = 'Error: ' + e.message;
        spStatus.style.display = 'flex';
    } finally {
        spLoading.classList.add('hidden');
    }
}

function renderStats(data) {
    spTotal.textContent = data.total;
    spToGenerate.textContent = data.to_generate.length;
    spAlready.textContent = data.already_generated;
    // by_format
    const byFormat = data.by_format || {};
    const fmtParts = Object.entries(byFormat)
        .sort((a, b) => b[1] - a[1])
        .map(([ext, count]) => `${ext.toUpperCase()}: ${count}`);
    spToGenerate.title = fmtParts.length ? fmtParts.join('\n') : '';
}

function renderPreview(files) {
    spTbody.innerHTML = '';
    if (files.length === 0) {
        spTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--text-muted);">' +
            'No hay archivos nuevos para generar. Todos ya están en el historial. ' +
            'Desmarca "Solo generar nuevos" si querés regenerar todo.' +
            '</td></tr>';
        return;
    }
    // Limitar a 500 filas para no congelar el navegador con bibliotecas grandes
    const MAX_ROWS = 500;
    const shown = files.slice(0, MAX_ROWS);
    shown.forEach((f, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary);">${escapeHtml(f.filename)}</td>
            <td><strong>${escapeHtml(f.name || '—')}</strong></td>
            <td>${escapeHtml(f.artist || '—')}</td>
            <td style="text-align:center;"><span class="format-badge ${escapeHtml(f.ext.toLowerCase())}">${escapeHtml(f.ext.toUpperCase())}</span></td>
        `;
        spTbody.appendChild(tr);
    });
    if (files.length > MAX_ROWS) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="5" style="text-align:center; padding:12px; color:var(--text-muted); font-style:italic;">
            ... y ${files.length - MAX_ROWS} archivos más (no se muestran para no congelar el navegador)
        </td>`;
        spTbody.appendChild(tr);
    }
}

// ------------------------------------------------------------------
// Generar ZIP
// ------------------------------------------------------------------
async function generateZip() {
    if (!lastPreview || lastPreview.to_generate.length === 0) {
        showToast('No hay archivos para generar. Desmarca "Solo generar nuevos" si querés regenerar todo.', 'info');
        return;
    }

    const count = lastPreview.to_generate.length;
    if (!confirm(`¿Generar ZIP con ${count} archivos dummy?\n\n` +
                 `Modo de nombres: ${spNaming.value === 'original' ? 'Nombre original' : 'Formato Spotiflac (Título - Artista.ext)'}\n` +
                 `Se descargar un archivo .zip que debés descomprimir en tu teléfono.`)) {
        return;
    }

    spLoadingText.textContent = `Generando ZIP con ${count} archivos...`;
    spLoading.classList.remove('hidden');
    btnGenerate.disabled = true;
    btnGenerate.textContent = 'Generando...';
    spResult.classList.add('hidden');

    try {
        const resp = await fetch('/api/spotiflac/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                only_new: spOnlyNew.checked,
                naming_mode: spNaming.value,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }

        // Leer stats del header antes de consumir el body
        const statsHeader = resp.headers.get('X-Spotiflac-Stats');
        let stats = null;
        if (statsHeader) {
            try { stats = JSON.parse(statsHeader); } catch (e) {}
        }

        // Descargar el ZIP
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // Intentar extraer el filename del Content-Disposition
        const cd = resp.headers.get('Content-Disposition') || '';
        const fnMatch = cd.match(/filename="([^"]+)"/);
        a.download = fnMatch ? fnMatch[1] : 'spotiflac_dummies.zip';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // Mostrar resultado
        if (stats) {
            renderResult(stats);
        } else {
            spResultContent.innerHTML = '✓ ZIP descargado.';
        }
        spResult.classList.remove('hidden');

        // Recargar preview (ahora los generados pasan al historial)
        await loadPreview();
        await loadHistory();
        showToast(`ZIP generado con ${stats ? stats.count : count} archivos.`, 'success');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        spLoading.classList.add('hidden');
        btnGenerate.disabled = false;
        btnGenerate.textContent = '⬇ Generar ZIP';
    }
}

function renderResult(stats) {
    const byFormat = stats.by_format || {};
    const fmtHtml = Object.entries(byFormat)
        .sort((a, b) => b[1] - a[1])
        .map(([ext, count]) => `<span class="format-badge ${escapeHtml(ext.toLowerCase())}" style="margin-right:6px;">${escapeHtml(ext.toUpperCase())}: ${count}</span>`)
        .join('');
    let html = `
        <p><strong>${stats.count}</strong> archivos dummy generados y descargados.</p>
    `;
    if (fmtHtml) {
        html += `<p style="margin:8px 0;">Por formato: ${fmtHtml}</p>`;
    }
    if (stats.already_generated > 0) {
        html += `<p style="font-size:12px; color:var(--text-muted); margin-top:8px;">${stats.already_generated} archivos se saltaron porque ya estaban en el historial.</p>`;
    }
    if (stats.errors && stats.errors.length > 0) {
        html += `<p style="color:var(--warning); margin-top:8px;">⚠ ${stats.errors.length} errores: ${escapeHtml(stats.errors[0].error)}${stats.errors.length > 1 ? ` (y ${stats.errors.length - 1} más)` : ''}</p>`;
    }
    html += `<p style="margin-top:12px; font-size:13px;">Pasá el ZIP a tu teléfono y descomprimilo en:</p>
             <p style="font-family:var(--font-mono); font-size:11px; background:var(--bg-card); padding:8px; border-radius:4px; margin-top:4px;">/storage/emulated/0/Music/SpotyFlac/</p>
             <p style="font-size:13px; margin-top:8px;">Después: Spotiflac → Biblioteca Local → escanear.</p>`;
    spResultContent.innerHTML = html;
}

// ------------------------------------------------------------------
// Historial
// ------------------------------------------------------------------
async function loadHistory() {
    try {
        const data = await getJSON('/api/spotiflac/history');
        spHistoryCount.textContent = data.count;
        if (data.count === 0) {
            spHistoryContainer.classList.add('hidden');
            return;
        }
        spHistoryContainer.classList.remove('hidden');
        spHistoryTbody.innerHTML = '';
        // Mostrar las últimas 200 (las más recientes primero)
        const recent = (data.generated || []).slice().reverse().slice(0, 200);
        recent.forEach((g, idx) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${idx + 1}</td>
                <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary);">${escapeHtml(g.filename)}</td>
                <td><strong>${escapeHtml(g.name || '—')}</strong></td>
                <td>${escapeHtml(g.artist || '—')}</td>
                <td style="font-size:11px; color:var(--text-muted);">${escapeHtml(g.generated_at || '—')}</td>
            `;
            spHistoryTbody.appendChild(tr);
        });
    } catch (e) {
        // Silencioso: el historial es opcional
        console.error('Error cargando historial:', e);
    }
}

// ------------------------------------------------------------------
// Limpiar historial
// ------------------------------------------------------------------
function confirmClearHistory() {
    if (!confirm('¿Vaciar el historial de dummies generados?\n\n' +
                 'La próxima vez se volverán a generar TODAS las canciones.\n' +
                 'Esto NO borra ningún archivo del disco ni del teléfono.')) {
        return;
    }
    clearHistory();
}

async function clearHistory() {
    try {
        const resp = await fetch('/api/spotiflac/clear-history', { method: 'POST' });
        if (!resp.ok) throw new Error('Error al limpiar historial');
        const data = await resp.json();
        showToast(`Historial vaciado. ${data.removed} entradas eliminadas.`, 'success');
        await loadHistory();
        await loadPreview();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
