(() => {
  const VOICE_KEY = "dailyBrief.cantoneseVoice";
  const RATE_KEY = "dailyBrief.cantoneseRate";
  const SHERPA_DIR = "https://huggingface.co/datasets/jiangzhuo9357/sherpa-onnx-tts-models/resolve/main/wasm-cantonese/";
  const sample = document.getElementById("voice-sample");
  const rate = document.getElementById("voice-rate");
  const list = document.getElementById("system-voice-list");
  const status = document.getElementById("system-status");
  const current = document.getElementById("current-voice");
  const currentNote = document.getElementById("current-voice-note");
  const player = document.getElementById("sherpa-player");
  const sherpaStatus = document.getElementById("sherpa-status");
  const loadSherpaBtn = document.getElementById("load-sherpa");
  const playSherpaBtn = document.getElementById("play-sherpa");
  const selectSherpaBtn = document.getElementById("select-sherpa");
  let cantoneseVoices = [];
  let selected = readChoice();
  let sherpaLoading = false;
  let sherpaReady = false;
  let sherpaInitTimer = null;

  function readChoice() {
    try { return JSON.parse(localStorage.getItem(VOICE_KEY) || "null"); }
    catch (_) { return null; }
  }

  function saveChoice(choice) {
    selected = choice;
    localStorage.setItem(VOICE_KEY, JSON.stringify(choice));
    renderCurrentChoice();
    renderSystemVoices();
  }

  function savedRate() {
    const value = localStorage.getItem(RATE_KEY);
    return ["0.8", "1", "1.2", "1.5"].includes(value) ? value : "1";
  }

  rate.value = savedRate();
  rate.addEventListener("change", () => localStorage.setItem(RATE_KEY, rate.value));

  function getText() {
    return sample.value.trim();
  }

  function stopAll() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (player) {
      player.pause();
      player.currentTime = 0;
    }
  }

  document.getElementById("stop-all").addEventListener("click", stopAll);

  function isCantoneseVoice(voice) {
    const lang = String(voice.lang || "").toLowerCase().replace("_", "-");
    const name = String(voice.name || "").toLowerCase();
    return lang === "zh-hk" || lang.startsWith("yue") ||
      /(cantonese|hong kong|hongkong|sin[- ]?ji|sinji|aasing|tracy|danny|hiu|wanlung|粵語|粤语|廣東話|广东话)/i.test(name);
  }

  function providerFor(voice) {
    const name = String(voice.name || "").toLowerCase();
    if (/(microsoft|tracy|danny)/.test(name)) return "Microsoft / Windows";
    if (/(apple|siri|sin[- ]?ji|sinji|aasing)/.test(name)) return "Apple / System";
    if (/google/.test(name)) return "Google / Browser";
    return voice.localService ? "System / Local" : "Browser / Remote voice";
  }

  function voiceId(voice) {
    return voice.voiceURI || `${voice.name}|${voice.lang}`;
  }

  function playWebVoice(voice) {
    const text = getText();
    if (!text) return;
    stopAll();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = voice.lang || "zh-HK";
    utterance.rate = Number(rate.value) || 1;
    window.speechSynthesis.speak(utterance);
  }

  function createButton(text, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = text;
    button.addEventListener("click", onClick);
    return button;
  }

  function renderSystemVoices() {
    if (!list) return;
    list.replaceChildren();
    if (!("speechSynthesis" in window)) {
      status.textContent = "呢個瀏覽器唔支援 Web Speech API；你仍然可以試下面嘅 browser-local 開源聲線。";
      status.className = "voice-status voice-error";
      return;
    }
    if (!cantoneseVoices.length) {
      status.textContent = "目前未偵測到 zh-HK / yue 廣東話聲線。可以試重新偵測，或者直接試 B 組開源聲線。";
      status.className = "voice-status";
      const empty = document.createElement("div");
      empty.className = "voice-empty";
      empty.textContent = "0 把廣東話系統聲線（呢個數字只代表目前瀏覽器／裝置）。";
      list.append(empty);
      return;
    }
    status.textContent = `偵測到 ${cantoneseVoices.length} 把廣東話候選聲線。每一把都可以即時免費試聽。`;
    status.className = "voice-status voice-ready";

    cantoneseVoices.forEach((voice) => {
      const card = document.createElement("article");
      card.className = "voice-card";
      const id = voiceId(voice);
      if (selected?.engine === "webspeech" && selected.voiceURI === id) card.classList.add("selected");

      const head = document.createElement("div");
      head.className = "voice-card-head";
      const titleWrap = document.createElement("div");
      const provider = document.createElement("span");
      provider.className = "provider-badge";
      provider.textContent = providerFor(voice);
      const title = document.createElement("h3");
      title.textContent = voice.name || "Unnamed Cantonese voice";
      titleWrap.append(provider, title);
      const lang = document.createElement("span");
      lang.className = "lang-badge";
      lang.textContent = voice.lang || "zh-HK";
      head.append(titleWrap, lang);

      const meta = document.createElement("p");
      meta.className = "voice-meta";
      meta.textContent = `${voice.localService ? "裝置本機聲線" : "瀏覽器提供聲線"} · ${voice.default ? "系統預設" : "非預設"} · Voice URI: ${id}`;

      const actions = document.createElement("div");
      actions.className = "voice-actions";
      actions.append(
        createButton("▶ 試聽", "voice-btn", () => playWebVoice(voice)),
        createButton("★ 選用呢把聲", "voice-btn select", () => saveChoice({ engine: "webspeech", voiceURI: id, name: voice.name, lang: voice.lang, provider: providerFor(voice) }))
      );
      card.append(head, meta, actions);
      list.append(card);
    });
  }

  function refreshVoices() {
    if (!("speechSynthesis" in window)) return renderSystemVoices();
    const all = window.speechSynthesis.getVoices();
    cantoneseVoices = all.filter(isCantoneseVoice).sort((a, b) => {
      const localSort = Number(b.localService) - Number(a.localService);
      return localSort || String(a.name).localeCompare(String(b.name));
    });
    renderSystemVoices();
  }

  document.getElementById("refresh-voices").addEventListener("click", () => {
    refreshVoices();
    setTimeout(refreshVoices, 300);
  });

  if ("speechSynthesis" in window) {
    window.speechSynthesis.addEventListener?.("voiceschanged", refreshVoices);
    refreshVoices();
    setTimeout(refreshVoices, 250);
    setTimeout(refreshVoices, 1000);
  } else {
    renderSystemVoices();
  }

  function renderCurrentChoice() {
    if (!selected) {
      current.textContent = "未選擇";
      currentNote.textContent = "試聽後按「★ 選用呢把聲」。選擇只會存喺你目前瀏覽器，之後可以隨時改。";
    } else if (selected.engine === "sherpa") {
      current.textContent = "Cantonese (xiaomaiiwn) · sherpa-onnx";
      currentNote.textContent = "已儲存：Browser-local 開源 Cantonese VITS。第一次正式朗讀前需要載入模型。";
    } else {
      current.textContent = `${selected.name || "Cantonese voice"} · ${selected.lang || "zh-HK"}`;
      currentNote.textContent = `已儲存：${selected.provider || "Web Speech"}。如果另一部裝置冇同一把聲，日後新聞播放器會自動要求重新選擇。`;
    }
    const sherpaCard = document.getElementById("sherpa-card");
    sherpaCard?.classList.toggle("selected", selected?.engine === "sherpa");
  }

  renderCurrentChoice();

  function setSherpaStatus(text, kind = "") {
    sherpaStatus.textContent = text;
    sherpaStatus.className = `model-status${kind ? ` voice-${kind}` : ""}`;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.async = false;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Unable to load ${src}`));
      document.body.append(script);
    });
  }

  function initSherpa() {
    if (sherpaReady || !window.Module || typeof window.createOfflineTts !== "function") {
      if (!sherpaReady && sherpaLoading) {
        clearTimeout(sherpaInitTimer);
        sherpaInitTimer = setTimeout(initSherpa, 100);
      }
      return;
    }
    try {
      setSherpaStatus("正在初始化 Cantonese VITS…");
      window._dailyBriefCantoneseTts = window.createOfflineTts(window.Module, {
        offlineTtsModelConfig: {
          offlineTtsVitsModelConfig: {
            model: "./vits-cantonese-hf-xiaomaiiwn.onnx",
            lexicon: "./lexicon.txt",
            tokens: "./tokens.txt",
            dataDir: "",
            dictDir: "",
            noiseScale: 0.667,
            noiseScaleW: 0.8,
            lengthScale: 1.0
          },
          numThreads: 1,
          debug: 0,
          provider: "cpu"
        },
        ruleFsts: "./rule.fst",
        ruleFars: "",
        maxNumSentences: 1
      });
      sherpaReady = true;
      sherpaLoading = false;
      loadSherpaBtn.disabled = true;
      loadSherpaBtn.textContent = "✓ 模型已載入";
      playSherpaBtn.disabled = false;
      setSherpaStatus(`準備完成 · ${window._dailyBriefCantoneseTts.sampleRate} Hz · 可以試聽。`, "ready");
    } catch (error) {
      console.error(error);
      sherpaLoading = false;
      setSherpaStatus(`模型初始化失敗：${error.message}`, "error");
      loadSherpaBtn.disabled = false;
    }
  }

  async function loadSherpa() {
    if (sherpaReady || sherpaLoading) return;
    sherpaLoading = true;
    loadSherpaBtn.disabled = true;
    loadSherpaBtn.textContent = "下載中…";
    setSherpaStatus("開始載入 browser-local Cantonese 模型；第一次約 114 MB。請保持頁面開啟。\n");

    window.Module = {
      locateFile(path) { return SHERPA_DIR + path; },
      setStatus(text) {
        if (!text) {
          initSherpa();
          return;
        }
        const match = String(text).match(/Downloading data\.\.\. \((\d+)\/(\d+)\)/);
        if (match) {
          const pct = (Number(match[1]) / Number(match[2]) * 100).toFixed(1);
          setSherpaStatus(`正在下載模型… ${pct}%`);
        } else {
          setSherpaStatus(String(text));
        }
      }
    };

    try {
      await loadScript(SHERPA_DIR + "sherpa-onnx-wasm-main-tts.js");
      await loadScript(SHERPA_DIR + "sherpa-onnx-tts.js");
      initSherpa();
    } catch (error) {
      console.error(error);
      sherpaLoading = false;
      loadSherpaBtn.disabled = false;
      loadSherpaBtn.textContent = "↻ 再試載入模型";
      setSherpaStatus("無法載入模型/WASM。可能係網絡、瀏覽器記憶體或第三方模型檔暫時不可用。", "error");
    }
  }

  function createWavBlob(samples, sampleRate) {
    const int16 = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i += 1) {
      const value = Math.max(-1, Math.min(1, samples[i]));
      int16[i] = value * 32767;
    }
    const buffer = new ArrayBuffer(44 + int16.length * 2);
    const view = new DataView(buffer);
    view.setUint32(0, 0x46464952, true);
    view.setUint32(4, 36 + int16.length * 2, true);
    view.setUint32(8, 0x45564157, true);
    view.setUint32(12, 0x20746d66, true);
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    view.setUint32(36, 0x61746164, true);
    view.setUint32(40, int16.length * 2, true);
    let offset = 44;
    for (let i = 0; i < int16.length; i += 1) {
      view.setInt16(offset, int16[i], true);
      offset += 2;
    }
    return new Blob([view], { type: "audio/wav" });
  }

  function playSherpa() {
    const tts = window._dailyBriefCantoneseTts;
    const text = getText();
    if (!tts || !text) return;
    stopAll();
    playSherpaBtn.disabled = true;
    playSherpaBtn.textContent = "合成中…";
    setTimeout(() => {
      try {
        const started = performance.now();
        const result = tts.generate({ text, sid: 0, speed: Number(rate.value) || 1 });
        const wav = createWavBlob(result.samples, result.sampleRate);
        if (player.src?.startsWith("blob:")) URL.revokeObjectURL(player.src);
        player.src = URL.createObjectURL(wav);
        player.hidden = false;
        player.play().catch(() => {});
        const seconds = (result.samples.length / result.sampleRate).toFixed(1);
        const elapsed = Math.round(performance.now() - started);
        setSherpaStatus(`已合成 ${seconds} 秒聲音 · ${elapsed} ms · ${result.sampleRate} Hz`, "ready");
      } catch (error) {
        console.error(error);
        setSherpaStatus(`語音合成失敗：${error.message}`, "error");
      } finally {
        playSherpaBtn.disabled = false;
        playSherpaBtn.textContent = "▶ 試聽";
      }
    }, 50);
  }

  loadSherpaBtn.addEventListener("click", loadSherpa);
  playSherpaBtn.addEventListener("click", playSherpa);
  selectSherpaBtn.addEventListener("click", () => saveChoice({ engine: "sherpa", id: "xiaomaiiwn", name: "Cantonese (xiaomaiiwn)", lang: "yue", provider: "sherpa-onnx / browser-local" }));
})();