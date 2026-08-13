// =====================================================================================
// utilities.js — أدوات عامة: QR / كلمات المرور / العدادات / الحاسبات / Markdown / Diff
// =====================================================================================

const crypto = require('crypto');
const QRCode = require('qrcode');
const { marked } = require('marked');
const { diffLines } = require('diff');
let zxcvbn;
try {
  zxcvbn = require('zxcvbn');
} catch (e) {
  /* optional dependency */
}

function secureRandomString(length, chars) {
  const bytes = crypto.randomBytes(length * 2);
  let out = '';
  for (let i = 0; i < bytes.length && out.length < length; i++) out += chars[bytes[i] % chars.length];
  return out;
}

const handlers = {
  async 'text-to-qr'({ res, text }) {
    const dataUrl = await QRCode.toDataURL(text, { errorCorrectionLevel: 'H', width: 280, margin: 1 });
    return res.status(200).json({ resultImage: dataUrl });
  },

  async 'password-generator'({ res }) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=';
    return res.status(200).json({ result: secureRandomString(20, chars) });
  },

  async 'password-strength'({ res, text, isArabic }) {
    if (zxcvbn) {
      const r = zxcvbn(text);
      const labelsAr = ['ضعيفة جداً', 'ضعيفة', 'متوسطة', 'قوية', 'قوية جداً'];
      const labelsEn = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
      const crackTime = r.crack_times_display.offline_slow_hashing_1e4_per_second;
      const result = `${isArabic ? 'التقييم' : 'Score'}: ${isArabic ? labelsAr[r.score] : labelsEn[r.score]} (${r.score}/4)\n${isArabic ? 'وقت تقريبي للاختراق' : 'Estimated crack time'}: ${crackTime}`;
      return res.status(200).json({ result });
    }
    const strong = text.length >= 8 && /[A-Z]/.test(text) && /[0-9]/.test(text) && /[^A-Za-z0-9]/.test(text);
    return res.status(200).json({ result: strong ? '🔒 STRONG' : '⚠️ WEAK' });
  },

  async 'text-counter'({ res, text }) {
    return res.status(200).json({
      result: `Chars: ${text.length}\nWords: ${text.trim() ? text.trim().split(/\s+/).length : 0}\nLines: ${text.split('\n').length}`,
    });
  },

  async 'percentage-calc'({ res, text, isArabic }) {
    const nums = text.match(/\d+(\.\d+)?/g);
    if (!nums || nums.length < 2) {
      return res.status(200).json({ result: isArabic ? 'يرجى إدخال رقمين' : 'Please enter two numbers' });
    }
    return res.status(200).json({ result: `${nums[0]}% of ${nums[1]} = ${(parseFloat(nums[0]) / 100) * parseFloat(nums[1])}` });
  },

  async 'byte-converter'({ res, text }) {
    const bytes = parseFloat(text.replace(/[^0-9.]/g, ''));
    return res.status(200).json({
      result: `Bytes: ${bytes}\nKB: ${(bytes / 1024).toFixed(2)}\nMB: ${(bytes / 1024 ** 2).toFixed(2)}\nGB: ${(bytes / 1024 ** 3).toFixed(4)}`,
    });
  },

  async 'unit-converter'({ res, text }) {
    const val = parseFloat(text.replace(/[^0-9.]/g, ''));
    return res.status(200).json({
      result: `Meters: ${val} m\nFeet: ${(val * 3.28084).toFixed(2)} ft\nInches: ${(val * 39.3701).toFixed(2)} in\nMiles: ${(val / 1609.34).toFixed(4)} mi`,
    });
  },

  async 'markdown-to-html'({ res, text }) {
    return res.status(200).json({ result: marked.parse(text) });
  },

  async 'text-diff'({ res, text }) {
    const lines = text.split('\n');
    const mid = Math.floor(lines.length / 2);
    const changes = diffLines(lines.slice(0, mid).join('\n'), lines.slice(mid).join('\n'));
    const result = changes.map((p) => (p.added ? '+ ' : p.removed ? '- ' : '  ') + p.value.replace(/\n$/, '')).join('\n');
    return res.status(200).json({ result });
  },
};

module.exports = { handlers };
