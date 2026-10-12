/* ================================================================
   DailyBrief – app.js
   Lightweight SPA with hash-based routing, data.json loader,
   archive explorer, and Service Worker / PWA integration.
   ================================================================ */

'use strict';

// Order here = tab order
const THEMES = {
  national_politics:      { label: 'Política Nacional', color: '#e5484d' },
  international_politics: { label: 'Mundo',             color: '#3e9bff' },
  economy:                { label: 'Economia',          color: '#30a46c' },
  technology:             { label: 'Tecnologia',        color: '#8e7bff' },
  ai:                     { label: 'IA',                color: '#d864d8' },
  science:                { label: 'Ciência',           color: '#12a594' },
  gaming:                 { label: 'Games',             color: '#f76b15' },
  game_dev:               { label: 'Game Dev',          color: '#ffb224' },
  custom_engines:         { label: 'Custom Engines',    color: '#0090ff' },
  anime:                  { label: 'Animes',            color: '#ff5d8f' },
  movies:                 { label: 'Filmes & Séries',   color: '#e54666' },
  crypto:                 { label: 'Cripto',            color: '#f7931a' },
  others:                 { label: 'Geral',             color: '#8b8d98' },
};

// Archives generated before the English refactor use Portuguese keys
const THEME_COMPAT = {
  politica_nacional: 'national_politics', politica_internacional: 'international_politics',
  tecnologia: 'technology', ia: 'ai', games: 'gaming', animes: 'anime',
  ciencia: 'science', economia: 'economy', outros: 'others',
};

const HOME_PER_THEME = 4;

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
    return new Intl.DateTimeFormat('pt-BR', { ...opts, timeZone: 'America/Sao_Paulo' }).format(new Date(iso));
  } catch { return iso; }
}

function timeAgo(iso) {
  const h = Math.round((Date.now() - new Date(iso)) / 36e5);
  if (!iso || isNaN(h)) return '';
  return h < 1 ? 'agora' : h < 24 ? `há ${h}h` : `há ${Math.round(h / 24)}d`;
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
    els.errorMsg.textContent = 'Não foi possível carregar as notícias. Verifique sua conexão.';
    showOnly(els.error);
  }
}

// ── Home ────────────────────────────────────────────────────────

function renderTabs() {
  const tabs = [['all', 'Destaques', _data.all_items?.length || 0],
    ...Object.entries(THEMES).map(([k, t]) => [k, t.label, _byTheme[k].length])];
  els.tabs.innerHTML = tabs.map(([key, label, n]) => `
    <button class="tab-btn" role="tab" data-theme="${key}"
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
  });
  _homeScroll = 0;
  if (location.hash.replace(/^#\/?/, '')) location.hash = '';
  renderHome();
}

function renderHome() {
  if (_activeTheme === 'all') {
    // One highlight per theme (its most relevant item); the strongest overall leads
    const top = Object.values(_byTheme).filter(l => l.length).map(l => l[0]).sort((a, b) => relOf(b) - relOf(a));
    const topIds = new Set(top.map(i => i.id));
    let html = top.length ? `<section class="highlights">${top.map((it, i) => card(it, i === 0 ? 'lead' : 'feature')).join('')}</section>` : '';
    for (const [key, t] of Object.entries(THEMES)) {
      const items = _byTheme[key].filter(i => !topIds.has(i.id));
      if (!items.length) continue;
      html += `
        <section class="theme-section" style="--c:${t.color}">
          <h2 class="section-title"><span>${t.label}</span></h2>
          <div class="card-list">${items.slice(0, HOME_PER_THEME).map(i => card(i)).join('')}</div>
          ${items.length > HOME_PER_THEME
            ? `<button class="btn-more" data-theme="${key}">Ver todas as ${_byTheme[key].length} de ${t.label} →</button>` : ''}
        </section>`;
    }
    els.home.innerHTML = html || empty();
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
}

function empty() {
  return '<p class="empty">Nenhuma notícia neste tema hoje.</p>';
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
        ${last ? '<span class="read-tag">Última aberta</span>' : read ? '<span class="read-tag">✓ Lida</span>' : ''}
        ${relOf(item) >= 4 ? '<span class="badge">Importante</span>' : ''}
      </span>
    </button>`;
}

// ── Detail ──────────────────────────────────────────────────────

function renderDetail(id) {
  const item = _byId[id];
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

    <section class="detail-section ai">
      <h3>Resumo por IA</h3>
      ${summary
        ? `<p>${escHtml(summary)}</p>`
        : '<p class="muted">Resumo indisponível para esta matéria (a IA não processou esta edição).</p>'}
    </section>

    ${comments ? `
      <section class="detail-section">
        <h3>O que a comunidade diz</h3>
        <p>${escHtml(comments)}</p>
        <p class="muted small">Sintetizado de comentários de usuários — opiniões, não fatos verificados.</p>
      </section>` : ''}

    <a class="btn-primary" href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer">Ler matéria original ↗</a>
  `;
  showOnly(els.detail);
  window.scrollTo(0, 0);
}

// ── Archive ─────────────────────────────────────────────────────

async function renderArchive() {
  showOnly(els.archive);
  els.archiveList.innerHTML = '<p class="empty">Carregando…</p>';
  try {
    const index = await loadJSON('archive/index.json');
    if (!index.dates?.length) throw new Error('empty');
    els.archiveList.innerHTML = '';
    [...index.dates].reverse().forEach(({ date, total_items }) => {
      const btn = document.createElement('button');
      btn.className = 'archive-item';
      btn.innerHTML = `
        <span class="archive-date">${formatDate(date + 'T12:00:00', { dateStyle: 'full' })}</span>
        <span class="archive-count">${total_items} notícias</span>`;
      btn.addEventListener('click', () => { location.hash = ''; loadData(`archive/${date}.json`); });
      els.archiveList.appendChild(btn);
    });
  } catch {
    els.archiveList.innerHTML = '<p class="empty">Nenhuma edição anterior ainda.</p>';
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
