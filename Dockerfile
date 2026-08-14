FROM python:3.10-slim

# تحديث النظام وتثبيت LibreOffice وحزمة الخطوط الأساسية فقط
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
