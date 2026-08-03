import os
from datetime import datetime
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create_pdf():
    try:
        raw_size = request.form.get("size", "REPORT")
        size = secure_filename(raw_size) or "REPORT"

        files = request.files.getlist("photos")

        if not files or files[0].filename == "":
            return "กรุณาเลือกไฟล์ภาพอย่างน้อย 1 รูป", 400

        # ปรับพิกัดวางรูป 4 ช่อง ขยับลงมาด้านล่างเพื่อเว้นพื้นที่ให้ Header ด้านบน
        positions = [
            (40, 180),       # บนซ้าย
            (1280, 180),     # บนขวา
            (40, 1840),      # ล่างซ้าย
            (1280, 1840)     # ล่างขวา
        ]

        pages = []
        current_canvas = Image.new("RGB", (2480, 3508), "white")
        img_count = 0
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ฟังก์ชั่นวาด Header ค่า SIZE ไว้ตรงกลางกระดาษ
        def draw_header(canvas_img, text_to_draw):
            draw_ctx = ImageDraw.Draw(canvas_img)
            # โหลดฟอนต์มาตรฐาน หากในระบบไม่มีฟอนต์ภายนอกจะใช้ default font
            try:
                font = ImageFont.truetype("arial.ttf", 70)
            except IOError:
                font = ImageFont.load_default()
            
            # ข้อความที่จะแสดงหัวกระดาษ
            header_text = f"SIZE : {text_to_draw}"
            
            # คำนวณพิกัดเพื่อให้อยู่กึ่งกลางกระดาษ (A4 กว้าง 2480px)
            bbox = draw_ctx.textbbox((0, 0), header_text, font=font)
            text_width = bbox[2] - bbox[0]
            x_pos = (2480 - text_width) // 2
            y_pos = 60
            
            # วาดตัวหนังสือหัวกระดาษ
            draw_ctx.text((x_pos, y_pos), header_text, fill=(0, 0, 0), font=font)

        # วาด Header สำหรับหน้าแรก
        draw_header(current_canvas, size)

        for i, file in enumerate(files):
            with Image.open(file) as raw_img:
                img = raw_img.convert("RGB")
                img.thumbnail((1160, 1600))

                # ปั๊มข้อความ วันที่/เวลา และลำดับรูป ที่มุมล่างขวาของรูปภาพ
                draw = ImageDraw.Draw(img)
                label_text = f"#{i+1} | {timestamp_str}"
                
                w, h = img.size
                draw.rectangle([(w - 350, h - 50), (w, h)], fill=(0, 0, 0))
                draw.text((w - 340, h - 40), label_text, fill=(255, 255, 255))

                pos_idx = img_count % 4
                current_canvas.paste(img, positions[pos_idx])
                img_count += 1

                # ครบ 4 รูปให้ตัดขึ้นหน้าใหม่
                if img_count % 4 == 0:
                    pages.append(current_canvas)
                    current_canvas = Image.new("RGB", (2480, 3508), "white")
                    draw_header(current_canvas, size)  # วาด Header ให้หน้าใหม่ด้วย

        # เพิ่มหน้าที่เหลือกรณีรูปไม่ครบ 4 ในหน้าสุดท้าย
        if img_count % 4 != 0:
            pages.append(current_canvas)

        # ตั้งชื่อไฟล์
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{size}_{today}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, filename)

        # บันทึกเป็น Multi-page PDF
        if pages:
            pages[0].save(
                pdf_path,
                "PDF",
                resolution=300.0,
                save_all=True,
                append_images=pages[1:]
            )

        return f"""
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Report</title>
</head>
<body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #f8fafc;">

    <div style="max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: #16a34a; margin-top: 0;">✅ สร้าง PDF สำเร็จ</h2>
        <p style="color: #475569;">ชื่อไฟล์: <strong>{filename}</strong></p>
        <p style="color: #64748b; font-size: 14px;">จำนวนรูปทั้งหมด: {len(files)} รูป ({len(pages)} หน้า)</p>
        <br>
        <a href="/download/{filename}">
            <button
                style="
                    font-size: 18px;
                    padding: 12px 28px;
                    background: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: bold;
                ">
                📥 ดาวน์โหลด PDF
            </button>
        </a>
    </div>

</body>
</html>
"""

    except Exception as e:
        app.logger.error(f"Error creating PDF: {str(e)}")
        return f"เกิดข้อผิดพลาดภายในระบบ: {e}", 500


@app.route("/download/<filename>")
def download(filename):
    safe_filename = secure_filename(filename)
    pdf_path = os.path.join(OUTPUT_DIR, safe_filename)

    if not os.path.exists(pdf_path):
        return "ไม่พบไฟล์ที่ต้องการดาวน์โหลด", 404

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=safe_filename
    )


if __name__ == "__main__":
    app.run(debug=True)