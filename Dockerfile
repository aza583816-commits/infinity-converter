FROM python:3.10-slim

# تحديث النظام وتثبيت LibreOffice مع الخطوط العربية الأساسية فقط لتجنب الأخطاء
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-noto-arabic \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
