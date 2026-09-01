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
const resultPanel = $("#result-panel");
if (form) form.addEventListener("submit", async (event) => {
  event.preventDefault(); const status = $("#status"); const result = $("#result");
  if (fileInput && !selectedFiles.length) { result.textContent = i18n("js.choose_file"); return; }
  status.textContent = i18n("js.processing"); result.textContent = "";
  const payload = new FormData(); payload.append("tool", $("#tool-id").value); selectedFiles.forEach((file) => payload.append("files", file));
  form.querySelectorAll("[name]").forEach((field) => { if (field.name && field.name !== "tool" && field.name !== "files" && field.value) payload.set(field.name, field.value); });
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

// Pricing billing toggle: presentation only until a payment provider is configured.
const billingButtons = $$('[data-billing]');
if (billingButtons.length) {
  const priceNodes = $$('[data-price-monthly]');
  billingButtons.forEach((button) => button.addEventListener('click', () => {
    billingButtons.forEach((b) => b.classList.toggle('is-active', b === button));
    const yearly = button.dataset.billing === 'yearly';
    priceNodes.forEach((node) => { node.textContent = `$${yearly ? node.dataset.priceYearly : node.dataset.priceMonthly}`; });
    $$('[data-billing-yearly]').forEach((node) => {
      node.textContent = yearly ? node.dataset.billingYearly : '';
      node.hidden = !yearly;
    });
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
  const number = (key) => Number(value(key));
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
    if (toolId === 'gpa-calculator') { const courses = parsePairs('courses'); const totals = courses.reduce((sum, [grade, credits]) => { const points = { 'A+': 4, A: 4, 'A-': 3.7, 'B+': 3.3, B: 3, 'B-': 2.7, 'C+': 2.3, C: 2, 'C-': 1.7, D: 1, F: 0 }[grade.toUpperCase()]; const hours = Number(credits); if (points === undefined || !hours) throw new Error('Use grades such as A, B+, C and positive credits.'); return [sum[0] + points * hours, sum[1] + hours]; }, [0, 0]); return `GPA: ${(totals[0] / totals[1]).toFixed(2)}\nCredits: ${totals[1]}`; }
    if (toolId === 'weighted-grade-calculator') { const pairs = parsePairs('items'); const totalWeight = pairs.reduce((sum, [, weight]) => sum + Number(weight), 0); const result = pairs.reduce((sum, [grade, weight]) => sum + Number(grade) * Number(weight), 0) / totalWeight; return `Weighted grade: ${fixed(result)}%\nTotal weight: ${fixed(totalWeight)}%`; }
    if (toolId === 'study-session-planner') { const minutes = requirePositive(number('minutes'), 'Minutes'); const topics = requirePositive(number('topics'), 'Topics'); const block = Math.floor(minutes / topics); return Array.from({ length: topics }, (_, index) => `Topic ${index + 1}: ${block} minutes${index < topics - 1 ? '\nBreak: 5 minutes' : ''}`).join('\n'); }
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
    if (toolId === 'pace-calculator') { const minutes = requirePositive(number('minutes'), 'Time'); const distance = requirePositive(number('distance'), 'Distance'); const pace = minutes / distance; return `Pace: ${Math.floor(pace)}:${String(Math.round((pace % 1) * 60)).padStart(2, '0')} min/km`; }
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
