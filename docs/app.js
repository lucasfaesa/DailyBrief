/* ================================================================
   DailyBrief – app.js
   Lightweight SPA with hash-based routing, data.json loader,
   archive explorer, and Service Worker / PWA integration.
   ================================================================ */

'use strict';

// ── Theme Mapping (Key → English Label + Icon) ──────────────────
const THEME_LABELS = {
  national_politics:      { label: 'National Politics',       icon: '🏛️' },
  international_politics: { label: 'World News',              icon: '🌍' },
  technology:             { label: 'Technology',              icon: '💻' },
  ai:                     { label: 'Artificial Intelligence',  icon: '🤖' },
  gaming:                 { label: 'Gaming',                  icon: '🎮' },
  anime:                  { label: 'Anime & Manga',           icon: '🎌' },
  science:                { label: 'Science',                 icon: '🔬' },
  economy:                { label: 'Economy & Markets',       icon: '📈' },
  others:                 { label: 'General News',            icon: '🌐' },
  // Backwards compatibility keys
  politica_nacional:      { label: 'National Politics',       icon: '🏛️' },
  politica_internacional: { label: 'World News',              icon: '🌍' },
  tecnologia:             { label: 'Technology',              icon: '💻' },
  games:                  { label: 'Gaming',                  icon: '🎮' },
  animes:                 { label: 'Anime & Manga',           icon: '🎌' },
  ciencia:                { label: 'Science',                 icon: '🔬' },
  economia:               { label: 'Economy & Markets',       icon: '📈' },
  outros:                 { label: 'General News',            icon: '🌐' },
};

// ── Global State ────────────────────────────────────────────────
let _data = null;
let _allItems = {};
let _activeTheme = null;

// ── DOM Elements ────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const els = {
  loading:        $('loading'),
  error:          $('error-screen'),
  errorMsg:       $('error-msg'),
  home:           $('home-view'),
  detail:         $('detail-view'),
  detailContent:  $('detail-content'),
  archive:        $('archive-view'),
  archiveList:    $('archive-list'),
  tabs:           $('theme-tabs'),
  sections:       $('theme-sections'),
  generatedAt:    $('generated-at'),
  btnArchive:     $('btn-archive'),
  btnInstall:     $('btn-install'),
};

// ── Utilities ───────────────────────────────────────────────────

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function showOnly(...toShow) {
  [els.loading, els.error, els.home, els.detail, els.archive].forEach(hide);
  toShow.forEach(show);
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'full', timeStyle: 'short', timeZone: 'America/Sao_Paulo'
    }).format(new Date(iso));
  } catch { return iso; }
}

function escHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function dots(relevance) {
  return Array.from({ length: 5 }, (_, i) =>
    `<span class="dot${i < relevance ? ' filled' : ''}"></span>`
  ).join('');
}

// ── Data Fetching ───────────────────────────────────────────────

async function loadJSON(path) {
  const resp = await fetch(path, { cache: 'no-store' });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function loadData(path = 'data.json') {
  showOnly(els.loading);
  try {
    _data = await loadJSON(path);
    _allItems = {};
    for (const item of (_data.all_items || [])) {
      _allItems[item.id] = item;
    }
    renderHome();
  } catch (err) {
    console.error(err);
    els.errorMsg.textContent = 'Unable to load stories. Please check your connection.';
    showOnly(els.error);
  }
}

// ── Home View Rendering ─────────────────────────────────────────

function renderHome() {
  const themes = _data.themes || {};
  const orderedKeys = Object.keys(THEME_LABELS).filter(k => themes[k]?.length);

  // Unique normalized keys to prevent duplicate tabs
  const renderedThemes = new Set();

  if (_data.generated_at) {
    els.generatedAt.textContent = `Updated on ${formatDate(_data.generated_at)}`;
  }

  // Filter Tabs
  els.tabs.innerHTML = '';
  const allTab = document.createElement('button');
  allTab.className = 'tab-btn active';
  allTab.textContent = '🗞️ All';
  allTab.dataset.theme = 'all';
  allTab.addEventListener('click', () => activateTab('all'));
  els.tabs.appendChild(allTab);

  orderedKeys.forEach(key => {
    if (renderedThemes.has(key)) return;
    renderedThemes.add(key);
    const meta = THEME_LABELS[key];
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.textContent = `${meta.icon} ${meta.label}`;
    btn.dataset.theme = key;
    btn.addEventListener('click', () => activateTab(key));
    els.tabs.appendChild(btn);
  });

  // Topic Sections
  els.sections.innerHTML = '';
  orderedKeys.forEach(key => {
    const items = themes[key] || [];
    const meta = THEME_LABELS[key];
    const section = document.createElement('section');
    section.className = 'theme-section';
    section.id = `section-${key}`;
    section.dataset.theme = key;

    section.innerHTML = `
      <div class="theme-header" role="button" tabindex="0"
           aria-expanded="true" aria-controls="items-${key}">
        <h2>${meta.icon} ${meta.label} <small>(${items.length})</small></h2>
        <span class="theme-chevron">▼</span>
      </div>
      <div class="theme-items" id="items-${key}"></div>
    `;

    const header = section.querySelector('.theme-header');
    const toggleCollapse = () => {
      section.classList.toggle('collapsed');
      header.setAttribute('aria-expanded', !section.classList.contains('collapsed'));
    };
    header.addEventListener('click', toggleCollapse);
    header.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') toggleCollapse(); });

    const container = section.querySelector('.theme-items');
    items.forEach(item => container.appendChild(buildCard(item)));

    els.sections.appendChild(section);
  });

  _activeTheme = 'all';
  showOnly(els.home);
  window.scrollTo(0, 0);
}

function activateTab(theme) {
  _activeTheme = theme;
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === theme);
  });
  document.querySelectorAll('.theme-section').forEach(sec => {
    sec.style.display = (theme === 'all' || sec.dataset.theme === theme) ? '' : 'none';
  });
}

function buildCard(item) {
  const btn = document.createElement('button');
  btn.className = 'news-card';
  btn.setAttribute('aria-label', `View story: ${item.title}`);
  const summary = item.short_summary || item.resumo_curto;
  const relevance = item.relevance || item.relevancia || 0;

  btn.innerHTML = `
    <p class="card-title">${escHtml(item.title)}</p>
    ${summary ? `<p class="card-summary">${escHtml(summary)}</p>` : ''}
    <div class="card-meta">
      <span class="tag-source">${escHtml(item.source)}</span>
      <div class="relevance-dots" aria-label="Relevance ${relevance} of 5">
        ${dots(relevance)}
      </div>
    </div>
  `;
  btn.addEventListener('click', () => {
    location.hash = `/item/${item.id}`;
  });
  return btn;
}

// ── Detail View Rendering ───────────────────────────────────────

function renderDetail(id) {
  const item = _allItems[id];
  if (!item) {
    location.hash = '';
    return;
  }

  const relevance = item.relevance || item.relevancia || 0;
  const articleSummary = item.article_summary || item.resumo_materia;
  const shortSummary = item.short_summary || item.resumo_curto;
  const commentsSummary = item.comments_summary || item.resumo_comentarios;

  let html = `
    <h2>${escHtml(item.title)}</h2>
    <div class="detail-meta">
      <span class="tag-source">${escHtml(item.source)}</span>
      ${item.published ? `<span style="font-size:.78rem;color:var(--text-muted)">${formatDate(item.published)}</span>` : ''}
      <div class="relevance-dots" aria-label="Relevance ${relevance} of 5">
        ${dots(relevance)}
      </div>
    </div>
  `;

  if (articleSummary) {
    html += `
      <div class="detail-section">
        <h3>📝 Story Overview</h3>
        <p>${escHtml(articleSummary)}</p>
      </div>
    `;
  } else if (shortSummary) {
    html += `
      <div class="detail-section">
        <h3>📝 Summary</h3>
        <p>${escHtml(shortSummary)}</p>
      </div>
    `;
  }

  if (commentsSummary) {
    html += `
      <div class="detail-section">
        <h3>💬 Community Discussion</h3>
        <p>${escHtml(commentsSummary)}</p>
        <p class="comments-notice">⚠️ Synthesized from user comments, not verified journalistic facts.</p>
      </div>
    `;
  }

  html += `<a class="btn-open" href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer">
    🔗 Open Original Article
  </a>`;

  els.detailContent.innerHTML = html;
  showOnly(els.detail);
  window.scrollTo(0, 0);
}

// ── Archive View Rendering ──────────────────────────────────────

async function renderArchive() {
  showOnly(els.archive);
  els.archiveList.innerHTML = '<p style="color:var(--text-muted);padding:16px">Loading past editions…</p>';

  try {
    const index = await loadJSON('archive/index.json');
    if (!index.dates?.length) throw new Error('empty');

    els.archiveList.innerHTML = '';
    [...index.dates].reverse().forEach(({ date, total_items }) => {
      const div = document.createElement('div');
      div.className = 'archive-item';
      div.innerHTML = `
        <span class="archive-date">${date}</span>
        <span class="archive-count">${total_items} stories</span>
      `;
      div.addEventListener('click', () => loadData(`archive/${date}.json`));
      els.archiveList.appendChild(div);
    });
  } catch {
    els.archiveList.innerHTML = '<p style="color:var(--text-muted);padding:16px">No past editions available yet.</p>';
  }
}

// ── Hash Routing ────────────────────────────────────────────────

function route() {
  const hash = location.hash.replace(/^#\/?/, '');

  if (!hash || hash === '/') {
    if (_data) {
      showOnly(els.home);
      window.scrollTo(0, 0);
    } else {
      loadData();
    }
  } else if (hash.startsWith('item/')) {
    const id = hash.slice(5);
    if (!_data) {
      loadData().then(() => renderDetail(id));
    } else {
      renderDetail(id);
    }
  } else if (hash === 'archive') {
    renderArchive();
  }
}

// ── PWA Install Handler ─────────────────────────────────────────

let _deferredInstall = null;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  _deferredInstall = e;
  show(els.btnInstall);
});

els.btnInstall.addEventListener('click', async () => {
  if (!_deferredInstall) return;
  _deferredInstall.prompt();
  const { outcome } = await _deferredInstall.userChoice;
  if (outcome === 'accepted') hide(els.btnInstall);
  _deferredInstall = null;
});

// Service Worker Registration
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(console.error);
}

// ── Event Listeners ─────────────────────────────────────────────

window.addEventListener('hashchange', route);
els.btnArchive.addEventListener('click', () => { location.hash = 'archive'; });

// ── Inline HTML Exposure ────────────────────────────────────────
window.App = {
  loadData,
  goHome() { location.hash = ''; },
};

// ── Bootstrap ───────────────────────────────────────────────────
route();
