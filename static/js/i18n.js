const TOOL_OPTIONS_EN = `
  <optgroup label="👩‍🏫 Teachers & Students (Word & PDF)">
    <option value="word-to-pdf" selected>Word (.docx/.doc) ➔ PDF</option>
    <option value="pdf-to-doc">PDF ➔ Word (.doc)</option>
    <option value="pdf-to-docx">PDF ➔ Word (.docx)</option>
    <option value="doc-to-docx">Word (.doc) ➔ Word (.docx)</option>
    <option value="csv-to-pdf">CSV ➔ PDF</option>
    <option value="pdf-to-excel">PDF ➔ Excel (.xlsx)</option>
    <option value="pdf-to-ppt">PDF ➔ PowerPoint (.pptx)</option>
    <option value="merge-pdf">Merge PDF Files</option>
    <option value="split-pdf">Split PDF into Pages (ZIP)</option>
  </optgroup>
  <optgroup label="📄 General Documents & PDF">
    <option value="pdf-to-text">PDF ➔ Extract Text</option>
    <option value="image-to-pdf">Image ➔ PDF</option>
    <option value="clean-text">Remove Formatting / HTML</option>
    <option value="text-diff">Text Compare (Diff)</option>
    <option value="markdown-to-html">Markdown ➔ HTML</option>
  </optgroup>
  <optgroup label="📊 Data & Spreadsheets">
    <option value="text-to-excel">Text/Table ➔ Excel (.xlsx)</option>
    <option value="excel-to-json">Excel (.xlsx) ➔ JSON</option>
    <option value="text-to-csv">Text/Table ➔ CSV</option>
    <option value="csv-to-json">CSV ➔ JSON</option>
    <option value="json-to-excel">JSON ➔ Excel</option>
    <option value="word-to-csv">Word ➔ CSV</option>
    <option value="csv-to-word">CSV ➔ Word</option>
  </optgroup>
  <optgroup label="🖼️ Images & Graphics Tools">
    <option value="compress-image">Compress Image Size (KB)</option>
    <option value="image-to-png">Image ➔ PNG</option>
    <option value="image-to-jpg">Image ➔ JPG</option>
    <option value="image-to-base64">Image ➔ Base64</option>
    <option value="heic-to-jpg">HEIC (iPhone) ➔ JPG</option>
  </optgroup>
  <optgroup label="💻 Web & Developer Tools">
    <option value="base64-tool">Base64 Encode / Decode</option>
    <option value="json-beautifier">JSON Beautifier / Format</option>
    <option value="hash-generator">Hash Generator (MD5 / SHA-256)</option>
    <option value="url-encoder">URL Encode / Decode</option>
    <option value="css-js-minifier">Minify CSS/JS</option>
    <option value="html-entity">HTML Entity Encode</option>
    <option value="timestamp-converter">Unix Timestamp ➔ Date</option>
  </optgroup>
  <optgroup label="🔧 Utilities">
    <option value="text-to-qr">Generate QR Code</option>
    <option value="password-generator">Generate Strong Password</option>
    <option value="password-strength">Check Password Strength</option>
    <option value="text-counter">Advanced Text Counter</option>
    <option value="text-to-speech">Text to Speech (Audio)</option>
    <option value="percentage-calc">Percentage Calculator</option>
    <option value="byte-converter">Byte / KB / MB Converter</option>
    <option value="unit-converter">Unit Converter (Meters/Feet)</option>
  </optgroup>
`;

const TOOL_OPTIONS_AR = `
  <optgroup label="👩‍🏫 أدوات المعلمين والطلاب">
    <option value="word-to-pdf" selected>تحويل وورد (.docx/.doc) إلى PDF</option>
    <option value="pdf-to-doc">تحويل PDF إلى وورد (.doc)</option>
    <option value="pdf-to-docx">تحويل PDF إلى وورد (.docx)</option>
    <option value="doc-to-docx">تحويل وورد قديم (.doc) إلى حديث (.docx)</option>
    <option value="csv-to-pdf">تحويل CSV إلى PDF</option>
    <option value="pdf-to-excel">تحويل PDF إلى إكسيل (.xlsx)</option>
    <option value="pdf-to-ppt">تحويل PDF إلى بوربوينت (.pptx)</option>
    <option value="merge-pdf">دمج عدة ملفات PDF</option>
    <option value="split-pdf">تقسيم PDF لصفحات (ZIP)</option>
  </optgroup>
  <optgroup label="📄 المستندات العامة والـ PDF">
    <option value="pdf-to-text">استخراج النصوص من PDF</option>
    <option value="image-to-pdf">تحويل صورة إلى PDF</option>
    <option value="clean-text">إزالة التنسيقات / HTML</option>
    <option value="text-diff">مقارنة النصوص (Diff)</option>
    <option value="markdown-to-html">تحويل Markdown إلى HTML</option>
  </optgroup>
  <optgroup label="📊 البيانات والجداول الإلكترونية">
    <option value="text-to-excel">تحويل نص/جدول إلى إكسيل (.xlsx)</option>
    <option value="excel-to-json">تحويل إكسيل (.xlsx) إلى JSON</option>
    <option value="text-to-csv">تحويل نص/جدول إلى CSV</option>
    <option value="csv-to-json">تحويل CSV إلى JSON</option>
    <option value="json-to-excel">تحويل JSON إلى إكسيل</option>
    <option value="word-to-csv">تحويل وورد إلى CSV</option>
    <option value="csv-to-word">تحويل CSV إلى وورد</option>
  </optgroup>
  <optgroup label="🖼️ أدوات الصور والرسومات">
    <option value="compress-image">ضغط حجم الصورة (KB)</option>
    <option value="image-to-png">تحويل صورة إلى PNG</option>
    <option value="image-to-jpg">تحويل صورة إلى JPG</option>
    <option value="image-to-base64">تحويل صورة إلى Base64</option>
    <option value="heic-to-jpg">تحويل HEIC (آيفون) إلى JPG</option>
  </optgroup>
  <optgroup label="💻 أدوات الويب والمطورين">
    <option value="base64-tool">ترميز / فك ترميز Base64</option>
    <option value="json-beautifier">تنسيق وترتيب JSON</option>
    <option value="hash-generator">مولد التشفير (MD5 / SHA-256)</option>
    <option value="url-encoder">تشفير الروابط (URL)</option>
    <option value="css-js-minifier">تصغير حجم CSS/JS</option>
    <option value="html-entity">تحويل نصوص HTML</option>
    <option value="timestamp-converter">تحويل وقت Unix إلى تاريخ</option>
  </optgroup>
  <optgroup label="🔧 أدوات عامة ومفيدة">
    <option value="text-to-qr">توليد باركود (QR Code)</option>
    <option value="password-generator">مولد كلمات مرور قوية</option>
    <option value="password-strength">فحص قوة كلمة المرور</option>
    <option value="text-counter">عداد الحروف والكلمات المفصل</option>
    <option value="text-to-speech">تحويل النص إلى صوت (نطق)</option>
    <option value="percentage-calc">حاسبة النسب المئوية</option>
    <option value="byte-converter">محول مساحات (Byte/KB/MB)</option>
    <option value="unit-converter">محول الأطوال والوحدات</option>
  </optgroup>
`;

const STRINGS = {
  en: {
    subtitle: 'The Infinite SaaS Conversion Suite',
    tool: 'What to do today?',
    content: 'Content',
    placeholder: 'Paste Text, Table, Links, or Code here...',
    result: 'Result:',
    chars: 'Chars',
    words: 'Words',
    uploadTitle: 'Drag & Drop file or click to upload',
    uploadSub: '(Supports Images, PDF, CSV, JSON, Word, TXT)',
    execute: 'Execute 🚀',
    themeToLight: '☀️ Light',
    themeToDark: '🌙 Dark',
    langToggle: '🌐 العربية',
    processingServer: '⏳ Processing on server',
    needFileOrText: 'Please upload a file or enter input first!',
    needTwoPdfs: 'Please upload at least 2 PDF files.',
    speaking: '🗣️ Speaking text...',
    needTextForSpeech: 'Please enter input first!',
    qrGenerated: '✅ QR Code Generated Below!',
    copy: 'Copy',
    copied: '✅ Copied to clipboard',
    clear: 'Clear',
  },
  ar: {
    subtitle: 'الأداة الشاملة لكل ما تحتاجه، بسرعة فائقة.',
    tool: 'ماذا تريد أن تفعل اليوم؟',
    content: 'المحتوى',
    placeholder: 'الصق النص أو الجدول أو الأكواد هنا...',
    result: 'النتيجة:',
    chars: 'الحروف',
    words: 'الكلمات',
    uploadTitle: 'اسحب الملف أو اضغط لرفع صورة/ملف',
    uploadSub: '(يدعم الصور، PDF، CSV، JSON، وورد، TXT)',
    execute: 'تنفيذ العملية 🚀',
    themeToLight: '☀️ فاتح',
    themeToDark: '🌙 داكن',
    langToggle: '🌐 English',
    processingServer: '⏳ جاري المعالجة بالسيرفر',
    needFileOrText: 'يرجى رفع ملف أو إدخال نص أولاً!',
    needTwoPdfs: 'يرجى رفع ملفين PDF على الأقل.',
    speaking: '🗣️ جاري النطق...',
    needTextForSpeech: 'يرجى إدخال نص أولاً!',
    qrGenerated: '✅ تم توليد الباركود بالأسفل!',
    copy: 'نسخ',
    copied: '✅ تم النسخ',
    clear: 'مسح',
  },
};

window.VInfinityI18n = { TOOL_OPTIONS_EN, TOOL_OPTIONS_AR, STRINGS };
