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
  const CENTRAL_AUDIO_RESOLVER_URL = `${VOICE_REPO_BASE}/wordaudio-delta-voices.js`;
  const PRODUCTION_ENGINE = "supertonic3";
  const PRODUCTION_VOICE = "F1";
  const POS_LABELS = {
    noun: "名詞", n: "名詞", verb: "動詞", v: "動詞", adj: "形容詞", adjective: "形容詞",
    adv: "副詞", adverb: "副詞", particle: "助詞", conjunction: "接続詞", conj: "接続詞",
    pronoun: "代名詞", pron: "代名詞", interjection: "感動詞", int: "感動詞", auxiliary: "助動詞",
    aux: "助動詞", determiner: "連体詞", prefix: "接頭語", suffix: "接尾語", counter: "助数詞",
    numeral: "数詞", expression: "表現", phrase: "慣用表現"
  };
  let centralAudioConfigPromise = null, activeAudio = null, activeBlobUrl = "", activeButton = null;

  function japanesePos(value = "") { const raw = String(value).trim(); return raw ? (POS_LABELS[raw.toLowerCase()] || raw) : ""; }
  async function getEditionData() { const edition = document.body.dataset.edition; const url = edition ? `data/${edition}.json` : "data/latest.json"; const res = await fetch(url, { cache: "no-store" }); if (!res.ok) throw new Error(`Edition HTTP ${res.status}`); return res.json(); }
  function normalizeFinanceLabels() { document.querySelectorAll('a[href="#market-economy"]').forEach((a) => { if (a.textContent !== "📈 財經 / 全球市場") a.textContent = "📈 財經 / 全球市場"; }); const heading = $("#market-economy .section-heading h2"); if (heading && heading.textContent !== "📈 財經 / 全球市場") heading.textContent = "📈 財經 / 全球市場"; }
  function groupWords(words = []) { return ["N1", "N2", "N3", "N4", "N5"].map((level) => ({ level, words: words.filter((word) => word.level === level).slice(0, 2) })); }

  async function getText(url, cache = "no-store") {
    const res = await fetch(url, { cache });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return res.text();
  }

  async function getJson(url, cache = "no-store") {
    const res = await fetch(url, { cache });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
    return res.json();
  }

  async function loadCentralAudioConfig() {
    if (!centralAudioConfigPromise) {
      centralAudioConfigPromise = (async () => {
        // japanese-vocab-game owns the production resolver. Read its current
        // production configuration instead of maintaining a Daily-Brief copy.
        const source = await getText(`${CENTRAL_AUDIO_RESOLVER_URL}?v=${Date.now()}`, "no-store");
        const baseMatch = source.match(/\bNAS_BASE\s*=\s*['\"]([^'\"]+)['\"]/);
        if (!baseMatch || !/playNas\s*\(/.test(source) || !/primary\s*:\s*true/.test(source)) {
          throw new Error("japanese-vocab-game production audio resolver is unavailable or incompatible");
        }
        return {
          apiBase: baseMatch[1].replace(/\/+$/, ""),
          resolverUrl: CENTRAL_AUDIO_RESOLVER_URL
        };
      })().catch((error) => {
        centralAudioConfigPromise = null;
        throw error;
      });
    }
    return centralAudioConfigPromise;
  }

  function selectCentralResult(payload, reading, written) {
    const rows = Array.isArray(payload?.results) ? payload.results : [];
    const targetWord = String(written || reading || "");
    const targetReading = String(reading || "");
    return rows.find((row) => String(row?.word || "") === targetWord && String(row?.reading || "") === targetReading)
      || rows.find((row) => String(row?.reading || "") === targetReading)
      || rows[0]
      || null;
  }

  async function resolveCentralF1(reading, kanji) {
    const config = await loadCentralAudioConfig();
    const term = String(kanji || reading || "");
    if (!term || !reading) throw new Error("單字資料不完整");
    const lookupUrl = `${config.apiBase}/api/v1/vocabulary/${encodeURIComponent(term)}?engine=${encodeURIComponent(PRODUCTION_ENGINE)}&voice=${encodeURIComponent(PRODUCTION_VOICE)}`;
    const payload = await getJson(lookupUrl, "no-store");
    const row = selectCentralResult(payload, reading, term);
    if (!row) throw new Error("中央 production audio 未命中此單字");
    const assets = Array.isArray(row.audios) ? row.audios : [];
    const asset = assets.find((item) => item?.engine === PRODUCTION_ENGINE && item?.voice === PRODUCTION_VOICE);
    if (!asset?.audio_url) throw new Error("中央 production F1 audio record 不完整");
    const audioUrl = /^https?:\/\//i.test(asset.audio_url)
      ? asset.audio_url
      : new URL(asset.audio_url, `${config.apiBase}/`).href;
    return { row, asset, audioUrl, lookupUrl, resolverUrl: config.resolverUrl };
  }

  function stopVocabAudio() {
    if (activeAudio) { try { activeAudio.pause(); activeAudio.currentTime = 0; } catch (_) {} activeAudio = null; }
    if (activeBlobUrl) { try { URL.revokeObjectURL(activeBlobUrl); } catch (_) {} activeBlobUrl = ""; }
    if (activeButton) { activeButton.disabled = false; activeButton.textContent = "🔊"; activeButton.classList.remove("is-playing", "is-loading"); activeButton = null; }
  }

  async function fetchCentralAudioBytes(url) {
    // Do not cache a mutable production audio URL locally. A central source
    // correction must take effect without clearing the browser cache.
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`Audio HTTP ${res.status}`);
    const bytes = await res.arrayBuffer();
    if (!bytes.byteLength) throw new Error("中央 production audio 為空");
    return bytes;
  }

  async function playF1(button) {
    if (!button || button.disabled) return; const reading = button.dataset.reading || ""; const kanji = button.dataset.kanji || ""; if (!reading) return;
    stopVocabAudio(); activeButton = button; button.disabled = true; button.classList.add("is-loading"); button.textContent = "…"; button.title = `正在載入 ${reading}`;
    try {
      const hit = await resolveCentralF1(reading, kanji);
      const bytes = await fetchCentralAudioBytes(hit.audioUrl);
      activeBlobUrl = URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
      const audio = activeAudio = new Audio(activeBlobUrl);
      button.classList.remove("is-loading"); button.classList.add("is-playing"); button.textContent = "■"; button.title = `Supertonic 3 F1 (japanese-vocab-game production)：${reading}`;
      audio.onended = stopVocabAudio; audio.onerror = stopVocabAudio; await audio.play();
    } catch (error) {
      console.warn("Central Supertonic F1 vocab audio unavailable", error); if (activeButton === button) { button.classList.remove("is-loading", "is-playing"); button.textContent = "⚠"; button.title = error?.message || "中央 F1 音訊暫時不可用"; button.disabled = false; activeButton = null; }
    }
  }

  function renderDailyVocab(vocab) {
    const study = $("#study-desk"); if (!study || study.dataset.vocabLoaded === "true") return;
    const groups = groupWords(vocab.words || []); study.dataset.vocabLoaded = "true"; study.className = "section-block daily-vocab"; study.setAttribute("aria-label", "今日10個日語單字");
    study.innerHTML = `<div class="section-heading daily-vocab-heading"><h2>今日10個日語單字</h2><span>N1–N5 · 每級2個</span></div><p class="daily-vocab-intro">每日從詞庫抽選 10 個字；按 <strong>🔊</strong> 可播放預錄發音</p><div class="vocab-level-grid">${groups.map((group) => `<section class="vocab-level-block"><div class="vocab-level-title">${esc(group.level)}</div>${group.words.length ? group.words.map((word) => `<article class="vocab-card"><div class="vocab-card-head"><div><div class="vocab-reading">${esc(word.reading || "")}</div><div class="vocab-kanji">${esc(word.kanji || word.reading || "")}</div></div><button class="vocab-play" type="button" data-reading="${esc(word.reading || "")}" data-kanji="${esc(word.kanji || "")}" title="Supertonic 3 F1 發音">🔊</button></div><div class="vocab-meaning">${esc(word.meaning || "")}</div><div class="vocab-pos">${esc(japanesePos(word.partOfSpeech))}</div></article>`).join("") : `<p class="vocab-missing">本級今日未能取得兩個有效詞條。</p>`}</section>`).join("")}</div><div class="vocab-source-note"><span>${esc(vocab.levelNote || "部分 JLPT 分級為推定，並非官方 JLPT 詞表。")} · Voice: Supertonic 3 F1 · Source: japanese-vocab-game production</span><a href="${esc(vocab.sourceUrl || "https://github.com/kanuli/japanese-vocab-game")}" target="_blank" rel="noopener noreferrer">在 japanese-vocab-game 查看詞庫 ↗</a></div>`;
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
