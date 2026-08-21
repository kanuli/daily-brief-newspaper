import { Client, handle_file } from 'https://cdn.jsdelivr.net/npm/@gradio/client@2.5.0/dist/index.min.js';

const SPACE_ID = 'ASLP-lab/WenetSpeech-Yue-TTS';
const STORAGE_KEY = 'dailyBrief.cantoneseVoice.v1';
const F01_REFERENCE = 'https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav';
const PREFERRED = {
  engine: 'wenet-female',
  id: 'cosyvoice2-yue-databaker-f01',
  name: 'CosyVoice2-Yue-Databaker — Female',
  lang: 'yue-HK',
  provider: 'ASLP-lab / WenetSpeech-Yue',
  reference: 'F01_中立_20054.wav',
  fallbackOrder: ['google-cantonese-female', 'microsoft-cantonese-female']
};

const GOOGLE_FEMALE_HINTS = [
  'standard-a', 'standard-c', 'achernar', 'aoede', 'autonoe', 'callirrhoe', 'despina',
  'erinome', 'gacrux', 'kore', 'laomedeia', 'leda', 'pulcherrima', 'sulafat',
  'vindemiatrix', 'zephyr', 'female', 'woman', '女性', '女聲', '女声'
];
const MICROSOFT_FEMALE_HINTS = ['hiumaan', 'hiu maan', 'hiugaai', 'hiu gaai', 'female', '女性', '女聲', '女声'];
const MICROSOFT_MALE_HINTS = ['wanlung', 'wan lung', 'male', '男性', '男聲', '男声'];

const $ = (selector, root = document) => root.querySelector(selector);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function setMainStatus(message, tone = '') {
  const status = $('#voice-status');
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function savePreferred() {
  const rate = Number($('#voice-rate')?.value || 1);
  const payload = { ...PREFERRED, rate, savedAt: new Date().toISOString() };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  const summary = $('#voice-saved-summary');
  if (summary) summary.textContent = `${payload.name} · 首選 → Google Female → Microsoft Female`;
  setMainStatus(`已設定首選聲線：${payload.name}；失敗時依次用 Google / Microsoft 女聲。`, 'ok');
  const btn = $('#wenet-use-female');
  if (btn) btn.textContent = '✓ 已選為首選聲線';
}

function extractAudioUrl(value) {
  if (!value) return null;
  if (typeof value === 'string') return value;
  if (typeof value.url === 'string') return value.url;
  if (typeof value.path === 'string' && /^https?:\/\//i.test(value.path)) return value.path;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = extractAudioUrl(item);
      if (found) return found;
    }
  }
  return null;
}

function readableSpaceState(status) {
  const raw = String(status?.status || status?.detail || '').toLowerCase();
  if (raw.includes('sleep')) return '免費 Space 正在喚醒';
  if (raw.includes('build')) return '免費 Space 正在重新建立';
  if (raw.includes('error')) return '官方免費 Space 暫時出錯';
  if (raw.includes('run')) return '官方免費 Space 已連線';
  return status?.message || '正在連線官方免費 Space';
}

function normalizeLang(lang) {
  return String(lang || '').trim().toLowerCase().replaceAll('_', '-');
}

function isCantoneseVoice(voice) {
  const lang = normalizeLang(voice?.lang);
  const name = String(voice?.name || '').toLowerCase();
  return lang === 'zh-hk' || lang === 'yue' || lang.startsWith('yue-') || lang === 'zh-yue' ||
    /cantonese|hong\s*kong|廣東話|广东话|粵語|粤语/.test(name);
}

async function getBrowserVoices() {
  if (!('speechSynthesis' in window)) return [];
  let voices = window.speechSynthesis.getVoices();
  if (voices.length) return voices;
  await Promise.race([
    new Promise((resolve) => window.speechSynthesis.addEventListener('voiceschanged', resolve, { once: true })),
    sleep(1200)
  ]);
  voices = window.speechSynthesis.getVoices();
  return voices;
}

function includesAny(value, hints) {
  const text = String(value || '').toLowerCase();
  return hints.some((hint) => text.includes(hint));
}

function pickGoogleFemale(voices) {
  const candidates = voices.filter((voice) => {
    const name = String(voice.name || '').toLowerCase();
    return isCantoneseVoice(voice) && name.includes('google');
  });
  if (!candidates.length) return null;

  const scored = candidates.map((voice) => {
    const name = String(voice.name || '').toLowerCase();
    let score = 10;
    if (includesAny(name, GOOGLE_FEMALE_HINTS)) score += 100;
    if (normalizeLang(voice.lang).startsWith('yue-hk')) score += 30;
    if (normalizeLang(voice.lang) === 'zh-hk') score += 20;
    if (/cantonese|粵語|粤语/.test(name)) score += 15;
    return { voice, score };
  }).sort((a, b) => b.score - a.score);

  return scored[0].voice;
}

function pickMicrosoftFemale(voices) {
  const candidates = voices.filter((voice) => {
    const name = String(voice.name || '').toLowerCase();
    return isCantoneseVoice(voice) && name.includes('microsoft') &&
      !includesAny(name, MICROSOFT_MALE_HINTS) && includesAny(name, MICROSOFT_FEMALE_HINTS);
  });
  if (!candidates.length) return null;

  return candidates.sort((a, b) => {
    const an = String(a.name || '').toLowerCase();
    const bn = String(b.name || '').toLowerCase();
    const as = an.includes('hiumaan') || an.includes('hiu maan') ? 20 : 10;
    const bs = bn.includes('hiumaan') || bn.includes('hiu maan') ? 20 : 10;
    return bs - as;
  })[0];
}

function speakWithVoice(voice, text, rate) {
  return new Promise((resolve, reject) => {
    if (!voice || !('speechSynthesis' in window)) {
      reject(new Error('Browser speech synthesis unavailable'));
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = voice.lang || 'zh-HK';
    utterance.rate = Number.isFinite(rate) ? rate : 1;
    utterance.pitch = 1;

    let started = false;
    const startTimer = setTimeout(() => {
      if (!started) {
        window.speechSynthesis.cancel();
        reject(new Error(`${voice.name} did not start`));
      }
    }, 7000);

    utterance.onstart = () => {
      started = true;
      clearTimeout(startTimer);
    };
    utterance.onend = () => {
      clearTimeout(startTimer);
      resolve(voice);
    };
    utterance.onerror = (event) => {
      clearTimeout(startTimer);
      reject(new Error(event.error || `${voice.name} playback failed`));
    };

    window.speechSynthesis.speak(utterance);
  });
}

async function runBrowserFallbackChain(text, panelStatus) {
  const voices = await getBrowserVoices();
  const rate = Number($('#voice-rate')?.value || 1);
  const google = pickGoogleFemale(voices);
  const microsoft = pickMicrosoftFemale(voices);
  const attempts = [
    { label: 'Google 廣東話 Female fallback', voice: google },
    { label: 'Microsoft 廣東話 Female fallback', voice: microsoft }
  ];

  for (const attempt of attempts) {
    if (!attempt.voice) {
      panelStatus.textContent = `${attempt.label}：此裝置 / browser 未提供，繼續下一層。`;
      continue;
    }

    try {
      panelStatus.textContent = `CosyVoice 失敗；正在改用 ${attempt.label}：${attempt.voice.name}…`;
      setMainStatus(`Fallback：${attempt.voice.name}`);
      await speakWithVoice(attempt.voice, text, rate);
      panelStatus.textContent = `Fallback 成功：實際使用 ${attempt.voice.name}（${attempt.voice.lang || 'zh-HK'}）。`;
      setMainStatus(`已用 fallback 播放：${attempt.voice.name}`, 'ok');
      return { ok: true, voice: attempt.voice, label: attempt.label };
    } catch (error) {
      console.warn(`${attempt.label} failed`, error);
      panelStatus.textContent = `${attempt.label} 播放失敗，繼續下一層。`;
    }
  }

  return { ok: false };
}

async function generateFemalePreview() {
  const button = $('#wenet-live-generate');
  const panelStatus = $('#wenet-live-status');
  const audio = $('#wenet-live-audio');
  const textArea = $('#voice-sample');
  const rawText = (textArea?.value || '').trim();
  const text = rawText.slice(0, 260);

  if (!text) {
    panelStatus.textContent = '請先輸入試聽文字。';
    return;
  }

  if (rawText.length > 260) {
    panelStatus.textContent = '免費即時測試先使用頭 260 個字，減少 ZeroGPU quota 消耗。';
  } else {
    panelStatus.textContent = '正在連線 ASLP-lab 免費 WenetSpeech-Yue Space…';
  }

  button.disabled = true;
  audio.removeAttribute('src');
  audio.load();
  setMainStatus('第 1 層：CosyVoice2-Yue-Databaker Female…');

  try {
    const app = await Client.connect(SPACE_ID, {
      events: ['data', 'status'],
      status_callback: (spaceStatus) => {
        panelStatus.textContent = readableSpaceState(spaceStatus);
      }
    });

    const payload = [
      'CosyVoice2-Yue',
      text,
      'Custom Upload',
      handle_file(F01_REFERENCE)
    ];

    let result;
    let lastError;
    for (const endpoint of ['/tts_inference', '/predict']) {
      try {
        result = await app.predict(endpoint, payload);
        if (result?.data) break;
      } catch (error) {
        lastError = error;
      }
    }
    if (!result?.data) throw lastError || new Error('No audio returned');

    const audioUrl = extractAudioUrl(result.data[0]);
    if (!audioUrl) throw new Error('Generated audio URL missing');

    audio.src = audioUrl;
    audio.load();
    panelStatus.textContent = '第 1 層成功：CosyVoice2-Yue + 官方 F01 Female reference。';
    setMainStatus('使用中：CosyVoice2-Yue-Databaker — Female', 'ok');
    savePreferred();
    await audio.play().catch(() => {});
  } catch (error) {
    console.error('WenetSpeech free live generation failed', error);
    const message = String(error?.message || error || 'service unavailable');
    panelStatus.textContent = `第 1 層 CosyVoice 失敗：${message.slice(0, 140)}。正在啟動 Google → Microsoft 女聲 fallback…`;
    setMainStatus('CosyVoice 失敗，進入 Google / Microsoft fallback。', 'warn');

    const fallback = await runBrowserFallbackChain(text, panelStatus);
    if (!fallback.ok) {
      panelStatus.textContent = '三層全部不可用：CosyVoice、Google Cantonese、Microsoft Cantonese Female 均未能播放。請檢查 browser / 系統廣東話 voice。';
      setMainStatus('所有廣東話聲線均不可用。', 'warn');
    }
  } finally {
    button.disabled = false;
  }
}

function buildPanel() {
  if ($('#wenet-live-free')) return;
  const neuralSection = $('#wenet-neural-demo');
  if (!neuralSection) return;

  const panel = document.createElement('section');
  panel.id = 'wenet-live-free';
  panel.className = 'voice-controls';
  panel.style.marginBottom = '18px';
  panel.innerHTML = `
    <div>
      <label>★ 自動聲線次序：CosyVoice Female → Google Female → Microsoft Female</label>
      <p class="voice-note"><strong>第 1 層：</strong>CosyVoice2-Yue-Databaker — Female（官方 F01 female reference）。<br><strong>第 2 層：</strong>Google Cantonese female；browser 若只暴露 generic Google Cantonese 名稱，會顯示實際名稱供核對。<br><strong>第 3 層：</strong>Microsoft zh-HK female，只接受 HiuMaan / HiuGaai 等 female voice，明確排除 WanLung 男聲。</p>
      <p class="voice-note">免費模式仍然唔會把約 5.94GB CosyVoice 模型放入 GitHub Pages。CosyVoice hosted generation 失敗先 fallback，唔會一開始就用 Google / Microsoft。</p>
      <div id="wenet-live-status" class="voice-status" role="status">未開始自動聲線測試。</div>
      <audio id="wenet-live-audio" controls preload="none" style="width:100%;margin-top:10px"></audio>
    </div>
    <div class="voice-control-row">
      <button class="voice-btn" id="wenet-use-female" type="button">★ 使用呢個自動次序</button>
      <button class="voice-btn secondary" id="wenet-live-generate" type="button">▶ 測試自動播放</button>
    </div>`;

  neuralSection.insertBefore(panel, neuralSection.querySelector('.voice-grid'));
  $('#wenet-use-female')?.addEventListener('click', savePreferred);
  $('#wenet-live-generate')?.addEventListener('click', generateFemalePreview);

  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (saved?.engine === 'wenet-female') {
      const btn = $('#wenet-use-female');
      if (btn) btn.textContent = '✓ 已使用自動次序';
    }
  } catch (_) {}
}

function boot() {
  if ($('#wenet-neural-demo')) buildPanel();
  else setTimeout(boot, 120);
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
else boot();
