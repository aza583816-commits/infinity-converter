// =====================================================================================
// download.js — تنزيل الملفات بشكل موثوق على كل المتصفحات، بما فيها Safari على الآيباد
//
// 🔧 هذا الملف يحل مشكلة "الشاشة السوداء/البيضاء عند التنزيل":
// الكود القديم كان يحوّل الـ Blob القادم من السيرفر إلى base64 عبر FileReader،
// ثم يضعه كـ data-URI ضخم داخل <a href="data:...">. متصفح Safari (خصوصاً على
// iPadOS) يفرض حدّاً على طول data-URI؛ فعند تجاوزه — وهو أمر شائع مع ملفات PDF/
// Word/ZIP الحقيقية — يفشل التنقل بصمت ويظهر تبويب أسود أو أبيض فارغ بدل التنزيل.
//
// الحل: نستخدم Blob URL (`URL.createObjectURL`) مباشرة بدون أي تحويل إضافي —
// وهو المسار القياسي الموثوق في كل المتصفحات الحديثة — ثم نحرره من الذاكرة بعد
// إتمام النقرة. لا حاجة لقراءة الملف كـ base64 مرتين (مرة من fetch ثم مرة أخرى
// عبر FileReader)، ما يوفر الذاكرة أيضاً على الأجهزة الضعيفة.
// =====================================================================================

const IOS_REGEX = /iP(hone|od|ad)/;

function isIOS() {
  // iPadOS 13+ يظهر كـ "Macintosh" لكنه يدعم اللمس، لذا نتحقق من الاثنين
  return IOS_REGEX.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

/**
 * ينزّل Blob باسم ملف معيّن بأكثر طريقة متوافقة مع المتصفحات، مع رسالة توضيحية
 * تُرجعها الدالة لتُعرض للمستخدم (لأن سلوك iOS مع بعض الصيغ يختلف عن سطح المكتب).
 */
function downloadBlob(blob, filename, lang) {
  const url = URL.createObjectURL(blob);
  const isPdf = /\.pdf$/i.test(filename) || blob.type === 'application/pdf';

  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  // نحرر الذاكرة بعد مهلة قصيرة لضمان بدء التنزيل فعلياً قبل الإلغاء
  setTimeout(() => URL.revokeObjectURL(url), 30000);

  // سلوك Safari على iOS/iPadOS: لا يدعم إجبار تنزيل ملفات PDF، بل يفتحها للمعاينة
  // داخل التبويب نفسه — وهذا سلوك طبيعي من النظام وليس عطلاً في الموقع.
  if (isIOS() && isPdf) {
    return lang === 'ar'
      ? '✅ تم فتح الملف للمعاينة (سلوك آيباد الطبيعي مع PDF) — لحفظه اضغط على أيقونة المشاركة ثم "حفظ في الملفات".'
      : '✅ File opened for preview (normal iPad/Safari behavior for PDFs) — tap the Share icon then "Save to Files" to keep it.';
  }

  return lang === 'ar' ? '✅ تمت المعالجة وتم بدء التنزيل!' : '✅ Processed and download started!';
}

window.VInfinityDownload = { downloadBlob, isIOS };
