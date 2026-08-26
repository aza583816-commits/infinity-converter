const $ = (selector) => document.querySelector(selector);
const form = $("#converter-form");

const search = $("#tool-search");
const cards = [...document.querySelectorAll(".tool-card")];
const emptyState = $("#empty-state");
const categoryLinks = [...document.querySelectorAll("[data-category]")];
let selectedCategory = "";

function filterCards() {
  const query = search ? search.value.trim().toLowerCase() : "";
  let visible = 0;
  cards.forEach((card) => {
    const matchesSearch = card.dataset.search.toLowerCase().includes(query);
    const matchesCategory = !selectedCategory || card.dataset.search.includes(selectedCategory);
    card.hidden = !matchesSearch || !matchesCategory;
    if (!card.hidden) visible += 1;
  });
  if (emptyState) emptyState.hidden = visible > 0;
}

if (search) search.addEventListener("input", filterCards);
categoryLinks.forEach((link) => link.addEventListener("click", () => {
  selectedCategory = link.dataset.category;
  if (search) search.value = "";
  filterCards();
  document.querySelector("#tools").scrollIntoView({ behavior: "smooth" });
}));

if (cards.length) {
  filterCards();
}

if (form) form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const statusEl = $("#status");
  const resultEl = $("#result");
  const input = $("#files");
  if (!input.files.length) {
    resultEl.textContent = "اختر ملفًا واحدًا على الأقل.";
    return;
  }

  const form = new FormData();
  form.append("tool", $("#tool-id").value);
  for (const file of input.files) form.append("files", file);

  statusEl.textContent = "جارٍ المعالجة...";
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

    statusEl.textContent = "اكتمل";
    resultEl.textContent = `تم إنشاء الملف: ${filename}`;
  } catch (error) {
    statusEl.textContent = "تعذر الإكمال";
    resultEl.textContent = error.message;
  }
});
