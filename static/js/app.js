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
  filterTabs.forEach((item) => item.classList.toggle("is-active", item === tab));
  filterCards();
}));
filterCards();

const categoryLinks = $$('[data-filter]');
categoryLinks.forEach((link) => link.addEventListener("click", () => {
  if (!cards.some((card) => card.dataset.category === link.dataset.filter)) return;
  selectedFilter = link.dataset.filter;
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

  function runBrowserTool() {
    if (timerState.interval) { clearInterval(timerState.interval); timerState.interval = null; }
    if (toolId === 'gpa-calculator') { const courses = parsePairs('courses'); const totals = courses.reduce((sum, [grade, credits]) => { const points = { 'A+': 4, A: 4, 'A-': 3.7, 'B+': 3.3, B: 3, 'B-': 2.7, 'C+': 2.3, C: 2, 'C-': 1.7, D: 1, F: 0 }[grade.toUpperCase()]; const hours = Number(credits); if (points === undefined || !hours) throw new Error('Use grades such as A, B+, C and positive credits.'); return [sum[0] + points * hours, sum[1] + hours]; }, [0, 0]); return `GPA: ${(totals[0] / totals[1]).toFixed(2)}\nCredits: ${totals[1]}`; }
    if (toolId === 'weighted-grade-calculator') { const pairs = parsePairs('items'); const totalWeight = pairs.reduce((sum, [, weight]) => sum + Number(weight), 0); const result = pairs.reduce((sum, [grade, weight]) => sum + Number(grade) * Number(weight), 0) / totalWeight; return `Weighted grade: ${fixed(result)}%\nTotal weight: ${fixed(totalWeight)}%`; }
    if (toolId === 'study-session-planner') { const minutes = requirePositive(number('minutes'), 'Minutes'); const topics = requirePositive(number('topics'), 'Topics'); const block = Math.floor(minutes / topics); return Array.from({ length: topics }, (_, index) => `Topic ${index + 1}: ${block} minutes${index < topics - 1 ? '\nBreak: 5 minutes' : ''}`).join('\n'); }
    if (toolId === 'focus-timer') { let remaining = Math.round(requirePositive(number('minutes'), 'Minutes') * 60); const render = () => { output.value = `Focus time remaining: ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`; }; render(); timerState.interval = setInterval(() => { remaining -= 1; render(); if (remaining <= 0) { clearInterval(timerState.interval); timerState.interval = null; output.value = 'Focus session complete.'; } }, 1000); return null; }
    if (toolId === 'flashcard-maker') { return lines('cards').map((card, index) => { const [question, answer] = card.split('|').map((part) => part.trim()); if (!question || !answer) throw new Error('Use Question | answer on each line.'); return `${index + 1}. Q: ${question}\n   A: ${answer}`; }).join('\n\n'); }
    if (toolId === 'reading-time-estimator' || toolId === 'word-character-counter') { const text = value('text'); const words = text.match(/\S+/g)?.length || 0; return toolId === 'reading-time-estimator' ? `${words} words\nEstimated reading time: ${Math.max(1, Math.ceil(words / 200))} minute(s)` : `Words: ${words}\nCharacters: ${text.length}\nCharacters without spaces: ${text.replace(/\s/g, '').length}\nLines: ${text ? text.split('\n').length : 0}`; }
    if (toolId === 'rubric-score-calculator') { const rows = parsePairs('items'); const total = rows.reduce((sum, [, score, weight]) => sum + Number(score) / 4 * Number(weight), 0); return `Rubric score: ${fixed(total)}%\nBased on a 4-point scale.`; }
    if (toolId === 'classroom-group-maker' || toolId === 'seating-plan-generator') { const shuffled = lines('names').sort(() => crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32 - .5); const count = requirePositive(number(toolId === 'classroom-group-maker' ? 'groups' : 'columns'), toolId === 'classroom-group-maker' ? 'Groups' : 'Columns'); if (toolId === 'classroom-group-maker') return Array.from({ length: count }, (_, index) => `Group ${index + 1}: ${shuffled.filter((_, itemIndex) => itemIndex % count === index).join(', ') || '-'}`).join('\n'); return shuffled.map((name, index) => `${name}${(index + 1) % count ? '\t' : '\n'}`).join('').trim(); }
    if (toolId === 'random-name-picker') { const names = lines('names'); if (!names.length) throw new Error('Enter at least one name.'); return `Selected name: ${names[crypto.getRandomValues(new Uint32Array(1))[0] % names.length]}`; }
    if (toolId === 'score-to-percentage') return `${fixed(number('score') / requirePositive(number('total'), 'Total') * 100)}%`;
    if (toolId === 'lesson-timing-planner') { const minutes = requirePositive(number('minutes'), 'Minutes'); return `Opening: ${Math.round(minutes * .1)} min\nInstruction: ${Math.round(minutes * .65)} min\nPractice: ${Math.round(minutes * .15)} min\nReview: ${Math.round(minutes * .1)} min`; }
    if (toolId === 'learning-objective-builder') return `By the end of the lesson, learners will be able to ${value('verb')} ${value('topic')} ${value('condition') ? ` ${value('condition')}` : ''}.`;
    if (toolId === 'jwt-decoder') { const [header, payload] = value('token').split('.'); if (!header || !payload) throw new Error('Enter a JWT with header.payload.signature.'); return `Header (signature unverified):\n${JSON.stringify(JSON.parse(base64Url(header)), null, 2)}\n\nPayload:\n${JSON.stringify(JSON.parse(base64Url(payload)), null, 2)}`; }
    if (toolId === 'query-string-parser-builder') { const source = value('query').replace(/^\?/, ''); return source.includes('&') || source.includes('?') ? JSON.stringify(Object.fromEntries(new URLSearchParams(source)), null, 2) : new URLSearchParams(lines('query').map((line) => line.split('='))).toString(); }
    if (toolId === 'html-entity-converter') { const text = value('text'); const decoded = document.createElement('textarea'); decoded.innerHTML = text; return decoded.value === text ? text.replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char])) : decoded.value; }
    if (toolId === 'unicode-inspector') return [...value('text')].map((char) => `${char}\tU+${char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')}\t\\u{${char.codePointAt(0).toString(16).toUpperCase()}}`).join('\n');
    if (toolId === 'cron-explainer') { const [minute, hour, day, month, weekday, extra] = value('expression').split(/\s+/); if (!weekday || extra) throw new Error('Use exactly five cron fields.'); return `Minute: ${minute}\nHour: ${hour}\nDay of month: ${day}\nMonth: ${month}\nDay of week: ${weekday}`; }
    if (toolId === 'color-contrast-checker') { const ratio = (Math.max(luminance(hexToRgb(value('foreground'))), luminance(hexToRgb(value('background')))) + .05) / (Math.min(luminance(hexToRgb(value('foreground'))), luminance(hexToRgb(value('background')))) + .05); return `Contrast ratio: ${ratio.toFixed(2)}:1\nWCAG AA normal text: ${ratio >= 4.5 ? 'Pass' : 'Fail'}\nWCAG AA large text: ${ratio >= 3 ? 'Pass' : 'Fail'}`; }
    if (toolId === 'semantic-version-comparator') { const parse = (version) => version.replace(/^v/, '').split(/[.+-]/).slice(0, 3).map(Number); const [first, second] = [parse(value('first')), parse(value('second'))]; const comparison = first.findIndex((part, index) => part !== second[index]); return comparison < 0 ? 'Versions are equal.' : `${value('first')} is ${first[comparison] > second[comparison] ? 'newer than' : 'older than'} ${value('second')}.`; }
    if (toolId === 'vat-calculator') { const amount = number('amount'); const vat = amount * number('rate') / 100; return `VAT: ${fixed(vat)}\nTotal: ${fixed(amount + vat)}`; }
    if (toolId === 'profit-margin-calculator') { const profit = number('revenue') - number('cost'); return `Profit: ${fixed(profit)}\nMargin: ${fixed(profit / requirePositive(number('revenue'), 'Sale price') * 100)}%`; }
    if (toolId === 'break-even-calculator') return `Break-even units: ${Math.ceil(requirePositive(number('fixed'), 'Fixed costs') / (requirePositive(number('price'), 'Unit price') - number('variable')))}`;
    if (toolId === 'invoice-due-date') { const date = new Date(`${value('date')}T00:00:00`); if (Number.isNaN(date)) throw new Error('Enter an invoice date.'); date.setDate(date.getDate() + number('days')); return `Due date: ${date.toLocaleDateString()}`; }
    if (toolId === 'timesheet-hours-calculator') { const hours = lines('entries').reduce((total, entry) => { const [start, end] = entry.split('-').map((time) => time.split(':').reduce((sum, part, index) => sum + Number(part) * (index ? 1 / 60 : 1), 0)); return total + (end - start); }, 0); return `Total hours: ${fixed(hours)}\nTotal minutes: ${Math.round(hours * 60)}`; }
    if (toolId === 'expense-splitter') return `Each person pays: ${fixed(number('amount') / requirePositive(number('people'), 'Participants'))}`;
    if (toolId === 'percentage-change') { const oldValue = requirePositive(number('old'), 'Original value'); const change = (number('new') - oldValue) / oldValue * 100; return `Change: ${change >= 0 ? '+' : ''}${fixed(change)}%`; }
    if (toolId === 'unit-converter' || toolId === 'cooking-measurement-converter') { const units = toolId === 'unit-converter' ? { m: 1, km: 1000, cm: .01, in: .0254, ft: .3048, kg: 1, lb: .45359237, mi: 1609.344 } : { ml: 1, cup: 236.588, tbsp: 14.7868, tsp: 4.92892 }; const from = value('from').toLowerCase(); const to = value('to').toLowerCase(); if (!units[from] || !units[to]) throw new Error('Use one of the listed units.'); return `${number('value')} ${from} = ${fixed(number('value') * units[from] / units[to])} ${to}`; }
    if (toolId === 'tip-calculator') { const tip = number('bill') * number('rate') / 100; return `Tip: ${fixed(tip)}\nTotal: ${fixed(number('bill') + tip)}\nPer person: ${fixed((number('bill') + tip) / requirePositive(number('people'), 'People'))}`; }
    if (toolId === 'age-calculator') { const birth = new Date(`${value('birth')}T00:00:00`); const today = new Date(); let age = today.getFullYear() - birth.getFullYear(); if (today < new Date(today.getFullYear(), birth.getMonth(), birth.getDate())) age -= 1; return `Age: ${age} years`; }
    if (toolId === 'date-difference') return `Difference: ${Math.abs(new Date(`${value('end')}T00:00:00`) - new Date(`${value('start')}T00:00:00`)) / 86400000} days`;
    if (toolId === 'time-zone-meeting-planner') { const date = new Date(`${value('datetime')}Z`); if (Number.isNaN(date)) throw new Error('Enter a meeting time.'); return `UTC: ${new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short', timeZone: 'UTC' }).format(date)}\n${value('zone')}: ${new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short', timeZone: value('zone') }).format(date)}`; }
    if (toolId === 'password-generator') { const length = Math.min(128, Math.max(8, Math.round(number('length')))); const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*?'; const random = crypto.getRandomValues(new Uint32Array(length)); return Array.from(random, (item) => chars[item % chars.length]).join(''); }
    throw new Error('This browser tool is unavailable.');
  }
  $('#browser-run')?.addEventListener('click', () => { try { const result = runBrowserTool(); if (result !== null) output.value = result; } catch (error) { output.value = error.message || String(error); } });
  $('#browser-copy')?.addEventListener('click', async () => { if (output.value) await navigator.clipboard?.writeText(output.value); });
}
