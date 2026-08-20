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
    : `<figcaption>新聞圖片接口已預留；Phase 2 只會接入可合法使用或來源允許的圖片。</figcaption>`;
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

function renderStudyDesk(data) {
  const host = $("#study-desk");
  if (!host || !data.studyDesk) return;
  const target = new Date(`${data.studyDesk.targetDate}T00:00:00+09:00`);
  const now = new Date();
  const days = Math.max(0, Math.ceil((target - now) / 86400000));
  host.innerHTML = `
    <div class="countdown">
      <div><strong>${days}</strong><span>日後 · ${esc(data.studyDesk.label)}</span></div>
    </div>
    <div>
      <h2>${esc(data.studyDesk.title)}</h2>
      <p>${esc(data.studyDesk.summary)}</p>
      <p><strong>今日行動：</strong>${esc(data.studyDesk.action)}</p>
      <a class="source-link" href="${esc(data.studyDesk.sourceUrl)}" target="_blank" rel="noopener noreferrer">官方資料：JLPT ↗</a>
    </div>
  `;
}

function setEditionMeta(data) {
  $$("[data-edition-date]").forEach((el) => (el.textContent = data.dateLabel));
  $$("[data-edition-number]").forEach((el) => (el.textContent = data.editionNumber || "001"));
  $$("[data-edition-tagline]").forEach((el) => (el.textContent = data.tagline || "只留下值得你知道的事"));
  document.title = `每日晨報 Daily Brief｜${data.dateLabel}`;
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
    renderStudyDesk(data);
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

if (document.body.dataset.page === "archive") loadArchive();
else loadEdition();
