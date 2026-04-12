/* ================================================================
   Research Reader — Frontend
   ================================================================ */

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
  async post(path, body) {
    const opts = { method: 'POST' };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
  async postForm(path, formData) {
    const r = await fetch(path, { method: 'POST', body: formData });
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) throw new Error((await r.json().catch(() => ({detail: r.statusText}))).detail);
    return r.json();
  },
};

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
let _toastTimer = null;
function toast(msg, type = '', duration = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), duration);
}

// ---------------------------------------------------------------------------
// Loading overlay
// ---------------------------------------------------------------------------
function showLoading(msg = 'Processing…') {
  document.getElementById('loading-msg').textContent = msg;
  document.getElementById('loading-overlay').classList.remove('hidden');
}
function hideLoading() {
  document.getElementById('loading-overlay').classList.add('hidden');
}

// ---------------------------------------------------------------------------
// Screen navigation
// ---------------------------------------------------------------------------
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.toggle('active', s.id === id);
    s.classList.toggle('hidden', s.id !== id);
  });
}

// ---------------------------------------------------------------------------
// Player
// ---------------------------------------------------------------------------
class Player {
  constructor() {
    this.audio = new Audio();
    this.queue  = [];        // audio URLs for current paragraph
    this.qIdx   = 0;         // index within queue

    this.paperId      = null;
    this.voiceId      = null;
    this.sections     = [];
    this.sectionIdx   = 0;
    this.paragraphIdx = 0;
    this.playing      = false;
    this.speed        = 1.0;

    this.audio.addEventListener('ended',  () => this._onChunkEnded());
    this.audio.addEventListener('error',  () => this._onAudioError());
    this.audio.addEventListener('playing', () => this._setStatus('Playing', 'playing'));
    this.audio.addEventListener('waiting', () => this._setStatus('Buffering…', 'loading'));
  }

  load(paperId, voiceId, sections, sectionIdx = 0, paragraphIdx = 0) {
    this.paperId      = paperId;
    this.voiceId      = voiceId;
    this.sections     = sections;
    this.sectionIdx   = sectionIdx;
    this.paragraphIdx = paragraphIdx;
    this.playing      = false;
    this.queue        = [];
    this._updateUI();
  }

  async play() {
    if (!this.voiceId) { toast('Select a voice first.', 'error'); return; }
    this.playing = true;
    this._updatePlayBtn();
    await this._generateAndPlay(this.sectionIdx, this.paragraphIdx);
  }

  pause() {
    this.playing = false;
    this.audio.pause();
    this._setStatus('Paused');
    this._updatePlayBtn();
  }

  togglePlay() { this.playing ? this.pause() : this.play(); }

  async next() {
    const sec = this.sections[this.sectionIdx];
    if (!sec) return;
    if (this.paragraphIdx < sec.paragraph_count - 1) {
      this.paragraphIdx++;
    } else if (this.sectionIdx < this.sections.length - 1) {
      this.sectionIdx++;
      this.paragraphIdx = 0;
    }
    this.audio.pause();
    this.queue = [];
    this._updateUI();
    if (this.playing) await this._generateAndPlay(this.sectionIdx, this.paragraphIdx);
  }

  async prev() {
    if (this.paragraphIdx > 0) {
      this.paragraphIdx--;
    } else if (this.sectionIdx > 0) {
      this.sectionIdx--;
      this.paragraphIdx = this.sections[this.sectionIdx].paragraph_count - 1;
    }
    this.audio.pause();
    this.queue = [];
    this._updateUI();
    if (this.playing) await this._generateAndPlay(this.sectionIdx, this.paragraphIdx);
  }

  async jumpTo(sectionIdx, paragraphIdx = 0) {
    this.sectionIdx   = sectionIdx;
    this.paragraphIdx = paragraphIdx;
    this.audio.pause();
    this.queue = [];
    this._updateUI();
    if (this.playing) await this._generateAndPlay(this.sectionIdx, this.paragraphIdx);
  }

  setSpeed(s) {
    this.speed = s;
    this.audio.playbackRate = s;
    document.querySelectorAll('.speed-btn').forEach(b => {
      b.classList.toggle('active', parseFloat(b.dataset.speed) === s);
    });
  }

  // -- internal --

  async _generateAndPlay(si, pi) {
    this._setStatus('Generating…', 'loading');
    try {
      const params = new URLSearchParams({ paper_id: this.paperId, voice_id: this.voiceId, section_idx: si, paragraph_idx: pi });
      const data = await api.post(`/api/tts/generate?${params}`);
      this.queue = data.audio_urls;
      this.qIdx  = 0;
      this._playNextChunk();
      this._saveProgress();
      this._prefetchNext(si, pi);
    } catch (err) {
      this._setStatus('Error', '');
      toast(`Generation failed: ${err.message}`, 'error');
      this.playing = false;
      this._updatePlayBtn();
    }
  }

  _playNextChunk() {
    if (this.qIdx >= this.queue.length) {
      this._onParagraphEnded();
      return;
    }
    const url = this.queue[this.qIdx++];
    this.audio.src = url;
    this.audio.playbackRate = this.speed;
    this.audio.play().catch(() => {});
  }

  _onChunkEnded() {
    if (!this.playing) return;
    this._playNextChunk();
  }

  async _onParagraphEnded() {
    if (!this.playing) return;
    const sec = this.sections[this.sectionIdx];
    if (!sec) return;

    if (this.paragraphIdx < sec.paragraph_count - 1) {
      this.paragraphIdx++;
    } else if (this.sectionIdx < this.sections.length - 1) {
      this.sectionIdx++;
      this.paragraphIdx = 0;
    } else {
      this.playing = false;
      this._setStatus('Finished', 'done');
      this._updatePlayBtn();
      this._updateUI();
      toast('Finished! End of paper.', 'success', 4000);
      return;
    }
    this._updateUI();
    await this._generateAndPlay(this.sectionIdx, this.paragraphIdx);
  }

  _onAudioError() {
    if (!this.playing) return;
    // Skip bad chunk and continue
    this._playNextChunk();
  }

  async _prefetchNext(si, pi) {
    const sec = this.sections[si];
    if (!sec) return;
    let nsi = si, npi = pi + 1;
    if (npi >= sec.paragraph_count) { nsi++; npi = 0; }
    if (nsi >= this.sections.length) return;
    // Fire and forget — just warms the cache on the server
    try {
      const params = new URLSearchParams({ paper_id: this.paperId, voice_id: this.voiceId, section_idx: nsi, paragraph_idx: npi });
      await api.post(`/api/tts/generate?${params}`);
    } catch (_) {}
  }

  _saveProgress() {
    const params = new URLSearchParams({ section_idx: this.sectionIdx, paragraph_idx: this.paragraphIdx });
    fetch(`/api/progress/${this.paperId}?${params}`, { method: 'POST' }).catch(() => {});
  }

  _setStatus(label, cls = '') {
    const el = document.getElementById('player-status');
    if (!el) return;
    el.textContent = label;
    el.className = `player-status-badge ${cls}`;
  }

  _updatePlayBtn() {
    document.getElementById('icon-play')?.classList.toggle('hidden', this.playing);
    document.getElementById('icon-pause')?.classList.toggle('hidden', !this.playing);
  }

  _updateUI() {
    const sec = this.sections[this.sectionIdx];
    const label = sec ? sec.title : '—';
    const el = document.getElementById('player-section-label');
    if (el) el.textContent = `${label} · ¶${this.paragraphIdx + 1}`;

    // Highlight active section in list
    document.querySelectorAll('.section-item').forEach((item, i) => {
      item.classList.toggle('active', i === this.sectionIdx);
      item.scrollIntoView && i === this.sectionIdx && item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    // Media Session API (lock screen controls)
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title:  sec ? sec.title : 'Research Reader',
        artist: 'Research Reader',
        album:  currentPaper?.title || '',
      });
      navigator.mediaSession.setActionHandler('play',          () => player.play());
      navigator.mediaSession.setActionHandler('pause',         () => player.pause());
      navigator.mediaSession.setActionHandler('nexttrack',     () => player.next());
      navigator.mediaSession.setActionHandler('previoustrack', () => player.prev());
    }
  }
}

const player = new Player();

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------
let currentPaper   = null;
let defaultVoiceId = null;

// ---------------------------------------------------------------------------
// Batch preparation
// ---------------------------------------------------------------------------
const activePreparePolls = new Map(); // paperId → intervalId
const notifyOnComplete   = new Set(); // paperIds to fire OS notification when ready
const paperTitles        = new Map(); // paperId → title (for notification text)

function stopPreparePolling(paperId) {
  const id = activePreparePolls.get(paperId);
  if (id) { clearInterval(id); activePreparePolls.delete(paperId); }
}

function requestNotifyPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
}

function fireReadyNotification(paperId) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const title = paperTitles.get(paperId) || 'Paper';
  const n = new Notification('Research Reader', {
    body: `"${title}" is ready to listen.`,
    tag: `ready-${paperId}`,
  });
  setTimeout(() => n.close(), 10000);
}

async function loadDefaultVoice() {
  try {
    const voices = await api.get('/api/voices');
    defaultVoiceId = voices.length ? voices[0].voice_id : null;
  } catch (_) {
    defaultVoiceId = null;
  }
}

function renderPrepareUI(paperId, prepEl, s) {
  if (s.ready) {
    prepEl.innerHTML = `<span class="ready-badge">✓ Ready to listen</span>`;
    stopPreparePolling(paperId);
    if (notifyOnComplete.has(paperId)) {
      notifyOnComplete.delete(paperId);
      fireReadyNotification(paperId);
    }
    return;
  }

  if (s.status === 'running') {
    const pct = s.total > 0 ? Math.round(s.done / s.total * 100) : 0;
    const bellHtml = ('Notification' in window && Notification.permission === 'default')
      ? `<button class="prep-notify-btn" title="Enable notifications">🔔</button>`
      : '';
    prepEl.innerHTML = `
      <div class="prep-progress-wrap">
        <span class="prep-label">Preparing</span>
        <div class="prep-bar-track">
          <div class="prep-bar-fill" style="width:${pct}%"></div>
        </div>
        <span class="prep-count">${s.done} / ${s.total} ¶</span>
        ${bellHtml}
      </div>`;
    if (bellHtml) {
      prepEl.querySelector('.prep-notify-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        const perm = await Notification.requestPermission();
        if (perm === 'granted') {
          notifyOnComplete.add(paperId);
          e.target.remove();
          toast('Notifications enabled — you\'ll be notified when ready.', 'success', 3000);
        }
      });
    }
    return;
  }

  // idle / error — show prepare button
  prepEl.innerHTML = `<button class="prepare-btn">Prepare for listening</button>`;
  prepEl.querySelector('.prepare-btn').addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!defaultVoiceId) {
      toast('Add a voice first (tap the mic icon at top right).', 'error', 4000);
      return;
    }
    try {
      requestNotifyPermission();
      notifyOnComplete.add(paperId);
      const res = await api.post(`/api/papers/${paperId}/prepare?voice_id=${defaultVoiceId}`);
      renderPrepareUI(paperId, prepEl, { status: 'running', done: res.already_done || 0, total: res.total, ready: false });
      toast('Preparing audio in the background…', '', 3000);
      const interval = setInterval(async () => {
        try {
          const st = await api.get(`/api/papers/${paperId}/prepare/status?voice_id=${defaultVoiceId}`);
          renderPrepareUI(paperId, prepEl, st);
          if (st.status !== 'running') stopPreparePolling(paperId);
        } catch (_) {}
      }, 10000);
      activePreparePolls.set(paperId, interval);
    } catch (err) {
      notifyOnComplete.delete(paperId);
      toast(`Prepare failed: ${err.message}`, 'error');
    }
  });
}

async function checkInitialPrepareStatus(paperId, prepEl, title) {
  if (!defaultVoiceId) return;
  try {
    const s = await api.get(`/api/papers/${paperId}/prepare/status?voice_id=${defaultVoiceId}`);
    renderPrepareUI(paperId, prepEl, s);
    // Resume polling if server says it's still running (e.g. after page refresh)
    if (s.status === 'running' && !activePreparePolls.has(paperId)) {
      // notifyOnComplete is added when user taps the 🔔 bell in the progress bar
      // (can't request notification permission without a user gesture on mobile)
      const interval = setInterval(async () => {
        try {
          const st = await api.get(`/api/papers/${paperId}/prepare/status?voice_id=${defaultVoiceId}`);
          renderPrepareUI(paperId, prepEl, st);
          if (st.status !== 'running') stopPreparePolling(paperId);
        } catch (_) {}
      }, 10000);
      activePreparePolls.set(paperId, interval);
    }
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------
async function loadLibrary() {
  try {
    await loadDefaultVoice();
    const papers = await api.get('/api/papers');
    renderPapers(papers);
  } catch (err) {
    toast(`Failed to load papers: ${err.message}`, 'error');
  }
}

function renderPapers(papers) {
  const list  = document.getElementById('papers-list');
  const empty = document.getElementById('papers-empty');
  list.innerHTML = '';

  if (!papers.length) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  papers.forEach(p => {
    const card = document.createElement('div');
    card.className = 'paper-card';
    card.innerHTML = `
      <span class="paper-icon">📄</span>
      <div class="paper-info">
        <div class="paper-title">${esc(p.title)}</div>
        <div class="paper-meta">${p.section_count} sections · ${fmtDate(p.created_at)}</div>
        <div class="paper-prepare" id="prep-${p.paper_id}">
          <button class="prepare-btn">Prepare for listening</button>
        </div>
      </div>
      <button class="paper-delete" data-id="${p.paper_id}" title="Delete">×</button>
    `;

    const prepEl = card.querySelector('.paper-prepare');

    // Wire up the default prepare button
    prepEl.querySelector('.prepare-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!defaultVoiceId) {
        toast('Add a voice first (tap the mic icon at top right).', 'error', 4000);
        return;
      }
      try {
        requestNotifyPermission();
        notifyOnComplete.add(p.paper_id);
        const res = await api.post(`/api/papers/${p.paper_id}/prepare?voice_id=${defaultVoiceId}`);
        renderPrepareUI(p.paper_id, prepEl, { status: 'running', done: res.already_done || 0, total: res.total, ready: false });
        toast('Preparing audio in the background…', '', 3000);
        const interval = setInterval(async () => {
          try {
            const st = await api.get(`/api/papers/${p.paper_id}/prepare/status?voice_id=${defaultVoiceId}`);
            renderPrepareUI(p.paper_id, prepEl, st);
            if (st.status !== 'running') stopPreparePolling(p.paper_id);
          } catch (_) {}
        }, 10000);
        activePreparePolls.set(p.paper_id, interval);
      } catch (err) {
        notifyOnComplete.delete(p.paper_id);
        toast(`Prepare failed: ${err.message}`, 'error');
      }
    });

    card.addEventListener('click', (e) => {
      if (e.target.closest('.paper-delete') || e.target.closest('.paper-prepare')) return;
      openPaper(p.paper_id);
    });

    card.querySelector('.paper-delete').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${p.title}"?`)) return;
      try {
        stopPreparePolling(p.paper_id);
        await api.del(`/api/papers/${p.paper_id}`);
        toast('Paper deleted.', 'success');
        loadLibrary();
      } catch (err) { toast(err.message, 'error'); }
    });

    list.appendChild(card);

    // Store title for use in ready notification
    paperTitles.set(p.paper_id, p.title);
    // Check actual status from server (shows Ready badge / progress if already running)
    checkInitialPrepareStatus(p.paper_id, prepEl, p.title);
  });
}

// ---------------------------------------------------------------------------
// Reader
// ---------------------------------------------------------------------------
async function openPaper(paperId) {
  showLoading('Loading paper…');
  try {
    const paper = await api.get(`/api/papers/${paperId}`);
    const progress = await api.get(`/api/progress/${paperId}`);
    currentPaper = paper;

    document.getElementById('reader-title').textContent = paper.title;

    renderSections(paper.sections);
    await populateVoiceSelect();

    // Resume from progress
    player.load(paperId, getSelectedVoice(), paper.sections, progress.section_idx, progress.paragraph_idx);

    showScreen('screen-reader');
  } catch (err) {
    toast(`Failed to open paper: ${err.message}`, 'error');
  } finally {
    hideLoading();
  }
}

function renderSections(sections) {
  const list = document.getElementById('sections-list');
  list.innerHTML = '';
  sections.forEach((sec, i) => {
    const item = document.createElement('div');
    item.className = `section-item${sec.is_boilerplate ? ' boilerplate' : ''}`;
    item.dataset.idx = i;
    item.innerHTML = `
      <span class="playing-dot"></span>
      <span class="section-num">${i + 1}</span>
      <span class="section-name">${esc(sec.title)}</span>
      <span class="section-paras">${sec.paragraph_count}¶</span>
    `;
    item.addEventListener('click', () => player.jumpTo(i));
    list.appendChild(item);
  });
}

async function populateVoiceSelect() {
  const sel = document.getElementById('voice-select');
  const current = sel.value;
  try {
    const voices = await api.get('/api/voices');
    sel.innerHTML = '<option value="">— select voice —</option>';
    voices.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.voice_id;
      opt.textContent = v.name;
      sel.appendChild(opt);
    });
    if (current) sel.value = current;
    if (!sel.value && voices.length) sel.value = voices[0].voice_id;
  } catch (_) {}
}

function getSelectedVoice() {
  return document.getElementById('voice-select')?.value || null;
}

// ---------------------------------------------------------------------------
// Voice sheet
// ---------------------------------------------------------------------------
let selectedWavFile = null;

function openVoiceSheet() {
  document.getElementById('voice-sheet').classList.remove('hidden');
  loadVoices();
}

function closeVoiceSheet() {
  document.getElementById('voice-sheet').classList.add('hidden');
}

async function loadVoices() {
  try {
    const voices = await api.get('/api/voices');
    renderVoices(voices);
  } catch (err) {
    toast(`Failed to load voices: ${err.message}`, 'error');
  }
}

function renderVoices(voices) {
  const list  = document.getElementById('voices-list');
  const empty = document.getElementById('voices-empty');
  list.innerHTML = '';

  if (!voices.length) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  voices.forEach(v => {
    const card = document.createElement('div');
    card.className = 'voice-card';
    card.innerHTML = `
      <div style="flex:1;min-width:0">
        <div class="voice-card-name">${esc(v.name)}</div>
        <div class="voice-card-date">${fmtDate(v.created_at)}</div>
      </div>
      <div class="voice-actions">
        <button class="voice-action-btn test-btn"   data-id="${v.voice_id}">Test</button>
        <button class="voice-action-btn delete-btn" data-id="${v.voice_id}">Delete</button>
      </div>
    `;
    card.querySelector('.test-btn').addEventListener('click', () => testVoice(v.voice_id, v.name));
    card.querySelector('.delete-btn').addEventListener('click', () => deleteVoice(v.voice_id, v.name));
    list.appendChild(card);
  });
}

async function testVoice(voiceId, name) {
  showLoading(`Generating test for "${name}"… (first run downloads ~2 GB model)`);
  try {
    const data = await api.post(`/api/voices/${voiceId}/test`);
    hideLoading();
    const audio = new Audio(data.audio_url);
    audio.play().catch(() => toast('Tap play to hear the test.'));
    toast(`Testing voice: ${name}`, 'success');
  } catch (err) {
    hideLoading();
    toast(`Test failed: ${err.message}`, 'error');
  }
}

async function deleteVoice(voiceId, name) {
  if (!confirm(`Delete voice "${name}"?`)) return;
  try {
    await api.del(`/api/voices/${voiceId}`);
    toast('Voice deleted.', 'success');
    loadVoices();
    // Refresh voice select if we're in the reader
    if (!document.getElementById('screen-reader').classList.contains('hidden')) {
      populateVoiceSelect();
    }
  } catch (err) { toast(err.message, 'error'); }
}

async function saveVoice() {
  const name = document.getElementById('voice-name-input').value.trim();
  if (!name)              { toast('Enter a name for this voice.', 'error'); return; }
  if (!selectedWavFile)   { toast('Choose a WAV file first.', 'error'); return; }

  showLoading('Saving voice…');
  try {
    const fd = new FormData();
    fd.append('file', selectedWavFile);
    fd.append('name', name);
    await api.postForm('/api/voices/upload', fd);
    toast(`Voice "${name}" saved!`, 'success');
    // Reset
    document.getElementById('voice-name-input').value = '';
    document.getElementById('wav-filename').textContent = '';
    document.getElementById('wav-filename').classList.add('hidden');
    document.getElementById('btn-save-voice').disabled = true;
    selectedWavFile = null;
    loadVoices();
  } catch (err) {
    toast(`Failed to save voice: ${err.message}`, 'error');
  } finally {
    hideLoading();
  }
}

// ---------------------------------------------------------------------------
// Log viewer
// ---------------------------------------------------------------------------
function openLogSheet() {
  document.getElementById('log-sheet').classList.remove('hidden');
  fetchLog();
}

function closeLogSheet() {
  document.getElementById('log-sheet').classList.add('hidden');
}

async function fetchLog() {
  const el = document.getElementById('log-content');
  el.textContent = 'Loading…';
  try {
    const data = await api.get('/api/log?lines=80');
    if (!data.lines.length) { el.textContent = 'Log is empty.'; return; }
    // Colour ERROR and WARNING lines
    el.innerHTML = data.lines.map(line => {
      const l = esc(line);
      if (line.includes('[ERROR]'))   return `<span class="log-error">${l}</span>`;
      if (line.includes('[WARNING]')) return `<span class="log-warn">${l}</span>`;
      return l;
    }).join('\n');
    el.scrollTop = el.scrollHeight;
  } catch (err) {
    el.textContent = `Could not fetch log: ${err.message}`;
  }
}

// ---------------------------------------------------------------------------
// PDF upload
// ---------------------------------------------------------------------------
async function uploadPDF(file) {
  if (!file) return;
  showLoading('Parsing PDF…\nDetecting columns, fixing hyphenation, extracting sections…');
  try {
    const fd = new FormData();
    fd.append('file', file);
    const data = await api.postForm('/api/papers/upload', fd);
    toast(`Parsed "${data.title}" — ${data.section_count} sections.`, 'success', 4000);
    loadLibrary();
  } catch (err) {
    toast(`Upload failed: ${err.message}`, 'error');
  } finally {
    hideLoading();
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {

  // Library
  document.getElementById('upload-pdf-input').addEventListener('change', e => {
    uploadPDF(e.target.files[0]);
    e.target.value = '';
  });

  document.getElementById('btn-open-voices').addEventListener('click', openVoiceSheet);

  // Reader
  document.getElementById('btn-back').addEventListener('click', () => {
    player.pause();
    showScreen('screen-library');
    loadLibrary(); // refresh in case voices changed
  });

  document.getElementById('voice-select').addEventListener('change', e => {
    player.voiceId = e.target.value || null;
  });

  document.getElementById('btn-play').addEventListener('click',  () => player.togglePlay());
  document.getElementById('btn-prev').addEventListener('click',  () => player.prev());
  document.getElementById('btn-next').addEventListener('click',  () => player.next());

  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => player.setSpeed(parseFloat(btn.dataset.speed)));
  });

  // Voice sheet
  document.getElementById('btn-close-voices').addEventListener('click', closeVoiceSheet);
  document.getElementById('sheet-backdrop').addEventListener('click', closeVoiceSheet);

  // Log sheet
  document.getElementById('btn-open-log').addEventListener('click', openLogSheet);
  document.getElementById('btn-close-log').addEventListener('click', closeLogSheet);
  document.getElementById('log-backdrop').addEventListener('click', closeLogSheet);
  document.getElementById('btn-refresh-log').addEventListener('click', fetchLog);

  document.getElementById('upload-wav-input').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    selectedWavFile = file;
    const label = document.getElementById('wav-filename');
    label.textContent = `Selected: ${file.name}`;
    label.classList.remove('hidden');
    document.getElementById('btn-save-voice').disabled = false;
    e.target.value = '';
  });

  document.getElementById('btn-save-voice').addEventListener('click', saveVoice);

  // Init
  loadLibrary();
  showScreen('screen-library');
});
