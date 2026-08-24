(() => {
  "use strict";

  const MANIFEST_URL = "data/tts-manifest.json";
  const POLICY = "f01-news-anchor-v14-young-female-semantic-sentences-hktrad";
  const REF_POLICY = "aslp-approved-databaker-female-synthetic-v1";
  const REF_ASSET = "9f24c7f95a2d040c43ce9fadfa56f6f3.wav";
  const CONDITIONING = "approved-young-female-synthetic-per-semantic-sentence";
  const SEGMENT_POLICY = "semantic-sentence-reference-locked";
  const INFERENCE_MODE = "cross-lingual-reference-only-per-semantic-sentence";
  const PACING = "hk-tv-news-semantic-pauses-v3-conservative";
  const TEMPO = "model-speed-only-no-post-stretch";
  const NAMESPACE = "-v14-";
  const SPEED = 1.0;
  const REF_SECONDS = 8;
  const READY = "🔊 廣東話朗讀";
  const STOP = "■ 停止朗讀";
  const PENDING = "⏳ F01 音訊準備中";
  const REFRESH_MS = 15000;

  let manifest = null;
  let activeButton = null;
  let refreshQueued = false;
  let timer = null;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const clean = (v) => String(v || "").replace(/\s+/g, " ").trim();

  function validEntry(e) {
    const segments = Number(e?.segmentCount || 0);
    return !!(e?.audio && String(e.audio).includes(NAMESPACE) &&
      e.prosodyPolicy === POLICY && e.referencePolicy === REF_POLICY &&
      e.referenceAsset === REF_ASSET && e.initialConditioningPolicy === CONDITIONING &&
      e.languageGate === "residual-latin-zero" && e.segmentPolicy === SEGMENT_POLICY &&
      e.inferenceMode === INFERENCE_MODE && e.instructionPolicy === "instruct2-cantonese-control-not-spoken" &&
      e.pacingPolicy === PACING && e.tempoPolicy === TEMPO &&
      Number(e.referenceStartSeconds) === 0 && Number(e.referenceDurationSeconds) === REF_SECONDS &&
      Number(e.speed) === SPEED && segments >= 1 && Number(e.semanticUnitCount || segments) === segments);
  }

  function validManifest(m) {
    return !!(m?.engine === "ASLP-lab/Cosyvoice2-Yue" && m?.language === "yue-HK" &&
      m?.prosodyPolicy === POLICY && m?.referencePolicy === REF_POLICY &&
      m?.referenceAsset === REF_ASSET && m?.initialConditioningPolicy === CONDITIONING &&
      m?.segmentPolicy === SEGMENT_POLICY && m?.inferenceMode === INFERENCE_MODE &&
      m?.instructionPolicy === "instruct2-cantonese-control-not-spoken" &&
      m?.pacingPolicy === PACING && m?.tempoPolicy === TEMPO &&
      Number(m?.referenceStartSeconds) === 0 && Number(m?.referenceDurationSeconds) === REF_SECONDS && Number(m?.speed) === SPEED);
  }

  function ensureUi() {
    if (!$("#site-tts-v14-style")) {
      const style = document.createElement("style");
      style.id = "site-tts-v14-style";
      style.textContent = `.site-tts-controls{display:flex;gap:8px;margin:10px 0}.site-tts-button{border:1px solid #222;background:#fff;color:#111;padding:7px 10px;font:700 12px/1.2 "Noto Sans TC",sans-serif;cursor:pointer;border-radius:3px}.site-tts-button:disabled{opacity:.58;cursor:default;background:#eee;color:#555}.site-tts-button[data-speaking="true"]{background:#111;color:#fff}#site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}#site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}`;
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">CosyVoice2-Yue · 年輕女聲 · v14</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="metadata" playsinline></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
      $("#site-tts-audio")?.addEventListener("ended", finish);
    }
  }

  function status(text, open = true) { ensureUi(); $("#site-tts-player").dataset.open = open ? "true" : "false"; $("#site-tts-status").textContent = text; }
  function resetButton(button) { if (!button) return; button.dataset.speaking = "false"; button.textContent = READY; }
  function finish() { resetButton(activeButton); activeButton = null; status("朗讀完成。", false); }
  function stopAll() {
    const audio = $("#site-tts-audio");
    if (audio) { try { audio.pause(); } catch (_) {} try { audio.currentTime = 0; } catch (_) {} audio.removeAttribute("src"); audio.dataset.ready = "false"; try { audio.load(); } catch (_) {} }
    resetButton(activeButton); activeButton = null; status("朗讀已停止。", false);
  }

  function titleOf(article) { return clean($("h1,h2,h3", article)?.textContent); }
  function findEntry(article) {
    const title = titleOf(article);
    if (!title || !manifest?.articles) return null;
    return Object.values(manifest.articles).find((e) => validEntry(e) && clean(e.title) === title) || null;
  }
  function audioUrl(entry) {
    const url = new URL(entry.audio, document.baseURI);
    url.searchParams.set("voicev", encodeURIComponent(`${entry.prosodyPolicy}|${entry.publishedAt || ""}|${entry.contentSha256 || ""}`));
    return url.href;
  }
  function play(entry, button = null) {
    if (!validEntry(entry)) return false;
    if (activeButton === button && button?.dataset.speaking === "true") { stopAll(); return true; }
    stopAll(); ensureUi();
    const audio = $("#site-tts-audio");
    audio.src = audioUrl(entry); audio.dataset.ready = "true"; activeButton = button;
    if (button) { button.dataset.speaking = "true"; button.textContent = STOP; }
    status("使用中：年輕女聲 · v14 語意分句廣東話新聞節奏");
    audio.play()?.catch?.((error) => { console.warn("F01 v14 playback rejected", error); finish(); });
    return true;
  }

  function configure(article) {
    if (!(article instanceof Element) || article.tagName !== "ARTICLE" || !article.closest("main")) return;
    if (article.closest(".study-desk,[data-no-tts]") || !titleOf(article)) return;
    let button = $(".site-tts-button", article);
    if (!button) {
      const wrap = document.createElement("div"); wrap.className = "site-tts-controls";
      button = document.createElement("button"); button.type = "button"; button.className = "site-tts-button"; wrap.appendChild(button);
      const heading = $("h1,h2,h3", article);
      if (heading?.nextSibling) heading.parentNode.insertBefore(wrap, heading.nextSibling); else article.prepend(wrap);
    }
    if (button === activeButton && button.dataset.speaking === "true") return;
    const entry = findEntry(article);
    button.onclick = null; button.dataset.speaking = "false";
    if (validEntry(entry)) {
      button.disabled = false; button.textContent = READY;
      button.title = "年輕女聲 · v14 · 語意分句逐段粵語生成 · 新聞主播停頓";
      button.onclick = () => play(entry, button);
    } else {
      button.disabled = true; button.textContent = PENDING;
      button.title = "只播放v14語意分句、逐段粵語鎖定的音訊。";
    }
  }

  function refreshButtons() { $$("main article").forEach(configure); }
  function containsArticle(node) { return node instanceof Element && (node.matches("article") || !!node.querySelector("article")); }
  function queueRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    (window.requestAnimationFrame || ((cb) => setTimeout(cb, 0)))(() => { refreshQueued = false; refreshButtons(); });
  }
  async function refreshManifest() {
    try {
      const url = new URL(MANIFEST_URL, document.baseURI); url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
      const fresh = await response.json(); manifest = validManifest(fresh) ? fresh : null;
    } catch (error) { console.warn("F01 v14 manifest unavailable", error); manifest = null; }
    refreshButtons();
  }
  function leadEntry() {
    if (!manifest?.articles) return null;
    if (manifest.leadId && validEntry(manifest.articles[manifest.leadId])) return manifest.articles[manifest.leadId];
    return Object.values(manifest.articles).find((e) => validEntry(e) && clean(e.title) === clean(manifest.leadTitle)) || null;
  }

  window.SiteTTS = { playLeadFromUserGesture() { const entry = leadEntry(); return validEntry(entry) ? play(entry) : false; }, stop: stopAll, isReady() { return true; } };
  function boot() {
    ensureUi(); refreshButtons(); refreshManifest();
    if (timer) clearInterval(timer); timer = setInterval(refreshManifest, REFRESH_MS);
    new MutationObserver((mutations) => { if (mutations.some((m) => [...m.addedNodes].some(containsArticle))) queueRefresh(); }).observe(document.body, { childList: true, subtree: true });
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refreshManifest(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true }); else boot();
})();
