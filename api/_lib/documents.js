  async 'word-to-pdf'({ req, res, fileBase64, text, isArabic }) {
    let html;
    if (fileBase64) {
      const result = await mammoth.convertToHtml({ buffer: Buffer.from(fileBase64, 'base64') });
      html = result.value;
    } else {
      html = `<pre>${escapeHtml(text)}</pre>`;
    }
    
    // استخدام محرك HTML نظيف وسريع يمنع التوقف المفاجئ
    const wrappedHtml = `<!DOCTYPE html>
    <html dir="${isArabic ? 'rtl' : 'ltr'}" lang="${isArabic ? 'ar' : 'en'}">
    <head><meta charset="utf-8"><style>
      body { font-family: Arial, sans-serif; padding: 20px; color: #000; direction: ${isArabic ? 'rtl' : 'ltr'}; text-align: ${isArabic ? 'right' : 'left'}; }
      table { width: 100%; border-collapse: collapse; margin-top: 15px; }
      th, td { border: 1px solid #333; padding: 8px; text-align: center; }
      th { background-color: #f2f2f2; }
    </style></head>
    <body>${html}</body></html>`;

    const pdf = await htmlToPdfBuffer(wrappedHtml, isArabic);
    return sendFile(res, pdf, 'application/pdf', 'converted_document.pdf');
  },
