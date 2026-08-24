FROM python:3.10-slim

# تثبيت البرامج الأساسية: تحويل المستندات + OCR (عربي وإنجليزي) + خطوط Noto العربية
# ملاحظة: هذي الخطوط كانت موجودة فقط بملف render-build.sh غير المستخدم فعليًا
# (السيرفر يبني بـ Docker)، فما كانت تتثبت على السيرفر الحي إطلاقًا
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ara \
    libreoffice \
    fonts-noto-core \
    fonts-noto-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# رفعنا وقت الانتظار لـ 300 ثانية (5 دقائق) عشان الملفات الثقيلة
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "app:app"]
