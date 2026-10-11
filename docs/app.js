/* ================================================================
   DailyBrief – app.js
   SPA leve com roteamento por hash, carregamento de data.json,
   suporte a arquivo e integração com Service Worker / PWA.
   ================================================================ */

'use strict';

// ── Mapeamento de temas (chave → rótulo PT-BR + emoji) ─────────
const THEME_LABELS = {
  politica_nacional:       { label: 'Política Nacional',       icon: '🇧🇷' },
  politica_internacional:  { label: 'Política Internacional',  icon: '🌍' },
  tecnologia:              { label: 'Tecnologia',               icon: '💻' },
  ia:                      { label: 'Inteligência Artificial',  icon: '🤖' },
  games:                   { label: 'Games',                    icon: '🎮' },
  animes:                  { label: 'Animes',                   icon: '🎌' },
  ciencia:                 { label: 'Ciência',                  icon: '🔬' },
  economia:                { label: 'Economia',                 icon: '📈' },
  outros:                  { label: 'Outros',                   icon: '🌐' },
};

// ── Estado global ───────────────────────────────────────────────
let _data = null;       // data.json carregado
let _allItems = {};     // mapa id → item
let _activeTheme = null;

// ── Elementos DOM ───────────────────────────────────────────────
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

// ── Utilitários ─────────────────────────────────────────────────

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function showOnly(...toShow) {
  [els.loading, els.error, els.home, els.detail, els.archive].forEach(hide);
  toShow.forEach(show);
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat('pt-BR', {
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

// ── Carregamento de dados ───────────────────────────────────────

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
    els.errorMsg.textContent = 'Não foi possível carregar as notícias. Verifique sua conexão.';
    showOnly(els.error);
  }
}

// ── Renderização da Home ────────────────────────────────────────

function renderHome() {
  const themes = _data.themes || {};
  const orderedKeys = Object.keys(THEME_LABELS).filter(k => themes[k]?.length);

  // Cabeçalho
  if (_data.generated_at) {
    els.generatedAt.textContent = `Atualizado em ${formatDate(_data.generated_at)}`;
  }

  // Abas
  els.tabs.innerHTML = '';
  const allTab = document.createElement('button');
  allTab.className = 'tab-btn active';
  allTab.textContent = '🗞️ Todos';
  allTab.dataset.theme = 'all';
  allTab.addEventListener('click', () => activateTab('all'));
  els.tabs.appendChild(allTab);

  orderedKeys.forEach(key => {
    const meta = THEME_LABELS[key];
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.textContent = `${meta.icon} ${meta.label}`;
    btn.dataset.theme = key;
    btn.addEventListener('click', () => activateTab(key));
    els.tabs.appendChild(btn);
  });

  // Seções
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
  btn.setAttribute('aria-label', `Abrir notícia: ${item.title}`);
  btn.innerHTML = `
    <p class="card-title">${escHtml(item.title)}</p>
    ${item.resumo_curto ? `<p class="card-summary">${escHtml(item.resumo_curto)}</p>` : ''}
    <div class="card-meta">
      <span class="tag-source">${escHtml(item.source)}</span>
      <div class="relevance-dots" aria-label="Relevância ${item.relevancia || 0} de 5">
        ${dots(item.relevancia || 0)}
      </div>
    </div>
  `;
  btn.addEventListener('click', () => {
    location.hash = `/item/${item.id}`;
  });
  return btn;
}

// ── Renderização de Detalhe ─────────────────────────────────────

function renderDetail(id) {
  const item = _allItems[id];
  if (!item) {
    location.hash = '';
    return;
  }

  let html = `
    <h2>${escHtml(item.title)}</h2>
    <div class="detail-meta">
      <span class="tag-source">${escHtml(item.source)}</span>
      ${item.published ? `<span style="font-size:.78rem;color:var(--text-muted)">${formatDate(item.published)}</span>` : ''}
      <div class="relevance-dots" aria-label="Relevância ${item.relevancia || 0} de 5">
        ${dots(item.relevancia || 0)}
      </div>
    </div>
  `;

  if (item.resumo_materia) {
    html += `
      <div class="detail-section">
        <h3>📝 Resumo da Matéria</h3>
        <p>${escHtml(item.resumo_materia)}</p>
      </div>
    `;
  } else if (item.resumo_curto) {
    html += `
      <div class="detail-section">
        <h3>📝 Resumo</h3>
        <p>${escHtml(item.resumo_curto)}</p>
      </div>
    `;
  }

  if (item.resumo_comentarios) {
    html += `
      <div class="detail-section">
        <h3>💬 O que a galera está falando</h3>
        <p>${escHtml(item.resumo_comentarios)}</p>
        <p class="comments-notice">⚠️ Estes são pontos de vista de usuários, não fatos verificados.</p>
      </div>
    `;
  }

  html += `<a class="btn-open" href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer">
    🔗 Abrir artigo original
  </a>`;

  els.detailContent.innerHTML = html;
  showOnly(els.detail);
  window.scrollTo(0, 0);
}

// ── Arquivo ─────────────────────────────────────────────────────

async function renderArchive() {
  showOnly(els.archive);
  els.archiveList.innerHTML = '<p style="color:var(--text-muted);padding:16px">Carregando…</p>';

  // Tenta listar arquivos via archive/index.json (gerado pelo pipeline)
  try {
    const index = await loadJSON('archive/index.json');
    if (!index.dates?.length) throw new Error('vazio');

    els.archiveList.innerHTML = '';
    [...index.dates].reverse().forEach(({ date, total_items }) => {
      const div = document.createElement('div');
      div.className = 'archive-item';
      div.innerHTML = `
        <span class="archive-date">${date}</span>
        <span class="archive-count">${total_items} notícias</span>
      `;
      div.addEventListener('click', () => loadData(`archive/${date}.json`));
      els.archiveList.appendChild(div);
    });
  } catch {
    els.archiveList.innerHTML = '<p style="color:var(--text-muted);padding:16px">Arquivo não disponível ainda.</p>';
  }
}

// ── Roteamento por hash ─────────────────────────────────────────

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

// ── PWA / Instalação ────────────────────────────────────────────

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

// Service Worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(console.error);
}

// ── Event listeners ─────────────────────────────────────────────

window.addEventListener('hashchange', route);
els.btnArchive.addEventListener('click', () => { location.hash = 'archive'; });

// ── Expõe para uso inline no HTML ──────────────────────────────
window.App = {
  loadData,
  goHome() { location.hash = ''; },
};

// ── Bootstrap ───────────────────────────────────────────────────
route();
