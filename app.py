from flask import Flask, request, send_file
import os
import tempfile
import base64
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pandas as pd
from PIL import Image

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Python Conversion Server is Live!", 200

@app.route('/convert', methods=['POST'])
def convert_file():
    try:
        data = request.get_json() or {}
        action = data.get('action')
        file_base64 = data.get('fileBase64')
        text = data.get('text', '')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output_result")
            
            # 1. تحويل Word إلى PDF
            if action == 'word-to-pdf':
                if not file_base64: return "No file provided", 400
                input_path = os.path.join(temp_dir, "input.docx")
                with open(input_path, "wb") as f:
                    f.write(base64.b64decode(file_base64))
                
                doc = Document(input_path)
                output_pdf = output_path + ".pdf"
                c = canvas.Canvas(output_pdf, pagesize=letter)
                text_object = c.beginText(50, 730)
                text_object.setFont("Helvetica", 11)
                
                for para in doc.paragraphs:
                    if para.text.strip():
                        text_object.textLine(para.text.strip()[:85])
                c.drawText(text_object)
                c.save()
                return send_file(output_pdf, as_attachment=True, download_name="converted.pdf")

            # 2. تحويل Excel إلى PDF أو JSON
            elif action in ['excel-to-json', 'pdf-to-excel']:
                # يمكن توسيعها لاحقاً حسب الطلب
                return "Action supported", 200

            # 3. ضغط الصور
            elif action == 'compress-image':
                if not file_base64: return "No image provided", 400
                input_img = os.path.join(temp_dir, "input_img.jpg")
                output_img = output_path + ".jpg"
                with open(input_img, "wb") as f:
                    f.write(base64.b64decode(file_base64))
                
                img = Image.open(input_img)
                img.save(output_img, "JPEG", quality=70)
                return send_file(output_img, as_attachment=True, download_name="compressed.jpg")

            return "Unknown action", 400

    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
