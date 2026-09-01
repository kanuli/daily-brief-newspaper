(() => {
  'use strict';

  const DATA_URL = 'data/retail-deals.json';
  const WATCH_KEY = 'dailyBriefRetailWatchlistV1';
  let state = { data: null, watch: new Set(), search: '', retailer: '', type: 'all', sort: 'latest', watchOnly: false };

  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const money = (value, currency = 'HKD') => Number.isFinite(Number(value)) ? `${currency === 'HKD' ? '$' : esc(currency) + ' '}${Number(value).toFixed(Number(value) % 1 ? 2 : 0)}` : '—';
  const pct = (value) => Number.isFinite(Number(value)) ? `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}%` : '—';
  const when = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return esc(value);
    return new Intl.DateTimeFormat('zh-HK', { timeZone: 'Asia/Hong_Kong', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }).format(d) + ' HKT';
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
    saveWatch(); render();
  }

  function advertisedDiscount(item) {
    const current = Number(item.currentPrice);
    const regular = Number(item.regularPrice);
    if (!(current >= 0) || !(regular > 0) || current >= regular) return null;
    return ((regular - current) / regular) * 100;
  }

  function sourceClass(type) {
    const t = String(type || '').toLowerCase();
    if (t.includes('official')) return 'official';
    if (t.includes('social')) return 'social';
    return 'secondary';
  }
  function sourceLabel(type) {
    const t = String(type || '').toLowerCase();
    if (t === 'official' || t.startsWith('official-')) return 'OFFICIAL';
    if (t.includes('social')) return 'SOCIAL REFERENCE';
    if (t.includes('secondary')) return 'SECONDARY';
    return 'SOURCE';
  }

  function sparkline(history) {
    const rows = (Array.isArray(history) ? history : []).filter((x) => Number.isFinite(Number(x.price))).slice(-20);
    if (rows.length < 2) return '';
    const vals = rows.map((x) => Number(x.price));
    const min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
    const points = vals.map((v, i) => `${(i / (vals.length - 1) * 118).toFixed(1)},${(31 - ((v - min) / range) * 27).toFixed(1)}`).join(' ');
    return `<svg class="spark" viewBox="0 0 120 34" role="img" aria-label="近期價格走勢"><polyline points="${points}"></polyline></svg>`;
  }

  function productMatches(p) {
    const q = state.search.trim().toLowerCase();
    if (state.retailer && p.retailer !== state.retailer) return false;
    if (state.watchOnly && !state.watch.has(String(p.id))) return false;
    if (!q) return true;
    return [p.retailer, p.name, p.size, p.promoLabel].some((v) => String(v || '').toLowerCase().includes(q));
  }
  function promoMatches(p) {
    const q = state.search.trim().toLowerCase();
    if (state.retailer && p.retailer !== state.retailer) return false;
    if (state.watchOnly && !state.watch.has(String(p.id))) return false;
    if (!q) return true;
    return [p.retailer, p.title, p.summary, p.restriction, p.sourceName].some((v) => String(v || '').toLowerCase().includes(q));
  }

  function sortProducts(rows) {
    const out = [...rows];
    if (state.sort === 'price-low') out.sort((a,b) => Number(a.currentPrice ?? Infinity) - Number(b.currentPrice ?? Infinity));
    else if (state.sort === 'discount') out.sort((a,b) => (advertisedDiscount(b) ?? -1) - (advertisedDiscount(a) ?? -1));
    else out.sort((a,b) => String(b.observedAt || '').localeCompare(String(a.observedAt || '')));
    return out;
  }

  function renderSummary(data) {
    const products = Array.isArray(data.products) ? data.products : [];
    const promos = Array.isArray(data.promotions) ? data.promotions : [];
    const sources = Array.isArray(data.sources) ? data.sources : [];
    const active = promos.filter((p) => p.active !== false).length;
    const drops = products.filter((p) => Number(p.changePct) < 0).length;
    const ok = sources.filter((s) => s.status === 'ok').length;
    $('retail-summary').innerHTML = `
      <div class="retail-stat"><strong>${products.length}</strong><span>價格項目</span></div>
      <div class="retail-stat"><strong>${active}</strong><span>有效優惠</span></div>
      <div class="retail-stat"><strong>${drops}</strong><span>實測減價</span></div>
      <div class="retail-stat"><strong>${ok}/${sources.length}</strong><span>來源正常</span></div>`;
  }

  function renderProducts(data) {
    const show = state.type !== 'promotions';
    $('prices-section').hidden = !show;
    if (!show) return;
    const rows = sortProducts((data.products || []).filter(productMatches));
    $('price-count').textContent = `${rows.length} ITEMS · PRICE HISTORY`;
    if (!rows.length) { $('price-list').innerHTML = '<p class="empty-retail">沒有符合目前篩選條件的價格項目。</p>'; return; }
    $('price-list').innerHTML = rows.map((p) => {
      const ad = advertisedDiscount(p);
      const change = Number.isFinite(Number(p.changePct)) ? Number(p.changePct) : null;
      const changeClass = change == null ? 'change-flat' : change < 0 ? 'change-down' : change > 0 ? 'change-up' : 'change-flat';
      const changeText = change == null ? '實測變動：累積觀察中' : `實測變動：${change < 0 ? '↓ ' : change > 0 ? '↑ ' : ''}${pct(change)}`;
      const hist = Array.isArray(p.priceHistory) ? p.priceHistory.filter((x) => Number.isFinite(Number(x.price))) : [];
      const vals = hist.map((x) => Number(x.price));
      const low = Number.isFinite(Number(p.historicalLow)) ? Number(p.historicalLow) : (vals.length ? Math.min(...vals) : null);
      const high = Number.isFinite(Number(p.historicalHigh)) ? Number(p.historicalHigh) : (vals.length ? Math.max(...vals) : null);
      return `<article class="price-row">
        <div class="price-main"><div class="price-shop">${esc(p.retailer)}</div><h3>${esc(p.name)}</h3><div class="price-size">${esc(p.size || '')}</div>${p.promoLabel ? `<span class="price-badge">${esc(p.promoLabel)}</span>` : ''}</div>
        <div class="price-value"><strong>${money(p.currentPrice, p.currency)}</strong>${Number.isFinite(Number(p.regularPrice)) ? `<div class="price-reference">參考／原價 ${money(p.regularPrice, p.currency)}</div>` : ''}${ad != null ? `<span class="change-badge change-down">廣告優惠 −${ad.toFixed(1)}%</span>` : ''}</div>
        <div><div class="${changeClass}">${changeText}</div><div class="price-history">上次實測：${Number.isFinite(Number(p.previousObservedPrice)) ? money(p.previousObservedPrice, p.currency) : '尚未有第二筆'}</div></div>
        <div class="price-history">觀察範圍：${low != null ? money(low,p.currency) : '—'} – ${high != null ? money(high,p.currency) : '—'}${sparkline(hist)}</div>
        <div class="price-actions"><button class="watch-button" data-watch="${esc(p.id)}" aria-pressed="${state.watch.has(String(p.id))}">${state.watch.has(String(p.id)) ? '⭐' : '☆'}</button><br>檢查：${when(p.observedAt)}<br>${p.sourceUrl ? `<a class="source-link-retail" href="${esc(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">查看來源 ↗</a>` : ''}</div>
      </article>`;
    }).join('');
  }

  function renderPromotions(data) {
    const show = state.type !== 'prices';
    $('promotions-section').hidden = !show;
    if (!show) return;
    let rows = (data.promotions || []).filter(promoMatches);
    rows = [...rows].sort((a,b) => {
      if ((a.active !== false) !== (b.active !== false)) return a.active === false ? 1 : -1;
      return String(b.discoveredAt || b.publishedAt || '').localeCompare(String(a.discoveredAt || a.publishedAt || ''));
    });
    $('promo-count').textContent = `${rows.length} PROMOTIONS`;
    if (!rows.length) { $('promotion-list').innerHTML = '<p class="empty-retail">沒有符合目前篩選條件的優惠。</p>'; return; }
    $('promotion-list').innerHTML = rows.map((p) => `<article class="promo-card ${p.active === false ? 'expired' : ''}">
      <div class="promo-top"><div class="promo-retailer">${esc(p.retailer)}</div><button class="watch-button" data-watch="${esc(p.id)}" aria-pressed="${state.watch.has(String(p.id))}">${state.watch.has(String(p.id)) ? '⭐' : '☆'}</button></div>
      <div><span class="source-badge ${sourceClass(p.sourceType)}">${sourceLabel(p.sourceType)}</span>${p.active === false ? ' <span class="source-badge">已完結</span>' : ' <span class="source-badge official">有效／最新</span>'}</div>
      <h3>${esc(p.title)}</h3><p>${esc(p.summary || '')}</p>
      <div class="promo-validity">日期：${dateOnly(p.startDate)} – ${dateOnly(p.endDate)}</div>
      ${p.restriction ? `<div class="promo-restriction">條件：${esc(p.restriction)}</div>` : ''}
      <div class="promo-source">${esc(p.sourceName || '')}${p.sourceUrl ? `<br><a class="source-link-retail" href="${esc(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">原始／引用來源 ↗</a>` : ''}</div>
    </article>`).join('');
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
    const retailers = [...new Set([...(data.products || []).map((x) => x.retailer), ...(data.promotions || []).map((x) => x.retailer)].filter(Boolean))].sort((a,b) => a.localeCompare(b,'zh-Hant'));
    select.innerHTML = '<option value="">全部商店</option>' + retailers.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
    select.value = retailers.includes(existing) ? existing : '';
  }

  function render() {
    const data = state.data;
    if (!data) return;
    renderSummary(data); renderProducts(data); renderPromotions(data); renderSources(data);
    document.querySelectorAll('[data-watch]').forEach((btn) => btn.addEventListener('click', () => toggleWatch(btn.dataset.watch)));
  }

  function bind() {
    $('retail-search').addEventListener('input', (e) => { state.search = e.target.value; render(); });
    $('retailer-filter').addEventListener('change', (e) => { state.retailer = e.target.value; render(); });
    $('type-filter').addEventListener('change', (e) => { state.type = e.target.value; render(); });
    $('sort-filter').addEventListener('change', (e) => { state.sort = e.target.value; render(); });
    $('watch-only').addEventListener('change', (e) => { state.watchOnly = e.target.checked; render(); });
  }

  async function init() {
    loadWatch(); bind();
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data || !Array.isArray(data.products) || !Array.isArray(data.promotions)) throw new Error('invalid retail schema');
      state.data = data;
      $('retail-generated').textContent = `資料時間：${when(data.generatedAt)}`;
      $('retail-checked').textContent = `UPDATED ${when(data.generatedAt)}`;
      populateRetailers(data); render();
    } catch (err) {
      const message = `格價資料暫時無法載入：${esc(err.message || err)}`;
      $('retail-generated').textContent = '資料暫時未能載入';
      $('price-list').innerHTML = `<p class="notice">${message}</p>`;
      $('promotion-list').innerHTML = `<p class="notice">${message}</p>`;
      $('source-health').innerHTML = '<p class="notice">請稍後重新整理頁面；新聞版面不受影響。</p>';
    }
  }

  init();
})();
