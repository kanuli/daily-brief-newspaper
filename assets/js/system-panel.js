(() => {
  "use strict";

  const DESKS = [
    ["world.html", "🌍 世界"], ["asia.html", "🌏 亞洲"], ["hong-kong.html", "🇭🇰 香港"], ["japan.html", "🇯🇵 日本"],
    ["finance.html", "📈 財經"], ["stocks.html", "📊 Stock News"], ["technology.html", "🤖 AI / 科技"],
    ["manga-anime.html", "📚 漫畫 / Anime"], ["manchester-united.html", "🏟️ Manchester United"], ["football.html", "⚽ Football"],
    ["retail-deals.html", "🛒 最新優惠", "retail-nav"], ["archive.html", "🗂️ Archive"]
  ];
  const LIVE_HREF = "live.html?v=20260904-layout-v8";
  const HOME_HREF = "index.html?v=20260904-layout-v8#daily-edition";

  function injectNavStyle() {
    if (document.getElementById("mobile-two-row-nav-style")) return;
    const style = document.createElement("style");
    style.id = "mobile-two-row-nav-style";
    style.textContent = `
      .section-nav a[aria-current="page"]{background:#b00016!important}
      .section-nav .live-nav:not([aria-current="page"]){background:transparent!important}
      .section-nav .retail-nav:not([aria-current="page"]){background:transparent!important}
      .section-nav .retail-nav:hover{background:#b00016!important}
      @media (max-width:620px){.section-nav{display:grid!important;grid-template-columns:repeat(7,minmax(0,1fr))!important;grid-auto-flow:row!important;overflow:visible!important;width:100%!important;flex-wrap:unset!important}.section-nav a{display:flex!important;align-items:center!important;justify-content:center!important;min-width:0!important;padding:7px 2px!important;white-space:normal!important;overflow-wrap:anywhere!important;text-align:center!important;font-size:9.5px!important;line-height:1.12!important;border-right:1px solid #444!important;border-bottom:1px solid #444!important}.section-nav a:nth-child(7n){border-right:0!important}.section-nav a:nth-last-child(-n+7){border-bottom:0!important}}
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
    const homeCurrent = page === "index.html";
    const liveCurrent = page === "live.html";
    const links = [
      `<a class="live-nav" href="${LIVE_HREF}"${liveCurrent ? ' aria-current="page"' : ""}>🔴 Live</a>`,
      `<a class="home-nav" href="${HOME_HREF}"${homeCurrent ? ' aria-current="page"' : ""}>📰 頭版</a>`,
      ...DESKS.map(([href, label, className]) => {
        const target = href.split("#")[0].toLowerCase();
        const classAttr = className ? ` class="${className}"` : "";
        return `<a${classAttr} href="${href}"${target === page ? ' aria-current="page"' : ""}>${label}</a>`;
      })
    ];
    nav.innerHTML = links.join("");
    nav.querySelector(".home-nav")?.addEventListener("click", (event) => {
      if (!homeCurrent) return;
      const daily = document.getElementById("daily-edition");
      if (!daily) return;
      event.preventDefault();
      daily.scrollIntoView({ block: "start", behavior: "auto" });
      if (location.hash !== "#daily-edition") history.replaceState(null, "", "#daily-edition");
    });
  }

  function removeVoiceLabLinks() {
    document.querySelectorAll('a[href="voice.html"], a[href$="/voice.html"]').forEach((link) => link.remove());
  }

  function inject(src, marker) {
    if (document.querySelector(`script[${marker}]`)) return;
    const script = document.createElement("script");
    script.src = src;
    script.defer = true;
    script.setAttribute(marker, "true");
    document.head.appendChild(script);
  }

  function loadDisplayLocalization() {
    inject("assets/js/hktrad-display-sync.js?v=20260831-hk-mixed-v1", "data-hktrad-display-sync");
  }

  function loadArticleEnhancers() {
    if (document.body.dataset.page === "live") return;
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
    inject("assets/js/site-tts-canto-nano.js?v=20260901-cnf4-playback-v1", "data-site-tts");
  }

  function loadVoiceProductionStatus() {
    inject("assets/js/voice-production-status.js?v=20260901-cnf4-playback-v1", "data-voice-production-status");
  }

  function loadNewsPipelineStatus() {
    inject("assets/js/news-pipeline-status.js?v=20260824-2049-recovery", "data-news-pipeline-status");
  }

  function playMainLeadFromClick(button) {
    window.SiteTTS?.stop?.();
    const played = window.SiteTTS?.playLeadFromUserGesture?.() || false;
    if (played) {
      button.textContent = "🔊 廣東話朗讀";
      button.title = "使用 canto-tts-nano verified female 朗讀目前頭條";
      return;
    }
    button.textContent = "⏳ 廣東話女聲準備中";
    button.disabled = true;
    window.setTimeout(() => { button.textContent = "🔊 廣東話朗讀"; button.disabled = false; }, 2500);
  }

  function mountVoiceLauncher() {
    if (document.body.dataset.page === "archive" || document.getElementById("main-site-voice-button")) return;
    const voiceButton = document.createElement("button");
    voiceButton.id = "main-site-voice-button";
    voiceButton.type = "button";
    voiceButton.textContent = "🔊 廣東話朗讀";
    voiceButton.setAttribute("aria-label", "播放 canto-tts-nano 年輕女聲廣東話頭條朗讀");
    voiceButton.addEventListener("click", () => playMainLeadFromClick(voiceButton));
    document.body.appendChild(voiceButton);
  }

  function mountSystemPanel() {
    injectNavStyle(); normalizeDeskNav(); removeVoiceLabLinks(); loadDisplayLocalization(); loadArticleEnhancers(); loadSiteTTS(); loadVoiceProductionStatus(); loadNewsPipelineStatus(); mountVoiceLauncher();
    if (document.getElementById("system-status-button")) return;
    const button = document.createElement("button");
    button.id = "system-status-button"; button.className = "system-status-button"; button.type = "button";
    button.setAttribute("aria-label", "System status"); button.setAttribute("aria-expanded", "false");
    button.innerHTML = '<span class="system-status-dot" aria-hidden="true"></span><span class="system-status-label">SYSTEM</span>';
    const panel = document.createElement("aside");
    panel.id = "system-status-panel"; panel.className = "system-status-panel"; panel.hidden = true;
    panel.innerHTML = `<div class="system-panel-head"><div><strong>System Status</strong><span>Maintenance & Monitoring</span></div><button type="button" class="system-panel-close" aria-label="關閉">×</button></div><div class="system-panel-row status-ok"><span class="status-dot"></span><div><strong>Website</strong><small>Static safe mode · publication layers monitored independently</small></div></div><div class="system-panel-row status-check"><span class="status-dot"></span><div><strong>Daily / Live / Stocks</strong><small>News Pipeline below separates background discovery, verified draft, main Live and public Pages</small></div></div><div class="system-panel-row status-check"><span class="status-dot"></span><div><strong>Cantonese Voice</strong><small>canto-tts-nano cnf4 · verified young female reference · HK Cantonese-English mixed-language · semantic-unit HK news-anchor pauses</small></div></div><div class="system-panel-row status-check"><span class="status-dot"></span><div><strong>GitHub Pages / Discord</strong><small>Pages deployment has automatic main/public convergence repair</small></div></div><div class="system-panel-links"><a href="https://github.com/kanuli/daily-brief-newspaper/actions" target="_blank" rel="noopener noreferrer">GitHub Actions ↗</a><a href="https://github.com/kanuli/daily-brief-newspaper" target="_blank" rel="noopener noreferrer">Repository ↗</a></div>`;
    function setOpen(open) { panel.hidden = !open; button.setAttribute("aria-expanded", String(open)); }
    button.addEventListener("click", () => setOpen(panel.hidden));
    panel.querySelector(".system-panel-close")?.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") setOpen(false); });
    document.body.append(button, panel);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountSystemPanel, { once: true });
  else mountSystemPanel();
  window.addEventListener("pageshow", normalizeDeskNav);
})();
