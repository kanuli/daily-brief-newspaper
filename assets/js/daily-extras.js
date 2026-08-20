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
      if (a.textContent !== "📈 財經 / 全球市場") {
        a.textContent = "📈 財經 / 全球市場";
      }
    });
    const heading = $("#market-economy .section-heading h2");
    if (heading && heading.textContent !== "📈 財經 / 全球市場") {
      heading.textContent = "📈 財經 / 全球市場";
    }
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
    if (!study || study.dataset.vocabLoaded === "true") return;

    const groups = groupWords(vocab.words || []);
    study.dataset.vocabLoaded = "true";
    study.className = "daily-vocab";
    study.setAttribute("aria-label", "今日10個日語單字");
    study.innerHTML = `
      <div class="section-heading daily-vocab-heading">
        <h2>今日10個日語單字</h2>
        <span>N1–N5 · 每級2個</span>
      </div>
      <p class="daily-vocab-intro">每日從 <strong>japanese-vocab-game</strong> 詞庫抽選 10 個字；假名、漢字、繁體中文意思及詞性沿用原資料。此版不再顯示 JLPT countdown。</p>
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

  async function init() {
    normalizeFinanceLabels();
    try {
      const data = await getEditionData();
      await loadDailyVocab(data.date || document.body.dataset.edition);
      setTimeout(normalizeFinanceLabels, 400);
      setTimeout(normalizeFinanceLabels, 1200);
    } catch (err) {
      console.warn("Daily extras unavailable", err);
    }
  }

  init();
})();
