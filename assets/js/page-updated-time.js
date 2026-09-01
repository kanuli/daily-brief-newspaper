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

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
