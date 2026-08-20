FROM python:3.10-slim

# تثبيت البرامج الأساسية: تحويل المستندات + الذكاء الاصطناعي للصور (عربي وإنجليزي)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fontconfig \
    tesseract-ocr \
    tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# رفعنا وقت الانتظار لـ 300 ثانية (5 دقائق) عشان الملفات الثقيلة
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "app:app"]
