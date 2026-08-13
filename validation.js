// =====================================================================================
// validation.js — دوال مساعدة صغيرة مشتركة (تحقق + تنظيف نصوص)
// =====================================================================================

const { MAX_FILE_BYTES } = require('./config');

function isArabicText(t) {
  return /[\u0600-\u06FF]/.test(t || '');
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function parseCsv(csv) {
  return (csv || '').trim().split('\n').map((r) => r.split(','));
}

/**
 * يتحقق من أن حجم أي ملف Base64 لا يتجاوز الحد المسموح، ويرسل خطأ 413 عند التجاوز.
 * @returns {boolean} true إذا تم إرسال خطأ (يجب إيقاف المعالجة)
 */
function rejectIfFileTooLarge(res, fileBase64, isArabic) {
  if (fileBase64 && Buffer.byteLength(fileBase64, 'base64') > MAX_FILE_BYTES) {
    res.status(413).json({
      error: isArabic
        ? 'حجم الملف أكبر من الحد المسموح (4MB)'
        : 'File exceeds the allowed size (4MB)',
    });
    return true;
  }
  return false;
}

function badRequest(res, message) {
  res.status(400).json({ error: message });
  return true;
}

module.exports = { isArabicText, escapeHtml, parseCsv, rejectIfFileTooLarge, badRequest };
