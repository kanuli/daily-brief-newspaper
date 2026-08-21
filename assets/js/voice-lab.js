(() => {
  'use strict';

  const STORAGE_KEY = 'dailyBrief.cantoneseVoice.v1';
  const SAMPLE_TEXT = '早晨，呢度係每日晨報。今日我哋會用廣東話，幫你快速掌握最值得留意嘅新聞。你可以逐把聲試聽，再揀一把最舒服嘅聲線。';
  const CANTONESE_LANGS = new Set(['zh-hk', 'yue', 'yue-hk', 'zh-yue', 'zh-hant-hk']);
  const CANTONESE_NAME_RE = /(cantonese|hong\s*kong|廣東話|广东话|粵語|粤语|粵|粤)/i;

  const state = {
    browserVoices: [],
    selected: null,
    meSpeakReady: false,
    meSpeakLoading: null
  };

  const $ = (id) => document.getElementById(id);
  const els = {
    count: $('voice-count'),
    list: $('voice-list'),
    sample: $('voice-sample'),
    rate: $('voice-rate'),
    rateValue: $('voice-rate-value'),
    save: $('voice-save'),
    status: $('voice-status'),
    refresh: $('voice-refresh'),
    stop: $('voice-stop'),
    saved: $('voice-saved-summary')
  };

  if (!els.list) return;
  els.sample.value = SAMPLE_TEXT;

  function esc(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function normalizeLang(lang) {
    return String(lang || '').trim().toLowerCase().replaceAll('_', '-');
  }

  function isCantoneseVoice(voice) {
    const lang = normalizeLang(voice.lang);
    return CANTONESE_LANGS.has(lang) || lang.startsWith('yue-') || CANTONESE_NAME_RE.test(voice.name || '');
  }

  function inferProvider(name) {
    const n = String(name || '').toLowerCase();
    if (n.includes('microsoft')) return 'Microsoft / Windows';
    if (n.includes('google')) return 'Google / Chrome';
    if (n.includes('apple') || n.includes('sin-ji') || n.includes('siri')) return 'Apple';
    if (n.includes('samsung')) return 'Samsung';
    return '裝置 / Browser';
  }

  function loadSaved() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      state.selected = raw ? JSON.parse(raw) : null;
    } catch (_) {
      state.selected = null;
    }
  }

  function saveSelected() {
    if (!state.selected) {
      setStatus('請先選擇一把聲線。', 'warn');
      return;
    }
    const payload = { ...state.selected, rate: Number(els.rate.value), savedAt: new Date().toISOString() };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    state.selected = payload;
    renderSaved();
    setStatus(`已儲存：${payload.name}`, 'ok');
  }

  function renderSaved() {
    if (!state.selected) {
      els.saved.textContent = '未選擇預設聲線';
      return;
    }
    const engine = state.selected.engine === 'webspeech' ? 'Browser / 裝置' : 'Open-source fallback';
    els.saved.textContent = `${state.selected.name} · ${engine}`;
  }

  function setStatus(message, tone = '') {
    els.status.textContent = message;
    els.status.dataset.tone = tone;
  }

  function stopAll() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (window.meSpeak && typeof window.meSpeak.stop === 'function') {
      try { window.meSpeak.stop(); } catch (_) {}
    }
    setStatus('播放已停止。');
  }

  function browserVoiceKey(voice) {
    return voice.voiceURI || `${voice.name}|${voice.lang}`;
  }

  function cardChecked(engine, id) {
    if (!state.selected) return false;
    if (engine === 'webspeech') return state.selected.engine === engine && state.selected.id === id;
    return state.selected.engine === engine && state.selected.profile === id;
  }

  function renderVoices() {
    const cards = [];

    for (const voice of state.browserVoices) {
      const id = browserVoiceKey(voice);
      const checked = cardChecked('webspeech', id) ? 'checked' : '';
      const service = voice.localService ? '本機 voice' : 'Browser 提供';
      cards.push(`
        <article class="voice-card" data-engine="webspeech" data-id="${esc(id)}">
          <label class="voice-select-line">
            <input type="radio" name="cantonese-voice" value="${esc(id)}" ${checked}>
            <span class="voice-name">${esc(voice.name)}</span>
          </label>
          <div class="voice-meta"><span>${esc(voice.lang || 'zh-HK')}</span><span>${esc(inferProvider(voice.name))}</span><span>${service}</span></div>
          <button type="button" class="voice-preview" data-preview="webspeech" data-id="${esc(id)}">▶ 試聽</button>
        </article>`);
    }

    const fallbackProfiles = [
      { id: 'classic', name: 'eSpeak Cantonese — 原聲', variant: '', pitch: 50 },
      { id: 'female-f2', name: 'eSpeak Cantonese — Female F2', variant: 'f2', pitch: 50 },
      { id: 'female-f5', name: 'eSpeak Cantonese — Female F5', variant: 'f5', pitch: 50 },
      { id: 'male-m3', name: 'eSpeak Cantonese — Male M3', variant: 'm3', pitch: 50 }
    ];

    for (const profile of fallbackProfiles) {
      const checked = cardChecked('mespeak', profile.id) ? 'checked' : '';
      cards.push(`
        <article class="voice-card voice-card-fallback" data-engine="mespeak" data-id="${profile.id}">
          <label class="voice-select-line">
            <input type="radio" name="cantonese-voice" value="mespeak:${profile.id}" ${checked}>
            <span class="voice-name">${profile.name}</span>
          </label>
          <div class="voice-meta"><span>zh-yue</span><span>meSpeak / eSpeak</span><span>GPL · client-side</span></div>
          <p class="voice-note">完全免費、無 API key；聲音較機械化，作為跨裝置 fallback。</p>
          <button type="button" class="voice-preview" data-preview="mespeak" data-id="${profile.id}" data-pitch="${profile.pitch}" data-variant="${profile.variant}">▶ 試聽</button>
        </article>`);
    }

    els.list.innerHTML = cards.join('');
    els.count.textContent = `${state.browserVoices.length} 把裝置廣東話聲線 + 4 個開源 fallback profiles`;

    els.list.querySelectorAll('input[name="cantonese-voice"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        const card = radio.closest('.voice-card');
        const engine = card.dataset.engine;
        if (engine === 'webspeech') {
          const voice = state.browserVoices.find((v) => browserVoiceKey(v) === card.dataset.id);
          if (!voice) return;
          state.selected = {
            engine: 'webspeech',
            id: card.dataset.id,
            name: voice.name,
            lang: voice.lang || 'zh-HK'
          };
        } else {
          const profile = card.dataset.id;
          const name = card.querySelector('.voice-name').textContent;
          state.selected = { engine: 'mespeak', profile, name, lang: 'zh-yue' };
        }
        renderSaved();
      });
    });

    els.list.querySelectorAll('.voice-preview').forEach((button) => {
      button.addEventListener('click', async () => {
        const kind = button.dataset.preview;
        if (kind === 'webspeech') previewBrowser(button.dataset.id);
        else await previewMeSpeak(button.dataset.id, Number(button.dataset.pitch), button.dataset.variant || '');
      });
    });
  }

  function refreshBrowserVoices() {
    if (!('speechSynthesis' in window)) {
      state.browserVoices = [];
      renderVoices();
      setStatus('呢個 browser 不支援 Web Speech API；仍可試用開源 fallback。', 'warn');
      return;
    }

    const all = window.speechSynthesis.getVoices();
    const deduped = new Map();
    all.filter(isCantoneseVoice).forEach((voice) => deduped.set(browserVoiceKey(voice), voice));
    state.browserVoices = [...deduped.values()].sort((a, b) => a.name.localeCompare(b.name));
    renderVoices();

    if (state.browserVoices.length) {
      setStatus(`已偵測到 ${state.browserVoices.length} 把可直接使用嘅廣東話聲線。`, 'ok');
    } else {
      setStatus('暫時偵測唔到裝置 zh-HK/yue voice；可以先試開源 fallback，或者安裝系統廣東話語音後再重新偵測。', 'warn');
    }
  }

  function previewBrowser(id) {
    const voice = state.browserVoices.find((v) => browserVoiceKey(v) === id);
    if (!voice || !('speechSynthesis' in window)) return;
    stopAll();
    const utterance = new SpeechSynthesisUtterance(els.sample.value.trim() || SAMPLE_TEXT);
    utterance.voice = voice;
    utterance.lang = voice.lang || 'zh-HK';
    utterance.rate = Number(els.rate.value);
    utterance.pitch = 1;
    utterance.onstart = () => setStatus(`播放中：${voice.name}`, 'ok');
    utterance.onerror = () => setStatus(`未能播放 ${voice.name}，請試另一把聲。`, 'warn');
    utterance.onend = () => setStatus(`試聽完成：${voice.name}`);
    window.speechSynthesis.speak(utterance);
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-voice-lib="${src}"]`);
      if (existing) {
        if (window.meSpeak) resolve();
        else existing.addEventListener('load', resolve, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.dataset.voiceLib = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function ensureMeSpeak() {
    if (state.meSpeakReady && window.meSpeak) return;
    if (state.meSpeakLoading) return state.meSpeakLoading;

    state.meSpeakLoading = (async () => {
      setStatus('第一次載入開源 Cantonese engine…');
      const base = 'https://cdn.jsdelivr.net/gh/btopro/mespeak@master/';
      await loadScript(`${base}mespeak.js`);
      if (!window.meSpeak) throw new Error('meSpeak unavailable');
      window.meSpeak.loadConfig(`${base}mespeak_config.json`);
      await new Promise((resolve, reject) => {
        window.meSpeak.loadVoice(`${base}voices/zh-yue.json`, (success, message) => {
          if (success) resolve(message);
          else reject(new Error(message || 'meSpeak voice data failed'));
        });
      });
      const started = Date.now();
      while (!window.meSpeak.isConfigLoaded() || !window.meSpeak.isVoiceLoaded('zh-yue')) {
        if (Date.now() - started > 10000) throw new Error('meSpeak timeout');
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      state.meSpeakReady = true;
    })();

    try {
      await state.meSpeakLoading;
    } finally {
      state.meSpeakLoading = null;
    }
  }

  async function previewMeSpeak(profile, pitch, variant) {
    stopAll();
    try {
      await ensureMeSpeak();
      const rate = Number(els.rate.value);
      const speed = Math.round(175 * rate);
      setStatus('播放中：eSpeak Cantonese', 'ok');
      window.meSpeak.speak(els.sample.value.trim() || SAMPLE_TEXT, {
        voice: 'zh-yue',
        speed,
        pitch: Number.isFinite(pitch) ? pitch : 50,
        variant: variant || undefined,
        amplitude: 100,
        wordgap: 0
      });
    } catch (error) {
      console.error(error);
      setStatus('開源 fallback 載入失敗；請用裝置 voice，或稍後再試。', 'warn');
    }
  }

  els.rate.addEventListener('input', () => {
    els.rateValue.textContent = `${Number(els.rate.value).toFixed(1)}×`;
  });
  els.save.addEventListener('click', saveSelected);
  els.refresh.addEventListener('click', refreshBrowserVoices);
  els.stop.addEventListener('click', stopAll);

  loadSaved();
  renderSaved();
  refreshBrowserVoices();

  if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = refreshBrowserVoices;
    setTimeout(refreshBrowserVoices, 500);
    setTimeout(refreshBrowserVoices, 1500);
  }
})();