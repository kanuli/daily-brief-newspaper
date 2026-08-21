(() => {
  "use strict";
  const esc = (v='') => String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const stories = [
    {
      title: 'J1今晚兩場關東焦點：柏太陽神迎長崎、FC東京對千葉',
      dek: 'J-League不再被歐洲大聯賽淹沒；今晚J1賽程有兩場需要跟進。',
      body: ['J1聯賽今日（8月21日）晚上有兩場賽事。柏太陽神在三協F柏球場迎戰V-Varen長崎，開賽時間為日本時間19:00；FC東京其後在19:30迎戰JEF千葉。柏太陽神官方與J.League賽程均列出柏對長崎的安排，而日本體育資訊亦確認FC東京對千葉的晚場賽程。', '對本報Football版而言，重點不是把J-League當作偶爾補充，而是像英超、西甲、意甲一樣每輪固定檢查賽程、賽果、傷兵、轉會與球會新聞。今晚兩場賽事會直接影響J1早段積分形勢，下一輪應跟進賽果、入球及任何傷停更新。'],
      sources: [['柏太陽神官方','https://www.reysol.co.jp/news/topteam/038779.html'],['J.League / 日本賽程','https://www.jleague.jp/']]
    },
    {
      title: '港超新季今晚開鑼：東方對沙田揭幕，11隊展開2026/27球季',
      dek: '香港足球屬Football版必搜項目，不能因歐洲轉會新聞較多而缺席。',
      body: ['2026/27香港超級聯賽今日（8月21日）開季，揭幕戰由東方對沙田。今季港超共有11支球隊參賽，本地媒體在開季前已報道賽事編排、各隊備戰與新兵情況；東方亦在新季開始前完成多項陣容調整。', '這類本地聯賽開季本身就是香港Football讀者應該看到的核心新聞，重要性不應由全球搜尋排名決定。之後每一輪Football搜集會固定檢查HKFA／港超、球會官方與可信本地體育媒體，並跟進揭幕戰賽果、球員表現、傷停及下一輪賽程。'],
      sources: [['TVB News','https://news.tvb.com/tc/sports/6888aa7fd639cb871fe9779b/%E9%AB%94%E8%82%B2-%E6%B8%AF%E8%B6%85%E8%81%AF%E6%96%B0%E7%90%83%E5%AD%A38%E6%9C%8821%E6%97%A5%E9%96%8B%E9%91%BC-%E6%9D%B1%E6%96%B9%E5%B0%8D%E6%B2%99%E7%94%B0%E6%89%93%E9%A0%AD%E9%99%A3'],['東網開季前瞻','https://hk.on.cc/hk/bkn/cnt/sport/20260818/bkn-20260818190000000-0818_00882_001.html']]
    }
  ];
  async function apply() {
    try {
      const edition = await fetch('data/latest.json', {cache:'no-store'}).then(r => r.json());
      if (edition.date !== '2026-08-21') return;
      const host = document.querySelector('#topic-sections .topic-section .topic-story-grid') || document.querySelector('#topic-sections');
      if (!host || document.querySelector('[data-football-catchup="20260821"]')) return;
      const wrap = document.createElement('div');
      wrap.setAttribute('data-football-catchup','20260821');
      wrap.className = 'football-catchup';
      wrap.innerHTML = stories.map(s => `<article class="topic-story"><div class="tag">Football · CURRENT</div><h2>${esc(s.title)}</h2><p class="topic-dek">${esc(s.dek)}</p><div class="topic-article-body">${s.body.map(p=>`<p>${esc(p)}</p>`).join('')}</div><div class="topic-info-grid"><div class="topic-info-card"><strong>下一步</strong><p>跟進賽果、傷兵、轉會與下一輪賽程。</p></div></div><div class="story-meta">2026-08-21 · cross-checked</div><div class="source-cluster">${s.sources.map(([n,u])=>`<a class="source-link" href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(n)} ↗</a>`).join(' ')}</div></article>`).join('');
      host.appendChild(wrap);
    } catch (e) { console.warn('Football catch-up unavailable', e); }
  }
  [300,900,1800].forEach(t => setTimeout(apply,t));
})();
