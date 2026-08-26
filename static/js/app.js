const state = { tool: null, tools: [] };

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#status");
const resultEl = $("#result");

async function loadTools() {
  const response = await fetch("/api/v2/tools", { headers: { Accept: "application/json" } });
  const data = await response.json();
  state.tools = data.tools || [];
}

function chooseTool(id) {
  const tool = state.tools.find((item) => item.id === id);
  if (!tool) return;
  state.tool = tool;
  $("#tool-id").value = id;
  $("#selected-name").textContent = `${tool.name_ar} — ${tool.name_en}`;
  statusEl.textContent = `✓ ${tool.category}`;
  resultEl.textContent = "";
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-tool]");
  if (button) chooseTool(button.dataset.tool);
});

$("#converter-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!state.tool) {
    resultEl.textContent = "اختر أداة أولاً.";
    return;
  }

  const input = $("#files");
  if (!input.files.length) {
    resultEl.textContent = "اختر ملفًا واحدًا على الأقل.";
    return;
  }

  const form = new FormData();
  form.append("tool", state.tool.id);
  for (const file of input.files) form.append("files", file);

  statusEl.textContent = "⏳ جارٍ التحقق والمعالجة...";
  resultEl.textContent = "";

  try {
    const response = await fetch("/api/v2/convert", { method: "POST", body: form });
    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
      const payload = contentType.includes("application/json")
        ? await response.json()
        : { error: "حدث خطأ غير متوقع." };
      throw new Error(payload.error || "فشل التحويل.");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
    const filename = filenameMatch ? filenameMatch[1] : "InfinityConverter-result";

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);

    statusEl.textContent = "✓ اكتمل";
    resultEl.textContent = `تم إنشاء الملف: ${filename}`;
  } catch (error) {
    statusEl.textContent = "✕ فشل";
    resultEl.textContent = error.message;
  }
});

loadTools().catch(() => {
  resultEl.textContent = "تعذر تحميل قائمة الأدوات.";
});
