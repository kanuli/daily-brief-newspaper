(() => {
  'use strict';

  const DATA_URL = 'data/retail-deals.json';
  const WATCH_KEY = 'dailyBriefRetailPromotionWatchlistV3';
  let state = { data: null, watch: new Set(), search: '', retailer: '', sort: 'latest', watchOnly: false };

  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const when = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return esc(value);
    return new Intl.DateTimeFormat('zh-HK', { timeZone:'Asia/Hong_Kong', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }).format(d) + ' HKT';
  };
  const dateOnly = (value) => {
    if (!value) return '未註明';
    const d = new Date(`${value}T00:00:00+08:00`);
    if (Number.isNaN(d.getTime())) return esc(value);
    return new Intl.DateTimeFormat('zh-HK', { timeZone:'Asia/Hong_Kong', year:'numeric', month:'2-digit', day:'2-digit' }).format(d);
  };

  function loadWatch() {
    try {
      const raw = JSON.parse(localStorage.getItem(WATCH_KEY) || '[]');
      state.watch = new Set(Array.isArray(raw) ? raw.map(String) : []);
    } catch (_) { state.watch = new Set(); }
  }
  function saveWatch() { localStorage.setItem(WATCH_KEY, JSON.stringify([...state.watch])); }
  function toggleWatch(id) {
    id = String(id);
    if (state.watch.has(id)) state.watch.delete(id); else state.watch.add(id);
    saveWatch();
    render();
  }

  function sourceClass(type) {
    const t = String(type || '').toLowerCase();
    if (t.includes('official')) return 'official';
    if (t.includes('social') || t.includes('facebook')) return 'social';
    return 'secondary';
  }
  function sourceLabel(type) {
    const t = String(type || '').toLowerCase();
    if (t.includes('official')) return 'OFFICIAL';
    if (t.includes('facebook')) return 'FACEBOOK';
    if (t.includes('social')) return 'SOCIAL';
    if (t.includes('secondary')) return 'SECONDARY';
    return 'SOURCE';
  }

  function promotions(data) {
    return (Array.isArray(data.promotions) ? data.promotions : [])
      .filter((p) => p && p.id && p.retailer && p.title && p.active !== false)
      .map((p) => ({ ...p, id: String(p.id), timestamp: p.publishedAt || p.discoveredAt || p.checkedAt || data.generatedAt }));
  }

  function cardMatches(p) {
    const q = state.search.trim().toLowerCase();
    if (state.retailer && p.retailer !== state.retailer) return false;
    if (state.watchOnly && !state.watch.has(String(p.id))) return false;
    if (!q) return true;
    return [p.retailer, p.title, p.summary, p.restriction, p.sourceName].some((v) => String(v || '').toLowerCase().includes(q));
  }

  function sortCards(rows) {
    const out = [...rows];
    if (state.sort === 'ending') {
      out.sort((a,b) => {
        const aa = a.endDate || '9999-12-31';
        const bb = b.endDate || '9999-12-31';
        return aa.localeCompare(bb) || String(b.timestamp || '').localeCompare(String(a.timestamp || ''));
      });
    } else {
      out.sort((a,b) => String(b.timestamp || '').localeCompare(String(a.timestamp || '')));
    }
    return out;
  }

  function renderSummary(data) {
    const rows = promotions(data);
    const retailers = new Set(rows.map((x) => x.retailer).filter(Boolean));
    const sources = Array.isArray(data.sources) ? data.sources : [];
    const ok = sources.filter((s) => s.status === 'ok').length;
    $('retail-summary').innerHTML = `
      <div class="retail-stat"><strong>${rows.length}</strong><span>最新推廣</span></div>
      <div class="retail-stat"><strong>${retailers.size}</strong><span>涵蓋商店</span></div>
      <div class="retail-stat"><strong>${ok}/${sources.length}</strong><span>來源正常</span></div>
      <div class="retail-stat"><strong>2小時</strong><span>更新頻率</span></div>`;
  }

  function renderPromotions(data) {
    const rows = sortCards(promotions(data).filter(cardMatches));
    $('promo-count').textContent = `${rows.length} PROMOTIONS`;
    if (!rows.length) {
      $('promotion-list').innerHTML = '<p class="empty-retail">目前沒有符合篩選條件的最新推廣。</p>';
      return;
    }
    $('promotion-list').innerHTML = rows.map((p) => {
      const hasDates = p.startDate || p.endDate;
      return `<article class="promo-card">
        <div class="promo-top"><div class="promo-retailer">${esc(p.retailer)}</div><button class="watch-button" data-watch="${esc(p.id)}" aria-pressed="${state.watch.has(String(p.id))}">${state.watch.has(String(p.id)) ? '⭐' : '☆'}</button></div>
        <div><span class="source-badge ${sourceClass(p.sourceType)}">${sourceLabel(p.sourceType)}</span> <span class="source-badge official">PROMOTION</span></div>
        <h3>${esc(p.title)}</h3>
        ${p.summary ? `<p>${esc(p.summary)}</p>` : ''}
        ${hasDates ? `<div class="promo-validity">活動日期：${dateOnly(p.startDate)} – ${dateOnly(p.endDate)}</div>` : `<div class="promo-validity">發布／發現：${when(p.timestamp)}</div>`}
        ${p.restriction ? `<div class="promo-restriction">條件／備註：${esc(p.restriction)}</div>` : ''}
        <div class="promo-source">${esc(p.sourceName || '')}${p.sourceUrl ? `<br><a class="source-link-retail" href="${esc(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">查看推廣來源 ↗</a>` : ''}</div>
      </article>`;
    }).join('');
  }

  function renderSources(data) {
    const rows = Array.isArray(data.sources) ? data.sources : [];
    if (!rows.length) { $('source-health').innerHTML = '<p class="empty-retail">未有來源健康資料。</p>'; return; }
    $('source-health').innerHTML = rows.map((s) => `<article class="source-health-card status-${esc(s.status || 'limited')}">
      <div class="status-line"><span class="status-dot"></span>${esc((s.status || 'limited').toUpperCase())} · ${esc(s.retailer)}</div>
      <h3>${esc(s.label)}</h3><p>${esc(s.detail || '')}</p><p>最後檢查：${when(s.checkedAt)}</p>
      ${s.url ? `<a class="source-link-retail" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">來源 ↗</a>` : ''}
    </article>`).join('');
  }

  function populateRetailers(data) {
    const select = $('retailer-filter');
    const existing = select.value;
    const retailers = [...new Set(promotions(data).map((x) => x.retailer).filter(Boolean))].sort((a,b) => a.localeCompare(b,'zh-Hant'));
    select.innerHTML = '<option value="">全部商店</option>' + retailers.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
    select.value = retailers.includes(existing) ? existing : '';
  }

  function render() {
    const data = state.data;
    if (!data) return;
    renderSummary(data);
    renderPromotions(data);
    renderSources(data);
    document.querySelectorAll('[data-watch]').forEach((btn) => btn.addEventListener('click', () => toggleWatch(btn.dataset.watch)));
  }

  function bind() {
    $('retail-search').addEventListener('input', (e) => { state.search = e.target.value; render(); });
    $('retailer-filter').addEventListener('change', (e) => { state.retailer = e.target.value; render(); });
    $('sort-filter').addEventListener('change', (e) => { state.sort = e.target.value; render(); });
    $('watch-only').addEventListener('change', (e) => { state.watchOnly = e.target.checked; render(); });
  }

  async function init() {
    loadWatch();
    bind();
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data || data.schemaVersion !== 3 || !Array.isArray(data.promotions) || !Array.isArray(data.sources)) throw new Error('invalid promotion-only schema');
      state.data = data;
      $('retail-generated').textContent = '資料範圍：推廣活動（PROMOTION ONLY）';
      $('retail-checked').textContent = `最後資料更新：${when(data.generatedAt)}`;
      populateRetailers(data);
      render();
    } catch (err) {
      const message = `最新推廣資料暫時無法載入：${esc(err.message || err)}`;
      $('retail-generated').textContent = '資料範圍：推廣活動（PROMOTION ONLY）';
      $('retail-checked').textContent = '最後資料更新：暫時未能讀取';
      $('promotion-list').innerHTML = `<p class="notice">${message}</p>`;
      $('source-health').innerHTML = '<p class="notice">請稍後重新整理頁面；其他新聞版面不受影響。</p>';
    }
  }

  init();
})();