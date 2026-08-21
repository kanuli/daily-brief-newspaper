(() => {
  "use strict";
  const esc = (v='') => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  if (!document.getElementById('topic-longform-style')) {
    const style = document.createElement('style');
    style.id = 'topic-longform-style';
    style.textContent = `.topic-article-body{margin:16px 0 14px;padding-top:12px;border-top:1px solid #8b8478;font-family:"Noto Serif TC","PMingLiU",serif;font-size:15px;line-height:1.78}.topic-article-body p{margin:0 0 1em;break-inside:avoid}.topic-body-main p:first-child:first-letter{float:left;font-size:3.1em;line-height:.8;padding:.08em .08em 0 0;font-weight:900}.topic-story.topic-feature .topic-body-main{column-count:2;column-gap:30px;column-rule:1px solid #c5beb3}.topic-story.has-longform .topic-dek{font-size:18px!important}.topic-analysis-box{margin-top:12px;padding-top:10px;border-top:1px dotted #777}.topic-analysis-box p{font-family:"Noto Sans TC",sans-serif;font-size:13px;line-height:1.65}.football-catchup{display:contents}@media(max-width:720px){.topic-story.topic-feature .topic-body-main{column-count:1}.topic-article-body{font-size:15px;line-height:1.72}}`;
    document.head.appendChild(style);
  }
  function paragraphs(value) {
    if (Array.isArray(value)) return value.map(String).map(s=>s.trim()).filter(Boolean);
    if (!value) return [];
    return String(value).split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean);
  }
  async function loadStoryMap() {
    const map = new Map();
    const latest = await fetch('data/latest.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
    (latest?.articles || []).forEach(story => { if (story?.title) map.set(story.title.trim(), story); });
    if (latest?.date) {
      const more = await fetch(`data/topic-more/${latest.date}.json`,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
      (more?.articles || []).forEach(story => { if (story?.title) map.set(story.title.trim(), {...(map.get(story.title.trim())||{}),...story}); });
    }
    for (const path of ['data/desk-latest.json','data/live.json']) {
      try {
        const data = await fetch(path,{cache:'no-store'}).then(r=>r.ok?r.json():null);
        if (!data) continue;
        const stories = data.desks ? Object.values(data.desks).flat() : (data.items || []);
        stories.forEach(story => { if (story?.title) map.set(story.title.trim(), {...(map.get(story.title.trim())||{}),...story}); });
      } catch (_) {}
    }
    return map;
  }
  function normalizeDeskLabels() {
    const slugs = String(document.body.dataset.topicSlugs || '').split(',').map(s=>s.trim());
    const subtitle = document.querySelector('#topic-sections .section-heading span');
    if (!subtitle) return;
    if (slugs.includes('asia')) subtitle.textContent = '東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · 全亞洲';
    if (slugs.includes('world')) subtitle.textContent = '歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）';
    if (slugs.includes('football')) subtitle.textContent = 'England · La Liga · Serie A · Bundesliga · Ligue 1 · Europe · UEFA · International · J-League · Hong Kong · Worldwide';
  }
  function enforceGeography() {
    const slugs = String(document.body.dataset.topicSlugs || '').split(',').map(s=>s.trim());
    if (!slugs.includes('world')) return;
    document.querySelectorAll('.topic-story').forEach(card => {
      const tag = card.querySelector('.tag')?.textContent || '';
      if (/中東|West Asia|Middle East|伊朗|以色列|海灣|Gulf/i.test(tag)) card.remove();
    });
  }
  function infoBlock(story) {
    const rows = [];
    if (story?.context) rows.push(`<p><strong>背景：</strong>${esc(story.context)}</p>`);
    if (story?.why) rows.push(`<p><strong>為何重要：</strong>${esc(story.why)}</p>`);
    if (story?.watchNext) rows.push(`<p><strong>下一步：</strong>${esc(story.watchNext)}</p>`);
    return rows.length ? `<div class="topic-analysis-box">${rows.join('')}</div>` : '';
  }
  async function apply() {
    if (document.body.dataset.page !== 'topic') return;
    normalizeDeskLabels();
    enforceGeography();
    const map = await loadStoryMap();
    document.querySelectorAll('.topic-story').forEach(card => {
      const title = card.querySelector('h2')?.textContent?.trim();
      const story = title ? map.get(title) : null;
      const paras = paragraphs(story?.body);
      if (!paras.length) return;
      let host = card.querySelector('.topic-article-body');
      if (!host) {
        host = document.createElement('div');
        host.className = 'topic-article-body';
        const info = card.querySelector('.story-meta') || card.querySelector('.source-cluster');
        if (info) card.insertBefore(host, info); else card.appendChild(host);
      }
      const summary = story?.summary ? `<p class="topic-summary"><strong>摘要：</strong>${esc(story.summary)}</p>` : '';
      host.innerHTML = `${summary}<div class="topic-body-main">${paras.map(p=>`<p>${esc(p)}</p>`).join('')}</div>${infoBlock(story)}`;
      card.classList.add('has-longform');
    });
  }
  [350,1000,2200].forEach(delay => setTimeout(apply,delay));
})();
