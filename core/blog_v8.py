"""Infinity 8 knowledge clusters.

These guides are manually written, implementation-aware additions to the existing
bilingual Knowledge Center. They are installed before page blueprints import the
canonical blog registry.
"""
from __future__ import annotations

V8_BLOG_POSTS = [
    {
        "slug": "repair-pdf-before-converting",
        "title_ar": "متى تصلح PDF قبل ما تحوله؟",
        "title_en": "When should you repair a PDF before converting it?",
        "description_ar": "دليل عملي يوضح متى يفيد إصلاح بنية PDF قبل الضغط أو التحويل، ومتى لن يعالج الإصلاح محتوى مفقودًا أصلًا.",
        "description_en": "A practical guide to when structural PDF repair helps before compression or conversion, and what repair cannot recover.",
        "category_ar": "PDF",
        "category_en": "PDF",
        "minutes": 6,
        "tool": "/tools/pdf-repair",
        "tool_label_ar": "جرّب إصلاح PDF",
        "tool_label_en": "Try PDF Repair",
        "sections": [
            ("ابدأ بالإصلاح عندما يتصرف الملف بشكل غير طبيعي", "إذا كان PDF يفتح في برنامج ويرفضه برنامج آخر، أو يفشل التحويل رغم أن الصفحات تبدو موجودة، فقد تكون المشكلة في البنية الداخلية. إعادة كتابة الملف وتنظيف الكائنات الزائدة قد تجعل الحاوية أكثر اتساقًا قبل الخطوة التالية."),
            ("الإصلاح لا يعيد المحتوى المفقود", "إذا كانت صفحة ناقصة من المصدر أو stream تالفًا لدرجة لا يستطيع محرك PDF قراءته، فالإصلاح البنيوي لا يستطيع اختراع البيانات. احتفظ بالأصل وتعامل مع النسخة المصلحة كنسخة جديدة تحتاج مقارنة."),
            ("بعد الإصلاح اختبر أكثر من الشكل", "افتح أول صفحة ووسط الملف وآخره، ثم جرّب البحث وتحديد النص والروابط المهمة. نجاح الفتح وحده لا يثبت أن كل ميزة متقدمة بقيت كما كانت."),
            ("متى تضغط بعد الإصلاح؟", "إذا أصبح الملف سليمًا بصريًا ووظيفيًا، يمكن أن يكون الضغط خطوة تالية مفيدة للمشاركة. الأفضل أن تصلح أولًا ثم تضغط الناتج بدل محاولة ضغط ملف غير مستقر."),
        ],
        "section_en": [
            "Start with repair when the file behaves inconsistently",
            "Repair cannot recreate missing content",
            "Test more than appearance after repair",
            "When compression should come next",
        ],
        "paragraph_en": [
            "If a PDF opens in one application but fails in another, or conversion fails even though the pages look present, the internal structure may be messy. Rewriting the file and cleaning redundant objects can create a more consistent container before the next operation.",
            "If a page is already missing or a stream is damaged beyond what the PDF engine can read, structural repair cannot invent that data. Keep the original and treat the repaired output as a new copy that must be compared.",
            "Open the first, middle, and last pages, then test search, text selection, and any important links. A file opening successfully does not prove that every advanced document feature survived a structural rewrite.",
            "Once the repaired copy looks and behaves correctly, compression can be a useful sharing step. Repairing first and compressing the clean result is safer than trying to optimize a PDF that is already behaving unpredictably.",
        ],
    },
    {
        "slug": "searchable-pdf-vs-ocr-text",
        "title_ar": "PDF قابل للبحث أم ملف نص OCR؟ اختر الناتج المناسب",
        "title_en": "Searchable PDF or OCR text? Choose the right output",
        "description_ar": "افهم الفرق بين إضافة طبقة بحث داخل PDF وبين استخراج النص إلى TXT، وكيف تختار حسب هدفك الحقيقي.",
        "description_en": "Understand the difference between adding a searchable text layer to a PDF and exporting OCR text to TXT.",
        "category_ar": "OCR",
        "category_en": "OCR",
        "minutes": 6,
        "tool": "/tools/ocr-pdf-to-searchable",
        "tool_label_ar": "جرّب PDF قابل للبحث",
        "tool_label_en": "Try Searchable PDF OCR",
        "sections": [
            ("إذا يهمك شكل الصفحة فاختر PDF قابلًا للبحث", "المسار القابل للبحث يحافظ على صورة الصفحة كمرجع بصري ويضيف طبقة نص تساعد في البحث والنسخ. هذا مناسب للأرشفة والمستندات التي تريد أن تبقى مطابقة للمسح بصريًا."),
            ("إذا يهمك النص الخام فاختر استخراج OCR", "ملف TXT أخف وأسهل للنقل إلى محرر أو نظام آخر، لكنه لا يحافظ على أماكن العناصر أو شكل الصفحة. استخدمه عندما تكون الكلمات نفسها أهم من التصميم."),
            ("الاثنان يحتاجان مراجعة", "طبقة البحث وملف النص كلاهما ناتجان عن تعرف بصري احتمالي. راجع الأسماء والأرقام والتواريخ، ولا تعتبر نجاح البحث دليلًا على أن كل حرف صحيح."),
            ("اختبر صفحة صعبة قبل معالجة ملف طويل", "اختر صفحة فيها أرقام وخط صغير أو جدول. إذا كانت النتيجة مقبولة هناك، تكون لديك صورة أوضح عن جودة بقية المستند قبل تشغيل مئات الصفحات."),
        ],
        "section_en": [
            "Choose searchable PDF when page appearance matters",
            "Choose OCR text when raw words matter most",
            "Both outputs still need review",
            "Test a difficult page before a long run",
        ],
        "paragraph_en": [
            "A searchable-PDF workflow keeps the scanned page as the visual reference while adding a text layer for search and copying. That is useful for archives and documents that should continue to look like the original scan.",
            "A TXT export is lighter and easier to move into an editor or another system, but it does not preserve page layout or visual positioning. Use it when the words matter more than the original design.",
            "Both the searchable layer and a text export come from probabilistic optical recognition. Check names, numbers, and dates carefully; successful search does not prove that every recognized character is correct.",
            "Pick a page with small text, numbers, or a table and test it first. If recognition is acceptable on the difficult page, you have a better signal before committing to a long multi-page OCR job.",
        ],
    },
    {
        "slug": "remove-image-metadata-before-sharing",
        "title_ar": "هل تحذف بيانات الصورة الوصفية قبل المشاركة؟",
        "title_en": "Should you remove image metadata before sharing?",
        "description_ar": "متى تكون EXIF مفيدة، ومتى يفضل إنشاء نسخة مشاركة بدون بيانات وصفية شائعة مع الاحتفاظ بالأصل.",
        "description_en": "When EXIF is useful, when a metadata-clean sharing copy makes sense, and why the original should be kept.",
        "category_ar": "الخصوصية",
        "category_en": "Privacy",
        "minutes": 5,
        "tool": "/tools/image-strip-metadata",
        "tool_label_ar": "جرّب إزالة بيانات الصورة",
        "tool_label_en": "Try Remove Image Metadata",
        "sections": [
            ("البيانات الوصفية ليست دائمًا سيئة", "معلومات مثل وقت التصوير أو إعدادات الكاميرا قد تكون مفيدة للأرشفة والتصوير. لا تحذفها من النسخة الأصلية لمجرد أنها موجودة."),
            ("أنشئ نسخة مشاركة عندما لا تحتاج التفاصيل", "إذا كان هدفك إرسال صورة أو نشرها بدون الحاجة إلى EXIF، فالنسخة المنظفة تقلل البيانات المصاحبة غير الضرورية. هذا مفيد خصوصًا عندما تريد مشاركة المحتوى نفسه فقط."),
            ("الإزالة ليست ضمان إخفاء كل معلومة", "قد تكون معلومات حساسة ظاهرة داخل البكسلات نفسها مثل لوحة أو اسم أو مستند في الخلفية. تنظيف metadata لا يطمس ما يظهر بصريًا."),
            ("راجع الجودة والصيغة بعد التنظيف", "بعض مسارات إزالة البيانات تعيد ترميز الصورة. افتح الناتج وقارن الأبعاد والخلفية والشفافية عند الحاجة، واحتفظ بالأصل للأرشفة."),
        ],
        "section_en": [
            "Metadata is not always bad",
            "Create a sharing copy when details are unnecessary",
            "Metadata removal does not hide visible information",
            "Check quality and format after cleaning",
        ],
        "paragraph_en": [
            "Information such as capture time or camera settings can be useful for photography and archiving. Do not erase useful metadata from your only original just because it exists.",
            "If the goal is simply to send or publish an image and you do not need EXIF, a cleaned sharing copy can reduce unnecessary attached information. The content remains the focus instead of the capture details.",
            "Sensitive information may be visible in the pixels themselves, such as a badge, document, address, or screen in the background. Removing metadata does not redact anything that can be seen in the image.",
            "Some metadata-cleaning workflows re-encode the image. Open the result and check dimensions, background, and transparency when those matter, while retaining the original as the archival copy.",
        ],
    },
    {
        "slug": "xlsx-to-csv-without-surprises",
        "title_ar": "Excel إلى CSV بدون مفاجآت: وش الذي يبقى ووش الذي يختفي؟",
        "title_en": "Excel to CSV without surprises: what stays and what disappears?",
        "description_ar": "فهم الفرق بين Workbook وCSV قبل التصدير، خصوصًا الأوراق المتعددة والصيغ والتنسيق.",
        "description_en": "Understand what a CSV keeps and loses compared with an Excel workbook, especially sheets, formulas, and formatting.",
        "category_ar": "البيانات",
        "category_en": "Data",
        "minutes": 6,
        "tool": "/tools/xlsx-to-csv",
        "tool_label_ar": "جرّب Excel إلى CSV",
        "tool_label_en": "Try XLSX to CSV",
        "sections": [
            ("CSV جدول مسطح وليس Workbook", "ملف Excel يستطيع حمل أوراق متعددة وتنسيقات ومخططات، بينما CSV يمثل صفوفًا وأعمدة نصية في جدول واحد. لذلك لا تتوقع أن تنتقل كل خصائص المصنف."),
            ("راجع الورقة التي تريد تصديرها", "إذا كان الملف يحتوي أكثر من Sheet، تأكد من سياسة الأداة أو المصدر الذي تريد أخذه. التصدير الخاطئ لورقة غير مقصودة قد ينتج ملفًا صحيحًا تقنيًا لكنه غير مفيد."),
            ("انتبه للصيغ والقيم المعروضة", "في سير البيانات يهمك غالبًا الناتج أو القيمة أكثر من شكل الصيغة داخل Excel. افتح CSV الناتج وتأكد من الأعمدة المهمة والأرقام والتواريخ بدل الاعتماد على أن الملف تم تنزيله فقط."),
            ("اختبر الترميز مع العربية", "UTF-8 هو الخيار المناسب لمعظم التدفقات الحديثة. افتح عينة تحتوي عربيًا وإنجليزيًا في البرنامج الذي سيستهلك CSV وتأكد أن الحروف والفواصل تظهر بشكل صحيح."),
        ],
        "section_en": [
            "CSV is a flat table, not a workbook",
            "Check which sheet you intend to export",
            "Pay attention to formulas and displayed values",
            "Test encoding with Arabic text",
        ],
        "paragraph_en": [
            "An Excel workbook can contain multiple sheets, formatting, charts, and richer cell behavior. CSV represents rows and columns in one flat table, so it cannot preserve every workbook feature.",
            "If the file has multiple sheets, confirm which sheet the workflow exports or which source you intend to use. Exporting the wrong sheet can produce a technically valid file that is still useless for your task.",
            "For data exchange, the resulting value is often more important than how a formula looked inside Excel. Open the CSV and check key columns, numbers, and dates rather than assuming a completed download means the data is correct.",
            "UTF-8 is the practical default for modern workflows. Test a sample containing both Arabic and English in the application that will consume the CSV so you can confirm characters and delimiters are interpreted correctly.",
        ],
    },
    {
        "slug": "csv-to-json-for-apis",
        "title_ar": "متى تحول CSV إلى JSON قبل استخدام البيانات في API؟",
        "title_en": "When should you turn CSV into JSON for an API?",
        "description_ar": "دليل للمطورين يشرح متى يكون JSON أسهل للأنظمة، وما الذي يجب التحقق منه في أسماء الأعمدة والأنواع.",
        "description_en": "A developer-focused guide to when JSON is easier for systems and what to verify in headers and value types.",
        "category_ar": "المطورون",
        "category_en": "Developers",
        "minutes": 6,
        "tool": "/tools/csv-to-json",
        "tool_label_ar": "جرّب CSV إلى JSON",
        "tool_label_en": "Try CSV to JSON",
        "sections": [
            ("JSON أوضح عندما تتعامل مع كائنات", "إذا كان كل صف يمثل سجلًا له حقول معروفة، يمكن أن يكون JSON أسهل للقراءة من تطبيقات الويب والـAPIs. أسماء الأعمدة تتحول عادة إلى مفاتيح، لذلك جودة header مهمة."),
            ("النص لا يتحول تلقائيًا إلى نوع مثالي دائمًا", "القيمة 00123 قد تكون رقمًا أو معرفًا يجب أن يحتفظ بالأصفار. راجع الحقول التي تبدو رقمية قبل أن تبني عليها منطقًا يفترض نوع بيانات معينًا."),
            ("نظف أسماء الأعمدة قبل التكامل", "العناوين المكررة أو الفارغة أو التي تحتوي مسافات غريبة تسبب ارتباكًا في الأنظمة اللاحقة. اجعل أسماء الحقول واضحة وثابتة قبل نشر تنسيق تعتمد عليه تطبيقات أخرى."),
            ("تحقق بعينة صغيرة أولًا", "حوّل عشرة صفوف وافحص JSON يدويًا أو عبر parser قبل معالجة ملف ضخم. ستكتشف مشاكل الفواصل والاقتباسات والعناوين أسرع بكثير."),
        ],
        "section_en": [
            "JSON is clearer when rows represent objects",
            "Text values do not always become ideal types automatically",
            "Clean headers before integration",
            "Validate a small sample first",
        ],
        "paragraph_en": [
            "When each CSV row represents a record with known fields, JSON can be easier for web applications and APIs to consume. Column headers commonly become keys, so header quality matters.",
            "A value such as 00123 might be a number or an identifier that must preserve leading zeros. Review fields that look numeric before building application logic that assumes a specific data type.",
            "Duplicate, empty, or strangely spaced headers create ambiguity downstream. Use clear and stable field names before publishing a data shape that other applications will depend on.",
            "Convert a small set of rows and inspect the JSON manually or with a parser before processing a very large file. Delimiter, quoting, and header problems become much easier to spot early.",
        ],
    },
    {
        "slug": "favicon-pack-from-one-image",
        "title_ar": "كيف تجهز Favicon من صورة واحدة بدون ما يطلع مشوش؟",
        "title_en": "How to build a favicon pack from one image without blurry results",
        "description_ar": "نصائح لاختيار صورة المصدر، تبسيط التفاصيل، وفحص المقاسات الصغيرة قبل استخدام حزمة الأيقونات.",
        "description_en": "Tips for source artwork, simplifying detail, and checking tiny sizes before using a generated favicon pack.",
        "category_ar": "الصور",
        "category_en": "Images",
        "minutes": 5,
        "tool": "/tools/image-favicon-pack",
        "tool_label_ar": "جرّب حزمة Favicon",
        "tool_label_en": "Try Favicon Pack",
        "sections": [
            ("ابدأ بصورة مربعة وواضحة", "الأيقونة الصغيرة لا تتحمل تفاصيل كثيرة. استخدم شعارًا أو رمزًا يمكن فهمه حتى عند تصغيره، وابتعد عن نص طويل أو عناصر دقيقة جدًا."),
            ("الشفافية والحواف تحتاج فحصًا", "إذا كان المصدر يحتوي خلفية شفافة، افتح الأيقونات على خلفيات فاتحة وداكنة. قد تكون حافة جميلة على لون واحد ضعيفة على لون آخر."),
            ("لا تحكم من 512 بكسل فقط", "المشكلة الحقيقية تظهر عند 16 و32 بكسل. افتح المقاسات الصغيرة نفسها وتأكد أن الشكل ما زال واضحًا بدل الاعتماد على معاينة كبيرة."),
            ("اختبر الحزمة داخل المتصفح", "بعد إضافة الملفات للموقع امسح cache أو استخدم نافذة خاصة عند الحاجة، لأن favicons تُخزن مؤقتًا بقوة وقد تظن أن الملف الجديد لم يعمل."),
        ],
        "section_en": [
            "Start with clear square artwork",
            "Check transparency and edges",
            "Do not judge only at 512 pixels",
            "Test the pack in a real browser",
        ],
        "paragraph_en": [
            "Tiny icons cannot carry much detail. Use a mark or logo that remains understandable when reduced and avoid long text or very fine elements.",
            "If the source uses transparency, view the generated icons against both light and dark backgrounds. An edge that looks good on one color can disappear on another.",
            "The real challenge appears at 16 and 32 pixels. Inspect those actual sizes instead of judging only from a large preview where every detail still looks sharp.",
            "After installing the favicon files on a site, clear relevant cache or use a private window when testing. Browsers cache favicons aggressively, which can make a correct new file appear unchanged.",
        ],
    },
    {
        "slug": "reorder-and-number-pdf-pages",
        "title_ar": "إعادة ترتيب صفحات PDF ثم ترقيمها: أي خطوة أول؟",
        "title_en": "Reorder PDF pages, then number them: which step comes first?",
        "description_ar": "مسار بسيط يمنع أرقام الصفحات من أن تصبح غير منطقية بعد إعادة الترتيب أو حذف صفحات.",
        "description_en": "A simple workflow that keeps page numbers logical after rearranging or removing pages.",
        "category_ar": "PDF",
        "category_en": "PDF",
        "minutes": 5,
        "tool": "/tools/pdf-reorder-pages",
        "tool_label_ar": "جرّب إعادة ترتيب PDF",
        "tool_label_en": "Try Reorder PDF Pages",
        "sections": [
            ("رتب المحتوى قبل إضافة الأرقام", "إذا رقمت الصفحات أولًا ثم غيرت ترتيبها، ستنتقل الأرقام القديمة مع الصفحات وقد لا تعكس التسلسل الجديد. اجعل ترتيب المستند نهائيًا أولًا."),
            ("راجع الصفحات التي لها ترقيم مطبوع أصلًا", "قد يحتوي المصدر أرقامًا داخل التصميم نفسه. إضافة أرقام جديدة فوقها قد تربك القارئ، لذلك افحص الهامش العلوي والسفلي قبل الترقيم."),
            ("افحص البداية والنهاية ونقطة التغيير", "بعد إعادة الترتيب افتح الصفحة الأولى والأخيرة والصفحات حول أي نقل مهم. بعدها أضف الترقيم وافحص الموضع على صفحة مزدحمة."),
            ("احتفظ بنسخة قبل التعديل", "عمليات الترتيب والترقيم تنتج نسخًا جديدة، وهذا جيد. لا تحذف الأصل حتى تتأكد أن التسلسل والمراجع الداخلية ما زالت منطقية."),
        ],
        "section_en": [
            "Finalize order before adding numbers",
            "Check for numbers already printed in the design",
            "Inspect the beginning, end, and moved boundaries",
            "Keep a copy before editing",
        ],
        "paragraph_en": [
            "If you add page numbers first and rearrange pages later, those old numbers move with the pages and may no longer match the new sequence. Finalize document order first.",
            "A source PDF may already contain numbers as part of the page design. Adding a second numbering layer can confuse readers, so inspect the top and bottom margins before applying new numbers.",
            "After reordering, open the first and last pages plus the pages around every important move. Then add numbering and check its position on a visually busy page.",
            "Reordering and numbering produce new copies, which is useful. Keep the original until you have verified the new sequence and any internal references that depend on page numbers.",
        ],
    },
    {
        "slug": "safe-multi-step-file-workflows",
        "title_ar": "ليش كل خطوة في مسار الملفات لازم تعيد التحقق من الناتج؟",
        "title_en": "Why should every step in a file workflow re-validate its input?",
        "description_ar": "شرح مبسط لفكرة المسارات المتعددة ولماذا لا يجب أن تثق الخطوة التالية تلقائيًا في ملف أنتجته الخطوة السابقة.",
        "description_en": "A plain-language explanation of multi-step file workflows and why each handoff should be validated again.",
        "category_ar": "الأمان",
        "category_en": "Security",
        "minutes": 7,
        "tool": "/tools",
        "tool_label_ar": "افتح مسارات Infinity",
        "tool_label_en": "Open Infinity Workflows",
        "sections": [
            ("الناتج الوسيط يصبح إدخالًا جديدًا", "إذا حوّلت Word إلى PDF ثم ضغطته، ملف PDF الناتج من الخطوة الأولى هو إدخال الخطوة الثانية. لذلك يجب أن يمر بفحص النوع والبنية كما لو أنه ملف جديد."),
            ("التوافق يمنع المسارات غير المنطقية", "ليس كل ناتج مناسبًا لكل أداة. معرفة امتداد ونوع الناتج تسمح ببناء سلسلة يمكن تنفيذها بدل قائمة أدوات تبدو ذكية لكنها لا تتصل ببعضها فعليًا."),
            ("المساحة المؤقتة تقلل البقايا", "كل خطوة تحتاج ملفات عمل مؤقتة. تنظيف المساحة السابقة بعد استلام الخطوة التالية للناتج يقلل مدة بقاء الملفات ويجعل حدود المعالجة أوضح."),
            ("الذكاء يقترح والخادم يتحقق", "حتى إذا اقترح AI مسارًا مناسبًا، التنفيذ الحقيقي يجب أن يتحقق من الأدوات والحدود والتوافق مرة ثانية على الخادم. الاقتراح ليس تصريحًا بتجاوز قواعد الأمان."),
        ],
        "section_en": [
            "An intermediate output becomes a new input",
            "Compatibility prevents impossible chains",
            "Temporary workspaces reduce leftovers",
            "AI can suggest; the server still verifies",
        ],
        "paragraph_en": [
            "If you convert Word to PDF and then compress it, the PDF created by the first step becomes the second step's input. It should therefore pass type and structural validation as if it were a new file.",
            "Not every output belongs in every tool. Knowing the output type lets the system build a chain that can actually execute instead of presenting a clever-looking list of unrelated actions.",
            "Each step needs temporary working files. Cleaning the previous workspace after the next step safely receives the artifact reduces how long files remain and makes processing boundaries easier to reason about.",
            "Even when AI proposes a sensible path, real execution should validate tools, limits, and compatibility again on the server. A recommendation is never permission to bypass security rules.",
        ],
    },
    {
        "slug": "browser-local-tools-and-privacy",
        "title_ar": "متى تكون الأداة التي تعمل داخل المتصفح أفضل للخصوصية؟",
        "title_en": "When is a browser-local tool better for privacy?",
        "description_ar": "فرق عملي بين الأدوات التي تحسب أو تنظف البيانات محليًا في المتصفح وبين مهام الملفات التي تحتاج معالجة خادمية.",
        "description_en": "A practical distinction between tools that can work locally in the browser and file tasks that require server-side processing.",
        "category_ar": "الخصوصية",
        "category_en": "Privacy",
        "minutes": 6,
        "tool": "/tools",
        "tool_label_ar": "تصفح الأدوات المحلية",
        "tool_label_en": "Browse Local Tools",
        "sections": [
            ("بعض المهام لا تحتاج رفع ملف أصلًا", "تحويل حالة نص، حساب نسبة، تحليل URL أو تنظيف قائمة يمكن أن يتم داخل المتصفح. عندما لا توجد حاجة لمعالجة خادمية، إبقاء البيانات على الجهاز يبسط نموذج الخصوصية."),
            ("المعالجة المحلية لها حدود", "OCR وLibreOffice وتحويلات PDF الثقيلة تحتاج محركات لا يوفرها كل متصفح بشكل مناسب. عندها تصبح المعالجة الخادمية المؤقتة خيارًا عمليًا مع حدود واضحة."),
            ("لا تخلط نتيجة متصفح مع ملف خادمي تلقائيًا", "الأداة المحلية قد تنتج نصًا أو رقمًا في الواجهة وليس ملفًا محفوظًا. المسار الجيد لا يدعي أن هذه النتيجة انتقلت تلقائيًا إلى محول ملفات إذا لم يحدث ذلك فعلًا."),
            ("اختر أبسط مكان ينفذ المهمة", "إذا كان المتصفح يكفي فالمحلي ممتاز. وإذا احتجت محرك مستندات أو OCR، استخدم خدمة تشرح أين تتم المعالجة ومدة بقاء الملفات وما الذي يرسل للذكاء الاصطناعي."),
        ],
        "section_en": [
            "Some tasks do not need an upload at all",
            "Local processing has practical limits",
            "Do not pretend a browser result is automatically a server file",
            "Use the simplest place that can do the job",
        ],
        "paragraph_en": [
            "Changing text case, calculating a percentage, parsing a URL, or cleaning a list can happen entirely in the browser. When server processing is unnecessary, keeping the data on the device makes the privacy model simpler.",
            "OCR, LibreOffice rendering, and heavy PDF conversion depend on engines that are not practical in every browser. Temporary server processing can then be a sensible option when its limits and behavior are clearly explained.",
            "A local utility may produce text or a number in the interface rather than a saved file. A trustworthy workflow should not pretend that result automatically became input to a server file converter when no such handoff occurred.",
            "If the browser is enough, local execution is a strong choice. If a document engine or OCR is required, use a service that explains where processing happens, how long files remain, and what—if anything—is sent to an AI provider.",
        ],
    },
]


_V8_DEPTH = {
    "repair-pdf-before-converting": {
        "ar": [
            ("قارن النسختين بمؤشرات واضحة", "لا تكتفِ بانطباع عام بعد الإصلاح. قارن عدد الصفحات، حجم الملف، قابلية البحث، الروابط، الصور، وأي حقول أو تعليقات مهمة بين الأصل والناتج. إذا كان المستند رسميًا أو أكاديميًا، افتح صفحات متباعدة بدل فحص أول صفحتين فقط، وسجل أي اختلاف قبل أن تعتمد النسخة الجديدة أو ترسلها لشخص آخر."),
            ("لا تجعل الإصلاح خطوة تلقائية لكل PDF", "الملف السليم لا يحتاج بالضرورة إلى إعادة كتابة قبل كل تحويل. كل معالجة إضافية تعني تغييرًا جديدًا يجب مراجعته. استخدم الإصلاح عندما توجد علامة فعلية مثل فشل القراءة أو أخطاء بنيوية أو اختلاف بين البرامج، ثم انتقل إلى التحويل أو الضغط بعد التحقق من النسخة الناتجة."),
        ],
        "en": [
            ("Compare the original and repaired copies with concrete checks", "Do not rely on a general visual impression after repair. Compare page count, file size, search behavior, links, images, and any important annotations or form fields between the source and the new copy. For academic, legal, or operational documents, inspect pages from the beginning, middle, and end and record any meaningful difference before treating the repaired file as the new working version."),
            ("Do not make repair an automatic step for every PDF", "A healthy PDF does not need to be rewritten before every conversion. Each extra processing step creates another output that should be verified, and unnecessary rewriting can remove or normalize features you actually wanted to keep. Use repair when there is evidence of structural trouble, then proceed to compression or conversion only after the repaired copy passes the checks that matter for your task."),
        ],
    },
    "searchable-pdf-vs-ocr-text": {
        "ar": [
            ("حدد كيف ستستخدم الناتج بعد OCR", "إذا كان الهدف أرشفة مستند ممسوح والرجوع إلى شكله الأصلي، فطبقة البحث داخل PDF عادة أوضح. أما إذا كنت ستنقل النص إلى محرر أو نظام بحث أو قاعدة بيانات، فقد يكون TXT أبسط. القرار الصحيح يعتمد على الخطوة التالية، وليس على اسم الصيغة وحده."),
            ("قيّم الدقة على محتوى يشبه ملفك الحقيقي", "جودة OCR تتأثر باللغة والدقة والميلان والجداول وجودة المسح. اختبر أسماء وأرقامًا وعناوين من ملفك نفسه، ثم قارن النص بصريًا. إذا كانت الأخطاء كثيرة، حسّن المصدر أو قسم المهمة بدل إنتاج مئات الصفحات ثم اكتشاف أن الناتج يحتاج مراجعة شاملة."),
        ],
        "en": [
            ("Choose the output based on what happens after OCR", "If the purpose is archiving a scanned document while preserving its original visual appearance, a searchable PDF is usually the clearer choice. If the next step is editing, indexing, importing into another system, or running text analysis, plain OCR text may be simpler. The right answer depends on the downstream task, not on which format sounds more advanced."),
            ("Measure recognition quality on content that resembles the real document", "OCR accuracy changes with language, resolution, skew, tables, handwriting, and scan quality. Test names, dates, numbers, and dense paragraphs from the actual material and compare the recognized text with the page image. When errors are frequent, improve the source or split the workflow before processing hundreds of pages that would later require expensive manual review."),
        ],
    },
    "remove-image-metadata-before-sharing": {
        "ar": [
            ("افصل بين نسخة الأرشيف ونسخة المشاركة", "أفضل ممارسة بسيطة هي الاحتفاظ بالأصل كما هو وإنشاء نسخة مخصصة للنشر أو الإرسال. بهذه الطريقة لا تخسر تاريخًا أو إعدادات قد تحتاجها لاحقًا، وفي الوقت نفسه تقلل البيانات غير الضرورية في النسخة التي تخرج خارج جهازك أو فريقك."),
            ("افحص أكثر من EXIF عند الحساسية العالية", "الخصوصية لا تتوقف على metadata. اسم الملف، محتوى الصورة المرئي، النصوص الموجودة داخل لقطة الشاشة، والمعلومات في الخلفية قد تكشف أكثر من إعدادات الكاميرا. قبل مشاركة مادة حساسة، راجع الصورة بصريًا وغيّر الاسم عند الحاجة بدل الاعتماد على إزالة EXIF وحدها."),
        ],
        "en": [
            ("Separate the archival original from the sharing copy", "A practical pattern is to keep the original image intact and create a dedicated copy for publishing or sending. That preserves capture history and technical information that may still be useful later while reducing unnecessary metadata in the version that leaves your device or organization. It also makes it easier to verify that privacy cleaning did not become an irreversible edit to your only source file."),
            ("Look beyond EXIF when the image is sensitive", "Privacy is not limited to metadata. The filename, visible text in a screenshot, a badge in the background, location details inside the pixels, or an embedded document can reveal more than camera settings do. Before sharing sensitive material, review the image visually and rename the sharing copy when appropriate instead of treating EXIF removal as a complete redaction or anonymization process."),
        ],
    },
    "xlsx-to-csv-without-surprises": {
        "ar": [
            ("اختبر الأرقام والتواريخ والقيم الفارغة", "CSV لا يحمل تعريفات أنواع غنية مثل المصنف. بعض البرامج قد تفسر التاريخ أو الفاصلة العشرية أو الأصفار في بداية المعرف بطريقة مختلفة. افتح الناتج في البرنامج الذي سيستهلكه فعلًا، وراجع أعمدة حساسة مثل الأكواد والتواريخ والمبالغ قبل الاعتماد على الملف."),
            ("احتفظ بالمصنف كمصدر مرجعي", "إذا كان Excel يحتوي صيغًا أو أوراقًا متعددة أو تنسيقًا مهمًا، لا تجعل CSV النسخة الوحيدة. استخدمه كصيغة تبادل بيانات، واحتفظ بالمصنف للمراجعة والرجوع إلى السياق الأصلي. هذا يفصل بين ملف التشغيل البسيط وملف المصدر الغني بالمعلومات."),
        ],
        "en": [
            ("Test numbers, dates, leading zeros, and empty values", "CSV does not carry the rich type definitions of a workbook, so receiving software may interpret dates, decimal separators, empty cells, or identifiers with leading zeros differently. Open the exported file in the application that will actually consume it and inspect sensitive columns such as account codes, dates, quantities, and currency before assuming that a technically valid CSV preserved the intended meaning."),
            ("Keep the workbook as the reference source", "If the Excel file contains formulas, multiple sheets, charts, comments, or formatting that explains the data, do not let the CSV become the only copy. Treat CSV as an exchange format and retain the workbook for context and verification. This separation gives downstream systems a simple table while preserving a richer source that can resolve questions when a row or value later looks ambiguous."),
        ],
    },
    "csv-to-json-for-apis": {
        "ar": [
            ("حدد بنية JSON التي يحتاجها المستهلك", "تحويل كل صف إلى object مناسب في حالات كثيرة، لكنه ليس الشكل الوحيد الممكن. بعض APIs تتوقع حقولًا متداخلة أو أسماء محددة أو مصفوفات داخل السجل. راجع العقد أو schema أولًا، ثم تأكد أن الناتج يطابق البنية المطلوبة بدل إرسال JSON صحيح نحويًا لكنه غير متوافق."),
            ("تحقق من القيم الخاصة قبل الإرسال", "الفراغ وnull وtrue وfalse والأرقام الكبيرة قد تحتاج معالجة واضحة. لا تفترض أن كل نص يجب تحويله تلقائيًا إلى رقم أو boolean. اختبر عينة تحتوي الحالات الطرفية، ثم مرر الناتج عبر validator أو بيئة تجريبية قبل استخدامه في تكامل إنتاجي."),
        ],
        "en": [
            ("Match the JSON shape to the consumer's contract", "Turning every row into one flat object is useful in many cases, but it is not the only valid JSON structure. An API may require nested objects, specific property names, arrays, or a wrapper object around the records. Read the receiving schema first and verify that the generated output matches that contract instead of sending JSON that is syntactically valid but structurally incompatible."),
            ("Handle special values deliberately before sending data", "Blank cells, nulls, booleans, very large numbers, and identifiers can all be misinterpreted if conversion relies on automatic guessing. Do not assume every numeric-looking string should become a number. Build a sample containing edge cases, validate the resulting JSON with the target schema or a staging endpoint, and only then scale the process to the full dataset used by production systems."),
        ],
    },
    "favicon-pack-from-one-image": {
        "ar": [
            ("بسّط الرمز قبل تصغيره", "إذا كان الشعار يحتوي ظلالًا دقيقة أو نصًا صغيرًا أو أكثر من عنصر، أنشئ نسخة مبسطة للأيقونة بدل استخدام نفس التصميم حرفيًا. الهدف أن يظل الرمز مميزًا عند المقاسات الصغيرة، وليس أن يحمل كل تفاصيل الهوية الموجودة في النسخة الكبيرة."),
            ("تحقق من HTML والـmanifest بعد إنشاء الملفات", "نجاح توليد الصور لا يعني أن المتصفح سيستخدمها تلقائيًا. راجع روابط icon وapple-touch-icon وmanifest، وتأكد أن المسارات والمقاسات تطابق الملفات الفعلية. بعدها اختبر تبويب المتصفح، الاختصار على الهاتف، وأي وضع PWA تستخدمه."),
        ],
        "en": [
            ("Simplify the mark before shrinking it", "If the source logo contains fine shadows, tiny lettering, gradients, or several competing elements, create a simplified icon version instead of scaling the full brand artwork literally. The goal is recognizability at tiny sizes, not preservation of every detail that works on a large banner. A deliberate small-size mark usually looks sharper and more intentional than an automatically reduced complex logo."),
            ("Verify the HTML and manifest references after generation", "Generating the image files is only part of the job. Check the favicon, apple-touch-icon, and web-app manifest references and make sure paths and declared sizes match the files you actually deployed. Then test a normal browser tab, a mobile home-screen shortcut, and any installed PWA experience you support, because each surface may select a different icon from the generated pack."),
        ],
    },
    "reorder-and-number-pdf-pages": {
        "ar": [
            ("راجع الروابط والفهارس بعد تغيير الترتيب", "إذا كان المستند يحتوي فهرسًا أو إشارات مثل راجع الصفحة 12، فإن إعادة الترتيب قد تجعل هذه المراجع قديمة حتى لو أضفت أرقامًا جديدة بصريًا. افحص الروابط الداخلية والمراجع المهمة، وحدّث المحتوى المصدر إذا كانت الأرقام جزءًا من النص نفسه."),
            ("اختر موضع الترقيم على صفحات مختلفة", "جرّب الرقم على صفحة نصية وصفحة تحتوي صورة أو تذييلًا مزدحمًا. الموضع المناسب في صفحة قد يغطي عنصرًا في أخرى. بعد اختيار المكان، مر سريعًا على عدة صفحات وتأكد أن الرقم واضح ولا يتداخل مع المحتوى أو علامات الطباعة."),
        ],
        "en": [
            ("Recheck links, tables of contents, and written page references", "If the document contains a table of contents, internal links, or text such as 'see page 12,' reordering can make those references stale even after you add a fresh visible page number. Inspect important navigation and update the source document when the page number is part of the written content itself. A visually correct footer number does not automatically repair semantic references inside the document."),
            ("Test numbering position on different page designs", "Place the number on a text-heavy page, an image-heavy page, and a page with a busy header or footer before applying the choice to the whole document. A position that looks clean on one page may cover content on another. After numbering, scan several pages at normal viewing size and confirm that the number remains legible without interfering with text, crop marks, or existing footer elements."),
        ],
    },
    "safe-multi-step-file-workflows": {
        "ar": [
            ("اجعل الفشل واضحًا وقابلًا لإعادة المحاولة", "المسار الجيد لا يخفي الخطوة التي فشلت. يجب أن يعرف المستخدم هل المشكلة في التحقق أو التحويل أو الناتج، وأن يتمكن من إعادة المحاولة بدون افتراض أن الخطوات السابقة نجحت بشكل سليم. الوضوح هنا مهم للثقة بقدر أهمية نجاح المسار نفسه."),
            ("لا تجعل الأتمتة تلغي المراجعة النهائية", "حتى المسار المتحقق تقنيًا قد ينتج ملفًا يحتاج فحصًا بصريًا أو وظيفيًا. افتح الناتج النهائي، قارن الحجم وعدد الصفحات أو قابلية البحث حسب المهمة، واحتفظ بالأصل عندما تكون النتيجة مهمة. الأتمتة تقلل العمل اليدوي لكنها لا تلغي التحقق المناسب."),
        ],
        "en": [
            ("Make failures visible and retryable", "A trustworthy workflow should not hide which stage failed. The user should be able to distinguish validation failure from conversion failure or rejected output, and retry without being told that earlier steps succeeded when that was never verified. Clear failure boundaries also make support and debugging easier because the system can explain what was attempted without exposing private file contents or silently skipping a broken step."),
            ("Automation should not remove the final quality check", "A chain can be technically valid and still produce an output that deserves visual or functional review. Open the final artifact, compare page count, size, searchability, or image quality according to the task, and retain the source when the result matters. Automation reduces repetitive work; it does not replace the human check needed to confirm that the final document still serves its intended purpose."),
        ],
    },
    "browser-local-tools-and-privacy": {
        "ar": [
            ("اعرف ما الذي يبقى محليًا فعلًا", "كلمة محلي يجب أن تعني أن المهمة تنفذ في المتصفح بدون إرسال البيانات إلى endpoint خادمي. افحص وصف الأداة وسلوك الشبكة إذا كانت الخصوصية حساسة، وميز بين أداة حساب محلية وبين ميزة تستدعي AI أو خدمة خارجية حتى لو كانت الواجهة نفسها داخل المتصفح."),
            ("استخدم المعالجة المحلية للبيانات القصيرة والمباشرة", "النصوص البسيطة والحسابات والتحويلات الصغيرة مناسبة جدًا للمتصفح، لكنها ليست بديلًا دائمًا لمحركات الملفات الثقيلة. اختر المسار المحلي عندما ينجز المهمة كاملة، وانتقل للخادم فقط عندما تحتاج قدرة لا يستطيع المتصفح توفيرها بموثوقية أو أداء مناسب."),
        ],
        "en": [
            ("Know what 'local' actually means in the product", "A browser-local tool should complete its task without sending the entered data to a server endpoint. When privacy is important, read the tool description and, if necessary, inspect network behavior so you can distinguish an offline calculation from a feature that calls an AI provider or another service even though both appear inside the same web interface. The processing boundary should be understandable rather than implied."),
            ("Use local processing for short, self-contained tasks", "Text cleanup, small calculations, parsing, formatting, and deterministic transformations are strong browser-local use cases because the browser can finish the job without heavy external engines. Local execution is not automatically the best choice for large document rendering or OCR. Choose it when it fully solves the task, and use temporary server processing only when the required capability cannot be delivered reliably on the device."),
        ],
    },
}

for _post in V8_BLOG_POSTS:
    _extra = _V8_DEPTH.get(_post["slug"])
    if not _extra:
        continue
    _post["sections"].extend(_extra["ar"])
    _post["section_en"].extend(title for title, _ in _extra["en"])
    _post["paragraph_en"].extend(paragraph for _, paragraph in _extra["en"])


def install() -> None:
    from core import blog

    existing = {post["slug"] for post in blog.BLOG_POSTS}
    collisions = existing.intersection(post["slug"] for post in V8_BLOG_POSTS)
    if collisions:
        raise RuntimeError(f"Infinity 8 blog slugs already exist: {sorted(collisions)}")
    blog.BLOG_POSTS.extend(V8_BLOG_POSTS)
    blog.BLOG_BY_SLUG.clear()
    blog.BLOG_BY_SLUG.update({post["slug"]: post for post in blog.BLOG_POSTS})
