/* ============================================
   downloads.js - Pestana "Descargas FLAC" (v2.0)
   ============================================
   Muestra un indice de sitios/programas para descargar
   musica FLAC, leidos desde data/download_sites.txt.
*/

let allSites = [];

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    loadSites();
});

function bindEvents() {
    const searchInput = document.getElementById('site-search');
    const filterStatus = document.getElementById('filter-status');
    const btnAdd = document.getElementById('btn-add-site');
    const btnEdit = document.getElementById('btn-edit-file');
    const btnReload = document.getElementById('btn-reload');
    const btnSaveTxt = document.getElementById('btn-save-txt');
    const btnConfirmAdd = document.getElementById('btn-confirm-add-site');

    if (searchInput) searchInput.addEventListener('input', renderSites);
    if (filterStatus) filterStatus.addEventListener('change', renderSites);
    if (btnAdd) btnAdd.addEventListener('click', openAddSiteModal);
    if (btnEdit) btnEdit.addEventListener('click', openEditModal);
    if (btnReload) btnReload.addEventListener('click', loadSites);
    if (btnSaveTxt) btnSaveTxt.addEventListener('click', saveTxtFile);
    if (btnConfirmAdd) btnConfirmAdd.addEventListener('click', confirmAddSite);
}

// ------------------------------------------------------------------
// Agregar enlace
// ------------------------------------------------------------------
function openAddSiteModal() {
    const modal = document.getElementById('add-site-modal');
    if (!modal) return;
    // Limpiar campos
    document.getElementById('add-site-name').value = '';
    document.getElementById('add-site-link').value = '';
    document.getElementById('add-site-desc').value = '';
    document.getElementById('add-site-status').value = 'OK';
    document.getElementById('add-site-error').textContent = '';
    modal.classList.remove('hidden');
    document.getElementById('add-site-name').focus();
}

async function confirmAddSite() {
    const name = document.getElementById('add-site-name').value.trim();
    const link = document.getElementById('add-site-link').value.trim();
    const description = document.getElementById('add-site-desc').value.trim();
    const status = document.getElementById('add-site-status').value;
    const errorEl = document.getElementById('add-site-error');

    if (!name) {
        if (errorEl) errorEl.textContent = 'El nombre es obligatorio.';
        return;
    }
    if (!link) {
        if (errorEl) errorEl.textContent = 'El enlace es obligatorio.';
        return;
    }

    const btn = document.getElementById('btn-confirm-add-site');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Agregando...';
    }
    if (errorEl) errorEl.textContent = '';

    try {
        const data = await postJSON('/api/download-sites/add', {
            name: name,
            link: link,
            description: description,
            status: status,
        });
        if (data.error) {
            if (errorEl) errorEl.textContent = data.error;
            return;
        }
        showToast(data.message, 'success');
        document.getElementById('add-site-modal').classList.add('hidden');
        // Recargar la lista
        loadSites();
    } catch (e) {
        if (errorEl) errorEl.textContent = 'Error: ' + e.message;
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '➕ Agregar';
        }
    }
}

async function loadSites() {
    try {
        const data = await getJSON('/api/download-sites');
        allSites = data.sites || [];
        renderSites();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function renderSites() {
    const tbody = document.getElementById('sites-tbody');
    if (!tbody) return;

    const query = (document.getElementById('site-search')?.value || '').toLowerCase().trim();
    const statusFilter = document.getElementById('filter-status')?.value || '';

    let filtered = allSites.filter(s => {
        if (statusFilter && s.status !== statusFilter) return false;
        if (query) {
            const hay = (s.name + ' ' + s.description + ' ' + s.link).toLowerCase();
            if (!hay.includes(query)) return false;
        }
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:32px; color:var(--text-muted);">
            No se encontraron sitios. ${allSites.length === 0 ? 'Espera a que cargue o pulsa "Recargar".' : 'Prueba con otros filtros.'}
        </td></tr>`;
        return;
    }

    tbody.innerHTML = '';
    filtered.forEach((site, idx) => {
        const tr = document.createElement('tr');

        // Estado badge
        const statusClass = site.status === 'OK' ? 'status-matched' : 'status-missing';
        const statusText = site.status === 'OK' ? 'OK' : 'Caído';

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(site.name)}</strong></td>
            <td><a href="${escapeHtml(site.link)}" target="_blank" rel="noopener"
                style="color:var(--accent); text-decoration:none;" title="Abrir ${escapeHtml(site.link)}">Abrir ↗</a></td>
            <td style="font-size:12px;">${escapeHtml(site.description)}</td>
            <td style="text-align:center;"><span class="match-status ${statusClass}">${statusText}</span></td>
            <td></td>
        `;

        // Boton de toggle estado
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-ghost btn-sm';
        toggleBtn.textContent = site.status === 'OK' ? '✓' : '✗';
        toggleBtn.title = 'Cambiar estado';
        toggleBtn.addEventListener('click', () => toggleSiteStatus(site));
        tr.children[5].appendChild(toggleBtn);

        tbody.appendChild(tr);
    });
}

async function toggleSiteStatus(site) {
    site.status = site.status === 'OK' ? 'CAIDO' : 'OK';
    // Guardar en el servidor
    try {
        await postJSON('/api/download-sites/save', { sites: allSites });
        renderSites();
        showToast(`Estado de "${site.name}" cambiado a ${site.status}.`, 'success');
    } catch (e) {
        showToast('Error al guardar: ' + e.message, 'error');
    }
}

async function openEditModal() {
    const modal = document.getElementById('txt-edit-modal');
    const textarea = document.getElementById('txt-edit-content');
    if (!modal || !textarea) return;

    // Cargar contenido actual del archivo
    try {
        const data = await getJSON('/api/download-sites/file');
        textarea.value = data.content || '';
        modal.classList.remove('hidden');
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function saveTxtFile() {
    const textarea = document.getElementById('txt-edit-content');
    if (!textarea) return;

    try {
        await postJSON('/api/download-sites/file', { content: textarea.value });
        showToast('Archivo guardado.', 'success');
        document.getElementById('txt-edit-modal').classList.add('hidden');
        // Recargar sitios desde el archivo
        loadSites();
    } catch (e) {
        showToast('Error al guardar: ' + e.message, 'error');
    }
}
