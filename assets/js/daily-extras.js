(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const ST3_CATALOG = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main/word-supertonic3-catalog.json";
  const ST3_F3_INDEX = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main/word-supertonic3-F3-index.json";
  let catalogPromise = null;
  let f3IndexPromise = null;
  let activeAudio = null;
  let activeBlobUrl = "";
  let activeButton = null;

  async function getEditionData() {
    const edition = document.body.dataset.edition;
    const url = edition ? `data/${edition}.json` : "data/latest.json";
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`Edition HTTP ${res.status}`);
    return res.json();
  }

  function normalizeFinanceLabels() {
    document.querySelectorAll('a[href="#market-economy"]').forEach((a) => {
      if (a.textContent !== "📈 財經 / 全球市場") a.textContent = "📈 財經 / 全球市場";
    });
    const heading = $("#market-economy .section-heading h2");
    if (heading && heading.textContent !== "📈 財經 / 全球市場") heading.textContent = "📈 財經 / 全球市場";
  }

  function groupWords(words = []) {
    const levels = ["N1", "N2", "N3", "N4", "N5"];
    return levels.map((level) => ({ level, words: words.filter((word) => word.level === level).slice(0, 2) }));
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: "force-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  function loadCatalog() {
    if (!catalogPromise) catalogPromise = getJson(ST3_CATALOG);
    return catalogPromise;
  }

  function loadF3Index() {
    if (!f3IndexPromise) f3IndexPromise = getJson(ST3_F3_INDEX);
    return f3IndexPromise;
  }

  function stopVocabAudio() {
    if (activeAudio) {
      try { activeAudio.pause(); activeAudio.currentTime = 0; } catch (_) {}
      activeAudio = null;
    }
    if (activeBlobUrl) {
      try { URL.revokeObjectURL(activeBlobUrl); } catch (_) {}
      activeBlobUrl = "";
    }
    if (activeButton) {
      activeButton.disabled = false;
      activeButton.textContent = "🔊 F3";
      activeButton.classList.remove("is-playing", "is-loading");
      activeButton = null;
    }
  }

  async function rangeBytes(bundle, offset, size) {
    const end = offset + size - 1;
    const urls = [bundle.githubUrl, bundle.hfUrl, bundle.url].filter(Boolean);
    let lastError = null;
    for (const url of urls) {
      try {
        const res = await fetch(url, {
          headers: { Range: `bytes=${offset}-${end}` },
          cache: "force-cache"
        });
        const bytes = await res.arrayBuffer();
        if (res.status !== 206 && !(res.status === 200 && bytes.byteLength === size)) {
          throw new Error(`Range HTTP ${res.status}`);
        }
        if (bytes.byteLength !== size) throw new Error(`Range size ${bytes.byteLength}/${size}`);
        return bytes;
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("音訊下載失敗");
  }

  async function playF3(button) {
    if (!button || button.disabled) return;
    const reading = button.dataset.reading || "";
    const kanji = button.dataset.kanji || "";
    if (!reading) return;

    stopVocabAudio();
    activeButton = button;
    button.disabled = true;
    button.classList.add("is-loading");
    button.textContent = "… F3";
    button.title = `正在載入 ${reading}`;

    try {
      const [catalog, index] = await Promise.all([loadCatalog(), loadF3Index()]);
      const key = `${reading}|${kanji || reading}`;
      const lookup = catalog?.words?.[key];
      if (!lookup) throw new Error("此單字未有 F3 預錄音");

      const [memberId, shard] = lookup;
      const bundle = index?.bundles?.[String(shard)];
      const member = bundle?.members?.[memberId];
      if (!bundle || !member) throw new Error("F3 音訊索引未命中");

      const bytes = await rangeBytes(bundle, Number(member[0]), Number(member[1]));
      activeBlobUrl = URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
      const audio = activeAudio = new Audio(activeBlobUrl);
      button.classList.remove("is-loading");
      button.classList.add("is-playing");
      button.textContent = "■ F3";
      button.title = `Supertonic 3 F3：${reading}`;
      audio.onended = stopVocabAudio;
      audio.onerror = stopVocabAudio;
      await audio.play();
    } catch (error) {
      console.warn("Supertonic F3 vocab audio unavailable", error);
      if (activeButton === button) {
        button.classList.remove("is-loading", "is-playing");
        button.textContent = "⚠ F3";
        button.title = error?.message || "F3 音訊暫時不可用";
        button.disabled = false;
        activeButton = null;
      }
    }
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
      <p class="daily-vocab-intro">每日從 <strong>japanese-vocab-game</strong> 詞庫抽選 10 個字；按 <strong>🔊 F3</strong> 可播放 Supertonic 3 專業播音女聲的預錄發音。音訊按需要逐字載入，不會下載整個 AI 模型。</p>
      <div class="vocab-level-grid">
        ${groups.map((group) => `
          <section class="vocab-level-block">
            <div class="vocab-level-title">${esc(group.level)}</div>
            ${group.words.length ? group.words.map((word) => `
              <article class="vocab-card">
                <div class="vocab-card-head">
                  <div>
                    <div class="vocab-reading">${esc(word.reading || "")}</div>
                    <div class="vocab-kanji">${esc(word.kanji || word.reading || "")}</div>
                  </div>
                  <button class="vocab-play" type="button" data-reading="${esc(word.reading || "")}" data-kanji="${esc(word.kanji || "")}" title="Supertonic 3 F3 發音">🔊 F3</button>
                </div>
                <div class="vocab-meaning">${esc(word.meaning || "")}</div>
                <div class="vocab-pos">${esc(word.partOfSpeech || "")}</div>
              </article>
            `).join("") : `<p class="vocab-missing">本級今日未能取得兩個有效詞條。</p>`}
          </section>
        `).join("")}
      </div>
      <div class="vocab-source-note">
        <span>${esc(vocab.levelNote || "部分 JLPT 分級為推定，並非官方 JLPT 詞表。")} · Voice: Supertonic 3 F3</span>
        <a href="${esc(vocab.sourceUrl || "https://github.com/kanuli/japanese-vocab-game")}" target="_blank" rel="noopener noreferrer">在 japanese-vocab-game 查看詞庫 ↗</a>
      </div>
    `;
    study.addEventListener("click", (event) => {
      const button = event.target.closest(".vocab-play");
      if (button) playF3(button);
    });
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

  window.addEventListener("pagehide", stopVocabAudio, { once: true });
  init();
})();
