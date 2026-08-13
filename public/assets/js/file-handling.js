// =====================================================================================
// file-handling.js — رفع الملفات: Drag & Drop حقيقي + معاينة المحتوى قبل الإرسال
//
// 🆕 إضافة: الواجهة القديمة كانت تعرض نص "Drag & Drop" لكنها لا تستمع فعلياً لأحداث
// dragover/drop على صندوق الرفع — فقط النقر كان يعمل. تم ربط الأحداث الحقيقية هنا.
// =====================================================================================

window.loadedFiles = [];
window.isDocxProcessing = false;

function pdfPageToOrderedText(items) {
  if (!items || !items.length) return '';
  let parts = items
    .map((it) => ({ text: it.str, x: it.transform[4], y: it.transform[5], width: it.width || 0 }))
    .filter((p) => p.text.trim().length > 0);
  if (!parts.length) return '';
  parts.sort((a, b) => {
    if (Math.abs(a.y - b.y) > 7) return b.y - a.y;
    return a.x - b.x;
  });
  let lines = [];
  let currentLine = [];
  let lastY = null;
  parts.forEach((p) => {
    if (lastY === null) {
      currentLine.push(p);
      lastY = p.y;
    } else if (Math.abs(lastY - p.y) <= 7) {
      currentLine.push(p);
    } else {
      lines.push(currentLine);
      currentLine = [p];
      lastY = p.y;
    }
  });
  if (currentLine.length > 0) lines.push(currentLine);
  return lines
    .map((line) => {
      line.sort((a, b) => a.x - b.x);
      let lineText = '';
      let prevEndX = null;
      line.forEach((it) => {
        if (prevEndX !== null) {
          const gap = it.x - prevEndX;
          if (gap > 40) lineText += '   ';
          else if (gap > 2) lineText += ' ';
        }
        lineText += it.text;
        prevEndX = it.x + it.width;
      });
      return lineText;
    })
    .join('\n');
}

function processFiles(files) {
  const { updateStats } = window.VInfinityApp;
  window.loadedFiles = files;
  const first = files[0];
  const reader = new FileReader();
  const inputData = document.getElementById('input-data');
  const lang = window.currentLang;
  const s = window.VInfinityI18n.STRINGS[lang];

  const fileName = first.name.toLowerCase();
  const isPDF = first.type.includes('pdf') || fileName.endsWith('.pdf');
  const isWord = first.type.includes('word') || fileName.endsWith('.docx') || fileName.endsWith('.doc');
  const isHeic = fileName.endsWith('.heic') || fileName.endsWith('.heif');

  if (isHeic) {
    inputData.value = lang === 'ar' ? `[تم تحميل صورة HEIC: ${first.name} — جاهزة للتحويل]` : `[HEIC image loaded: ${first.name} — ready to convert]`;
    updateStats();
    return;
  }

  if (first.type.startsWith('image/')) {
    reader.onload = (e) => {
      first.dataUrl = e.target.result;
      inputData.value = lang === 'ar' ? `[تم تحميل الصورة: ${first.name}]` : `[Image Loaded: ${first.name}]`;
      updateStats();
    };
    reader.readAsDataURL(first);
  } else if (isWord) {
    const executeBtn = document.querySelector('.btn-execute');
    window.isDocxProcessing = true;
    if (executeBtn) {
      executeBtn.disabled = true;
      executeBtn.innerText = lang === 'ar' ? '⏳ جاري القراءة...' : '⏳ Processing...';
    }
    inputData.value = lang === 'ar' ? '⏳ جاري تجهيز الملف للمعاينة...' : '⏳ Reading Word file...';
    updateStats();

    reader.onload = function (e) {
      mammoth
        .extractRawText({ arrayBuffer: e.target.result })
        .then(function (resultText) {
          inputData.value = resultText.value.trim() || `[Loaded Word: ${first.name}]`;
          updateStats();
        })
        .catch(function (err) {
          console.error('Mammoth preview error:', err);
        })
        .finally(() => {
          window.isDocxProcessing = false;
          if (executeBtn) {
            executeBtn.disabled = false;
            executeBtn.innerText = s.execute;
          }
        });
    };
    reader.readAsArrayBuffer(first);
  } else if (isPDF) {
    inputData.value = lang === 'ar' ? '⏳ جاري استخراج معاينة النص...' : '⏳ Extracting text preview...';
    updateStats();
    reader.onload = async function () {
      try {
        const typedarray = new Uint8Array(this.result);
        const pdf = await pdfjsLib.getDocument(typedarray).promise;
        let fullText = '';
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const textContent = await page.getTextContent();
          fullText += pdfPageToOrderedText(textContent.items) + '\n\n';
        }
        inputData.value = fullText.trim() || `[Loaded PDF: ${first.name}]`;
        updateStats();
      } catch (err) {
        console.error('PDF text extraction error:', err);
        inputData.value = `[Loaded PDF: ${first.name}]`;
        updateStats();
      }
    };
    reader.readAsArrayBuffer(first);
  } else {
    reader.onload = (e) => {
      const text = e.target.result;
      if (text.includes('%PDF-') || text.includes('PK\x03\x04')) {
        inputData.value = lang === 'ar' ? '⚠️ ملف ثنائي غير مدعوم للطباعة كنص.' : '⚠️ Binary file detected.';
      } else {
        inputData.value = text;
      }
      updateStats();
    };
    reader.readAsText(first, 'UTF-8');
  }
}

function initFileHandling() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) processFiles(Array.from(e.target.files));
  });

  // ✅ ربط أحداث السحب والإفلات الحقيقية (كانت مفقودة سابقاً رغم ظهور النص في الواجهة)
  ['dragenter', 'dragover'].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-active');
    })
  );
  ['dragleave', 'drop'].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-active');
    })
  );
  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length > 0) processFiles(Array.from(files));
  });
}

window.VInfinityFiles = { processFiles, initFileHandling };
