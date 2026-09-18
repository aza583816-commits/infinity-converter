(() => {
  "use strict";
  const form = document.getElementById("workspace-inspector-form");
  if (!form) return;

  const fileInput = document.getElementById("workspace-file");
  const status = document.getElementById("workspace-status");
  const result = document.getElementById("workspace-inspector-result");
  const label = document.getElementById("workspace-file-label");
  const summary = document.getElementById("workspace-file-summary");
  const facts = document.getElementById("workspace-file-facts");
  const recommendations = document.getElementById("workspace-recommendations");
  const grid = document.getElementById("workspace-recommendation-grid");
  const projectBoard = document.getElementById("workspace-project-board");
  const projectFiles = document.getElementById("workspace-project-files");
  const projectCount = document.getElementById("workspace-project-count");
  const recents = document.getElementById("workspace-recents");
  const recentList = document.getElementById("workspace-recent-list");
  const clearRecents = document.getElementById("workspace-clear-recents");
  const builder = document.getElementById("workspace-builder");
  const builderStatus = document.getElementById("workspace-builder-status");
  const builderStepsNode = document.getElementById("workspace-builder-steps");
  const builderNextTool = document.getElementById("workspace-next-tool");
  const builderAddStep = document.getElementById("workspace-add-step");
  const builderReset = document.getElementById("workspace-builder-reset");
  const builderRun = document.getElementById("workspace-run-builder");
  const savePreset = document.getElementById("workspace-save-preset");
  const savedPreset = document.getElementById("workspace-saved-preset");
  const loadPreset = document.getElementById("workspace-load-preset");
  const deletePreset = document.getElementById("workspace-delete-preset");
  const installApp = document.getElementById("workspace-install-app");
  const recovery = document.getElementById("workspace-session-recovery");
  const restoreSession = document.getElementById("workspace-restore-session");
  const discardSession = document.getElementById("workspace-discard-session");
  const runQueue = document.getElementById("workspace-run-queue");
  const clearQueue = document.getElementById("workspace-clear-queue");
  const queueList = document.getElementById("workspace-queue-list");
  const en = document.documentElement.lang === "en";
  let catalogPromise = null;
  let builderCatalogPromise = null;
  let builderFile = null;
  let builderExt = "";
  let builderSteps = [];
  let projectEntries = [];
  let pendingRestore = null;

  function emitEvent(event) {
    try {
      fetch("/api/v2/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        keepalive: true,
        body: JSON.stringify({ event, path: location.pathname }),
      }).catch(() => {});
    } catch (_) {}
  }

  const copy = en ? {
    inspecting: "Inspecting safely…",
    ready: "Ready",
    failed: "Could not inspect this file.",
    invalid: "Choose at least one file first.",
    safe: "The file passed Infinity's inspection checks.",
    type: "Type",
    size: "Size",
    pages: "Pages",
    encrypted: "Encrypted",
    yes: "Yes",
    no: "No",
    open: "Open",
  } : {
    inspecting: "جاري الفحص بأمان…",
    ready: "جاهز",
    failed: "تعذر فحص هذا الملف.",
    invalid: "اختر ملفًا واحدًا على الأقل.",
    safe: "الملف اجتاز فحوصات Infinity.",
    type: "النوع",
    size: "الحجم",
    pages: "الصفحات",
    encrypted: "مشفّر",
    yes: "نعم",
    no: "لا",
    open: "افتح",
  };

  const known = {
    ".pdf": [
      ["workflow", "scan-to-searchable-pdf", "OCR + compress", "OCR + ضغط", "OCR and compression for scanned PDFs.", "OCR وضغط لملفات PDF الممسوحة."],
      ["tool", "pdf-compress", "Compress PDF", "ضغط PDF", "Reduce size while keeping the PDF workflow intact.", "قلل الحجم مع الحفاظ على مسار PDF."],
      ["tool", "pdf-to-word", "PDF to Word", "PDF إلى Word", "Make the document easier to edit when layout allows.", "حوّل الملف إلى Word للتعديل عندما تسمح البنية."]
    ],
    ".doc": [
      ["workflow", "office-share-ready", "Share-ready document", "مستند جاهز للمشاركة", "Convert Word to PDF and compress it in one verified chain.", "حوّل Word إلى PDF ثم اضغطه في مسار متحقق."],
      ["tool", "word-to-pdf", "Word to PDF", "Word إلى PDF", "Create a shareable PDF.", "أنشئ PDF جاهزًا للمشاركة."]
    ],
    ".docx": [
      ["workflow", "office-share-ready", "Share-ready document", "مستند جاهز للمشاركة", "Convert Word to PDF and compress it in one verified chain.", "حوّل Word إلى PDF ثم اضغطه في مسار متحقق."],
      ["tool", "word-to-pdf", "Word to PDF", "Word إلى PDF", "Create a shareable PDF.", "أنشئ PDF جاهزًا للمشاركة."]
    ],
    ".png": [
      ["workflow", "web-ready-image", "Web-ready image", "صورة جاهزة للويب", "Convert, compress and strip metadata in one chain.", "حوّل واضغط وأزل البيانات الوصفية في مسار واحد."],
      ["tool", "image-ocr", "Extract text", "استخراج النص", "Use OCR when the image contains readable text.", "استخدم OCR عندما تحتوي الصورة على نص."]
    ],
    ".jpg": [
      ["workflow", "web-ready-image", "Web-ready image", "صورة جاهزة للويب", "Compress and strip metadata for web sharing.", "اضغط وأزل البيانات الوصفية للمشاركة على الويب."],
      ["tool", "image-ocr", "Extract text", "استخراج النص", "Use OCR when the image contains readable text.", "استخدم OCR عندما تحتوي الصورة على نص."]
    ],
    ".jpeg": [
      ["workflow", "web-ready-image", "Web-ready image", "صورة جاهزة للويب", "Compress and strip metadata for web sharing.", "اضغط وأزل البيانات الوصفية للمشاركة على الويب."],
      ["tool", "image-ocr", "Extract text", "استخراج النص", "Use OCR when the image contains readable text.", "استخدم OCR عندما تحتوي الصورة على نص."]
    ],
    ".webp": [
      ["workflow", "web-ready-image", "Web-ready image", "صورة جاهزة للويب", "Normalize and optimize the image.", "وحّد الصيغة وحسّن الصورة."]
    ],
    ".xlsx": [
      ["tool", "excel-to-pdf", "Excel to PDF", "Excel إلى PDF", "Create a shareable document copy.", "أنشئ نسخة مستندية قابلة للمشاركة."]
    ],
    ".pptx": [
      ["tool", "ppt-to-pdf", "PowerPoint to PDF", "PowerPoint إلى PDF", "Create a portable presentation copy.", "أنشئ نسخة عرض قابلة للمشاركة."]
    ],
    ".zip": [
      ["tool", "zip-extract", "Extract archive", "فك الضغط", "Inspect and extract a safe archive.", "افحص وفك أرشيف آمن."]
    ]
  };

  const RECENTS_KEY = "infinity_workspace_recents_v1";
  const PRESETS_KEY = "infinity_workspace_presets_v1";
  const SESSION_KEY = "infinity_workspace_session_v1";
  let deferredInstallPrompt = null;

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    if (installApp) installApp.hidden = false;
  });

  installApp?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    try { await deferredInstallPrompt.userChoice; } catch (_) {}
    deferredInstallPrompt = null;
    installApp.hidden = true;
    emitEvent("workspace_install");
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    if (installApp) installApp.hidden = true;
  });


  function safeSessionRead() {
    try {
      const value = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
      if (!value || typeof value !== "object") return null;
      if (Date.now() - Number(value.at || 0) > 6 * 60 * 60 * 1000) return null;
      if (!/^\.[a-z0-9]{1,10}$/.test(String(value.extension || ""))) return null;
      if (!Array.isArray(value.steps) || value.steps.length > 4) return null;
      if (!value.steps.every((step) => typeof step === "string" && /^[a-z0-9:-]{1,80}$/.test(step))) return null;
      return value;
    } catch (_) { return null; }
  }

  function persistSessionPlan() {
    if (!builderExt) return;
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({
        at: Date.now(),
        extension: builderExt,
        steps: builderSteps.map((step) => step.id),
      }));
    } catch (_) {}
  }

  function renderSessionRecovery() {
    if (!recovery) return;
    const saved = safeSessionRead();
    recovery.hidden = !saved;
    if (saved) pendingRestore = saved;
  }

  restoreSession?.addEventListener("click", () => {
    const saved = safeSessionRead();
    if (!saved) { renderSessionRecovery(); return; }
    pendingRestore = saved;
    if (fileInput) fileInput.focus();
    if (status) status.textContent = en
      ? `Plan ready to restore for ${saved.extension.toUpperCase()}. Re-select the file.`
      : `الخطة جاهزة لنوع ${saved.extension.toUpperCase()}. اختر الملف من جديد.`;
  });

  discardSession?.addEventListener("click", () => {
    try { sessionStorage.removeItem(SESSION_KEY); } catch (_) {}
    pendingRestore = null;
    renderSessionRecovery();
  });

  renderSessionRecovery();

  function safeRecentRead() {
    try {
      const value = JSON.parse(localStorage.getItem(RECENTS_KEY) || "[]");
      return Array.isArray(value) ? value.slice(0, 8) : [];
    } catch (_) { return []; }
  }

  function renderRecents() {
    if (!recentList || !recents) return;
    const items = safeRecentRead();
    recentList.replaceChildren();
    items.forEach((item) => {
      const row = document.createElement("span");
      row.className = "text-button";
      const when = item.at ? new Date(item.at).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "";
      row.textContent = `${String(item.extension || "file").toUpperCase()} · ${bytes(item.size_bytes || 0)}${when ? " · " + when : ""}`;
      recentList.append(row);
    });
    recents.hidden = !items.length;
  }

  function rememberRecent(data, fallbackSize) {
    const item = {
      extension: String(data.extension || "").slice(0, 16),
      size_bytes: Number(data.size || fallbackSize || 0),
      pages: Number(data.pages || 0),
      at: Date.now(),
    };
    try {
      const existing = safeRecentRead();
      localStorage.setItem(RECENTS_KEY, JSON.stringify([item, ...existing].slice(0, 8)));
    } catch (_) {}
    renderRecents();
  }

  clearRecents?.addEventListener("click", () => {
    try { localStorage.removeItem(RECENTS_KEY); } catch (_) {}
    renderRecents();
  });
  renderRecents();

  async function catalogIndex() {
    if (!catalogPromise) {
      catalogPromise = fetch("/api/v2/discovery", { credentials: "same-origin" })
        .then((response) => response.ok ? response.json() : Promise.reject(new Error("catalog unavailable")))
        .then((payload) => {
          const map = new Map();
          for (const item of payload.items || []) {
            map.set(item.id, item);
            if (item.raw_id && !map.has(item.raw_id)) map.set(item.raw_id, item);
          }
          return map;
        })
        .catch(() => new Map());
    }
    return catalogPromise;
  }

  function bytes(value) {
    const n = Number(value || 0);
    if (!Number.isFinite(n) || n <= 0) return "";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function addFact(text) {
    const span = document.createElement("span");
    span.textContent = text;
    facts.append(span);
  }

  function card(item, catalogItem = null) {
    const [kind, id, titleEn, titleAr, descEn, descAr] = item;
    const a = document.createElement("a");
    a.className = "workflow-card";
    a.href = kind === "workflow" ? `/workflows?recipe=${encodeURIComponent(id)}` : (catalogItem?.url || "/tools");
    const icon = document.createElement("span");
    icon.className = "tool-icon large";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = kind === "workflow" ? "FLOW" : "→";
    const strong = document.createElement("strong");
    strong.textContent = en ? titleEn : titleAr;
    const p = document.createElement("p");
    p.textContent = en ? descEn : descAr;
    const open = document.createElement("span");
    open.className = "text-button";
    open.textContent = copy.open + " ↗";
    a.append(icon, strong, p, open);
    return a;
  }

  async function renderRecommendations(ext) {
    grid.replaceChildren();
    const catalog = await catalogIndex();
    const items = known[String(ext || "").toLowerCase()] || [
      ["tool", "tools", "Browse compatible tools", "تصفح الأدوات المتوافقة", "Use the complete Infinity catalog to choose the next action.", "استخدم كتالوج Infinity الكامل لاختيار الخطوة التالية."]
    ];
    for (const item of items) {
      if (item[1] === "tools") {
        const a = card(["tool", "tools", item[2], item[3], item[4], item[5]]);
        a.href = "/tools";
        grid.append(a);
        continue;
      }
      if (item[0] === "workflow") {
        grid.append(card(item));
        continue;
      }
      const actual = catalog.get(item[1]);
      if (actual) grid.append(card(item, actual));
    }
    if (!grid.children.length) {
      const fallback = card(["tool", "tools", "Browse compatible tools", "تصفح الأدوات المتوافقة", "Use the complete Infinity catalog to choose the next action.", "استخدم كتالوج Infinity الكامل لاختيار الخطوة التالية."]);
      fallback.href = "/tools";
      grid.append(fallback);
    }
    recommendations.hidden = false;
  }


  function safePresetRead() {
    try {
      const value = JSON.parse(localStorage.getItem(PRESETS_KEY) || "[]");
      if (!Array.isArray(value)) return [];
      return value.slice(0, 10).filter((item) =>
        item && typeof item === "object" &&
        typeof item.extension === "string" &&
        Array.isArray(item.steps) &&
        item.steps.length >= 1 && item.steps.length <= 4 &&
        item.steps.every((step) => typeof step === "string" && /^[a-z0-9:-]{1,80}$/.test(step))
      );
    } catch (_) { return []; }
  }

  function renderSavedPresets() {
    if (!savedPreset) return;
    const current = savedPreset.value;
    savedPreset.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = en ? "No saved preset selected" : "لا يوجد مسار محدد";
    savedPreset.append(empty);
    safePresetRead().forEach((item, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      const names = item.steps.join(" → ");
      option.textContent = (item.extension || "file").toUpperCase() + " · " + names;
      savedPreset.append(option);
    });
    if ([...savedPreset.options].some((option) => option.value === current)) savedPreset.value = current;
  }

  savePreset?.addEventListener("click", () => {
    if (!builderExt || !builderSteps.length) return;
    const item = {
      extension: builderExt,
      steps: builderSteps.map((step) => step.id),
      at: Date.now(),
    };
    try {
      const existing = safePresetRead().filter((preset) =>
        !(preset.extension === item.extension && JSON.stringify(preset.steps) === JSON.stringify(item.steps))
      );
      localStorage.setItem(PRESETS_KEY, JSON.stringify([item, ...existing].slice(0, 10)));
    } catch (_) {}
    renderSavedPresets();
    emitEvent("workspace_preset_save");
    if (builderStatus) builderStatus.textContent = en ? "Preset saved on this device ✓" : "تم حفظ المسار على هذا الجهاز ✓";
  });

  loadPreset?.addEventListener("click", async () => {
    const rawIndex = savedPreset?.value || "";
    if (!/^\d+$/.test(rawIndex)) return;
    const index = Number(rawIndex);
    const presets = safePresetRead();
    if (!Number.isInteger(index) || index < 0 || index >= presets.length) return;
    const preset = presets[index];
    if (preset.extension !== builderExt) {
      if (builderStatus) builderStatus.textContent = en ? "This preset starts with a different file type." : "هذا المسار يبدأ بنوع ملف مختلف.";
      return;
    }
    const catalog = await builderCatalog();
    const byId = new Map(catalog.map((item) => [item.id, item]));
    const next = [];
    let current = builderExt;
    for (const id of preset.steps) {
      const item = byId.get(id);
      if (!item || !acceptsExtension(item, current)) {
        if (builderStatus) builderStatus.textContent = en ? "Saved preset is no longer compatible." : "المسار المحفوظ لم يعد متوافقًا.";
        return;
      }
      next.push(item);
      current = item.output_ext;
    }
    builderSteps = next;
    document.querySelectorAll("[data-workspace-profile]").forEach((button) => button.classList.remove("is-active"));
    await renderBuilder();
  });

  deletePreset?.addEventListener("click", () => {
    const rawIndex = savedPreset?.value || "";
    if (!/^\d+$/.test(rawIndex)) return;
    const index = Number(rawIndex);
    const presets = safePresetRead();
    if (!Number.isInteger(index) || index < 0 || index >= presets.length) return;
    presets.splice(index, 1);
    try { localStorage.setItem(PRESETS_KEY, JSON.stringify(presets)); } catch (_) {}
    renderSavedPresets();
  });

  renderSavedPresets();

  async function builderCatalog() {
    if (!builderCatalogPromise) {
      builderCatalogPromise = fetch("/api/v2/discovery", { credentials: "same-origin" })
        .then((response) => response.ok ? response.json() : Promise.reject(new Error("catalog unavailable")))
        .then((payload) => (payload.items || []).filter((item) => item.kind === "converter" && item.workflow_safe))
        .catch(() => []);
    }
    return builderCatalogPromise;
  }

  function acceptsExtension(item, extension) {
    const accepted = (item?.input_ext || []).map((value) => String(value).toLowerCase());
    const ext = String(extension || "").toLowerCase();
    return accepted.includes(ext) || accepted.includes("*") || accepted.includes(".*");
  }

  function stepLabel(item) {
    return en ? item.name_en : item.name_ar;
  }

  function contentDispositionFilename(response) {
    const header = response.headers.get("content-disposition") || "";
    const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf) {
      try { return decodeURIComponent(utf[1]); } catch (_) {}
    }
    const plain = header.match(/filename="?([^";]+)"?/i);
    return plain ? plain[1] : "Infinity-Workflow-Result";
  }

  async function renderBuilder() {
    if (!builder || !builderNextTool || !builderStepsNode) return;
    const catalog = await builderCatalog();
    const currentExt = builderSteps.length ? builderSteps[builderSteps.length - 1].output_ext : builderExt;

    builderStepsNode.replaceChildren();
    if (!builderSteps.length) {
      const empty = document.createElement("span");
      empty.className = "text-button";
      empty.textContent = (en ? "Start: " : "البداية: ") + (builderExt || "—");
      builderStepsNode.append(empty);
    } else {
      builderSteps.forEach((item, index) => {
        const chip = document.createElement("span");
        chip.className = "text-button";
        chip.textContent = String(index + 1).padStart(2, "0") + " · " + stepLabel(item) + " · " + (item.output_ext || "—");
        builderStepsNode.append(chip);
      });
    }

    builderNextTool.replaceChildren();
    const compatible = builderSteps.length >= 4 ? [] : catalog
      .filter((item) => acceptsExtension(item, currentExt))
      .filter((item) => !builderSteps.some((step) => step.id === item.id))
      .sort((left, right) => stepLabel(left).localeCompare(stepLabel(right)));

    if (!compatible.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = en ? "No compatible safe next step" : "لا توجد خطوة آمنة متوافقة";
      builderNextTool.append(option);
    } else {
      compatible.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = stepLabel(item) + " → " + (item.output_ext || "—");
        builderNextTool.append(option);
      });
    }

    if (builderAddStep) builderAddStep.disabled = !compatible.length || builderSteps.length >= 4;
    if (builderRun) builderRun.disabled = !builderFile || !builderSteps.length;
    if (runQueue) runQueue.disabled = !builderSteps.length || !projectEntries.some((entry) => entry?.data?.safe);
    persistSessionPlan();
    if (builderStatus) builderStatus.textContent = en
      ? (builderSteps.length + "/4 steps · current " + (currentExt || "—"))
      : (builderSteps.length + "/4 خطوات · الحالي " + (currentExt || "—"));
  }

  const PROFILE_STEPS = {
    ".pdf": {
      balanced: ["pdf-repair", "pdf-compress"],
      smallest: ["pdf-compress"],
      editable: ["pdf-to-docx"],
      clean: ["pdf-repair"],
    },
    ".doc": {
      balanced: ["word-to-pdf", "pdf-compress"],
      smallest: ["word-to-pdf", "pdf-compress"],
      editable: [],
      clean: ["word-to-pdf"],
    },
    ".docx": {
      balanced: ["word-to-pdf", "pdf-compress"],
      smallest: ["word-to-pdf", "pdf-compress"],
      editable: ["docx-to-text"],
      clean: ["word-to-pdf"],
    },
    ".png": {
      balanced: ["image-to-jpg", "image-compress", "image-strip-metadata"],
      smallest: ["image-to-jpg", "image-compress"],
      editable: ["image-ocr"],
      clean: ["image-strip-metadata"],
    },
    ".jpg": {
      balanced: ["image-compress", "image-strip-metadata"],
      smallest: ["image-compress"],
      editable: ["image-ocr"],
      clean: ["image-strip-metadata"],
    },
    ".jpeg": {
      balanced: ["image-compress", "image-strip-metadata"],
      smallest: ["image-compress"],
      editable: ["image-ocr"],
      clean: ["image-strip-metadata"],
    },
    ".webp": {
      balanced: ["image-to-jpg", "image-compress", "image-strip-metadata"],
      smallest: ["image-to-jpg", "image-compress"],
      editable: ["image-ocr"],
      clean: ["image-strip-metadata"],
    },
    ".xlsx": {
      balanced: ["excel-to-pdf", "pdf-compress"],
      smallest: ["excel-to-pdf", "pdf-compress"],
      editable: ["xlsx-to-csv"],
      clean: ["xlsx-to-csv"],
    },
    ".pptx": {
      balanced: ["ppt-to-pdf", "pdf-compress"],
      smallest: ["ppt-to-pdf", "pdf-compress"],
      editable: [],
      clean: ["ppt-to-pdf"],
    },
    ".zip": {
      balanced: ["zip-integrity"],
      smallest: [],
      editable: ["zip-list"],
      clean: ["zip-flatten"],
    },
  };

  const TEMPLATE_STEPS = {
    student: {
      ".pdf": ["pdf-compress"],
      ".doc": ["word-to-pdf", "pdf-compress"],
      ".docx": ["word-to-pdf", "pdf-compress"],
      ".png": ["image-to-pdf", "pdf-compress"],
      ".jpg": ["image-to-pdf", "pdf-compress"],
      ".jpeg": ["image-to-pdf", "pdf-compress"],
    },
    business: {
      ".pdf": ["pdf-repair", "pdf-compress"],
      ".doc": ["word-to-pdf", "pdf-compress"],
      ".docx": ["word-to-pdf", "pdf-compress"],
      ".xlsx": ["excel-to-pdf", "pdf-compress"],
      ".pptx": ["ppt-to-pdf", "pdf-compress"],
    },
    creator: {
      ".png": ["image-to-jpg", "image-compress", "image-strip-metadata"],
      ".jpg": ["image-compress", "image-strip-metadata"],
      ".jpeg": ["image-compress", "image-strip-metadata"],
      ".webp": ["image-to-jpg", "image-compress", "image-strip-metadata"],
    },
  };

  async function applyStepIds(ids) {
    const catalog = await builderCatalog();
    const byId = new Map(catalog.map((item) => [item.id, item]));
    const next = [];
    let current = builderExt;
    for (const id of ids || []) {
      const item = byId.get(id);
      if (!item || !acceptsExtension(item, current) || next.some((step) => step.id === item.id)) break;
      next.push(item);
      current = item.output_ext;
      if (next.length >= 4) break;
    }
    builderSteps = next;
    await renderBuilder();
    return next.length === (ids || []).length;
  }

  document.querySelectorAll("[data-workspace-template]").forEach((button) => button.addEventListener("click", async () => {
    const template = button.dataset.workspaceTemplate || "";
    const ids = TEMPLATE_STEPS[template]?.[builderExt] || [];
    if (!ids.length) {
      if (builderStatus) builderStatus.textContent = en ? "This template does not match the selected file type." : "هذا القالب لا يناسب نوع الملف المختار.";
      return;
    }
    document.querySelectorAll("[data-workspace-template]").forEach((item) => item.classList.toggle("is-active", item === button));
    document.querySelectorAll("[data-workspace-profile]").forEach((item) => item.classList.remove("is-active"));
    const complete = await applyStepIds(ids);
    emitEvent("workspace_template_apply");
    if (!complete && builderStatus) builderStatus.textContent = en ? "Template was shortened to the safe compatible steps." : "تم تقصير القالب إلى الخطوات الآمنة المتوافقة.";
  }));

  async function applyProfile(profile) {
    document.querySelectorAll("[data-workspace-profile]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.workspaceProfile === profile);
    });
    const catalog = await builderCatalog();
    const byId = new Map(catalog.map((item) => [item.id, item]));
    const requested = PROFILE_STEPS[builderExt]?.[profile] || [];
    const next = [];
    let current = builderExt;
    for (const id of requested) {
      const item = byId.get(id);
      if (!item || !acceptsExtension(item, current)) break;
      next.push(item);
      current = item.output_ext;
      if (next.length >= 4) break;
    }
    builderSteps = next;
    await renderBuilder();
  }

  builderAddStep?.addEventListener("click", async () => {
    const id = builderNextTool?.value || "";
    if (!id || builderSteps.length >= 4) return;
    const catalog = await builderCatalog();
    const item = catalog.find((candidate) => candidate.id === id);
    if (!item) return;
    const current = builderSteps.length ? builderSteps[builderSteps.length - 1].output_ext : builderExt;
    if (!acceptsExtension(item, current)) return;
    builderSteps.push(item);
    await renderBuilder();
  });

  builderReset?.addEventListener("click", async () => {
    builderSteps = [];
    document.querySelectorAll("[data-workspace-profile]").forEach((button) => button.classList.remove("is-active"));
    await renderBuilder();
  });

  document.querySelectorAll("[data-workspace-profile]").forEach((button) => button.addEventListener("click", () => {
    applyProfile(button.dataset.workspaceProfile || "balanced");
  }));

  builderRun?.addEventListener("click", async () => {
    if (!builderFile || !builderSteps.length) return;
    const original = builderRun.textContent;
    builderRun.disabled = true;
    if (builderStatus) builderStatus.textContent = en ? "Running verified workflow…" : "جاري تنفيذ المسار المتحقق…";
    try {
      const body = new FormData();
      body.set("file", builderFile, builderFile.name);
      body.set("steps", JSON.stringify(builderSteps.map((item) => item.id)));
      const response = await fetch("/api/v2/workflows/execute", { method: "POST", body, credentials: "same-origin" });
      if (!response.ok) {
        let message = en ? "Workflow failed." : "تعذر تنفيذ المسار.";
        try {
          const payload = await response.json();
          if (payload?.error) message = payload.error;
        } catch (_) {}
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = contentDispositionFilename(response);
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      if (builderStatus) builderStatus.textContent = en ? "Completed ✓" : "اكتمل ✓";
      emitEvent("workspace_workflow_run");
    } catch (error) {
      if (builderStatus) builderStatus.textContent = error?.message || (en ? "Workflow failed." : "تعذر تنفيذ المسار.");
    } finally {
      builderRun.textContent = original;
      builderRun.disabled = false;
    }
  });

  async function inspectOne(file) {
    const body = new FormData();
    body.set("file", file, file.name);
    const response = await fetch("/api/v2/inspect", { method: "POST", body, credentials: "same-origin" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.error || copy.failed);
    return data;
  }

  function addProjectRow(file, data, error = "") {
    if (!projectFiles) return;
    const row = document.createElement("span");
    row.className = "text-button";
    row.textContent = error
      ? `${file.name} · ${error}`
      : `${file.name} · ${String(data.extension || "").toUpperCase()} · ${bytes(data.size || file.size)}${data.pages ? " · " + data.pages + " " + copy.pages : ""}`;
    projectFiles.append(row);
  }

  function chainAcceptsExtension(extension) {
    if (!builderSteps.length) return false;
    return acceptsExtension(builderSteps[0], String(extension || "").toLowerCase());
  }

  function renderQueue() {
    if (!queueList) return;
    queueList.replaceChildren();
    projectEntries.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "personal-card";
      const head = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = entry.file.name;
      const badge = document.createElement("span");
      badge.textContent = entry.status || (en ? "Ready" : "جاهز");
      head.append(name, badge);
      const detail = document.createElement("p");
      detail.textContent = entry.error
        ? entry.error
        : `${String(entry.data?.extension || "").toUpperCase()} · ${bytes(entry.data?.size || entry.file.size)}`;
      row.append(head, detail);
      if (entry.status === "failed" || entry.status === "skipped") {
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "secondary";
        retry.textContent = en ? "Retry" : "إعادة المحاولة";
        retry.addEventListener("click", () => runQueueItem(index));
        row.append(retry);
      }
      queueList.append(row);
    });
  }

  async function runQueueItem(index) {
    const entry = projectEntries[index];
    if (!entry || !entry.data?.safe || !builderSteps.length) return;
    if (!chainAcceptsExtension(entry.data.extension)) {
      entry.status = "skipped";
      entry.error = en ? "Current workflow does not accept this file type." : "المسار الحالي لا يقبل نوع هذا الملف.";
      renderQueue();
      return;
    }
    entry.status = "running";
    entry.error = "";
    renderQueue();
    try {
      const body = new FormData();
      body.set("file", entry.file, entry.file.name);
      body.set("steps", JSON.stringify(builderSteps.map((item) => item.id)));
      const response = await fetch("/api/v2/workflows/execute", { method: "POST", body, credentials: "same-origin" });
      if (!response.ok) {
        let message = en ? "Workflow failed." : "تعذر تنفيذ المسار.";
        try {
          const payload = await response.json();
          if (payload?.error) message = payload.error;
        } catch (_) {}
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = contentDispositionFilename(response);
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      entry.status = "done";
      entry.error = "";
    } catch (error) {
      entry.status = "failed";
      entry.error = error?.message || (en ? "Workflow failed." : "تعذر تنفيذ المسار.");
    }
    renderQueue();
  }

  runQueue?.addEventListener("click", async () => {
    if (!builderSteps.length || !projectEntries.length) return;
    runQueue.disabled = true;
    emitEvent("workspace_queue_run");
    for (let index = 0; index < projectEntries.length; index += 1) {
      await runQueueItem(index);
    }
    runQueue.disabled = false;
  });

  clearQueue?.addEventListener("click", () => {
    projectEntries = [];
    projectFiles?.replaceChildren();
    queueList?.replaceChildren();
    if (projectBoard) projectBoard.hidden = true;
    if (projectCount) projectCount.textContent = "";
    if (runQueue) runQueue.disabled = true;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const files = [...(fileInput?.files || [])].slice(0, 6);
    if (!files.length) { status.textContent = copy.invalid; return; }

    status.textContent = copy.inspecting;
    result.hidden = true;
    recommendations.hidden = true;
    facts.replaceChildren();
    projectFiles?.replaceChildren();
    if (projectBoard) projectBoard.hidden = false;
    if (projectCount) projectCount.textContent = `${files.length}/6`;

    let firstSuccess = null;
    projectEntries = [];
    for (const file of files) {
      try {
        const data = await inspectOne(file);
        addProjectRow(file, data);
        rememberRecent(data, file.size);
        projectEntries.push({ file, data, status: en ? "Ready" : "جاهز", error: "" });
        if (!firstSuccess) firstSuccess = { file, data };
      } catch (error) {
        const message = error?.message || copy.failed;
        addProjectRow(file, {}, message);
        projectEntries.push({ file, data: {}, status: "failed", error: message });
      }
    }
    renderQueue();

    if (!firstSuccess) {
      status.textContent = copy.failed;
      return;
    }
    emitEvent("workspace_inspect");

    const { file, data } = firstSuccess;
    builderFile = file;
    builderExt = String(data.extension || "").toLowerCase();
    builderSteps = [];
    if (builder) builder.hidden = false;
    if (pendingRestore && pendingRestore.extension === builderExt && pendingRestore.steps?.length) {
      const restored = await applyStepIds(pendingRestore.steps);
      if (restored) {
        if (builderStatus) builderStatus.textContent = en ? "Restored previous safe plan ✓" : "تم استعادة الخطة الآمنة السابقة ✓";
        pendingRestore = null;
        if (recovery) recovery.hidden = true;
      } else {
        await applyProfile("balanced");
      }
    } else {
      await applyProfile("balanced");
    }
    label.textContent = files.length > 1
      ? (en ? `${files.length} files inspected · primary: ${file.name}` : `تم فحص ${files.length} ملفات · الأساسي: ${file.name}`)
      : file.name;
    summary.textContent = copy.safe;
    addFact(`${copy.type}: ${data.extension || file.name.slice(file.name.lastIndexOf(".")) || "—"}`);
    addFact(`${copy.size}: ${bytes(data.size || file.size)}`);
    if (data.pages) addFact(`${copy.pages}: ${data.pages}`);
    if (typeof data.encrypted === "boolean") addFact(`${copy.encrypted}: ${data.encrypted ? copy.yes : copy.no}`);
    result.hidden = false;
    result.focus({ preventScroll: false });

    try {
      sessionStorage.setItem("infinity_safe_file_context", JSON.stringify({
        at: Date.now(),
        extension: data.extension || "",
        mime: data.mime || file.type || "",
        size_bytes: Number(data.size || file.size || 0),
        pages: Number(data.pages || 0),
        encrypted: Boolean(data.encrypted),
        safe: Boolean(data.safe),
        project_file_count: files.length,
      }));
    } catch (_) {}
    await renderRecommendations(data.extension || "");
    status.textContent = copy.ready;
  });
})();
