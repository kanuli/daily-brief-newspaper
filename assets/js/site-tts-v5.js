(() => {
  "use strict";

  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const STOP_TEXT = "■ 停止朗讀";
  const MANIFEST_URL = "data/tts-manifest.json";
  const LEAD_AUDIO_URL = "assets/audio/cosyvoice/latest-lead.wav";
  const PAGE_CACHE_KEY = Date.now();
  const MAX_SPEECH_CHARS = 150;

  let activeButton = null;
  let activeMode = null;
  let speechToken = 0;
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
        .site-tts-button:hover{background:#111;color:#fff}.site-tts-button[data-speaking="true"]{background:#111;color:#fff}
        #site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}
        #site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}
      `;
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">廣東話新聞朗讀</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="auto" playsinline></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
      $("#site-tts-audio")?.addEventListener("ended", finishActive);
      $("#site-tts-audio")?.addEventListener("error", (event) => console.warn("Cantonese audio element error", event));
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
    activeMode = null;
    setStatus("朗讀完成。", false);
  }

  function stopAll() {
    speechToken += 1;
    if ("speechSynthesis" in window) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
    }
    const audio = $("#site-tts-audio");
    if (audio) {
      try { audio.pause(); } catch (_) {}
      try { audio.currentTime = 0; } catch (_) {}
    }
    resetButton(activeButton);
    activeButton = null;
    activeMode = null;
    setStatus("朗讀已停止。", false);
  }

  function activateButton(button, mode) {
    if (activeButton && activeButton !== button) resetButton(activeButton);
    activeButton = button || null;
    activeMode = mode;
    if (button) {
      button.dataset.speaking = "true";
      button.textContent = STOP_TEXT;
    }
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
    } else {
      audio.dataset.ready = "true";
    }
    return audio;
  }

  function playAudioUrl(url, button = null) {
    if (!url) return false;
    if (activeButton === button && activeMode === "audio") {
      stopAll();
      return true;
    }
    stopAll();
    const audio = primeAudio(url);
    if (!audio) return false;
    activateButton(button, "audio");
    setStatus("使用中：CosyVoice2-Yue · F01 女聲");
    try {
      const promise = audio.play();
      if (promise && typeof promise.catch === "function") {
        promise.catch((error) => {
          console.warn("CosyVoice2-Yue play rejected", error);
          finishActive();
        });
      }
      return true;
    } catch (error) {
      console.warn("CosyVoice2-Yue play threw", error);
      finishActive();
      return false;
    }
  }

  function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = fetch(`${MANIFEST_URL}?v=${Date.now()}`, { cache: "no-store" })
        .then(async (response) => {
          if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
          const manifest = await response.json();
          if (manifest?.engine !== "ASLP-lab/Cosyvoice2-Yue") throw new Error("Unexpected TTS engine");
          manifestData = manifest;
          return manifest;
        })
        .catch((error) => {
          manifestPromise = null;
          manifestData = null;
          console.warn("CosyVoice manifest unavailable; device Cantonese remains available", error);
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

  function articleSpeechText(article) {
    const title = articleTitle(article);
    const paragraphs = $$("p", article)
      .filter((node) => !node.closest(".site-tts-controls,.article-sources,.source-link,[data-no-tts]"))
      .map((node) => clean(node.textContent))
      .filter(Boolean);
    return clean([title, ...paragraphs].filter(Boolean).join("。"));
  }

  function chunkSpeech(text) {
    const sentences = String(text || "").match(/[^。！？!?]+[。！？!?]?/g) || [];
    const chunks = [];
    let current = "";
    for (const raw of sentences) {
      const sentence = clean(raw);
      if (!sentence) continue;
      if (current && current.length + sentence.length > MAX_SPEECH_CHARS) {
        chunks.push(current);
        current = "";
      }
      if (sentence.length > MAX_SPEECH_CHARS) {
        if (current) { chunks.push(current); current = ""; }
        for (let i = 0; i < sentence.length; i += MAX_SPEECH_CHARS) chunks.push(sentence.slice(i, i + MAX_SPEECH_CHARS));
      } else {
        current += sentence;
      }
    }
    if (current) chunks.push(current);
    return chunks;
  }

  function cantoneseVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices?.() || [];
    return voices.find((voice) => /^zh[-_]HK$/i.test(voice.lang || ""))
      || voices.find((voice) => /^yue(?:[-_]|$)/i.test(voice.lang || ""))
      || voices.find((voice) => /cantonese|hong kong|sin-ji|善怡/i.test(`${voice.name || ""} ${voice.lang || ""}`))
      || null;
  }

  function playDeviceCantonese(article, button) {
    if (!("speechSynthesis" in window)) return false;
    if (activeButton === button && activeMode === "speech") {
      stopAll();
      return true;
    }
    const text = articleSpeechText(article);
    const chunks = chunkSpeech(text);
    if (!chunks.length) return false;

    stopAll();
    const myToken = ++speechToken;
    const voice = cantoneseVoice();
    const audio = $("#site-tts-audio");
    if (audio) audio.dataset.ready = "false";
    activateButton(button, "speech");
    setStatus("廣東話朗讀中");

    let index = 0;
    const speakNext = () => {
      if (myToken !== speechToken) return;
      if (index >= chunks.length) {
        finishActive();
        return;
      }
      const utterance = new SpeechSynthesisUtterance(chunks[index++]);
      utterance.lang = "zh-HK";
      if (voice) utterance.voice = voice;
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.onend = speakNext;
      utterance.onerror = (event) => {
        if (myToken !== speechToken) return;
        console.warn("Device Cantonese speech error", event);
        finishActive();
      };
      window.speechSynthesis.speak(utterance);
    };
    speakNext();
    return true;
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
    button.textContent = BUTTON_TEXT;
    button.setAttribute("aria-label", "用廣東話朗讀這則新聞");
    button.addEventListener("click", () => {
      if (entry?.audio) playAudioUrl(entryUrl(entry), button);
      else playDeviceCantonese(article, button);
    });
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

  window.SiteTTS = {
    playLeadFromUserGesture() {
      return playAudioUrl(leadUrl(), null);
    },
    stop: stopAll,
    isReady() { return true; }
  };

  async function boot() {
    ensureUi();
    primeAudio(leadUrl());

    // Buttons must exist for every story even before/without the pre-generated manifest.
    scan(document, null);
    const manifest = await loadManifest();
    if (manifest) {
      // Rebuild controls so any pre-generated CosyVoice entry takes priority.
      $$("main article[data-site-tts-ready='true']").forEach((article) => {
        article.dataset.siteTtsReady = "false";
        $(".site-tts-controls", article)?.remove();
      });
      scan(document, manifest);
    }

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
