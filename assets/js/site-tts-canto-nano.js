(() => {
  "use strict";

  const scriptUrl = (() => {
    try { return new URL(document.currentScript?.src || "", document.baseURI); }
    catch (_) { return null; }
  })();
  const SITE_ROOT = scriptUrl ? new URL("../../", scriptUrl) : new URL("./", document.baseURI);
  const MANIFEST_URL = new URL("data/tts-manifest.json", SITE_ROOT).href;
  const ENGINE = "typangaa/canto-tts-nano";
  const ENGINE_VERSION = "canto-tts-nano-v1";
  const VOICE = "verified-female-reference";
  const POLICY = "canto-nano-female-hk-news-anchor-v1";
  const SPEAKER = "runtime-ref-audio-voice-clone-verified";
  const REF_ASSET = "9f24c7f95a2d040c43ce9fadfa56f6f3.wav";
  const PRON = "jyutping-tone-cantonese-first";
  const PACING = "hk-tv-news-semantic-pauses-v1";
  const TARGET = "RYTsc9N5748@04:19-05:00";
  const SEGMENT = "semantic-completeness-breathing-audience-processing";
  const TEMPO = "native-model-rate-no-post-stretch";
  const QUALITY = "duration_filter";
  const MODE = "full";
  const ASSET_NAMESPACE = "cnf4";
  const LANGUAGE_GATE = "hk-cantonese-english-codeswitch-allowed";
  const READY = "🔊 廣東話朗讀";
  const STOP = "■ 停止朗讀";
  const PENDING = "⏳ 廣東話女聲準備中";
  const REFRESH_MS = 15000;

  let manifest = null, activeButton = null, refreshQueued = false, timer = null;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const clean = (v) => String(v || "").replace(/\s+/g, " ").trim();

  function validEntry(e) {
    const segments = Number(e?.segmentCount || 0);
    return !!(e?.audio && String(e.audio).includes(`-${ASSET_NAMESPACE}-`) &&
      e.prosodyPolicy === POLICY && e.engineVersion === ENGINE_VERSION &&
      e.speakerMode === SPEAKER && e.referenceAsset === REF_ASSET &&
      e.pronunciationPolicy === PRON && e.languageGate === LANGUAGE_GATE &&
      e.segmentPolicy === SEGMENT && e.pacingPolicy === PACING &&
      e.pacingTarget === TARGET && e.tempoPolicy === TEMPO &&
      e.quality === QUALITY && e.sampleMode === MODE &&
      e.contentCoveragePolicy === "full-visible-article-no-truncation-v1" &&
      e.contentComplete === true &&
      segments >= 1 && Number(e.semanticUnitCount || segments) === segments &&
      e.femalePromptCodesSha256 && e.defaultPromptCodesSha256 &&
      e.femalePromptCodesSha256 !== e.defaultPromptCodesSha256);
  }

  function validManifest(m) {
    return !!(m?.engine === ENGINE && m?.engineVersion === ENGINE_VERSION &&
      m?.voice === VOICE && m?.language === "yue-HK" &&
      m?.prosodyPolicy === POLICY && m?.speakerMode === SPEAKER &&
      m?.referenceAsset === REF_ASSET && m?.pronunciationPolicy === PRON &&
      m?.segmentPolicy === SEGMENT && m?.pacingPolicy === PACING &&
      m?.pacingTarget === TARGET && m?.tempoPolicy === TEMPO &&
      m?.quality === QUALITY && m?.sampleMode === MODE &&
      m?.assetNamespace === ASSET_NAMESPACE);
  }

  function ensureUi() {
    if (!$("#site-tts-canto-nano-style")) {
      const style = document.createElement("style");
      style.id = "site-tts-canto-nano-style";
      style.textContent = `.site-tts-controls{display:flex;gap:8px;margin:10px 0}.site-tts-button{border:1px solid #222;background:#fff;color:#111;padding:7px 10px;font:700 12px/1.2 "Noto Sans TC",sans-serif;cursor:pointer;border-radius:3px}.site-tts-button:disabled{opacity:.58;cursor:default;background:#eee;color:#555}.site-tts-button[data-speaking="true"]{background:#111;color:#fff}#site-tts-player{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:9998;width:min(680px,calc(100% - 24px));background:#111;color:#fff;border:1px solid #444;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.28);display:none}#site-tts-player[data-open="true"]{display:block}.site-tts-player-row{display:flex;align-items:center;gap:10px}.site-tts-status{flex:1;font:700 12px/1.35 "Noto Sans TC",sans-serif}.site-tts-stop{border:1px solid #777;background:#222;color:#fff;padding:6px 9px;cursor:pointer}.site-tts-audio{width:100%;margin-top:8px;display:none}.site-tts-audio[data-ready="true"]{display:block}`;
      document.head.appendChild(style);
    }
    if (!$("#site-tts-player")) {
      const panel = document.createElement("div");
      panel.id = "site-tts-player";
      panel.dataset.open = "false";
      panel.innerHTML = '<div class="site-tts-player-row"><div class="site-tts-status" id="site-tts-status">canto-tts-nano · verified female · HK mixed-language news pacing</div><button type="button" class="site-tts-stop" id="site-tts-stop">■ 停止</button></div><audio class="site-tts-audio" id="site-tts-audio" controls preload="metadata" playsinline></audio>';
      document.body.appendChild(panel);
      $("#site-tts-stop")?.addEventListener("click", stopAll);
      $("#site-tts-audio")?.addEventListener("ended", finish);
    }
  }

  function status(text, open = true) {
    ensureUi();
    $("#site-tts-player").dataset.open = open ? "true" : "false";
    $("#site-tts-status").textContent = text;
  }
  function resetButton(b) {
    if (!b) return;
    b.dataset.speaking = "false";
    b.textContent = READY;
  }
  function finish() { resetButton(activeButton); activeButton = null; status("朗讀完成。", false); }
  function stopAll() {
    const a = $("#site-tts-audio");
    if (a) {
      try { a.pause(); } catch (_) {}
      try { a.currentTime = 0; } catch (_) {}
      a.removeAttribute("src"); a.dataset.ready = "false";
      try { a.load(); } catch (_) {}
    }
    resetButton(activeButton); activeButton = null; status("朗讀已停止。", false);
  }

  function titleOf(article) { return clean($("h1,h2,h3", article)?.textContent); }
  function cjkKey(value) {
    return clean(value).normalize("NFKC").toLowerCase()
      .replace(/[a-z][a-z0-9+./:&'’_-]*/gi, "")
      .replace(/[^\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}0-9]/gu, "");
  }
  function bigrams(value) {
    const s = cjkKey(value), out = new Set();
    for (let i = 0; i < s.length - 1; i++) out.add(s.slice(i, i + 2));
    return out;
  }
  function similarity(a, b) {
    const ca = clean(a), cb = clean(b);
    if (!ca || !cb) return 0;
    if (ca === cb) return 1;
    const ak = cjkKey(ca), bk = cjkKey(cb);
    if (!ak || !bk) return 0;
    if (ak === bk) return 1;
    if (Math.min(ak.length, bk.length) >= 6 && (ak.includes(bk) || bk.includes(ak))) return 0.98;
    const A = bigrams(ak), B = bigrams(bk);
    if (!A.size || !B.size) return 0;
    let hit = 0; A.forEach((x) => { if (B.has(x)) hit += 1; });
    return hit / Math.min(A.size, B.size);
  }
  function findEntry(article) {
    if (!manifest?.articles) return null;
    const explicitId = clean(article.dataset.articleId || article.getAttribute("data-article-id") || "");
    if (explicitId && validEntry(manifest.articles[explicitId])) return manifest.articles[explicitId];
    const title = titleOf(article);
    if (!title) return null;
    const entries = Object.values(manifest.articles).filter(validEntry);
    const exact = entries.find((e) => clean(e.title) === title);
    if (exact) return exact;
    const ranked = entries.map((entry) => ({ entry, score: similarity(entry.title, title) }))
      .filter((x) => x.score >= 0.82)
      .sort((a, b) => b.score - a.score);
    if (!ranked.length) return null;
    if (ranked[0].score >= 0.95) return ranked[0].entry;
    if (ranked.length === 1 || ranked[0].score - ranked[1].score >= 0.12) return ranked[0].entry;
    return null;
  }

  function audioUrl(entry) {
    const url = new URL(entry.audio, SITE_ROOT);
    url.searchParams.set("voicev", `${entry.prosodyPolicy}|${entry.publishedAt || ""}|${entry.contentSha256 || ""}`);
    return url.href;
  }
  function play(entry, button = null) {
    if (!validEntry(entry)) return false;
    if (activeButton === button && button?.dataset.speaking === "true") { stopAll(); return true; }
    stopAll(); ensureUi();
    const audio = $("#site-tts-audio");
    audio.src = audioUrl(entry); audio.dataset.ready = "true"; activeButton = button;
    if (button) { button.dataset.speaking = "true"; button.textContent = STOP; }
    status("使用中：canto-tts-nano 年輕女聲 · 香港廣東話／英文自然混讀");
    const p = audio.play();
    if (p?.catch) p.catch((error) => {
      console.warn("canto nano playback rejected", error);
      status("音檔已存在，但瀏覽器未能播放。請再按一次播放。", true);
      resetButton(activeButton); activeButton = null;
    });
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
      button.disabled = false; button.textContent = READY; button.dataset.ttsState = "ready";
      button.title = "canto-tts-nano verified female · HK Cantonese-English mixed-language playback";
      button.onclick = () => play(entry, button);
    } else {
      button.disabled = true; button.textContent = PENDING; button.dataset.ttsState = "pending";
      button.title = "目前文章尚未有對應的 cnf4 廣東話音檔；系統會自動重新檢查。";
    }
  }

  function refreshButtons() { $$("main article").forEach(configure); }
  function queueRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    (window.requestAnimationFrame || ((cb) => setTimeout(cb, 0)))(() => { refreshQueued = false; refreshButtons(); });
  }
  async function refreshManifest() {
    try {
      const url = new URL(MANIFEST_URL); url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
      const fresh = await response.json();
      manifest = validManifest(fresh) ? fresh : null;
      window.dispatchEvent(new CustomEvent("site-tts-manifest", { detail: { valid: !!manifest, namespace: fresh?.assetNamespace || null } }));
    } catch (error) {
      console.warn("canto nano manifest unavailable", error); manifest = null;
    }
    refreshButtons();
  }
  function leadEntry() {
    if (!manifest?.articles) return null;
    if (manifest.leadId && validEntry(manifest.articles[manifest.leadId])) return manifest.articles[manifest.leadId];
    return Object.values(manifest.articles).find((e) => validEntry(e) && clean(e.title) === clean(manifest.leadTitle)) || null;
  }

  window.SiteTTS = {
    playLeadFromUserGesture() { const e = leadEntry(); return validEntry(e) ? play(e) : false; },
    stop: stopAll,
    isReady() { return !!manifest; },
    manifestNamespace() { return manifest?.assetNamespace || null; }
  };
  function boot() {
    ensureUi(); refreshButtons(); refreshManifest();
    if (timer) clearInterval(timer); timer = setInterval(refreshManifest, REFRESH_MS);
    new MutationObserver(() => queueRefresh()).observe(document.body, { childList: true, subtree: true });
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refreshManifest(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true }); else boot();
})();
