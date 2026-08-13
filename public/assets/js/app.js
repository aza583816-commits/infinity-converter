// =====================================================================================
// app.js — تجميع كل الوحدات وتشغيل التطبيق (نقطة الدخول الوحيدة على الواجهة)
// =====================================================================================

const ALL_ACTIONS = [
  'word-to-pdf', 'csv-to-pdf', 'pdf-to-text', 'pdf-to-doc', 'pdf-to-docx', 'doc-to-docx',
  'pdf-to-excel', 'pdf-to-ppt', 'merge-pdf', 'split-pdf', 'text-to-excel', 'json-to-excel',
  'excel-to-json', 'csv-to-json', 'text-to-csv', 'word-to-csv', 'csv-to-word', 'compress-image',
  'image-to-png', 'image-to-jpg', 'image-to-base64', 'image-to-pdf', 'heic-to-jpg', 'base64-tool',
  'url-encoder', 'json-beautifier', 'css-js-minifier', 'html-entity', 'hash-generator',
  'timestamp-converter', 'clean-text', 'text-to-qr', 'password-generator', 'password-strength',
  'text-counter', 'percentage-calc', 'byte-converter', 'unit-converter', 'markdown-to-html', 'text-diff',
];

const MAX_FILE_MB = 4;

function updateStats() {
  const text = document.getElementById('input-data').value;
  document.getElementById('char-count').innerText = text.length;
  document.getElementById('word-count').innerText = text.trim() ? text.trim().split(/\s+/).length : 0;
}

function validateFileSize(file, lang) {
  const sizeMB = file.size / (1024 * 1024);
  if (sizeMB > MAX_FILE_MB) {
    return lang === 'ar'
      ? `⚠️ الملف "${file.name}" حجمه ${sizeMB.toFixed(1)}MB — يتجاوز الحد المسموح (${MAX_FILE_MB}MB).`
      : `⚠️ File "${file.name}" is ${sizeMB.toFixed(1)}MB — exceeds the allowed limit (${MAX_FILE_MB}MB).`;
  }
  return null;
}

let loadingInterval = null;
function startLoadingAnimation(executeBtn, baseText) {
  let dots = 0;
  loadingInterval = setInterval(() => {
    dots = (dots + 1) % 4;
    executeBtn.innerText = baseText + '.'.repeat(dots);
  }, 400);
}
function stopLoadingAnimation() {
  if (loadingInterval) {
    clearInterval(loadingInterval);
    loadingInterval = null;
  }
}

async function runConversion() {
  const { callConvertApi, fileToBase64, NEEDS_FILE, NEEDS_MULTIPLE_FILES, BINARY_ACTIONS } = window.VInfinityApi;
  const { downloadBlob } = window.VInfinityDownload;
  const { showToast } = window.VInfinityToast;

  const lang = window.currentLang;
  const s = window.VInfinityI18n.STRINGS[lang];
  const input = document.getElementById('input-data').value;
  const type = document.getElementById('conversion-type').value;
  const output = document.getElementById('output-data');
  const qrContainer = document.getElementById('qrcode-container');
  const executeBtn = document.querySelector('.btn-execute');
  qrContainer.innerHTML = '';

  if (type === 'text-to-speech') {
    if (!input.trim()) {
      output.value = s.needTextForSpeech;
      return;
    }
    const msg = new SpeechSynthesisUtterance(input);
    msg.lang = /[\u0600-\u06FF]/.test(input) || lang === 'ar' ? 'ar-SA' : 'en-US';
    window.speechSynthesis.speak(msg);
    output.value = s.speaking;
    return;
  }

  if (window.isDocxProcessing) {
    output.value = lang === 'ar' ? '⏳ الملف قيد التجهيز...' : '⏳ Processing...';
    return;
  }

  const loadedFiles = window.loadedFiles;

  if (NEEDS_MULTIPLE_FILES.includes(type)) {
    if (!loadedFiles || loadedFiles.length < 2) {
      output.value = s.needTwoPdfs;
      return;
    }
  } else if (NEEDS_FILE.includes(type) && !loadedFiles[0] && !input.trim()) {
    output.value = s.needFileOrText;
    return;
  }

  const filesToCheck = NEEDS_MULTIPLE_FILES.includes(type) ? loadedFiles : loadedFiles[0] ? [loadedFiles[0]] : [];
  for (const f of filesToCheck) {
    const sizeError = validateFileSize(f, lang);
    if (sizeError) {
      output.value = sizeError;
      return;
    }
  }

  const origBtnText = executeBtn.innerText;
  executeBtn.disabled = true;
  startLoadingAnimation(executeBtn, s.processingServer);

  try {
    if (!ALL_ACTIONS.includes(type)) {
      output.value = input;
      return;
    }

    const payload = { action: type, text: input, lang };

    if (NEEDS_MULTIPLE_FILES.includes(type)) {
      payload.filesBase64 = await Promise.all(loadedFiles.map((f) => fileToBase64(f)));
    } else if (NEEDS_FILE.includes(type) && loadedFiles[0]) {
      payload.fileBase64 = await fileToBase64(loadedFiles[0]);
      payload.fileName = loadedFiles[0].name;
      payload.mimeType = loadedFiles[0].type;
    }
    if (type === 'json-to-excel') payload.json = input;

    const result = await callConvertApi(payload);

    if (result.isBinary) {
      output.value = downloadBlob(result.blob, result.filename, lang);
    } else if (result.data.resultImage) {
      const img = document.createElement('img');
      img.src = result.data.resultImage;
      img.style.width = '140px';
      img.style.height = '140px';
      qrContainer.appendChild(img);
      output.value = s.qrGenerated;
    } else {
      output.value = result.data.result !== undefined ? result.data.result : JSON.stringify(result.data);
    }
  } catch (e) {
    console.error('Conversion error:', e);
    output.value = (lang === 'ar' ? '❌ حدث خطأ: ' : '❌ Error: ') + e.message;
    showToast(output.value, { duration: 5000 });
  } finally {
    stopLoadingAnimation();
    executeBtn.disabled = false;
    executeBtn.innerText = origBtnText;
  }
}

function initApp() {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';

  document.getElementById('conversion-type').innerHTML = window.VInfinityI18n.TOOL_OPTIONS_EN;

  document.getElementById('input-data').addEventListener('input', updateStats);
  document.getElementById('theme-btn').addEventListener('click', window.VInfinityTheme.toggleTheme);
  document.getElementById('lang-btn').addEventListener('click', window.VInfinityTheme.toggleLanguage);
  document.querySelector('.btn-execute').addEventListener('click', runConversion);
  document.getElementById('dropZone').addEventListener('click', () => document.getElementById('fileInput').click());

  document.getElementById('copy-btn').addEventListener('click', async () => {
    const output = document.getElementById('output-data');
    if (!output.value) return;
    try {
      await navigator.clipboard.writeText(output.value);
      const s = window.VInfinityI18n.STRINGS[window.currentLang];
      window.VInfinityToast.showToast(s.copied, { duration: 2000 });
    } catch (e) {
      console.error('Clipboard error:', e);
    }
  });

  document.getElementById('clear-btn').addEventListener('click', () => {
    document.getElementById('input-data').value = '';
    document.getElementById('output-data').value = '';
    document.getElementById('qrcode-container').innerHTML = '';
    window.loadedFiles = [];
    document.getElementById('fileInput').value = '';
    updateStats();
  });

  document.getElementById('pwa-btn').addEventListener('click', () => {
    const lang = window.currentLang;
    window.VInfinityToast.showToast(
      lang === 'ar'
        ? 'لإضافة التطبيق لشاشتك الرئيسية: اضغط على زر المشاركة في المتصفح، ثم اختر "إضافة إلى الشاشة الرئيسية".'
        : 'To add to your home screen: tap the Share button in your browser, then choose "Add to Home Screen".',
      { duration: 6000 }
    );
  });

  window.VInfinityFiles.initFileHandling();
  updateStats();
}

document.addEventListener('DOMContentLoaded', initApp);

window.VInfinityApp = { updateStats, runConversion };
