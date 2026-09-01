"""Schemas for browser-only utilities. These tools never receive user data server-side."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserTool:
    id: str
    collection: str
    name_ar: str
    name_en: str
    description_ar: str
    description_en: str
    icon: str
    fields: tuple[dict, ...]


def field(key, label_ar, label_en, kind="number", placeholder="", value=""):
    return {"key": key, "label_ar": label_ar, "label_en": label_en, "type": kind, "placeholder": placeholder, "value": value}


TEXT = lambda key, ar, en, placeholder="": field(key, ar, en, "textarea", placeholder)
DATE = lambda key, ar, en: field(key, ar, en, "date")

BROWSER_TOOLS = (
    BrowserTool("gpa-calculator", "students", "حاسبة المعدل التراكمي", "GPA Calculator", "احسب معدلك من درجات الساعات المعتمدة.", "Calculate your GPA from course grades and credit hours.", "GPA", (TEXT("courses", "المقررات: الدرجة,الساعات لكل سطر", "Courses: grade,credits per line", "A,3\nB+,4"),)),
    BrowserTool("weighted-grade-calculator", "students", "حاسبة الدرجات الموزونة", "Weighted Grade Calculator", "احسب نتيجتك من الدرجات وأوزانها.", "Calculate a result from grades and their weights.", "%", (TEXT("items", "الدرجات: الدرجة,الوزن لكل سطر", "Grades: grade,weight per line", "85,40\n92,60"),)),
    BrowserTool("study-session-planner", "students", "مخطط جلسة المذاكرة", "Study Session Planner", "أنشئ خطة مذاكرة قصيرة بفواصل منتظمة.", "Create a focused study plan with regular breaks.", "PLAN", (field("minutes", "الدقائق المتاحة", "Minutes available", value="120"), field("topics", "عدد الموضوعات", "Topics", value="3"))),
    BrowserTool("focus-timer", "students", "مؤقت التركيز", "Focus Timer", "مؤقت تركيز بسيط يعمل داخل المتصفح.", "A simple focus timer that runs in your browser.", "25", (field("minutes", "دقائق التركيز", "Focus minutes", value="25"),)),
    BrowserTool("flashcard-maker", "students", "صانع البطاقات التعليمية", "Flashcard Maker", "حوّل أزواج السؤال والجواب إلى بطاقات قابلة للمراجعة.", "Turn question and answer pairs into reviewable cards.", "Q/A", (TEXT("cards", "سؤال | جواب لكل سطر", "Question | answer per line", "Capital of France | Paris"),)),
    BrowserTool("reading-time-estimator", "students", "مقدر وقت القراءة", "Reading Time Estimator", "قدّر وقت القراءة للنص الذي تكتبه.", "Estimate reading time for text you enter.", "READ", (TEXT("text", "النص", "Text"),)),
    BrowserTool("word-character-counter", "students", "عداد الكلمات والأحرف", "Word and Character Counter", "عد الكلمات والأحرف والأسطر في النص.", "Count words, characters, and lines in text.", "ABC", (TEXT("text", "النص", "Text"),)),
    BrowserTool("rubric-score-calculator", "educators", "حاسبة درجات التقييم", "Rubric Score Calculator", "احسب درجة تقييم موزونة بسرعة.", "Calculate a weighted rubric score quickly.", "RUB", (TEXT("items", "المعيار: الدرجة,الوزن لكل سطر", "Criterion: score,weight per line", "Research,4,30\nWriting,3,70"),)),
    BrowserTool("classroom-group-maker", "educators", "منشئ مجموعات الصف", "Classroom Group Maker", "وزع أسماء الطلاب عشوائيًا على مجموعات.", "Randomly distribute student names into groups.", "GRP", (TEXT("names", "الأسماء، اسم في كل سطر", "Names, one per line", "Amina\nOmar\nSara"), field("groups", "عدد المجموعات", "Number of groups", value="2"))),
    BrowserTool("random-name-picker", "educators", "اختيار اسم عشوائي", "Random Name Picker", "اختر اسمًا عشوائيًا من قائمتك.", "Pick a random name from your list.", "RND", (TEXT("names", "الأسماء، اسم في كل سطر", "Names, one per line"),)),
    BrowserTool("score-to-percentage", "educators", "تحويل الدرجة إلى نسبة", "Score-to-Percentage Converter", "حوّل الدرجة إلى نسبة مئوية.", "Convert a score into a percentage.", "%", (field("score", "الدرجة", "Score", value="18"), field("total", "الدرجة الكلية", "Total score", value="20"))),
    BrowserTool("lesson-timing-planner", "educators", "مخطط توقيت الدرس", "Lesson Timing Planner", "قسّم وقت الدرس إلى افتتاح ومحتوى ومراجعة.", "Split a lesson into opening, instruction, and review.", "TIME", (field("minutes", "مدة الدرس بالدقائق", "Lesson minutes", value="50"),)),
    BrowserTool("learning-objective-builder", "educators", "منشئ أهداف التعلم", "Learning Objective Builder", "أنشئ صياغة هدف تعلم واضحة.", "Build a clear learning-objective statement.", "OBJ", (field("verb", "الفعل", "Action verb", "text", "analyze", "Analyze"), field("topic", "الموضوع", "Topic", "text", "photosynthesis", "photosynthesis"), field("condition", "السياق أو الشرط", "Condition or context", "text", "after the lesson", "after the lesson"))),
    BrowserTool("seating-plan-generator", "educators", "مولد مخطط الجلوس", "Seating Plan Generator", "رتب أسماء الطلاب عشوائيًا في شبكة مقاعد.", "Arrange student names randomly in a seating grid.", "SEAT", (TEXT("names", "الأسماء، اسم في كل سطر", "Names, one per line"), field("columns", "عدد الأعمدة", "Columns", value="4"))),
    BrowserTool("jwt-decoder", "developers", "محلل JWT", "JWT Decoder", "يفك ترميز رأس وحمولة JWT محليًا فقط؛ التوقيع غير متحقق منه.", "Decode a JWT header and payload locally only; signature is unverified.", "JWT", (TEXT("token", "رمز JWT", "JWT token"),)),
    BrowserTool("query-string-parser-builder", "developers", "محلل وباني Query String", "Query String Parser/Builder", "حلل query string أو ابنها من أسطر مفتاح=قيمة.", "Parse a query string or build one from key=value lines.", "?=", (TEXT("query", "Query string أو key=value", "Query string or key=value", "name=Amina&role=editor"),)),
    BrowserTool("html-entity-converter", "developers", "تشفير وفك HTML Entities", "HTML Entity Encode/Decode", "شفّر أو فك HTML entities داخل المتصفح.", "Encode or decode HTML entities in your browser.", "&;", (TEXT("text", "النص", "Text", "<strong>Hello</strong>"),)),
    BrowserTool("unicode-inspector", "developers", "فاحص Unicode ومحوله", "Unicode Inspector/Escape Converter", "اعرض نقاط Unicode أو حوّل النص إلى escapes.", "Inspect Unicode code points or convert text to escapes.", "U+", (TEXT("text", "النص", "Text", "Hello مرحبا"),)),
    BrowserTool("cron-explainer", "developers", "شارح Cron", "Cron Expression Explainer", "اشرح تعبير cron القياسي ذي الحقول الخمسة.", "Explain a standard five-field cron expression.", "CRON", (field("expression", "تعبير Cron", "Cron expression", "text", "0 9 * * 1-5", "0 9 * * 1-5"),)),
    BrowserTool("color-contrast-checker", "developers", "فاحص تباين الألوان", "Color Contrast Checker", "تحقق من تباين لون النص والخلفية وفق WCAG.", "Check foreground and background contrast against WCAG.", "AA", (field("foreground", "لون النص", "Foreground color", "text", "#102019", "#102019"), field("background", "لون الخلفية", "Background color", "text", "#ffffff", "#ffffff"))),
    BrowserTool("semantic-version-comparator", "developers", "مقارن الإصدارات الدلالية", "Semantic Version Comparator", "قارن بين إصدارين دلاليين.", "Compare two semantic versions.", "SEM", (field("first", "الإصدار الأول", "First version", "text", "1.2.0", "1.2.0"), field("second", "الإصدار الثاني", "Second version", "text", "1.10.0", "1.10.0"))),
    BrowserTool("vat-calculator", "business", "حاسبة ضريبة القيمة المضافة", "VAT Calculator", "احسب ضريبة القيمة المضافة والإجمالي.", "Calculate VAT and the total amount.", "VAT", (field("amount", "المبلغ قبل الضريبة", "Amount before VAT", value="100"), field("rate", "نسبة الضريبة", "VAT rate (%)", value="15"))),
    BrowserTool("profit-margin-calculator", "business", "حاسبة هامش الربح", "Profit Margin Calculator", "احسب الربح وهامش الربح من التكلفة وسعر البيع.", "Calculate profit and profit margin from cost and sale price.", "MARGIN", (field("cost", "التكلفة", "Cost", value="80"), field("revenue", "سعر البيع", "Sale price", value="120"))),
    BrowserTool("break-even-calculator", "business", "حاسبة نقطة التعادل", "Break-Even Calculator", "احسب عدد الوحدات اللازمة لتغطية التكاليف.", "Calculate units needed to cover your costs.", "BE", (field("fixed", "التكاليف الثابتة", "Fixed costs", value="1000"), field("price", "سعر الوحدة", "Unit price", value="25"), field("variable", "تكلفة الوحدة المتغيرة", "Variable unit cost", value="10"))),
    BrowserTool("invoice-due-date", "business", "حاسبة استحقاق الفاتورة", "Invoice Due-Date Calculator", "احسب تاريخ استحقاق الفاتورة من تاريخها وشروط الدفع.", "Calculate an invoice due date from issue date and terms.", "DUE", (DATE("date", "تاريخ الفاتورة", "Invoice date"), field("days", "أيام الدفع", "Payment terms (days)", value="30"))),
    BrowserTool("timesheet-hours-calculator", "business", "حاسبة ساعات الدوام", "Timesheet Hours Calculator", "اجمع ساعات العمل من فترات البداية والنهاية.", "Add work hours from start and end time periods.", "HRS", (TEXT("entries", "بداية-نهاية لكل سطر", "Start-End per line", "09:00-17:30\n09:00-16:00"),)),
    BrowserTool("expense-splitter", "business", "مقسم المصروفات", "Expense Splitter", "قسّم إجمالي المصروفات بالتساوي بين المشاركين.", "Split a total expense evenly among participants.", "SPLIT", (field("amount", "إجمالي المصروف", "Total expense", value="250"), field("people", "عدد المشاركين", "Participants", value="5"))),
    BrowserTool("percentage-change", "business", "حاسبة التغير المئوي", "Percentage Change Calculator", "احسب الزيادة أو الانخفاض المئوي بين قيمتين.", "Calculate the percentage increase or decrease between values.", "%", (field("old", "القيمة الأصلية", "Original value", value="100"), field("new", "القيمة الجديدة", "New value", value="125"))),
    BrowserTool("unit-converter", "everyday", "محول الوحدات", "Unit Converter", "حوّل بين وحدات الطول والوزن الشائعة.", "Convert between common length and weight units.", "UNIT", (field("value", "القيمة", "Value", value="1"), field("from", "من: m, km, cm, in, ft, kg, lb", "From: m, km, cm, in, ft, kg, lb", "text", "km", "km"), field("to", "إلى", "To", "text", "mi", "mi"))),
    BrowserTool("cooking-measurement-converter", "everyday", "محول مقاييس الطبخ", "Cooking Measurement Converter", "حوّل بين المليلتر والأكواب والملاعق.", "Convert between milliliters, cups, tablespoons, and teaspoons.", "COOK", (field("value", "القيمة", "Value", value="1"), field("from", "من: ml, cup, tbsp, tsp", "From: ml, cup, tbsp, tsp", "text", "cup", "cup"), field("to", "إلى", "To", "text", "ml", "ml"))),
    BrowserTool("tip-calculator", "everyday", "حاسبة البقشيش", "Tip Calculator", "احسب البقشيش وحصة كل شخص.", "Calculate a tip and each person's share.", "TIP", (field("bill", "قيمة الفاتورة", "Bill amount", value="100"), field("rate", "البقشيش (%)", "Tip (%)", value="15"), field("people", "عدد الأشخاص", "People", value="2"))),
    BrowserTool("age-calculator", "everyday", "حاسبة العمر", "Age Calculator", "احسب العمر من تاريخ الميلاد.", "Calculate age from a birth date.", "AGE", (DATE("birth", "تاريخ الميلاد", "Birth date"),)),
    BrowserTool("date-difference", "everyday", "حاسبة فرق التاريخ", "Date Difference Calculator", "احسب الأيام بين تاريخين.", "Calculate the days between two dates.", "DATE", (DATE("start", "تاريخ البداية", "Start date"), DATE("end", "تاريخ النهاية", "End date"))),
    BrowserTool("time-zone-meeting-planner", "everyday", "مخطط اجتماع المناطق الزمنية", "Time Zone Meeting Planner", "اعرض وقت اجتماع في منطقتين زمنيتين.", "Show a meeting time in two time zones.", "TZ", (field("datetime", "وقت الاجتماع (UTC)", "Meeting time (UTC)", "datetime-local"), field("zone", "المنطقة الثانية (IANA)", "Second zone (IANA)", "text", "Asia/Riyadh", "Asia/Riyadh"))),
    BrowserTool("password-generator", "everyday", "مولد كلمات المرور", "Password Generator", "أنشئ كلمة مرور قوية محليًا.", "Generate a strong password locally.", "PASS", (field("length", "طول كلمة المرور", "Password length", value="16"),)),
)

BROWSER_TOOL_MAP = {tool.id: tool for tool in BROWSER_TOOLS}


def get_browser_tool(tool_id: str) -> BrowserTool | None:
    return BROWSER_TOOL_MAP.get(tool_id)


def browser_collection_tools(collection_id: str) -> list[BrowserTool]:
    return [tool for tool in BROWSER_TOOLS if tool.collection == collection_id]