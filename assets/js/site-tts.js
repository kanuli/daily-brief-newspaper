(() => {
  "use strict";

  const SPACE_ID = "ASLP-lab/WenetSpeech-Yue-TTS";
  const F01_REFERENCE = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav";
  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const MAX_COSY_CHARS = 320;
  const GOOGLE_FEMALE_HINTS = [
    "standard-a", "standard-c", "achernar", "aoede", "autonoe", "callirrhoe", "despina",
    "erinome", "gacrux", "kore", "laomedeia", "leda", "pulcherrima", "sulafat",
    "vindemiatrix", "zephyr", "female", "woman", "女性", "女聲", "女声"
  ];
  const MICROSOFT_FEMALE_HINTS = ["hiumaan", "hiu maan", "hiugaai", "hiu gaai", "female", "女性", "女聲", "女声"];
  const MICROSOFT_MALE_HINTS = ["wanlung", "wan lung", "male", "男性", "男聲", "男声"];

  let gradioModulePromise = null;
  let activeSequence = 0;
  let activeButton = null;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function injectStyle() {
    if ($("#site-tts-style")) return;
    const style = document.createElement("style");
    style.id = "site-tts-style";
    style.textContent = `
      .site-tts-controls{display:flex;align-items:center;gap:8px;margin:10px 0 8px}
      .site-tts-button{appearance:none;border:1px solid #222;background:#fff;color:#111;padding:7px 10px;font:700 12px/1.2 "Noto Sans TC",sans-serif;cursor:pointer;border-radius:3px}
      .site-tts-button:hover{background:#111;color:#fff}.site-tts-button:disabled{opacity:.55;cursor:wait}
      #site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}
      #site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}
      @media(max-width:620px){.site-tts-controls{margin:8px 0}.site-tts-button{font-size:11px;padding:6px 8px}#site-tts-player{bottom:8px}}
    `;
    document.head.appendChild(style);
  }

  function ensurePlayer() {
    let panel = $("#site-tts-player");
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = "site-tts-player";
    panel.dataset.open = "false";
    panel.innerHTML = `
      <div class="site-tts-player-row">
        <div class="site-tts-status" id="site-tts-status">準備廣東話朗讀…</div>
        <button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button>
      </div>
      <audio class="site-tts-audio" id="site-tts-audio" controls preload="none"></audio>`;
    document.body.appendChild(panel);
    $("#site-tts-stop")?.addEventListener("click", stopAll);
    return panel;
  }

  function setStatus(message) {
    ensurePlayer().dataset.open = "true";
    const el = $("#site-tts-status");
    if (el) el.textContent = message;
  }

  function stopAll() {
    activeSequence += 1;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    const audio = $("#site-tts-audio");
    if (audio) {
      try { audio.pause(); } catch (_) {}
      audio.removeAttribute("src");
      audio.dataset.ready = "false";
      audio.load();
    }
    if (activeButton) {
      activeButton.disabled = false;
      activeButton.textContent = BUTTON_TEXT;
      activeButton = null;
    }
    setStatus("朗讀已停止。");
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function extractArticleText(article) {
    const clone = article.cloneNode(true);
    $$("button,a,figure,figcaption,.site-tts-controls,.story-meta,.tag,.eyebrow,.live-badge,.live-time,.source-link", clone).forEach((el) => el.remove());
    return normalizeText(clone.textContent).slice(0, 900);
  }

  function shouldEnhance(article) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE") return false;
    if (!article.closest("main")) return false;
    if (article.dataset.siteTtsReady === "true") return false;
    if (article.closest(".study-desk,[data-no-tts]")) return false;
    return extractArticleText(article).length >= 24;
  }

  function addButton(article) {
    if (!shouldEnhance(article)) return;
    article.dataset.siteTtsReady = "true";
    const controls = document.createElement("div");
    controls.className = "site-tts-controls";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "site-tts-button";
    button.textContent = BUTTON_TEXT;
    button.setAttribute("aria-label", "用廣東話朗讀這則新聞");
    button.addEventListener("click", () => speakArticle(article, button));
    controls.appendChild(button);
    const heading = $("h1,h2,h3", article);
    if (heading?.nextSibling) heading.parentNode.insertBefore(controls, heading.nextSibling);
    else article.prepend(controls);
  }

  function scanArticles(root = document) {
    if (root instanceof Element) {
      if (root.matches("article")) addButton(root);
      const ownerArticle = root.closest("article");
      if (ownerArticle) addButton(ownerArticle);
      $$("article", root).forEach(addButton);
      return;
    }
    $$("main article").forEach(addButton);
  }

  function normalizeLang(lang) {
    return String(lang || "").trim().toLowerCase().replaceAll("_", "-");
  }

  function isCantoneseVoice(voice) {
    const lang = normalizeLang(voice?.lang);
    const name = String(voice?.name || "").toLowerCase();
    return lang === "zh-hk" || lang === "yue" || lang.startsWith("yue-") || lang === "zh-yue" || /cantonese|hong\s*kong|廣東話|广东话|粵語|粤语/.test(name);
  }

  function includesAny(value, hints) {
    const text = String(value || "").toLowerCase();
    return hints.some((hint) => text.includes(hint));
  }

  async function getBrowserVoices() {
    if (!("speechSynthesis" in window)) return [];
    let voices = window.speechSynthesis.getVoices();
    if (voices.length) return voices;
    await Promise.race([
      new Promise((resolve) => window.speechSynthesis.addEventListener("voiceschanged", resolve, { once: true })),
      sleep(1200)
    ]);
    return window.speechSynthesis.getVoices();
  }

  function pickGoogleFemale(voices) {
    const candidates = voices.filter((voice) => isCantoneseVoice(voice) && String(voice.name || "").toLowerCase().includes("google"));
    if (!candidates.length) return null;
    return candidates.map((voice) => {
      const name = String(voice.name || "").toLowerCase();
      let score = 10;
      if (includesAny(name, GOOGLE_FEMALE_HINTS)) score += 100;
      if (normalizeLang(voice.lang).startsWith("yue-hk")) score += 30;
      if (normalizeLang(voice.lang) === "zh-hk") score += 20;
      if (/cantonese|粵語|粤语/.test(name)) score += 15;
      return { voice, score };
    }).sort((a, b) => b.score - a.score)[0].voice;
  }

  function pickMicrosoftFemale(voices) {
    const candidates = voices.filter((voice) => {
      const name = String(voice.name || "").toLowerCase();
      return isCantoneseVoice(voice) && name.includes("microsoft") && !includesAny(name, MICROSOFT_MALE_HINTS) && includesAny(name, MICROSOFT_FEMALE_HINTS);
    });
    if (!candidates.length) return null;
    return candidates.sort((a, b) => {
      const an = String(a.name || "").toLowerCase();
      const bn = String(b.name || "").toLowerCase();
      const as = an.includes("hiumaan") || an.includes("hiu maan") ? 20 : 10;
      const bs = bn.includes("hiumaan") || bn.includes("hiu maan") ? 20 : 10;
      return bs - as;
    })[0];
  }

  function speakWithBrowserVoice(voice, text, seq) {
    return new Promise((resolve, reject) => {
      if (!voice || !("speechSynthesis" in window)) return reject(new Error("Browser speech synthesis unavailable"));
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang || "zh-HK";
      utterance.rate = 1;
      utterance.pitch = 1;
      let started = false;
      const timer = setTimeout(() => {
        if (!started && seq === activeSequence) {
          window.speechSynthesis.cancel();
          reject(new Error(`${voice.name} did not start`));
        }
      }, 7000);
      utterance.onstart = () => { started = true; clearTimeout(timer); };
      utterance.onend = () => { clearTimeout(timer); resolve(voice); };
      utterance.onerror = (event) => { clearTimeout(timer); reject(new Error(event.error || `${voice.name} playback failed`)); };
      window.speechSynthesis.speak(utterance);
    });
  }

  async function browserFallback(text, seq) {
    const voices = await getBrowserVoices();
    const attempts = [
      { label: "Google Cantonese Female", voice: pickGoogleFemale(voices) },
      { label: "Microsoft Cantonese Female", voice: pickMicrosoftFemale(voices) }
    ];
    for (const attempt of attempts) {
      if (seq !== activeSequence) return false;
      if (!attempt.voice) continue;
      try {
        setStatus(`CosyVoice 不可用，改用 ${attempt.label}：${attempt.voice.name}`);
        await speakWithBrowserVoice(attempt.voice, text, seq);
        if (seq === activeSequence) setStatus(`朗讀完成：${attempt.voice.name}`);
        return true;
      } catch (error) {
        console.warn(`${attempt.label} failed`, error);
      }
    }
    return false;
  }

  function extractAudioUrl(value) {
    if (!value) return null;
    if (typeof value === "string") return value;
    if (typeof value.url === "string") return value.url;
    if (typeof value.path === "string" && /^https?:\/\//i.test(value.path)) return value.path;
    if (Array.isArray(value)) {
      for (const item of value) {
        const found = extractAudioUrl(item);
        if (found) return found;
      }
    }
    return null;
  }

  function withTimeout(promise, ms, label) {
    return Promise.race([
      promise,
      new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timeout`)), ms))
    ]);
  }

  async function getGradio() {
    if (!gradioModulePromise) gradioModulePromise = import("https://cdn.jsdelivr.net/npm/@gradio/client@2.5.0/dist/index.min.js");
    return gradioModulePromise;
  }

  async function generateCosy(text, seq) {
    const { Client, handle_file } = await getGradio();
    if (seq !== activeSequence) throw new Error("cancelled");
    const app = await withTimeout(Client.connect(SPACE_ID), 12000, "CosyVoice connect");
    const payload = ["CosyVoice2-Yue", text.slice(0, MAX_COSY_CHARS), "Custom Upload", handle_file(F01_REFERENCE)];
    let lastError;
    for (const endpoint of ["/tts_inference", "/predict"]) {
      try {
        const result = await withTimeout(app.predict(endpoint, payload), 30000, "CosyVoice generation");
        const url = extractAudioUrl(result?.data?.[0]);
        if (url) return url;
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("CosyVoice returned no audio");
  }

  async function playGeneratedAudio(url, seq) {
    const audio = $("#site-tts-audio");
    if (!audio || seq !== activeSequence) return;
    audio.src = url;
    audio.dataset.ready = "true";
    audio.load();
    try {
      await audio.play();
      setStatus("使用中：CosyVoice2-Yue-Databaker — Female");
    } catch (_) {
      setStatus("CosyVoice Female 已生成；如瀏覽器阻止自動播放，請按下方播放器。");
    }
  }

  async function speakArticle(article, button) {
    const text = extractArticleText(article);
    if (!text) return;
    stopAll();
    const seq = ++activeSequence;
    activeButton = button;
    button.disabled = true;
    button.textContent = "⏳ 準備朗讀…";
    setStatus("第 1 層：正在嘗試 CosyVoice2-Yue-Databaker — Female…");

    try {
      const url = await generateCosy(text, seq);
      if (seq !== activeSequence) return;
      await playGeneratedAudio(url, seq);
    } catch (error) {
      if (seq !== activeSequence) return;
      console.warn("CosyVoice failed", error);
      setStatus("CosyVoice 失敗，正在依次嘗試 Google Female → Microsoft Female…");
      const ok = await browserFallback(text, seq);
      if (!ok && seq === activeSequence) setStatus("三層均不可用：CosyVoice、Google Cantonese、Microsoft Cantonese Female 都未能播放。");
    } finally {
      if (seq === activeSequence) {
        button.disabled = false;
        button.textContent = BUTTON_TEXT;
        activeButton = null;
      }
    }
  }

  function boot() {
    injectStyle();
    ensurePlayer();
    scanArticles();

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.target instanceof Element) scanArticles(mutation.target);
        for (const node of mutation.addedNodes) {
          if (node instanceof Element) scanArticles(node);
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });

    [250, 750, 1500, 3000].forEach((delay) => setTimeout(() => scanArticles(), delay));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
