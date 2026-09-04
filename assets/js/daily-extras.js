(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const VOICE_REPO_BASE = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main";
  const ST3_LAYERS = [
    { name: "runtime", catalogUrl: `${VOICE_REPO_BASE}/word-supertonic3-runtime-delta-catalog.json?v=20260827-runtime` },
    { name: "delta", catalogUrl: `${VOICE_REPO_BASE}/word-supertonic3-delta-catalog.json?v=20260827-delta` },
    { name: "base", catalogUrl: `${VOICE_REPO_BASE}/word-supertonic3-catalog.json?v=20260827-base`, indexUrl: `${VOICE_REPO_BASE}/word-supertonic3-F1-index.json?v=20260827-base` }
  ];
  const POS_LABELS = {
    noun: "名詞", n: "名詞", verb: "動詞", v: "動詞", adj: "形容詞", adjective: "形容詞",
    adv: "副詞", adverb: "副詞", particle: "助詞", conjunction: "接続詞", conj: "接続詞",
    pronoun: "代名詞", pron: "代名詞", interjection: "感動詞", int: "感動詞", auxiliary: "助動詞",
    aux: "助動詞", determiner: "連体詞", prefix: "接頭語", suffix: "接尾語", counter: "助数詞",
    numeral: "数詞", expression: "表現", phrase: "慣用表現"
  };
  let voiceLayersPromise = null, activeAudio = null, activeBlobUrl = "", activeButton = null;

  function japanesePos(value = "") { const raw = String(value).trim(); return raw ? (POS_LABELS[raw.toLowerCase()] || raw) : ""; }
  async function getEditionData() { const edition = document.body.dataset.edition; const url = edition ? `data/${edition}.json` : "data/latest.json"; const res = await fetch(url, { cache: "no-store" }); if (!res.ok) throw new Error(`Edition HTTP ${res.status}`); return res.json(); }
  function normalizeFinanceLabels() { document.querySelectorAll('a[href="#market-economy"]').forEach((a) => { if (a.textContent !== "📈 財經 / 全球市場") a.textContent = "📈 財經 / 全球市場"; }); const heading = $("#market-economy .section-heading h2"); if (heading && heading.textContent !== "📈 財經 / 全球市場") heading.textContent = "📈 財經 / 全球市場"; }
  function groupWords(words = []) { return ["N1", "N2", "N3", "N4", "N5"].map((level) => ({ level, words: words.filter((word) => word.level === level).slice(0, 2) })); }
  async function getJson(url, cache = "force-cache") { const res = await fetch(url, { cache }); if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`); return res.json(); }

  function absoluteIndexUrl(raw = "") {
    const value = String(raw || "").trim();
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value;
    return `${VOICE_REPO_BASE}/${value.replace(/^\.\//, "")}`;
  }

  function f1IndexUrl(catalog, fallback = "") {
    const voice = catalog?.voices?.F1 || {};
    return absoluteIndexUrl(voice.indexGithubUrl || voice.indexUrl || voice.indexURL || fallback);
  }

  async function loadVoiceLayers() {
    if (!voiceLayersPromise) {
      voiceLayersPromise = Promise.all(ST3_LAYERS.map(async (spec) => {
        try {
          const catalog = await getJson(spec.catalogUrl, "no-store");
          const indexUrl = f1IndexUrl(catalog, spec.indexUrl || "");
          if (!indexUrl) throw new Error(`${spec.name}: missing F1 index URL`);
          return { ...spec, catalog, indexUrl, indexPromise: null };
        } catch (error) {
          console.warn(`Supertonic F1 ${spec.name} catalog unavailable`, error);
          return null;
        }
      })).then((layers) => layers.filter(Boolean));
    }
    return voiceLayersPromise;
  }

  async function findF1Recording(key) {
    const layers = await loadVoiceLayers();
    for (const layer of layers) {
      const lookup = layer.catalog?.words?.[key];
      if (!lookup) continue;
      if (!layer.indexPromise) layer.indexPromise = getJson(layer.indexUrl, "no-store");
      const index = await layer.indexPromise;
      const [memberId, shard] = lookup;
      const bundle = index?.bundles?.[String(shard)];
      const member = bundle?.members?.[memberId];
      if (!bundle || !member) throw new Error(`${layer.name} F1 音訊索引未命中`);
      return { layer: layer.name, bundle, member };
    }
    throw new Error("此單字未有 F1 預錄音");
  }

  function stopVocabAudio() {
    if (activeAudio) { try { activeAudio.pause(); activeAudio.currentTime = 0; } catch (_) {} activeAudio = null; }
    if (activeBlobUrl) { try { URL.revokeObjectURL(activeBlobUrl); } catch (_) {} activeBlobUrl = ""; }
    if (activeButton) { activeButton.disabled = false; activeButton.textContent = "🔊"; activeButton.classList.remove("is-playing", "is-loading"); activeButton = null; }
  }

  async function rangeBytes(bundle, offset, size) {
    const end = offset + size - 1; const urls = [bundle.githubUrl, bundle.gitUrl, bundle.hfUrl, bundle.url].filter(Boolean); let lastError = null;
    for (const url of urls) {
      try { const res = await fetch(url, { headers: { Range: `bytes=${offset}-${end}` }, cache: "force-cache" }); const bytes = await res.arrayBuffer(); if (res.status !== 206 && !(res.status === 200 && bytes.byteLength === size)) throw new Error(`Range HTTP ${res.status}`); if (bytes.byteLength !== size) throw new Error(`Range size ${bytes.byteLength}/${size}`); return bytes; } catch (error) { lastError = error; }
    }
    throw lastError || new Error("音訊下載失敗");
  }

  async function playF1(button) {
    if (!button || button.disabled) return; const reading = button.dataset.reading || ""; const kanji = button.dataset.kanji || ""; if (!reading) return;
    stopVocabAudio(); activeButton = button; button.disabled = true; button.classList.add("is-loading"); button.textContent = "…"; button.title = `正在載入 ${reading}`;
    try {
      const key = `${reading}|${kanji || reading}`;
      const hit = await findF1Recording(key);
      const bytes = await rangeBytes(hit.bundle, Number(hit.member[0]), Number(hit.member[1])); activeBlobUrl = URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" })); const audio = activeAudio = new Audio(activeBlobUrl);
      button.classList.remove("is-loading"); button.classList.add("is-playing"); button.textContent = "■"; button.title = `Supertonic 3 F1 (${hit.layer})：${reading}`; audio.onended = stopVocabAudio; audio.onerror = stopVocabAudio; await audio.play();
    } catch (error) {
      console.warn("Supertonic F1 vocab audio unavailable", error); if (activeButton === button) { button.classList.remove("is-loading", "is-playing"); button.textContent = "⚠"; button.title = error?.message || "F1 音訊暫時不可用"; button.disabled = false; activeButton = null; }
    }
  }

  function renderDailyVocab(vocab) {
    const study = $("#study-desk"); if (!study || study.dataset.vocabLoaded === "true") return;
    const groups = groupWords(vocab.words || []); study.dataset.vocabLoaded = "true"; study.className = "section-block daily-vocab"; study.setAttribute("aria-label", "今日10個日語單字");
    study.innerHTML = `<div class="section-heading daily-vocab-heading"><h2>今日10個日語單字</h2><span>N1–N5 · 每級2個</span></div><p class="daily-vocab-intro">每日從詞庫抽選 10 個字；按 <strong>🔊</strong> 可播放預錄發音</p><div class="vocab-level-grid">${groups.map((group) => `<section class="vocab-level-block"><div class="vocab-level-title">${esc(group.level)}</div>${group.words.length ? group.words.map((word) => `<article class="vocab-card"><div class="vocab-card-head"><div><div class="vocab-reading">${esc(word.reading || "")}</div><div class="vocab-kanji">${esc(word.kanji || word.reading || "")}</div></div><button class="vocab-play" type="button" data-reading="${esc(word.reading || "")}" data-kanji="${esc(word.kanji || "")}" title="Supertonic 3 F1 發音">🔊</button></div><div class="vocab-meaning">${esc(word.meaning || "")}</div><div class="vocab-pos">${esc(japanesePos(word.partOfSpeech))}</div></article>`).join("") : `<p class="vocab-missing">本級今日未能取得兩個有效詞條。</p>`}</section>`).join("")}</div><div class="vocab-source-note"><span>${esc(vocab.levelNote || "部分 JLPT 分級為推定，並非官方 JLPT 詞表。")} · Voice: Supertonic 3 F1</span><a href="${esc(vocab.sourceUrl || "https://github.com/kanuli/japanese-vocab-game")}" target="_blank" rel="noopener noreferrer">在 japanese-vocab-game 查看詞庫 ↗</a></div>`;
    study.addEventListener("click", (event) => { const button = event.target.closest(".vocab-play"); if (button) playF1(button); });
  }

  async function loadDailyVocab(date) {
    const urls = date ? [`data/vocab/${date}.json`, "data/vocab/latest.json"] : ["data/vocab/latest.json"];
    let lastError = null;
    for (const url of urls) {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error(`Vocab HTTP ${res.status}`);
        const vocab = await res.json();
        if (!Array.isArray(vocab.words) || !vocab.words.length) throw new Error("Vocab payload is empty");
        renderDailyVocab(vocab);
        if (url.endsWith("latest.json") && date && vocab.date !== date) console.warn(`Daily vocab fallback used: requested ${date}, serving ${vocab.date || "latest"}`);
        return;
      } catch (err) {
        lastError = err;
      }
    }
    console.warn("Daily vocab unavailable", lastError);
  }
  function hongKongDate() {
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en", { timeZone: "Asia/Hong_Kong", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date()).map(({ type, value }) => [type, value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  }
  async function init() { normalizeFinanceLabels(); try { await getEditionData(); const vocabDate = document.body.dataset.edition || hongKongDate(); await loadDailyVocab(vocabDate); setTimeout(normalizeFinanceLabels, 400); setTimeout(normalizeFinanceLabels, 1200); } catch (err) { console.warn("Daily extras unavailable", err); } }
  window.addEventListener("pagehide", stopVocabAudio, { once: true }); init();
})();
