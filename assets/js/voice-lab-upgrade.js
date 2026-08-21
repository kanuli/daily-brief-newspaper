(() => {
  'use strict';

  const OFFICIAL_BASE = 'https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/';
  const $ = (sel, root = document) => root.querySelector(sel);

  function addNeuralDemoSection() {
    if ($('#wenet-neural-demo')) return;
    const research = $('.voice-research');
    if (!research) return;

    const section = document.createElement('section');
    section.className = 'voice-research';
    section.id = 'wenet-neural-demo';
    section.innerHTML = `
      <h3>🧠 WenetSpeech-Yue Neural TTS 官方試聽</h3>
      <p class="voice-footnote">以下全部係 ASLP-lab 官方 <strong>demo_page</strong> 提供嘅預生成 synthetic audio，由 GitHub 直接播放，唔需要 API key。WenetSpeech-Yue / CosyVoice2-Yue 係 prompt-conditioned / zero-shot TTS，<strong>唔係固定只有一把男聲或女聲</strong>；音色可以跟 reference speaker。完整模型仍然太大，唔適合純 GitHub Pages 即時推理。</p>
      <div class="voice-grid" style="margin-top:14px">
        <article class="voice-card">
          <div class="voice-name">♀ CosyVoice2-Yue-Databaker — Female</div>
          <div class="voice-meta"><span>Female-conditioned</span><span>Official F01 reference</span><span>Neural Cantonese</span></div>
          <p class="voice-note">官方 demo 以 <strong>F01_中立_20054.wav</strong> 女性 reference 作 conditioning，再生成下面嘅廣東話新聞式句子。呢個最適合你先判斷女性聲線自然度。</p>
          <small>女性 Reference</small>
          <audio controls preload="none" style="width:100%;margin:6px 0 10px">
            <source src="${OFFICIAL_BASE}F01_%E4%B8%AD%E7%AB%8B_20054.wav" type="audio/wav">
          </audio>
          <small>CosyVoice2-Yue-Databaker 合成聲</small>
          <audio controls preload="none" style="width:100%;margin-top:6px">
            <source src="${OFFICIAL_BASE}9f24c7f95a2d040c43ce9fadfa56f6f3.wav" type="audio/wav">
          </audio>
        </article>
        <article class="voice-card">
          <div class="voice-name">Llasa-1B-Yue</div>
          <div class="voice-meta"><span>Neural Cantonese</span><span>Official sample</span><span>A-MOS 4.34/5</span></div>
          <p class="voice-note">官方評測中自然度約 4.34/5。呢段同下一張 CosyVoice2-Yue 用同一句，方便公平 A/B。</p>
          <audio controls preload="none" style="width:100%">
            <source src="${OFFICIAL_BASE}WSYue_TTS/common_voice_yue_39115507-common_voice_yue_39115508.wav" type="audio/wav">
          </audio>
        </article>
        <article class="voice-card">
          <div class="voice-name">CosyVoice2-Yue</div>
          <div class="voice-meta"><span>Neural Cantonese</span><span>Official sample</span><span>A-MOS 4.21/5</span></div>
          <p class="voice-note">官方評測自然度約 4.21/5；同 Llasa-1B-Yue 用相同測試句。</p>
          <audio controls preload="none" style="width:100%">
            <source src="${OFFICIAL_BASE}CosyVoice2-Yue/common_voice_yue_39115507-common_voice_yue_39115508.wav" type="audio/wav">
          </audio>
        </article>
        <article class="voice-card">
          <div class="voice-name">CosyVoice2-Yue-ZoengJyutGaai</div>
          <div class="voice-meta"><span>Storytelling fine-tune</span><span>Official sample</span><span>Natural Cantonese</span></div>
          <p class="voice-note">張悅楷粵語評書風格 fine-tune，較偏男聲 storytelling；保留作風格比較。</p>
          <audio controls preload="none" style="width:100%">
            <source src="${OFFICIAL_BASE}9%E6%9C%887%E6%97%A5.WAV" type="audio/wav">
          </audio>
        </article>
      </div>
      <p class="voice-legal">資料來源：ASLP-lab / WenetSpeech-Yue 官方 GitHub demo_page（Apache-2.0 repository）。女性卡係官方 F01 reference + 官方 synthetic output；佢代表「女性 reference conditioning」而唔係一個固定叫 Female 嘅獨立 model。eSpeak 已經從主要聲線清單移除，因為佢本質係機械式 formant TTS，唔適合作新聞朗讀。</p>`;

    research.parentNode.insertBefore(section, research);
  }

  document.addEventListener('DOMContentLoaded', addNeuralDemoSection);
  if (document.readyState !== 'loading') addNeuralDemoSection();
})();
