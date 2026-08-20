(() => {
  "use strict";

  const host = document.querySelector("#maintenance-monitoring");
  if (!host) return;

  const MAX_LIVE_AGE_MS = 4.25 * 60 * 60 * 1000;
  const FETCH_TIMEOUT_MS = 5000;

  function esc(value = "") {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function hktDateKey(date = new Date()) {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Hong_Kong",
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).formatToParts(date);
    const get = (type) => parts.find((p) => p.type === type)?.value || "";
    return `${get("year")}-${get("month")}-${get("day")}`;
  }

  function formatAge(ms) {
    if (!Number.isFinite(ms) || ms < 0) return "剛剛";
    const minutes = Math.floor(ms / 60000);
    if (minutes < 60) return `${minutes} 分鐘前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} 小時前`;
    return `${Math.floor(hours / 24)} 日前`;
  }

  function card(key, title, value, detail, cls = "status-check") {
    return `
      <article class="monitor-card ${cls}" data-monitor-card="${esc(key)}">
        <div class="monitor-label"><span class="status-dot"></span>${esc(title)}</div>
        <div class="monitor-value">${esc(value)}</div>
        <div class="monitor-detail">${esc(detail)}</div>
      </article>
    `;
  }

  async function localJson(url) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(url, { cache: "no-store", signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function replaceCard(key, html) {
    const el = host.querySelector(`[data-monitor-card="${key}"]`);
    if (el) el.outerHTML = html;
  }

  function renderShell() {
    host.innerHTML = `
      <div class="monitoring-head">
        <div>
          <h2>Maintenance & Monitoring｜維護與監察</h2>
          <p>輕量模式：只檢查本站資料，不在閱讀頁背景查詢 GitHub API。</p>
        </div>
        <div class="monitoring-overall status-check" id="monitoring-overall"><span class="status-dot"></span><span>CHECKING</span></div>
      </div>
      <div class="monitoring-grid">
        ${card("site", "Website", "Online", "此頁已成功載入。", "status-ok")}
        ${card("daily", "Daily Edition", "檢查中…", "讀取本地 Daily data", "status-check")}
        ${card("live", "Live Update", "檢查中…", "讀取本地 Live data", "status-check")}
        ${card("pages", "GitHub Pages", "Actions 監察", "按下方 GitHub Actions 查看正式 deployment 狀態。", "status-check")}
        ${card("discord", "Discord Push", "Actions 監察", "Discord workflow 狀態改由 GitHub Actions 頁確認。", "status-check")}
        ${card("data", "Data Integrity", "檢查中…", "檢查 Top 5、sections 與每日10字", "status-check")}
      </div>
      <div class="monitoring-footer">
        <div>
          <strong>Maintenance:</strong> 目前沒有預定維護。為保持手機頁面順暢，不再自動背景輪詢。<br>
          <span id="monitoring-checked">尚未完成檢查</span>
        </div>
        <div class="monitoring-links">
          <a href="https://github.com/kanuli/daily-brief-newspaper/actions" target="_blank" rel="noopener noreferrer">GitHub Actions ↗</a>
          <a href="https://github.com/kanuli/daily-brief-newspaper" target="_blank" rel="noopener noreferrer">Repository ↗</a>
          <button class="monitor-refresh" id="monitor-refresh" type="button">重新檢查</button>
        </div>
      </div>
    `;
  }

  function updateOverall() {
    const localCards = ["site", "daily", "live", "data"]
      .map((key) => host.querySelector(`[data-monitor-card="${key}"]`))
      .filter(Boolean);
    const overall = host.querySelector("#monitoring-overall");
    if (!overall) return;

    let cls = "status-ok";
    let label = "LOCAL CHECKS OK";
    if (localCards.some((c) => c.classList.contains("status-fail"))) {
      cls = "status-fail";
      label = "ACTION REQUIRED";
    } else if (localCards.some((c) => c.classList.contains("status-warn"))) {
      cls = "status-warn";
      label = "WARNING";
    } else if (localCards.some((c) => c.classList.contains("status-check"))) {
      cls = "status-check";
      label = "PARTIAL CHECK";
    }
    overall.className = `monitoring-overall ${cls}`;
    overall.innerHTML = `<span class="status-dot"></span><span>${esc(label)}</span>`;
  }

  async function runChecks() {
    const refresh = host.querySelector("#monitor-refresh");
    if (refresh) {
      refresh.disabled = true;
      refresh.textContent = "檢查中…";
    }

    let daily = null;
    let vocab = null;

    try {
      daily = await localJson("data/latest.json");
      const isToday = daily.date === hktDateKey();
      replaceCard("daily", card(
        "daily",
        "Daily Edition",
        isToday ? "今日版本已載入" : "版本日期需留意",
        `${daily.dateLabel || daily.date || "日期 N/V"} · ${daily.articles?.length || 0} 篇`,
        isToday ? "status-ok" : "status-warn"
      ));
    } catch (err) {
      replaceCard("daily", card("daily", "Daily Edition", "讀取失敗", String(err.name === "AbortError" ? "讀取逾時" : err.message || err), "status-fail"));
    }

    try {
      const live = await localJson("data/live.json");
      const updated = live.lastUpdated ? new Date(live.lastUpdated) : null;
      const age = updated ? Date.now() - updated.getTime() : Infinity;
      const stale = !updated || age > MAX_LIVE_AGE_MS;
      replaceCard("live", card(
        "live",
        "Live Update",
        stale ? "更新可能逾時" : "正常更新",
        `${live.lastUpdatedLabel || "Last updated N/V"} · ${updated ? formatAge(age) : "時間 N/V"} · ${live.nextUpdateLabel || ""}`,
        stale ? "status-warn" : "status-ok"
      ));
    } catch (err) {
      replaceCard("live", card("live", "Live Update", "讀取失敗", String(err.name === "AbortError" ? "讀取逾時" : err.message || err), "status-fail"));
    }

    if (daily?.date) {
      try {
        vocab = await localJson(`data/vocab/${daily.date}.json`);
      } catch (_) {
        vocab = null;
      }
    }

    if (daily) {
      const problems = [];
      if (!Array.isArray(daily.articles) || !daily.articles.length) problems.push("articles 缺失");
      if (!Array.isArray(daily.topFive) || daily.topFive.length !== 5) problems.push("Top 5 不完整");
      if (!Array.isArray(daily.sections) || !daily.sections.length) problems.push("sections 缺失");
      const words = Array.isArray(vocab?.words) ? vocab.words : [];
      if (words.length !== 10) problems.push(`單字 ${words.length}/10`);
      for (const level of ["N1", "N2", "N3", "N4", "N5"]) {
        if (words.filter((w) => w.level === level).length !== 2) problems.push(`${level} ≠ 2`);
      }
      replaceCard("data", card(
        "data",
        "Data Integrity",
        problems.length ? "需要檢查" : "資料完整",
        problems.length ? problems.join(" · ") : `${daily.articles.length} 篇新聞 · ${daily.sections.length} 個 sections · Top 5 完整 · Vocabulary 10/10`,
        problems.length ? "status-warn" : "status-ok"
      ));
    } else {
      replaceCard("data", card("data", "Data Integrity", "無法驗證", "Daily data 未能讀取。", "status-fail"));
    }

    const checked = host.querySelector("#monitoring-checked");
    if (checked) {
      checked.textContent = `Last checked ${new Intl.DateTimeFormat("zh-HK", {
        timeZone: "Asia/Hong_Kong",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      }).format(new Date())} HKT`;
    }

    updateOverall();
    if (refresh) {
      refresh.disabled = false;
      refresh.textContent = "重新檢查";
    }
  }

  renderShell();
  host.querySelector("#monitor-refresh")?.addEventListener("click", runChecks);

  const start = () => runChecks().catch(() => {});
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(start, { timeout: 1500 });
  } else {
    setTimeout(start, 500);
  }
})();
