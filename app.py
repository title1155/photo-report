import os
from datetime import datetime
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)

# สร้างโฟลเดอร์สำหรับเก็บไฟล์ PDF หากยังไม่มี
OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create_pdf():
    try:
        # รับค่า SIZE
        raw_size = request.form.get("size", "REPORT")
        size = secure_filename(raw_size) or "REPORT"

        files = request.files.getlist("photos")

        if not files or files[0].filename == "":
            return "กรุณาเลือกไฟล์ภาพ", 400

        # A4 300 DPI
        canvas = Image.new("RGB", (2480, 3508), "white")

        positions = [
            (40, 40),
            (1280, 40),
            (40, 1794),
            (1280, 1794)
        ]

        for i, file in enumerate(files[:4]):

            app.logger.info(
                f"Processing File {i+1}: {file.filename} | Type: {file.content_type}"
            )

            with Image.open(file) as raw_img:
                img = raw_img.convert("RGB")
                img.thumbnail((1160, 1670))
                canvas.paste(img, positions[i])

        # ชื่อไฟล์
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{size}_{today}.pdf"

        pdf_path = os.path.join(OUTPUT_DIR, filename)

        canvas.save(
            pdf_path,
            "PDF",
            resolution=300.0
        )

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        app.logger.error(f"Error creating PDF: {str(e)}")
        return f"เกิดข้อผิดพลาดภายในระบบ: {e}", 500

if __name__ == "__main__":
    app.run(debug=True)