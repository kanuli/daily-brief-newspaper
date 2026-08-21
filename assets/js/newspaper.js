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

function dedupeIds(ids = []) {
  return [...new Set(ids.filter(Boolean))];
}

const SECTION_DEFS = [
  ["world", "世界", "歐洲 · 中東 · 美洲 · 非洲 · 大洋洲"],
  ["asia", "亞洲", "中國 · 台灣 · 韓國 · 東南亞 · 南亞"],
  ["hong-kong", "香港", "本地 · 社會 · 公共政策 · 民生"],
  ["japan", "日本", "社會 · 政策 · 交通 · 生活"],
  ["market-economy", "📈 財經 / 全球市場", "美國 · 歐洲 · 台灣 · 日本 · 香港 · 全球"],
  ["ai-tech", "AI / 科技", "AI · 半導體 · 軟件 · 科技"],
  ["science-new-tech", "🧪 科學 / 新技術", "科研 · 新技術"],
  ["cybersecurity", "🔐 網絡安全", "Cybersecurity"],
  ["software-apps", "📱 軟件 / App / 消費科技", "Software · Apps"],
  ["manga-anime", "漫畫 / Anime", "作品 · 產業 · 票房 · 聲優"],
  ["manchester-united", "Manchester United", "Club · Squad · Transfers"],
  ["football", "Football", "Worldwide football"],
  ["breaking-news", "📰 突發新聞", "Breaking"],
  ["worth-following", "🔎 今日值得跟進", "Follow-up"],
  ["upcoming-events", "📅 Upcoming events / 明日焦點", "Upcoming"]
];

const SECTION_META = new Map(SECTION_DEFS.map(([slug, title, subtitle]) => [slug, { slug, title, subtitle }]));

function sectionSlug(value = "") {
  const raw = String(value).trim();
  const lower = raw.toLowerCase();
  if (!raw) return "worth-following";
  if (raw.startsWith("世界") || lower === "world") return "world";
  if (raw.startsWith("亞洲") || lower === "asia") return "asia";
  if (raw.startsWith("香港") || lower === "hong-kong") return "hong-kong";
  if (raw.startsWith("日本") || lower === "japan") return "japan";
  if (raw.startsWith("📈") || raw.startsWith("財經") || lower === "market-economy") return "market-economy";
  if (raw.startsWith("AI / 科技") || raw.startsWith("AI／科技") || lower === "ai-tech") return "ai-tech";
  if (raw.startsWith("科學") || lower === "science-new-tech") return "science-new-tech";
  if (raw.startsWith("網絡安全") || raw.startsWith("網路安全") || lower === "cybersecurity") return "cybersecurity";
  if (raw.startsWith("軟件") || raw.startsWith("App") || lower === "software-apps") return "software-apps";
  if (raw.startsWith("漫畫") || raw.startsWith("Anime") || lower === "manga-anime") return "manga-anime";
  if (raw.startsWith("Manchester United") || lower === "manchester-united") return "manchester-united";
  if (raw.startsWith("Football") || lower === "football") return "football";
  if (lower === "breaking-news") return "breaking-news";
  if (lower === "upcoming-events") return "upcoming-events";
  return "worth-following";
}

function ensureSections(data) {
  data = data || {};
  data.articles = Array.isArray(data.articles) ? data.articles : [];
  const validSections = Array.isArray(data.sections) && data.sections.length > 0 && data.sections.every((section) => section && typeof section === "object" && !Array.isArray(section));
  if (validSections) {
    data.sections = data.sections.map((section) => ({ ...section, articleIds: dedupeIds(section.articleIds || []) }));
    return data;
  }

  const grouped = new Map();
  data.articles.forEach((article) => {
    if (!article?.id) return;
    const slug = sectionSlug(article.section);
    if (!grouped.has(slug)) grouped.set(slug, []);
    grouped.get(slug).push(article.id);
  });

  data.sections = SECTION_DEFS
    .filter(([slug]) => grouped.has(slug))
    .map(([slug, title, subtitle]) => ({ slug, title, subtitle, articleIds: dedupeIds(grouped.get(slug)) }));

  if (!data.sections.length && data.articles.length) {
    data.sections = [{ ...SECTION_META.get("worth-following"), articleIds: data.articles.map((article) => article.id).filter(Boolean) }];
  }
  return data;
}

function articleById(data, id) {
  return (data.articles || []).find((a) => a.id === id);
}

async function applyEditorialOverride(data) {
  data = ensureSections(data);
  if (!data?.date) return data;
  try {
    const res = await fetch(`data/editorial-overrides/${data.date}.json`, { cache: "no-store" });
    if (res.status === 404) return data;
    if (!res.ok) throw new Error(`Editorial override HTTP ${res.status}`);
    const override = await res.json();

    const incoming = Array.isArray(override.articles) ? override.articles : [];
    const incomingById = new Map(incoming.map((article) => [article.id, article]));
    const existingIds = new Set((data.articles || []).map((article) => article.id));
    data.articles = (data.articles || []).map((article) => incomingById.get(article.id) || article);
    incoming.forEach((article) => {
      if (!existingIds.has(article.id)) data.articles.push(article);
    });

    if (override.leadId) data.leadId = override.leadId;
    if (Array.isArray(override.topFive) && override.topFive.length) data.topFive = dedupeIds(override.topFive).slice(0, 5);

    Object.entries(override.sectionOverrides || {}).forEach(([slug, config]) => {
      let section = data.sections.find((item) => item.slug === slug);
      if (!section) {
        section = { ...(SECTION_META.get(slug) || { slug, title: slug, subtitle: "" }), articleIds: [] };
        data.sections.push(section);
      }
      if (config.title) section.title = config.title;
      if (config.subtitle) section.subtitle = config.subtitle;
      if (Array.isArray(config.articleIds)) section.articleIds = dedupeIds(config.articleIds);
    });

    const financeIds = dedupeIds(override.moveToMarketEconomy || []);
    if (financeIds.length) {
      data.sections.forEach((section) => {
        if (section.slug !== "market-economy") section.articleIds = (section.articleIds || []).filter((id) => !financeIds.includes(id));
      });
      let market = data.sections.find((section) => section.slug === "market-economy");
      if (!market) {
        market = { ...SECTION_META.get("market-economy"), articleIds: [] };
        data.sections.push(market);
      }
      market.articleIds = dedupeIds([...(market.articleIds || []), ...financeIds]);
    }
    return ensureSections(data);
  } catch (err) {
    console.warn("Editorial override unavailable", err);
    return ensureSections(data);
  }
}

function mediaMarkup(article, isLead = false) {
  const label = article.mediaLabel || article.section || "DAILY BRIEF";
  const img = article.image ? `<img src="${esc(article.image)}" alt="${esc(article.imageAlt || article.title)}" loading="${isLead ? "eager" : "lazy"}">` : "";
  const caption = article.imageCaption ? `<figcaption>${esc(article.imageCaption)}</figcaption>` : `<figcaption>圖片接口已預留；只會接入可合法使用或來源允許的新聞圖片。</figcaption>`;
  return `<figure class="media-frame" data-label="${esc(label)}">${img}${caption}</figure>`;
}

function sourceMarkup(article) {
  if (!article.sourceUrl) return "";
  return `<a class="source-link" href="${esc(article.sourceUrl)}" target="_blank" rel="noopener noreferrer">來源：${esc(article.sourceName || "原文")} ↗</a>`;
}

function renderLead(data) {
  const article = articleById(data, data.leadId) || (data.articles || [])[0];
  const host = $("#lead-story");
  if (!article || !host) return;
  host.innerHTML = `<span class="eyebrow">${esc(article.section)}｜今日頭條</span><h2>${esc(article.title)}</h2><p class="lead-deck">${esc(article.dek)}</p>${mediaMarkup(article, true)}<div class="story-meta">${esc(article.timeLabel || data.dateLabel)} · ${esc(article.sourceName || "")}</div><div class="story-body"><p>${esc(article.summary)}</p></div><div class="why-box"><strong>為何重要：</strong> ${esc(article.why)}</div>${sourceMarkup(article)}`;
}

function renderTopFive(data) {
  const host = $("#top-five");
  if (!host) return;
  const ids = Array.isArray(data.topFive) && data.topFive.length ? data.topFive : (data.articles || []).slice(0, 5).map((article) => article.id);
  host.innerHTML = ids.map((id) => articleById(data, id)).filter(Boolean).map((article) => `<article class="top-card"><div><h3>${esc(article.title)}</h3><p>${esc(article.dek)}</p></div></article>`).join("");
}

function renderSections(data) {
  const host = $("#dynamic-sections");
  if (!host) return;
  const sections = Array.isArray(data.sections) ? data.sections : [];
  host.innerHTML = sections.map((section) => {
    const stories = (section.articleIds || []).map((id) => articleById(data, id)).filter(Boolean);
    if (!stories.length) return "";
    const cards = stories.map((article, idx) => `<article class="story-card ${idx === 0 && stories.length > 1 ? "feature" : ""}"><div class="tag">${esc(article.section)}</div><h3>${esc(article.title)}</h3><p>${esc(article.summary)}</p><p class="why-mini"><strong>為何重要：</strong> ${esc(article.why)}</p>${sourceMarkup(article)}</article>`).join("");
    return `<section class="section-block" id="${esc(section.slug)}"><div class="section-heading"><h2>${esc(section.title)}</h2><span>${esc(section.subtitle || `${stories.length} 則`)}</span></div><div class="story-grid">${cards}</div></section>`;
  }).join("");
}

function setEditionMeta(data) {
  $$("[data-edition-date]").forEach((el) => (el.textContent = data.dateLabel || data.date || ""));
  $$("[data-edition-number]").forEach((el) => (el.textContent = data.editionNumber || "001"));
  $$("[data-edition-tagline]").forEach((el) => (el.textContent = data.tagline || "只留下值得你知道的事"));
  document.title = `每日晨報 Daily Brief｜${data.dateLabel || data.date || ""}`;
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
  host.innerHTML = `<div class="live-summary-head"><div><div class="live-kicker"><span class="live-dot"></span> LIVE UPDATE</div><h2>最新新聞更新</h2><p>Last updated ${esc(data.lastUpdatedLabel || "—")} · ${esc(data.nextUpdateLabel || "")}</p></div><div class="live-counts"><span><strong>${Number(data.newCount || 0)}</strong> NEW</span><span><strong>${Number(data.updatedCount || 0)}</strong> UPDATED</span><span><strong>${Number(data.developingCount || 0)}</strong> DEVELOPING</span></div></div><div class="live-summary-grid">${items.length ? items.map((item) => `<article class="live-mini-card"><div>${liveBadge(item.status)} <span class="live-time">${esc(item.timeLabel || "")}</span></div><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p></article>`).join("") : `<p class="notice">本輪沒有需要新增的重大新聞。Daily Edition 保持不變。</p>`}</div><div class="live-more"><a href="live.html">查看完整 Live Update →</a></div>`;
}

function renderLivePage(data) {
  const headerTime = $("#live-header-time");
  if (headerTime) headerTime.textContent = data.lastUpdatedLabel || "—";
  const stats = $("#live-page-stats");
  if (stats) stats.innerHTML = `<div><strong>${Number(data.newCount || 0)}</strong><span>NEW</span></div><div><strong>${Number(data.updatedCount || 0)}</strong><span>UPDATED</span></div><div><strong>${Number(data.developingCount || 0)}</strong><span>DEVELOPING</span></div><p>${esc(data.nextUpdateLabel || "")}</p>`;
  const host = $("#live-page-items");
  if (!host) return;
  const items = data.items || [];
  host.innerHTML = items.length ? items.map((item) => `<article class="live-story"><div class="live-story-meta">${liveBadge(item.status)} <span>${esc(item.section || "Live")}</span> <span>${esc(item.timeLabel || "")}</span></div><h2>${esc(item.title)}</h2><p>${esc(item.summary)}</p>${liveSource(item)}</article>`).join("") : `<p class="notice">本輪沒有重大新消息。下一輪仍會按排程檢查。</p>`;
  document.title = `Live Update｜每日晨報｜${data.lastUpdatedLabel || ""}`;
}

async function fetchLiveData() {
  const res = await fetch("data/live.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadLiveSummary() {
  try { renderLiveSummary(await fetchLiveData()); }
  catch (err) { console.error(err); const host = $("#live-summary"); if (host) host.innerHTML = `<p class="notice">Live Update 暫時未能載入；Daily Edition 仍可正常閱讀。</p>`; }
}

async function loadLivePage() {
  try { renderLivePage(await fetchLiveData()); }
  catch (err) { console.error(err); const host = $("#live-page-items"); if (host) host.innerHTML = `<p class="notice">Live Update 暫時未能載入。</p>`; }
}

async function loadEdition() {
  const edition = document.body.dataset.edition;
  const url = edition ? `data/${edition}.json` : "data/latest.json";
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    let data = ensureSections(await res.json());
    data = ensureSections(await applyEditorialOverride(data));
    setEditionMeta(data);
    renderLead(data);
    renderTopFive(data);
    renderSections(data);
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
    host.innerHTML = (data.editions || []).map((edition) => `<a class="archive-item" href="${esc(edition.url)}"><div class="archive-date">${esc(edition.shortDate)}</div><div><div class="archive-title">${esc(edition.headline)}</div><div class="archive-topics">${esc((edition.topics || []).join(" · "))}</div></div><div>閱讀 →</div></a>`).join("");
  } catch (err) { host.innerHTML = `<p class="notice">Archive 暫時未能載入。</p>`; }
}

const page = document.body.dataset.page;
if (page === "archive") loadArchive();
else if (page === "live") loadLivePage();
else {
  loadEdition();
  if (!document.body.dataset.edition) loadLiveSummary();
}
