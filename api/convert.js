// =====================================================================================
// convert.js — نقطة الدخول الوحيدة للـ API (Router خفيف فقط، بدون منطق أعمال)
//
// كل خدمة انتقلت لملفها الخاص تحت api/_lib/*  →  سهولة صيانة، واختبار كل جزء لوحده،
// وتفادي ملف ٥٠٠ سطر واحد يحتوي كل التحويلات معاً.
// =====================================================================================

process.env.AWS_LAMBDA_JS_RUNTIME = process.env.AWS_LAMBDA_JS_RUNTIME || 'nodejs20.x';

const { applyCors } = require('./_lib/cors');
const { isArabicText, rejectIfFileTooLarge, badRequest } = require('./_lib/validation');

const { handlers: documentHandlers } = require('./_lib/documents');
const { handlers: spreadsheetHandlers } = require('./_lib/spreadsheets');
const { handlers: imageHandlers } = require('./_lib/images');
const { handlers: devtoolHandlers } = require('./_lib/devtools');
const { handlers: utilityHandlers } = require('./_lib/utilities');

// دمج كل الخدمات في سجلّ (registry) واحد: action -> handler
const registry = {
  ...documentHandlers,
  ...spreadsheetHandlers,
  ...imageHandlers,
  ...devtoolHandlers,
  ...utilityHandlers,
};

module.exports = async (req, res) => {
  if (applyCors(req, res)) return;
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const { action, text = '', json, fileBase64, filesBase64, mimeType, lang } = req.body || {};
    const isArabic = lang === 'ar' || isArabicText(text);

    if (rejectIfFileTooLarge(res, fileBase64, isArabic)) return;

    const handler = registry[action];
    if (!handler) return badRequest(res, 'Unknown action: ' + action);

    return await handler({ req, res, action, text, json, fileBase64, filesBase64, mimeType, isArabic });
  } catch (err) {
    console.error('convert.js error:', err);
    return res.status(500).json({ error: err.message });
  }
};
