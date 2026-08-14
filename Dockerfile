FROM python:3.10-slim

# تحديث السيرفر وتثبيت LibreOffice والخطوط العربية عشان التنسيق يجي مسطرة
RUN apt-get update && apt-get install -y \
    libreoffice \
    fonts-noto-arabic \
    fonts-kacst \
    fonts-hosny-amiri \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# تشغيل السيرفر (رفعنا وقت الانتظار لـ 120 ثانية عشان البرنامج الثقيل ياخذ راحته)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
