(() => {
  "use strict";
  if (document.querySelector('script[data-site-tts-v5-compat]')) return;
  const script = document.createElement("script");
  script.src = "assets/js/site-tts-v5.js?v=20260822-cosy2only1";
  script.defer = true;
  script.setAttribute("data-site-tts-v5-compat", "true");
  document.head.appendChild(script);
})();
