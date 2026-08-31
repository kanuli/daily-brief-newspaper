(() => {
  "use strict";

  const MAP_URL = "data/hktrad-localization.json";
  const SKIP = "a,script,style,code,pre,.source-link,.topic-sources,.story-meta,[data-no-hktrad-display]";
  const escapeRegExp = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  function makeRules(pairs, flags = "gi") {
    return [...(pairs || [])]
      .sort((a, b) => String(b?.[0] || "").length - String(a?.[0] || "").length)
      .filter((item) => Array.isArray(item) && item.length >= 2 && item[0])
      .map(([source, target]) => [
        new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(source)}(?![A-Za-z0-9])`, flags),
        String(target || ""),
      ]);
  }

  function makeUnitRules(pairs) {
    return [...(pairs || [])]
      .sort((a, b) => String(b?.[0] || "").length - String(a?.[0] || "").length)
      .filter((item) => Array.isArray(item) && item.length >= 2 && item[0])
      .map(([source, target]) => [
        // Units are commonly attached directly to digits, e.g. 2nm. Only
        // alphabetic neighbours block the replacement.
        new RegExp(`(?<![A-Za-z])${escapeRegExp(source)}(?![A-Za-z])`, "gi"),
        String(target || ""),
      ]);
  }

  function makePreserveRules(terms) {
    return [...new Set((terms || []).map((term) => String(term || "").trim()).filter(Boolean))]
      .sort((a, b) => b.length - a.length)
      .map((term) => new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(term)}(?![A-Za-z0-9])`, "gi"));
  }

  function buildLocalizer(data) {
    const baseRules = makeRules(data?.baseReplacements, "gi");
    const shortRules = makeRules(Object.entries(data?.shortAcronyms || {}), "g");
    const overrideRules = makeRules(data?.overrides, "gi");
    const unitRules = makeUnitRules(data?.unitReplacements);
    const preserveRules = makePreserveRules(data?.preserveOfficialEnglish);

    return (value) => {
      let out = String(value || "");
      const restored = [];

      // Protect official English names before any general replacement runs.
      // This prevents substring rules such as App / Store / Digital / Markets
      // from damaging Hong Kong-normal names such as App Store or OpenAI.
      for (const pattern of preserveRules) {
        out = out.replace(pattern, (match) => {
          const marker = String.fromCharCode(0xE000 + restored.length);
          restored.push([marker, match]);
          return marker;
        });
      }

      for (const [pattern, target] of baseRules) out = out.replace(pattern, target);
      for (const [pattern, target] of shortRules) out = out.replace(pattern, target);
      for (const [pattern, target] of overrideRules) out = out.replace(pattern, target);
      for (const [pattern, target] of unitRules) out = out.replace(pattern, target);
      for (const [marker, original] of restored) out = out.replaceAll(marker, original);
      return out;
    };
  }

  function processNode(node, localize) {
    if (!node || node.nodeType !== Node.TEXT_NODE || !node.parentElement) return;
    if (!node.nodeValue || !/[A-Za-z\u00C0-\u024F]/.test(node.nodeValue)) return;
    if (node.parentElement.closest(SKIP)) return;
    const next = localize(node.nodeValue);
    if (next !== node.nodeValue) node.nodeValue = next;
  }

  function scan(root, localize) {
    const articles = [];
    if (root?.nodeType === Node.ELEMENT_NODE && root.matches?.("main article")) articles.push(root);
    else (root?.querySelectorAll?.("main article") || []).forEach((article) => articles.push(article));
    for (const article of articles) {
      const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) processNode(walker.currentNode, localize);
    }
  }

  async function boot() {
    try {
      const response = await fetch(`${MAP_URL}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HKTrad map HTTP ${response.status}`);
      const data = await response.json();
      const localize = buildLocalizer(data);
      scan(document, localize);
      const main = document.querySelector("main") || document.body;
      const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          if (mutation.type === "characterData") processNode(mutation.target, localize);
          for (const node of mutation.addedNodes || []) {
            if (node.nodeType === Node.TEXT_NODE) processNode(node, localize);
            else if (node.nodeType === Node.ELEMENT_NODE) scan(node, localize);
          }
        }
      });
      observer.observe(main, { childList: true, subtree: true, characterData: true });
      window.HKTradDisplayMap = {
        policy: data.policy,
        preserveOfficialEnglish: data.preserveOfficialEnglish || [],
        localize,
        scan: (root = document) => scan(root, localize),
      };
    } catch (error) {
      // Safe failure mode: keep the source newsroom wording. Never fall back to
      // an older forced-translation table that can corrupt official names.
      console.warn("Shared HK mixed-language display map unavailable; source wording preserved", error);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();