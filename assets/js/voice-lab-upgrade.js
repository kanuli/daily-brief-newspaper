(() => {
  'use strict';

  const MESPEAK_BASE = 'https://cdn.jsdelivr.net/gh/btopro/mespeak@master/';
  const OPENCC_SRC = 'https://cdn.jsdelivr.net/npm/opencc-js@1.4.1/dist/umd/full.js';
  const OFFICIAL_BASE = 'https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/';
  let enginePromise = null;
  let openCCPromise = null;
  let audioContext = null;
  let currentSource = null;

  const $ = (sel, root = document) => root.querySelector(sel);

  function setStatus(message, tone = '') {
    const el = $('#voice-status');
    if (!el) return;
    el.textContent = message;
    el.dataset.tone = tone;
  }

  function loadScript(src, key) {
    return new Promise((resolve, reject) => {
      if (window[key]) return resolve(window[key]);
      const existing = document.querySelector(`script[data-upgrade-lib="${src}"]`);
      if (existing) {
        existing.addEventListener('load', () => resolve(window[key]), { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.dataset.upgradeLib = src;
      script.onload = () => resolve(window[key]);
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function ensureOpenCC() {
    if (window.OpenCC) return window.OpenCC;
    if (!openCCPromise) openCCPromise = loadScript(OPENCC_SRC, 'OpenCC');
    return openCCPromise;
  }

  async function toSimplified(text) {
    try {
      const OpenCC = await ensureOpenCC();
      if (OpenCC?.Converter) {
        const converter = OpenCC.Converter({ from: 'hk', to: 'cn' });
        return converter(text);
      }
    } catch (error) {
      console.warn('OpenCC unavailable; using original text', error);
    }
    return text;
  }

  async function ensureMeSpeak() {
    if (window.meSpeak?.isConfigLoaded?.() && window.meSpeak?.isVoiceLoaded?.('zh-yue')) return window.meSpeak;
    if (enginePromise) return enginePromise;

    enginePromise = (async () => {
      await loadScript(`${MESPEAK_BASE}mespeak.js`, 'meSpeak');
      const meSpeak = window.meSpeak;
      if (!meSpeak) throw new Error('meSpeak library unavailable');

      if (!meSpeak.isConfigLoaded()) {
        meSpeak.loadConfig(`${MESPEAK_BASE}mespeak_config.json`);
        const started = Date.now();
        while (!meSpeak.isConfigLoaded()) {
          if (Date.now() - started > 12000) throw new Error('meSpeak config timeout');
          await new Promise((r) => setTimeout(r, 100));
        }
      }

      if (!meSpeak.isVoiceLoaded('zh-yue')) {
        await new Promise((resolve, reject) => {
          meSpeak.loadVoice(`${MESPEAK_BASE}voices/zh-yue.json`, (success, message) => {
            if (success) resolve(message);
            else reject(new Error(message || 'Cantonese voice load failed'));
          });
        });
      }
      return meSpeak;
    })();

    try {
      return await enginePromise;
    } finally {
      enginePromise = null;
    }
  }

  async function playFixedESpeak(button) {
    try {
      if (currentSource) {
        try { currentSource.stop(); } catch (_) {}
        currentSource = null;
      }
      if (window.meSpeak?.stop) {
        try { window.meSpeak.stop(); } catch (_) {}
      }

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error('Web Audio API unavailable');
      audioContext ||= new AudioContextClass();
      await audioContext.resume();

      setStatus('正在準備 eSpeak Cantonese（繁體會先轉成簡體以提高相容性）…');
      const meSpeak = await ensureMeSpeak();
      const rawText = ($('#voice-sample')?.value || '').trim() || '早晨，呢度係每日晨報。';
      const text = await toSimplified(rawText);
      const rate = Number($('#voice-rate')?.value || 1);
      const variant = button.dataset.variant || '';
      const pitch = Number(button.dataset.pitch || 50);

      const wav = meSpeak.speak(text, {
        voice: 'zh-yue',
        speed: Math.round(175 * rate),
        pitch,
        variant: variant || undefined,
        amplitude: 100,
        wordgap: 0,
        rawdata: true
      });
      if (!wav) throw new Error('eSpeak returned no audio data');

      const decoded = await audioContext.decodeAudioData(wav.slice ? wav.slice(0) : wav);
      const source = audioContext.createBufferSource();
      source.buffer = decoded;
      source.connect(audioContext.destination);
      source.onended = () => {
        if (currentSource === source) currentSource = null;
        setStatus('eSpeak Cantonese 試聽完成。');
      };
      currentSource = source;
      source.start();
      setStatus('播放中：eSpeak Cantonese（修正版）', 'ok');
    } catch (error) {
      console.error(error);
      setStatus(`eSpeak 仍未能播放：${error.message || 'unknown error'}。建議使用裝置 voice 或下方 neural sample。`, 'warn');
    }
  }

  function addNeuralDemoSection() {
    if ($('#wenet-neural-demo')) return;
    const research = $('.voice-research');
    if (!research) return;

    const section = document.createElement('section');
    section.className = 'voice-research';
    section.id = 'wenet-neural-demo';
    section.innerHTML = `
      <h3>🧠 WenetSpeech-Yue Neural TTS 官方試聽</h3>
      <p class="voice-footnote">以下係 ASLP-lab 官方 <strong>demo_page</strong> 提供嘅預生成 synthetic audio，全部由 GitHub 直接讀取，唔需要 API key。呢度係用嚟比較自然度，<strong>唔係即時把上面文字轉語音</strong>。完整 CosyVoice2-Yue 模型約數 GB，唔適合純 GitHub Pages browser 即時推理。</p>
      <div class="voice-grid" style="margin-top:14px">
        <article class="voice-card">
          <div class="voice-name">Llasa-1B-Yue</div>
          <div class="voice-meta"><span>Neural Cantonese</span><span>Official sample</span><span>A-MOS 4.34/5</span></div>
          <p class="voice-note">同一測試句：冇人性何來有人。官方評測中自然度略高於 CosyVoice2-Yue。</p>
          <audio controls preload="none" style="width:100%">
            <source src="${OFFICIAL_BASE}WSYue_TTS/common_voice_yue_39115507-common_voice_yue_39115508.wav" type="audio/wav">
          </audio>
        </article>
        <article class="voice-card">
          <div class="voice-name">CosyVoice2-Yue</div>
          <div class="voice-meta"><span>Neural Cantonese</span><span>Official sample</span><span>A-MOS 4.21/5</span></div>
          <p class="voice-note">同一測試句：冇人性何來有人。適合直接同 Llasa-1B-Yue A/B 比較。</p>
          <audio controls preload="none" style="width:100%">
            <source src="${OFFICIAL_BASE}CosyVoice2-Yue/common_voice_yue_39115507-common_voice_yue_39115508.wav" type="audio/wav">
          </audio>
        </article>
        <article class="voice-card">
          <div class="voice-name">CosyVoice2-Yue-ZoengJyutGaai</div>
          <div class="voice-meta"><span>Storytelling fine-tune</span><span>Official sample</span><span>較自然聲線</span></div>
          <p class="voice-note">官方較高質 fine-tune，以張悅楷粵語評書風格資料訓練；呢段較長，檔案亦較大。</p>
          <audio controls preload="none" style="width:100%">
            <source src="${OFFICIAL_BASE}9%E6%9C%887%E6%97%A5.WAV" type="audio/wav">
          </audio>
        </article>
      </div>
      <p class="voice-legal">資料來源：ASLP-lab / WenetSpeech-Yue 官方 GitHub demo_page，Apache-2.0。即時 neural TTS 暫不列為可儲存預設聲線，因為現階段需要大型模型及 GPU/Python runtime，唔符合純 GitHub Pages 執行限制。</p>`;
    research.parentNode.insertBefore(section, research);
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest?.('.voice-preview[data-preview="mespeak"]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    playFixedESpeak(button);
  }, true);

  document.addEventListener('DOMContentLoaded', addNeuralDemoSection);
  if (document.readyState !== 'loading') addNeuralDemoSection();
})();
