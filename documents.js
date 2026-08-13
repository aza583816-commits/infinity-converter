// =====================================================================================
// documents.js — تحويلات المستندات: Word / PDF / Excel / PowerPoint
// =====================================================================================

const mammoth = require('mammoth');
const pdfParse = require('pdf-parse');
const pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell } = require('docx');
const { PDFDocument } = require('pdf-lib');
const XLSX = require('xlsx');
const PptxGenJS = require('pptxgenjs');
const JSZip = require('jszip');

const { htmlToPdfBuffer } = require('./browser');
const { escapeHtml, parseCsv, badRequest } = require('./validation');

function csvToHtmlTable(csv) {
  const rows = parseCsv(csv);
  return (
    '<table>' +
    rows
      .map(
        (row, ri) =>
          '<tr>' +
          row
            .map((c) => `<${ri === 0 ? 'th' : 'td'}>${escapeHtml((c || '').trim())}</${ri === 0 ? 'th' : 'td'}>`)
            .join('') +
          '</tr>'
      )
      .join('') +
    '</table>'
  );
}

async function buildDocxFromText(text, isArabic) {
  const paragraphs = (text || '').split('\n').map(
    (line) =>
      new Paragraph({
        bidirectional: isArabic,
        alignment: isArabic ? 'right' : 'left',
        children: [new TextRun({ text: line.length ? line : ' ', rightToLeft: isArabic })],
      })
  );
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
    pages.push(content.items.map((it) => ({ text: it.str, x: it.transform[4], y: it.transform[5] })));
  }
  return pages;
}

function itemsToRows(items) {
  const parts = items.filter((p) => p.text.trim().length > 0);
  parts.sort((a, b) => (Math.abs(a.y - b.y) > 7 ? b.y - a.y : a.x - b.x));
  const lines = [];
  let currentLine = [];
  let lastY = null;
  parts.forEach((p) => {
    if (lastY === null || Math.abs(lastY - p.y) <= 7) {
      currentLine.push(p);
      lastY = p.y;
    } else {
      lines.push(currentLine);
      currentLine = [p];
      lastY = p.y;
    }
  });
  if (currentLine.length) lines.push(currentLine);
  return lines.map((line) => {
    line.sort((a, b) => a.x - b.x);
    const cells = [];
    let currentCell = '';
    let prevEndX = null;
    line.forEach((it) => {
      if (prevEndX !== null && it.x - prevEndX > 15) {
        cells.push(currentCell.trim());
        currentCell = '';
      }
      currentCell += (currentCell ? ' ' : '') + it.text;
      prevEndX = it.x + it.text.length * 5;
    });
    if (currentCell) cells.push(currentCell.trim());
    return cells;
  });
}

function sendFile(res, buffer, contentType, filename) {
  res.setHeader('Content-Type', contentType);
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  return res.status(200).send(buffer);
}

const handlers = {
  async 'word-to-pdf'({ req, res, fileBase64, text, isArabic }) {
    let html;
    if (fileBase64) {
      const result = await mammoth.convertToHtml({ buffer: Buffer.from(fileBase64, 'base64') });
      html = result.value;
    } else {
      html = `<pre>${escapeHtml(text)}</pre>`;
    }
    const pdf = await htmlToPdfBuffer(html, isArabic);
    return sendFile(res, pdf, 'application/pdf', 'converted_document.pdf');
  },

  async 'csv-to-pdf'({ res, text, isArabic }) {
    const pdf = await htmlToPdfBuffer(csvToHtmlTable(text), isArabic);
    return sendFile(res, pdf, 'application/pdf', 'converted_table.pdf');
  },

  async 'pdf-to-text'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No file provided');
    const data = await pdfParse(Buffer.from(fileBase64, 'base64'));
    return res.status(200).json({ result: data.text.trim() });
  },

  async 'pdf-to-doc'({ res, text, isArabic }) {
    const buffer = await buildDocxFromText(text, isArabic);
    return sendFile(res, buffer, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'converted.doc');
  },

  async 'pdf-to-docx'({ res, text, isArabic }) {
    const buffer = await buildDocxFromText(text, isArabic);
    return sendFile(res, buffer, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'converted.docx');
  },

  async 'doc-to-docx'({ res, text, isArabic }) {
    const buffer = await buildDocxFromText(text, isArabic);
    return sendFile(res, buffer, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'converted.docx');
  },

  async 'pdf-to-excel'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No file provided');
    const pages = await extractPdfPagesWithPositions(Buffer.from(fileBase64, 'base64'));
    const wb = XLSX.utils.book_new();
    pages.forEach((items, idx) => {
      const ws = XLSX.utils.aoa_to_sheet(itemsToRows(items));
      XLSX.utils.book_append_sheet(wb, ws, `Page ${idx + 1}`);
    });
    const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
    return sendFile(res, buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'converted.xlsx');
  },

  async 'pdf-to-ppt'({ res, fileBase64, isArabic }) {
    if (!fileBase64) return badRequest(res, 'No file provided');
    const data = await pdfParse(Buffer.from(fileBase64, 'base64'));
    const pagesText = data.text.split('\f').filter((p) => p.trim().length > 0);
    const pptx = new PptxGenJS();
    (pagesText.length ? pagesText : [data.text]).forEach((pageText, idx) => {
      const slide = pptx.addSlide();
      slide.addText(`Page ${idx + 1}`, { x: 0.4, y: 0.3, fontSize: 20, bold: true, rtlMode: isArabic });
      slide.addText(pageText.trim().slice(0, 1800), {
        x: 0.4,
        y: 1.0,
        w: 9,
        h: 5,
        fontSize: 12,
        rtlMode: isArabic,
        align: isArabic ? 'right' : 'left',
      });
    });
    const buf = await pptx.write({ outputType: 'nodebuffer' });
    return sendFile(
      res,
      buf,
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'converted.pptx'
    );
  },

  async 'merge-pdf'({ res, fileBase64, filesBase64, isArabic }) {
    const files = filesBase64 || (fileBase64 ? [fileBase64] : []);
    if (files.length < 2) {
      return badRequest(
        res,
        isArabic ? 'يرجى رفع ملفين PDF على الأقل للدمج' : 'Please upload at least 2 PDF files to merge'
      );
    }
    const merged = await PDFDocument.create();
    for (const b64 of files) {
      const src = await PDFDocument.load(Buffer.from(b64, 'base64'));
      const copiedPages = await merged.copyPages(src, src.getPageIndices());
      copiedPages.forEach((p) => merged.addPage(p));
    }
    const bytes = await merged.save();
    return sendFile(res, Buffer.from(bytes), 'application/pdf', 'merged.pdf');
  },

  async 'split-pdf'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No file provided');
    const src = await PDFDocument.load(Buffer.from(fileBase64, 'base64'));
    const zip = new JSZip();
    for (let i = 0; i < src.getPageCount(); i++) {
      const single = await PDFDocument.create();
      const [copied] = await single.copyPages(src, [i]);
      single.addPage(copied);
      zip.file(`page_${i + 1}.pdf`, await single.save());
    }
    const zipBuf = await zip.generateAsync({ type: 'nodebuffer' });
    return sendFile(res, zipBuf, 'application/zip', 'split_pages.zip');
  },

  async 'csv-to-word'({ res, text, isArabic }) {
    const rows = parseCsv(text);
    const table = new Table({
      rows: rows.map(
        (row) =>
          new TableRow({
            children: row.map(
              (cell) =>
                new TableCell({
                  children: [
                    new Paragraph({
                      bidirectional: isArabic,
                      children: [new TextRun({ text: (cell || '').trim(), rightToLeft: isArabic })],
                    }),
                  ],
                })
            ),
          })
      ),
    });
    const doc = new Document({ sections: [{ children: [table] }] });
    const buf = await Packer.toBuffer(doc);
    return sendFile(res, buf, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'converted.docx');
  },
};

module.exports = { handlers, csvToHtmlTable, buildDocxFromText };
