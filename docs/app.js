/* ================================================================
   DailyBrief – app.js
   Lightweight SPA with hash-based routing, data.json loader,
   archive explorer, and Service Worker / PWA integration.
   ================================================================ */

'use strict';

// Order here = tab order
const THEMES = {
  economy:                { label: 'Economy',           color: '#30a46c' },
  technology:             { label: 'Technology',        color: '#8e7bff' },
  ai:                     { label: 'AI',                color: '#d864d8' },
  concursos:              { label: 'Public Exams (ES)', color: '#00b4d8' },
  science:                { label: 'Science',           color: '#12a594' },
  gaming:                 { label: 'Games',             color: '#f76b15' },
  steamdeck:              { label: 'Steam Deck',        color: '#1a9fff' },
  game_dev:               { label: 'Game Dev',          color: '#ffb224' },
  custom_engines:         { label: 'Custom Engines',    color: '#0090ff' },
  anime:                  { label: 'Anime',             color: '#ff5d8f' },
  martial_arts:           { label: 'Judo & Jiu-Jitsu',  color: '#c2410c' },
  movies:                 { label: 'Movies & TV',       color: '#e54666' },
  crypto:                 { label: 'Crypto',            color: '#f7931a' },
  others:                 { label: 'General',           color: '#8b8d98' },
  national_politics:      { label: 'National Politics', color: '#e5484d' },
  international_politics: { label: 'World',             color: '#3e9bff' },
};

// Archives generated before the English refactor use Portuguese keys;
// judo and bjj are separate pipeline themes (capped 10 each) sharing one tab
const THEME_COMPAT = {
  judo: 'martial_arts', bjj: 'martial_arts',
  politica_nacional: 'national_politics', politica_internacional: 'international_politics',
  tecnologia: 'technology', ia: 'ai', games: 'gaming', animes: 'anime',
  ciencia: 'science', economia: 'economy', concursos_es: 'concursos', outros: 'others',
};

const HOME_PER_THEME = 4;
const HIGHLIGHTS = 5;

let _data = null;
let _byId = {};
let _byTheme = {};
let _activeTheme = 'all';
let _homeScroll = 0;

// Opened items persist across sessions; capped so localStorage never grows unbounded
const READ_KEY = 'db-read';
const READ_MAX = 1000;
let _read = JSON.parse(localStorage.getItem(READ_KEY) || '[]');

function markRead(id) {
  _read = [..._read.filter(r => r !== id), id].slice(-READ_MAX);
  localStorage.setItem(READ_KEY, JSON.stringify(_read));
}

// Favorites keep a full copy of the item: data.json is replaced every run, an id alone would dangle
const FAV_KEY = 'db-favs';
let _favs = JSON.parse(localStorage.getItem(FAV_KEY) || '[]');
const isFav = id => _favs.some(f => f.id === id);

function toggleFav(item) {
  _favs = isFav(item.id) ? _favs.filter(f => f.id !== item.id) : [{ ...item, saved_at: new Date().toISOString() }, ..._favs];
  localStorage.setItem(FAV_KEY, JSON.stringify(_favs));
  renderTabs();
}

const $ = id => document.getElementById(id);

const els = {
  loading:       $('loading'),
  error:         $('error-screen'),
  errorMsg:      $('error-msg'),
  home:          $('home-view'),
  detail:        $('detail-view'),
  detailContent: $('detail-content'),
  archive:       $('archive-view'),
  archiveList:   $('archive-list'),
  tabs:          $('theme-tabs'),
  generatedAt:   $('generated-at'),
  btnArchive:    $('btn-archive'),
  btnInstall:    $('btn-install'),
};

// ── Utilities ───────────────────────────────────────────────────

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function showOnly(...toShow) {
  [els.loading, els.error, els.home, els.detail, els.archive].forEach(hide);
  toShow.forEach(show);
}

function formatDate(iso, opts = { dateStyle: 'long', timeStyle: 'short' }) {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat('en-US', { ...opts, timeZone: 'America/Sao_Paulo' }).format(new Date(iso));
  } catch { return iso; }
}

function timeAgo(iso) {
  const h = Math.round((Date.now() - new Date(iso)) / 36e5);
  if (!iso || isNaN(h)) return '';
  return h < 1 ? 'now' : h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}

function escHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const themeOf = item => {
  const raw = item.theme || item.tema || 'others';
  return THEMES[raw] ? raw : (THEME_COMPAT[raw] || 'others');
};
const relOf = item => item.relevance || item.relevancia || 0;
const shortOf = item => item.short_summary || item.resumo_curto;
const longOf = item => item.article_summary || item.resumo_materia;
const commentsOf = item => item.comments_summary || item.resumo_comentarios;

function videoBlock(video) {
  if (!video?.url) return '';
  return video.type === 'video'
    ? `<video class="detail-video" controls preload="metadata" src="${escHtml(video.url)}"></video>`
    : `<iframe class="detail-video" src="${escHtml(video.url)}" loading="lazy"
        allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
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
    _byId = {};
    _byTheme = Object.fromEntries(Object.keys(THEMES).map(k => [k, []]));
    for (const item of (_data.all_items || [])) {
      _byId[item.id] = item;
      _byTheme[themeOf(item)].push(item);
    }
    Object.values(_byTheme).forEach(list => list.sort((a, b) => relOf(b) - relOf(a)));
    els.generatedAt.textContent = _data.generated_at ? formatDate(_data.generated_at) : '';
    renderTabs();
    selectTheme('all');
  } catch (err) {
    console.error(err);
    els.errorMsg.textContent = 'Could not load the news. Check your connection.';
    showOnly(els.error);
  }
}

// ── Home ────────────────────────────────────────────────────────

function renderTabs() {
  const tabs = [['all', 'Highlights', _data.all_items?.length || 0],
    ...Object.entries(THEMES).map(([k, t]) => [k, t.label, _byTheme[k].length]),
    ['favorites', '★ Favorites', _favs.length]];
  els.tabs.innerHTML = tabs.map(([key, label, n]) => `
    <button class="tab-btn${key === _activeTheme ? ' active' : ''}" role="tab" data-theme="${key}"
            style="--c:${THEMES[key]?.color || 'var(--accent)'}">
      ${label}<span class="tab-count">${n}</span>
    </button>`).join('');
  els.tabs.querySelectorAll('.tab-btn').forEach(btn =>
    btn.addEventListener('click', () => selectTheme(btn.dataset.theme)));
}

function selectTheme(theme) {
  _activeTheme = theme;
  els.tabs.querySelectorAll('.tab-btn').forEach(btn => {
    const on = btn.dataset.theme === theme;
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-selected', on);
    if (on) revealTab(btn);
  });
  _homeScroll = 0;
  if (location.hash.replace(/^#\/?/, '')) location.hash = '';
  renderHome();
}

function renderHome() {
  if (_activeTheme === 'all') {
    // Top 5 highlights across all themes, at most 1 item per theme (the strongest overall leads)
    const top = Object.values(_byTheme)
      .filter(l => l.length)
      .map(l => l[0])
      .sort((a, b) => relOf(b) - relOf(a))
      .slice(0, HIGHLIGHTS);
    const topIds = new Set(top.map(i => i.id));
    let html = top.length ? `<section class="highlights">${top.map((it, i) => card(it, i === 0 ? 'lead' : 'feature')).join('')}</section>` : '';
    for (const [key, t] of Object.entries(THEMES)) {
      const items = _byTheme[key].filter(i => !topIds.has(i.id));
      if (!items.length) continue;
      html += `
        <section class="theme-section" data-theme="${key}" style="--c:${t.color}">
          <h2 class="section-title"><span>${t.label}</span></h2>
          <div class="card-list">${items.slice(0, HOME_PER_THEME).map(i => card(i)).join('')}</div>
          ${items.length > HOME_PER_THEME
            ? `<button class="btn-more" data-theme="${key}">See all ${_byTheme[key].length} ${t.label} →</button>` : ''}
        </section>`;
    }
    els.home.innerHTML = html || empty();
  } else if (_activeTheme === 'favorites') {
    els.home.innerHTML = `
      <section class="theme-section" style="--c:var(--accent)">
        <h2 class="page-title">Favorites</h2>
        ${_favs.length
          ? `<div class="card-list">${_favs.map(i => card(i)).join('')}</div>`
          : '<p class="empty">No favorites yet. Open an article and tap ☆ Favorite.</p>'}
      </section>`;
  } else {
    const t = THEMES[_activeTheme];
    const items = _byTheme[_activeTheme];
    els.home.innerHTML = `
      <section class="theme-section" style="--c:${t.color}">
        <h2 class="page-title">${t.label}</h2>
        ${items.length ? `<div class="card-list">${items.map(i => card(i)).join('')}</div>` : empty()}
      </section>`;
  }

  els.home.querySelectorAll('[data-id]').forEach(el =>
    el.addEventListener('click', () => {
      _homeScroll = window.scrollY;
      location.hash = `/item/${el.dataset.id}`;
    }));
  els.home.querySelectorAll('.btn-more').forEach(el =>
    el.addEventListener('click', () => selectTheme(el.dataset.theme)));

  showOnly(els.home);
  window.scrollTo(0, _homeScroll);
  updateSpy();
}

// Mobile tab strip scrolls horizontally: bring a tab into view without moving the page vertically
function revealTab(btn) {
  const strip = els.tabs;
  if (strip.scrollWidth <= strip.clientWidth) return;
  strip.scrollTo({ left: btn.offsetLeft - (strip.clientWidth - btn.offsetWidth) / 2, behavior: 'smooth' });
}

// On the Destaques page, light up the tab of the theme section currently under the header
function updateSpy() {
  let current = null;
  if (_activeTheme === 'all' && !els.home.classList.contains('hidden')) {
    const line = $('app-header').getBoundingClientRect().bottom + 24;
    for (const sec of els.home.querySelectorAll('.theme-section[data-theme]')) {
      if (sec.getBoundingClientRect().top > line) break;
      current = sec.dataset.theme;
    }
  }
  els.tabs.querySelectorAll('.tab-btn').forEach(btn => {
    const on = btn.dataset.theme === current;
    if (on && !btn.classList.contains('spy')) revealTab(btn);
    btn.classList.toggle('spy', on);
  });
}

let _spyQueued = false;
window.addEventListener('scroll', () => {
  if (_spyQueued) return;
  _spyQueued = true;
  requestAnimationFrame(() => { _spyQueued = false; updateSpy(); });
}, { passive: true });

function empty() {
  return '<p class="empty">No news in this category today.</p>';
}

function card(item, variant = '') {
  const t = THEMES[themeOf(item)];
  const summary = variant === 'lead' ? (longOf(item) || shortOf(item)) : shortOf(item);
  const hasSummary = summary && summary !== item.title;
  const last = _read[_read.length - 1] === item.id;
  const read = last || _read.includes(item.id);
  return `
    <button class="news-card ${variant}${read ? ' read' : ''}${last ? ' last' : ''}" data-id="${escHtml(item.id)}" style="--c:${t.color}">
      ${variant ? `<span class="kicker">${t.label}</span>` : ''}
      <span class="card-title">${escHtml(item.title)}</span>
      ${hasSummary ? `<span class="card-summary">${escHtml(summary)}</span>` : ''}
      <span class="card-meta">
        <span>${escHtml(item.source)}</span>
        ${item.published ? `<span>· ${timeAgo(item.published)}</span>` : ''}
        ${last ? '<span class="read-tag">Last opened</span>' : read ? '<span class="read-tag">✓ Read</span>' : ''}
        ${isFav(item.id) ? '<span class="fav-tag" aria-label="Favorite">★</span>' : ''}
        ${relOf(item) >= 4 ? '<span class="badge">Important</span>' : ''}
      </span>
    </button>`;
}

// ── Detail ──────────────────────────────────────────────────────

function renderDetail(id) {
  const item = _byId[id] || _favs.find(f => f.id === id);
  if (!item) { location.hash = ''; return; }
  markRead(id);
  const t = THEMES[themeOf(item)];
  const summary = longOf(item) || (shortOf(item) !== item.title ? shortOf(item) : '');
  const comments = commentsOf(item);

  els.detailContent.style.setProperty('--c', t.color);
  els.detailContent.innerHTML = `
    <span class="kicker">${t.label}</span>
    <h1 class="detail-title">${escHtml(item.title)}</h1>
    <p class="detail-meta">${escHtml(item.source)}${item.published ? ` · ${formatDate(item.published)}` : ''}</p>
    <button id="btn-fav" class="btn-fav"></button>
    ${videoBlock(item.video)}

    <section class="detail-section ai">
      <h3>AI Summary</h3>
      ${summary
        ? `<p>${escHtml(summary)}</p>`
        : '<p class="muted">Summary unavailable for this article (the AI did not process this edition).</p>'}
    </section>

    ${comments ? `
      <section class="detail-section">
        <h3>What the community says</h3>
        <p>${escHtml(comments)}</p>
        <p class="muted small">Synthesized from user comments — opinions, not verified facts.</p>
      </section>` : ''}

    <a class="btn-primary" href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer">Read original article ↗</a>
  `;
  const favBtn = $('btn-fav');
  const paintFav = () => {
    const on = isFav(item.id);
    favBtn.textContent = on ? '★ Favorited' : '☆ Favorite';
    favBtn.classList.toggle('on', on);
    favBtn.setAttribute('aria-pressed', on);
  };
  favBtn.addEventListener('click', () => { toggleFav(item); paintFav(); });
  paintFav();

  showOnly(els.detail);
  window.scrollTo(0, 0);
}

// ── Archive ─────────────────────────────────────────────────────

async function renderArchive() {
  showOnly(els.archive);
  els.archiveList.innerHTML = '<p class="empty">Loading…</p>';
  try {
    const index = await loadJSON('archive/index.json');
    if (!index.dates?.length) throw new Error('empty');
    els.archiveList.innerHTML = '';
    [...index.dates].reverse().forEach(({ date, total_items }) => {
      const btn = document.createElement('button');
      btn.className = 'archive-item';
      btn.innerHTML = `
        <span class="archive-date">${formatDate(date + 'T12:00:00', { dateStyle: 'full' })}</span>
        <span class="archive-count">${total_items} news items</span>`;
      btn.addEventListener('click', () => { location.hash = ''; loadData(`archive/${date}.json`); });
      els.archiveList.appendChild(btn);
    });
  } catch {
    els.archiveList.innerHTML = '<p class="empty">No previous editions yet.</p>';
  }
}

// ── Hash Routing ────────────────────────────────────────────────

function route() {
  const hash = location.hash.replace(/^#\/?/, '');
  if (hash.startsWith('item/')) {
    const id = hash.slice(5);
    _data ? renderDetail(id) : loadData().then(() => renderDetail(id));
  } else if (hash === 'archive') {
    renderArchive();
  } else {
    _data ? renderHome() : loadData();
  }
}

// ── PWA Install ─────────────────────────────────────────────────

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

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(console.error);
}

window.addEventListener('hashchange', route);
els.btnArchive.addEventListener('click', () => { location.hash = 'archive'; });

window.App = {
  loadData,
  selectTheme,
  goHome() { location.hash = ''; },
};

route();
