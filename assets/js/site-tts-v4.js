(() => {
  "use strict";

  const BUTTON_TEXT = "🔊 廣東話朗讀";
  const F01_REFERENCE = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav";
  const CANTONESE_INSTRUCT = "You are a helpful assistant. 请用广东话表达。<|endofprompt|>";
  const REFERENCE_SECONDS = 6;
  const TARGET_RATE = 16000;
  const MAX_COSY_CHARS = 260;
  const TITLE_PAUSE_MS = 800;
  const SUBTITLE_PAUSE_MS = 650;
  const BODY_PAUSE_MS = 260;

  const REGULAR_BACKENDS = [
    {
      id: "Originalmmd/CosyVoice3-VoiceStudio",
      label: "CosyVoice3 Regular CPU · Instruct",
      mode: "instruct",
      timeoutMs: 180000
    },
    {
      id: "recentechstudio/CosyVoice3",
      label: "CosyVoice3 Regular Runtime · F01",
      mode: "zero-shot",
      timeoutMs: 150000
    }
  ];

  const GOOGLE_HINTS = ["standard-a", "standard-c", "female", "woman", "女性", "女聲", "女声"];
  const MS_FEMALE_HINTS = ["hiumaan", "hiu maan", "hiugaai", "hiu gaai", "female", "女性", "女聲", "女声"];
  const MS_MALE_HINTS = ["wanlung", "wan lung", "male", "男性", "男聲", "男声"];

  let activeSequence = 0;
  let activeButton = null;
  let activeSubmission = null;
  let gradioPromise = null;
  let referencePromise = null;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
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
    if (activeSubmission?.cancel) {
      try { activeSubmission.cancel(); } catch (_) {}
    }
    activeSubmission = null;
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

  function articleSegments(article) {
    const title = clean($("h1,h2,h3", article)?.textContent);
    const subtitle = clean($(".lead-deck,.dek,.subtitle,.sub-title,.story-deck", article)?.textContent);
    const ignored = new Set();
    $$("button,a,figure,figcaption,.site-tts-controls,.story-meta,.tag,.eyebrow,.live-badge,.live-time,.source-link,.why-box,.why-mini", article).forEach((node) => ignored.add(node));

    const body = [];
    $$(".story-body p,p", article).forEach((p) => {
      if ([...ignored].some((node) => node === p || node.contains?.(p))) return;
      if (p.matches(".lead-deck,.dek,.subtitle,.sub-title,.story-deck,.why-mini")) return;
      const text = clean(p.textContent);
      if (!text || text === subtitle || text === title || body.includes(text)) return;
      body.push(text);
    });

    const parts = [];
    if (title) parts.push({ kind: "title", text: title });
    if (subtitle && subtitle !== title) parts.push({ kind: "subtitle", text: subtitle });
    for (const text of body) parts.push({ kind: "body", text });
    return parts.slice(0, 8);
  }

  function punctuate(text) {
    const value = clean(text);
    if (!value) return "";
    return /[。！？!?…]$/.test(value) ? value : `${value}。`;
  }

  function cosyText(segments) {
    return segments.map((part) => {
      const sentence = punctuate(part.text);
      if (!sentence) return "";
      if (part.kind === "title" || part.kind === "subtitle") return `${sentence}……`;
      return sentence;
    }).filter(Boolean).join("\n\n").slice(0, MAX_COSY_CHARS);
  }

  function addButton(article) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE" || !article.closest("main")) return;
    if (article.dataset.siteTtsReady === "true" || article.closest(".study-desk,[data-no-tts]")) return;
    if (articleSegments(article).reduce((n, part) => n + part.text.length, 0) < 24) return;
    article.dataset.siteTtsReady = "true";
    const wrap = document.createElement("div");
    wrap.className = "site-tts-controls";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "site-tts-button";
    button.textContent = BUTTON_TEXT;
    button.setAttribute("aria-label", "用廣東話朗讀這則新聞");
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
      return;
    }
    $$("main article").forEach(addButton);
  }

  function encodeWav(samples, rate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const write = (offset, text) => { for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i)); };
    write(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); write(8, "WAVE"); write(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, samples.length * 2, true);
    let offset = 44;
    for (const sample of samples) {
      const s = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
    return new Blob([buffer], { type: "audio/wav" });
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
      for (let i = 0; i < targetFrames; i += 1) {
        const pos = i * decoded.sampleRate / TARGET_RATE;
        const a = Math.min(sourceFrames - 1, Math.floor(pos));
        const b = Math.min(sourceFrames - 1, a + 1);
        const f = pos - a;
        out[i] = source[a] * (1 - f) + source[b] * f;
      }
      return encodeWav(out, TARGET_RATE);
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
    if (typeof value === "string" && /^https?:\/\//i.test(value)) return value;
    if (typeof value?.url === "string") return value.url;
    if (typeof value?.path === "string" && /^https?:\/\//i.test(value.path)) return value.path;
    if (Array.isArray(value)) {
      for (const item of value) {
        const found = extractAudioUrl(item);
        if (found) return found;
      }
    } else if (typeof value === "object") {
      for (const item of Object.values(value)) {
        const found = extractAudioUrl(item);
        if (found) return found;
      }
    }
    return null;
  }

  function allEndpoints(api) {
    const result = [];
    for (const [key, info] of Object.entries(api?.named_endpoints || {})) result.push({ key, info, named: true });
    for (const [key, info] of Object.entries(api?.unnamed_endpoints || {})) result.push({ key, info, named: false });
    return result;
  }

  function endpointLabels(endpoint) {
    return (endpoint?.info?.parameters || []).map((p) => clean(p?.label).toLowerCase());
  }

  function resolveEndpoint(api, mode) {
    const endpoints = allEndpoints(api);
    if (!endpoints.length) throw new Error("CosyVoice API exposes no callable endpoint");
    const scored = endpoints.map((endpoint) => {
      const labels = endpointLabels(endpoint);
      let score = 0;
      if (labels.some((x) => x.includes("text to synthesize") || x === "text" || x.includes("text to speak"))) score += 30;
      if (labels.some((x) => x.includes("reference audio") || x.includes("voice sample"))) score += 30;
      if (mode === "instruct" && labels.some((x) => x.includes("instruction"))) score += 80;
      if (mode === "instruct" && labels.some((x) => x.includes("prompt text"))) score -= 10;
      if (mode === "zero-shot" && labels.length === 2) score += 30;
      return { ...endpoint, score };
    }).sort((a, b) => b.score - a.score);
    if (scored[0].score < 40) throw new Error(`No suitable ${mode} CosyVoice endpoint found`);
    return scored[0];
  }

  function endpointKey(endpoint) {
    if (endpoint.named) return endpoint.key;
    return /^\d+$/.test(endpoint.key) ? Number(endpoint.key) : endpoint.key;
  }

  function endpointPayload(endpoint, backend, text, reference, handle_file) {
    const params = endpoint.info?.parameters || [];
    return params.map((param) => {
      const label = clean(param?.label).toLowerCase();
      if (label.includes("text to synthesize") || label === "text" || label.includes("text to speak")) return text;
      if (label.includes("instruction")) return CANTONESE_INSTRUCT;
      if (label.includes("reference audio") || label.includes("voice sample")) return handle_file(reference);
      if (label.includes("prompt text")) return "";
      if (label.includes("speed")) return 0.96;
      if (label.includes("seed")) return 42;
      if (label.includes("stream")) return false;
      return param?.example_input ?? param?.default ?? null;
    });
  }

  async function runRegularBackend(backend, text, reference, seq) {
    const { Client, handle_file } = await getGradio();
    let spaceState = "connecting";
    setStatus(`第 1 層：連接 ${backend.label}…`);
    const app = await Client.connect(backend.id, {
      events: ["data", "status"],
      status_callback: (status) => { spaceState = status?.status || spaceState; }
    });
    if (seq !== activeSequence) throw new Error("cancelled");
    if (["space_error", "error", "stopped"].includes(spaceState)) throw new Error(`${backend.label} unavailable`);

    setStatus(`${backend.label}：讀取 live API schema…`);
    const api = await app.view_api();
    const endpoint = resolveEndpoint(api, backend.mode);
    const payload = endpointPayload(endpoint, backend, text, reference, handle_file);
    const submission = app.submit(endpointKey(endpoint), payload);
    activeSubmission = submission;

    let resultUrl = null;
    let serverMessage = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try { submission.cancel(); } catch (_) {}
    }, backend.timeoutMs);

    try {
      for await (const msg of submission) {
        if (seq !== activeSequence) {
          try { submission.cancel(); } catch (_) {}
          throw new Error("cancelled");
        }
        if (msg.type === "status") {
          if (msg.stage === "error") throw new Error(msg.message || `${backend.label} server error`);
          if (msg.stage === "pending") setStatus(`${backend.label} 正在排隊／喚醒 server…`);
          if (msg.stage === "generating") setStatus(`${backend.label} 正在生成 F01 女聲廣東話…`);
        }
        if (msg.type === "data") {
          resultUrl = extractAudioUrl(msg.data) || resultUrl;
          const strings = Array.isArray(msg.data) ? msg.data.filter((x) => typeof x === "string") : [];
          if (strings.length) serverMessage = strings.join(" ");
        }
      }
    } finally {
      clearTimeout(timer);
      if (activeSubmission === submission) activeSubmission = null;
    }

    if (timedOut) throw new Error(`${backend.label} timeout`);
    if (!resultUrl) throw new Error(serverMessage || `${backend.label} returned no audio`);
    return { url: resultUrl, label: backend.label };
  }

  async function generateCosy(segments, seq) {
    const text = cosyText(segments);
    if (!text) throw new Error("No readable text");
    setStatus("第 1 層：準備 F01 女聲 reference…");
    const reference = await getReference();
    let lastError = null;
    for (let i = 0; i < REGULAR_BACKENDS.length; i += 1) {
      const backend = REGULAR_BACKENDS[i];
      try {
        return await runRegularBackend(backend, text, reference, seq);
      } catch (error) {
        if (seq !== activeSequence || error?.message === "cancelled") throw error;
        lastError = error;
        console.warn(`${backend.label} failed`, error);
        if (i + 1 < REGULAR_BACKENDS.length) setStatus(`${backend.label} 未能完成，轉用另一個非 ZeroGPU CosyVoice server…`);
      }
    }
    throw lastError || new Error("Regular CosyVoice backends unavailable");
  }

  function normalizeLang(lang) { return String(lang || "").toLowerCase().replaceAll("_", "-"); }
  function isCantonese(voice) {
    const lang = normalizeLang(voice?.lang);
    const name = String(voice?.name || "").toLowerCase();
    return lang === "zh-hk" || lang === "yue" || lang.startsWith("yue-") || /cantonese|hong\s*kong|廣東話|广东话|粵語|粤语/.test(name);
  }
  function includesAny(value, hints) { const text = String(value || "").toLowerCase(); return hints.some((hint) => text.includes(hint)); }

  async function browserVoices() {
    if (!("speechSynthesis" in window)) return [];
    let list = speechSynthesis.getVoices();
    if (list.length) return list;
    await Promise.race([new Promise((resolve) => speechSynthesis.addEventListener("voiceschanged", resolve, { once: true })), sleep(1500)]);
    return speechSynthesis.getVoices();
  }

  function googleFemale(list) {
    const candidates = list.filter((voice) => isCantonese(voice) && String(voice.name || "").toLowerCase().includes("google"));
    return candidates.sort((a, b) => Number(includesAny(b.name, GOOGLE_HINTS)) - Number(includesAny(a.name, GOOGLE_HINTS)))[0] || null;
  }

  function microsoftFemale(list) {
    return list.find((voice) => {
      const name = String(voice.name || "").toLowerCase();
      return isCantonese(voice) && name.includes("microsoft") && !includesAny(name, MS_MALE_HINTS) && includesAny(name, MS_FEMALE_HINTS);
    }) || null;
  }

  function speakOne(voice, text, seq) {
    return new Promise((resolve, reject) => {
      if (!voice || !("speechSynthesis" in window)) return reject(new Error("browser speech unavailable"));
      if (seq !== activeSequence) return reject(new Error("cancelled"));
      const utterance = new SpeechSynthesisUtterance(punctuate(text));
      utterance.voice = voice;
      utterance.lang = voice.lang || "zh-HK";
      utterance.rate = 0.96;
      utterance.pitch = 1;
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

  async function speakBrowserSegments(voice, segments, seq) {
    speechSynthesis.cancel();
    for (let i = 0; i < segments.length; i += 1) {
      if (seq !== activeSequence) throw new Error("cancelled");
      const segment = segments[i];
      await speakOne(voice, segment.text, seq);
      if (segment.kind === "title") await sleep(TITLE_PAUSE_MS);
      else if (segment.kind === "subtitle") await sleep(SUBTITLE_PAUSE_MS);
      else if (i < segments.length - 1) await sleep(BODY_PAUSE_MS);
    }
  }

  async function fallback(segments, seq) {
    const list = await browserVoices();
    for (const item of [
      { label: "Google Cantonese Female", voice: googleFemale(list) },
      { label: "Microsoft Cantonese Female", voice: microsoftFemale(list) }
    ]) {
      if (!item.voice || seq !== activeSequence) continue;
      try {
        setStatus(`CosyVoice regular server 暫時不可用，改用 ${item.label}：${item.voice.name}`);
        await speakBrowserSegments(item.voice, segments, seq);
        if (seq === activeSequence) setStatus(`朗讀完成：${item.voice.name}`);
        return true;
      } catch (error) {
        if (error?.message === "cancelled") return false;
        console.warn(item.label, error);
      }
    }
    return false;
  }

  async function speakArticle(article, button) {
    const segments = articleSegments(article);
    if (!segments.length) return;
    stopAll();
    const seq = ++activeSequence;
    activeButton = button;
    button.disabled = true;
    button.textContent = "⏳ 準備朗讀…";
    try {
      const generated = await generateCosy(segments, seq);
      if (seq !== activeSequence) return;
      const audio = $("#site-tts-audio");
      audio.src = generated.url;
      audio.dataset.ready = "true";
      audio.load();
      try {
        await audio.play();
        setStatus(`使用中：${generated.label} · F01 Female`);
      } catch (_) {
        setStatus(`${generated.label} 已生成；如未自動播放，請按播放器開始。`);
      }
    } catch (error) {
      if (seq !== activeSequence) return;
      console.warn("All regular CosyVoice backends failed", error);
      setStatus("非 ZeroGPU CosyVoice server 未能完成，依次嘗試 Google Female → Microsoft Female…");
      const ok = await fallback(segments, seq);
      if (!ok && seq === activeSequence) setStatus("所有聲線均不可用：CosyVoice、Google Cantonese、Microsoft Cantonese Female 都未能播放。");
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