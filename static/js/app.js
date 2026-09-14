const $ = (selector) => document.querySelector(selector);


/* Persistent dark/light theme with system fallback. */
(() => {
  const root = document.documentElement;
  const buttons = [document.querySelector('#theme-toggle'), document.querySelector('#theme-toggle-mobile')].filter(Boolean);
  if (!buttons.length) return;
  const stored = localStorage.getItem('infinity-theme');
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const apply = (theme) => {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    localStorage.setItem('infinity-theme', theme);
    buttons.forEach((button) => {
      const isDark = theme === 'dark';
      button.setAttribute('aria-pressed', String(isDark));
      button.querySelector('[aria-hidden="true"]')?.replaceChildren(document.createTextNode(isDark ? '☾' : '☼'));
    });
  };
  apply(stored === 'dark' || stored === 'light' ? stored : (systemDark ? 'dark' : 'light'));
  buttons.forEach((button) => button.addEventListener('click', () => apply(root.dataset.theme === 'dark' ? 'light' : 'dark')));
})();
const $$ = (selector) => [...document.querySelectorAll(selector)];

const menuToggle = $(".menu-toggle");
const mobileNav = $("#mobile-nav");
if (menuToggle && mobileNav) {
  menuToggle.addEventListener("click", () => {
    const open = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!open));
    mobileNav.hidden = open;
  });
}

const toolGrid = $("#tool-list") || $("#listing-grid");
const cards = toolGrid ? [...toolGrid.querySelectorAll(".tool-card")] : [];
const emptyState = $("#empty-state") || $("#listing-empty");
const search = $("#tool-search") || $("#listing-search");
const filterTabs = $$(".filter-tabs [data-filter]");
let selectedFilter = toolGrid?.dataset.activeFilter || "all";

function filterCards() {
  if (!cards.length) return;
  const query = search ? search.value.trim().toLowerCase() : "";
  selectedFilter = toolGrid?.dataset.activeFilter || selectedFilter;
  let visible = 0;
  cards.forEach((card) => {
    const text = (card.dataset.search || "").toLowerCase();
    const category = card.dataset.category || "";
    const matchesFilter = selectedFilter === "all"
      || (selectedFilter === "popular" ? card.dataset.popular === "true" : category === selectedFilter);
    card.hidden = !text.includes(query) || !matchesFilter;
    if (!card.hidden) visible += 1;
    const title = card.querySelector("h3, h2");
    if (title && title.dataset.originalTitle) {
      const original = title.dataset.originalTitle;
      const index = query ? original.toLowerCase().indexOf(query) : -1;
      title.replaceChildren();
      if (index < 0) title.textContent = original;
      else {
        title.append(document.createTextNode(original.slice(0, index)));
        const mark = document.createElement("mark");
        mark.textContent = original.slice(index, index + query.length);
        title.append(mark, document.createTextNode(original.slice(index + query.length)));
      }
    }
  });
  if (emptyState) emptyState.hidden = visible > 0;
}
cards.forEach((card) => {
  const title = card.querySelector("h3, h2");
  if (title) title.dataset.originalTitle = title.textContent;
});
if (search) search.addEventListener("input", filterCards);
filterTabs.forEach((tab) => tab.addEventListener("click", () => {
  selectedFilter = tab.dataset.filter;
  if (toolGrid) toolGrid.dataset.activeFilter = selectedFilter;
  filterTabs.forEach((item) => item.classList.toggle("is-active", item === tab));
  filterCards();
}));
filterCards();

const categoryLinks = $$(".category-dock [data-filter]");
categoryLinks.forEach((link) => link.addEventListener("click", () => {
  if (!cards.some((card) => card.dataset.category === link.dataset.filter)) return;
  selectedFilter = link.dataset.filter;
  if (toolGrid) toolGrid.dataset.activeFilter = selectedFilter;
  categoryLinks.forEach((item) => item.classList.toggle("is-active", item === link));
  filterCards();
  $("#featured-tools")?.scrollIntoView({ behavior: "smooth", block: "start" });
}));

$$('[data-scroll-target]').forEach((link) => link.addEventListener("click", () => {
  $(`#${link.dataset.scrollTarget}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}));

function renderSuggestions(query) {
  const suggestions = $("#search-suggestions");
  if (!suggestions || !query) { if (suggestions) suggestions.innerHTML = ""; return; }
  const matches = cards.filter((card) => (card.dataset.search || "").toLowerCase().includes(query)).slice(0, 4);
  suggestions.innerHTML = matches.map((card) => `<a href="${card.href}">${card.querySelector("h3, h2")?.textContent || i18n("js.open_tool")}<span aria-hidden="true">←</span></a>`).join("");
}
if (search) search.addEventListener("input", () => renderSuggestions(search.value.trim().toLowerCase()));

function safeStorageArray(key) { try { const value = JSON.parse(localStorage.getItem(key) || "[]"); return Array.isArray(value) ? value : []; } catch (_) { localStorage.removeItem(key); return []; } }
function readRecent() { return safeStorageArray("infinity-recent"); }
function saveRecent(toolId, name, path) {
  const recent = readRecent().filter((item) => item.id !== toolId);
  recent.unshift({ id: toolId, name, path: path || `/tool/${encodeURIComponent(toolId)}` });
  localStorage.setItem("infinity-recent", JSON.stringify(recent.slice(0, 5)));
}
function renderRecent() {
  const section = $("#personal-tools");
  const list = $("#recent-list");
  if (!section || !list) return;
  const recent = readRecent();
  section.hidden = recent.length === 0;
  list.innerHTML = recent.map((item) => `<a href="${item.path || `/tool/${encodeURIComponent(item.id)}`}">${escapeHtml(item.name || item.id)} <span aria-hidden="true">↗</span></a>`).join("");
}
$("#clear-recent")?.addEventListener("click", () => { localStorage.removeItem("infinity-recent"); renderRecent(); });

function readFavorites() { return safeStorageArray("infinity-favorites"); }
function renderFavorites() {
  const section = $("#favorite-tools");
  const list = $("#favorite-list");
  if (!section || !list) return;
  const favorites = readFavorites();
  section.hidden = favorites.length === 0;
  list.innerHTML = favorites.map((item) => `<a href="${item.path || `/tool/${encodeURIComponent(item.id)}`}">${escapeHtml(item.name || item.id)} <span aria-hidden="true">↗</span></a>`).join("");
}
const favoriteButton = $("#favorite-tool");
function syncFavorite() {
  if (!favoriteButton) return;
  const active = readFavorites().some((item) => item.id === favoriteButton.dataset.toolId);
  favoriteButton.textContent = active ? favoriteButton.dataset.labelActive : favoriteButton.dataset.labelInactive;
  favoriteButton.classList.toggle("is-favorite", active);
}
if (favoriteButton) favoriteButton.addEventListener("click", () => {
  const favorites = readFavorites();
  const index = favorites.findIndex((item) => item.id === favoriteButton.dataset.toolId);
  if (index >= 0) favorites.splice(index, 1);
  else favorites.unshift({ id: favoriteButton.dataset.toolId, name: favoriteButton.dataset.toolName, path: favoriteButton.dataset.toolPath || `/tool/${encodeURIComponent(favoriteButton.dataset.toolId)}` });
  localStorage.setItem("infinity-favorites", JSON.stringify(favorites.slice(0, 10)));
  syncFavorite();
  renderFavorites();
});
syncFavorite();
renderRecent();
renderFavorites();

const form = $("#converter-form");
const fileInput = $("#files");
const dropzone = $("#dropzone");
const fileList = $("#file-list");
const intelligence = $("#file-intelligence");
let selectedFiles = [];
function escapeHtml(value) { return value.replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;", "'":"&#39;"}[character])); }
let I18N = {};
try { I18N = JSON.parse(document.querySelector("#i18n-data")?.content || "{}"); } catch (_) { I18N = {}; }
function i18n(key, replacements) {
  const template = I18N[key] || key;
  return Object.keys(replacements || {}).reduce((text, name) => text.replace(`{${name}}`, replacements[name]), template);
}
function renderFiles() {
  if (!fileList) return;
  fileList.innerHTML = selectedFiles.map((file, index) => `<div class="file-item" draggable="true" data-file-index="${index}"><span>☷ ${escapeHtml(file.name)} <small>${Math.ceil(file.size / 1024)}KB</small></span><button class="file-remove" type="button" data-remove-file="${index}" aria-label="${escapeHtml(i18n("js.remove_file", { name: file.name }))}">${escapeHtml(i18n("js.remove"))}</button></div>`).join("");
}
function addFiles(files) {
  const maxFiles = Number($("#max-files")?.value || Infinity);
  const maxBytes = Number(document.body.dataset.maxFileBytes || 0);
  const oversized = maxBytes ? files.filter((file) => file.size > maxBytes) : [];
  if (oversized.length) {
    if (intelligence) { intelligence.hidden = false; intelligence.textContent = i18n("js.file_too_large", { name: oversized[0].name }); }
    files = files.filter((file) => file.size <= maxBytes);
  }
  const existing = new Set(selectedFiles.map((file) => `${file.name}\u0000${file.size}\u0000${file.lastModified}`));
  files = files.filter((file) => !existing.has(`${file.name}\u0000${file.size}\u0000${file.lastModified}`));
  const attemptedCount = selectedFiles.length + files.length;
  selectedFiles = [...selectedFiles, ...files].slice(0, maxFiles);
  if (intelligence && selectedFiles.length) {
    const extensions = [...new Set(selectedFiles.map((file) => file.name.split(".").pop().toUpperCase()))].join(", ");
    intelligence.hidden = false;
    const limited = attemptedCount > maxFiles;
    intelligence.textContent = limited
      ? i18n("js.limited_files", { max: maxFiles })
      : selectedFiles.length > 1
      ? i18n("js.multiple_files", { count: selectedFiles.length, extensions })
      : i18n("js.single_file", { extension: extensions, size: Math.ceil(selectedFiles[0].size / 1024) });
  }
  renderFiles();
}
if (fileInput) fileInput.addEventListener("change", () => { addFiles([...fileInput.files]); fileInput.value = ""; });
if (fileList) {
  fileList.addEventListener("click", (event) => { const button = event.target.closest("[data-remove-file]"); if (!button) return; selectedFiles.splice(Number(button.dataset.removeFile), 1); renderFiles(); });
  fileList.addEventListener("dragstart", (event) => { const item = event.target.closest("[data-file-index]"); if (item) event.dataTransfer.setData("text/plain", item.dataset.fileIndex); });
  fileList.addEventListener("dragover", (event) => event.preventDefault());
  fileList.addEventListener("drop", (event) => { event.preventDefault(); const target = event.target.closest("[data-file-index]"); if (!target) return; const source = Number(event.dataTransfer.getData("text/plain")); const targetIndex = Number(target.dataset.fileIndex); if (source === targetIndex || Number.isNaN(source)) return; const [file] = selectedFiles.splice(source, 1); selectedFiles.splice(targetIndex, 0, file); renderFiles(); });
}
if (dropzone) {
  ["dragenter", "dragover"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.add("is-dragging"); }));
  ["dragleave", "drop"].forEach((eventName) => dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.remove("is-dragging"); }));
  dropzone.addEventListener("drop", (event) => addFiles([...event.dataTransfer.files]));
}
const heroDropzone = $("#hero-dropzone");
if (heroDropzone) {
  ["dragenter", "dragover"].forEach((eventName) => heroDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    heroDropzone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => heroDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    heroDropzone.classList.remove("is-dragging");
  }));
  heroDropzone.addEventListener("drop", () => { window.location.assign("/tools"); });
  heroDropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") window.location.assign("/tools");
  });
}
const sampleButton = $("#load-sample");
if (sampleButton) sampleButton.addEventListener("click", async () => {
  const urls = JSON.parse(sampleButton.dataset.samples || "[]");
  const names = JSON.parse(sampleButton.dataset.sampleNames || "[]");
  if (!urls.length) return;
  const original = sampleButton.textContent;
  sampleButton.disabled = true;
  sampleButton.textContent = document.documentElement.lang === "ar" ? "جاري تجهيز العينة…" : "Loading sample…";
  try {
    const files = await Promise.all(urls.map(async (url, index) => {
      const response = await fetch(url, { cache: "force-cache" });
      if (!response.ok) throw new Error("Sample file is unavailable.");
      const blob = await response.blob();
      const name = names[index] || url.split("/").pop() || `sample-${index + 1}`;
      return new File([blob], name, { type: blob.type || "application/octet-stream", lastModified: Date.now() });
    }));
    selectedFiles = [];
    addFiles(files);
    const sampleParam = sampleButton.dataset.sampleParam || "";
    const paramInput = document.getElementById("param");
    if (paramInput && sampleParam) {
      paramInput.value = sampleParam;
      paramInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
    let sampleOptions = {};
    try { sampleOptions = JSON.parse(sampleButton.dataset.sampleOptions || "{}"); } catch (_) { sampleOptions = {}; }
    Object.entries(sampleOptions).forEach(([id, value]) => {
      const field = document.getElementById(id);
      if (!field) return;
      field.value = value;
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.dispatchEvent(new Event("change", { bubbles: true }));
    });
    dropzone?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  } catch (error) {
    if (intelligence) { intelligence.hidden = false; intelligence.textContent = error.message || String(error); }
  } finally {
    sampleButton.disabled = false;
    sampleButton.textContent = original;
  }
});

let resultObjectUrl = null;
const releaseResult = () => {
  if (resultObjectUrl) URL.revokeObjectURL(resultObjectUrl);
  resultObjectUrl = null;
  const download = document.getElementById('download-again');
  if (download) { download.hidden = true; download.removeAttribute('href'); }
};
window.addEventListener('pagehide', releaseResult);
const resultPanel = $("#result-panel");
function setResultState(state, message = "") {
  if (!resultPanel) return;
  resultPanel.dataset.state = state;
  resultPanel.classList.toggle("is-error", state === "error");
  resultPanel.classList.toggle("is-success", state === "success");
  const icon = resultPanel.querySelector(".result-icon");
  if (icon) icon.textContent = state === "error" ? "!" : "✓";
  const result = $("#result");
  if (result && message) result.textContent = message;
  resultPanel.hidden = state === "idle";
}
if (form) form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (form.getAttribute("aria-busy") === "true") return;
  releaseResult();
  const status = $("#status");
  const result = $("#result");
  const metrics = $("#result-metrics");
  const engineNode = $("#result-engine");
  const progress = $("#conversion-progress");
  const submitButton = form.querySelector('[type="submit"]');
  const startedAt = performance.now();
  const inputBytes = selectedFiles.reduce((total, file) => total + (file.size || 0), 0);
  document.querySelectorAll(".batch-summary").forEach((el) => el.remove());

  if (fileInput && !selectedFiles.length) {
    status.textContent = i18n("js.failed");
    setResultState("error", i18n("js.choose_file"));
    return;
  }

  if (progress) progress.hidden = false;
  if (submitButton) submitButton.disabled = true;
  if (metrics) metrics.hidden = true;
  if (engineNode) engineNode.hidden = true;
  form.setAttribute("aria-busy", "true");
  status.textContent = i18n("js.processing");
  result.textContent = "";
  if (resultPanel) resultPanel.hidden = true;

  const payload = new FormData();
  payload.append("tool", $("#tool-id").value);
  selectedFiles.forEach((file) => payload.append("files", file));
  form.querySelectorAll("[name]").forEach((field) => {
    if (field.name && field.name !== "tool" && field.name !== "files" && field.value) payload.set(field.name, field.value);
  });

  const timeoutSeconds = Math.max(5, Number(document.body.dataset.requestTimeoutSeconds || 210));
  const controller = new AbortController();
  const abortTimer = window.setTimeout(() => controller.abort(), timeoutSeconds * 1000);

  try {
    const response = await fetch("/api/v2/convert", { method: "POST", body: payload, signal: controller.signal });
    const type = response.headers.get("content-type") || "";
    if (!response.ok) {
      const data = type.includes("application/json") ? await response.json() : {};
      if ((response.status === 401 || response.status === 403) && document.body.dataset.billingEnabled === "1") {
        result.replaceChildren(document.createTextNode(data.error || i18n("js.generic_error")), document.createElement("br"));
        const upgrade = document.createElement("a");
        upgrade.href = "/pricing";
        upgrade.className = "upgrade-link";
        upgrade.textContent = i18n("js.upgrade_plans");
        result.append(upgrade);
        setResultState("error");
      }
      throw new Error(data.error || i18n("js.generic_error"));
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
    let filename = "InfinityConverter-result";
    try { filename = utf8Match ? decodeURIComponent(utf8Match[1]) : (asciiMatch ? asciiMatch[1] : filename); } catch (_) {}
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    resultObjectUrl = url;
    const downloadAgain = document.getElementById('download-again');
    if (downloadAgain) {
      downloadAgain.href = url; downloadAgain.download = filename; downloadAgain.hidden = false;
    }

    const batchTotal = Number(response.headers.get("X-Batch-Total") || 0);
    const batchFailed = Number(response.headers.get("X-Batch-Failed") || 0);
    saveRecent($("#tool-id").value, document.title.split(" | ")[0], $("#tool-path")?.value);
    renderRecent();
    status.textContent = i18n("js.completed");
    result.textContent = i18n("js.result_label", { filename, size: Math.ceil(blob.size / 1024) });

    const formatBytes = (bytes) => bytes >= 1024 * 1024
      ? `${(bytes / 1024 / 1024).toFixed(bytes >= 10 * 1024 * 1024 ? 1 : 2)} MB`
      : `${Math.max(1, Math.ceil(bytes / 1024))} KB`;
    const serverInputBytes = Number(response.headers.get("X-Input-Bytes") || inputBytes || 0);
    const serverOutputBytes = Number(response.headers.get("X-Output-Bytes") || blob.size || 0);
    const serverDurationMs = Number(response.headers.get("X-Conversion-Duration-MS") || 0);
    if (metrics) {
      $("#metric-input").textContent = serverInputBytes ? formatBytes(serverInputBytes) : "—";
      $("#metric-output").textContent = formatBytes(serverOutputBytes || blob.size);
      const change = serverInputBytes ? (((serverOutputBytes || blob.size) - serverInputBytes) / serverInputBytes) * 100 : null;
      $("#metric-change").textContent = change === null ? "—" : `${change > 0 ? "+" : ""}${change.toFixed(Math.abs(change) >= 10 ? 0 : 1)}%`;
      const elapsedMs = serverDurationMs || (performance.now() - startedAt);
      $("#metric-time").textContent = `${(elapsedMs / 1000).toFixed(elapsedMs >= 10000 ? 1 : 2)}s`;
      metrics.hidden = false;
    }

    const engine = response.headers.get("X-Conversion-Engine") || "";
    window.InfinityRuntimeContext = window.InfinityRuntimeContext || {};
    window.InfinityRuntimeContext.lastError = null;
    window.InfinityRuntimeContext.lastResult = {
      tool_id: $("#tool-id")?.value || "",
      input_bytes: serverInputBytes,
      output_bytes: serverOutputBytes || blob.size,
      duration_ms: serverDurationMs || Math.round(performance.now() - startedAt),
      engine,
    };
    if (engineNode && engine) {
      engineNode.textContent = `${document.documentElement.lang === "ar" ? "المحرك" : "Engine"}: ${engine}`;
      engineNode.hidden = false;
    }
    if (batchTotal > 1) {
      const summary = document.createElement("p");
      summary.className = "batch-summary";
      summary.textContent = i18n("js.batch_summary", { total: batchTotal, succeeded: batchTotal - batchFailed, failed: batchFailed });
      result.after(summary);
    }
    setResultState("success");
  } catch (error) {
    status.textContent = i18n("js.failed");
    const timedOut = error?.name === "AbortError";
    const message = timedOut
      ? (document.documentElement.lang === "ar" ? "انتهت مهلة العملية. جرّب ملفًا أصغر أو أعد المحاولة." : "The operation timed out. Try a smaller file or retry.")
      : (error?.message || i18n("js.generic_error"));
    if (!result.querySelector(".upgrade-link")) result.textContent = message;
    if (metrics) metrics.hidden = true;
    if (engineNode) engineNode.hidden = true;
    setResultState("error");
    window.InfinityRuntimeContext = window.InfinityRuntimeContext || {};
    window.InfinityRuntimeContext.lastResult = null;
    window.InfinityRuntimeContext.lastError = { tool_id: $("#tool-id")?.value || "", message: String(message).slice(0, 900) };
  } finally {
    window.clearTimeout(abortTimer);
    if (progress) progress.hidden = true;
    if (submitButton) submitButton.disabled = false;
    form.removeAttribute("aria-busy");
  }
});
$("#reset-tool")?.addEventListener("click", () => {
  window.InfinityRuntimeContext = window.InfinityRuntimeContext || {};
  window.InfinityRuntimeContext.lastResult = null;
  window.InfinityRuntimeContext.lastError = null;
  selectedFiles = [];
  renderFiles();
  if (intelligence) intelligence.hidden = true;
  setResultState("idle");
  $("#status").textContent = i18n("js.ready");
  $("#result").textContent = "";
  const metrics = $("#result-metrics"); if (metrics) metrics.hidden = true;
  const engineNode = $("#result-engine"); if (engineNode) engineNode.hidden = true;
  document.querySelectorAll(".batch-summary").forEach((el) => el.remove());
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); search?.focus(); }
});


// Smart File Router: metadata-only matching in the browser; the selected file is never uploaded here.
(() => {
  const picker = document.getElementById("smart-file-input");
  const drop = document.getElementById("smart-drop");
  const summary = document.getElementById("smart-file-summary");
  const output = document.getElementById("smart-tool-results");
  const dataNode = document.getElementById("command-palette-data");
  if (!picker || !drop || !summary || !output || !dataNode) return;
  let tools = [];
  try { tools = JSON.parse(dataNode.textContent || "[]"); } catch (_) { tools = []; }
  const isEnglish = document.documentElement.lang === "en";
  const bytes = (value) => value >= 1024 * 1024 ? `${(value / 1024 / 1024).toFixed(value >= 10 * 1024 * 1024 ? 1 : 2)} MB` : `${Math.max(1, Math.ceil(value / 1024))} KB`;
  const extensionOf = (name) => { const match = String(name || "").toLowerCase().match(/(\.[a-z0-9]+)$/); return match ? match[1] : ""; };
  const choose = (file) => {
    if (!file) return;
    const ext = extensionOf(file.name);
    window.InfinityRuntimeContext = window.InfinityRuntimeContext || {};
    window.InfinityRuntimeContext.smartFile = { extension: ext, mime: file.type || "", size_bytes: Number(file.size || 0) };
    const compatible = tools.filter((tool) => Array.isArray(tool.input_ext) && (tool.input_ext.includes(ext) || tool.input_ext.includes(".*") || tool.input_ext.includes("*")));
    summary.hidden = false;
    summary.replaceChildren();
    const strong = document.createElement("strong"); strong.textContent = file.name || (isEnglish ? "Selected file" : "الملف المختار");
    summary.append(strong, document.createTextNode(` · ${ext || (file.type || (isEnglish ? "unknown type" : "نوع غير معروف"))} · ${bytes(file.size || 0)}`));
    output.hidden = false; output.replaceChildren();
    if (!compatible.length) {
      const empty = document.createElement("div"); empty.className = "smart-no-match";
      empty.append(document.createTextNode(isEnglish ? "No reviewed landing page currently advertises this file type. The full toolbox may still contain a compatible utility. " : "لا توجد حاليًا صفحة أداة مراجعة نروّج لها لهذا النوع، لكن صندوق الأدوات الكامل قد يحتوي أداة مناسبة. "));
      const link = document.createElement("a"); link.href = "/tools"; link.textContent = isEnglish ? "Browse all tools →" : "تصفح كل الأدوات ←"; empty.append(link); output.append(empty); return;
    }
    compatible.slice(0, 6).forEach((tool) => {
      const a = document.createElement("a"); a.className = "smart-suggestion"; a.href = tool.href;
      const icon = document.createElement("span"); icon.textContent = tool.icon || "∞";
      const copy = document.createElement("span"); const title = document.createElement("strong"); title.textContent = isEnglish ? tool.name_en : tool.name_ar; const small = document.createElement("small"); small.textContent = isEnglish ? tool.category_en : tool.category_ar; copy.append(title, small);
      const arrow = document.createElement("span"); arrow.textContent = "↗"; a.append(icon, copy, arrow); output.append(a);
    });
  };
  drop.addEventListener("click", () => picker.click());
  picker.addEventListener("change", () => choose(picker.files?.[0]));
  ["dragenter", "dragover"].forEach((type) => drop.addEventListener(type, (event) => { event.preventDefault(); drop.classList.add("is-dragging"); }));
  ["dragleave", "drop"].forEach((type) => drop.addEventListener(type, (event) => { event.preventDefault(); drop.classList.remove("is-dragging"); }));
  drop.addEventListener("drop", (event) => choose(event.dataTransfer?.files?.[0]));
})();

// Global Quick Jump command palette. It intentionally promotes only the manually reviewed tool pages.
(() => {
  const palette = document.getElementById("command-palette");
  const input = document.getElementById("command-input");
  const results = document.getElementById("command-results");
  const triggers = [document.getElementById("command-trigger"), document.getElementById("mobile-command-trigger")].filter(Boolean);
  const dataNode = document.getElementById("command-palette-data");
  if (!palette || !input || !results || !dataNode) return;
  let toolItems = [];
  try { toolItems = JSON.parse(dataNode.textContent || "[]"); } catch (_) { toolItems = []; }
  const isEnglish = document.documentElement.lang === "en";
  const pageItems = [
    { icon: "∞", name_ar: "الرئيسية", name_en: "Home", category_ar: "الموقع", category_en: "Site", href: "/" },
    { icon: "ALL", name_ar: "كل الأدوات", name_en: "All tools", category_ar: "الدليل", category_en: "Directory", href: "/tools" },
    { icon: "✦", name_ar: "Infinity Intelligence", name_en: "Infinity Intelligence", category_ar: "الذكاء", category_en: "AI Workspace", href: "/assistant" },
    { icon: "KNW", name_ar: "مركز المعرفة", name_en: "Knowledge Center", category_ar: "أدلة", category_en: "Guides", href: "/blog" },
    { icon: "✓", name_ar: "مركز الثقة والأمان", name_en: "Trust & Security", category_ar: "الثقة", category_en: "Trust", href: "/trust" },
    { icon: "ED", name_ar: "سياسة التحرير والجودة", name_en: "Editorial Policy", category_ar: "الجودة", category_en: "Quality", href: "/editorial" },
    { icon: "@", name_ar: "تواصل معنا", name_en: "Contact", category_ar: "الدعم", category_en: "Support", href: "/contact" }
  ];
  const allItems = [...toolItems, ...pageItems];
  let activeIndex = 0;
  let visibleItems = [];
  const normalize = (value) => String(value || "").toLowerCase().normalize("NFKD").replace(/[\u064B-\u065F\u0670]/g, "").replace(/[أإآ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه");
  const label = (item) => isEnglish ? item.name_en : item.name_ar;
  const category = (item) => isEnglish ? item.category_en : item.category_ar;
  function render() {
    const q = normalize(input.value.trim());
    visibleItems = allItems.filter((item) => !q || normalize(`${item.name_ar} ${item.name_en} ${item.category_ar} ${item.category_en} ${(item.input_ext || []).join(" ")}`).includes(q)).slice(0, 14);
    if (activeIndex >= visibleItems.length) activeIndex = 0;
    results.replaceChildren();
    if (!visibleItems.length) {
      const empty = document.createElement("div"); empty.className = "command-empty"; empty.textContent = isEnglish ? "No reviewed tool or site page matches that search." : "ما لقينا أداة مراجعة أو صفحة موقع تطابق البحث."; results.append(empty); return;
    }
    visibleItems.forEach((item, index) => {
      const a = document.createElement("a"); a.className = "command-item"; a.href = item.href; a.setAttribute("role", "option"); a.setAttribute("aria-selected", String(index === activeIndex));
      const icon = document.createElement("span"); icon.className = "command-item-icon"; icon.textContent = item.icon || "∞";
      const copy = document.createElement("span"); copy.className = "command-item-copy";
      const strong = document.createElement("strong"); strong.textContent = label(item);
      const small = document.createElement("small"); small.textContent = category(item) || (isEnglish ? "Reviewed tool" : "أداة مراجعة");
      copy.append(strong, small);
      const arrow = document.createElement("span"); arrow.className = "command-item-arrow"; arrow.textContent = "↗";
      a.append(icon, copy, arrow); results.append(a);
    });
  }
  function openPalette() { palette.hidden = false; document.documentElement.classList.add("command-open"); activeIndex = 0; input.value = ""; render(); requestAnimationFrame(() => input.focus()); }
  function closePalette() { palette.hidden = true; document.documentElement.classList.remove("command-open"); }
  triggers.forEach((trigger) => trigger.addEventListener("click", openPalette));
  palette.querySelectorAll("[data-command-close]").forEach((node) => node.addEventListener("click", closePalette));
  input.addEventListener("input", () => { activeIndex = 0; render(); });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); if (!visibleItems.length) return; activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + visibleItems.length) % visibleItems.length; render(); }
    if (event.key === "Enter" && visibleItems[activeIndex]) { event.preventDefault(); window.location.assign(visibleItems[activeIndex].href); }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); palette.hidden ? openPalette() : closePalette(); }
    if (event.key === "Escape" && !palette.hidden) { event.preventDefault(); closePalette(); }
  });
})();

// Pricing billing toggle and Paddle checkout are scoped to the pricing page.
const billingButtons = $$('[data-billing]');
if (billingButtons.length) {
  const priceNodes = $$('[data-price-monthly]');
  let selectedBilling = 'monthly';
  const pricingPage = $('.pricing-wrap[data-paddle-client-token]');
  const checkoutButtons = $$('[data-paddle-checkout]');
  const paddleNotice = $('#paddle-notice');
  const paddleToken = pricingPage?.dataset.paddleClientToken || '';
  const checkoutUserId = pricingPage?.dataset.userId || '';
  const checkoutEmail = pricingPage?.dataset.userEmail || '';
  let paddleReady = false;
  if (paddleToken && window.Paddle) {
    try {
      window.Paddle.Initialize({ token: paddleToken });
      paddleReady = true;
    } catch (_) { paddleReady = false; }
  }
  checkoutButtons.forEach((button) => { if (!button.disabled) button.disabled = !paddleReady; });
  if (paddleToken && checkoutUserId && !paddleReady && paddleNotice) paddleNotice.hidden = false;
  billingButtons.forEach((button) => button.addEventListener('click', () => {
    billingButtons.forEach((b) => b.classList.toggle('is-active', b === button));
    const yearly = button.dataset.billing === 'yearly';
    selectedBilling = yearly ? 'yearly' : 'monthly';
    priceNodes.forEach((node) => { node.textContent = `$${yearly ? node.dataset.priceYearly : node.dataset.priceMonthly}`; });
    $$('[data-price-period]').forEach((node) => { node.textContent = yearly ? node.dataset.periodYearly : node.dataset.periodMonthly; });
  }));
  checkoutButtons.forEach((button) => button.addEventListener('click', () => {
    if (!paddleReady) return;
    const priceId = selectedBilling === 'yearly' ? button.dataset.priceYearly : button.dataset.priceMonthly;
    if (priceId && checkoutUserId && checkoutEmail) window.Paddle.Checkout.open({ items: [{ priceId, quantity: 1 }], customData: { user_id: checkoutUserId, email: checkoutEmail } });
  }));
}

const developerWorkspace = document.querySelector('[data-developer-tool]');
if (developerWorkspace) {
  const toolId = developerWorkspace.dataset.developerTool;
  const input = document.querySelector('#developer-input');
  const output = document.querySelector('#developer-output');
  const run = document.querySelector('#developer-run');
  const copy = document.querySelector('#developer-copy');
  const utf8ToBase64 = (value) => btoa(String.fromCharCode(...new TextEncoder().encode(value)));
  const base64ToUtf8 = (value) => new TextDecoder().decode(Uint8Array.from(atob(value.trim()), (char) => char.charCodeAt(0)));

  async function transformDeveloperInput() {
    const value = input.value;
    if (toolId === 'json-formatter') return JSON.stringify(JSON.parse(value), null, 2);
    if (toolId === 'base64') {
      try { return base64ToUtf8(value); } catch (_) { return utf8ToBase64(value); }
    }
    if (toolId === 'url-encoder') {
      try { return decodeURIComponent(value); } catch (_) { return encodeURIComponent(value); }
    }
    if (toolId === 'uuid-generator') return crypto.randomUUID();
    if (toolId === 'hash-generator') {
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
      return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
    }
    if (toolId === 'timestamp-converter') {
      const numeric = Number(value);
      if (Number.isFinite(numeric) && value.trim()) return new Date(numeric * 1000).toISOString();
      const timestamp = Date.parse(value);
      if (Number.isNaN(timestamp)) throw new Error('Invalid date or timestamp');
      return String(Math.floor(timestamp / 1000));
    }
    return value;
  }

  run?.addEventListener('click', async () => {
    try { output.value = await transformDeveloperInput(); }
    catch (error) { output.value = error.message || String(error); }
  });
  copy?.addEventListener('click', async () => {
    if (output.value) await navigator.clipboard?.writeText(output.value);
  });
}

const browserWorkspace = document.querySelector('[data-browser-tool]');
if (browserWorkspace) {
  const toolId = browserWorkspace.dataset.browserTool;
  const output = $('#browser-output');
  const download = $('#browser-download');
  const value = (key) => $(`#browser-${key}`)?.value.trim() || '';
  const number = (key) => { const raw = value(key); const parsed = Number(raw); if (!raw || !Number.isFinite(parsed)) throw new Error('Enter a valid number.'); return parsed; };
  const lines = (key) => value(key).split('\n').map((item) => item.trim()).filter(Boolean);
  const fixed = (amount) => Number(amount).toLocaleString(undefined, { maximumFractionDigits: 2 });
  const requirePositive = (amount, label = 'Value') => { if (!Number.isFinite(amount) || amount <= 0) throw new Error(`${label} must be greater than zero.`); return amount; };
  const parsePairs = (key) => lines(key).map((item) => item.split(',').map((part) => part.trim()));
  const base64Url = (part) => new TextDecoder().decode(Uint8Array.from(atob(part.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(part.length / 4) * 4, '=')), (character) => character.charCodeAt(0)));
  const hexToRgb = (hex) => { const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex); if (!match) throw new Error('Use a six-digit hex color.'); return match.slice(1).map((part) => parseInt(part, 16) / 255); };
  const luminance = (rgb) => rgb.map((channel) => channel <= .03928 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4).reduce((total, channel, index) => total + channel * [.2126, .7152, .0722][index], 0);
  const timerState = { interval: null };

  async function cleanLightBackground() {
    const file = $('#browser-image')?.files?.[0];
    if (!file) throw new Error('Choose an image first.');
    const image = new Image();
    const sourceUrl = URL.createObjectURL(file);
    try {
      await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = reject; image.src = sourceUrl; });
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
      for (let index = 0; index < pixels.data.length; index += 4) {
        const lightness = (pixels.data[index] + pixels.data[index + 1] + pixels.data[index + 2]) / 3;
        if (lightness > 238) pixels.data[index + 3] = 0;
        else if (lightness > 215) pixels.data[index + 3] = Math.round((238 - lightness) / 23 * 255);
      }
      context.putImageData(pixels, 0, 0);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('Could not process this image.');
      if (download?.dataset.objectUrl) URL.revokeObjectURL(download.dataset.objectUrl);
      const resultUrl = URL.createObjectURL(blob);
      download.href = resultUrl;
      download.dataset.objectUrl = resultUrl;
      download.hidden = false;
      return `Processed locally: ${image.naturalWidth} x ${image.naturalHeight}px.`;
    } finally { URL.revokeObjectURL(sourceUrl); }
  }

  async function runBrowserTool() {
    if (timerState.interval) { clearInterval(timerState.interval); timerState.interval = null; }
    if (download) download.hidden = true;
    if (toolId === 'gpa-calculator') { const courses = parsePairs('courses'); if (!courses.length) throw new Error('Enter at least one course.'); const totals = courses.reduce((sum, [grade, credits]) => { const points = { 'A+': 4, A: 4, 'A-': 3.7, 'B+': 3.3, B: 3, 'B-': 2.7, 'C+': 2.3, C: 2, 'C-': 1.7, D: 1, F: 0 }[grade.toUpperCase()]; const hours = Number(credits); if (points === undefined || !Number.isFinite(hours) || hours <= 0) throw new Error('Use grades such as A, B+, C and positive credits.'); return [sum[0] + points * hours, sum[1] + hours]; }, [0, 0]); return `GPA: ${(totals[0] / totals[1]).toFixed(2)}\nCredits: ${totals[1]}`; }
    if (toolId === 'weighted-grade-calculator') { const pairs = parsePairs('items'); if (!pairs.length || pairs.some(([grade, weight]) => !Number.isFinite(Number(grade)) || !Number.isFinite(Number(weight)) || Number(weight) <= 0)) throw new Error('Enter grades with positive weights.'); const totalWeight = pairs.reduce((sum, [, weight]) => sum + Number(weight), 0); const result = pairs.reduce((sum, [grade, weight]) => sum + Number(grade) * Number(weight), 0) / totalWeight; return `Weighted grade: ${fixed(result)}%\nTotal weight: ${fixed(totalWeight)}%`; }
    if (toolId === 'study-session-planner') { const minutes = requirePositive(number('minutes'), 'Minutes'); const topics = requirePositive(number('topics'), 'Topics'); if (!Number.isInteger(topics) || topics > 100 || minutes <= (topics - 1) * 5) throw new Error('Choose fewer topics or allow more study time.'); const block = Math.floor((minutes - (topics - 1) * 5) / topics); return Array.from({ length: topics }, (_, index) => `Topic ${index + 1}: ${block} minutes${index < topics - 1 ? '\nBreak: 5 minutes' : ''}`).join('\n'); }
    if (toolId === 'focus-timer') { let remaining = Math.round(requirePositive(number('minutes'), 'Minutes') * 60); const render = () => { output.value = `Focus time remaining: ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`; }; render(); timerState.interval = setInterval(() => { remaining -= 1; render(); if (remaining <= 0) { clearInterval(timerState.interval); timerState.interval = null; output.value = 'Focus session complete.'; } }, 1000); return null; }
    if (toolId === 'flashcard-maker') { return lines('cards').map((card, index) => { const [question, answer] = card.split('|').map((part) => part.trim()); if (!question || !answer) throw new Error('Use Question | answer on each line.'); return `${index + 1}. Q: ${question}\n   A: ${answer}`; }).join('\n\n'); }
    if (toolId === 'presentation-outline-builder') { const topic = value('topic'); const points = lines('points'); if (!topic || !points.length) throw new Error('Enter a topic and at least one key point.'); return [`1. ${topic}`, '2. Context and goal', ...points.map((point, index) => `${index + 3}. ${point}`), `${points.length + 3}. Summary and next steps`].join('\n'); }
    if (toolId === 'slide-glossary-translator') { const entries = lines('glossary').map((line) => line.split('=').map((part) => part.trim())).filter(([source, translation]) => source && translation).sort(([left], [right]) => right.length - left.length); if (!entries.length) throw new Error('Add at least one source = translation glossary entry.'); return entries.reduce((translated, [source, translation]) => translated.replace(new RegExp(source.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), translation), value('text')); }
    if (toolId === 'reading-time-estimator' || toolId === 'word-character-counter') { const text = value('text'); const words = text.match(/\S+/g)?.length || 0; return toolId === 'reading-time-estimator' ? `${words} words\nEstimated reading time: ${Math.max(1, Math.ceil(words / 200))} minute(s)` : `Words: ${words}\nCharacters: ${text.length}\nCharacters without spaces: ${text.replace(/\s/g, '').length}\nLines: ${text ? text.split('\n').length : 0}`; }
    if (toolId === 'rubric-score-calculator') { const rows = parsePairs('items'); const total = rows.reduce((sum, [, score, weight]) => sum + Number(score) / 4 * Number(weight), 0); return `Rubric score: ${fixed(total)}%\nBased on a 4-point scale.`; }
    if (toolId === 'classroom-group-maker' || toolId === 'seating-plan-generator') { const shuffled = lines('names').sort(() => crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32 - .5); const count = requirePositive(number(toolId === 'classroom-group-maker' ? 'groups' : 'columns'), toolId === 'classroom-group-maker' ? 'Groups' : 'Columns'); if (toolId === 'classroom-group-maker') return Array.from({ length: count }, (_, index) => `Group ${index + 1}: ${shuffled.filter((_, itemIndex) => itemIndex % count === index).join(', ') || '-'}`).join('\n'); return shuffled.map((name, index) => `${name}${(index + 1) % count ? '\t' : '\n'}`).join('').trim(); }
    if (toolId === 'random-name-picker') { const names = lines('names'); if (!names.length) throw new Error('Enter at least one name.'); return `Selected name: ${names[crypto.getRandomValues(new Uint32Array(1))[0] % names.length]}`; }
    if (toolId === 'text-similarity-checker') { const words = (key) => new Set(value(key).toLowerCase().match(/[\p{L}\p{N}]+/gu) || []); const first = words('first'); const second = words('second'); const shared = [...first].filter((word) => second.has(word)); const total = new Set([...first, ...second]).size; return `Shared words: ${shared.length}\nSimilarity: ${total ? fixed(shared.length / total * 100) : 0}%\n${shared.slice(0, 30).join(', ')}`; }
    if (toolId === 'score-to-percentage') return `${fixed(number('score') / requirePositive(number('total'), 'Total') * 100)}%`;
    if (toolId === 'lesson-timing-planner') { const minutes = requirePositive(number('minutes'), 'Minutes'); return `Opening: ${Math.round(minutes * .1)} min\nInstruction: ${Math.round(minutes * .65)} min\nPractice: ${Math.round(minutes * .15)} min\nReview: ${Math.round(minutes * .1)} min`; }
    if (toolId === 'learning-objective-builder') return `By the end of the lesson, learners will be able to ${value('verb')} ${value('topic')} ${value('condition') ? ` ${value('condition')}` : ''}.`;
    if (toolId === 'citation-formatter') { const author = value('author'); const title = value('title'); const year = value('year'); const source = value('source'); if (!author || !title || !year) throw new Error('Enter author, title, and year.'); return `${author} (${year}). ${title}.${source ? ` ${source}.` : ''}`; }
    if (toolId === 'grade-needed-calculator') { const completed = requirePositive(number('completed'), 'Completed weight'); const needed = (number('target') - number('current') * completed / 100) / (1 - completed / 100); return `Required score on remaining ${fixed(100 - completed)}%: ${fixed(needed)}%`; }
    if (toolId === 'deadline-countdown') { const deadline = new Date(value('deadline')); const remaining = deadline - new Date(); if (Number.isNaN(deadline) || remaining < 0) throw new Error('Enter a future deadline.'); return `${Math.floor(remaining / 86400000)} day(s), ${Math.floor(remaining % 86400000 / 3600000)} hour(s) remaining`; }
    if (toolId === 'exam-score-target') { const questions = requirePositive(number('questions'), 'Question count'); return `Correct answers needed: ${Math.ceil(questions * number('target') / 100)} of ${questions}`; }
    if (toolId === 'course-workload-estimator') { const credits = requirePositive(number('credits'), 'Credit hours'); const weeks = requirePositive(number('weeks'), 'Term weeks'); return `Suggested study time: ${fixed(credits * 2)} hours/week\nEstimated term study time: ${fixed(credits * 2 * weeks)} hours`; }
    if (toolId === 'quiz-question-shuffler' || toolId === 'question-order-randomizer') return lines('questions').sort(() => crypto.getRandomValues(new Uint32Array(1))[0] - 2 ** 31).map((question, index) => `${index + 1}. ${question}`).join('\n');
    if (toolId === 'note-outline-organizer') return lines('notes').map((note, index) => `${index + 1}. ${note}`).join('\n');
    if (toolId === 'bibliography-alphabetizer' || toolId === 'grocery-list-organizer') return [...new Set(lines(toolId === 'bibliography-alphabetizer' ? 'entries' : 'items'))].sort((left, right) => left.localeCompare(right)).join('\n');
    if (toolId === 'letter-grade-converter') { const score = number('score'); return `Letter grade: ${score >= 97 ? 'A+' : score >= 93 ? 'A' : score >= 90 ? 'A-' : score >= 87 ? 'B+' : score >= 83 ? 'B' : score >= 80 ? 'B-' : score >= 77 ? 'C+' : score >= 73 ? 'C' : score >= 70 ? 'C-' : score >= 60 ? 'D' : 'F'}`; }
    if (toolId === 'reading-list-planner') { const pages = requirePositive(number('pages'), 'Pages'); const days = requirePositive(number('days'), 'Days'); return `Read ${Math.ceil(pages / days)} page(s) per day for ${days} days.`; }
    if (toolId === 'paragraph-counter') { const text = value('text'); return `Paragraphs: ${text.trim() ? text.trim().split(/\n\s*\n/).length : 0}\nSentences: ${text.match(/[.!?]+(?=\s|$)/g)?.length || 0}`; }
    if (toolId === 'study-goal-checklist' || toolId === 'standards-checklist-builder') return lines(toolId === 'study-goal-checklist' ? 'goals' : 'standards').map((item) => `[ ] ${item}`).join('\n');
    if (toolId === 'attendance-rate-calculator') return `Attendance rate: ${fixed(number('present') / requirePositive(number('total'), 'Total students') * 100)}%`;
    if (toolId === 'grade-scale-builder') { const total = requirePositive(number('total'), 'Maximum score'); return `A: ${Math.ceil(total * number('a') / 100)}-${total}\nB: ${Math.ceil(total * number('b') / 100)}-${Math.ceil(total * number('a') / 100) - 1}\nC: ${Math.ceil(total * number('c') / 100)}-${Math.ceil(total * number('b') / 100) - 1}`; }
    if (toolId === 'exit-ticket-builder') { const topic = value('topic'); if (!topic) throw new Error('Enter a lesson topic.'); return `Exit Ticket: ${topic}\n1. What is one key idea you learned?\n2. What question do you still have?\n3. Apply ${topic} in one example.`; }
    if (toolId === 'parent-message-template') { const student = value('student'); const topic = value('topic'); if (!student || !topic) throw new Error('Enter a student name and topic.'); return value('tone') === 'positive' ? `Hello,\n\nI wanted to share a positive update about ${student}. ${topic}.\n\nKind regards,` : `Hello,\n\nI would appreciate your support with ${student} regarding ${topic}. Please let me know if you would like to discuss this.\n\nKind regards,`; }
    if (toolId === 'syllabus-date-planner') { const units = requirePositive(number('units'), 'Units'); const weeks = requirePositive(number('weeks'), 'Weeks'); return Array.from({ length: units }, (_, index) => `Unit ${index + 1}: weeks ${Math.floor(index * weeks / units) + 1}-${Math.floor((index + 1) * weeks / units)}`).join('\n'); }
    if (toolId === 'duplicate-name-checker') { const names = lines('names'); const duplicates = [...new Set(names.filter((name, index) => names.findIndex((item) => item.toLowerCase() === name.toLowerCase()) !== index))]; return duplicates.length ? `Duplicate names:\n${duplicates.join('\n')}` : 'No duplicate names found.'; }
    if (toolId === 'reading-level-estimator') { const text = value('text'); const words = text.match(/[A-Za-z]+/g) || []; const sentences = text.match(/[.!?]+/g)?.length || 1; const syllables = words.reduce((total, word) => total + Math.max(1, (word.toLowerCase().match(/[aeiouy]+/g) || []).length), 0); return `Approximate Flesch-Kincaid grade: ${fixed(.39 * (words.length / sentences) + 11.8 * (syllables / Math.max(words.length, 1)) - 15.59)}`; }
    if (toolId === 'participation-tracker') { const entries = parsePairs('entries'); const total = entries.reduce((sum, [, count]) => sum + Number(count), 0); return `${entries.map(([name, count]) => `${name}: ${count}`).join('\n')}\n\nTotal participation marks: ${total}`; }
    if (toolId === 'quiz-time-estimator') return `Suggested quiz time: ${fixed(requirePositive(number('questions'), 'Questions') * requirePositive(number('minutes'), 'Minutes per question'))} minutes`;
    if (toolId === 'class-list-numberer') return lines('names').map((name, index) => `${index + 1}. ${name}`).join('\n');
    if (toolId === 'url-parser') { const parsed = new URL(value('url')); return JSON.stringify({ protocol: parsed.protocol, host: parsed.host, pathname: parsed.pathname, query: Object.fromEntries(parsed.searchParams), hash: parsed.hash }, null, 2); }
    if (toolId === 'regex-tester') { const expression = new RegExp(value('pattern'), 'g'); const matches = [...value('text').matchAll(expression)]; return matches.length ? matches.map((match) => `${match[0]} at index ${match.index}`).join('\n') : 'No matches.'; }
    if (toolId === 'http-status-lookup') { const statuses = { 200: 'OK', 201: 'Created', 204: 'No Content', 301: 'Moved Permanently', 302: 'Found', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 409: 'Conflict', 422: 'Unprocessable Content', 429: 'Too Many Requests', 500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable' }; return statuses[number('code')] ? `${number('code')}: ${statuses[number('code')]}` : 'Status code not in this offline reference.'; }
    if (toolId === 'css-unit-converter') { const root = requirePositive(number('root'), 'Root size'); const px = value('from') === 'rem' ? number('value') * root : number('value'); const result = value('to') === 'rem' ? px / root : px; return `${fixed(number('value'))}${value('from')} = ${fixed(result)}${value('to')}`; }
    if (toolId === 'text-diff') { const first = new Set(lines('first')); const second = new Set(lines('second')); return [...first].filter((line) => !second.has(line)).map((line) => `- ${line}`).concat([...second].filter((line) => !first.has(line)).map((line) => `+ ${line}`)).join('\n') || 'No line differences.'; }
    if (toolId === 'slug-generator') return value('text').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '');
    if (toolId === 'mime-type-lookup') { const types = { txt: 'text/plain', html: 'text/html', css: 'text/css', js: 'text/javascript', json: 'application/json', xml: 'application/xml', pdf: 'application/pdf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', svg: 'image/svg+xml', zip: 'application/zip', csv: 'text/csv' }; const extension = value('extension').replace(/^\./, '').toLowerCase(); return types[extension] || 'Unknown in this offline reference.'; }
    if (toolId === 'ipv4-converter') { const input = value('address'); if (/^\d+$/.test(input)) { const numeric = BigInt(input); if (numeric > 4294967295n) throw new Error('Use a value from 0 to 4294967295.'); return [24n, 16n, 8n, 0n].map((shift) => Number((numeric >> shift) & 255n)).join('.'); } const parts = input.split('.').map(Number); if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) throw new Error('Enter a valid IPv4 address.'); return String(parts.reduce((total, part) => total * 256 + part, 0)); }
    if (toolId === 'line-ending-converter') return value('text').replace(/\r?\n/g, value('ending') === 'crlf' ? '\r\n' : '\n');
    if (toolId === 'html-tag-stripper') return new DOMParser().parseFromString(value('text'), 'text/html').body.textContent || '';
    if (toolId === 'case-converter') { const words = value('text').trim().split(/[^\p{L}\p{N}]+/u).filter(Boolean); const style = value('style'); return style === 'camel' ? words.map((word, index) => index ? word[0].toUpperCase() + word.slice(1).toLowerCase() : word.toLowerCase()).join('') : words.map((word) => word.toLowerCase()).join(style === 'snake' ? '_' : '-'); }
    if (toolId === 'duplicate-line-remover') return [...new Set(lines('text'))].join('\n');
    if (toolId === 'jwt-decoder') { const [header, payload] = value('token').split('.'); if (!header || !payload) throw new Error('Enter a JWT with header.payload.signature.'); return `Header (signature unverified):\n${JSON.stringify(JSON.parse(base64Url(header)), null, 2)}\n\nPayload:\n${JSON.stringify(JSON.parse(base64Url(payload)), null, 2)}`; }
    if (toolId === 'query-string-parser-builder') { const source = value('query').replace(/^\?/, ''); return source.includes('&') || source.includes('?') ? JSON.stringify(Object.fromEntries(new URLSearchParams(source)), null, 2) : new URLSearchParams(lines('query').map((line) => line.split('='))).toString(); }
    if (toolId === 'html-entity-converter') { const text = value('text'); const decoded = new DOMParser().parseFromString(text, 'text/html').body.textContent || ''; return decoded === text ? text.replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char])) : decoded; }
    if (toolId === 'unicode-inspector') return [...value('text')].map((char) => `${char}\tU+${char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')}\t\\u{${char.codePointAt(0).toString(16).toUpperCase()}}`).join('\n');
    if (toolId === 'cron-explainer') { const [minute, hour, day, month, weekday, extra] = value('expression').split(/\s+/); if (!weekday || extra) throw new Error('Use exactly five cron fields.'); return `Minute: ${minute}\nHour: ${hour}\nDay of month: ${day}\nMonth: ${month}\nDay of week: ${weekday}`; }
    if (toolId === 'color-contrast-checker') { const ratio = (Math.max(luminance(hexToRgb(value('foreground'))), luminance(hexToRgb(value('background')))) + .05) / (Math.min(luminance(hexToRgb(value('foreground'))), luminance(hexToRgb(value('background')))) + .05); return `Contrast ratio: ${ratio.toFixed(2)}:1\nWCAG AA normal text: ${ratio >= 4.5 ? 'Pass' : 'Fail'}\nWCAG AA large text: ${ratio >= 3 ? 'Pass' : 'Fail'}`; }
    if (toolId === 'semantic-version-comparator') { const parse = (version) => version.replace(/^v/, '').split(/[.+-]/).slice(0, 3).map(Number); const [first, second] = [parse(value('first')), parse(value('second'))]; const comparison = first.findIndex((part, index) => part !== second[index]); return comparison < 0 ? 'Versions are equal.' : `${value('first')} is ${first[comparison] > second[comparison] ? 'newer than' : 'older than'} ${value('second')}.`; }
    if (toolId === 'secret-redactor') return value('text').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, '[redacted-email]').replace(/\b(?:sk|pk|api|token|secret)[_-]?[A-Za-z0-9_-]{12,}\b/gi, '[redacted-secret]').replace(/\b(?:\d[ -]?){13,19}\b/g, '[redacted-number]');
    if (toolId === 'discount-calculator') { const discount = number('price') * number('rate') / 100; return `Discount: ${fixed(discount)}\nFinal price: ${fixed(number('price') - discount)}`; }
    if (toolId === 'commission-calculator') return `Commission: ${fixed(number('sales') * number('rate') / 100)}`;
    if (toolId === 'roi-calculator') { const cost = requirePositive(number('cost'), 'Investment cost'); return `ROI: ${fixed((number('return') - cost) / cost * 100)}%\nNet gain: ${fixed(number('return') - cost)}`; }
    if (toolId === 'cash-flow-summary') { const entries = parsePairs('entries'); const incoming = entries.reduce((sum, [, amount]) => sum + Math.max(0, Number(amount)), 0); const outgoing = entries.reduce((sum, [, amount]) => sum + Math.min(0, Number(amount)), 0); return `Incoming: ${fixed(incoming)}\nOutgoing: ${fixed(Math.abs(outgoing))}\nNet cash flow: ${fixed(incoming + outgoing)}`; }
    if (toolId === 'business-days-calculator') { const start = new Date(`${value('start')}T00:00:00`); const end = new Date(`${value('end')}T00:00:00`); if (Number.isNaN(start) || Number.isNaN(end)) throw new Error('Enter both dates.'); let days = 0; for (const date = new Date(start); date <= end; date.setDate(date.getDate() + 1)) if (![0, 6].includes(date.getDay())) days += 1; return `Business days: ${days}`; }
    if (toolId === 'meeting-agenda-builder') { const title = value('title'); const items = lines('items'); if (!title || !items.length) throw new Error('Enter a meeting title and agenda items.'); return `${title}\n${items.map((item, index) => `${index + 1}. ${item}`).join('\n')}`; }
    if (toolId === 'purchase-order-total') { const rows = parsePairs('items'); const total = rows.reduce((sum, [, quantity, price]) => sum + Number(quantity) * Number(price), 0); return `${rows.map(([item, quantity, price]) => `${item}: ${quantity} x ${price} = ${fixed(Number(quantity) * Number(price))}`).join('\n')}\n\nTotal: ${fixed(total)}`; }
    if (toolId === 'straight-line-depreciation') return `Annual depreciation: ${fixed((number('cost') - number('salvage')) / requirePositive(number('years'), 'Useful life'))}`;
    if (toolId === 'installment-calculator') return `Each installment: ${fixed(number('amount') / requirePositive(number('payments'), 'Installments'))}`;
    if (toolId === 'inventory-reorder-point') return `Reorder point: ${fixed(requirePositive(number('daily'), 'Daily demand') * requirePositive(number('lead'), 'Lead time') + number('safety'))} units`;
    if (toolId === 'invoice-number-generator') { const date = value('date'); if (!date) throw new Error('Enter an invoice date.'); return `${value('prefix') || 'INV'}-${date.replaceAll('-', '')}-${String(Math.max(1, Math.floor(number('sequence')))).padStart(4, '0')}`; }
    if (toolId === 'overtime-pay-calculator') { const hours = requirePositive(number('hours'), 'Total hours'); const rate = requirePositive(number('rate'), 'Hourly rate'); const threshold = requirePositive(number('threshold'), 'Regular-hours threshold'); const regular = Math.min(hours, threshold) * rate; const overtime = Math.max(0, hours - threshold) * rate * 1.5; return `Regular pay: ${fixed(regular)}\nOvertime pay: ${fixed(overtime)}\nTotal pay: ${fixed(regular + overtime)}`; }
    if (toolId === 'vat-calculator') { const amount = number('amount'); const vat = amount * number('rate') / 100; return `VAT: ${fixed(vat)}\nTotal: ${fixed(amount + vat)}`; }
    if (toolId === 'profit-margin-calculator') { const profit = number('revenue') - number('cost'); return `Profit: ${fixed(profit)}\nMargin: ${fixed(profit / requirePositive(number('revenue'), 'Sale price') * 100)}%`; }
    if (toolId === 'break-even-calculator') return `Break-even units: ${Math.ceil(requirePositive(number('fixed'), 'Fixed costs') / (requirePositive(number('price'), 'Unit price') - number('variable')))}`;
    if (toolId === 'invoice-due-date') { const date = new Date(`${value('date')}T00:00:00`); if (Number.isNaN(date)) throw new Error('Enter an invoice date.'); date.setDate(date.getDate() + number('days')); return `Due date: ${date.toLocaleDateString()}`; }
    if (toolId === 'timesheet-hours-calculator') { const hours = lines('entries').reduce((total, entry) => { const [start, end] = entry.split('-').map((time) => time.split(':').reduce((sum, part, index) => sum + Number(part) * (index ? 1 / 60 : 1), 0)); return total + (end - start); }, 0); return `Total hours: ${fixed(hours)}\nTotal minutes: ${Math.round(hours * 60)}`; }
    if (toolId === 'expense-splitter') return `Each person pays: ${fixed(number('amount') / requirePositive(number('people'), 'Participants'))}`;
    if (toolId === 'percentage-change') { const oldValue = requirePositive(number('old'), 'Original value'); const change = (number('new') - oldValue) / oldValue * 100; return `Change: ${change >= 0 ? '+' : ''}${fixed(change)}%`; }
    if (toolId === 'document-key-points') { const source = value('text'); const sentences = source.match(/[^.!?\n]+[.!?]?/g)?.map((sentence) => sentence.trim()).filter(Boolean) || []; const terms = source.toLowerCase().match(/[\p{L}\p{N}]{4,}/gu) || []; const frequencies = terms.reduce((all, term) => ({ ...all, [term]: (all[term] || 0) + 1 }), {}); return sentences.map((sentence) => ({ sentence, score: (sentence.toLowerCase().match(/[\p{L}\p{N}]{4,}/gu) || []).reduce((score, word) => score + (frequencies[word] || 0), 0) })).sort((left, right) => right.score - left.score).slice(0, 5).map((item, index) => `${index + 1}. ${item.sentence}`).join('\n'); }
    if (toolId === 'unit-converter' || toolId === 'cooking-measurement-converter') { const units = toolId === 'unit-converter' ? { m: 1, km: 1000, cm: .01, in: .0254, ft: .3048, kg: 1, lb: .45359237, mi: 1609.344 } : { ml: 1, cup: 236.588, tbsp: 14.7868, tsp: 4.92892 }; const from = value('from').toLowerCase(); const to = value('to').toLowerCase(); if (!units[from] || !units[to]) throw new Error('Use one of the listed units.'); return `${number('value')} ${from} = ${fixed(number('value') * units[from] / units[to])} ${to}`; }
    if (toolId === 'tip-calculator') { const tip = number('bill') * number('rate') / 100; return `Tip: ${fixed(tip)}\nTotal: ${fixed(number('bill') + tip)}\nPer person: ${fixed((number('bill') + tip) / requirePositive(number('people'), 'People'))}`; }
    if (toolId === 'age-calculator') { const birth = new Date(`${value('birth')}T00:00:00`); const today = new Date(); let age = today.getFullYear() - birth.getFullYear(); if (today < new Date(today.getFullYear(), birth.getMonth(), birth.getDate())) age -= 1; return `Age: ${age} years`; }
    if (toolId === 'date-difference') return `Difference: ${Math.abs(new Date(`${value('end')}T00:00:00`) - new Date(`${value('start')}T00:00:00`)) / 86400000} days`;
    if (toolId === 'time-zone-meeting-planner') { const date = new Date(`${value('datetime')}Z`); if (Number.isNaN(date)) throw new Error('Enter a meeting time.'); return `UTC: ${new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short', timeZone: 'UTC' }).format(date)}\n${value('zone')}: ${new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short', timeZone: value('zone') }).format(date)}`; }
    if (toolId === 'password-generator') { const length = Math.min(128, Math.max(8, Math.round(number('length')))); const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*?'; const random = crypto.getRandomValues(new Uint32Array(length)); return Array.from(random, (item) => chars[item % chars.length]).join(''); }
    if (toolId === 'bmi-calculator') { const height = requirePositive(number('height'), 'Height') / 100; const bmi = requirePositive(number('weight'), 'Weight') / height ** 2; return `BMI: ${fixed(bmi)}\nCategory: ${bmi < 18.5 ? 'Underweight' : bmi < 25 ? 'Healthy range' : bmi < 30 ? 'Overweight' : 'Obesity range'}`; }
    if (toolId === 'temperature-converter') { const source = value('from'); const target = value('to'); let celsius = number('value'); if (source === 'f') celsius = (celsius - 32) * 5 / 9; if (source === 'k') celsius -= 273.15; const result = target === 'f' ? celsius * 9 / 5 + 32 : target === 'k' ? celsius + 273.15 : celsius; return `${fixed(number('value'))} ${source.toUpperCase()} = ${fixed(result)} ${target.toUpperCase()}`; }
    if (toolId === 'pace-calculator') { const minutes = requirePositive(number('minutes'), 'Time'); const distance = requirePositive(number('distance'), 'Distance'); const seconds = Math.round(minutes / distance * 60); return `Pace: ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} min/km`; }
    if (toolId === 'fuel-cost-calculator') { const liters = requirePositive(number('distance'), 'Distance') * requirePositive(number('efficiency'), 'Fuel use') / 100; return `Fuel needed: ${fixed(liters)} L\nEstimated cost: ${fixed(liters * number('price'))}`; }
    if (toolId === 'loan-payment-estimator') { const months = requirePositive(number('months'), 'Months'); const monthlyRate = number('rate') / 1200; const payment = monthlyRate ? number('principal') * monthlyRate / (1 - (1 + monthlyRate) ** -months) : number('principal') / months; return `Estimated monthly payment: ${fixed(payment)}\nEstimated total paid: ${fixed(payment * months)}`; }
    if (toolId === 'random-decision-picker') { const choices = lines('choices'); if (!choices.length) throw new Error('Enter at least one choice.'); return `Selected: ${choices[crypto.getRandomValues(new Uint32Array(1))[0] % choices.length]}`; }
    if (toolId === 'chore-splitter') { const chores = lines('chores'); const people = lines('people'); if (!chores.length || !people.length) throw new Error('Enter chores and people.'); return people.map((person, index) => `${person}: ${chores.filter((_, choreIndex) => choreIndex % people.length === index).join(', ') || '-'}`).join('\n'); }
    if (toolId === 'sleep-time-planner') { const [hours, minutes] = value('wake').split(':').map(Number); if (!Number.isInteger(hours) || !Number.isInteger(minutes)) throw new Error('Enter a wake-up time.'); return [6, 5, 4].map((cycles) => { const date = new Date(); date.setHours(hours, minutes - cycles * 90 - 15, 0, 0); return `${cycles} cycles: ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`; }).join('\n'); }
    if (toolId === 'water-intake-estimator') return `Approximate daily water: ${fixed(requirePositive(number('weight'), 'Weight') * 0.033)} L`;
    if (toolId === 'random-number-generator') { const min = Math.ceil(number('min')); const max = Math.floor(number('max')); if (!Number.isFinite(min) || max < min) throw new Error('Maximum must be at least the minimum.'); return String(min + crypto.getRandomValues(new Uint32Array(1))[0] % (max - min + 1)); }
    if (toolId === 'text-cleaner') return value('text').split('\n').map((line) => line.trim().replace(/\s{2,}/g, ' ')).filter(Boolean).join('\n');
    if (toolId === 'light-background-cleanup') return cleanLightBackground();
    throw new Error('This browser tool is unavailable.');
  }
  $('#browser-run')?.addEventListener('click', async () => { try { const result = await runBrowserTool(); if (result !== null) output.value = result; } catch (error) { output.value = error.message || String(error); } });
  $('#browser-copy')?.addEventListener('click', async () => { if (output.value) await navigator.clipboard?.writeText(output.value); });
}


/* Infinity 7.0 — one contextual intelligence layer across the entire product. */
(() => {
  const ar = document.documentElement.lang === 'ar';
  const runtime = window.InfinityRuntimeContext = window.InfinityRuntimeContext || { lastResult: null, lastError: null, smartFile: null };
  const history = [];

  const parseJSONNode = (id) => {
    try { return JSON.parse(document.getElementById(id)?.textContent || '{}'); } catch (_) { return {}; }
  };
  const toolContext = parseJSONNode('tool-ai-context');

  const safeSelectedFiles = () => {
    try {
      return (selectedFiles || []).slice(0, 20).map((file) => {
        const match = String(file.name || '').toLowerCase().match(/(\.[a-z0-9]+)$/);
        return { extension: match ? match[1] : '', mime: file.type || '', size_bytes: Number(file.size || 0) };
      });
    } catch (_) { return []; }
  };
  const currentSettings = () => {
    const form = document.getElementById('converter-form');
    if (!form) return {};
    const settings = {};
    form.querySelectorAll('[name]').forEach((field) => {
      if (!field.name || !['select-one', 'number', 'range'].includes(field.type)) return;
      const value = String(field.value || '').slice(0, 300);
      if (value) settings[field.name] = value;
    });
    return settings;
  };
  const pageContext = () => ({
    path: location.pathname,
    page_title: document.title.slice(0, 220),
    tool: toolContext && toolContext.id ? toolContext : undefined,
    files: safeSelectedFiles(),
    smart_file: runtime.smartFile || undefined,
    settings: {},
    result: runtime.lastResult || undefined,
    error: runtime.lastError ? { present: true } : undefined,
    privacy: { file_contents_attached: false, filenames_attached: false },
  });

  const text = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value || '';
    return node;
  };
  const renderPlan = (container, data) => {
    container.replaceChildren();
    container.classList.add('v7-ai-render');
    const head = text('div', 'v7-ai-result-head', '');
    head.append(text('span', 'v7-ai-result-mark', '∞'));
    const copy = text('div', '', '');
    copy.append(text('strong', '', data.title || (ar ? 'مسار Infinity' : 'Infinity workflow')));
    copy.append(text('p', '', data.summary || ''));
    head.append(copy);
    container.append(head);
    if (Array.isArray(data.steps) && data.steps.length) {
      const steps = text('div', 'v7-ai-steps', '');
      data.steps.forEach((step, index) => {
        const row = text('a', 'v7-ai-step', '');
        row.href = step.url || '/tools';
        const n = text('span', 'v7-ai-step-number', String(step.order || index + 1).padStart(2, '0'));
        const body = text('span', 'v7-ai-step-copy', '');
        body.append(text('strong', '', step.tool_name || step.tool_id || (ar ? 'أداة' : 'Tool')));
        body.append(text('small', '', step.why || ''));
        const arrow = text('span', 'v7-ai-step-arrow', '↗');
        row.append(n, body, arrow);
        steps.append(row);
      });
      container.append(steps);
    }
    if (Array.isArray(data.tips) && data.tips.length) {
      const tips = text('div', 'v7-ai-tips', '');
      data.tips.slice(0, 4).forEach((tip) => tips.append(text('p', '', `◇ ${tip}`)));
      container.append(tips);
    }
    if (Array.isArray(data.questions) && data.questions.length) {
      const q = text('div', 'v7-ai-questions', '');
      q.append(text('strong', '', ar ? 'إذا تبي مسار أدق:' : 'For a more precise path:'));
      data.questions.slice(0, 3).forEach((item) => q.append(text('p', '', item)));
      container.append(q);
    }
    const source = text('small', 'v7-ai-source', data.enhanced ? (ar ? '✦ تحليل Infinity AI المتقدم' : '✦ Enhanced Infinity AI') : (ar ? '∞ Infinity Smart Core' : '∞ Infinity Smart Core'));
    container.append(source);
    container.hidden = false;
  };

  async function requestPlan(prompt, mode = 'plan', container, statusNode) {
    const value = String(prompt || '').trim();
    if (!value) return null;
    if (statusNode) statusNode.textContent = ar ? 'Infinity يفكر…' : 'Infinity is thinking…';
    if (container) { container.hidden = false; container.replaceChildren(text('div', 'v7-ai-loading', ar ? 'جارٍ بناء المسار من أدوات الموقع…' : 'Building a path from the real tool catalog…')); }
    try {
      const response = await fetch('/api/v2/ai/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ prompt: value, mode, lang: ar ? 'ar' : 'en', context: pageContext(), history: history.slice(-8) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || (ar ? 'تعذر إكمال الطلب.' : 'Could not complete the request.'));
      history.push({ role: 'user', text: value }, { role: 'assistant', text: `${data.title || ''}\n${data.summary || ''}` });
      if (history.length > 16) history.splice(0, history.length - 16);
      if (container) renderPlan(container, data);
      if (statusNode) statusNode.textContent = data.enhanced ? (ar ? 'تم · تحليل متقدم' : 'Done · enhanced') : (ar ? 'تم · Smart Core' : 'Done · Smart Core');
      return data;
    } catch (error) {
      if (container) { container.replaceChildren(text('p', 'v7-ai-error', error.message || String(error))); container.hidden = false; }
      if (statusNode) statusNode.textContent = ar ? 'تعذر إكمال الطلب' : 'Could not complete request';
      return null;
    }
  }

  // Homepage intelligence console.
  const homeForm = document.getElementById('ai-form');
  const homePrompt = document.getElementById('ai-prompt');
  const homeAnswer = document.getElementById('ai-answer');
  const homeStatus = document.getElementById('ai-status');
  document.querySelectorAll('[data-ai-prompt]').forEach((button) => button.addEventListener('click', () => {
    if (!homePrompt) return;
    homePrompt.value = button.dataset.aiPrompt || '';
    homePrompt.focus();
  }));
  if (homeForm && homePrompt && homeAnswer) homeForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = homeForm.querySelector('[type="submit"]'); if (button) button.disabled = true;
    await requestPlan(homePrompt.value, 'plan', homeAnswer, homeStatus);
    if (button) button.disabled = false;
  });
  const queryAI = new URLSearchParams(location.search).get('ai');
  if (queryAI && homePrompt) homePrompt.value = `${queryAI} — ${ar ? 'اقترح أفضل مسار والخطوة التالية.' : 'suggest the best workflow and next step.'}`;

  // Global contextual dock.
  const dock = document.getElementById('global-ai-dock');
  const toggle = document.getElementById('ai-dock-toggle');
  const panel = document.getElementById('ai-dock-panel');
  const close = document.getElementById('ai-dock-close');
  const globalForm = document.getElementById('global-ai-form');
  const globalPrompt = document.getElementById('global-ai-prompt');
  const globalAnswer = document.getElementById('global-ai-answer');
  const globalStatus = document.getElementById('global-ai-status');
  const dockState = document.getElementById('ai-dock-state');
  let globalMode = 'plan';
  function setDock(open) {
    if (!panel || !toggle) return;
    panel.hidden = !open; toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) setTimeout(() => globalPrompt?.focus(), 30);
  }
  toggle?.addEventListener('click', () => setDock(panel?.hidden));
  close?.addEventListener('click', () => setDock(false));
  document.querySelectorAll('[data-open-global-ai]').forEach((node) => node.addEventListener('click', () => setDock(true)));
  document.querySelectorAll('[data-global-ai-mode]').forEach((node) => node.addEventListener('click', () => {
    document.querySelectorAll('[data-global-ai-mode]').forEach((x) => x.classList.toggle('is-active', x === node));
    globalMode = node.dataset.globalAiMode || 'plan';
    if (globalMode === 'troubleshoot' && runtime.lastError && globalPrompt) globalPrompt.value = ar ? 'شخّص آخر خطأ حصل واقترح أقصر طريقة لإصلاحه.' : 'Diagnose the last conversion error and suggest the shortest recovery path.';
    if (globalMode === 'next' && runtime.lastResult && globalPrompt) globalPrompt.value = ar ? 'بناءً على نتيجة التحويل الحالية، هل فيه خطوة تالية مفيدة فعلًا؟' : 'Based on the current conversion result, is there a genuinely useful next step?';
  }));
  if (globalForm && globalPrompt && globalAnswer) globalForm.addEventListener('submit', async (event) => {
    event.preventDefault(); const button = globalForm.querySelector('[type="submit"]'); if (button) button.disabled = true;
    await requestPlan(globalPrompt.value, globalMode, globalAnswer, globalStatus);
    if (button) button.disabled = false;
  });
  async function checkStatus() {
    if (!globalStatus) return;
    try {
      const response = await fetch('/api/v2/ai/status', { headers: { Accept: 'application/json' } });
      const data = await response.json();
      if (dockState) dockState.dataset.state = data.enhanced_ready ? 'ready' : 'core';
      globalStatus.textContent = data.enhanced_ready ? (ar ? 'Smart Core + AI المتقدم جاهزان' : 'Smart Core + enhanced AI ready') : (ar ? 'Smart Core جاهز' : 'Smart Core ready');
    } catch (_) { globalStatus.textContent = ar ? 'Smart Core متاح' : 'Smart Core available'; }
  }
  checkStatus();

  // Tool-specific copilot buttons.
  const inline = document.getElementById('tool-ai-inline-answer');
  document.querySelectorAll('[data-tool-ai-action]').forEach((button) => button.addEventListener('click', async () => {
    const mode = button.dataset.toolAiAction || 'explain';
    let prompt = ar ? `ساعدني في أداة ${toolContext.name || ''}.` : `Help me with ${toolContext.name || 'this tool'}.`;
    if (mode === 'explain') prompt = ar ? 'اشرح لي هذه الأداة، متى أستخدمها، وما أهم شيء أنتبه له؟' : 'Explain this tool, when to use it, and the main trade-off I should watch.';
    if (mode === 'optimize') prompt = ar ? 'بناءً على الإعدادات والملفات المختارة حاليًا، وش الإعدادات أو الخيارات الأنسب ولماذا؟' : 'Based on the current settings and selected file metadata, what settings are best and why?';
    if (mode === 'troubleshoot') prompt = ar ? 'شخّص المشكلة الحالية في هذه الأداة. إذا ما فيه خطأ مسجل، علمني أكثر الأسباب الشائعة للفشل وكيف أتجنبها.' : 'Diagnose the current problem in this tool. If no error is recorded, explain the most common failure causes and how to avoid them.';
    if (mode === 'next') prompt = ar ? 'بعد استخدام هذه الأداة، وش الخطوة التالية المفيدة فعلًا بناءً على النتيجة الحالية؟' : 'After this tool, what is the genuinely useful next step based on the current result?';
    button.disabled = true; await requestPlan(prompt, mode, inline, null); button.disabled = false;
  }));

  // Full-screen assistant workspace.
  const assistantForm = document.getElementById('assistant-form');
  const assistantPrompt = document.getElementById('assistant-prompt');
  const assistantThread = document.getElementById('assistant-thread');
  const assistantStatus = document.getElementById('assistant-status');
  const assistantLabel = document.getElementById('assistant-mode-label');
  let assistantMode = 'plan';
  const modeLabels = ar ? { plan: 'تخطيط المسار', explain: 'شرح وفهم', optimize: 'تحسين الخيارات', troubleshoot: 'تشخيص وإصلاح' } : { plan: 'Workflow planning', explain: 'Explain & understand', optimize: 'Optimize choices', troubleshoot: 'Diagnose & fix' };
  document.querySelectorAll('[data-ai-mode]').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('[data-ai-mode]').forEach((x) => x.classList.toggle('is-active', x === button));
    assistantMode = button.dataset.aiMode || 'plan'; if (assistantLabel) assistantLabel.textContent = modeLabels[assistantMode] || modeLabels.plan;
    assistantPrompt?.focus();
  }));
  if (assistantForm && assistantPrompt && assistantThread) assistantForm.addEventListener('submit', async (event) => {
    event.preventDefault(); const value = assistantPrompt.value.trim(); if (!value) return;
    const userRow = text('div', 'v7-thread-user', ''); userRow.append(text('span', '', ar ? 'أنت' : 'You'), text('p', '', value)); assistantThread.append(userRow);
    const aiRow = text('div', 'v7-thread-ai', ''); const resultNode = text('div', 'v7-thread-ai-body', ''); aiRow.append(text('span', '', '∞'), resultNode); assistantThread.append(aiRow);
    assistantThread.scrollTop = assistantThread.scrollHeight;
    const button = assistantForm.querySelector('[type="submit"]'); if (button) button.disabled = true;
    const data = await requestPlan(value, assistantMode, resultNode, assistantStatus);
    if (button) button.disabled = false; if (data) { assistantPrompt.value = ''; assistantThread.scrollTop = assistantThread.scrollHeight; }
  });

  // Bridge homepage shortcut to the existing command palette.
  document.getElementById('v7-quick-jump')?.addEventListener('click', () => document.getElementById('command-trigger')?.click());
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && panel && !panel.hidden) setDock(false); });
})();

/* Subtle pointer spotlight on premium cards; disabled on touch/reduced motion. */
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && !window.matchMedia('(hover: none)').matches) {
  document.querySelectorAll('.tool-card,.workflow-card,.audience-card').forEach((card) => {
    card.addEventListener('pointermove', (event) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${event.clientX - r.left}px`);
      card.style.setProperty('--my', `${event.clientY - r.top}px`);
    });
  });
}

/* Knowledge Center: reveal motion that remains fully usable without JavaScript. */
(() => {
  const items = document.querySelectorAll('.reveal-on-scroll');
  if (!items.length) return;
  if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    items.forEach((item) => item.classList.add('is-visible'));
    return;
  }
  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      obs.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  items.forEach((item) => observer.observe(item));
})();


/* Knowledge Center reading progress. */
(() => {
  const bar = document.querySelector('#reading-progress-bar');
  if (!bar) return;
  const article = document.querySelector('.blog-article');
  const update = () => {
    const start = article ? article.offsetTop : 0;
    const end = article ? start + article.offsetHeight - window.innerHeight : document.documentElement.scrollHeight - window.innerHeight;
    const distance = Math.max(1, end - start);
    const progress = Math.min(1, Math.max(0, (window.scrollY - start) / distance));
    bar.style.transform = `scaleX(${progress})`;
  };
  update();
  addEventListener('scroll', update, { passive: true });
  addEventListener('resize', update);
})();


/* 7.1 living backdrop: subtle pointer response, never required for use. */
(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || window.matchMedia('(hover: none)').matches) return;
  let frame = 0;
  addEventListener('pointermove', (event) => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      document.documentElement.style.setProperty('--cursor-x', `${event.clientX}px`);
      document.documentElement.style.setProperty('--cursor-y', `${event.clientY}px`);
      frame = 0;
    });
  }, { passive: true });
})();

/* Install a conservative PWA worker that caches only same-origin static assets. */
(() => {
  if (!('serviceWorker' in navigator) || location.protocol !== 'https:') return;
  addEventListener('load', () => navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {}), { once: true });
})();
