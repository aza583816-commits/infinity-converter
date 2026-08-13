// =====================================================================================
// api.js — طبقة اتصال واحدة بالـ backend، لسهولة تغيير المسار أو إضافة headers لاحقاً
// =====================================================================================

const API_ENDPOINT = '/api/convert';

const BINARY_ACTIONS = new Set([
  'word-to-pdf', 'csv-to-pdf', 'pdf-to-doc', 'pdf-to-docx', 'doc-to-docx',
  'pdf-to-excel', 'pdf-to-ppt', 'merge-pdf', 'split-pdf',
  'text-to-excel', 'json-to-excel', 'text-to-csv', 'word-to-csv', 'csv-to-word',
  'compress-image', 'image-to-png', 'image-to-jpg', 'image-to-pdf', 'heic-to-jpg',
]);

const BINARY_FILENAMES = {
  'word-to-pdf': 'converted_document.pdf', 'csv-to-pdf': 'converted_table.pdf',
  'pdf-to-doc': 'converted.doc', 'pdf-to-docx': 'converted.docx', 'doc-to-docx': 'converted.docx',
  'pdf-to-excel': 'converted.xlsx', 'pdf-to-ppt': 'converted.pptx',
  'merge-pdf': 'merged.pdf', 'split-pdf': 'split_pages.zip',
  'text-to-excel': 'converted.xlsx', 'json-to-excel': 'converted.xlsx',
  'text-to-csv': 'converted.csv', 'word-to-csv': 'converted.csv', 'csv-to-word': 'converted.docx',
  'compress-image': 'compressed.jpg', 'image-to-png': 'converted.png', 'image-to-jpg': 'converted.jpg',
  'image-to-pdf': 'converted.pdf', 'heic-to-jpg': 'converted.jpg',
};

const NEEDS_FILE = ['word-to-pdf', 'pdf-to-text', 'excel-to-json', 'compress-image', 'image-to-png', 'image-to-jpg', 'image-to-base64', 'image-to-pdf', 'heic-to-jpg', 'pdf-to-excel', 'pdf-to-ppt', 'split-pdf'];
const NEEDS_MULTIPLE_FILES = ['merge-pdf'];

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * ينفّذ الطلب على الـ backend. يُرجع { isBinary, blob } أو { isBinary: false, data }.
 */
async function callConvertApi(payload) {
  const isBinary = BINARY_ACTIONS.has(payload.action);
  const res = await fetch(API_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let msg = window.currentLang === 'ar' ? 'خطأ من السيرفر' : 'Server error';
    try {
      const j = await res.json();
      if (j.error) msg = j.error;
    } catch (e) {
      /* ignore */
    }
    throw new Error(msg);
  }

  if (isBinary) {
    const blob = await res.blob();
    return { isBinary: true, blob, filename: BINARY_FILENAMES[payload.action] };
  }
  const data = await res.json();
  return { isBinary: false, data };
}

window.VInfinityApi = {
  callConvertApi,
  fileToBase64,
  BINARY_ACTIONS,
  BINARY_FILENAMES,
  NEEDS_FILE,
  NEEDS_MULTIPLE_FILES,
};
