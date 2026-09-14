(() => {
  "use strict";

  const resultPanel = document.getElementById("result-panel");
  const toolIdNode = document.getElementById("tool-id");
  const fileInput = document.getElementById("files");
  if (!resultPanel || !toolIdNode) return;

  const currentToolId = toolIdNode.value || "";
  const isEnglish = document.documentElement.lang === "en";
  const MAX_HANDOFF_BYTES = 32 * 1024 * 1024;
  const HANDOFF_TTL_MS = 15 * 60 * 1000;
  const DB_NAME = "infinity-smart-flow";
  const STORE_NAME = "handoff";
  const RECORD_KEY = "latest";

  const text = isEnglish ? {
    title: "Infinity Finish Line",
    subtitle: "A private receipt plus smart next steps for the file you just created.",
    receipt: "Privacy receipt",
    processed: "Processing",
    processedValue: "Completed in a temporary request workspace",
    cleanup: "Cleanup",
    cleanupValue: "Server scratch files are removed when the response closes",
    ai: "AI access",
    aiValue: "File contents are not attached to Infinity Intelligence automatically",
    history: "Cloud history",
    historyValue: "No permanent public conversion file history",
    next: "Smart Continue",
    nextHint: "Carry the result into a compatible next tool without choosing the file again. The handoff stays in this browser and expires automatically.",
    carry: "Carry result to",
    open: "Open",
    preparing: "Preparing local handoff…",
    tooLarge: "This result is too large for a reliable browser handoff. Open the next tool and choose the downloaded file instead.",
    carried: "Result carried from the previous tool. Review the file and settings, then press Convert when you are ready.",
    unavailable: "Local handoff is unavailable in this browser. The downloaded result is still safe to use manually.",
    copy: "Copy receipt",
    copied: "Receipt copied",
    engine: "Engine",
    duration: "Duration",
  } : {
    title: "خط النهاية الذكي من Infinity",
    subtitle: "إيصال خصوصية وخطوات ذكية للملف الذي أنشأته للتو.",
    receipt: "إيصال الخصوصية",
    processed: "المعالجة",
    processedValue: "اكتملت داخل مساحة مؤقتة مستقلة للطلب",
    cleanup: "التنظيف",
    cleanupValue: "تُحذف ملفات المعالجة المؤقتة عند إغلاق الاستجابة",
    ai: "وصول الذكاء",
    aiValue: "محتوى الملف لا يُرفق مع Infinity Intelligence تلقائيًا",
    history: "السجل السحابي",
    historyValue: "لا يوجد سجل دائم لملفات التحويل العامة",
    next: "أكمل بذكاء",
    nextHint: "انقل الناتج إلى أداة متوافقة بدون ما تختار الملف مرة ثانية. النقل يبقى داخل متصفحك وينتهي تلقائيًا.",
    carry: "انقل الناتج إلى",
    open: "افتح",
    preparing: "جاري تجهيز النقل المحلي…",
    tooLarge: "حجم الناتج كبير على النقل المحلي الموثوق داخل المتصفح. افتح الأداة التالية واختر الملف الذي نزلته بدلًا من ذلك.",
    carried: "تم نقل ناتج الأداة السابقة محليًا. راجع الملف والإعدادات ثم اضغط تحويل عندما تكون جاهزًا.",
    unavailable: "النقل المحلي غير متاح في هذا المتصفح. تقدر تستخدم الملف الذي تم تنزيله يدويًا بشكل طبيعي.",
    copy: "نسخ الإيصال",
    copied: "تم نسخ الإيصال",
    engine: "المحرك",
    duration: "المدة",
  };

  const NEXT = {
    "word-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "excel-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "ppt-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "txt-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "html-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "csv-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "markdown-to-pdf": ["pdf-compress", "pdf-password-protect", "pdf-merge"],
    "pdf-merge": ["pdf-compress", "pdf-password-protect", "pdf-page-numbers"],
    "pdf-compress": ["pdf-password-protect", "pdf-merge", "pdf-redact"],
    "pdf-repair": ["pdf-compress", "pdf-to-docx", "pdf-password-protect"],
    "pdf-to-docx": ["word-to-pdf"],
    "image-to-pdf": ["pdf-compress", "ocr-pdf-to-searchable", "pdf-password-protect"],
    "ocr-pdf-to-searchable": ["pdf-to-docx", "pdf-compress", "pdf-password-protect"],
    "pdf-ocr": ["text-clean", "text-statistics"],
    "image-ocr": ["text-clean", "text-statistics"],
    "image-to-jpg": ["image-compress", "image-resize", "image-to-webp"],
    "image-to-png": ["image-compress", "image-resize", "image-watermark"],
    "image-to-webp": ["image-resize", "image-watermark"],
    "image-resize": ["image-compress", "image-to-webp", "image-watermark"],
    "image-compress": ["image-to-webp", "image-watermark"],
    "image-upscale": ["image-compress", "image-watermark"],
    "csv-to-xlsx": ["excel-to-pdf", "xlsx-to-csv", "xlsx-to-json"],
    "zip-create": ["zip-list", "zip-integrity"],
    "tar-gzip-create": ["tar-list", "tar-integrity"],
  };

  function addStyles() {
    if (document.getElementById("infinity-smart-flow-style")) return;
    const style = document.createElement("style");
    style.id = "infinity-smart-flow-style";
    style.textContent = `
      .infinity-smart-flow{margin-top:1rem;padding:1rem;border:1px solid color-mix(in srgb,currentColor 14%,transparent);border-radius:18px;background:color-mix(in srgb,var(--surface,#fff) 92%,transparent)}
      .infinity-smart-flow__head{display:flex;gap:.8rem;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
      .infinity-smart-flow__head h3,.infinity-smart-flow__next h4{margin:.1rem 0 .25rem}.infinity-smart-flow__head p,.infinity-smart-flow__next p{margin:0;max-width:66ch;opacity:.78}
      .infinity-smart-flow__badge{display:inline-grid;place-items:center;min-width:2.2rem;height:2.2rem;border-radius:999px;border:1px solid currentColor;font-weight:800}
      .infinity-smart-flow__receipt{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem;margin-top:.9rem}
      .infinity-smart-flow__fact{padding:.75rem;border-radius:14px;background:color-mix(in srgb,currentColor 5%,transparent)}
      .infinity-smart-flow__fact small{display:block;opacity:.64;margin-bottom:.2rem}.infinity-smart-flow__fact strong{font-size:.92rem;line-height:1.45}
      .infinity-smart-flow__meta{display:flex;gap:.55rem;flex-wrap:wrap;margin:.75rem 0 0;font-size:.82rem;opacity:.72}
      .infinity-smart-flow__actions{display:flex;gap:.55rem;flex-wrap:wrap;margin-top:.8rem}.infinity-smart-flow__actions button,.infinity-smart-flow__actions a{display:inline-flex;align-items:center;gap:.4rem;padding:.65rem .8rem;border-radius:12px;border:1px solid color-mix(in srgb,currentColor 18%,transparent);background:transparent;color:inherit;text-decoration:none;cursor:pointer;font:inherit;font-weight:700}
      .infinity-smart-flow__actions button:hover,.infinity-smart-flow__actions a:hover{transform:translateY(-1px)}
      .infinity-smart-flow__next{margin-top:1rem;padding-top:1rem;border-top:1px solid color-mix(in srgb,currentColor 12%,transparent)}
      .infinity-handoff-note{margin:.75rem 0;padding:.75rem .9rem;border-radius:14px;border:1px solid color-mix(in srgb,currentColor 18%,transparent);font-weight:650}
      @media(max-width:680px){.infinity-smart-flow__receipt{grid-template-columns:1fr}.infinity-smart-flow__actions>*{width:100%;justify-content:center}}
      @media(prefers-reduced-motion:reduce){.infinity-smart-flow__actions button,.infinity-smart-flow__actions a{transition:none!important;transform:none!important}}
    `;
    document.head.append(style);
  }

  function readCatalog() {
    const node = document.getElementById("command-palette-data");
    if (!node) return [];
    try { return JSON.parse(node.textContent || "[]"); } catch (_) { return []; }
  }

  function readToolContext() {
    const node = document.getElementById("tool-ai-context");
    if (!node) return {};
    try { return JSON.parse(node.textContent || "{}"); } catch (_) { return {}; }
  }

  const catalog = readCatalog();
  const toolContext = readToolContext();
  const byId = new Map(catalog.map((item) => [item.id, item]));

  function compatibleWithOutput(item) {
    const ext = String(toolContext.output_ext || "").toLowerCase();
    const accepted = Array.isArray(item?.input_ext) ? item.input_ext.map((value) => String(value).toLowerCase()) : [];
    return Boolean(ext && (accepted.includes(ext) || accepted.includes("*") || accepted.includes(".*")));
  }

  function nextItems() {
    const chosen = [];
    const seen = new Set([currentToolId]);
    const preferred = NEXT[currentToolId] || [];
    for (const id of preferred) {
      const item = byId.get(id);
      if (item && item.kind !== "browser" && !seen.has(id)) {
        chosen.push(item); seen.add(id);
      }
      if (chosen.length >= 3) return chosen;
    }
    const outputExt = String(toolContext.output_ext || "").toLowerCase();
    if (outputExt && outputExt !== ".zip") {
      for (const item of catalog) {
        if (item.kind === "browser" || seen.has(item.id)) continue;
        if (compatibleWithOutput(item)) {
          chosen.push(item); seen.add(item.id);
        }
        if (chosen.length >= 3) break;
      }
    }
    return chosen;
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) return reject(new Error("indexedDB unavailable"));
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME);
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("IndexedDB open failed"));
    });
  }

  async function putHandoff(record) {
    const db = await openDb();
    try {
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        tx.objectStore(STORE_NAME).put(record, RECORD_KEY);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error || new Error("IndexedDB write failed"));
        tx.onabort = () => reject(tx.error || new Error("IndexedDB write aborted"));
      });
    } finally { db.close(); }
  }

  async function takeHandoff() {
    const db = await openDb();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        const request = store.get(RECORD_KEY);
        request.onsuccess = () => {
          const value = request.result || null;
          store.delete(RECORD_KEY);
          resolve(value);
        };
        request.onerror = () => reject(request.error || new Error("IndexedDB read failed"));
      });
    } finally { db.close(); }
  }

  function extensionOf(name) {
    const match = String(name || "").toLowerCase().match(/(\.[a-z0-9]+)$/);
    return match ? match[1] : "";
  }

  function currentAccepts(name) {
    if (!fileInput) return false;
    const accepted = String(fileInput.getAttribute("accept") || "").toLowerCase().split(",").map((x) => x.trim()).filter(Boolean);
    if (!accepted.length) return true;
    return accepted.includes(extensionOf(name));
  }

  function showHandoffNote(message) {
    if (!fileInput) return;
    const form = fileInput.closest("form");
    if (!form) return;
    let note = document.getElementById("infinity-handoff-note");
    if (!note) {
      note = document.createElement("div");
      note.id = "infinity-handoff-note";
      note.className = "infinity-handoff-note";
      note.setAttribute("role", "status");
      form.prepend(note);
    }
    note.textContent = message;
  }

  async function restoreIncomingHandoff() {
    const params = new URLSearchParams(location.search);
    if (params.get("handoff") !== "1" || !fileInput) return;
    try {
      const record = await takeHandoff();
      if (!record || Number(record.expiresAt || 0) < Date.now() || record.targetToolId !== currentToolId || !(record.blob instanceof Blob)) {
        showHandoffNote(text.unavailable);
        return;
      }
      if (!currentAccepts(record.filename)) {
        showHandoffNote(text.unavailable);
        return;
      }
      if (!("DataTransfer" in window)) {
        showHandoffNote(text.unavailable);
        return;
      }
      const file = new File([record.blob], record.filename || "InfinityConverter-result", {
        type: record.mime || record.blob.type || "application/octet-stream",
        lastModified: Date.now(),
      });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
      showHandoffNote(text.carried);
    } catch (_) {
      showHandoffNote(text.unavailable);
    } finally {
      params.delete("handoff");
      const query = params.toString();
      history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
    }
  }

  async function carryTo(item, button) {
    const download = document.getElementById("download-again");
    const blobUrl = download?.href || "";
    if (!compatibleWithOutput(item) || !blobUrl.startsWith("blob:")) {
      location.assign(item.href);
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = text.preparing;
    try {
      const response = await fetch(blobUrl);
      const blob = await response.blob();
      if (blob.size > MAX_HANDOFF_BYTES) {
        button.disabled = false;
        button.textContent = original;
        const notice = button.closest(".infinity-smart-flow__next")?.querySelector("p");
        if (notice) notice.textContent = text.tooLarge;
        return;
      }
      await putHandoff({
        sourceToolId: currentToolId,
        targetToolId: item.id,
        filename: download.download || "InfinityConverter-result",
        mime: blob.type || "application/octet-stream",
        blob,
        createdAt: Date.now(),
        expiresAt: Date.now() + HANDOFF_TTL_MS,
      });
      const separator = item.href.includes("?") ? "&" : "?";
      location.assign(`${item.href}${separator}handoff=1`);
    } catch (_) {
      button.disabled = false;
      button.textContent = original;
      location.assign(item.href);
    }
  }

  function receiptText(runtime) {
    const duration = Number(runtime.duration_ms || 0);
    const engine = String(runtime.engine || "").trim();
    return [
      `Infinity Converter — ${text.receipt}`,
      `${text.processed}: ${text.processedValue}`,
      `${text.cleanup}: ${text.cleanupValue}`,
      `${text.ai}: ${text.aiValue}`,
      `${text.history}: ${text.historyValue}`,
      engine ? `${text.engine}: ${engine}` : "",
      duration ? `${text.duration}: ${(duration / 1000).toFixed(duration >= 10000 ? 1 : 2)}s` : "",
    ].filter(Boolean).join("\n");
  }

  function renderSmartFlow() {
    let root = document.getElementById("infinity-smart-flow");
    if (resultPanel.dataset.state !== "success") {
      if (root) root.remove();
      return;
    }
    if (root) root.remove();
    addStyles();

    const runtime = window.InfinityRuntimeContext?.lastResult || {};
    root = document.createElement("section");
    root.id = "infinity-smart-flow";
    root.className = "infinity-smart-flow";
    root.setAttribute("aria-live", "polite");

    const head = document.createElement("div");
    head.className = "infinity-smart-flow__head";
    const headingWrap = document.createElement("div");
    const heading = document.createElement("h3"); heading.textContent = text.title;
    const subtitle = document.createElement("p"); subtitle.textContent = text.subtitle;
    headingWrap.append(heading, subtitle);
    const badge = document.createElement("span"); badge.className = "infinity-smart-flow__badge"; badge.textContent = "∞"; badge.setAttribute("aria-hidden", "true");
    head.append(headingWrap, badge);
    root.append(head);

    const receipt = document.createElement("div");
    receipt.className = "infinity-smart-flow__receipt";
    const facts = [
      [text.processed, text.processedValue],
      [text.cleanup, text.cleanupValue],
      [text.ai, text.aiValue],
      [text.history, text.historyValue],
    ];
    for (const [label, value] of facts) {
      const fact = document.createElement("div"); fact.className = "infinity-smart-flow__fact";
      const small = document.createElement("small"); small.textContent = label;
      const strong = document.createElement("strong"); strong.textContent = value;
      fact.append(small, strong); receipt.append(fact);
    }
    root.append(receipt);

    const meta = document.createElement("div"); meta.className = "infinity-smart-flow__meta";
    if (runtime.engine) { const span = document.createElement("span"); span.textContent = `${text.engine}: ${runtime.engine}`; meta.append(span); }
    if (runtime.duration_ms) { const span = document.createElement("span"); span.textContent = `${text.duration}: ${(Number(runtime.duration_ms) / 1000).toFixed(Number(runtime.duration_ms) >= 10000 ? 1 : 2)}s`; meta.append(span); }
    root.append(meta);

    const receiptActions = document.createElement("div"); receiptActions.className = "infinity-smart-flow__actions";
    const copy = document.createElement("button"); copy.type = "button"; copy.textContent = text.copy;
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(receiptText(runtime));
        const original = copy.textContent; copy.textContent = text.copied;
        setTimeout(() => { copy.textContent = original; }, 1400);
      } catch (_) {}
    });
    receiptActions.append(copy); root.append(receiptActions);

    const items = nextItems();
    if (items.length) {
      const next = document.createElement("div"); next.className = "infinity-smart-flow__next";
      const h4 = document.createElement("h4"); h4.textContent = text.next;
      const hint = document.createElement("p"); hint.textContent = text.nextHint;
      const actions = document.createElement("div"); actions.className = "infinity-smart-flow__actions";
      for (const item of items) {
        const label = isEnglish ? item.name_en : item.name_ar;
        if (compatibleWithOutput(item)) {
          const button = document.createElement("button"); button.type = "button"; button.textContent = `${text.carry} ${label} →`;
          button.addEventListener("click", () => carryTo(item, button));
          actions.append(button);
        } else {
          const link = document.createElement("a"); link.href = item.href; link.textContent = `${text.open} ${label} ↗`; actions.append(link);
        }
      }
      next.append(h4, hint, actions); root.append(next);
    }

    resultPanel.append(root);
  }

  const observer = new MutationObserver(renderSmartFlow);
  observer.observe(resultPanel, { attributes: true, attributeFilter: ["data-state", "hidden"] });
  restoreIncomingHandoff();
})();
