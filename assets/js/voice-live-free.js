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
  reference: 'F01_中立_20054.wav'
};

const $ = (selector, root = document) => root.querySelector(selector);

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
  if (summary) summary.textContent = `${payload.name} · WenetSpeech neural（首選）`;
  setMainStatus(`已設定首選聲線：${payload.name}`, 'ok');
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
  setMainStatus('正在用 CosyVoice2-Yue-Databaker Female 生成試聽…');

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
    panelStatus.textContent = '生成成功：CosyVoice2-Yue + 官方 F01 女性 reference。';
    setMainStatus('免費 neural 試聽生成成功。', 'ok');
    savePreferred();
    await audio.play().catch(() => {});
  } catch (error) {
    console.error('WenetSpeech free live generation failed', error);
    const message = String(error?.message || error || 'service unavailable');
    panelStatus.textContent = `官方免費 Space 暫時不可用：${message.slice(0, 180)}。下方官方預生成 Female sample 仍可正常比較。`;
    setMainStatus('CosyVoice 女性聲線已保留為首選；官方免費即時服務目前不可用。', 'warn');
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
      <label>★ 首選：CosyVoice2-Yue-Databaker — Female</label>
      <p class="voice-note">免費模式：GitHub Pages 唔下載 5.94GB 模型，而係需要時呼叫 ASLP-lab 官方公開 Hugging Face Space，並使用官方 F01 女性 reference。唔需要 API key；ZeroGPU 有免費每日 quota，服務休眠、排隊或 runtime error 時可能暫時不可生成。</p>
      <p class="voice-note"><strong>Production 策略：</strong>呢把聲已作為首選 neural voice；即時服務不可用時唔會冒充同一聲線，網站會保留最後已生成音訊／官方 sample，再考慮 GitHub Actions CPU 預生成。</p>
      <div id="wenet-live-status" class="voice-status" role="status">未開始即時生成測試。</div>
      <audio id="wenet-live-audio" controls preload="none" style="width:100%;margin-top:10px"></audio>
    </div>
    <div class="voice-control-row">
      <button class="voice-btn" id="wenet-use-female" type="button">★ 使用呢把聲</button>
      <button class="voice-btn secondary" id="wenet-live-generate" type="button">▶ 用上面文字免費生成</button>
    </div>`;

  neuralSection.insertBefore(panel, neuralSection.querySelector('.voice-grid'));
  $('#wenet-use-female')?.addEventListener('click', savePreferred);
  $('#wenet-live-generate')?.addEventListener('click', generateFemalePreview);

  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (saved?.engine === 'wenet-female') {
      const btn = $('#wenet-use-female');
      if (btn) btn.textContent = '✓ 已選為首選聲線';
    }
  } catch (_) {}
}

function boot() {
  if ($('#wenet-neural-demo')) buildPanel();
  else setTimeout(boot, 120);
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
else boot();
