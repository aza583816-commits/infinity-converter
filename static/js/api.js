// Infinity Converter API client v2.
// File uploads intentionally use multipart/form-data; Base64 JSON remains supported only
// by the backend for backward compatibility with older clients.
export async function convert({ action, text = '', lang = 'ar', files = [], extra = {}, signal } = {}) {
  const form = new FormData();
  form.append('action', action);
  form.append('text', text);
  form.append('lang', lang);
  for (const file of files) form.append('files', file, file.name);
  for (const [key, value] of Object.entries(extra)) form.append(key, value);

  const response = await fetch('/convert', { method: 'POST', body: form, signal });
  if (!response.ok) {
    let message = lang === 'ar' ? 'حدث خطأ في المعالجة.' : 'Processing failed.';
    try { const data = await response.json(); if (data.error) message = data.error; } catch (_) {}
    throw new Error(message);
  }

  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) return { binary: false, data: await response.json() };
  return { binary: true, blob: await response.blob(), filename: filenameFromDisposition(response.headers.get('content-disposition')) };
}

function filenameFromDisposition(value) {
  if (!value) return 'downloaded_file';
  const match = value.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : 'downloaded_file';
}
