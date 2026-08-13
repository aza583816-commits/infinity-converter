from flask import Flask, request, send_file
import os
from docx2pdf import convert
import tempfile
import base64

app = Flask(__name__)

@app.route('/convert', methods=['POST'])
def convert_file():
    try:
        data = request.get_json() or {}
        file_base64 = data.get('fileBase64')
        
        if not file_base64:
            return "No file provided", 400
        
        file_bytes = base64.b64decode(file_base64)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.docx")
            output_path = os.path.join(temp_dir, "output.pdf")
            
            with open(input_path, "wb") as f:
                f.write(file_bytes)
                
            convert(input_path, output_path)
            
            return send_file(output_path, as_attachment=True, download_name="converted.pdf")
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
