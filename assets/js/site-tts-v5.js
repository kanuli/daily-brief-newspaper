(() => {
  "use strict";

  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const MANIFEST_URL = "data/tts-manifest.json";
  const LEAD_AUDIO_URL = "assets/audio/cosyvoice/latest-lead.wav";
  const PAGE_CACHE_KEY = Date.now();
  let activeButton = null;
  let manifestPromise = null;
  let manifestData = null;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  function ensureUi() {
    if (!$("#site-tts-style")) {
      const style = document.createElement("style");
      style.id = "site-tts-style";
      style.textContent = `
        .site-tts-controls{display:flex;gap:8px;margin:10px 0}
        .site-tts-button{border:1px solid #222;background:#fff;color:#111;padding:7px 10px;font:700 12px/1.2 "Noto Sans TC",sans-serif;cursor:pointer;border-radius:3px}
        .site-tts-button:hover{background:#111;color:#fff}.site-tts-button:disabled{opacity:.55;cursor:wait}
        #site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}
        #site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}
      `;
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">CosyVoice2-Yue · F01 女聲</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="auto" playsinline></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
      $("#site-tts-audio")?.addEventListener("error", (event) => {
        console.warn("CosyVoice2-Yue audio element error", event);
      });
    }
  }

  function setStatus(text) {
    ensureUi();
    $("#site-tts-player").dataset.open = "true";
    $("#site-tts-status").textContent = text;
  }

  function leadUrl() {
    const url = new URL(LEAD_AUDIO_URL, document.baseURI);
    url.searchParams.set("v", String(PAGE_CACHE_KEY));
    return url.href;
  }

  function entryUrl(entry) {
    if (!entry?.audio) return null;
    const url = new URL(entry.audio, document.baseURI);
    url.searchParams.set("v", String(entry.bytes || entry.generatedAt || PAGE_CACHE_KEY));
    return url.href;
  }

  function primeAudio(url = leadUrl()) {
    ensureUi();
    const audio = $("#site-tts-audio");
    if (!audio) return null;
    if (audio.dataset.sourceUrl !== url) {
      try { audio.pause(); } catch (_) {}
      audio.src = url;
      audio.dataset.sourceUrl = url;
      audio.dataset.ready = "true";
      audio.preload = "auto";
      audio.load();
    }
    return audio;
  }

  function stopAll() {
    const audio = $("#site-tts-audio");
    if (audio) {
      try { audio.pause(); } catch (_) {}
      try { audio.currentTime = 0; } catch (_) {}
    }
    if (activeButton) {
      activeButton.disabled = false;
      activeButton.textContent = BUTTON_TEXT;
      activeButton = null;
    }
    setStatus("朗讀已停止。");
  }

  function playPreparedAudio(audio, button = null) {
    if (!audio) return false;
    if (activeButton && activeButton !== button) {
      activeButton.disabled = false;
      activeButton.textContent = BUTTON_TEXT;
    }
    activeButton = button;
    if (button) {
      button.disabled = true;
      button.textContent = "🔊 朗讀中";
    }
    setStatus("使用中：CosyVoice2-Yue · F01 女聲");

    let promise;
    try {
      promise = audio.play();
    } catch (error) {
      console.warn("CosyVoice2-Yue play() threw", error);
      return false;
    }

    if (promise && typeof promise.catch === "function") {
      promise.catch((error) => {
        console.warn("CosyVoice2-Yue initial play() rejected; retrying with fresh source", error);
        const fresh = new URL(LEAD_AUDIO_URL, document.baseURI);
        fresh.searchParams.set("v", String(Date.now()));
        audio.src = fresh.href;
        audio.dataset.sourceUrl = fresh.href;
        audio.dataset.ready = "true";
        try {
          const retry = audio.play();
          if (retry && typeof retry.catch === "function") retry.catch((retryError) => console.warn("CosyVoice2-Yue retry rejected", retryError));
        } catch (retryError) {
          console.warn("CosyVoice2-Yue retry threw", retryError);
        }
      }).finally(() => {
        if (button) {
          button.disabled = false;
          button.textContent = BUTTON_TEXT;
        }
        activeButton = null;
      });
    }
    return true;
  }

  function playEntry(entry, button = null) {
    const url = entryUrl(entry);
    if (!url) return false;
    const audio = primeAudio(url);
    return playPreparedAudio(audio, button);
  }

  function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = fetch(`${MANIFEST_URL}?v=${Date.now()}`, { cache: "no-store" }).then(async (response) => {
        if (!response.ok) throw new Error(`CosyVoice manifest HTTP ${response.status}`);
        const manifest = await response.json();
        if (manifest?.engine !== "ASLP-lab/Cosyvoice2-Yue") throw new Error("Unexpected TTS engine in manifest");
        if (!manifest?.articles || typeof manifest.articles !== "object") throw new Error("CosyVoice manifest has no articles");
        manifestData = manifest;
        return manifest;
      }).catch((error) => {
        manifestPromise = null;
        manifestData = null;
        throw error;
      });
    }
    return manifestPromise;
  }

  function articleTitle(article) {
    return clean($("h1,h2,h3", article)?.textContent);
  }

  function findEntry(manifest, article) {
    const title = articleTitle(article);
    if (!title) return null;
    return Object.values(manifest.articles).find((entry) => clean(entry?.title) === title) || null;
  }

  function addButton(article, manifest) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE" || !article.closest("main")) return;
    if (article.dataset.siteTtsReady === "true" || article.closest(".study-desk,[data-no-tts]")) return;
    const entry = findEntry(manifest, article);
    if (!entry) return;
    article.dataset.siteTtsReady = "true";
    const wrap = document.createElement("div");
    wrap.className = "site-tts-controls";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "site-tts-button";
    button.textContent = BUTTON_TEXT;
    button.setAttribute("aria-label", "用 CosyVoice2-Yue F01 女聲朗讀這則新聞");
    button.addEventListener("click", () => playEntry(entry, button));
    wrap.appendChild(button);
    const heading = $("h1,h2,h3", article);
    if (heading?.nextSibling) heading.parentNode.insertBefore(wrap, heading.nextSibling);
    else article.prepend(wrap);
  }

  function scan(manifest, root = document) {
    if (root instanceof Element) {
      if (root.matches("article")) addButton(root, manifest);
      const owner = root.closest("article");
      if (owner) addButton(owner, manifest);
      $$("article", root).forEach((article) => addButton(article, manifest));
      return;
    }
    $$("main article").forEach((article) => addButton(article, manifest));
  }

  window.SiteTTS = {
    playLeadFromUserGesture() {
      const audio = primeAudio(leadUrl());
      return playPreparedAudio(audio, null);
    },
    isReady() {
      return Boolean($("#site-tts-audio")?.src);
    }
  };

  async function boot() {
    ensureUi();
    // Prime the real production WAV immediately. The user click later only calls play().
    primeAudio(leadUrl());
    let manifest;
    try {
      manifest = await loadManifest();
    } catch (error) {
      console.warn("CosyVoice2-Yue manifest unavailable; lead playback remains available", error);
      return;
    }
    const leadEntry = manifest?.leadId ? manifest.articles?.[manifest.leadId] : null;
    if (leadEntry?.audio) primeAudio(entryUrl(leadEntry));
    scan(manifest);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.target instanceof Element) scan(manifest, mutation.target);
        for (const node of mutation.addedNodes) if (node instanceof Element) scan(manifest, node);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    [250, 750, 1500, 3000].forEach((delay) => setTimeout(() => scan(manifest), delay));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
