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

  function normalizeDeskNav() {
    const nav = document.querySelector('.section-nav[aria-label="新聞分版"]');
    if (!nav) return;
    const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    const links = [
      '<a class="live-nav" href="live.html">Live</a>',
      ...DESKS.map(([href, label]) => {
        const target = href.split("#")[0].toLowerCase();
        const current = target === page ? ' aria-current="page"' : "";
        return `<a href="${href}"${current}>${label}</a>`;
      })
    ];
    nav.innerHTML = links.join("");
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
      inject("assets/js/topic-longform.js?v=20260821-1915", "data-topic-longform");
      return;
    }
    if (document.body.dataset.page !== "archive" && document.body.dataset.page !== "stocks") {
      inject("assets/js/article-body-upgrade.js?v=20260821-1915", "data-article-body-upgrade");
    }
  }

  function mountSystemPanel() {
    normalizeDeskNav();
    loadArticleEnhancers();
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
      <div class="system-panel-head">
        <div><strong>System Status</strong><span>Maintenance & Monitoring</span></div>
        <button type="button" class="system-panel-close" aria-label="關閉">×</button>
      </div>
      <div class="system-panel-row status-ok">
        <span class="status-dot"></span><div><strong>Website</strong><small>Static safe mode · no background monitoring loop</small></div>
      </div>
      <div class="system-panel-row status-ok">
        <span class="status-dot"></span><div><strong>Daily / Live / Stocks</strong><small>Daily + Hourly Live + Rolling Desk + Stock News JSON are publishing sources</small></div>
      </div>
      <div class="system-panel-row status-check">
        <span class="status-dot"></span><div><strong>GitHub Pages / Discord</strong><small>Deployment and push delivery are checked externally</small></div>
      </div>
      <div class="system-panel-links">
        <a href="https://github.com/kanuli/daily-brief-newspaper/actions" target="_blank" rel="noopener noreferrer">GitHub Actions ↗</a>
        <a href="https://github.com/kanuli/daily-brief-newspaper" target="_blank" rel="noopener noreferrer">Repository ↗</a>
      </div>
    `;

    function setOpen(open) {
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    }

    button.addEventListener("click", () => setOpen(panel.hidden));
    panel.querySelector(".system-panel-close")?.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") setOpen(false); });
    document.body.append(button, panel);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountSystemPanel, { once: true });
  else mountSystemPanel();
})();