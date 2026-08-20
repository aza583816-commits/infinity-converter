#!/usr/bin/env bash
# exit on error
set -o errexit

# تحديث وتثبيت LibreOffice والخطوط لدعم اللغة العربية بالكامل
apt-get update && apt-get install -y libreoffice libreoffice-writer fonts-noto-core fonts-noto-extra tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng


# تثبيت مكتبات بايثون كالمعتاد
pip install -r requirements.txt
