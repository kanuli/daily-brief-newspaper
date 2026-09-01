(() => {
  'use strict';

  const DATA_URL = 'data/retail-deals.json';
  const WATCH_KEY = 'dailyBriefRetailWatchlistV2';
  let state = { data: null, watch: new Set(), search: '', retailer: '', sort: 'latest', watchOnly: false };

  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const money = (value, currency = 'HKD') => Number.isFinite(Number(value)) ? `${currency === 'HKD' ? '$' : esc(currency) + ' '}${Number(value).toFixed(Number(value) % 1 ? 2 : 0)}` : '—';
  const when = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return esc(value);
    return new Intl.DateTimeFormat('zh-HK', { timeZone: 'Asia/Hong_Kong', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }).format(d) + ' HKT';
  };
  const timeOnly = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '—';
    return new Intl.DateTimeFormat('zh-HK', { timeZone:'Asia/Hong_Kong', hour:'2-digit', minute:'2-digit', hour12:false }).format(d);
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

  function advertisedDiscount(currentPrice, regularPrice) {
    const current = Number(currentPrice);
    const regular = Number(regularPrice);
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

  function offerCards(data) {
    const offers = Array.isArray(data.offers) ? data.offers : (Array.isArray(data.products) ? data.products : []);
    return offers.map((o) => {
      const discount = advertisedDiscount(o.currentPrice, o.regularPrice);
      const priceBits = [];
      if (Number.isFinite(Number(o.currentPrice))) priceBits.push(`優惠價 ${money(o.currentPrice, o.currency)}`);
      if (Number.isFinite(Number(o.regularPrice))) priceBits.push(`原價／參考價 ${money(o.regularPrice, o.currency)}`);
      if (discount != null) priceBits.push(`節省 ${discount.toFixed(1)}%`);
      return {
        id: String(o.id || ''),
        kind: 'offer',
        retailer: o.retailer,
        title: o.name,
        summary: [o.promoLabel, priceBits.join(' · ')].filter(Boolean).join('｜'),
        startDate: null,
        endDate: null,
        active: o.active !== false,
        restriction: o.restriction || '',
        sourceType: o.sourceType || 'official-products',
        sourceName: o.sourceName || `${o.retailer || '零售商'}官方`,
        sourceUrl: o.sourceUrl,
        timestamp: o.checkedAt || o.observedAt || data.generatedAt,
        discount,
        currentPrice: o.currentPrice,
        regularPrice: o.regularPrice,
        currency: o.currency || 'HKD'
      };
    });
  }

  function promotionCards(data) {
    return (Array.isArray(data.promotions) ? data.promotions : []).map((p) => ({
      ...p,
      id: String(p.id || ''),
      kind: 'promotion',
      timestamp: p.discoveredAt || p.publishedAt || data.generatedAt,
      discount: Number.isFinite(Number(p.discountPct)) ? Number(p.discountPct) : null
    }));
  }

  function allCards(data) {
    return [...offerCards(data), ...promotionCards(data)].filter((x) => x.id && x.retailer && x.title && x.active !== false);
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
    if (state.sort === 'discount') {
      out.sort((a,b) => (b.discount ?? -1) - (a.discount ?? -1) || String(b.timestamp || '').localeCompare(String(a.timestamp || '')));
    } else if (state.sort === 'ending') {
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
    const cards = allCards(data);
    const retailers = new Set(cards.map((x) => x.retailer).filter(Boolean));
    const sources = Array.isArray(data.sources) ? data.sources : [];
    const ok = sources.filter((s) => s.status === 'ok').length;
    $('retail-summary').innerHTML = `
      <div class="retail-stat"><strong>${cards.length}</strong><span>最新優惠</span></div>
      <div class="retail-stat"><strong>${retailers.size}</strong><span>涵蓋商店</span></div>
      <div class="retail-stat"><strong>${ok}/${sources.length}</strong><span>來源正常</span></div>
      <div class="retail-stat"><strong>${timeOnly(data.generatedAt)}</strong><span>最後更新 HKT</span></div>`;
  }

  function renderPromotions(data) {
    const rows = sortCards(allCards(data).filter(cardMatches));
    $('promo-count').textContent = `${rows.length} LATEST DEALS`;
    if (!rows.length) {
      $('promotion-list').innerHTML = '<p class="empty-retail">沒有符合目前篩選條件的最新優惠。</p>';
      return;
    }
    $('promotion-list').innerHTML = rows.map((p) => {
      const validity = p.kind === 'offer'
        ? `最後檢查：${when(p.timestamp)}`
        : `日期：${dateOnly(p.startDate)} – ${dateOnly(p.endDate)}`;
      const dealPrice = p.kind === 'offer' && Number.isFinite(Number(p.currentPrice))
        ? `<div class="deal-price"><strong>${money(p.currentPrice, p.currency)}</strong>${Number.isFinite(Number(p.regularPrice)) ? `<span>原價／參考價 ${money(p.regularPrice, p.currency)}</span>` : ''}${p.discount != null ? `<b>節省 ${p.discount.toFixed(1)}%</b>` : ''}</div>`
        : '';
      return `<article class="promo-card">
        <div class="promo-top"><div class="promo-retailer">${esc(p.retailer)}</div><button class="watch-button" data-watch="${esc(p.id)}" aria-pressed="${state.watch.has(String(p.id))}">${state.watch.has(String(p.id)) ? '⭐' : '☆'}</button></div>
        <div><span class="source-badge ${sourceClass(p.sourceType)}">${sourceLabel(p.sourceType)}</span> <span class="source-badge official">最新優惠</span></div>
        <h3>${esc(p.title)}</h3>
        ${dealPrice}
        ${p.summary ? `<p>${esc(p.summary)}</p>` : ''}
        <div class="promo-validity">${validity}</div>
        ${p.restriction ? `<div class="promo-restriction">條件：${esc(p.restriction)}</div>` : ''}
        <div class="promo-source">${esc(p.sourceName || '')}${p.sourceUrl ? `<br><a class="source-link-retail" href="${esc(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">原始／官方來源 ↗</a>` : ''}</div>
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
    const retailers = [...new Set(allCards(data).map((x) => x.retailer).filter(Boolean))].sort((a,b) => a.localeCompare(b,'zh-Hant'));
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
      if (!data || !Array.isArray(data.promotions) || (!Array.isArray(data.offers) && !Array.isArray(data.products))) throw new Error('invalid retail deals schema');
      state.data = data;
      $('retail-generated').textContent = `資料時間：${when(data.generatedAt)}`;
      $('retail-checked').textContent = `UPDATED ${when(data.generatedAt)}`;
      populateRetailers(data);
      render();
    } catch (err) {
      const message = `最新優惠資料暫時無法載入：${esc(err.message || err)}`;
      $('retail-generated').textContent = '資料暫時未能載入';
      $('promotion-list').innerHTML = `<p class="notice">${message}</p>`;
      $('source-health').innerHTML = '<p class="notice">請稍後重新整理頁面；新聞版面不受影響。</p>';
    }
  }

  init();
})();
