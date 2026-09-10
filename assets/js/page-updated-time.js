(() => {
  "use strict";

  const PAGE = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  const DESK_PAGES = new Set([
    "index.html", "world.html", "asia.html", "hong-kong.html", "japan.html",
    "finance.html", "technology.html", "manga-anime.html", "manchester-united.html", "football.html"
  ]);

  function formatHkt(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat("zh-HK", {
      timeZone: "Asia/Hong_Kong",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date) + " HKT";
  }

  async function fetchJson(path) {
    const url = new URL(path, document.baseURI);
    url.searchParams.set("v", String(Date.now()));
    const response = await fetch(url.href, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path} HTTP ${response.status}`);
    return response.json();
  }

  async function resolveTimestamp() {
    if (PAGE === "live.html") {
      const data = await fetchJson("data/live.json");
      return { label: "最後 Live 更新", value: data.lastUpdated || data.generatedAt };
    }
    if (PAGE === "stocks.html") {
      const data = await fetchJson("data/stocks-latest.json");
      return { label: "最後檢查", value: data.lastCheckedAt || data.generatedAt };
    }
    if (PAGE === "retail-deals.html") {
      const data = await fetchJson("data/retail-deals.json");
      return { label: "最後資料更新", value: data.generatedAt };
    }
    if (PAGE === "archive.html") {
      try {
        const data = await fetchJson("data/archive.json");
        if (data.generatedAt || data.lastUpdated) {
          return { label: "最後內容更新", value: data.generatedAt || data.lastUpdated };
        }
      } catch (_) {
        // Fall through to the current rolling desk timestamp.
      }
    }
    if (DESK_PAGES.has(PAGE) || PAGE === "archive.html") {
      const data = await fetchJson("data/desk-latest.json");
      return { label: "最後內容更新", value: data.generatedAt };
    }
    return null;
  }

  function mount(label, value) {
    const utility = document.querySelector(".utility-bar");
    if (!utility || !value) return;

    let target = PAGE === "retail-deals.html" ? document.getElementById("retail-checked") : null;
    if (!target) {
      target = utility.querySelector("[data-page-updated-time]");
      if (!target) {
        target = document.createElement("span");
        target.setAttribute("data-page-updated-time", "true");
        utility.appendChild(target);
      }
    }
    target.textContent = `${label}：${formatHkt(value)}`;
    target.style.marginLeft = "auto";
    target.style.fontWeight = "700";
    target.style.whiteSpace = "nowrap";
  }

  async function init() {
    try {
      const resolved = await resolveTimestamp();
      if (resolved) mount(resolved.label, resolved.value);
    } catch (error) {
      console.warn("Page update timestamp unavailable", error);
    }
  }

  // ============================================================
  // Idle Auto Reload
  //
  // A page becomes reload-eligible after 30 minutes without genuine
  // user activity. Reload is still blocked while the visitor is using
  // media, an editor/form, an open overlay, or has just returned to the
  // page. Once eligible, blocked pages recheck every minute instead of
  // restarting the full idle period.
  // ============================================================

  const IDLE_RELOAD_FLAG = "__dailyBriefIdleAutoReloadInitialized";
  const IDLE_RELOAD_IDLE_MS = 30 * 60 * 1000;
  const IDLE_RELOAD_RECHECK_MS = 60 * 1000;
  const IDLE_RELOAD_RETURN_GRACE_MS = 2 * 60 * 1000;
  const IDLE_RELOAD_ACTIVITY_THROTTLE_MS = 1000;

  function initIdleAutoReload() {
    if (window[IDLE_RELOAD_FLAG]) return;
    window[IDLE_RELOAD_FLAG] = true;

    let lastActivity = Date.now();
    let lastForegroundAt = Date.now();
    let reloadPending = false;
    let checkTimer = null;
    let lastHighFrequencyUpdate = 0;

    function clearCheckTimer() {
      if (checkTimer !== null) {
        window.clearTimeout(checkTimer);
        checkTimer = null;
      }
    }

    function scheduleNextCheck() {
      clearCheckTimer();

      const idleFor = Date.now() - lastActivity;
      const remaining = Math.max(IDLE_RELOAD_IDLE_MS - idleFor, 1000);
      checkTimer = window.setTimeout(checkIdleState, remaining);
    }

    function markActivity() {
      lastActivity = Date.now();
      reloadPending = false;
      scheduleNextCheck();
    }

    function markHighFrequencyActivity() {
      const now = Date.now();
      if (now - lastHighFrequencyUpdate < IDLE_RELOAD_ACTIVITY_THROTTLE_MS) return;
      lastHighFrequencyUpdate = now;
      markActivity();
    }

    function isTypingOrEditing() {
      const el = document.activeElement;
      if (!el) return false;

      const tag = el.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
      return Boolean(el.isContentEditable);
    }

    function isMediaPlaying() {
      return Array.from(document.querySelectorAll("audio, video")).some((item) => (
        !item.paused && !item.ended
      ));
    }

    function isOverlayOpen() {
      const selectors = [
        "dialog[open]",
        '[role="dialog"][aria-modal="true"]',
        ".modal.show",
        ".modal.is-open",
        ".modal.open",
        ".dialog.open",
        ".dialog.is-open",
        ".menu.open",
        ".menu.show",
        ".dropdown-menu.show",
        ".offcanvas.show",
        '[aria-expanded="true"][aria-haspopup]',
        '[data-state="open"]'
      ];

      return selectors.some((selector) => {
        try {
          return document.querySelector(selector) !== null;
        } catch (_) {
          return false;
        }
      });
    }

    function justReturnedToPage() {
      if (document.visibilityState !== "visible") return false;
      return Date.now() - lastForegroundAt < IDLE_RELOAD_RETURN_GRACE_MS;
    }

    function isSafeToReload() {
      if (isMediaPlaying()) return false;
      if (isTypingOrEditing()) return false;
      if (isOverlayOpen()) return false;
      if (justReturnedToPage()) return false;
      return true;
    }

    function checkIdleState() {
      checkTimer = null;

      const idleFor = Date.now() - lastActivity;
      if (idleFor < IDLE_RELOAD_IDLE_MS) {
        reloadPending = false;
        scheduleNextCheck();
        return;
      }

      reloadPending = true;

      if (isSafeToReload()) {
        window.location.reload();
        return;
      }

      checkTimer = window.setTimeout(checkIdleState, IDLE_RELOAD_RECHECK_MS);
    }

    const immediateActivityEvents = [
      "mousedown",
      "click",
      "keydown",
      "pointerdown",
      "touchstart",
      "input",
      "change",
      "contextmenu"
    ];

    const highFrequencyActivityEvents = [
      "mousemove",
      "pointermove",
      "scroll",
      "touchmove"
    ];

    immediateActivityEvents.forEach((eventName) => {
      window.addEventListener(eventName, markActivity, {
        passive: eventName !== "keydown" && eventName !== "input" && eventName !== "change"
      });
    });

    highFrequencyActivityEvents.forEach((eventName) => {
      window.addEventListener(eventName, markHighFrequencyActivity, { passive: true });
    });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        lastForegroundAt = Date.now();

        // Returning to the tab does not reset the original 30-minute idle
        // clock. If reload was already pending, only add the short grace.
        if (reloadPending) {
          clearCheckTimer();
          checkTimer = window.setTimeout(checkIdleState, IDLE_RELOAD_RETURN_GRACE_MS);
        }
        return;
      }

      // A background tab keeps its existing idle clock and may refresh once
      // the threshold is reached, as long as the safety gate allows it.
      scheduleNextCheck();
    });

    window.addEventListener("focus", () => {
      lastForegroundAt = Date.now();

      if (reloadPending) {
        clearCheckTimer();
        checkTimer = window.setTimeout(checkIdleState, IDLE_RELOAD_RETURN_GRACE_MS);
      }
    });

    window.addEventListener("blur", scheduleNextCheck);

    scheduleNextCheck();
  }

  initIdleAutoReload();

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
