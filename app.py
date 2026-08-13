from flask import Flask, request, send_file
import os
from docx2pdf import convert
import tempfile

app = Flask(__name__)

@app.route('/convert', methods=['POST'])
def convert_file():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    
    # استخدام مجلد مؤقت آمن لمعالجة الملفات
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, file.filename)
        file.save(input_path)
        
        # تحديد مسار ملف الـ PDF الناتج
        output_filename = file.filename.rsplit('.', 1)[0] + '.pdf'
        output_path = os.path.join(temp_dir, output_filename)
        
        # التحويل باستخدام مكتبة بايثون
        try:
            convert(input_path, output_path)
            return send_file(output_path, as_attachment=True, download_name=output_filename)
        except Exception as e:
            return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
