import base64
import os
from datetime import datetime
from flask import Flask, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# จำกัดขนาดไฟล์อัปโหลดรวมไม่เกิน 64MB
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024

OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# ⚙️ ตั้งค่า Brevo API & อีเมล
# ==========================================
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = "godtitle@gmail.com"  # อีเมลที่สมัครใช้งาน Brevo
SENDER_NAME = "Photo Report System"

# 🎯 อีเมลผู้รับปลายทาง
RECEIVER_EMAIL = "ptcuringfac1@hotmail.com"

configuration = sib_api_v3_sdk.Configuration()
if BREVO_API_KEY:
    configuration.api_key['api-key'] = BREVO_API_KEY


def send_pdf_email(receiver_email, filename, pdf_path, pdf_url):
    """ฟังก์ชันส่งอีเมลพร้อมแนบไฟล์ PDF (Attachment) ผ่าน Brevo API"""
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    sender = {"name": SENDER_NAME, "email": SENDER_EMAIL}
    to = [{"email": receiver_email}]
    subject = f"📄 รายงาน PDF ของคุณพร้อมแล้ว: {filename}"

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f8fafc;">
        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0;">
            <h2 style="color: #16a34a; margin-top: 0;">✅ สร้างไฟล์ PDF สำเร็จแล้ว</h2>
            <p style="font-size: 16px; color: #334155;">ชื่อไฟล์: <strong>{filename}</strong></p>
            <p style="font-size: 16px; color: #334155;">ระบบได้แนบไฟล์ PDF มากับอีเมลฉบับนี้เรียบร้อยแล้วครับ คุณสามารถเปิดดูหรือดาวน์โหลดได้จากไฟล์แนบด้านล่าง</p>
            <br>
            <div style="text-align: center;">
                <a href="{pdf_url}" style="padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                    🌐 หรือกดดูผ่านเว็บไซต์
                </a>
            </div>
            <br>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin-top: 30px;">
            <p style="font-size: 12px; color: #94a3b8; text-align: center;">อีเมลนี้ส่งอัตโนมัติจากระบบ Photo Report</p>
        </div>
      </body>
    </html>
    """

    attachment_list = []
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode("utf-8")

        attachment_list.append({"content": encoded_file, "name": filename})

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject=subject,
        html_content=html_content,
        attachment=attachment_list,
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print("ส่งอีเมลสำเร็จ:", api_response)
        return True
    except ApiException as e:
        print("เกิดข้อผิดพลาดในการส่งอีเมล:", e)
        return False


# ==========================================
# 🌐 Routes
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create_pdf():
    try:
        raw_size = request.form.get("size", "REPORT").strip()
        size = secure_filename(raw_size) or "REPORT"

        # 📌 รับค่า Result จากฟอร์ม
        result_val = request.form.get("result", "RC OK").strip()

        files = request.files.getlist("photos")

        if not files or files[0].filename == "":
            return "กรุณาเลือกไฟล์ภาพอย่างน้อย 1 รูป", 400

        positions = [(40, 180), (1280, 180), (40, 1840), (1280, 1840)]

        pages = []
        current_canvas = Image.new("RGB", (2480, 3508), "white")
        img_count = 0
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M")

        # ข้อความ Header บนหัวกระดาษ (แสดงทั้ง Size และ Result)
        header_title = f"{size} [{result_val}]"

        def draw_header(canvas_img, text_to_draw):
            draw_ctx = ImageDraw.Draw(canvas_img)
            font_size = 110

            font = None
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "arial.ttf",
            ]

            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except IOError:
                    continue

            if font is None:
                font = ImageFont.load_default()

            header_text = f"SIZE : {text_to_draw}"
            bbox = draw_ctx.textbbox((0, 0), header_text, font=font)
            text_width = bbox[2] - bbox[0]
            x_pos = (2480 - text_width) // 2
            draw_ctx.text((x_pos, 45), header_text, fill=(0, 0, 0), font=font)

        draw_header(current_canvas, header_title)

        label_font = None
        label_font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "arial.ttf",
        ]
        for path in label_font_paths:
            try:
                label_font = ImageFont.truetype(path, 36)
                break
            except IOError:
                continue

        for i, file in enumerate(files):
            with Image.open(file) as raw_img:
                img = raw_img.convert("RGB")
                img.thumbnail((1160, 1600))

                draw = ImageDraw.Draw(img)
                label_text = f"#{i+1} | {timestamp_str}"
                w, h = img.size

                draw.rectangle([(w - 450, h - 60), (w, h)], fill=(0, 0, 0))
                if label_font:
                    draw.text(
                        (w - 430, h - 50),
                        label_text,
                        fill=(255, 255, 255),
                        font=label_font,
                    )
                else:
                    draw.text(
                        (w - 340, h - 40), label_text, fill=(255, 255, 255)
                    )

                pos_idx = img_count % 4
                current_canvas.paste(img, positions[pos_idx])
                img_count += 1

                if img_count % 4 == 0:
                    pages.append(current_canvas)
                    current_canvas = Image.new("RGB", (2480, 3508), "white")
                    draw_header(current_canvas, header_title)

        if img_count % 4 != 0:
            pages.append(current_canvas)

        # 📌 จัดรูปแบบวันที่: วันที่ + เดือนย่อ + ปี 4 หลัก (เช่น 4Aug2026)
        day_str = str(now.day)
        date_str = f"{day_str}{now.strftime('%b%Y')}"  # %Y จะได้ปี 4 หลัก เช่น 2026

        # 📌 ตั้งชื่อไฟล์ตามรูปแบบ: 1234 RC NG 4Aug2026.pdf
        filename = f"{size} {result_val} {date_str}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, filename)

        if pages:
            pages[0].save(
                pdf_path,
                "PDF",
                resolution=300.0,
                save_all=True,
                append_images=pages[1:],
            )

        # ส่งอีเมลอัตโนมัติพร้อมแนบไฟล์ PDF
        email_sent_status = "ไม่ได้ส่งอีเมล"
        if RECEIVER_EMAIL:
            file_url = url_for("download", filename=filename, _external=True)
            if send_pdf_email(RECEIVER_EMAIL, filename, pdf_path, file_url):
                email_sent_status = f"ส่งอีเมลสำเร็จไปยัง {RECEIVER_EMAIL}"
            else:
                email_sent_status = "เกิดข้อผิดพลาดในการส่งอีเมล"

        return redirect(
            url_for("result", filename=filename, status=email_sent_status)
        )

    except Exception as e:
        app.logger.error(f"Error creating PDF: {str(e)}")
        return f"เกิดข้อผิดพลาดภายในระบบ: {e}", 500


@app.route("/result/<filename>")
def result(filename):
    status = request.args.get("status", "")
    file_url = url_for("download", filename=filename, _external=True)
    return f"""
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Report</title>
</head>
<body style="font-family: Arial, sans-serif; text-align: center; margin-top: 40px; background-color: #f8fafc; padding: 20px;">

    <div style="max-width: 650px; margin: 0 auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
        <h1 style="color: #16a34a; margin-top: 0; font-size: 32px;">✅ สร้าง PDF สำเร็จ</h1>
        <p style="color: #475569; font-size: 20px; margin: 15px 0;">ชื่อไฟล์: <strong style="color: #0f172a;">{filename}</strong></p>
        <p style="color: #2563eb; font-size: 16px; font-weight: bold; background: #eff6ff; padding: 10px; border-radius: 8px;">📬 สถานะอีเมล: {status}</p>
        <br>
        
        <a href="/download/{filename}" style="text-decoration: none;">
            <button
                style="
                    font-size: 22px;
                    padding: 16px 36px;
                    background: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    cursor: pointer;
                    font-weight: bold;
                    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
                    width: 100%;
                    max-width: 400px;
                    margin-bottom: 15px;
                ">
                👁️ เปิดดู / แชร์ไฟล์ PDF
            </button>
        </a>

        <br>

        <button
            onclick="shareLink('{file_url}')"
            style="
                font-size: 20px;
                padding: 14px 30px;
                background: #059669;
                color: white;
                border: none;
                border-radius: 12px;
                cursor: pointer;
                font-weight: bold;
                box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
                width: 100%;
                max-width: 400px;
            ">
            🔗 ส่งลิงก์ PDF เข้า LINE / แอปอื่น
        </button>
    </div>

    <script>
    function shareLink(url) {{
        if (navigator.share) {{
            navigator.share({{
                title: 'Photo Report PDF',
                text: 'ไฟล์เอกสาร PDF: {filename}',
                url: url
            }}).catch(console.error);
        }} else {{
            navigator.clipboard.writeText(url);
            alert('คัดลอกลิงก์ดาวน์โหลดเรียบร้อยแล้ว!');
        }}
    }}
    </script>

</body>
</html>
"""


@app.route("/download/<filename>")
def download(filename):
    safe_filename = filename
    pdf_path = os.path.join(OUTPUT_DIR, safe_filename)

    if not os.path.exists(pdf_path):
        return "ไม่พบไฟล์ที่ต้องการดาวน์โหลด", 404

    response = send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=safe_filename,
    )

    response.headers["Content-Disposition"] = (
        f'inline; filename="{safe_filename}"'
    )
    response.headers["Content-Type"] = "application/pdf"

    return response


if __name__ == "__main__":
    app.run(debug=True)