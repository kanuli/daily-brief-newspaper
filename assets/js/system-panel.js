(() => {
  "use strict";

  const DESKS = [
    ["index.html", "頭版"],
    ["world.html", "世界"],
    ["asia.html", "亞洲"],
    ["hong-kong.html", "香港"],
    ["japan.html", "日本"],
    ["finance.html", "📈 財經"],
    ["stocks.html", "📊 Stock News"],
    ["technology.html", "AI / 科技"],
    ["manga-anime.html", "漫畫 / Anime"],
    ["manchester-united.html", "Manchester United"],
    ["football.html", "Football"],
    ["archive.html", "Archive"]
  ];

  function injectNavStyle() {
    if (document.getElementById("mobile-two-row-nav-style")) return;
    const style = document.createElement("style");
    style.id = "mobile-two-row-nav-style";
    style.textContent = `
      @media (max-width:620px){
        .section-nav{display:grid!important;grid-template-columns:repeat(7,minmax(0,1fr))!important;grid-auto-flow:row!important;overflow:visible!important;width:100%!important;flex-wrap:unset!important}
        .section-nav a{display:flex!important;align-items:center!important;justify-content:center!important;min-width:0!important;padding:7px 2px!important;white-space:normal!important;overflow-wrap:anywhere!important;text-align:center!important;font-size:9.5px!important;line-height:1.12!important;border-right:1px solid #444!important;border-bottom:1px solid #444!important}
        .section-nav a:nth-child(7n){border-right:0!important}.section-nav a:nth-last-child(-n+6){border-bottom:0!important}
      }
      #main-site-voice-button{position:fixed;right:14px;bottom:72px;z-index:9997;border:2px solid #111;background:#fff;color:#111;padding:10px 13px;border-radius:999px;font:800 12px/1.2 "Noto Sans TC",sans-serif;box-shadow:0 4px 18px rgba(0,0,0,.18);cursor:pointer}
      #main-site-voice-button:hover{background:#111;color:#fff}#main-site-voice-button:disabled{opacity:.6;cursor:wait}
      @media(max-width:620px){#main-site-voice-button{right:10px;bottom:68px;padding:9px 11px;font-size:11px}}
    `;
    document.head.appendChild(style);
  }

  function normalizeDeskNav() {
    const nav = document.querySelector('.section-nav[aria-label="新聞分版"]');
    if (!nav) return;
    const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    const links = ['<a class="live-nav" href="live.html">Live</a>', ...DESKS.map(([href, label]) => {
      const target = href.split("#")[0].toLowerCase();
      const current = target === page ? ' aria-current="page"' : "";
      return `<a href="${href}"${current}>${label}</a>`;
    })];
    nav.innerHTML = links.join("");
  }

  function removeVoiceLabLinks() {
    document.querySelectorAll('a[href="voice.html"], a[href$="/voice.html"]').forEach((link) => {
      const previous = link.previousSibling;
      const next = link.nextSibling;
      link.remove();
      if (previous?.nodeType === Node.TEXT_NODE && /^\s*·\s*$/.test(previous.textContent || "")) previous.remove();
      else if (next?.nodeType === Node.TEXT_NODE && /^\s*·\s*$/.test(next.textContent || "")) next.remove();
    });
  }

  function inject(src, marker) {
    if (document.querySelector(`script[${marker}]`)) return;
    const script = document.createElement("script");
    script.src = src;
    script.defer = true;
    script.setAttribute(marker, "true");
    document.head.appendChild(script);
  }

  function loadArticleEnhancers() {
    if (document.body.dataset.page === "topic") {
      inject("assets/js/topic-longform.js?v=20260821-2020", "data-topic-longform");
      return;
    }
    if (document.body.dataset.page !== "archive" && document.body.dataset.page !== "stocks") {
      inject("assets/js/article-body-upgrade.js?v=20260821-2020", "data-article-body-upgrade");
    }
  }

  function loadSiteTTS() {
    if (document.body.dataset.page === "archive") return;
    inject("assets/js/site-tts-v3.js?v=20260822-cosyqueue1", "data-site-tts");
  }

  function mountVoiceLauncher() {
    if (document.body.dataset.page === "archive" || document.getElementById("main-site-voice-button")) return;
    const voiceButton = document.createElement("button");
    voiceButton.id = "main-site-voice-button";
    voiceButton.type = "button";
    voiceButton.textContent = "🔊 廣東話朗讀";
    voiceButton.setAttribute("aria-label", "朗讀本頁首則新聞");
    voiceButton.addEventListener("click", async () => {
      const original = "🔊 廣東話朗讀";
      voiceButton.disabled = true;
      voiceButton.textContent = "⏳ 尋找新聞…";
      let articleButton = null;
      for (let i = 0; i < 20; i += 1) {
        articleButton = document.querySelector("main article .site-tts-button");
        if (articleButton) break;
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      if (articleButton) {
        articleButton.click();
        voiceButton.textContent = "🔊 正在朗讀首則新聞";
        setTimeout(() => { voiceButton.disabled = false; voiceButton.textContent = original; }, 1200);
        return;
      }
      voiceButton.disabled = false;
      voiceButton.textContent = "⚠️ 暫未找到可朗讀新聞";
      setTimeout(() => { voiceButton.textContent = original; }, 2500);
    });
    document.body.appendChild(voiceButton);
  }

  function mountSystemPanel() {
    injectNavStyle();
    normalizeDeskNav();
    removeVoiceLabLinks();
    loadArticleEnhancers();
    loadSiteTTS();
    mountVoiceLauncher();
    if (document.getElementById("system-status-button")) return;

    const button = document.createElement("button");
    button.id = "system-status-button";
    button.className = "system-status-button";
    button.type = "button";
    button.setAttribute("aria-label", "System status");
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = '<span class="system-status-dot" aria-hidden="true"></span><span class="system-status-label">SYSTEM</span>';

    const panel = document.createElement("aside");
    panel.id = "system-status-panel";
    panel.className = "system-status-panel";
    panel.hidden = true;
    panel.innerHTML = `
      <div class="system-panel-head"><div><strong>System Status</strong><span>Maintenance & Monitoring</span></div><button type="button" class="system-panel-close" aria-label="關閉">×</button></div>
      <div class="system-panel-row status-ok"><span class="status-dot"></span><div><strong>Website</strong><small>Static safe mode · no background monitoring loop</small></div></div>
      <div class="system-panel-row status-ok"><span class="status-dot"></span><div><strong>Daily / Live / Stocks</strong><small>Daily + Hourly Live + Rolling Desk + Stock News JSON are publishing sources</small></div></div>
      <div class="system-panel-row status-check"><span class="status-dot"></span><div><strong>GitHub Pages / Discord</strong><small>Deployment and push delivery are checked externally</small></div></div>
      <div class="system-panel-links"><a href="https://github.com/kanuli/daily-brief-newspaper/actions" target="_blank" rel="noopener noreferrer">GitHub Actions ↗</a><a href="https://github.com/kanuli/daily-brief-newspaper" target="_blank" rel="noopener noreferrer">Repository ↗</a></div>`;

    function setOpen(open) { panel.hidden = !open; button.setAttribute("aria-expanded", String(open)); }
    button.addEventListener("click", () => setOpen(panel.hidden));
    panel.querySelector(".system-panel-close")?.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") setOpen(false); });
    document.body.append(button, panel);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountSystemPanel, { once: true });
  else mountSystemPanel();
})();