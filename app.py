from flask import Flask, request, send_file
import os
import tempfile
import base64
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

@app.route('/convert', methods=['POST'])
def convert_file():
    try:
        data = request.get_json() or {}
        file_base64 = data.get('fileBase64')
        
        if not file_base64:
            return "No fileBase64 provided", 400
        
        file_bytes = base64.b64decode(file_base64)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.docx")
            output_path = os.path.join(temp_dir, "output.pdf")
            
            with open(input_path, "wb") as f:
                f.write(file_bytes)
                
            # قراءة ملف الـ Word واستخراج النصوص
            doc = Document(input_path)
            fullText = []
            for para in doc.paragraphs:
                if para.text.strip():
                    fullText.append(para.text)
            
            # إنشاء ملف PDF نظيف من النصوص المستخرجة
            c = canvas.Canvas(output_path, pagesize=letter)
            text_object = c.beginText(40, 750)
            text_object.setFont("Helvetica", 12)
            
            for line in fullText:
                # تقسيم الأسطر الطويلة لتتطابق مع صفحة الـ PDF
                text_object.textLine(line[:90])
                
            c.drawText(text_object)
            c.save()
            
            if os.path.exists(output_path):
                return send_file(output_path, as_attachment=True, download_name="converted.pdf")
            else:
                return "PDF generation failed", 500
                
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
