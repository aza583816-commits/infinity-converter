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
  const en = document.documentElement.lang === "en";
  let catalogPromise = null;

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
    for (const file of files) {
      try {
        const data = await inspectOne(file);
        addProjectRow(file, data);
        rememberRecent(data, file.size);
        if (!firstSuccess) firstSuccess = { file, data };
      } catch (error) {
        addProjectRow(file, {}, error?.message || copy.failed);
      }
    }

    if (!firstSuccess) {
      status.textContent = copy.failed;
      return;
    }

    const { file, data } = firstSuccess;
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
