(() => {
  "use strict";

  const SPACE_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B";
  const F01_REFERENCE = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav";
  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const MAX_COSY_CHARS = 180;
  const REFERENCE_SECONDS = 8;
  const TARGET_RATE = 16000;
  const GOOGLE_HINTS = ["standard-a", "standard-c", "female", "woman", "女性", "女聲", "女声"];
  const MS_FEMALE_HINTS = ["hiumaan", "hiu maan", "hiugaai", "hiu gaai", "female", "女性", "女聲", "女声"];
  const MS_MALE_HINTS = ["wanlung", "wan lung", "male", "男性", "男聲", "男声"];

  let activeSequence = 0;
  let activeButton = null;
  let gradioPromise = null;
  let referencePromise = null;

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function ensureUi() {
    if (!$("#site-tts-style")) {
      const style = document.createElement("style");
      style.id = "site-tts-style";
      style.textContent = '.site-tts-controls{display:flex;gap:8px;margin:10px 0}.site-tts-button{border:1px solid #222;background:#fff;color:#111;padding:7px 10px;font:700 12px/1.2 "Noto Sans TC",sans-serif;cursor:pointer;border-radius:3px}.site-tts-button:hover{background:#111;color:#fff}.site-tts-button:disabled{opacity:.55;cursor:wait}#site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}#site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}';
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">準備廣東話朗讀…</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="none"></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
    }
  }

  function setStatus(text) {
    ensureUi();
    $("#site-tts-player").dataset.open = "true";
    $("#site-tts-status").textContent = text;
  }

  function stopAll() {
    activeSequence += 1;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
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

  function articleText(article) {
    const clone = article.cloneNode(true);
    $$("button,a,figure,figcaption,.site-tts-controls,.story-meta,.tag,.eyebrow,.live-badge,.live-time,.source-link", clone).forEach((el) => el.remove());
    return String(clone.textContent || "").replace(/\s+/g, " ").trim().slice(0, 900);
  }

  function addButton(article) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE" || !article.closest("main")) return;
    if (article.dataset.siteTtsReady === "true" || article.closest(".study-desk,[data-no-tts]")) return;
    if (articleText(article).length < 24) return;
    article.dataset.siteTtsReady = "true";
    const wrap = document.createElement("div");
    wrap.className = "site-tts-controls";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "site-tts-button";
    button.textContent = BUTTON_TEXT;
    button.addEventListener("click", () => speakArticle(article, button));
    wrap.appendChild(button);
    const heading = $("h1,h2,h3", article);
    if (heading?.nextSibling) heading.parentNode.insertBefore(wrap, heading.nextSibling);
    else article.prepend(wrap);
  }

  function scan(root = document) {
    if (root instanceof Element) {
      if (root.matches("article")) addButton(root);
      const owner = root.closest("article");
      if (owner) addButton(owner);
      $$("article", root).forEach(addButton);
    } else {
      $$("main article").forEach(addButton);
    }
  }

  function encodeWav(samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buf);
    const write = (offset, text) => { for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i)); };
    write(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); write(8, "WAVE"); write(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, samples.length * 2, true);
    let offset = 44;
    for (const sample of samples) {
      const s = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
    return new Blob([buf], { type: "audio/wav" });
  }

  async function buildReference() {
    const response = await fetch(F01_REFERENCE, { cache: "force-cache" });
    if (!response.ok) throw new Error(`F01 reference HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) throw new Error("Web Audio API unavailable");
    const ctx = new AudioCtx();
    try {
      const decoded = await ctx.decodeAudioData(bytes.slice(0));
      const source = decoded.getChannelData(0);
      const sourceFrames = Math.min(source.length, Math.floor(decoded.sampleRate * REFERENCE_SECONDS));
      const targetFrames = Math.max(1, Math.floor(sourceFrames * TARGET_RATE / decoded.sampleRate));
      const out = new Float32Array(targetFrames);
      for (let i = 0; i < targetFrames; i++) {
        const pos = i * decoded.sampleRate / TARGET_RATE;
        const a = Math.min(sourceFrames - 1, Math.floor(pos));
        const b = Math.min(sourceFrames - 1, a + 1);
        const f = pos - a;
        out[i] = source[a] * (1 - f) + source[b] * f;
      }
      return new File([encodeWav(out, TARGET_RATE)], "F01_female_8s_16k.wav", { type: "audio/wav" });
    } finally {
      try { await ctx.close(); } catch (_) {}
    }
  }

  function getReference() {
    if (!referencePromise) referencePromise = buildReference().catch((error) => { referencePromise = null; throw error; });
    return referencePromise;
  }

  function getGradio() {
    if (!gradioPromise) gradioPromise = import("https://cdn.jsdelivr.net/npm/@gradio/client@2.5.0/dist/index.min.js");
    return gradioPromise;
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

  function timeout(promise, ms, label) {
    return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timeout`)), ms))]);
  }

  async function generateCosy(text, seq) {
    setStatus("第 1 層：準備 F01 女聲 reference…");
    const reference = await getReference();
    if (seq !== activeSequence) throw new Error("cancelled");
    const { Client, handle_file } = await getGradio();
    setStatus("第 1 層：連接官方 CosyVoice ZeroGPU…");
    const app = await timeout(Client.connect(SPACE_ID), 45000, "CosyVoice connect");
    if (seq !== activeSequence) throw new Error("cancelled");
    const payload = [text.slice(0, MAX_COSY_CHARS), "instruct", "", handle_file(reference), null, "用粤语说这句话", 42, false, "Zh"];
    const result = await timeout(app.predict("/generate_audio", payload), 90000, "CosyVoice generation");
    const url = extractAudioUrl(result?.data?.[0]);
    if (!url) throw new Error("CosyVoice returned no audio URL");
    return url;
  }

  function normalizeLang(lang) { return String(lang || "").toLowerCase().replaceAll("_", "-"); }
  function isCantonese(voice) {
    const lang = normalizeLang(voice?.lang);
    const name = String(voice?.name || "").toLowerCase();
    return lang === "zh-hk" || lang === "yue" || lang.startsWith("yue-") || /cantonese|hong\s*kong|廣東話|粵語|粤语/.test(name);
  }
  function includesAny(value, hints) { const text = String(value || "").toLowerCase(); return hints.some((hint) => text.includes(hint)); }

  async function voices() {
    if (!("speechSynthesis" in window)) return [];
    let list = speechSynthesis.getVoices();
    if (list.length) return list;
    await Promise.race([new Promise((resolve) => speechSynthesis.addEventListener("voiceschanged", resolve, { once: true })), sleep(1200)]);
    return speechSynthesis.getVoices();
  }

  function googleFemale(list) {
    const candidates = list.filter((v) => isCantonese(v) && String(v.name || "").toLowerCase().includes("google"));
    return candidates.sort((a, b) => Number(includesAny(b.name, GOOGLE_HINTS)) - Number(includesAny(a.name, GOOGLE_HINTS)))[0] || null;
  }
  function microsoftFemale(list) {
    return list.find((v) => {
      const name = String(v.name || "").toLowerCase();
      return isCantonese(v) && name.includes("microsoft") && !includesAny(name, MS_MALE_HINTS) && includesAny(name, MS_FEMALE_HINTS);
    }) || null;
  }

  function speakBrowser(voice, text, seq) {
    return new Promise((resolve, reject) => {
      if (!voice || !("speechSynthesis" in window)) return reject(new Error("browser speech unavailable"));
      speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang || "zh-HK";
      let started = false;
      const timer = setTimeout(() => {
        if (!started && seq === activeSequence) {
          speechSynthesis.cancel();
          reject(new Error("voice start timeout"));
        }
      }, 7000);
      utterance.onstart = () => { started = true; clearTimeout(timer); };
      utterance.onend = () => { clearTimeout(timer); resolve(); };
      utterance.onerror = (event) => { clearTimeout(timer); reject(new Error(event.error || "voice failed")); };
      speechSynthesis.speak(utterance);
    });
  }

  async function fallback(text, seq) {
    const list = await voices();
    for (const item of [
      { label: "Google Cantonese Female", voice: googleFemale(list) },
      { label: "Microsoft Cantonese Female", voice: microsoftFemale(list) }
    ]) {
      if (!item.voice || seq !== activeSequence) continue;
      try {
        setStatus(`CosyVoice 暫時不可用，改用 ${item.label}：${item.voice.name}`);
        await speakBrowser(item.voice, text, seq);
        if (seq === activeSequence) setStatus(`朗讀完成：${item.voice.name}`);
        return true;
      } catch (error) {
        console.warn(item.label, error);
      }
    }
    return false;
  }

  async function speakArticle(article, button) {
    const text = articleText(article);
    if (!text) return;
    stopAll();
    const seq = ++activeSequence;
    activeButton = button;
    button.disabled = true;
    button.textContent = "⏳ 準備朗讀…";
    try {
      const url = await generateCosy(text, seq);
      if (seq !== activeSequence) return;
      const audio = $("#site-tts-audio");
      audio.src = url;
      audio.dataset.ready = "true";
      audio.load();
      try {
        await audio.play();
        setStatus("使用中：CosyVoice · F01 Female");
      } catch (_) {
        setStatus("CosyVoice · F01 Female 已生成；請按播放器開始。");
      }
    } catch (error) {
      if (seq !== activeSequence) return;
      console.warn("CosyVoice failed", error);
      setStatus("CosyVoice 失敗，依次嘗試 Google Female → Microsoft Female…");
      const ok = await fallback(text, seq);
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
    ensureUi();
    scan();
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.target instanceof Element) scan(mutation.target);
        for (const node of mutation.addedNodes) if (node instanceof Element) scan(node);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    [250, 750, 1500, 3000].forEach((delay) => setTimeout(() => scan(), delay));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
