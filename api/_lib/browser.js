// =====================================================================================
// browser.js — تشغيل Chromium بدون واجهة (Headless) لتحويل HTML إلى PDF
// =====================================================================================

const path = require('path');
const chromium = require('@sparticuz/chromium');
const puppeteer = require('puppeteer-core');
const {
  ARABIC_FONT_FAMILY,
  ARABIC_FONT_STYLESHEET_URL,
  LATIN_FONT_FAMILY,
} = require('./config');

async function getBrowser() {
  if (typeof chromium.setGraphicsMode === 'function') {
    chromium.setGraphicsMode(false);
  } else {
    chromium.setGraphicsMode = false;
  }

  const executablePath = await chromium.executablePath();
  process.env.LD_LIBRARY_PATH = [path.dirname(executablePath), process.env.LD_LIBRARY_PATH || '']
    .filter(Boolean)
    .join(':');

  return puppeteer.launch({
    args: chromium.args,
    defaultViewport: chromium.defaultViewport,
    executablePath,
    headless: chromium.headless,
    ignoreHTTPSErrors: true,
  });
}

/**
 * ينتظر جاهزية كل الخطوط المطلوبة في الصفحة، مع سقف زمني أمان.
 */
async function waitForFonts(page, timeoutMs = 4000) {
  await Promise.race([
    page.evaluate(() => document.fonts && document.fonts.ready).catch(() => null),
    new Promise((resolve) => setTimeout(resolve, timeoutMs)),
  ]);
}

function buildFullHtml(bodyHtml, isArabic) {
  const fontFamily = isArabic ? ARABIC_FONT_FAMILY : LATIN_FONT_FAMILY;
  const fontLink = isArabic
    ? `<link rel="stylesheet" href="${ARABIC_FONT_STYLESHEET_URL}">`
    : '';

  return `<!DOCTYPE html>
<html dir="${isArabic ? 'rtl' : 'ltr'}" lang="${isArabic ? 'ar' : 'en'}">
<head>
<meta charset="utf-8">
${fontLink}
<style>
  body {
    font-family: ${fontFamily};
    direction: ${isArabic ? 'rtl' : 'ltr'};
    text-align: ${isArabic ? 'right' : 'left'};
    color: #000;
    background: #fff;
    padding: 10px 20px;
    unicode-bidi: plaintext;
  }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  th, td { border: 1px solid #000; padding: 8px; color: #000; }
  th { background: #e2e8f0; font-weight: bold; }
  pre { white-space: pre-wrap; font-family: inherit; font-size: 14px; }
  img { max-width: 100%; }
</style>
</head>
<body>${bodyHtml}</body>
</html>`;
}

async function htmlToPdfBuffer(bodyHtml, isArabic) {
  let browser = null;
  try {
    browser = await getBrowser();
    const page = await browser.newPage();
    const fullHtml = buildFullHtml(bodyHtml, isArabic);

    // تم التعديل هنا: استخدام domcontentloaded لضمان عدم التعليق في انتظار الشبكة
    await page.setContent(fullHtml, { waitUntil: 'domcontentloaded', timeout: 15000 });
    
    // الانتظار الفعلي لتحميل الخط العربي
    await waitForFonts(page);

    return await page.pdf({
      format: 'A4',
      printBackground: true,
      margin: { top: '15mm', bottom: '15mm', left: '15mm', right: '15mm' },
    });
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
}

module.exports = { getBrowser, htmlToPdfBuffer };
