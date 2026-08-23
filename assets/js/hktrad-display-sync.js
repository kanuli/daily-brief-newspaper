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

  function buildLocalizer(data) {
    const baseRules = makeRules(data?.baseReplacements, "gi");
    const shortRules = makeRules(Object.entries(data?.shortAcronyms || {}), "g");
    const overrideRules = makeRules(data?.overrides, "gi");
    return (value) => {
      let out = String(value || "");
      for (const [pattern, target] of baseRules) out = out.replace(pattern, target);
      for (const [pattern, target] of shortRules) out = out.replace(pattern, target);
      for (const [pattern, target] of overrideRules) out = out.replace(pattern, target);
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
      window.HKTradDisplayMap = { policy: data.policy, localize, scan: (root = document) => scan(root, localize) };
    } catch (error) {
      console.warn("Shared HK Traditional Chinese display map unavailable; using embedded fallback", error);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
