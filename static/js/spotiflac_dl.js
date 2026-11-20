/*
 * static/js/spotiflac_dl.js (v4.0)
 * =================================
 * Lógica de la pestaña "Spotiflac DL" con 3 sub-pestañas:
 *   1. Buscar (búsqueda individual por nombre/URL)
 *   2. Mejorar Calidad (lista tu música local, descarga FLAC de las que están en MP3)
 *   3. Por Playlist (selecciona playlist guardada, descarga faltantes)
 *
 * Requiere que el módulo SpotiFLAC esté instalado (pip install SpotiFLAC)
 * y al menos una extensión configurada.
 */

// ------------------------------------------------------------------
// Estado global
// ------------------------------------------------------------------
let spdlModuleReady = false;
let spdlSearchResults = [];
let spdlImproveSongs = [];
let spdlPlaylistTracks = [];
let spdlCurrentJobPoller = null;

// v4.3: carpeta de descarga recordada (compartida entre las 3 sub-pestañas)
const SPDL_OUTPUT_DIR_KEY = 'spdl_output_dir';
function getSavedOutputDir() {
    return localStorage.getItem(SPDL_OUTPUT_DIR_KEY) || '';
}
function setSavedOutputDir(dir) {
    if (dir) localStorage.setItem(SPDL_OUTPUT_DIR_KEY, dir);
}
// Helper único: lee la carpeta de cualquiera de los 3 inputs (todos sincronizados)
function getOutputDir() {
    return $('spdl-output-dir').value.trim() || $('spdl-improve-dir').value.trim() || $('spdl-playlist-dir').value.trim() || getSavedOutputDir();
}
// Helper: sincroniza los 3 inputs con el mismo valor
function syncOutputDirs(dir) {
    if (!dir) return;
    ['spdl-output-dir', 'spdl-improve-dir', 'spdl-playlist-dir'].forEach(id => {
        const el = $(id);
        if (el && !el.value.trim()) el.value = dir;
    });
    setSavedOutputDir(dir);
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function $(id) { return document.getElementById(id); }
function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function showToast(msg, type = 'info', duration = 3000) {
    // Reutilizar el toast global si existe
    if (typeof window.showToast === 'function') {
        window.showToast(msg, type, duration);
    } else {
        const t = $('spdl-toast') || $('toast');
        if (t) {
            t.textContent = msg;
            t.className = 'toast ' + type;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, duration);
        }
    }
}
async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}
async function postJSON(url, body) {
    const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
    });
    return r.json();
}
function formatDuration(ms) {
    if (!ms || ms <= 0) return '—';
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2, '0')}`;
}

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // Sub-pestañas
    document.querySelectorAll('[data-spdl-subtab]').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const target = tab.dataset.spdlSubtab;
            document.querySelectorAll('[data-spdl-subtab]').forEach(t => t.classList.toggle('active', t === tab));
            ['search', 'improve', 'playlist', 'queue'].forEach(s => {
                $(`spdl-subtab-${s}`).classList.toggle('hidden', s !== target);
            });
            // Cargar datos de la sub-pestaña al activarla
            if (target === 'improve' && spdlImproveSongs.length === 0) loadImproveSongs();
            if (target === 'playlist' && $('spdl-playlist-select').options.length <= 1) loadPlaylistsList();
            if (target === 'queue') loadQueue();
        });
    });

    // Estado del módulo
    loadModuleStatus();
    // Estado del registry (.env)
    loadRegistryConfig();

    // v4.3: Cargar carpeta recordada en los 3 inputs
    const savedDir = getSavedOutputDir();
    if (savedDir) {
        ['spdl-output-dir', 'spdl-improve-dir', 'spdl-playlist-dir'].forEach(id => {
            const el = $(id);
            if (el) el.value = savedDir;
        });
    }
    // Sincronizar cuando cualquiera de los 3 inputs cambia (oninput/onchange)
    ['spdl-output-dir', 'spdl-improve-dir', 'spdl-playlist-dir'].forEach(id => {
        const el = $(id);
        if (el) {
            el.addEventListener('change', () => {
                const v = el.value.trim();
                if (v) syncOutputDirs(v);
            });
        }
    });

    // Botones
    $('btn-spdl-install').addEventListener('click', () => installModule(false));
    $('btn-spdl-upgrade').addEventListener('click', () => installModule(true));
    $('btn-spdl-search').addEventListener('click', doSearch);
    $('spdl-search-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    // v4.3: browseFolder ahora sincroniza los 3 inputs
    $('btn-spdl-browse').addEventListener('click', () => browseFolder('spdl-output-dir', true));
    $('btn-spdl-improve-browse').addEventListener('click', () => browseFolder('spdl-improve-dir', true));
    $('btn-spdl-playlist-browse').addEventListener('click', () => browseFolder('spdl-playlist-dir', true));
    $('btn-spdl-load-playlist').addEventListener('click', loadPlaylistTracks);
    $('btn-spdl-download-all-missing').addEventListener('click', downloadAllMissing);
    $('btn-spdl-manage-ext').addEventListener('click', openExtensionsModal);

    // Botones de configuración del registry (v4.1)
    $('btn-spdl-config-registry').addEventListener('click', openEnvModal);
    $('btn-spdl-auto-config').addEventListener('click', autoConfigRegistry);
    $('btn-spdl-env-close').addEventListener('click', () => $('spdl-env-modal').classList.add('hidden'));
    $('btn-spdl-env-save').addEventListener('click', saveEnvConfig);
    $('btn-spdl-use-default-registry').addEventListener('click', () => {
        $('spdl-env-registries').value = 'https://raw.githubusercontent.com/spotiflacapp/SpotiFLAC-Extension/main/registry.json';
    });
    $('spdl-env-modal').addEventListener('click', (e) => {
        if (e.target === $('spdl-env-modal')) $('spdl-env-modal').classList.add('hidden');
    });
    document.querySelector('#spdl-env-modal .modal-close').addEventListener('click', () => {
        $('spdl-env-modal').classList.add('hidden');
    });

    // Botones de cola de descargas (v4.2)
    $('btn-spdl-refresh-queue').addEventListener('click', loadQueue);
    $('btn-spdl-clear-completed').addEventListener('click', clearCompletedJobs);

    // Modal de extensiones
    document.querySelector('#spdl-ext-modal .modal-close').addEventListener('click', () => {
        $('spdl-ext-modal').classList.add('hidden');
    });
    $('spdl-ext-modal').addEventListener('click', (e) => {
        if (e.target === $('spdl-ext-modal')) $('spdl-ext-modal').classList.add('hidden');
    });

    // Filtros de mejorar
    $('spdl-improve-search').addEventListener('input', renderImproveTable);
    $('spdl-improve-filter-quality').addEventListener('change', renderImproveTable);
});

// ------------------------------------------------------------------
// Estado del módulo
// ------------------------------------------------------------------
async function loadModuleStatus() {
    try {
        const data = await getJSON('/api/spotiflac-dl/status');
        renderModuleStatus(data);
        if (data.installed) {
            spdlModuleReady = true;
            loadExtensionsList();
        }
    } catch (e) {
        renderModuleStatus({ installed: false, error: e.message });
    }
}

function renderModuleStatus(data) {
    const icon = $('spdl-status-icon');
    const title = $('spdl-status-title');
    const detail = $('spdl-status-detail');
    const btnInstall = $('btn-spdl-install');
    const btnUpgrade = $('btn-spdl-upgrade');

    if (data.installed) {
        icon.textContent = '✓';
        icon.style.color = 'var(--accent)';
        title.textContent = `Módulo SpotiFLAC instalado (v${data.version})`;
        if (data.update_available) {
            detail.textContent = `Actualización disponible: v${data.latest_version}`;
            btnUpgrade.classList.remove('hidden');
            btnUpgrade.textContent = `Actualizar a v${data.latest_version}`;
        } else if (data.latest_version) {
            detail.textContent = `Estás en la última versión.`;
            btnUpgrade.classList.add('hidden');
        } else {
            detail.textContent = 'No se pudo verificar la última versión (sin internet?).';
            btnUpgrade.classList.add('hidden');
        }
        btnInstall.classList.add('hidden');
    } else {
        icon.textContent = '⚠';
        icon.style.color = 'var(--warning)';
        title.textContent = 'Módulo SpotiFLAC no instalado';
        detail.textContent = 'Hacé clic en "Instalar" para descargarlo desde PyPI (pip install SpotiFLAC).';
        btnInstall.classList.remove('hidden');
        btnUpgrade.classList.add('hidden');
    }
}

async function installModule(upgrade) {
    const btn = upgrade ? $('btn-spdl-upgrade') : $('btn-spdl-install');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Instalando... (puede tardar 1-2 min)';
    try {
        const data = await postJSON('/api/spotiflac-dl/install', { upgrade });
        if (data.success) {
            showToast(`SpotiFLAC v${data.installed_version} instalado. Recargando página...`, 'success', 3000);
            // v4.4: recargar la página automáticamente tras 2 segundos
            // para que el banner se actualice y spdlModuleReady se recalcule.
            setTimeout(() => window.location.reload(), 2000);
        } else {
            showToast('Error al instalar: ' + (data.error || 'desconocido'), 'error', 6000);
            console.error('pip output:', data.output);
            console.error('pip error:', data.error);
            btn.disabled = false;
            btn.textContent = originalText;
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// ------------------------------------------------------------------
// Extensiones
// ------------------------------------------------------------------
async function loadExtensionsList() {
    try {
        const data = await getJSON('/api/spotiflac-dl/extensions');
        if (data.error) {
            $('spdl-extensions-list').textContent = 'Error: ' + data.error;
            return;
        }
        const exts = data.extensions || [];
        if (exts.length === 0) {
            $('spdl-extensions-list').innerHTML = '<span style="color:var(--warning);">Ninguna extensión instalada. Necesitas instalar al menos una para descargar.</span>';
        } else {
            $('spdl-extensions-list').innerHTML = exts.map(e =>
                `<span class="format-badge" style="margin-right:4px;" title="${escapeHtml(e.description)}">${escapeHtml(e.display_name)} v${escapeHtml(e.version)}</span>`
            ).join('');
        }
    } catch (e) {
        $('spdl-extensions-list').textContent = 'Error: ' + e.message;
    }
}

async function openExtensionsModal() {
    $('spdl-ext-modal').classList.remove('hidden');
    $('spdl-installed-ext-list').innerHTML = '<p style="color:var(--text-muted);">Cargando...</p>';
    $('spdl-registry-ext-list').innerHTML = '<p style="color:var(--text-muted);">Cargando...</p>';

    // Cargar ambas listas en paralelo para ir más rápido
    const [installedRes, registryRes] = await Promise.allSettled([
        getJSON('/api/spotiflac-dl/extensions'),
        getJSON('/api/spotiflac-dl/registry'),
    ]);

    // Procesar instaladas
    const installedExts = installedRes.status === 'fulfilled' ? (installedRes.value.extensions || []) : [];
    const installedIds = new Set(installedExts.map(e => e.id));

    if (installedRes.status !== 'fulfilled') {
        $('spdl-installed-ext-list').innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(installedRes.reason.message)}</p>`;
    } else if (installedExts.length === 0) {
        $('spdl-installed-ext-list').innerHTML = '<p style="color:var(--text-muted);">Ninguna instalada.</p>';
    } else {
        $('spdl-installed-ext-list').innerHTML = installedExts.map(e => `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:8px; border-bottom:1px solid var(--border);">
                <div>
                    <strong>${escapeHtml(e.display_name)}</strong> <span style="color:var(--text-muted); font-size:11px;">v${escapeHtml(e.version)} (${escapeHtml(e.runtime)})</span><br>
                    <span style="font-size:11px; color:var(--text-secondary);">${escapeHtml(e.description)}</span>
                </div>
                <button class="btn btn-ghost btn-sm" onclick="removeExtension('${escapeHtml(e.id)}')">Eliminar</button>
            </div>
        `).join('');
    }

    // Procesar registry — marcar las ya instaladas
    if (registryRes.status !== 'fulfilled') {
        $('spdl-registry-ext-list').innerHTML = `<p style="color:var(--danger);">Error: ${escapeHtml(registryRes.reason.message)}</p>`;
    } else {
        const data = registryRes.value;
        if (data.error) {
            $('spdl-registry-ext-list').innerHTML = `<p style="color:var(--warning);">${escapeHtml(data.error)}</p>
                <p style="font-size:12px;">Para configurar el registry, hacé clic en "Configurar" en el banner de registry arriba.</p>`;
        } else {
            const exts = data.extensions || [];
            if (exts.length === 0) {
                $('spdl-registry-ext-list').innerHTML = '<p style="color:var(--text-muted);">El registry no tiene extensiones.</p>';
            } else {
                $('spdl-registry-ext-list').innerHTML = exts.map(e => {
                    const isInstalled = installedIds.has(e.id);
                    const buttonHtml = isInstalled
                        ? '<span style="color:var(--accent); font-size:12px;">✓ Instalada</span>'
                        : `<button class="btn btn-secondary btn-sm" onclick="installExtension('${escapeHtml(e.id)}')">Instalar</button>`;
                    return `
                        <div style="display:flex; justify-content:space-between; align-items:center; padding:8px; border-bottom:1px solid var(--border);${isInstalled ? ' opacity:0.6;' : ''}">
                            <div>
                                <strong>${escapeHtml(e.display_name)}</strong> <span style="color:var(--text-muted); font-size:11px;">v${escapeHtml(e.version)}</span><br>
                                <span style="font-size:11px; color:var(--text-secondary);">${escapeHtml(e.description)}</span>
                            </div>
                            ${buttonHtml}
                        </div>
                    `;
                }).join('');
            }
        }
    }
}

async function installExtension(extId) {
    showToast(`Instalando ${extId}...`, 'info');
    try {
        const data = await postJSON('/api/spotiflac-dl/extensions/install', { ext_id: extId });
        if (data.success) {
            showToast(`Extensión ${extId} instalada.`, 'success');
            // v4.4: refrescar el modal Y la lista de extensiones del banner
            await openExtensionsModal();
            loadExtensionsList();
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error', 6000);
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
window.installExtension = installExtension;

async function removeExtension(extId) {
    if (!confirm(`¿Eliminar extensión "${extId}"?`)) return;
    try {
        const resp = await fetch(`/api/spotiflac-dl/extensions/${encodeURIComponent(extId)}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            showToast(`Extensión ${extId} eliminada.`, 'success');
            // v4.4: refrescar el modal Y la lista de extensiones del banner
            await openExtensionsModal();
            loadExtensionsList();
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
window.removeExtension = removeExtension;

// ------------------------------------------------------------------
// Sub-pestaña 1: Buscar
// ------------------------------------------------------------------
async function doSearch() {
    const query = $('spdl-search-input').value.trim();
    if (!query) return;
    if (!spdlModuleReady) {
        showToast('Instalá el módulo SpotiFLAC primero.', 'error');
        return;
    }
    // Si parece una URL de Spotify, ir directo a descarga
    if (query.includes('open.spotify.com/') || query.startsWith('spotify:')) {
        startDownload([query], $('spdl-output-dir').value.trim());
        return;
    }
    const btn = $('btn-spdl-search');
    btn.disabled = true;
    btn.textContent = 'Buscando...';
    try {
        const data = await postJSON('/api/spotiflac-dl/search', { query, limit: 30 });
        if (data.error) {
            showToast('Error: ' + data.error, 'error', 6000);
            return;
        }
        spdlSearchResults = data.results || [];
        renderSearchResults();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🔍 Buscar';
    }
}

function renderSearchResults() {
    const tbody = $('spdl-search-tbody');
    tbody.innerHTML = '';
    if (spdlSearchResults.length === 0) {
        $('spdl-search-results').classList.add('hidden');
        showToast('Sin resultados.', 'info');
        return;
    }
    $('spdl-search-results').classList.remove('hidden');
    spdlSearchResults.forEach((t, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td><strong>${escapeHtml(t.title)}</strong></td>
            <td>${escapeHtml(t.artists)}</td>
            <td>${escapeHtml(t.album)}</td>
            <td style="text-align:center; font-family:var(--font-mono); font-size:11px;">${formatDuration(t.duration_ms)}</td>
            <td></td>
        `;
        const dlCell = tr.children[5];
        const btn = document.createElement('button');
        btn.className = 'btn btn-primary btn-sm';
        btn.textContent = '⬇ Descargar';
        btn.addEventListener('click', () => {
            const url = t.external_url || `https://open.spotify.com/track/${t.id}`;
            startDownload([url], $('spdl-output-dir').value.trim());
        });
        dlCell.appendChild(btn);
        tbody.appendChild(tr);
    });
}

// ------------------------------------------------------------------
// Descarga con tracking de progreso
// ------------------------------------------------------------------
async function startDownload(urls, outputDir) {
    // v4.3: si no se pasó outputDir, usar el helper que lee de cualquier input o localStorage
    if (!outputDir) outputDir = getOutputDir();
    if (!outputDir) {
        showToast('Indicá una carpeta de destino.', 'error');
        return;
    }
    // v4.4: quitar el checkeo de spdlModuleReady aquí — el backend valida
    // si el módulo está instalado y devuelve error claro si no.
    // Antes: if (!spdlModuleReady) { showToast('Instalá...'); return; }
    // Eso causaba que si el usuario instalaba SpotiFLAC sin recargar la página,
    // los botones de descarga no hicieran nada.
    // v4.3: guardar la carpeta usada para recordar la próxima vez
    setSavedOutputDir(outputDir);
    const quality = $('spdl-quality') ? $('spdl-quality').value : 'LOSSLESS';
    try {
        const data = await postJSON('/api/spotiflac-dl/download', {
            urls, output_dir: outputDir, quality
        });
        if (data.error) {
            showToast('Error: ' + data.error, 'error', 6000);
            return;
        }
        showToast(`Descarga iniciada (job ${data.job_id}). ${urls.length} URL(s).`, 'success');
        // v4.2: cambiar automáticamente a la sub-pestaña Cola para que se vea el progreso
        const queueTab = document.querySelector('[data-spdl-subtab="queue"]');
        if (queueTab) queueTab.click();
        // Cargar la cola inmediatamente
        loadQueue();
        return data.job_id;  // v4.3: devolver job_id para que el llamador pueda trackear
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function pollJobStatus(jobId) {
    if (spdlCurrentJobPoller) clearInterval(spdlCurrentJobPoller);
    spdlCurrentJobPoller = setInterval(async () => {
        try {
            const data = await getJSON(`/api/spotiflac-dl/jobs/${jobId}`);
            renderJobStatus(data);
            if (data.status === 'completed' || data.status === 'error') {
                clearInterval(spdlCurrentJobPoller);
                spdlCurrentJobPoller = null;
                if (data.status === 'completed') {
                    showToast(`Descarga completada: ${data.done}/${data.total} (${data.failed} fallidos)`, 'success');
                } else {
                    showToast('Descarga con errores.', 'error', 6000);
                }
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 1500);
}

function renderJobStatus(data) {
    const logs = $('spdl-download-logs');
    logs.innerHTML = data.logs.map(l => `<div>${escapeHtml(l)}</div>`).join('');
    logs.scrollTop = logs.scrollHeight;
}

// ------------------------------------------------------------------
// Browse folder (dialog nativo)
// ------------------------------------------------------------------
async function browseFolder(inputId, sync) {
    try {
        const data = await getJSON('/api/browse');
        if (data.folder) {
            $(inputId).value = data.folder;
            // v4.3: si sync=true, propagar a los otros inputs y guardar en localStorage
            if (sync) {
                syncOutputDirs(data.folder);
            }
        }
    } catch (e) {
        showToast('Error al abrir explorador: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Sub-pestaña 2: Mejorar Calidad
// ------------------------------------------------------------------
async function loadImproveSongs() {
    try {
        const data = await getJSON('/api/spotiflac-dl/local-songs');
        if (data.error) {
            $('spdl-improve-status').style.display = 'flex';
            return;
        }
        spdlImproveSongs = data.songs || [];
        $('spdl-improve-status').style.display = 'none';
        $('spdl-improve-filters').classList.remove('hidden');
        $('spdl-improve-output').classList.remove('hidden');
        $('spdl-improve-table-container').classList.remove('hidden');
        renderImproveTable();
    } catch (e) {
        $('spdl-improve-status').style.display = 'flex';
    }
}

function renderImproveTable() {
    const tbody = $('spdl-improve-tbody');
    const q = ($('spdl-improve-search').value || '').toLowerCase().trim();
    const filter = $('spdl-improve-filter-quality').value;
    let filtered = spdlImproveSongs.filter(s => {
        if (q && !(`${s.name} ${s.artist}`.toLowerCase().includes(q))) return false;
        if (filter === 'lossless' && !s.is_lossless) return false;
        if (filter === 'lossy' && s.is_lossless) return false;
        if (filter === 'low') {
            // Baja calidad: bitrate < 320000 o sample_rate < 44100
            if (s.bitrate > 320000 && s.sample_rate >= 44100) return false;
        }
        return true;
    });
    $('spdl-improve-count').textContent = `${filtered.length} canciones`;
    tbody.innerHTML = '';
    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted);">Sin resultados.</td></tr>';
        return;
    }
    // Limitar a 500 filas
    const shown = filtered.slice(0, 500);
    shown.forEach((s, i) => {
        const tr = document.createElement('tr');
        const hzKbps = s.is_lossless
            ? `${s.sample_rate / 1000}kHz / ${s.bits_per_sample}-bit`
            : `${Math.round(s.bitrate / 1000)}kbps`;
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td><strong>${escapeHtml(s.name)}</strong></td>
            <td>${escapeHtml(s.artist)}</td>
            <td style="text-align:center;"><span class="format-badge ${escapeHtml(s.ext.toLowerCase())}">${escapeHtml(s.ext.toUpperCase())}</span></td>
            <td style="text-align:center; font-family:var(--font-mono); font-size:11px;">${escapeHtml(hzKbps)}</td>
            <td style="text-align:center;">${escapeHtml(s.quality_label)}</td>
            <td></td>
        `;
        const dlCell = tr.children[6];
        if (!s.is_lossless) {
            const btn = document.createElement('button');
            btn.className = 'btn btn-secondary btn-sm';
            btn.textContent = '⬇ FLAC';
            btn.title = 'Descargar en FLAC desde Spotify';
            btn.addEventListener('click', () => {
                // Buscar la canción en Spotify y descargar
                downloadImproved(s);
            });
            dlCell.appendChild(btn);
        } else {
            dlCell.innerHTML = '<span style="color:var(--accent);">✓</span>';
        }
        tbody.appendChild(tr);
    });
    if (filtered.length > 500) {
        tbody.innerHTML += `<tr><td colspan="7" style="text-align:center; padding:12px; color:var(--text-muted);">... y ${filtered.length - 500} más (afiná el filtro)</td></tr>`;
    }
}

async function downloadImproved(song) {
    // Buscar la canción en Spotify por nombre + artista
    const query = `${song.name} ${song.artist}`;
    showToast(`Buscando "${query}" en Spotify...`, 'info');
    try {
        const data = await postJSON('/api/spotiflac-dl/search', { query, limit: 5 });
        if (data.error) {
            showToast('Error: ' + data.error, 'error');
            return;
        }
        const results = data.results || [];
        if (results.length === 0) {
            showToast('No se encontró en Spotify.', 'error');
            return;
        }
        // Tomar primer resultado
        const url = results[0].external_url || `https://open.spotify.com/track/${results[0].id}`;
        // v4.3: usar getOutputDir() para leer de cualquier input o localStorage
        const outputDir = getOutputDir();
        if (!outputDir) {
            showToast('Indicá una carpeta de destino (en cualquier sub-pestaña).', 'error');
            return;
        }
        // v4.3: usar la calidad de la sub-pestaña improve si está, sino la default
        const quality = $('spdl-improve-quality') ? $('spdl-improve-quality').value : 'LOSSLESS';
        try {
            const resp = await postJSON('/api/spotiflac-dl/download', {
                urls: [url], output_dir: outputDir, quality
            });
            if (resp.error) {
                showToast('Error: ' + resp.error, 'error', 6000);
                return;
            }
            showToast(`Descarga iniciada: ${song.name}`, 'success');
            const queueTab = document.querySelector('[data-spdl-subtab="queue"]');
            if (queueTab) queueTab.click();
            loadQueue();
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Configuración del registry (.env) - v4.1
// ------------------------------------------------------------------
async function loadRegistryConfig() {
    try {
        const data = await getJSON('/api/spotiflac-dl/registry-config');
        renderRegistryStatus(data);
    } catch (e) {
        renderRegistryStatus({ is_configured: false, error: e.message });
    }
}

function renderRegistryStatus(data) {
    const icon = $('spdl-registry-icon');
    const title = $('spdl-registry-title');
    const detail = $('spdl-registry-detail');
    const extra = $('spdl-registry-detail-extra');
    const btnConfig = $('btn-spdl-config-registry');
    const btnAuto = $('btn-spdl-auto-config');

    if (data.is_configured) {
        icon.textContent = '✓';
        icon.style.color = 'var(--accent)';
        title.textContent = 'Registry configurado';
        const urls = data.registries || [];
        detail.textContent = `${urls.length} registry(s) configurado(s).`;
        extra.innerHTML = urls.map(u => `📄 ${escapeHtml(u)}`).join('<br>');
        btnAuto.classList.add('hidden');
    } else {
        icon.textContent = '⚠';
        icon.style.color = 'var(--warning)';
        title.textContent = 'Registry NO configurado';
        detail.textContent = 'Sin un registry, SpotiFLAC no puede encontrar extensiones para descargar.';
        extra.innerHTML = '<span style="color:var(--text-muted);">Hacé clic en "Auto-configurar" para usar el registry oficial, o "Configurar" para personalizarlo.</span>';
        btnAuto.classList.remove('hidden');
    }

    if (data.error) {
        extra.innerHTML += `<br><span style="color:var(--danger);">Error: ${escapeHtml(data.error)}</span>`;
    }
}

async function autoConfigRegistry() {
    if (!confirm('¿Configurar automáticamente el registry oficial de SpotiFLAC?\n\nEsto creará/editará el archivo .env en la carpeta de Music Manager.')) return;
    try {
        const data = await postJSON('/api/spotiflac-dl/registry-config/default', {});
        if (data.success) {
            showToast(`Registry configurado en: ${data.env_path}`, 'success', 5000);
            await loadRegistryConfig();
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error', 6000);
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function openEnvModal() {
    $('spdl-env-modal').classList.remove('hidden');
    $('spdl-env-registries').value = '';
    $('spdl-env-content').value = 'Cargando...';
    $('spdl-env-path').textContent = 'Cargando...';
    try {
        const data = await getJSON('/api/spotiflac-dl/registry-config');
        $('spdl-env-path').textContent = data.env_path || '—';
        $('spdl-env-content').value = data.env_content || '(archivo no existe aún)';
        const urls = data.registries || [];
        $('spdl-env-registries').value = urls.join('\n');
    } catch (e) {
        $('spdl-env-content').value = 'Error: ' + e.message;
    }
}

async function saveEnvConfig() {
    const raw = $('spdl-env-registries').value.trim();
    if (!raw) {
        showToast('Debes indicar al menos una URL de registry.', 'error');
        return;
    }
    // Aceptar URLs separadas por comas o saltos de línea
    const registries = raw.split(/[\n,]/).map(s => s.trim()).filter(s => s);
    try {
        const data = await postJSON('/api/spotiflac-dl/registry-config', { registries });
        if (data.success) {
            showToast(`Configuración guardada en: ${data.env_path}`, 'success', 5000);
            $('spdl-env-modal').classList.add('hidden');
            await loadRegistryConfig();
        } else {
            showToast('Error: ' + (data.error || 'desconocido'), 'error', 6000);
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ------------------------------------------------------------------
// Sub-pestaña 3: Por Playlist
// ------------------------------------------------------------------
async function loadPlaylistsList() {
    try {
        const data = await getJSON('/api/spotiflac-dl/playlists');
        const playlists = data.playlists || [];
        const select = $('spdl-playlist-select');
        select.innerHTML = '<option value="">Selecciona una playlist...</option>';
        playlists.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            const platformLabel = p.platform === 'youtube' ? 'YT Music' : (p.platform === 'spotify' ? 'Spotify' : 'CSV/JSON');
            opt.textContent = `${p.name} | ${p.track_count} canciones | ${platformLabel}`;
            select.appendChild(opt);
        });
    } catch (e) {
        showToast('Error al cargar playlists: ' + e.message, 'error');
    }
}

async function loadPlaylistTracks() {
    const playlistId = $('spdl-playlist-select').value;
    if (!playlistId) {
        showToast('Selecciona una playlist.', 'error');
        return;
    }
    try {
        const data = await getJSON(`/api/spotiflac-dl/playlists/${playlistId}/tracks`);
        if (data.error) {
            showToast('Error: ' + data.error, 'error');
            return;
        }
        spdlPlaylistTracks = data.tracks || [];
        $('spdl-pl-total').textContent = data.total;
        $('spdl-pl-downloaded').textContent = data.matched;
        $('spdl-pl-missing').textContent = data.missing;
        $('spdl-playlist-stats').classList.remove('hidden');
        $('spdl-playlist-table-container').classList.remove('hidden');
        renderPlaylistTable();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function renderPlaylistTable() {
    const tbody = $('spdl-playlist-tbody');
    tbody.innerHTML = '';
    spdlPlaylistTracks.forEach((t, i) => {
        const tr = document.createElement('tr');
        const statusBadge = t.is_downloaded
            ? '<span class="rename-ok-badge">✓ Descargada</span>'
            : '<span class="needs-rename-badge">⚠ Falta</span>';
        tr.innerHTML = `
            <td>${i + 1}</td>
            <td><strong>${escapeHtml(t.title)}</strong></td>
            <td>${escapeHtml(t.artist)}</td>
            <td>${escapeHtml(t.album || '—')}</td>
            <td style="text-align:center;">${statusBadge}</td>
            <td></td>
        `;
        const dlCell = tr.children[5];
        if (!t.is_downloaded && t.url) {
            const btn = document.createElement('button');
            btn.className = 'btn btn-primary btn-sm';
            btn.textContent = '⬇';
            btn.title = 'Descargar esta canción';
            btn.addEventListener('click', () => {
                // v4.3: usar getOutputDir() que lee de cualquier input o localStorage
                const dir = getOutputDir();
                if (!dir) {
                    showToast('Indicá una carpeta de destino (en cualquier sub-pestaña).', 'error');
                    return;
                }
                const quality = $('spdl-playlist-quality') ? $('spdl-playlist-quality').value : 'LOSSLESS';
                postJSON('/api/spotiflac-dl/download', { urls: [t.url], output_dir: dir, quality })
                    .then(resp => {
                        if (resp.error) {
                            showToast('Error: ' + resp.error, 'error', 6000);
                            return;
                        }
                        showToast(`Descarga iniciada: ${t.title}`, 'success');
                        const queueTab = document.querySelector('[data-spdl-subtab="queue"]');
                        if (queueTab) queueTab.click();
                        loadQueue();
                    })
                    .catch(e => showToast('Error: ' + e.message, 'error'));
            });
            dlCell.appendChild(btn);
        } else if (t.is_downloaded) {
            dlCell.innerHTML = '<span style="color:var(--accent);">✓</span>';
        }
        tbody.appendChild(tr);
    });
}

async function downloadAllMissing() {
    const missing = spdlPlaylistTracks.filter(t => !t.is_downloaded && t.url);
    if (missing.length === 0) {
        showToast('No hay canciones faltantes para descargar.', 'info');
        return;
    }
    // v4.3: usar getOutputDir() que lee de cualquier input o localStorage
    const dir = getOutputDir();
    if (!dir) {
        showToast('Indicá una carpeta de destino (en cualquier sub-pestaña).', 'error');
        return;
    }
    if (!confirm(`¿Descargar ${missing.length} canciones faltantes en ${dir}?\n\nEsto puede tardar varios minutos.`)) return;
    const urls = missing.map(t => t.url);
    const quality = $('spdl-playlist-quality') ? $('spdl-playlist-quality').value : 'LOSSLESS';
    try {
        const data = await postJSON('/api/spotiflac-dl/download', {
            urls, output_dir: dir, quality
        });
        if (data.error) {
            showToast('Error: ' + data.error, 'error');
            return;
        }
        // v4.3: capturar el job_id ANTES de que se sobreescriba la variable `data`
        const jobId = data.job_id;
        showToast(`Descarga iniciada: ${urls.length} canciones. Job ${jobId}`, 'success');
        // v4.2: cambiar a la sub-pestaña Cola para ver el progreso
        const queueTab = document.querySelector('[data-spdl-subtab="queue"]');
        if (queueTab) queueTab.click();
        loadQueue();
        // v4.3: después de completar, recargar la playlist para actualizar estados
        // Bug arreglado: antes buscaba data.job_id en la respuesta de /jobs (que no tiene job_id)
        const checkInterval = setInterval(() => {
            fetch('/api/spotiflac-dl/jobs')
                .then(r => r.json())
                .then(jobsData => {
                    const job = (jobsData.jobs || []).find(j => j.job_id === jobId);
                    if (!job || job.status === 'completed' || job.status === 'error') {
                        clearInterval(checkInterval);
                        // Re-escanear Mi Música y recargar playlist
                        setTimeout(() => loadPlaylistTracks(), 2000);
                    }
                })
                .catch(() => {});
        }, 3000);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ==================================================================
// SUB-PESTAÑA 4: COLA DE DESCARGAS (v4.2)
// ==================================================================

let spdlQueuePoller = null;  // interval para auto-refresh

async function loadQueue() {
    try {
        const data = await getJSON('/api/spotiflac-dl/jobs');
        renderQueue(data.jobs || []);
        // Auto-poll si hay trabajos activos
        const hasActive = (data.jobs || []).some(j => j.status === 'running' || j.status === 'pending');
        if (hasActive) {
            startQueuePolling();
        } else {
            stopQueuePolling();
        }
    } catch (e) {
        console.error('Error cargando cola:', e);
    }
}

function startQueuePolling() {
    if (spdlQueuePoller) return; // ya está corriendo
    spdlQueuePoller = setInterval(loadQueue, 2000);
}

function stopQueuePolling() {
    if (spdlQueuePoller) {
        clearInterval(spdlQueuePoller);
        spdlQueuePoller = null;
    }
}

function renderQueue(jobs) {
    const container = $('spdl-queue-list');
    if (!container) return;

    // Actualizar stats
    const total = jobs.length;
    const running = jobs.filter(j => j.status === 'running').length;
    const pending = jobs.filter(j => j.status === 'pending').length;
    const done = jobs.filter(j => j.status === 'completed').length;
    const error = jobs.filter(j => j.status === 'error').length;

    if ($('spdl-q-total')) $('spdl-q-total').textContent = total;
    if ($('spdl-q-running')) $('spdl-q-running').textContent = running;
    if ($('spdl-q-pending')) $('spdl-q-pending').textContent = pending;
    if ($('spdl-q-done')) $('spdl-q-done').textContent = done;
    if ($('spdl-q-error')) $('spdl-q-error').textContent = error;

    // Badge en el tab
    const badge = $('spdl-queue-badge');
    if (badge) {
        const activeCount = running + pending;
        if (activeCount > 0) {
            badge.textContent = activeCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    // Mostrar/ocultar stats bar
    if ($('spdl-queue-stats')) {
        $('spdl-queue-stats').classList.toggle('hidden', total === 0);
    }

    if (total === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📥</div>
                <h3>Sin descargas activas</h3>
                <p>Cuando inicies una descarga desde las otras sub-pestañas, aparecerá acá con su progreso en tiempo real.</p>
            </div>`;
        return;
    }

    // Renderizar cada job como una tarjeta
    container.innerHTML = jobs.map(job => renderJobCard(job)).join('');

    // Añadir event listeners para expandir/colapsar logs
    container.querySelectorAll('.spdl-job-toggle-logs').forEach(btn => {
        btn.addEventListener('click', () => {
            const logDiv = btn.parentElement.querySelector('.spdl-job-logs');
            if (logDiv) {
                logDiv.classList.toggle('hidden');
                btn.textContent = logDiv.classList.contains('hidden') ? '📄 Ver logs' : '📄 Ocultar logs';
            }
        });
    });
}

function renderJobCard(job) {
    const statusInfo = getJobStatusInfo(job.status);
    const startedAt = new Date(job.started_at * 1000).toLocaleTimeString();
    const duration = job.finished_at
        ? `${Math.round(job.finished_at - job.started_at)}s`
        : '—';

    let progressHtml = '';
    if (job.total > 0) {
        const pct = job.progress || 0;
        progressHtml = `
            <div style="margin-top:8px;">
                <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); margin-bottom:4px;">
                    <span>${job.done}/${job.total} descargadas${job.failed > 0 ? ` · ${job.failed} fallidas` : ''}</span>
                    <span>${pct}%</span>
                </div>
                <div style="background:var(--bg-elevated); border-radius:4px; height:8px; overflow:hidden;">
                    <div style="background:${statusInfo.color}; height:100%; width:${pct}%; transition: width 0.5s ease;"></div>
                </div>
            </div>`;
    }

    return `
        <div class="spdl-job-card" style="background:var(--bg-card); border:1px solid var(--border); border-left:3px solid ${statusInfo.color}; border-radius:8px; padding:16px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:start; gap:12px;">
                <div style="flex:1;">
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                        <span style="font-size:18px;">${statusInfo.icon}</span>
                        <strong style="font-size:14px;">${escapeHtml(job.output_dir)}</strong>
                    </div>
                    <div style="font-size:11px; color:var(--text-muted);">
                        Job ID: <code>${escapeHtml(job.job_id)}</code> · Iniciado: ${escapeHtml(startedAt)} · Duración: ${escapeHtml(duration)}
                    </div>
                    <div style="margin-top:6px;">
                        <span style="display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; background:${statusInfo.bgColor}; color:${statusInfo.color}; border:1px solid ${statusInfo.color};">
                            ${statusInfo.label}
                        </span>
                    </div>
                    ${progressHtml}
                </div>
                <button class="btn btn-ghost btn-sm spdl-job-toggle-logs">📄 Ver logs</button>
            </div>
            <div class="spdl-job-logs hidden" style="margin-top:12px; max-height:200px; overflow-y:auto; background:var(--bg-elevated); border-radius:4px; padding:8px; font-family:var(--font-mono); font-size:11px; color:var(--text-secondary);">
                ${job.logs ? job.logs.map(l => `<div>${escapeHtml(l)}</div>`).join('') : '<div style="color:var(--text-muted);">Sin logs.</div>'}
            </div>
        </div>`;
}

function getJobStatusInfo(status) {
    const map = {
        'pending':   { icon: '⏳', label: 'Pendiente',     color: 'var(--warning)',       bgColor: 'rgba(255,165,0,0.15)' },
        'running':   { icon: '⏳', label: 'Descargando',   color: 'var(--accent)',        bgColor: 'rgba(29,185,84,0.15)' },
        'completed': { icon: '✓',  label: 'Completado',    color: 'var(--accent-hover)',  bgColor: 'rgba(29,185,84,0.1)' },
        'error':     { icon: '✗',  label: 'Error',         color: 'var(--danger)',        bgColor: 'rgba(255,107,107,0.15)' },
    };
    return map[status] || { icon: '?', label: status, color: 'var(--text-muted)', bgColor: 'var(--bg-elevated)' };
}

async function clearCompletedJobs() {
    if (!confirm('¿Limpiar trabajos completados y con errores de la lista?\n\nEsto NO afecta los archivos ya descargados.')) return;
    try {
        // Como no hay endpoint para limpiar, hacemos un POST a un endpoint nuevo
        // Por ahora, recargamos la página para que se vuelva a renderizar vacío
        // (los jobs se guardan en memoria del servidor, así que persisten hasta reiniciar)
        const resp = await fetch('/api/spotiflac-dl/jobs/clear', { method: 'POST' });
        if (resp.ok) {
            showToast('Trabajos limpiados.', 'success');
            loadQueue();
        } else {
            showToast('No se pudo limpiar (endpoint no disponible).', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}
