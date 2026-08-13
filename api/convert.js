// =====================================================================================
// convert.js — موجّه الطلبات المحدث لربط Vercel بسيرفر Render المعالج
// =====================================================================================

process.env.AWS_LAMBDA_JS_RUNTIME = process.env.AWS_LAMBDA_JS_RUNTIME || 'nodejs20.x';

const { applyCors } = require('./_lib/cors');
const { isArabicText, rejectIfFileTooLarge, badRequest } = require('./_lib/validation');

const { handlers: documentHandlers } = require('./_lib/documents');
const { handlers: spreadsheetHandlers } = require('./_lib/spreadsheets');
const { handlers: imageHandlers } = require('./_lib/images');
const { handlers: devtoolHandlers } = require('./_lib/devtools');
const { handlers: utilityHandlers } = require('./_lib/utilities');

// رابط سيرفر Render الخاص بك
const RENDER_BACKEND_URL = 'https://infinity-converter.onrender.com/convert';

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

    // العمليات الثقيلة (مثل Word to PDF وغيرها) سنقوم بتحويلها مباشرة لسيرفر Render المعالج
    const heavyActions = ['word-to-pdf', 'csv-to-pdf', 'pdf-to-doc', 'pdf-to-docx', 'doc-to-docx', 'pdf-to-excel', 'pdf-to-ppt'];
    
    if (heavyActions.includes(action)) {
      const response = await fetch(RENDER_BACKEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req.body)
      });

      if (!response.ok) {
        throw new Error('فشل المعالجة في السيرفر الخارجي');
      }

      const buffer = await response.arrayBuffer();
      res.setHeader('Content-Type', response.headers.get('Content-Type') || 'application/octet-stream');
      res.setHeader('Content-Disposition', response.headers.get('Content-Disposition') || 'attachment; filename="converted.pdf"');
      return res.status(200).send(Buffer.from(buffer));
    }

    // باقي العمليات الخفيفة تتم محلياً كالمعتاد
    const handler = registry[action];
    if (!handler) return badRequest(res, 'Unknown action: ' + action);

    return await handler({ req, res, action, text, json, fileBase64, filesBase64, mimeType, isArabic });
  } catch (err) {
    console.error('convert.js error:', err);
    return res.status(500).json({ error: err.message });
  }
};
