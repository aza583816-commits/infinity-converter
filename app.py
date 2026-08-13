from flask import Flask, request, send_file
import os
import tempfile
import base64
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import urllib.request

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
                
            doc = Document(input_path)
            fullText = []
            for para in doc.paragraphs:
                if para.text.strip():
                    fullText.append(para.text)
            
            # استخدام تقنية رسم النصوص المباشرة مع ترميز سليم
            c = canvas.Canvas(output_path, pagesize=letter)
            
            # رسم النصوص بشكل نظيف
            y = 750
            for line in fullText:
                if y < 50:
                    c.showPage()
                    y = 750
                # معالجة النص لطباعته بشكل مقروء
                clean_text = line.strip()
                c.drawString(40, y, clean_text)
                y -= 25
                
            c.save()
            
            return send_file(output_path, as_attachment=True, download_name="converted.pdf")
            
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
