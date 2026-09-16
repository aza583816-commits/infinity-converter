(() => {
  "use strict";
  const toolId = document.getElementById("tool-id");
  const hero = document.querySelector(".tool-hero");
  if (!toolId || !hero || document.getElementById("tool-trust-labels")) return;

  const en = document.documentElement.lang === "en";
  const labels = en ? [
    ["Processing", "Infinity server runtime"],
    ["AI file access", "Not attached automatically"],
    ["Temporary storage", "Per-request workspace"],
    ["Cleanup", "Response close + stale-workspace recovery"],
  ] : [
    ["المعالجة", "داخل خادم Infinity"],
    ["وصول الذكاء للملف", "لا يُرفق تلقائيًا"],
    ["التخزين المؤقت", "مساحة مستقلة لكل طلب"],
    ["التنظيف", "عند إغلاق الاستجابة + استرداد المساحات المتروكة"],
  ];

  const section = document.createElement("section");
  section.id = "tool-trust-labels";
  section.className = "tool-trust-labels";
  section.setAttribute("aria-label", en ? "Processing and privacy facts" : "حقائق المعالجة والخصوصية");
  section.innerHTML = labels.map(([name, value]) => `
    <div class="tool-trust-label"><small>${name}</small><strong>${value}</strong></div>
  `).join("") + `<a href="/trust">${en ? "How protection works" : "كيف تعمل الحماية"} ↗</a>`;

  const style = document.createElement("style");
  style.textContent = `
    .tool-trust-labels{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;margin:.8rem 0 1.1rem;padding:.8rem;border:1px solid color-mix(in srgb,currentColor 12%,transparent);border-radius:18px;background:color-mix(in srgb,var(--surface,#fff) 90%,transparent)}
    .tool-trust-label{padding:.7rem;border-radius:13px;background:color-mix(in srgb,currentColor 5%,transparent)}
    .tool-trust-label small{display:block;opacity:.62;margin-bottom:.22rem}.tool-trust-label strong{font-size:.88rem;line-height:1.4}
    .tool-trust-labels>a{grid-column:1/-1;justify-self:end;font-size:.86rem;font-weight:700;color:inherit}
    @media(max-width:800px){.tool-trust-labels{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:520px){.tool-trust-labels{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
  hero.insertAdjacentElement("afterend", section);
})();
