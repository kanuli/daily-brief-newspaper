(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  // Single source of truth for Japanese vocabulary audio. Daily Brief does not
  // resolve catalogs, offsets or byte ranges itself; it delegates playback to
  // the same production runtime used by 日本語單字清單.
  const CENTRAL_WORDLIST_URL = "https://kanuli.github.io/japanese-vocab-game/wordlist.html";
  const CENTRAL_WORDLIST_ORIGIN = new URL(CENTRAL_WORDLIST_URL).origin;
  const PRODUCTION_ENGINE = "supertonic3";
  const PRODUCTION_VOICE = "F1";
  const POS_LABELS = {
    noun: "名詞", n: "名詞", verb: "動詞", v: "動詞", adj: "形容詞", adjective: "形容詞",
    adv: "副詞", adverb: "副詞", particle: "助詞", conjunction: "接続詞", conj: "接続詞",
    pronoun: "代名詞", pron: "代名詞", interjection: "感動詞", int: "感動詞", auxiliary: "助動詞",
    aux: "助動詞", determiner: "連体詞", prefix: "接頭語", suffix: "接尾語", counter: "助数詞",
    numeral: "数詞", expression: "表現", phrase: "慣用表現"
  };

  let centralVoiceFrame = null, centralVoiceReadyPromise = null, activeButton = null;

  function japanesePos(value = "") { const raw = String(value).trim(); return raw ? (POS_LABELS[raw.toLowerCase()] || raw) : ""; }
  async function getEditionData() { const edition = document.body.dataset.edition; const url = edition ? `data/${edition}.json` : "data/latest.json"; const res = await fetch(url, { cache: "no-store" }); if (!res.ok) throw new Error(`Edition HTTP ${res.status}`); return res.json(); }
  function normalizeFinanceLabels() { document.querySelectorAll('a[href="#market-economy"]').forEach((a) => { if (a.textContent !== "📈 財經 / 全球市場") a.textContent = "📈 財經 / 全球市場"; }); const heading = $("#market-economy .section-heading h2"); if (heading && heading.textContent !== "📈 財經 / 全球市場") heading.textContent = "📈 財經 / 全球市場"; }
  function groupWords(words = []) { return ["N1", "N2", "N3", "N4", "N5"].map((level) => ({ level, words: words.filter((word) => word.level === level).slice(0, 2) })); }

  function configureCentralF1(win) {
    const doc = win.document;
    const engine = doc.getElementById("audioEngine");
    if (engine) {
      if (![...engine.options].some((option) => option.value === PRODUCTION_ENGINE)) {
        engine.add(new Option("Supertonic 3", PRODUCTION_ENGINE));
      }
      engine.value = PRODUCTION_ENGINE;
      engine.dispatchEvent(new Event("change", { bubbles: true }));
    }

    const voice = doc.getElementById("voice");
    if (voice) {
      if (![...voice.options].some((option) => option.value === PRODUCTION_VOICE)) {
        voice.add(new Option(PRODUCTION_VOICE, PRODUCTION_VOICE));
      }
      voice.value = PRODUCTION_VOICE;
    }

    const speed = doc.getElementById("speed");
    if (speed) speed.value = "1";
  }

  function waitForCentralRuntime(frame) {
    return new Promise((resolve, reject) => {
      const deadline = Date.now() + 15000;
      const check = () => {
        try {
          const win = frame.contentWindow;
          if (win?.WA && typeof win.WA.speak === "function" && win.JAPANESE_NAS_AUDIO?.primary === true) {
            configureCentralF1(win);
            resolve(win);
            return;
          }
        } catch (error) {
          reject(error);
          return;
        }
        if (Date.now() >= deadline) {
          reject(new Error("japanese-vocab-game production playback runtime did not become ready"));
          return;
        }
        setTimeout(check, 100);
      };
      check();
    });
  }

  function ensureCentralVoiceBridge() {
    if (centralVoiceReadyPromise) return centralVoiceReadyPromise;
    centralVoiceReadyPromise = new Promise((resolve, reject) => {
      if (location.origin !== CENTRAL_WORDLIST_ORIGIN) {
        reject(new Error("Central vocabulary playback bridge requires the production GitHub Pages origin"));
        return;
      }

      const frame = document.createElement("iframe");
      centralVoiceFrame = frame;
      frame.id = "daily-vocab-central-audio-bridge";
      frame.title = "Japanese vocabulary production audio bridge";
      frame.tabIndex = -1;
      frame.setAttribute("aria-hidden", "true");
      frame.style.cssText = "position:fixed;width:1px;height:1px;left:-10000px;top:-10000px;border:0;opacity:0;pointer-events:none";
      frame.src = `${CENTRAL_WORDLIST_URL}?daily-brief-audio-bridge=${Date.now()}`;
      frame.addEventListener("load", () => {
        waitForCentralRuntime(frame).then(resolve, reject);
      }, { once: true });
      frame.addEventListener("error", () => reject(new Error("Unable to load japanese-vocab-game production playback runtime")), { once: true });
      document.body.appendChild(frame);
    }).catch((error) => {
      centralVoiceReadyPromise = null;
      if (centralVoiceFrame?.isConnected) centralVoiceFrame.remove();
      centralVoiceFrame = null;
      throw error;
    });
    return centralVoiceReadyPromise;
  }

  function resetActiveButton() {
    if (!activeButton) return;
    activeButton.disabled = false;
    activeButton.textContent = "🔊";
    activeButton.classList.remove("is-playing", "is-loading");
    activeButton = null;
  }

  function stopVocabAudio() {
    try { centralVoiceFrame?.contentWindow?.WA?.pause?.(); } catch (_) {}
    resetActiveButton();
  }

  async function playF1(button) {
    if (!button || button.disabled) return;
    const reading = button.dataset.reading || "";
    const kanji = button.dataset.kanji || "";
    if (!reading) return;

    stopVocabAudio();
    activeButton = button;
    button.disabled = true;
    button.classList.add("is-loading");
    button.textContent = "…";
    button.title = `正在載入 ${reading}`;

    try {
      const win = await ensureCentralVoiceBridge();
      configureCentralF1(win);
      button.classList.remove("is-loading");
      button.classList.add("is-playing");
      button.textContent = "■";
      button.title = `Supertonic 3 F1 (japanese-vocab-game production)：${reading}`;

      await win.WA.speak(reading, {
        reading,
        kanji: kanji || "",
        displayWord: kanji || reading
      });

      if (activeButton === button) resetActiveButton();
    } catch (error) {
      console.warn("Central Supertonic F1 vocab audio unavailable", error);
      if (activeButton === button) {
        button.classList.remove("is-loading", "is-playing");
        button.textContent = "⚠";
        button.title = error?.message || "中央 F1 音訊暫時不可用";
        button.disabled = false;
        activeButton = null;
      }
    }
  }

  function renderDailyVocab(vocab) {
    const study = $("#study-desk"); if (!study || study.dataset.vocabLoaded === "true") return;
    const groups = groupWords(vocab.words || []); study.dataset.vocabLoaded = "true"; study.className = "section-block daily-vocab"; study.setAttribute("aria-label", "今日10個日語單字");
    study.innerHTML = `<div class="section-heading daily-vocab-heading"><h2>今日10個日語單字</h2><span>N1–N5 · 每級2個</span></div><p class="daily-vocab-intro">每日從詞庫抽選 10 個字；按 <strong>🔊</strong> 可播放預錄發音</p><div class="vocab-level-grid">${groups.map((group) => `<section class="vocab-level-block"><div class="vocab-level-title">${esc(group.level)}</div>${group.words.length ? group.words.map((word) => `<article class="vocab-card"><div class="vocab-card-head"><div><div class="vocab-reading">${esc(word.reading || "")}</div><div class="vocab-kanji">${esc(word.kanji || word.reading || "")}</div></div><button class="vocab-play" type="button" data-reading="${esc(word.reading || "")}" data-kanji="${esc(word.kanji || "")}" title="Supertonic 3 F1 發音">🔊</button></div><div class="vocab-meaning">${esc(word.meaning || "")}</div><div class="vocab-pos">${esc(japanesePos(word.partOfSpeech))}</div></article>`).join("") : `<p class="vocab-missing">本級今日未能取得兩個有效詞條。</p>`}</section>`).join("")}</div><div class="vocab-source-note"><span>${esc(vocab.levelNote || "部分 JLPT 分級為推定，並非官方 JLPT 詞表。")} · Voice: Supertonic 3 F1 · Source: japanese-vocab-game production</span><a href="${esc(vocab.sourceUrl || "https://github.com/kanuli/japanese-vocab-game")}" target="_blank" rel="noopener noreferrer">在 japanese-vocab-game 查看詞庫 ↗</a></div>`;
    study.addEventListener("click", (event) => { const button = event.target.closest(".vocab-play"); if (button) playF1(button); });
    // Preload the authoritative runtime so a later click keeps the browser's
    // user activation while the central resolver performs its normal fetches.
    ensureCentralVoiceBridge().catch((error) => console.warn("Central vocabulary audio bridge preload failed", error));
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

  async function init() {
    normalizeFinanceLabels();
    try {
      await getEditionData();
      const vocabDate = document.body.dataset.edition || hongKongDate();
      await loadDailyVocab(vocabDate);
      setTimeout(normalizeFinanceLabels, 400);
      setTimeout(normalizeFinanceLabels, 1200);
    } catch (err) {
      console.warn("Daily extras unavailable", err);
    }
  }

  window.addEventListener("pagehide", stopVocabAudio, { once: true });
  init();
})();