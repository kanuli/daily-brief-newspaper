(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  async function getEditionData() {
    const edition = document.body.dataset.edition;
    const url = edition ? `data/${edition}.json` : "data/latest.json";
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`Edition HTTP ${res.status}`);
    return res.json();
  }

  function normalizeFinanceLabels() {
    document.querySelectorAll('a[href="#market-economy"]').forEach((a) => {
      a.textContent = "📈 財經 / 全球市場";
    });
    const heading = $("#market-economy .section-heading h2");
    if (heading) heading.textContent = "📈 財經 / 全球市場";
  }

  function observeFinanceLabel() {
    normalizeFinanceLabels();
    const host = $("#dynamic-sections");
    if (!host) return;
    const observer = new MutationObserver(() => normalizeFinanceLabels());
    observer.observe(host, { childList: true, subtree: true });
    setTimeout(() => observer.disconnect(), 8000);
  }

  function groupWords(words = []) {
    const levels = ["N1", "N2", "N3", "N4", "N5"];
    return levels.map((level) => ({
      level,
      words: words.filter((word) => word.level === level).slice(0, 2)
    }));
  }

  function renderDailyVocab(vocab) {
    const study = $("#study-desk");
    if (!study || $("#daily-vocab")) return;

    const groups = groupWords(vocab.words || []);
    const section = document.createElement("section");
    section.id = "daily-vocab";
    section.className = "daily-vocab";
    section.innerHTML = `
      <div class="section-heading daily-vocab-heading">
        <h2>今日10個日語單字</h2>
        <span>N1–N5 · 每級2個</span>
      </div>
      <p class="daily-vocab-intro">每日從 <strong>japanese-vocab-game</strong> 詞庫抽選 10 個字；假名、漢字、繁體中文意思及詞性沿用原資料。</p>
      <div class="vocab-level-grid">
        ${groups.map((group) => `
          <section class="vocab-level-block">
            <div class="vocab-level-title">${esc(group.level)}</div>
            ${group.words.length ? group.words.map((word) => `
              <article class="vocab-card">
                <div class="vocab-reading">${esc(word.reading || "")}</div>
                <div class="vocab-kanji">${esc(word.kanji || word.reading || "")}</div>
                <div class="vocab-meaning">${esc(word.meaning || "")}</div>
                <div class="vocab-pos">${esc(word.partOfSpeech || "")}</div>
              </article>
            `).join("") : `<p class="vocab-missing">本級今日未能取得兩個有效詞條。</p>`}
          </section>
        `).join("")}
      </div>
      <div class="vocab-source-note">
        <span>${esc(vocab.levelNote || "部分 JLPT 分級為推定，並非官方 JLPT 詞表。")}</span>
        <a href="${esc(vocab.sourceUrl || "https://github.com/kanuli/japanese-vocab-game")}" target="_blank" rel="noopener noreferrer">在 japanese-vocab-game 查看詞庫 ↗</a>
      </div>
    `;
    study.insertAdjacentElement("afterend", section);
  }

  async function loadDailyVocab(date) {
    if (!date) return;
    try {
      const res = await fetch(`data/vocab/${date}.json`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Vocab HTTP ${res.status}`);
      renderDailyVocab(await res.json());
    } catch (err) {
      console.warn("Daily vocab unavailable", err);
    }
  }

  function siteRootUrl() {
    const baseAttr = document.querySelector("base")?.getAttribute("href") || "./";
    return new URL(baseAttr, location.href);
  }

  function buildWhatsAppText(data) {
    const titles = (data.topFive || [])
      .map((id) => (data.articles || []).find((a) => a.id === id))
      .filter(Boolean)
      .slice(0, 3)
      .map((a, index) => `${index + 1}. ${a.title}`)
      .join("\n");
    const root = siteRootUrl();
    const dailyUrl = new URL("index.html", root).href;
    const liveUrl = new URL("live.html", root).href;
    return `🗞️ 每日晨報 Daily Brief｜${data.dateLabel || data.date || "今日"}\n\n${titles}${titles ? "\n\n" : ""}今日晨報：${dailyUrl}\nLive：${liveUrl}`;
  }

  async function copyText(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }

  function injectShareBar(data) {
    if ($("#share-bar")) return;
    const dateStrip = $(".date-strip");
    if (!dateStrip) return;
    const text = buildWhatsAppText(data);
    const bar = document.createElement("div");
    bar.id = "share-bar";
    bar.className = "share-bar";
    bar.innerHTML = `
      <span><strong>分享今日晨報</strong> · WhatsApp Channel 目前使用手動貼上方式</span>
      <div class="share-actions">
        <button type="button" id="copy-whatsapp-post">複製 WhatsApp Channel 貼文</button>
        <button type="button" id="share-daily-brief">分享連結</button>
      </div>
    `;
    dateStrip.insertAdjacentElement("afterend", bar);

    $("#copy-whatsapp-post", bar)?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      try {
        await copyText(text);
        const old = button.textContent;
        button.textContent = "已複製 ✓";
        setTimeout(() => (button.textContent = old), 1800);
      } catch (err) {
        console.error(err);
      }
    });

    $("#share-daily-brief", bar)?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      try {
        if (navigator.share) {
          await navigator.share({ title: "每日晨報 Daily Brief", text, url: new URL("index.html", siteRootUrl()).href });
        } else {
          await copyText(text);
          const old = button.textContent;
          button.textContent = "連結已複製 ✓";
          setTimeout(() => (button.textContent = old), 1800);
        }
      } catch (err) {
        if (err?.name !== "AbortError") console.error(err);
      }
    });
  }

  async function init() {
    observeFinanceLabel();
    try {
      const data = await getEditionData();
      await loadDailyVocab(data.date || document.body.dataset.edition);
      injectShareBar(data);
      setTimeout(normalizeFinanceLabels, 500);
      setTimeout(normalizeFinanceLabels, 1600);
    } catch (err) {
      console.warn("Daily extras unavailable", err);
    }
  }

  init();
})();
