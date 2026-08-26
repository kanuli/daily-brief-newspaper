(() => {
  "use strict";
  const ORDER = ["NVDA","AAPL","TSM","PLTR","MSFT","GOOG","EMXC","EWY","VT"];
  const esc = (v='') => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const paragraphs = (value='') => String(value || '').split(/\n\s*\n/).map(v=>v.trim()).filter(Boolean);
  const impactClass = (impact='↔') => impact === '↑' ? 'stock-impact-up' : impact === '↓' ? 'stock-impact-down' : 'stock-impact-neutral';

  function sourceMarkup(story){
    const sources = Array.isArray(story.sources) && story.sources.length ? story.sources : (story.sourceUrl ? [{name:story.sourceName||'原文',url:story.sourceUrl}] : []);
    if(!sources.length) return '';
    return `<div class="stock-sources"><strong>核實來源：</strong> ${sources.map(s=>`<a href="${esc(s.url||'#')}" target="_blank" rel="noopener noreferrer">${esc(s.name||'原文')} ↗</a>`).join(' · ')}</div>`;
  }

  function renderStory(story,index){
    const body = paragraphs(story.body);
    return `<article class="stock-story ${index===0?'featured':''}">
      <div class="tag"><span class="stock-impact ${impactClass(story.impact)}">${esc(story.impact||'↔')} ${esc(story.impactLabel||'READ-THROUGH')}</span>${esc(story.storyType||'LATEST')}</div>
      <h2>${esc(story.title||'')}</h2>
      ${story.dek?`<p class="stock-story-dek">${esc(story.dek)}</p>`:''}
      ${story.summary?`<p class="stock-summary"><strong>摘要：</strong>${esc(story.summary)}</p>`:''}
      <div class="stock-story-body">${body.map(p=>`<p>${esc(p)}</p>`).join('')}</div>
      <div class="stock-info-grid stock-info-grid-three">
        <div class="stock-info-card"><strong>背景</strong><p>${esc(story.context||'')}</p></div>
        <div class="stock-info-card"><strong>為何重要</strong><p>${esc(story.why||'')}</p></div>
        <div class="stock-info-card"><strong>下一步</strong><p>${esc(story.watchNext||'')}</p></div>
      </div>
      <div class="stock-story-meta">${esc(story.timeLabel||'')} ${story.sourceName?`· ${esc(story.sourceName)}`:''}</div>
      ${sourceMarkup(story)}
    </article>`;
  }

  function hoursSince(value){
    if(!value) return null;
    const ts = Date.parse(value);
    if(!Number.isFinite(ts)) return null;
    return Math.max(0, (Date.now() - ts) / 3600000);
  }

  function renderFreshness(data){
    const checked = document.querySelector('#stock-checked');
    const updated = document.querySelector('#stock-updated');
    const host = document.querySelector('#stock-freshness');
    if(checked) checked.textContent = data.lastCheckedLabel || data.lastCheckedAt || '尚未建立獨立檢查時間';
    if(updated) updated.textContent = data.lastUpdatedLabel || data.generatedAt || 'N/V';
    if(!host) return;

    const status = String(data.collectionStatus || '').toUpperCase();
    const contentAge = hoursSince(data.generatedAt);
    const discovered = Number(data.discoveredThisCheck || 0);
    const reservoir = Number(data.discoveryCandidateCount || 0);

    if(status === 'COLLECTION_FAILURE'){
      host.innerHTML = `<p class="notice"><strong>⚠️ Stock News 搜集失敗：</strong>最近一次檢查沒有取得 fresh candidate。這會被視為 collection failure，而不是「市場沒有新聞」。現有稿件仍保留為最近已核實內容。</p>`;
      return;
    }
    if(status === 'INCOMPLETE'){
      host.innerHTML = `<p class="notice"><strong>⚠️ Stock News 搜集未達完整度：</strong>本輪找到 ${discovered} 則 fresh discovery candidate，但未達 Stock Desk 的 breadth floor。系統會保留最近已核實稿件；這一輪不會標記為完整搜集。</p>`;
      return;
    }

    if(data.lastCheckedAt){
      const depth = Number.isFinite(reservoir) && reservoir > 0 ? `；rolling candidate reservoir ${reservoir} 則` : '';
      const fresh = discovered > 0 ? `本輪找到 ${discovered} 則 fresh discovery candidate${depth}` : `本輪已完成搜集${depth}`;
      const oldCopy = contentAge !== null && contentAge > 24
        ? ' 現有已核實稿件的內容時間較舊，表示最近檢查未有新的材料通過核實／編輯門檻；舊稿不會被重新標示成新新聞。'
        : ' 如「最後檢查」較「最近已核實內容更新」新，代表該輪已檢查但沒有需要改寫的已核實新稿。';
      host.innerHTML = `<p class="notice"><strong>Newsroom freshness：</strong>${esc(fresh)}。${esc(oldCopy)}</p>`;
      return;
    }

    host.innerHTML = `<p class="notice"><strong>Newsroom freshness：</strong>目前只保存「最近已核實內容更新」時間；獨立 hourly check timestamp 會由新的 Stock News maintenance 建立。</p>`;
  }

  function render(data){
    const host = document.querySelector('#stock-sections');
    if(!host) return;
    const nav = document.querySelector('#stock-ticker-nav');
    if(nav) nav.innerHTML = ORDER.map(t=>`<a href="#stock-${t.toLowerCase()}">${t}</a>`).join('');
    renderFreshness(data);
    const tickers = data.tickers || {};
    host.innerHTML = ORDER.map(ticker=>{
      const block = tickers[ticker] || {};
      const stories = Array.isArray(block.stories)?block.stories:[];
      return `<section class="stock-section" id="stock-${ticker.toLowerCase()}">
        <div class="stock-section-head"><div><div class="stock-symbol">${ticker}</div><div class="stock-name">${esc(block.name||'')}</div></div><div class="stock-asset-type">${esc(block.assetType||'SECURITY')}</div></div>
        ${stories.length?stories.map(renderStory).join(''):`<div class="stock-empty">暫未有已核實的新稿；本節會保留最近有效新聞並在下一輪繼續檢查。</div>`}
      </section>`;
    }).join('');
  }

  async function init(){
    try{
      const url = new URL('data/stocks-latest.json', document.baseURI);
      url.searchParams.set('v', String(Date.now()));
      const res = await fetch(url.href,{cache:'no-store'});
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      render(await res.json());
    }catch(err){
      console.error(err);
      const host=document.querySelector('#stock-sections');
      if(host) host.innerHTML='<p class="notice">Stock News 暫時未能載入。</p>';
    }
  }
  init();
})();