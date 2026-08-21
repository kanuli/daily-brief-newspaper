(() => {
  'use strict';

  const STORAGE_KEY = 'dailyBrief.cantoneseVoice.v1';
  const SAMPLE_TEXT = '早晨，呢度係每日晨報。今日我哋會用廣東話，幫你快速掌握最值得留意嘅新聞。你可以逐把聲試聽，再揀一把最舒服嘅聲線。';
  const CANTONESE_LANGS = new Set(['zh-hk', 'yue', 'yue-hk', 'zh-yue', 'zh-hant-hk']);
  const CANTONESE_NAME_RE = /(cantonese|hong\s*kong|廣東話|广东话|粵語|粤语|粵|粤)/i;

  const state = { browserVoices: [], selected: null };
  const $ = (id) => document.getElementById(id);
  const els = {
    count: $('voice-count'), list: $('voice-list'), sample: $('voice-sample'), rate: $('voice-rate'),
    rateValue: $('voice-rate-value'), save: $('voice-save'), status: $('voice-status'),
    refresh: $('voice-refresh'), stop: $('voice-stop'), saved: $('voice-saved-summary')
  };

  if (!els.list) return;
  els.sample.value = SAMPLE_TEXT;

  function esc(value) {
    return String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
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

  function setStatus(message, tone = '') {
    els.status.textContent = message;
    els.status.dataset.tone = tone;
  }

  function browserVoiceKey(voice) {
    return voice.voiceURI || `${voice.name}|${voice.lang}`;
  }

  function loadSaved() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const saved = raw ? JSON.parse(raw) : null;
      if (saved?.engine === 'webspeech' || saved?.engine === 'wenet-female') state.selected = saved;
      else if (saved) localStorage.removeItem(STORAGE_KEY);
    } catch (_) {
      state.selected = null;
    }
  }

  function renderSaved() {
    if (!state.selected) {
      els.saved.textContent = '未選擇預設聲線';
      return;
    }
    if (state.selected.engine === 'wenet-female') {
      els.saved.textContent = `${state.selected.name} · WenetSpeech neural（首選）`;
      return;
    }
    els.saved.textContent = `${state.selected.name} · Browser / 裝置`;
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

  function stopAll() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    document.querySelectorAll('audio').forEach((audio) => {
      try { audio.pause(); } catch (_) {}
    });
    setStatus('播放已停止。');
  }

  function renderVoices() {
    const cards = state.browserVoices.map((voice) => {
      const id = browserVoiceKey(voice);
      const checked = state.selected?.engine === 'webspeech' && state.selected?.id === id ? 'checked' : '';
      const service = voice.localService ? '本機 voice' : 'Browser 提供';
      return `
        <article class="voice-card" data-engine="webspeech" data-id="${esc(id)}">
          <label class="voice-select-line">
            <input type="radio" name="cantonese-voice" value="${esc(id)}" ${checked}>
            <span class="voice-name">${esc(voice.name)}</span>
          </label>
          <div class="voice-meta"><span>${esc(voice.lang || 'zh-HK')}</span><span>${esc(inferProvider(voice.name))}</span><span>${service}</span></div>
          <button type="button" class="voice-preview" data-preview="webspeech" data-id="${esc(id)}">▶ 試聽</button>
        </article>`;
    });

    els.list.innerHTML = cards.join('');
    els.count.textContent = state.browserVoices.length
      ? `${state.browserVoices.length} 把裝置廣東話聲線；WenetSpeech-Yue neural samples 喺下方`
      : '未偵測到裝置廣東話聲線；請直接試下方 WenetSpeech-Yue neural samples';

    els.list.querySelectorAll('input[name="cantonese-voice"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        const card = radio.closest('.voice-card');
        const voice = state.browserVoices.find((v) => browserVoiceKey(v) === card.dataset.id);
        if (!voice) return;
        state.selected = { engine: 'webspeech', id: card.dataset.id, name: voice.name, lang: voice.lang || 'zh-HK' };
        renderSaved();
      });
    });

    els.list.querySelectorAll('.voice-preview').forEach((button) => {
      button.addEventListener('click', () => previewBrowser(button.dataset.id));
    });
  }

  function refreshBrowserVoices() {
    if (!('speechSynthesis' in window)) {
      state.browserVoices = [];
      renderVoices();
      setStatus('呢個 browser 不支援 Web Speech API；請試下方 WenetSpeech-Yue neural samples。', 'warn');
      return;
    }

    const deduped = new Map();
    window.speechSynthesis.getVoices().filter(isCantoneseVoice)
      .forEach((voice) => deduped.set(browserVoiceKey(voice), voice));
    state.browserVoices = [...deduped.values()].sort((a, b) => a.name.localeCompare(b.name));
    renderVoices();
    setStatus(state.browserVoices.length
      ? `已偵測到 ${state.browserVoices.length} 把可直接使用嘅廣東話聲線。`
      : '暫時偵測唔到裝置 zh-HK/yue voice；請試下方較自然嘅 WenetSpeech-Yue neural samples。',
      state.browserVoices.length ? 'ok' : 'warn');
  }

  function previewBrowser(id) {
    const voice = state.browserVoices.find((v) => browserVoiceKey(v) === id);
    if (!voice || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
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

  els.rate.addEventListener('input', () => { els.rateValue.textContent = `${Number(els.rate.value).toFixed(1)}×`; });
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
