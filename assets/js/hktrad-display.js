(() => {
  "use strict";

  // Legacy compatibility shim only.
  //
  // Visible-news localization is now owned exclusively by
  // hktrad-display-sync.js + data/hktrad-localization.json, which are generated
  // from the same Hong Kong mixed-language terminology policy as production
  // Cantonese TTS.
  //
  // This file intentionally performs NO text replacement.  Older cached
  // versions contained forced translations such as:
  //   OpenAI  -> 開放人工智能公司
  //   ChatGPT -> 人工智能聊天機械人
  // Those translations are not normal Hong Kong newsroom usage and must never
  // be reintroduced as a fallback.  If the shared map is unavailable, the safe
  // behaviour is to preserve the newsroom source wording unchanged.

  window.HKTradLegacyDisplay = {
    retired: true,
    policy: "source-wording-safe-fallback; shared-hk-mixed-language-map-authoritative",
  };
})();
