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
      <div class="stock-story-body">${body.map(p=>`<p>${esc(p)}</p>`).join('')}</div>
      <div class="stock-info-grid">
        <div class="stock-info-card"><strong>為何重要</strong><p>${esc(story.why||'')}</p></div>
        <div class="stock-info-card"><strong>下一步</strong><p>${esc(story.watchNext||'')}</p></div>
      </div>
      <div class="stock-story-meta">${esc(story.timeLabel||'')} ${story.sourceName?`· ${esc(story.sourceName)}`:''}</div>
      ${sourceMarkup(story)}
    </article>`;
  }

  function render(data){
    const host = document.querySelector('#stock-sections');
    if(!host) return;
    const nav = document.querySelector('#stock-ticker-nav');
    if(nav) nav.innerHTML = ORDER.map(t=>`<a href="#stock-${t.toLowerCase()}">${t}</a>`).join('');
    const updated = document.querySelector('#stock-updated');
    if(updated) updated.textContent = data.lastUpdatedLabel || data.generatedAt || '';
    const tickers = data.tickers || {};
    host.innerHTML = ORDER.map(ticker=>{
      const block = tickers[ticker] || {};
      const stories = Array.isArray(block.stories)?block.stories:[];
      return `<section class="stock-section" id="stock-${ticker.toLowerCase()}">
        <div class="stock-section-head"><div><div class="stock-symbol">${ticker}</div><div class="stock-name">${esc(block.name||'')}</div></div><div class="stock-asset-type">${esc(block.assetType||'SECURITY')}</div></div>
        ${stories.length?stories.map(renderStory).join(''):`<div class="stock-empty">暫未有已核實的新稿；本節會保留最近有效新聞並在下一輪更新。</div>`}
      </section>`;
    }).join('');
  }

  async function init(){
    try{
      const res = await fetch('data/stocks-latest.json',{cache:'no-store'});
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