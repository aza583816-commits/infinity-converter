// =====================================================================================
// images.js — تحويلات الصور: ضغط / تحويل صيغ / HEIC / PDF
// =====================================================================================

const sharp = require('sharp');
const heicConvert = require('heic-convert');
const { PDFDocument } = require('pdf-lib');
const { badRequest } = require('./validation');

function sendFile(res, buffer, contentType, filename) {
  res.setHeader('Content-Type', contentType);
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  return res.status(200).send(buffer);
}

const handlers = {
  async 'compress-image'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No image provided');
    const out = await sharp(Buffer.from(fileBase64, 'base64'))
      .rotate()
      .resize({ width: 1600, withoutEnlargement: true })
      .jpeg({ quality: 70, mozjpeg: true })
      .toBuffer();
    return sendFile(res, out, 'image/jpeg', 'compressed.jpg');
  },

  async 'image-to-png'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No image provided');
    const out = await sharp(Buffer.from(fileBase64, 'base64')).rotate().png({ compressionLevel: 9 }).toBuffer();
    return sendFile(res, out, 'image/png', 'converted.png');
  },

  async 'image-to-jpg'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No image provided');
    const out = await sharp(Buffer.from(fileBase64, 'base64'))
      .rotate()
      .flatten({ background: '#ffffff' })
      .jpeg({ quality: 92 })
      .toBuffer();
    return sendFile(res, out, 'image/jpeg', 'converted.jpg');
  },

  async 'image-to-base64'({ res, fileBase64, mimeType }) {
    if (!fileBase64) return badRequest(res, 'No image provided');
    return res.status(200).json({ result: `data:${mimeType || 'image/png'};base64,${fileBase64}` });
  },

  async 'image-to-pdf'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No image provided');
    const buffer = Buffer.from(fileBase64, 'base64');
    const pdfDoc = await PDFDocument.create();
    let img;
    try {
      img = await pdfDoc.embedJpg(buffer);
    } catch (e) {
      img = await pdfDoc.embedPng(buffer);
    }
    const page = pdfDoc.addPage([img.width, img.height]);
    page.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
    const pdfBytes = await pdfDoc.save();
    return sendFile(res, Buffer.from(pdfBytes), 'application/pdf', 'converted.pdf');
  },

  async 'heic-to-jpg'({ res, fileBase64 }) {
    if (!fileBase64) return badRequest(res, 'No image provided');
    const jpgBuffer = await heicConvert({ buffer: Buffer.from(fileBase64, 'base64'), format: 'JPEG', quality: 0.92 });
    return sendFile(res, Buffer.from(jpgBuffer), 'image/jpeg', 'converted.jpg');
  },
};

module.exports = { handlers };
