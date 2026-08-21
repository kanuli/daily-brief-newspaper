(() => {
  "use strict";
  const desired = '每日從詞庫抽選 10 個字；按 <strong>🔊</strong> 可播放預錄發音';
  function apply() {
    const intro = document.querySelector('.daily-vocab-intro');
    if (!intro) return false;
    if (intro.innerHTML !== desired) intro.innerHTML = desired;
    return true;
  }
  [0, 200, 600, 1200, 2500, 5000].forEach((delay) => setTimeout(apply, delay));
})();
