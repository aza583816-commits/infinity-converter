function downloadBlob(blob, filename, lang) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'download';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => window.URL.revokeObjectURL(url), 1000);

  return lang === 'ar' ? `✅ تم تنزيل الملف: ${filename}` : `✅ File downloaded: ${filename}`;
}

window.VInfinityDownload = { downloadBlob };
