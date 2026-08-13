// =====================================================================================
// config.js — إعدادات مشتركة عبر كل الخدمات (Single Source of Truth)
// =====================================================================================

module.exports = {
  ALLOWED_ORIGINS: [
    'https://www.infinityconverter.com',
    'https://infinityconverter.com',
  ],
  // نسمح أيضاً بأي معاينة على Vercel عبر نمط regex (يُستخدم في cors.js)
  VERCEL_PREVIEW_REGEX: /^https:\/\/[a-z0-9-]+\.vercel\.app$/,

  MAX_FILE_BYTES: 4 * 1024 * 1024, // 4MB لكل ملف

  // خط عربي موثوق نضمن تحميله داخل متصفح Chromium الخاص بالسيرفر (Google Fonts)
  // هذا هو الحل الجذري لمشكلة "الرموز المخربطة" عند تحويل Word/CSV العربي إلى PDF:
  // متصفح Chromium على البيئة السحابية (Lambda/Vercel) لا يحتوي على خطوط عربية مثبّتة
  // بشكل افتراضي، فتظهر مربعات فارغة (tofu) أو رموز مشوّهة بدل الحروف العربية.
  ARABIC_FONT_FAMILY: "'Noto Naskh Arabic', 'Noto Sans Arabic', 'Cairo', 'Arial', sans-serif",
  ARABIC_FONT_STYLESHEET_URL:
    'https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;700&family=Noto+Sans+Arabic:wght@400;700&display=swap',
  LATIN_FONT_FAMILY: "'Segoe UI', 'Cairo', Tahoma, Arial, sans-serif",
};
