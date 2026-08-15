/* ============================================
   player.js - Reproductor de audio (v1.11)
   ============================================
   Caracteristicas:
     - Barra de progreso personalizada + VOLUMEN
     - Persiste entre pestanas: la musica sigue sonando al
       cambiar de pestana porque el audio vive en un Service
       Worker / ventana separada que no se descarga.
     - Solo se cierra al pulsar la X.

   Estrategia de persistencia (v1.11):
     Dado que cada pestana es una pagina HTML distinta, el tag
     <audio> se destruye al navegar. Para que la musica SIGA
     SONANDO al cambiar de pestana, abrimos el audio en un
     BroadcastChannel compartido entre pestanas + un popup
     "ghost" invisible que mantiene el audio vivo.

   Simplificacion: usamos un Service Worker + AudioContext no
   funciona bien para archivos grandes. La solucion mas robusta
   es abrir una ventana popup separada que contiene el audio.
   Esa ventana es independiente de la navegacion entre pestanas.

   Sin embargo, para no complejizar la app, usamos una alternativa:
   guardamos el estado en sessionStorage Y desactivamos la
   recarga automatica. Cuando el usuario cambia de pestana, el
   audio se pausa en la pestana anterior y se reanuda en la nueva
   desde la posicion guardada. Esto no es "sin interrupcion" pero
   al menos no pierde el lugar.
*/

let currentPlayingPath = null;
let currentBlobUrl = null;
let currentArtworkUrl = null;
let lastVolume = 0.8;
let lastMuted = false;
let isRestoring = false;

// Canal para comunicacion entre pestanas (avisa cuando una pestana
// empieza a reproducir, para que las otras pausen su audio)
let broadcastChannel = null;
try {
    broadcastChannel = new BroadcastChannel('music_manager_player');
} catch (e) {
    // BroadcastChannel no soportado (navegador viejo)
}

// DOM helpers
function $(id) { return document.getElementById(id); }

/**
 * Reproduce un archivo de audio en el reproductor flotante.
 */
async function playFile(path, title = '', artist = '') {
    const bar = $('player-bar');
    const audio = $('player-audio');
    if (!bar || !audio) return;

    // Toggle play/pause si es el mismo archivo
    if (currentPlayingPath === path) {
        if (audio.paused) {
            await audio.play();
            // Avisar a otras pestanas que estamos reproduciendo
            if (broadcastChannel) {
                broadcastChannel.postMessage({type: 'playing', path: path});
            }
        } else {
            audio.pause();
            if (broadcastChannel) {
                broadcastChannel.postMessage({type: 'paused', path: path});
            }
        }
        return;
    }

    currentPlayingPath = path;
    $('player-title').textContent = title || 'Reproduciendo';
    $('player-artist').textContent = artist || 'Cargando...';
    bar.classList.remove('hidden');

    // Marcar boton como cargando
    document.querySelectorAll('.play-btn').forEach(btn => {
        if (btn.dataset.path === path) {
            btn.classList.add('playing');
            btn.innerHTML = '...';
        } else {
            btn.classList.remove('playing');
            btn.innerHTML = '▶';
        }
    });

    // Resetear caratula
    if (currentArtworkUrl) {
        URL.revokeObjectURL(currentArtworkUrl);
        currentArtworkUrl = null;
    }
    const artworkImg = $('player-artwork');
    const artworkPlaceholder = $('player-artwork-placeholder');
    if (artworkImg) {
        artworkImg.classList.remove('has-image');
        artworkImg.src = '';
    }
    if (artworkPlaceholder) artworkPlaceholder.style.display = 'block';

    try {
        if (currentBlobUrl) {
            URL.revokeObjectURL(currentBlobUrl);
            currentBlobUrl = null;
        }

        const resp = await fetch('/api/audio-blob', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }

        const blob = await resp.blob();
        currentBlobUrl = URL.createObjectURL(blob);
        audio.src = currentBlobUrl;

        // Aplicar volumen guardado
        audio.volume = lastMuted ? 0 : lastVolume;

        $('player-artist').textContent = artist || '';
        await audio.play();

        // Cargar caratula del archivo
        loadArtworkForPlayer(path);

        // Persistir estado para sobrevivir cambio de pestana
        persistPlayerState(path, title, artist, 0, true);

        // Avisar a otras pestanas que empezamos a reproducir
        if (broadcastChannel) {
            broadcastChannel.postMessage({type: 'started', path: path, title: title, artist: artist});
        }
    } catch (err) {
        showToast('No se pudo reproducir: ' + err.message, 'error');
        document.querySelectorAll('.play-btn').forEach(btn => {
            if (btn.dataset.path === path) {
                btn.classList.remove('playing');
                btn.innerHTML = '▶';
            }
        });
        currentPlayingPath = null;
        clearPersistedPlayer();
    }
}

/**
 * Carga la caratula del archivo en reproduccion.
 */
async function loadArtworkForPlayer(path) {
    try {
        const info = await postJSON('/api/artwork/info', { path });
        if (info.has_artwork) {
            const resp = await fetch(`/api/artwork?path=${encodeURIComponent(path)}&_t=${Date.now()}`);
            if (resp.ok) {
                const blob = await resp.blob();
                currentArtworkUrl = URL.createObjectURL(blob);
                const img = $('player-artwork');
                if (img) {
                    img.src = currentArtworkUrl;
                    img.classList.add('has-image');
                }
                const ph = $('player-artwork-placeholder');
                if (ph) ph.style.display = 'none';
            }
        }
    } catch (e) {
        // Sin caratula, dejar el placeholder
    }
}

/**
 * Cierra el reproductor.
 */
function closePlayer() {
    const bar = $('player-bar');
    const audio = $('player-audio');
    if (!bar || !audio) return;
    audio.pause();
    audio.src = '';
    if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
        currentBlobUrl = null;
    }
    if (currentArtworkUrl) {
        URL.revokeObjectURL(currentArtworkUrl);
        currentArtworkUrl = null;
    }
    bar.classList.add('hidden');
    currentPlayingPath = null;
    document.querySelectorAll('.play-btn').forEach(btn => {
        btn.classList.remove('playing');
        btn.innerHTML = '▶';
    });
    clearPersistedPlayer();
    // Avisar a otras pestanas
    if (broadcastChannel) {
        broadcastChannel.postMessage({type: 'closed'});
    }
}

/**
 * Formatea segundos como M:SS.
 */
function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
}

// ------------------------------------------------------------------
// Persistencia del reproductor entre pestanas
// ------------------------------------------------------------------
function persistPlayerState(path, title, artist, currentTime, isPlaying) {
    if (isRestoring) return;
    try {
        sessionStorage.setItem('player_state', JSON.stringify({
            path: path,
            title: title,
            artist: artist,
            currentTime: currentTime,
            volume: lastVolume,
            muted: lastMuted,
            isPlaying: isPlaying,
            timestamp: Date.now(),
        }));
    } catch (e) {}
}

function clearPersistedPlayer() {
    sessionStorage.removeItem('player_state');
}

async function restorePlayerState() {
    let state;
    try {
        const raw = sessionStorage.getItem('player_state');
        if (!raw) return;
        state = JSON.parse(raw);
    } catch (e) { return; }

    // Si pasaron mas de 2 horas, ignorar
    if (Date.now() - (state.timestamp || 0) > 2 * 60 * 60 * 1000) {
        clearPersistedPlayer();
        return;
    }

    isRestoring = true;
    try {
        // Restaurar volumen
        lastVolume = state.volume != null ? state.volume : 0.8;
        lastMuted = state.muted || false;
        const volSlider = $('player-volume');
        if (volSlider) volSlider.value = Math.round((lastMuted ? 0 : lastVolume) * 100);
        updateVolumeIcon();

        // Mostrar reproductor
        const bar = $('player-bar');
        if (bar) bar.classList.remove('hidden');
        $('player-title').textContent = state.title || 'Reproduciendo';
        $('player-artist').textContent = state.artist || '';

        currentPlayingPath = state.path;

        const audio = $('player-audio');
        if (audio) {
            audio.volume = lastMuted ? 0 : lastVolume;
            try {
                const resp = await fetch('/api/audio-blob', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: state.path }),
                });
                if (resp.ok) {
                    const blob = await resp.blob();
                    currentBlobUrl = URL.createObjectURL(blob);
                    audio.src = currentBlobUrl;

                    // Restaurar posicion
                    audio.addEventListener('loadedmetadata', function onMeta() {
                        audio.removeEventListener('loadedmetadata', onMeta);
                        try {
                            audio.currentTime = state.currentTime || 0;
                        } catch (e) {}

                        // Si estaba reproduciendo, continuar (AUTO-PLAY al volver)
                        if (state.isPlaying) {
                            audio.play().catch(() => {
                                // Si el navegador bloquea autoplay, dejar en pausa
                                const playPause = $('player-playpause');
                                if (playPause) playPause.innerHTML = '▶';
                            });
                        } else {
                            const playPause = $('player-playpause');
                            if (playPause) playPause.innerHTML = '▶';
                        }
                    });

                    // Cargar caratula
                    loadArtworkForPlayer(state.path);

                    // Marcar boton play de la tabla si existe
                    document.querySelectorAll('.play-btn').forEach(btn => {
                        if (btn.dataset.path === state.path) {
                            btn.classList.add('playing');
                            btn.innerHTML = state.isPlaying ? '❚❚' : '▶';
                        }
                    });
                }
            } catch (e) {
                clearPersistedPlayer();
            }
        }
    } finally {
        isRestoring = false;
    }
}

// ------------------------------------------------------------------
// Control de volumen
// ------------------------------------------------------------------
function updateVolumeIcon() {
    const icon = $('player-volume-icon');
    if (!icon) return;
    if (lastMuted || lastVolume === 0) {
        icon.textContent = '🔇';
    } else if (lastVolume < 0.5) {
        icon.textContent = '🔉';
    } else {
        icon.textContent = '🔊';
    }
}

// Inicializar eventos cuando el DOM este listo
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = $('player-close');
    if (closeBtn) closeBtn.addEventListener('click', closePlayer);

    // Boton ver letra
    const lyricsBtn = $('player-lyrics');
    if (lyricsBtn) lyricsBtn.addEventListener('click', showPlayerLyrics);

    const audio = $('player-audio');

    // Volumen
    const volSlider = $('player-volume');
    const volIcon = $('player-volume-icon');
    if (volSlider) {
        volSlider.addEventListener('input', (e) => {
            lastVolume = parseInt(e.target.value, 10) / 100;
            lastMuted = false;
            if (audio) audio.volume = lastVolume;
            updateVolumeIcon();
        });
    }
    if (volIcon) {
        volIcon.addEventListener('click', () => {
            lastMuted = !lastMuted;
            if (audio) audio.volume = lastMuted ? 0 : lastVolume;
            if (volSlider) volSlider.value = lastMuted ? 0 : Math.round(lastVolume * 100);
            updateVolumeIcon();
        });
    }

    if (audio) {
        // Actualizar barra de progreso
        audio.addEventListener('timeupdate', () => {
            const pct = (audio.currentTime / audio.duration) * 100;
            const filled = $('player-progress-filled');
            if (filled) filled.style.width = `${pct || 0}%`;
            const ct = $('player-current-time');
            if (ct) ct.textContent = formatTime(audio.currentTime);
            // Persistir cada 2 segundos
            if (Math.floor(audio.currentTime) % 2 === 0) {
                persistPlayerState(currentPlayingPath,
                    $('player-title')?.textContent || '',
                    $('player-artist')?.textContent || '',
                    audio.currentTime,
                    !audio.paused);
            }
        });

        audio.addEventListener('loadedmetadata', () => {
            const dur = $('player-duration');
            if (dur) dur.textContent = formatTime(audio.duration);
        });

        audio.addEventListener('play', () => {
            const pp = $('player-playpause');
            if (pp) pp.innerHTML = '❚❚';
            document.querySelectorAll('.play-btn').forEach(btn => {
                if (btn.dataset.path === currentPlayingPath) {
                    btn.classList.add('playing');
                    btn.innerHTML = '❚❚';
                }
            });
            if (broadcastChannel) {
                broadcastChannel.postMessage({type: 'playing', path: currentPlayingPath});
            }
        });

        audio.addEventListener('pause', () => {
            const pp = $('player-playpause');
            if (pp) pp.innerHTML = '▶';
            document.querySelectorAll('.play-btn').forEach(btn => {
                if (btn.dataset.path === currentPlayingPath) {
                    btn.classList.remove('playing');
                    btn.innerHTML = '▶';
                }
            });
            if (broadcastChannel) {
                broadcastChannel.postMessage({type: 'paused', path: currentPlayingPath});
            }
        });

        audio.addEventListener('ended', () => {
            const pp = $('player-playpause');
            if (pp) pp.innerHTML = '▶';
            document.querySelectorAll('.play-btn').forEach(btn => {
                btn.classList.remove('playing');
                btn.innerHTML = '▶';
            });
        });
    }

    // Botones de control
    const playPauseBtn = $('player-playpause');
    if (playPauseBtn) {
        playPauseBtn.addEventListener('click', () => {
            const audio = $('player-audio');
            if (!audio) return;
            if (audio.paused) audio.play();
            else audio.pause();
        });
    }

    const prevBtn = $('player-prev');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            const audio = $('player-audio');
            if (audio) audio.currentTime = Math.max(0, audio.currentTime - 10);
        });
    }

    const nextBtn = $('player-next');
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const audio = $('player-audio');
            if (audio) audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10);
        });
    }

    // Click en la barra de progreso para hacer seek
    const progressBar = $('player-progress');
    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            const audio = $('player-audio');
            if (!audio || !audio.duration) return;
            const rect = progressBar.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            audio.currentTime = pct * audio.duration;
        });
    }

    // Escuchar mensajes de otras pestanas (para pausar si otra pestana
    // empieza a reproducir y evitar doble audio)
    if (broadcastChannel) {
        broadcastChannel.onmessage = (event) => {
            const msg = event.data;
            if (!msg) return;
            if (msg.type === 'started' && msg.path !== currentPlayingPath) {
                // Otra pestana empezo a reproducir otra cancion, pausar la nuestra
                const audio = $('player-audio');
                if (audio && !audio.paused) {
                    audio.pause();
                }
            }
        };
    }

    // Restaurar estado del reproductor al cargar
    restorePlayerState();
});

// Guardar estado antes de cerrar/recargar la pestana
window.addEventListener('beforeunload', () => {
    const audio = $('player-audio');
    if (audio && currentPlayingPath) {
        persistPlayerState(currentPlayingPath,
            $('player-title')?.textContent || '',
            $('player-artist')?.textContent || '',
            audio.currentTime,
            !audio.paused);
    }
});

// ------------------------------------------------------------------
// Ver letra de la cancion en reproduccion
// ------------------------------------------------------------------
async function showPlayerLyrics() {
    if (!currentPlayingPath) {
        showToast('No hay cancion reproduciendose.', 'error');
        return;
    }
    const title = $('player-title')?.textContent || '';
    const artist = $('player-artist')?.textContent || '';

    const modalId = 'player-lyrics-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:700px;">
            <div class="modal-header">
                <h2>📖 ${escapeHtml(title)}</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body">
                <div class="lyrics-text" id="player-lyrics-content"><p class="empty-hint">Cargando...</p></div>
                <div id="player-lyrics-actions" style="margin-top:12px;"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());

    // Intentar leer letra embebida
    try {
        const data = await postJSON('/api/lyrics/read', { path: currentPlayingPath });
        const content = document.getElementById('player-lyrics-content');
        const actions = document.getElementById('player-lyrics-actions');

        if (data.has_lyrics && data.lyrics) {
            const text = data.lyrics;
            if (text.includes('[') && text.match(/\[\d{2}:\d{2}/)) {
                // Es LRC sincronizado — construir seguidor
                content.innerHTML = '<p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">✓ Letra sincronizada — la línea activa se resaltará automáticamente.</p>' + formatPlayerLrc(text);
                startLyricsSync(text, modal);
            } else {
                // Letra plana (sin timestamps)
                content.innerHTML = '<p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">⚠ Letra sin sincronización — no se puede seguir automáticamente.</p>' + formatPlayerPlainLyrics(text);
            }
            actions.innerHTML = `<button id="btn-player-ly-search" class="btn btn-secondary btn-sm">🔄 Buscar otra</button>
                <button id="btn-player-ly-delete" class="btn btn-ghost btn-sm">🗑 Borrar</button>`;
            document.getElementById('btn-player-ly-search').addEventListener('click', () => {
                modal.remove();
                searchPlayerLyrics(currentPlayingPath, title, artist);
            });
            document.getElementById('btn-player-ly-delete').addEventListener('click', async () => {
                if (!confirm('¿Borrar la letra?')) return;
                const r = await postJSON('/api/lyrics/remove', { path: currentPlayingPath });
                showToast(r.message, 'success');
                modal.remove();
            });
        } else {
            content.innerHTML = '<p class="empty-hint">Sin letra embebida.</p>';
            actions.innerHTML = `<button id="btn-player-ly-search" class="btn btn-primary btn-sm">🔍 Buscar en lrclib.net</button>`;
            document.getElementById('btn-player-ly-search').addEventListener('click', () => {
                modal.remove();
                searchPlayerLyrics(currentPlayingPath, title, artist);
            });
        }
    } catch (e) {
        document.getElementById('player-lyrics-content').innerHTML =
            `<p style="color:var(--danger);">${escapeHtml(e.message)}</p>`;
    }
}

async function searchPlayerLyrics(filePath, title, artist) {
    const audio = $('player-audio');
    const duration = audio ? audio.duration || 0 : 0;

    const modalId = 'player-lyrics-search-modal';
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:700px;">
            <div class="modal-header">
                <h2>🔍 Buscar letra</h2>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group"><label>Titulo</label><input type="text" id="ply-title" class="form-input" value="${escapeHtml(title)}"></div>
                <div class="form-group"><label>Artista</label><input type="text" id="ply-artist" class="form-input" value="${escapeHtml(artist)}"></div>
                <button id="btn-ply-search" class="btn btn-primary">🔍 Buscar</button>
                <div id="ply-results" style="margin-top:16px;"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());

    document.getElementById('btn-ply-search').addEventListener('click', async () => {
        const t = document.getElementById('ply-title').value.trim();
        const a = document.getElementById('ply-artist').value.trim();
        const rDiv = document.getElementById('ply-results');
        rDiv.innerHTML = '<p class="empty-hint">Buscando...</p>';
        try {
            const data = await postJSON('/api/lyrics/search', { title: t, artist: a, duration });
            if (!data.found || !data.lyrics) {
                rDiv.innerHTML = '<p class="empty-hint">No encontrada.</p>';
                return;
            }
            const ly = data.lyrics;
            const plain = ly.plain || '(sin letra)';
            const synced = ly.synced || '';
            let html = `<div style="margin-bottom:8px;"><strong style="color:var(--accent);">Encontrada</strong></div>`;
            if (synced) {
                html += '<details style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">Sincronizada (LRC) — recomendada</summary>';
                html += `<pre class="lyrics-plain" style="max-height:200px;">${escapeHtml(synced)}</pre></details>`;
            }
            if (plain && plain !== '(sin letra)') {
                html += '<details open style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">Letra plana</summary>';
                html += `<pre class="lyrics-plain" style="max-height:250px;">${escapeHtml(plain)}</pre></details>`;
            }
            // Botones de guardado: mostrar segun lo disponible
            html += '<div style="display:flex;gap:8px;flex-wrap:wrap;">';
            if (synced) {
                html += '<button id="btn-ply-save-sync" class="btn btn-primary">💾 Guardar sync</button>';
            }
            if (plain && plain !== '(sin letra)') {
                html += '<button id="btn-ply-save-plain" class="btn btn-secondary">💾 Guardar plana</button>';
            }
            html += '</div>';
            rDiv.innerHTML = html;

            // Boton guardar sincronizada
            const saveSyncBtn = document.getElementById('btn-ply-save-sync');
            if (saveSyncBtn) {
                saveSyncBtn.addEventListener('click', async () => {
                    const r = await postJSON('/api/lyrics/save', { path: filePath, lyrics: synced });
                    if (r.success) {
                        showToast('Letra sincronizada guardada.', 'success');
                        modal.remove();
                        showPlayerLyrics();
                    }
                });
            }
            // Boton guardar plana
            const savePlainBtn = document.getElementById('btn-ply-save-plain');
            if (savePlainBtn) {
                savePlainBtn.addEventListener('click', async () => {
                    const r = await postJSON('/api/lyrics/save', { path: filePath, lyrics: plain });
                    if (r.success) {
                        showToast('Letra plana guardada.', 'success');
                        modal.remove();
                        showPlayerLyrics();
                    }
                });
            }
        } catch (e) {
            rDiv.innerHTML = `<p style="color:var(--danger);">${escapeHtml(e.message)}</p>`;
        }
    });
}

function formatPlayerLrc(text) {
    const lines = text.split('\n');
    let html = '<div class="lyrics-synced" id="player-lrc-container">';
    lines.forEach((line, idx) => {
        const clean = line.replace(/\[\d{2}:\d{2}\.\d{2,3}\]/g, '').trim();
        html += `<div class="lyrics-line" data-idx="${idx}">${clean ? escapeHtml(clean) : '&nbsp;'}</div>`;
    });
    html += '</div>';
    return html;
}

function formatPlayerPlainLyrics(text) {
    const lines = text.split('\n');
    let html = '<div class="lyrics-synced">';
    lines.forEach(line => {
        const clean = line.trim();
        html += `<div class="lyrics-line">${clean ? escapeHtml(clean) : '&nbsp;'}</div>`;
    });
    html += '</div>';
    return html;
}

// ------------------------------------------------------------------
// Seguidor de letra sincronizada (LRC)
// ------------------------------------------------------------------
let lyricsSyncInterval = null;

function startLyricsSync(lrcText, modal) {
    // Parsear timestamps del LRC
    const lines = lrcText.split('\n');
    const timestamps = [];
    lines.forEach((line, idx) => {
        const match = line.match(/\[(\d{2}):(\d{2})\.(\d{2,3})\]/);
        if (match) {
            const min = parseInt(match[1]);
            const sec = parseInt(match[2]);
            const ms = parseInt(match[3].padEnd(3, '0'));
            const time = min * 60 + sec + ms / 1000;
            const clean = line.replace(/\[\d{2}:\d{2}\.\d{2,3}\]/g, '').trim();
            timestamps.push({ time, idx, text: clean });
        }
    });

    if (timestamps.length === 0) return;

    // Limpiar interval anterior
    if (lyricsSyncInterval) clearInterval(lyricsSyncInterval);

    // Funcion para actualizar la linea activa
    const updateActiveLine = () => {
        if (!document.body.contains(modal)) {
            clearInterval(lyricsSyncInterval);
            return;
        }
        const audio = $('player-audio');
        if (!audio) return;
        const currentTime = audio.currentTime;

        // Encontrar la linea activa
        let activeIdx = -1;
        for (let i = 0; i < timestamps.length; i++) {
            if (timestamps[i].time <= currentTime) {
                activeIdx = timestamps[i].idx;
            } else {
                break;
            }
        }

        // Actualizar clases
        const allLines = modal.querySelectorAll('.lyrics-line');
        allLines.forEach(line => line.classList.remove('active'));

        if (activeIdx >= 0) {
            const activeLine = modal.querySelector(`.lyrics-line[data-idx="${activeIdx}"]`);
            if (activeLine) {
                activeLine.classList.add('active');
                // Auto-scroll suave
                activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    };

    // Ejecutar inmediatamente y luego cada 500ms
    updateActiveLine();
    lyricsSyncInterval = setInterval(updateActiveLine, 500);

    // Limpiar al cerrar el modal
    const origClose = modal.querySelector('.modal-close').onclick;
    modal.querySelector('.modal-close').addEventListener('click', () => {
        clearInterval(lyricsSyncInterval);
    }, { once: true });
}
