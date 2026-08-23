(() => {
  "use strict";

  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const STOP_TEXT = "■ 停止朗讀";
  const PENDING_TEXT = "⏳ F01 音訊準備中";
  const MANIFEST_URL = "data/tts-manifest.json";
  const REQUIRED_POLICY = "f01-news-anchor-v9-semantic-pauses-approved-10s-hktrad";
  const REQUIRED_LANGUAGE_GATE = "residual-latin-zero";
  const REQUIRED_SEGMENT_POLICY = "single-inference-per-article";
  const REQUIRED_CONDITIONING_POLICY = "approved-reference-bistream";
  const REQUIRED_PACING_POLICY = "hk-tv-news-semantic-pauses-v1";
  const REQUIRED_TEMPO_POLICY = "model-speed-only-no-post-stretch";
  const REQUIRED_REFERENCE_SECONDS = 10;
  const REFRESH_MS = 15000;

  let manifest = null;
  let activeButton = null;
  let timer = null;
  let refreshQueued = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function validEntry(entry) {
    return !!(
      entry?.audio &&
      entry?.prosodyPolicy === REQUIRED_POLICY &&
      entry?.languageGate === REQUIRED_LANGUAGE_GATE &&
      entry?.segmentPolicy === REQUIRED_SEGMENT_POLICY &&
      entry?.initialConditioningPolicy === REQUIRED_CONDITIONING_POLICY &&
      entry?.pacingPolicy === REQUIRED_PACING_POLICY &&
      entry?.tempoPolicy === REQUIRED_TEMPO_POLICY &&
      Number(entry?.referenceDurationSeconds) === REQUIRED_REFERENCE_SECONDS &&
      Number(entry?.segmentCount) === 1
    );
  }

  function validManifest(data) {
    return !!(
      data?.engine === "ASLP-lab/Cosyvoice2-Yue" &&
      data?.voice === "F01 female reference" &&
      data?.language === "yue-HK" &&
      data?.prosodyPolicy === REQUIRED_POLICY &&
      data?.languageGate === REQUIRED_LANGUAGE_GATE &&
      data?.segmentPolicy === REQUIRED_SEGMENT_POLICY &&
      data?.initialConditioningPolicy === REQUIRED_CONDITIONING_POLICY &&
      data?.pacingPolicy === REQUIRED_PACING_POLICY &&
      data?.tempoPolicy === REQUIRED_TEMPO_POLICY &&
      Number(data?.referenceDurationSeconds) === REQUIRED_REFERENCE_SECONDS
    );
  }

  function ensurePlayer() {
    if (!$("#site-tts-style")) {
      const style = document.createElement("style");
      style.id = "site-tts-style";
      style.textContent = `.site-tts-controls{display:flex;gap:8px;margin:10px 0}.site-tts-button{border:1px solid #222;background:#fff;color:#111;padding:7px 10px;font:700 12px/1.2 "Noto Sans TC",sans-serif;cursor:pointer;border-radius:3px}.site-tts-button:disabled{opacity:.58;cursor:default;background:#eee;color:#555}.site-tts-button[data-speaking="true"]{background:#111;color:#fff}#site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}#site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}`;
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">CosyVoice2-Yue · F01 女聲 · 新聞主播節奏</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="metadata" playsinline></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
      $("#site-tts-audio")?.addEventListener("ended", finishActive);
    }
  }

  function setStatus(text, open = true) {
    ensurePlayer();
    const player = $("#site-tts-player");
    if (player && player.dataset.open !== String(open)) player.dataset.open = String(open);
    setText($("#site-tts-status"), text);
  }

  function resetButton(button) {
    if (!button) return;
    if (button.dataset.speaking !== "false") button.dataset.speaking = "false";
    setText(button, BUTTON_TEXT);
  }

  function finishActive() {
    resetButton(activeButton);
    activeButton = null;
    setStatus("朗讀完成。", false);
  }

  function stopAll() {
    const audio = $("#site-tts-audio");
    if (audio) {
      try { audio.pause(); } catch (_) {}
      try { audio.currentTime = 0; } catch (_) {}
    }
    resetButton(activeButton);
    activeButton = null;
    setStatus("朗讀已停止。", false);
  }

  function articleTitle(article) {
    return clean($("h1,h2,h3", article)?.textContent);
  }

  function findEntry(article) {
    const title = articleTitle(article);
    if (!title || !manifest?.articles) return null;
    return Object.values(manifest.articles).find((entry) => validEntry(entry) && clean(entry?.title) === title) || null;
  }

  function entryUrl(entry) {
    const url = new URL(entry.audio, document.baseURI);
    url.searchParams.set("v", String(entry.bytes || entry.contentSha256 || manifest?.generatedAt || Date.now()));
    return url.href;
  }

  function play(entry, button = null) {
    if (!validEntry(entry)) return false;
    if (activeButton === button && button?.dataset.speaking === "true") {
      stopAll();
      return true;
    }
    stopAll();
    ensurePlayer();
    const audio = $("#site-tts-audio");
    audio.src = entryUrl(entry);
    audio.dataset.ready = "true";
    activeButton = button;
    if (button) {
      button.dataset.speaking = "true";
      setText(button, STOP_TEXT);
    }
    setStatus("使用中：F01 女聲 · 香港新聞主播節奏");
    const result = audio.play();
    result?.catch?.((error) => { console.warn("F01 playback rejected", error); finishActive(); });
    return true;
  }

  function configure(article) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE" || !article.closest("main")) return;
    if (article.closest(".study-desk,[data-no-tts]") || !articleTitle(article)) return;

    let button = $(".site-tts-button", article);
    if (!button) {
      const wrap = document.createElement("div");
      wrap.className = "site-tts-controls";
      button = document.createElement("button");
      button.type = "button";
      button.className = "site-tts-button";
      wrap.appendChild(button);
      const heading = $("h1,h2,h3", article);
      if (heading?.nextSibling) heading.parentNode.insertBefore(wrap, heading.nextSibling);
      else article.prepend(wrap);
    }

    if (button === activeButton && button.dataset.speaking === "true") return;

    const entry = findEntry(article);
    button.onclick = null;
    if (button.dataset.speaking !== "false") button.dataset.speaking = "false";

    if (validEntry(entry)) {
      if (button.disabled) button.disabled = false;
      setText(button, BUTTON_TEXT);
      if (button.title !== "F01 女聲 · 10秒核准聲線 · 新聞主播語義停頓") {
        button.title = "F01 女聲 · 10秒核准聲線 · 新聞主播語義停頓";
      }
      button.onclick = () => play(entry, button);
    } else {
      if (!button.disabled) button.disabled = true;
      setText(button, PENDING_TEXT);
      if (button.title !== "只播放通過目前v9聲線與節奏政策的F01音訊。") {
        button.title = "只播放通過目前v9聲線與節奏政策的F01音訊。";
      }
    }
  }

  function refreshButtons() {
    $$("main article").forEach(configure);
  }

  function queueButtonRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    const schedule = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 0));
    schedule(() => {
      refreshQueued = false;
      refreshButtons();
    });
  }

  async function refreshManifest() {
    try {
      const url = new URL(MANIFEST_URL, document.baseURI);
      url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
      const fresh = await response.json();
      manifest = validManifest(fresh) ? fresh : null;
    } catch (error) {
      console.warn("F01 v9 manifest unavailable", error);
      manifest = null;
    }
    refreshButtons();
  }

  function leadEntry() {
    if (!manifest?.articles) return null;
    if (manifest.leadId && validEntry(manifest.articles[manifest.leadId])) return manifest.articles[manifest.leadId];
    const title = clean(manifest.leadTitle);
    return Object.values(manifest.articles).find((entry) => validEntry(entry) && clean(entry?.title) === title) || null;
  }

  window.SiteTTS = {
    playLeadFromUserGesture() {
      const entry = leadEntry();
      return validEntry(entry) ? play(entry, null) : false;
    },
    stop: stopAll,
    isReady() { return true; }
  };

  function containsArticle(node) {
    return node instanceof Element && (node.matches("article") || !!node.querySelector("article"));
  }

  function boot() {
    ensurePlayer();
    refreshButtons();
    refreshManifest();
    if (timer) clearInterval(timer);
    timer = setInterval(refreshManifest, REFRESH_MS);

    const observer = new MutationObserver((mutations) => {
      const articleAdded = mutations.some((mutation) => [...mutation.addedNodes].some(containsArticle));
      if (articleAdded) queueButtonRefresh();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refreshManifest();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
