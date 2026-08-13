// =====================================================================================
// V-Infinity Converter — Backend موحّد (كل الأدوات بملف واحد)
// كل الطلبات تدخل من هنا وتوجَّه حسب حقل "action" بالـ body
// =====================================================================================

const mammoth = require('mammoth');
const pdfParse = require('pdf-parse');
const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
const chromium = require('@sparticuz/chromium');
const puppeteer = require('puppeteer-core');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell } = require('docx');
const { PDFDocument } = require('pdf-lib');
const XLSX = require('xlsx');
const PptxGenJS = require('pptxgenjs');
const JSZip = require('jszip');
const sharp = require('sharp');
const heicConvert = require('heic-convert');
const QRCode = require('qrcode');
const crypto = require('crypto');
const { marked } = require('marked');
const { diffLines } = require('diff');
let zxcvbn, terser, CleanCSS;
try { zxcvbn = require('zxcvbn'); } catch (e) { /* optional */ }
try { terser = require('terser'); } catch (e) { /* optional */ }
try { CleanCSS = require('clean-css'); } catch (e) { /* optional */ }

// ---------------------------------------------------------------------------
// [1] حماية CORS — يقبل الطلبات فقط من الدومين الرسمي (+ بيئات vercel.app للمعاينة)
// عدّل هذي القائمة إذا أضفت نطاقات فرعية جديدة
// ---------------------------------------------------------------------------
const ALLOWED_ORIGINS = [
  'https://www.infinityconverter.com',
  'https://infinityconverter.com',
];

function isAllowedOrigin(origin) {
  if (!origin) return false;
  if (ALLOWED_ORIGINS.includes(origin)) return true;
  if (/^https:\/\/[a-z0-9-]+\.vercel\.app$/.test(origin)) return true;
  return false;
}

function applyCors(req, res) {
  const origin = req.headers.origin;
  if (isAllowedOrigin(origin)) res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Max-Age', '86400');
  if (req.method === 'OPTIONS') { res.status(204).end(); return true; }
  if (origin && !isAllowedOrigin(origin)) { res.status(403).json({ error: 'Forbidden: origin not allowed' }); return true; }
  return false;
}

// ---------------------------------------------------------------------------
// [2] أدوات مساعدة عامة
// ---------------------------------------------------------------------------
const MAX_FILE_BYTES = 4 * 1024 * 1024; // 4MB — هامش أمان تحت حد الـ 4.5MB لخطة Vercel Hobby

function isArabicText(t) { return /[\u0600-\u06FF]/.test(t || ''); }
function escapeHtml(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function parseCsv(csv) { return csv.trim().split('\n').map(r => r.split(',')); }

async function getBrowser() {
  return puppeteer.launch({
    args: chromium.args,
    defaultViewport: chromium.defaultViewport,
    executablePath: await chromium.executablePath(),
    headless: chromium.headless,
  });
}

// طباعة HTML إلى PDF عبر Chromium حقيقي (بديل قوي وموثوق لـ html2canvas)
async function htmlToPdfBuffer(bodyHtml, isArabic) {
  const browser = await getBrowser();
  try {
    const page = await browser.newPage();
    const fullHtml = `<!DOCTYPE html><html dir="${isArabic ? 'rtl' : 'ltr'}"><head><meta charset="utf-8">
    <style>
      body{font-family:'Segoe UI',Tahoma,Arial,sans-serif;direction:${isArabic ? 'rtl' : 'ltr'};text-align:${isArabic ? 'right' : 'left'};color:#000;background:#fff;padding:10px 20px;}
      table{width:100%;border-collapse:collapse;margin-bottom:16px;}
      th,td{border:1px solid #000;padding:8px;color:#000;}
      th{background:#e2e8f0;font-weight:bold;}
      pre{white-space:pre-wrap;font-family:inherit;font-size:14px;}
      img{max-width:100%;}
    </style></head><body>${bodyHtml}</body></html>`;
    await page.setContent(fullHtml, { waitUntil: 'networkidle0' });
    return page.pdf({ format: 'A4', printBackground: true, margin: { top: '15mm', bottom: '15mm', left: '15mm', right: '15mm' } });
  } finally {
    await browser.close();
  }
}

function csvToHtmlTable(csv) {
  const rows = csv.trim().split('\n').map(r => r.split(','));
  return '<table>' + rows.map((row, ri) =>
    '<tr>' + row.map(c => `<${ri === 0 ? 'th' : 'td'}>${escapeHtml((c || '').trim())}</${ri === 0 ? 'th' : 'td'}>`).join('') + '</tr>'
  ).join('') + '</table>';
}

async function buildDocxFromText(text, isArabic) {
  const paragraphs = (text || '').split('\n').map(line => new Paragraph({
    bidirectional: isArabic,
    alignment: isArabic ? 'right' : 'left',
    children: [new TextRun({ text: line.length ? line : ' ', rightToLeft: isArabic })],
  }));
  const doc = new Document({ sections: [{ children: paragraphs }] });
  return Packer.toBuffer(doc);
}

async function extractPdfPagesWithPositions(buffer) {
  const loadingTask = pdfjsLib.getDocument({ data: new Uint8Array(buffer) });
  const pdf = await loadingTask.promise;
  const pages = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    pages.push(content.items.map(it => ({ text: it.str, x: it.transform[4], y: it.transform[5] })));
  }
  return pages;
}

function itemsToRows(items) {
  const parts = items.filter(p => p.text.trim().length > 0);
  parts.sort((a, b) => (Math.abs(a.y - b.y) > 7 ? b.y - a.y : a.x - b.x));
  const lines = [];
  let currentLine = [];
  let lastY = null;
  parts.forEach(p => {
    if (lastY === null || Math.abs(lastY - p.y) <= 7) { currentLine.push(p); lastY = p.y; }
    else { lines.push(currentLine); currentLine = [p]; lastY = p.y; }
  });
  if (currentLine.length) lines.push(currentLine);
  return lines.map(line => {
    line.sort((a, b) => a.x - b.x);
    const cells = [];
    let currentCell = '';
    let prevEndX = null;
    line.forEach(it => {
      if (prevEndX !== null && it.x - prevEndX > 15) { cells.push(currentCell.trim()); currentCell = ''; }
      currentCell += (currentCell ? ' ' : '') + it.text;
      prevEndX = it.x + (it.text.length * 5);
    });
    if (currentCell) cells.push(currentCell.trim());
    return cells;
  });
}

function secureRandomString(length, chars) {
  const bytes = crypto.randomBytes(length * 2);
  let out = '';
  for (let i = 0; i < bytes.length && out.length < length; i++) out += chars[bytes[i] % chars.length];
  return out;
}

// ---------------------------------------------------------------------------
// [3] المعالج الرئيسي — نقطة الدخول الوحيدة لكل الأدوات
// ---------------------------------------------------------------------------
module.exports = async (req, res) => {
  if (applyCors(req, res)) return;
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const { action, text = '', json, fileBase64, filesBase64, mimeType, lang } = req.body || {};
    const isArabic = lang === 'ar' || isArabicText(text);

    if (fileBase64 && Buffer.byteLength(fileBase64, 'base64') > MAX_FILE_BYTES) {
      return res.status(413).json({ error: isArabic ? 'حجم الملف أكبر من الحد المسموح (4MB)' : 'File exceeds the allowed size (4MB)' });
    }

    switch (action) {
      // ============================= مستندات (Word/PDF/CSV) =============================
      case 'word-to-pdf': {
        let html;
        if (fileBase64) {
          const result = await mammoth.convertToHtml({ buffer: Buffer.from(fileBase64, 'base64') });
          html = result.value;
        } else {
          html = `<pre>${escapeHtml(text)}</pre>`;
        }
        const pdf = await htmlToPdfBuffer(html, isArabic);
        res.setHeader('Content-Type', 'application/pdf');
        res.setHeader('Content-Disposition', 'attachment; filename="converted_document.pdf"');
        return res.status(200).send(pdf);
      }

      case 'csv-to-pdf': {
        const pdf = await htmlToPdfBuffer(csvToHtmlTable(text), isArabic);
        res.setHeader('Content-Type', 'application/pdf');
        res.setHeader('Content-Disposition', 'attachment; filename="converted_table.pdf"');
        return res.status(200).send(pdf);
      }

      case 'pdf-to-text': {
        if (!fileBase64) return res.status(400).json({ error: 'No file provided' });
        const data = await pdfParse(Buffer.from(fileBase64, 'base64'));
        return res.status(200).json({ result: data.text.trim() });
      }

      case 'pdf-to-doc':
      case 'pdf-to-docx':
      case 'doc-to-docx': {
        const buffer = await buildDocxFromText(text, isArabic);
        const ext = action === 'pdf-to-doc' ? 'doc' : 'docx';
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        res.setHeader('Content-Disposition', `attachment; filename="converted.${ext}"`);
        return res.status(200).send(buffer);
      }

      case 'pdf-to-excel': {
        if (!fileBase64) return res.status(400).json({ error: 'No file provided' });
        const pages = await extractPdfPagesWithPositions(Buffer.from(fileBase64, 'base64'));
        const wb = XLSX.utils.book_new();
        pages.forEach((items, idx) => {
          const ws = XLSX.utils.aoa_to_sheet(itemsToRows(items));
          XLSX.utils.book_append_sheet(wb, ws, `Page ${idx + 1}`);
        });
        const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.xlsx"');
        return res.status(200).send(buf);
      }

      case 'pdf-to-ppt': {
        if (!fileBase64) return res.status(400).json({ error: 'No file provided' });
        const data = await pdfParse(Buffer.from(fileBase64, 'base64'));
        const pagesText = data.text.split('\f').filter(p => p.trim().length > 0);
        const pptx = new PptxGenJS();
        (pagesText.length ? pagesText : [data.text]).forEach((pageText, idx) => {
          const slide = pptx.addSlide();
          slide.addText(`Page ${idx + 1}`, { x: 0.4, y: 0.3, fontSize: 20, bold: true, rtlMode: isArabic });
          slide.addText(pageText.trim().slice(0, 1800), { x: 0.4, y: 1.0, w: 9, h: 5, fontSize: 12, rtlMode: isArabic, align: isArabic ? 'right' : 'left' });
        });
        const buf = await pptx.write({ outputType: 'nodebuffer' });
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.pptx"');
        return res.status(200).send(buf);
      }

      case 'merge-pdf': {
        const files = filesBase64 || (fileBase64 ? [fileBase64] : []);
        if (files.length < 2) return res.status(400).json({ error: isArabic ? 'يرجى رفع ملفين PDF على الأقل للدمج' : 'Please upload at least 2 PDF files to merge' });
        const merged = await PDFDocument.create();
        for (const b64 of files) {
          const src = await PDFDocument.load(Buffer.from(b64, 'base64'));
          const copiedPages = await merged.copyPages(src, src.getPageIndices());
          copiedPages.forEach(p => merged.addPage(p));
        }
        const bytes = await merged.save();
        res.setHeader('Content-Type', 'application/pdf');
        res.setHeader('Content-Disposition', 'attachment; filename="merged.pdf"');
        return res.status(200).send(Buffer.from(bytes));
      }

      case 'split-pdf': {
        if (!fileBase64) return res.status(400).json({ error: 'No file provided' });
        const src = await PDFDocument.load(Buffer.from(fileBase64, 'base64'));
        const zip = new JSZip();
        for (let i = 0; i < src.getPageCount(); i++) {
          const single = await PDFDocument.create();
          const [copied] = await single.copyPages(src, [i]);
          single.addPage(copied);
          zip.file(`page_${i + 1}.pdf`, await single.save());
        }
        const zipBuf = await zip.generateAsync({ type: 'nodebuffer' });
        res.setHeader('Content-Type', 'application/zip');
        res.setHeader('Content-Disposition', 'attachment; filename="split_pages.zip"');
        return res.status(200).send(zipBuf);
      }

      // ============================= بيانات وجداول =============================
      case 'text-to-excel':
      case 'json-to-excel': {
        const wb = XLSX.utils.book_new();
        let ws;
        if (action === 'json-to-excel') {
          const data = JSON.parse(json || text);
          ws = XLSX.utils.json_to_sheet(Array.isArray(data) ? data : [data]);
        } else {
          ws = XLSX.utils.aoa_to_sheet(text.split('\n').map(l => l.split(/[\t,]/)));
        }
        XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
        const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.xlsx"');
        return res.status(200).send(buf);
      }

      case 'excel-to-json': {
        if (!fileBase64) return res.status(400).json({ error: 'No file provided' });
        const wb = XLSX.read(Buffer.from(fileBase64, 'base64'), { type: 'buffer' });
        const data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
        return res.status(200).json({ result: JSON.stringify(data, null, 2) });
      }

      case 'csv-to-json': {
        const rows = parseCsv(text);
        const headers = rows[0];
        const data = rows.slice(1).map(r => headers.reduce((acc, h, i) => { acc[h.trim()] = (r[i] || '').trim(); return acc; }, {}));
        return res.status(200).json({ result: JSON.stringify(data, null, 2) });
      }

      case 'text-to-csv':
      case 'word-to-csv': {
        const buf = Buffer.from('\uFEFF' + text, 'utf-8');
        res.setHeader('Content-Type', 'text/csv; charset=utf-8');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.csv"');
        return res.status(200).send(buf);
      }

      case 'csv-to-word': {
        const rows = parseCsv(text);
        const table = new Table({
          rows: rows.map(row => new TableRow({
            children: row.map(cell => new TableCell({
              children: [new Paragraph({ bidirectional: isArabic, children: [new TextRun({ text: (cell || '').trim(), rightToLeft: isArabic })] })],
            })),
          })),
        });
        const doc = new Document({ sections: [{ children: [table] }] });
        const buf = await Packer.toBuffer(doc);
        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.docx"');
        return res.status(200).send(buf);
      }

      // ============================= صور =============================
      case 'compress-image': {
        if (!fileBase64) return res.status(400).json({ error: 'No image provided' });
        const out = await sharp(Buffer.from(fileBase64, 'base64')).rotate().resize({ width: 1600, withoutEnlargement: true }).jpeg({ quality: 70, mozjpeg: true }).toBuffer();
        res.setHeader('Content-Type', 'image/jpeg');
        res.setHeader('Content-Disposition', 'attachment; filename="compressed.jpg"');
        return res.status(200).send(out);
      }

      case 'image-to-png': {
        if (!fileBase64) return res.status(400).json({ error: 'No image provided' });
        const out = await sharp(Buffer.from(fileBase64, 'base64')).rotate().png({ compressionLevel: 9 }).toBuffer();
        res.setHeader('Content-Type', 'image/png');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.png"');
        return res.status(200).send(out);
      }

      case 'image-to-jpg': {
        if (!fileBase64) return res.status(400).json({ error: 'No image provided' });
        const out = await sharp(Buffer.from(fileBase64, 'base64')).rotate().flatten({ background: '#ffffff' }).jpeg({ quality: 92 }).toBuffer();
        res.setHeader('Content-Type', 'image/jpeg');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.jpg"');
        return res.status(200).send(out);
      }

      case 'image-to-base64': {
        if (!fileBase64) return res.status(400).json({ error: 'No image provided' });
        return res.status(200).json({ result: `data:${mimeType || 'image/png'};base64,${fileBase64}` });
      }

      case 'image-to-pdf': {
        if (!fileBase64) return res.status(400).json({ error: 'No image provided' });
        const buffer = Buffer.from(fileBase64, 'base64');
        const pdfDoc = await PDFDocument.create();
        let img;
        try { img = await pdfDoc.embedJpg(buffer); } catch (e) { img = await pdfDoc.embedPng(buffer); }
        const page = pdfDoc.addPage([img.width, img.height]);
        page.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
        const pdfBytes = await pdfDoc.save();
        res.setHeader('Content-Type', 'application/pdf');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.pdf"');
        return res.status(200).send(Buffer.from(pdfBytes));
      }

      case 'heic-to-jpg': {
        if (!fileBase64) return res.status(400).json({ error: 'No image provided' });
        const jpgBuffer = await heicConvert({ buffer: Buffer.from(fileBase64, 'base64'), format: 'JPEG', quality: 0.92 });
        res.setHeader('Content-Type', 'image/jpeg');
        res.setHeader('Content-Disposition', 'attachment; filename="converted.jpg"');
        return res.status(200).send(Buffer.from(jpgBuffer));
      }

      // ============================= أدوات مطورين =============================
      case 'base64-tool': {
        let result;
        try {
          const decoded = Buffer.from(text, 'base64').toString('utf-8');
          const reEncoded = Buffer.from(decoded, 'utf-8').toString('base64');
          result = (reEncoded.replace(/=+$/, '') === text.trim().replace(/=+$/, '')) ? decoded : Buffer.from(text, 'utf-8').toString('base64');
        } catch (e) { result = Buffer.from(text, 'utf-8').toString('base64'); }
        return res.status(200).json({ result });
      }

      case 'url-encoder': {
        let result;
        try { const decoded = decodeURIComponent(text); result = (decoded !== text) ? decoded : encodeURIComponent(text); }
        catch (e) { result = encodeURIComponent(text); }
        return res.status(200).json({ result });
      }

      case 'json-beautifier': {
        return res.status(200).json({ result: JSON.stringify(JSON.parse(text), null, 4) });
      }

      case 'css-js-minifier': {
        let result = null;
        const looksLikeCss = /\{[^{}]*:[^{}]*;?[^{}]*\}/.test(text) && !/function|=>|const |let |var /.test(text);
        if (looksLikeCss && CleanCSS) { try { result = new CleanCSS({}).minify(text).styles; } catch (e) { /* fallthrough */ } }
        if (!result && terser) { try { const out = await terser.minify(text); if (out.code) result = out.code; } catch (e) { /* fallthrough */ } }
        if (!result) result = text.replace(/\/\*[\s\S]*?\*\/|\/\/.*/g, '').replace(/\s+/g, ' ').trim();
        return res.status(200).json({ result });
      }

      case 'html-entity': {
        const result = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        return res.status(200).json({ result });
      }

      case 'hash-generator': {
        const md5 = crypto.createHash('md5').update(text).digest('hex');
        const sha1 = crypto.createHash('sha1').update(text).digest('hex');
        const sha256 = crypto.createHash('sha256').update(text).digest('hex');
        const sha512 = crypto.createHash('sha512').update(text).digest('hex');
        return res.status(200).json({ result: `MD5: ${md5}\nSHA-1: ${sha1}\nSHA-256: ${sha256}\nSHA-512: ${sha512}` });
      }

      case 'timestamp-converter': {
        return res.status(200).json({ result: new Date(parseInt(text.trim(), 10) * 1000).toUTCString() });
      }

      case 'clean-text': {
        return res.status(200).json({ result: text.replace(/<[^>]*>?/gm, '').replace(/&nbsp;/g, ' ').trim() });
      }

      // ============================= أدوات عامة =============================
      case 'text-to-qr': {
        const dataUrl = await QRCode.toDataURL(text, { errorCorrectionLevel: 'H', width: 280, margin: 1 });
        return res.status(200).json({ resultImage: dataUrl });
      }

      case 'password-generator': {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=';
        return res.status(200).json({ result: secureRandomString(20, chars) });
      }

      case 'password-strength': {
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
      }

      case 'text-counter': {
        return res.status(200).json({ result: `Chars: ${text.length}\nWords: ${text.trim() ? text.trim().split(/\s+/).length : 0}\nLines: ${text.split('\n').length}` });
      }

      case 'percentage-calc': {
        const nums = text.match(/\d+(\.\d+)?/g);
        if (!nums || nums.length < 2) return res.status(200).json({ result: isArabic ? 'يرجى إدخال رقمين' : 'Please enter two numbers' });
        return res.status(200).json({ result: `${nums[0]}% of ${nums[1]} = ${(parseFloat(nums[0]) / 100) * parseFloat(nums[1])}` });
      }

      case 'byte-converter': {
        const bytes = parseFloat(text.replace(/[^0-9.]/g, ''));
        return res.status(200).json({ result: `Bytes: ${bytes}\nKB: ${(bytes / 1024).toFixed(2)}\nMB: ${(bytes / (1024 ** 2)).toFixed(2)}\nGB: ${(bytes / (1024 ** 3)).toFixed(4)}` });
      }

      case 'unit-converter': {
        const val = parseFloat(text.replace(/[^0-9.]/g, ''));
        return res.status(200).json({ result: `Meters: ${val} m\nFeet: ${(val * 3.28084).toFixed(2)} ft\nInches: ${(val * 39.3701).toFixed(2)} in\nMiles: ${(val / 1609.34).toFixed(4)} mi` });
      }

      case 'markdown-to-html': {
        return res.status(200).json({ result: marked.parse(text) });
      }

      case 'text-diff': {
        const lines = text.split('\n');
        const mid = Math.floor(lines.length / 2);
        const changes = diffLines(lines.slice(0, mid).join('\n'), lines.slice(mid).join('\n'));
        const result = changes.map(p => (p.added ? '+ ' : p.removed ? '- ' : '  ') + p.value.replace(/\n$/, '')).join('\n');
        return res.status(200).json({ result });
      }

      default:
        return res.status(400).json({ error: 'Unknown action: ' + action });
    }
  } catch (err) {
    console.error('convert.js error:', err);
    return res.status(500).json({ error: err.message });
  }
};
