(() => {
  "use strict";
  if (!("PerformanceObserver" in window) || !navigator.sendBeacon) return;

  const path = location.pathname.replace(/[^A-Za-z0-9_./-]/g, "").slice(0, 200) || "/";
  const width = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
  const device = width < 768 ? "mobile" : (width < 1100 ? "tablet" : "desktop");
  const values = new Map();

  function record(metric, value) {
    if (!Number.isFinite(value) || value < 0) return;
    values.set(metric, value);
  }

  try {
    const nav = performance.getEntriesByType("navigation")[0];
    if (nav) record("TTFB", Math.max(0, nav.responseStart - nav.requestStart));
  } catch (_) {}

  try {
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (last) record("LCP", last.startTime);
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch (_) {}

  try {
    let cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) cls += entry.value || 0;
      }
      record("CLS", cls);
    }).observe({ type: "layout-shift", buffered: true });
  } catch (_) {}

  try {
    let maxDuration = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.interactionId && entry.duration > maxDuration) maxDuration = entry.duration;
      }
      if (maxDuration) record("INP", maxDuration);
    }).observe({ type: "event", durationThreshold: 40, buffered: true });
  } catch (_) {}

  try {
    new PerformanceObserver((list) => {
      const first = list.getEntries()[0];
      if (first) record("FCP", first.startTime);
    }).observe({ type: "paint", buffered: true });
  } catch (_) {}

  function flush() {
    for (const [metric, value] of values) {
      const blob = new Blob([JSON.stringify({ metric, value, path, device })], { type: "application/json" });
      navigator.sendBeacon("/api/v2/vitals", blob);
    }
    values.clear();
  }

  addEventListener("pagehide", flush, { once: true });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
})();
