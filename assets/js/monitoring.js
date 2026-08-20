(() => {
  "use strict";

  const host = document.querySelector("#maintenance-monitoring");
  if (!host) return;

  const API = "https://api.github.com/repos/kanuli/daily-brief-newspaper";
  const MAX_LIVE_AGE_MS = 4.25 * 60 * 60 * 1000;

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
    const rem = minutes % 60;
    if (hours < 24) return `${hours} 小時${rem ? ` ${rem} 分鐘` : ""}前`;
    return `${Math.floor(hours / 24)} 日前`;
  }

  function statusFromConclusion(run) {
    if (!run) return { cls: "status-check", label: "N/V" };
    if (run.status !== "completed") return { cls: "status-warn", label: String(run.status || "RUNNING").toUpperCase() };
    if (run.conclusion === "success") return { cls: "status-ok", label: "OPERATIONAL" };
    if (["failure", "timed_out", "cancelled", "startup_failure"].includes(run.conclusion)) {
      return { cls: "status-fail", label: String(run.conclusion).toUpperCase() };
    }
    return { cls: "status-warn", label: String(run.conclusion || "UNKNOWN").toUpperCase() };
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

  async function json(url) {
    const res = await fetch(url, {
      cache: "no-store",
      headers: url.startsWith("https://api.github.com/") ? { Accept: "application/vnd.github+json" } : undefined
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  async function latestWorkflowRun(workflow) {
    const data = await json(`${API}/actions/workflows/${workflow}/runs?branch=main&per_page=1`);
    return data.workflow_runs?.[0] || null;
  }

  function dataHealth(daily, vocab) {
    const problems = [];
    if (!Array.isArray(daily.articles) || daily.articles.length === 0) problems.push("articles 缺失");
    if (!Array.isArray(daily.topFive) || daily.topFive.length !== 5) problems.push("Top 5 不完整");
    if (!Array.isArray(daily.sections) || daily.sections.length === 0) problems.push("sections 缺失");

    const words = Array.isArray(vocab?.words) ? vocab.words : [];
    if (words.length !== 10) problems.push(`單字 ${words.length}/10`);
    for (const level of ["N1", "N2", "N3", "N4", "N5"]) {
      if (words.filter((w) => w.level === level).length !== 2) problems.push(`${level} ≠ 2`);
    }

    if (problems.length) {
      return { cls: "status-warn", value: "需要檢查", detail: problems.join(" · ") };
    }
    return {
      cls: "status-ok",
      value: "資料完整",
      detail: `${daily.articles.length} 篇新聞 · ${daily.sections.length} 個 sections · Top 5 完整 · Vocabulary 10/10`
    };
  }

  function renderShell() {
    host.innerHTML = `
      <div class="monitoring-head">
        <div>
          <h2>Maintenance & Monitoring｜維護與監察</h2>
          <p>即時檢查網站、Daily / Live 資料、GitHub Pages 與 Discord 通知 pipeline。</p>
        </div>
        <div class="monitoring-overall status-check" id="monitoring-overall"><span class="status-dot"></span><span>CHECKING</span></div>
      </div>
      <div class="monitoring-grid" id="monitoring-grid">
        ${card("site", "Website", "Online", "此監察面板已成功載入。", "status-ok")}
        ${card("daily", "Daily Edition", "檢查中…", "讀取 data/latest.json", "status-check")}
        ${card("live", "Live Update", "檢查中…", "讀取 data/live.json", "status-check")}
        ${card("pages", "GitHub Pages", "檢查中…", "查詢最近 deployment workflow", "status-check")}
        ${card("discord", "Discord Push", "檢查中…", "查詢最近 Discord workflow", "status-check")}
        ${card("data", "Data Integrity", "檢查中…", "檢查 Top 5、sections 與每日10字", "status-check")}
      </div>
      <div class="monitoring-footer">
        <div>
          <strong>Maintenance:</strong> 目前沒有預定維護。頁面開啟期間每 5 分鐘自動重新檢查。<br>
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

  function replaceCard(key, html) {
    const el = host.querySelector(`[data-monitor-card="${key}"]`);
    if (el) el.outerHTML = html;
  }

  function updateOverall() {
    const cards = [...host.querySelectorAll(".monitor-card")];
    const overall = host.querySelector("#monitoring-overall");
    if (!overall) return;
    let cls = "status-ok";
    let label = "ALL SYSTEMS OPERATIONAL";
    if (cards.some((c) => c.classList.contains("status-fail"))) {
      cls = "status-fail";
      label = "ACTION REQUIRED";
    } else if (cards.some((c) => c.classList.contains("status-warn"))) {
      cls = "status-warn";
      label = "WARNING";
    } else if (cards.some((c) => c.classList.contains("status-check"))) {
      cls = "status-check";
      label = "PARTIAL / N/V";
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
    let live = null;
    let vocab = null;

    try {
      daily = await json("data/latest.json");
      const isToday = daily.date === hktDateKey();
      replaceCard("daily", card(
        "daily",
        "Daily Edition",
        isToday ? "今日版本已載入" : "版本日期需留意",
        `${daily.dateLabel || daily.date || "日期 N/V"} · ${daily.articles?.length || 0} 篇`,
        isToday ? "status-ok" : "status-warn"
      ));
    } catch (err) {
      replaceCard("daily", card("daily", "Daily Edition", "讀取失敗", String(err.message || err), "status-fail"));
    }

    try {
      live = await json("data/live.json");
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
      replaceCard("live", card("live", "Live Update", "讀取失敗", String(err.message || err), "status-fail"));
    }

    if (daily?.date) {
      try {
        vocab = await json(`data/vocab/${daily.date}.json`);
      } catch (_) {
        vocab = null;
      }
    }

    if (daily) {
      const health = dataHealth(daily, vocab);
      replaceCard("data", card("data", "Data Integrity", health.value, health.detail, health.cls));
    } else {
      replaceCard("data", card("data", "Data Integrity", "無法驗證", "Daily data 未能讀取。", "status-fail"));
    }

    try {
      const run = await latestWorkflowRun("pages.yml");
      const status = statusFromConclusion(run);
      const age = run?.updated_at ? formatAge(Date.now() - new Date(run.updated_at).getTime()) : "時間 N/V";
      replaceCard("pages", card(
        "pages",
        "GitHub Pages",
        status.label,
        run ? `Run #${run.run_number} · ${age}` : "沒有可讀取的 workflow run",
        status.cls
      ));
    } catch (err) {
      replaceCard("pages", card("pages", "GitHub Pages", "API N/V", "網站已載入；GitHub workflow API 暫時未能讀取。", "status-check"));
    }

    try {
      const run = await latestWorkflowRun("discord-notify.yml");
      const status = statusFromConclusion(run);
      const age = run?.updated_at ? formatAge(Date.now() - new Date(run.updated_at).getTime()) : "時間 N/V";
      replaceCard("discord", card(
        "discord",
        "Discord Push",
        status.label,
        run ? `最近 workflow Run #${run.run_number} · ${age}` : "沒有可讀取的 workflow run",
        status.cls
      ));
    } catch (err) {
      replaceCard("discord", card("discord", "Discord Push", "API N/V", "GitHub workflow API 暫時未能讀取；不代表 Discord 發送失敗。", "status-check"));
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
  runChecks();
  setInterval(runChecks, 5 * 60 * 1000);
})();
