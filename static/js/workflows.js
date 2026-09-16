(() => {
  "use strict";
  const form = document.getElementById("workflow-form");
  if (!form) return;

  const status = document.getElementById("workflow-status");
  const progress = document.getElementById("workflow-progress");
  const resultPanel = document.getElementById("workflow-result");
  const resultText = document.getElementById("workflow-result-text");
  const download = document.getElementById("workflow-download");
  const isEnglish = document.documentElement.lang === "en";
  let objectUrl = "";

  const text = isEnglish ? {
    running: "Running verified workflow…",
    done: "Completed",
    failed: "Workflow failed",
    choose: "Choose a file first.",
    generic: "The workflow could not be completed. Try another file or run the tools step by step.",
    final: "The final file passed the workflow output checks.",
  } : {
    running: "جاري تنفيذ المسار المتحقق…",
    done: "اكتمل",
    failed: "فشل المسار",
    choose: "اختر ملفًا أولًا.",
    generic: "تعذر إكمال المسار. جرّب ملفًا آخر أو نفّذ الأدوات خطوة بخطوة.",
    final: "الملف النهائي اجتاز فحوصات ناتج المسار.",
  };

  function filenameFrom(response) {
    const header = response.headers.get("content-disposition") || "";
    const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf) {
      try { return decodeURIComponent(utf[1]); } catch (_) {}
    }
    const plain = header.match(/filename="?([^";]+)"?/i);
    return plain ? plain[1] : "InfinityConverter-Workflow-Result";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = document.getElementById("workflow-file")?.files?.[0];
    const selected = form.querySelector('input[name="workflow"]:checked');
    if (!file || !selected) {
      status.textContent = text.choose;
      return;
    }

    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = "";
    }
    resultPanel.hidden = true;
    download.hidden = true;
    progress.hidden = false;
    status.textContent = text.running;

    const body = new FormData();
    body.set("workflow", selected.value);
    body.set("file", file, file.name);

    const controller = new AbortController();
    const timeoutSeconds = Number(document.body.dataset.requestTimeoutSeconds || 210);
    const timer = setTimeout(() => controller.abort(), Math.max(30, timeoutSeconds + 15) * 1000);
    try {
      const response = await fetch("/api/v2/workflows/execute", {
        method: "POST",
        body,
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!response.ok) {
        let message = text.generic;
        try {
          const payload = await response.json();
          if (payload?.error) message = payload.error;
        } catch (_) {}
        throw new Error(message);
      }
      const blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      download.href = objectUrl;
      download.download = filenameFrom(response);
      download.hidden = false;
      resultText.textContent = `${text.final} ${response.headers.get("X-Workflow-Steps") || ""}`.trim();
      resultPanel.hidden = false;
      resultPanel.focus({ preventScroll: false });
      status.textContent = text.done;
    } catch (error) {
      status.textContent = text.failed;
      resultPanel.hidden = false;
      resultText.textContent = error?.name === "AbortError" ? text.generic : (error?.message || text.generic);
      resultPanel.focus({ preventScroll: false });
    } finally {
      clearTimeout(timer);
      progress.hidden = true;
    }
  });

  window.addEventListener("pagehide", () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }, { once: true });
})();
