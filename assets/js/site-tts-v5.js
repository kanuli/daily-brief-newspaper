(() => {
  "use strict";

  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const STOP_TEXT = "■ 停止朗讀";
  const PENDING_TEXT = "⏳ F01 音訊準備中";
  const MANIFEST_URL = "data/tts-manifest.json";
  const LEAD_AUDIO_URL = "assets/audio/cosyvoice/latest-lead.wav";
  const MANIFEST_REFRESH_MS = 15000;
  const PAGE_CACHE_KEY = Date.now();

  let activeButton = null;
  let manifestPromise = null;
  let manifestData = null;
  let manifestKey = "";
  let manifestRefreshTimer = null;

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
        .site-tts-button:hover:not(:disabled){background:#111;color:#fff}.site-tts-button[data-speaking="true"]{background:#111;color:#fff}
        .site-tts-button:disabled{opacity:.58;cursor:default;background:#eee;color:#555}
        #site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}
        #site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}
      `;
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">CosyVoice2-Yue · F01 女聲</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="metadata" playsinline></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
      $("#site-tts-audio")?.addEventListener("ended", finishActive);
      $("#site-tts-audio")?.addEventListener("error", (event) => console.warn("CosyVoice2-Yue F01 audio element error", event));
    }
  }

  function setStatus(text, open = true) {
    ensureUi();
    $("#site-tts-player").dataset.open = open ? "true" : "false";
    $("#site-tts-status").textContent = text;
  }

  function resetButton(button) {
    if (!button) return;
    button.dataset.speaking = "false";
    button.textContent = BUTTON_TEXT;
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

  function leadUrl() {
    const url = new URL(LEAD_AUDIO_URL, document.baseURI);
    url.searchParams.set("v", String(PAGE_CACHE_KEY));
    return url.href;
  }

  function entryUrl(entry) {
    if (!entry?.audio) return null;
    const url = new URL(entry.audio, document.baseURI);
    url.searchParams.set("v", String(entry.bytes || entry.contentSha256 || manifestData?.generatedAt || PAGE_CACHE_KEY));
    return url.href;
  }

  function playAudioUrl(url, button = null) {
    if (!url) return false;
    if (activeButton === button && button?.dataset.speaking === "true") {
      stopAll();
      return true;
    }
    stopAll();
    ensureUi();
    const audio = $("#site-tts-audio");
    if (!audio) return false;
    audio.src = url;
    audio.dataset.ready = "true";
    audio.preload = "auto";
    activeButton = button;
    if (button) {
      button.dataset.speaking = "true";
      button.textContent = STOP_TEXT;
    }
    setStatus("使用中：CosyVoice2-Yue · F01 女聲");
    try {
      const promise = audio.play();
      if (promise && typeof promise.catch === "function") {
        promise.catch((error) => {
          console.warn("CosyVoice2-Yue F01 play rejected", error);
          finishActive();
        });
      }
      return true;
    } catch (error) {
      console.warn("CosyVoice2-Yue F01 play threw", error);
      finishActive();
      return false;
    }
  }

  function validateManifest(manifest) {
    if (manifest?.engine !== "ASLP-lab/Cosyvoice2-Yue") throw new Error("Unexpected TTS engine");
    if (manifest?.voice !== "F01 female reference") throw new Error("Unexpected TTS voice");
    if (manifest?.language !== "yue-HK") throw new Error("Unexpected TTS language");
    return manifest;
  }

  function keyForManifest(manifest) {
    return [
      manifest?.generatedAt || "",
      manifest?.availableArticleCount ?? manifest?.articleCount ?? Object.keys(manifest?.articles || {}).length,
      manifest?.pendingArticleCount ?? "",
      manifest?.sourceSetSha256 || ""
    ].join("|");
  }

  async function fetchManifest() {
    const response = await fetch(`${MANIFEST_URL}?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
    return validateManifest(await response.json());
  }

  function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = fetchManifest()
        .then((manifest) => {
          manifestData = manifest;
          manifestKey = keyForManifest(manifest);
          return manifest;
        })
        .catch((error) => {
          manifestPromise = null;
          console.warn("CosyVoice2-Yue F01 manifest unavailable", error);
          return null;
        });
    }
    return manifestPromise;
  }

  function articleTitle(article) {
    return clean($("h1,h2,h3", article)?.textContent);
  }

  function findEntry(manifest, article) {
    if (!manifest?.articles) return null;
    const title = articleTitle(article);
    if (!title) return null;
    return Object.values(manifest.articles).find((entry) => clean(entry?.title) === title) || null;
  }

  function configureButton(button, entry) {
    if (!button) return;
    button.onclick = null;
    button.dataset.speaking = "false";
    button.setAttribute("aria-label", "用 CosyVoice2-Yue F01 女聲朗讀這則新聞");

    if (entry?.audio) {
      button.textContent = BUTTON_TEXT;
      button.disabled = false;
      button.title = "CosyVoice2-Yue · F01 女聲已完成，可立即播放。";
      button.onclick = () => playAudioUrl(entryUrl(entry), button);
    } else {
      button.textContent = PENDING_TEXT;
      button.disabled = true;
      button.title = "只使用 CosyVoice2-Yue F01；此新聞的 F01 音訊尚未完成。";
    }
  }

  function addButton(article, manifest = manifestData) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE" || !article.closest("main")) return;
    if (article.dataset.siteTtsReady === "true" || article.closest(".study-desk,[data-no-tts]")) return;
    if (!articleTitle(article)) return;

    const entry = findEntry(manifest, article);
    article.dataset.siteTtsReady = "true";
    const wrap = document.createElement("div");
    wrap.className = "site-tts-controls";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "site-tts-button";
    configureButton(button, entry);

    wrap.appendChild(button);
    const heading = $("h1,h2,h3", article);
    if (heading?.nextSibling) heading.parentNode.insertBefore(wrap, heading.nextSibling);
    else article.prepend(wrap);
  }

  function scan(root = document, manifest = manifestData) {
    if (root instanceof Element) {
      if (root.matches("article")) addButton(root, manifest);
      const owner = root.closest("article");
      if (owner) addButton(owner, manifest);
      $$("article", root).forEach((article) => addButton(article, manifest));
      return;
    }
    $$("main article").forEach((article) => addButton(article, manifest));
  }

  function refreshButtons(manifest = manifestData) {
    $$("main article").forEach((article) => {
      if (article.closest(".study-desk,[data-no-tts]") || !articleTitle(article)) return;
      const button = $(".site-tts-button", article);
      if (!button) {
        article.dataset.siteTtsReady = "false";
        addButton(article, manifest);
        return;
      }
      if (button === activeButton && button.dataset.speaking === "true") return;
      configureButton(button, findEntry(manifest, article));
    });
  }

  async function refreshManifest() {
    try {
      const fresh = await fetchManifest();
      const nextKey = keyForManifest(fresh);
      const changed = nextKey !== manifestKey;
      manifestData = fresh;
      manifestKey = nextKey;
      manifestPromise = Promise.resolve(fresh);
      if (changed) refreshButtons(fresh);
    } catch (error) {
      console.warn("CosyVoice2-Yue F01 manifest refresh failed", error);
    }
  }

  function startManifestRefresh() {
    if (manifestRefreshTimer) window.clearInterval(manifestRefreshTimer);
    manifestRefreshTimer = window.setInterval(refreshManifest, MANIFEST_REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refreshManifest();
    });
  }

  window.SiteTTS = {
    playLeadFromUserGesture() { return playAudioUrl(leadUrl(), null); },
    stop: stopAll,
    isReady() { return true; }
  };

  async function boot() {
    ensureUi();
    // Controls appear immediately. Pending buttons are automatically upgraded as soon as a new F01 entry lands in the production manifest.
    scan(document, null);
    const manifest = await loadManifest();
    if (manifest) refreshButtons(manifest);
    startManifestRefresh();

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.target instanceof Element) scan(mutation.target, manifestData);
        for (const node of mutation.addedNodes) if (node instanceof Element) scan(node, manifestData);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    [250, 750, 1500, 3000].forEach((delay) => setTimeout(() => scan(document, manifestData), delay));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
