const $ = (selector) => document.querySelector(selector);
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

const cards = $$(".tool-card");
const emptyState = $("#empty-state") || $("#listing-empty");
const search = $("#tool-search") || $("#listing-search");
const filterTabs = $$('[data-filter]');
let selectedFilter = "all";

function filterCards() {
  if (!cards.length) return;
  const query = search ? search.value.trim().toLowerCase() : "";
  let visible = 0;
  cards.forEach((card) => {
    const text = (card.dataset.search || "").toLowerCase();
    const category = card.dataset.category || "";
    const matchesFilter = selectedFilter === "all"
      || (selectedFilter === "popular" ? card.dataset.popular === "true" : category === selectedFilter);
    card.hidden = !text.includes(query) || !matchesFilter;
    if (!card.hidden) visible += 1;
  });
  if (emptyState) emptyState.hidden = visible > 0;
}
if (search) search.addEventListener("input", filterCards);
filterTabs.forEach((tab) => tab.addEventListener("click", () => {
  selectedFilter = tab.dataset.filter;
  filterTabs.forEach((item) => item.classList.toggle("is-active", item === tab));
  filterCards();
}));
filterCards();

const categoryLinks = $$(".category-list [data-category]");
categoryLinks.forEach((link) => link.addEventListener("click", () => {
  selectedFilter = link.dataset.category;
  filterTabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.filter === selectedFilter));
  filterCards();
  $("#tools")?.scrollIntoView({ behavior: "smooth" });
}));

function renderSuggestions(query) {
  const suggestions = $("#search-suggestions");
  if (!suggestions || !query) { if (suggestions) suggestions.innerHTML = ""; return; }
  const matches = cards.filter((card) => (card.dataset.search || "").toLowerCase().includes(query)).slice(0, 4);
  suggestions.innerHTML = matches.map((card) => `<a href="${card.href}">${card.querySelector("h3, h2")?.textContent || i18n("js.open_tool")}<span aria-hidden="true">←</span></a>`).join("");
}
if (search) search.addEventListener("input", () => renderSuggestions(search.value.trim().toLowerCase()));

function readRecent() { return JSON.parse(localStorage.getItem("infinity-recent") || "[]"); }
function saveRecent(toolId, name) {
  const recent = readRecent().filter((item) => item.id !== toolId);
  recent.unshift({ id: toolId, name });
  localStorage.setItem("infinity-recent", JSON.stringify(recent.slice(0, 5)));
}
function renderRecent() {
  const section = $("#personal-tools");
  const list = $("#recent-list");
  if (!section || !list) return;
  const recent = readRecent();
  section.hidden = recent.length === 0;
  list.innerHTML = recent.map((item) => `<a href="/tool/${item.id}">${item.name} <span aria-hidden="true">←</span></a>`).join("");
}
$("#clear-recent")?.addEventListener("click", () => { localStorage.removeItem("infinity-recent"); renderRecent(); });

function readFavorites() { return JSON.parse(localStorage.getItem("infinity-favorites") || "[]"); }
function renderFavorites() {
  const section = $("#favorite-tools");
  const list = $("#favorite-list");
  if (!section || !list) return;
  const favorites = readFavorites();
  section.hidden = favorites.length === 0;
  list.innerHTML = favorites.map((item) => `<a href="/tool/${item.id}">${item.name} <span aria-hidden="true">←</span></a>`).join("");
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
  else favorites.unshift({ id: favoriteButton.dataset.toolId, name: favoriteButton.dataset.toolName });
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
const I18N = window.I18N || {};
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
const resultPanel = $("#result-panel");
if (form) form.addEventListener("submit", async (event) => {
  event.preventDefault(); const status = $("#status"); const result = $("#result");
  if (!selectedFiles.length) { result.textContent = i18n("js.choose_file"); return; }
  status.textContent = i18n("js.processing"); result.textContent = "";
  const payload = new FormData(); payload.append("tool", $("#tool-id").value); selectedFiles.forEach((file) => payload.append("files", file));
  const paramField = $("#param"); if (paramField && paramField.value) payload.append("param", paramField.value);
  try {
    const response = await fetch("/api/v2/convert", { method: "POST", body: payload }); const type = response.headers.get("content-type") || "";
    if (!response.ok) { const data = type.includes("application/json") ? await response.json() : {}; throw new Error(data.error || i18n("js.generic_error")); }
    const blob = await response.blob(); const match = (response.headers.get("content-disposition") || "").match(/filename="?([^\"]+)"?/i); const filename = match ? match[1] : "InfinityConverter-result";
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    const batchTotal = Number(response.headers.get("X-Batch-Total") || 0);
    const batchFailed = Number(response.headers.get("X-Batch-Failed") || 0);
    saveRecent($("#tool-id").value, document.title.split(" | ")[0]); renderRecent(); status.textContent = i18n("js.completed");
    result.textContent = i18n("js.result_label", { filename, size: Math.ceil(blob.size / 1024) });
    if (batchTotal > 1) { const summary = document.createElement("p"); summary.className = "batch-summary"; summary.textContent = i18n("js.batch_summary", { total: batchTotal, succeeded: batchTotal - batchFailed, failed: batchFailed }); result.after(summary); }
    if (resultPanel) resultPanel.hidden = false;
  } catch (error) { status.textContent = i18n("js.failed"); result.textContent = error.message; }
});
$("#reset-tool")?.addEventListener("click", () => { selectedFiles = []; renderFiles(); if (intelligence) intelligence.hidden = true; if (resultPanel) resultPanel.hidden = true; $("#status").textContent = i18n("js.ready"); $("#result").textContent = ""; document.querySelectorAll(".batch-summary").forEach((el) => el.remove()); });

document.addEventListener("keydown", (event) => {
  if ((event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) || ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k")) { event.preventDefault(); search?.focus(); }
});
