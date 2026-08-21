(() => {
  "use strict";
  const esc = (v='') => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  if (!document.getElementById('topic-longform-style')) {
    const style = document.createElement('style');
    style.id = 'topic-longform-style';
    style.textContent = `.topic-article-body{margin:16px 0 14px;padding-top:12px;border-top:1px solid #8b8478;font-family:"Noto Serif TC","PMingLiU",serif;font-size:15px;line-height:1.78}.topic-article-body p{margin:0 0 1em;break-inside:avoid}.topic-story.topic-feature .topic-article-body{column-count:2;column-gap:30px;column-rule:1px solid #c5beb3}.topic-story.has-longform .topic-dek{font-size:18px!important}.football-catchup{display:contents}@media(max-width:720px){.topic-story.topic-feature .topic-article-body{column-count:1}.topic-article-body{font-size:15px;line-height:1.72}}`;
    document.head.appendChild(style);
  }
  function paragraphs(value) {
    if (Array.isArray(value)) return value.map(String).map(s=>s.trim()).filter(Boolean);
    if (!value) return [];
    return String(value).split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean);
  }
  async function loadStoryMap() {
    const map = new Map();
    for (const path of ['data/desk-latest.json','data/live.json']) {
      try {
        const data = await fetch(path,{cache:'no-store'}).then(r=>r.ok?r.json():null);
        if (!data) continue;
        const stories = data.desks ? Object.values(data.desks).flat() : (data.items || []);
        stories.forEach(story => { if (story?.title) map.set(story.title.trim(), story); });
      } catch (_) {}
    }
    return map;
  }
  async function apply() {
    if (document.body.dataset.page !== 'topic') return;
    const map = await loadStoryMap();
    document.querySelectorAll('.topic-story').forEach(card => {
      if (card.querySelector('.topic-article-body')) return;
      const title = card.querySelector('h2')?.textContent?.trim();
      const story = title ? map.get(title) : null;
      const paras = paragraphs(story?.body);
      if (!paras.length) return;
      const body = document.createElement('div');
      body.className = 'topic-article-body';
      body.innerHTML = paras.map(p=>`<p>${esc(p)}</p>`).join('');
      const info = card.querySelector('.topic-info-grid') || card.querySelector('.story-meta') || card.querySelector('.source-cluster');
      if (info) card.insertBefore(body, info); else card.appendChild(body);
      card.classList.add('has-longform');
    });
  }
  [350,1000,2200].forEach(delay => setTimeout(apply,delay));
})();
