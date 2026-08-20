const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function esc(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function articleById(data, id) {
  return data.articles.find((a) => a.id === id);
}

function mediaMarkup(article, isLead = false) {
  const label = article.mediaLabel || article.section || "DAILY BRIEF";
  const img = article.image
    ? `<img src="${esc(article.image)}" alt="${esc(article.imageAlt || article.title)}" loading="${isLead ? "eager" : "lazy"}">`
    : "";
  const caption = article.imageCaption
    ? `<figcaption>${esc(article.imageCaption)}</figcaption>`
    : `<figcaption>圖片接口已預留；只會接入可合法使用或來源允許的新聞圖片。</figcaption>`;
  return `<figure class="media-frame" data-label="${esc(label)}">${img}${caption}</figure>`;
}

function sourceMarkup(article) {
  if (!article.sourceUrl) return "";
  return `<a class="source-link" href="${esc(article.sourceUrl)}" target="_blank" rel="noopener noreferrer">來源：${esc(article.sourceName || "原文")} ↗</a>`;
}

function renderLead(data) {
  const article = articleById(data, data.leadId);
  if (!article) return;
  const host = $("#lead-story");
  if (!host) return;
  host.innerHTML = `
    <span class="eyebrow">${esc(article.section)}｜今日頭條</span>
    <h2>${esc(article.title)}</h2>
    <p class="lead-deck">${esc(article.dek)}</p>
    ${mediaMarkup(article, true)}
    <div class="story-meta">${esc(article.timeLabel || data.dateLabel)} · ${esc(article.sourceName || "")}</div>
    <div class="story-body"><p>${esc(article.summary)}</p></div>
    <div class="why-box"><strong>為何重要：</strong> ${esc(article.why)}</div>
    ${sourceMarkup(article)}
  `;
}

function renderTopFive(data) {
  const host = $("#top-five");
  if (!host) return;
  host.innerHTML = data.topFive
    .map((id) => articleById(data, id))
    .filter(Boolean)
    .map((article) => `
      <article class="top-card">
        <div>
          <h3>${esc(article.title)}</h3>
          <p>${esc(article.dek)}</p>
        </div>
      </article>
    `)
    .join("");
}

function renderSections(data) {
  const host = $("#dynamic-sections");
  if (!host) return;
  host.innerHTML = data.sections
    .map((section) => {
      const stories = section.articleIds.map((id) => articleById(data, id)).filter(Boolean);
      if (!stories.length) return "";
      const cards = stories
        .map((article, idx) => `
          <article class="story-card ${idx === 0 && stories.length > 1 ? "feature" : ""}">
            <div class="tag">${esc(article.section)}</div>
            <h3>${esc(article.title)}</h3>
            <p>${esc(article.summary)}</p>
            <p class="why-mini"><strong>為何重要：</strong> ${esc(article.why)}</p>
            ${sourceMarkup(article)}
          </article>
        `)
        .join("");
      return `
        <section class="section-block" id="${esc(section.slug)}">
          <div class="section-heading">
            <h2>${esc(section.title)}</h2>
            <span>${esc(section.subtitle || `${stories.length} 則`)}</span>
          </div>
          <div class="story-grid">${cards}</div>
        </section>
      `;
    })
    .join("");
}

function clearLegacyStudyDesk() {
  const host = $("#study-desk");
  if (host) host.innerHTML = "";
}

function setEditionMeta(data) {
  $$("[data-edition-date]").forEach((el) => (el.textContent = data.dateLabel));
  $$("[data-edition-number]").forEach((el) => (el.textContent = data.editionNumber || "001"));
  $$("[data-edition-tagline]").forEach((el) => (el.textContent = data.tagline || "只留下值得你知道的事"));
  document.title = `每日晨報 Daily Brief｜${data.dateLabel}`;
}

function liveBadge(status = "UPDATED") {
  const safe = String(status).toUpperCase();
  return `<span class="live-badge live-${esc(safe.toLowerCase())}">${esc(safe)}</span>`;
}

function liveSource(item) {
  if (!item.sourceUrl) return "";
  return `<a class="source-link" href="${esc(item.sourceUrl)}" target="_blank" rel="noopener noreferrer">來源：${esc(item.sourceName || "原文")} ↗</a>`;
}

function renderLiveSummary(data) {
  const host = $("#live-summary");
  if (!host) return;
  const items = (data.items || []).slice(0, 4);
  host.innerHTML = `
    <div class="live-summary-head">
      <div>
        <div class="live-kicker"><span class="live-dot"></span> LIVE UPDATE</div>
        <h2>最新新聞更新</h2>
        <p>Last updated ${esc(data.lastUpdatedLabel || "—")} · ${esc(data.nextUpdateLabel || "")}</p>
      </div>
      <div class="live-counts">
        <span><strong>${Number(data.newCount || 0)}</strong> NEW</span>
        <span><strong>${Number(data.updatedCount || 0)}</strong> UPDATED</span>
        <span><strong>${Number(data.developingCount || 0)}</strong> DEVELOPING</span>
      </div>
    </div>
    <div class="live-summary-grid">
      ${items.length ? items.map((item) => `
        <article class="live-mini-card">
          <div>${liveBadge(item.status)} <span class="live-time">${esc(item.timeLabel || "")}</span></div>
          <h3>${esc(item.title)}</h3>
          <p>${esc(item.summary)}</p>
        </article>
      `).join("") : `<p class="notice">本輪沒有需要新增的重大新聞。Daily Edition 保持不變。</p>`}
    </div>
    <div class="live-more"><a href="live.html">查看完整 Live Update →</a></div>
  `;
}

function renderLivePage(data) {
  const headerTime = $("#live-header-time");
  if (headerTime) headerTime.textContent = data.lastUpdatedLabel || "—";
  const stats = $("#live-page-stats");
  if (stats) {
    stats.innerHTML = `
      <div><strong>${Number(data.newCount || 0)}</strong><span>NEW</span></div>
      <div><strong>${Number(data.updatedCount || 0)}</strong><span>UPDATED</span></div>
      <div><strong>${Number(data.developingCount || 0)}</strong><span>DEVELOPING</span></div>
      <p>${esc(data.nextUpdateLabel || "")}</p>
    `;
  }
  const host = $("#live-page-items");
  if (!host) return;
  const items = data.items || [];
  host.innerHTML = items.length ? items.map((item) => `
    <article class="live-story">
      <div class="live-story-meta">${liveBadge(item.status)} <span>${esc(item.section || "Live")}</span> <span>${esc(item.timeLabel || "")}</span></div>
      <h2>${esc(item.title)}</h2>
      <p>${esc(item.summary)}</p>
      ${liveSource(item)}
    </article>
  `).join("") : `<p class="notice">本輪沒有重大新消息。下一輪仍會按排程檢查。</p>`;
  document.title = `Live Update｜每日晨報｜${data.lastUpdatedLabel || ""}`;
}

async function fetchLiveData() {
  const res = await fetch("data/live.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadLiveSummary() {
  try {
    renderLiveSummary(await fetchLiveData());
  } catch (err) {
    console.error(err);
    const host = $("#live-summary");
    if (host) host.innerHTML = `<p class="notice">Live Update 暫時未能載入；Daily Edition 仍可正常閱讀。</p>`;
  }
}

async function loadLivePage() {
  try {
    renderLivePage(await fetchLiveData());
  } catch (err) {
    console.error(err);
    const host = $("#live-page-items");
    if (host) host.innerHTML = `<p class="notice">Live Update 暫時未能載入。</p>`;
  }
}

async function loadEdition() {
  const edition = document.body.dataset.edition;
  const url = edition ? `data/${edition}.json` : "data/latest.json";
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    setEditionMeta(data);
    renderLead(data);
    renderTopFive(data);
    renderSections(data);
    clearLegacyStudyDesk();
  } catch (err) {
    console.error(err);
    const main = $("main");
    if (main) main.innerHTML = `<p class="notice">無法載入本日新聞資料。請稍後重試或前往 Archive。</p>`;
  }
}

async function loadArchive() {
  const host = $("#archive-items");
  if (!host) return;
  try {
    const res = await fetch("data/archive.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    host.innerHTML = data.editions
      .map((edition) => `
        <a class="archive-item" href="${esc(edition.url)}">
          <div class="archive-date">${esc(edition.shortDate)}</div>
          <div>
            <div class="archive-title">${esc(edition.headline)}</div>
            <div class="archive-topics">${esc(edition.topics.join(" · "))}</div>
          </div>
          <div>閱讀 →</div>
        </a>
      `)
      .join("");
  } catch (err) {
    host.innerHTML = `<p class="notice">Archive 暫時未能載入。</p>`;
  }
}

const page = document.body.dataset.page;
if (page === "archive") loadArchive();
else if (page === "live") loadLivePage();
else {
  loadEdition();
  if (!document.body.dataset.edition) loadLiveSummary();
}
