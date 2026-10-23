import base64
import os
import threading
from datetime import datetime
from flask import jsonify, url_for
from PIL import Image, ImageDraw, ImageFont
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = "godtitle@gmail.com"
SENDER_NAME = "Hot Press Report System"
RECEIVER_EMAIL = "ptcuringfac1@hotmail.com"

configuration = sib_api_v3_sdk.Configuration()
if BREVO_API_KEY:
    configuration.api_key['api-key'] = BREVO_API_KEY


def send_pdf_email_async(receiver_email, filename, pdf_path, pdf_url):
    def send_task():
        try:
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
            sender = {"name": SENDER_NAME, "email": SENDER_EMAIL}
            to = [{"email": receiver_email}]
            # หัวข้ออีเมลลิงก์ตรงกับชื่อไฟล์ PDF พร้อมวันที่และรายละเอียดครบถ้วน
            subject = f"📄 รายงาน Hot Press PDF: {filename}"

            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f8fafc;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0;">
                    <h2 style="color: #2563eb; margin-top: 0;">✅ สร้างไฟล์ Hot Press PDF สำเร็จแล้ว</h2>
                    <p style="font-size: 16px; color: #334155;">ชื่อไฟล์: <strong>{filename}</strong></p>
                    <p style="font-size: 16px; color: #334155;">ระบบได้แนบไฟล์ PDF มากับอีเมลฉบับนี้เรียบร้อยแล้วครับ</p>
                    <br>
                    <div style="text-align: center;">
                        <a href="{pdf_url}" style="padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                            🌐 หรือกดดูผ่านเว็บไซต์
                        </a>
                    </div>
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

            api_instance.send_transac_email(send_smtp_email)
            print(f"Async email sent successfully for {filename}")
        except ApiException as e:
            print("Error sending email async:", e)

    thread = threading.Thread(target=send_task)
    thread.start()


def process_hotpress(request):
    try:
        # รับค่าจากฟอร์มหน้าเว็บครบทุกฟิลด์
        unit = request.form.get("units", "1").strip()
        size_code = request.form.get("size_code", "").strip()
        machine_no = request.form.get("machine_no", "").strip()
        condition_type = request.form.get("condition_type", "Mass").strip()
        result_status = request.form.get("result_status", "RC_OK").strip()
        remark = request.form.get("remark", "-").strip()
        
        files = request.files.getlist("photos")

        if not files or files[0].filename == "":
            return jsonify({"error": "กรุณาเลือกไฟล์ภาพอย่างน้อย 1 รูป"}), 400

        # ขยับตำแหน่งรูปภาพลงเล็กน้อย (จาก 180 เป็น 240) เพื่อเผื่อพื้นที่หัวกระดาษ 2 บรรทัด
        positions = [(40, 240), (1280, 240), (40, 1840), (1280, 1840)]
        pages = []
        current_canvas = Image.new("RGB", (2480, 3508), "white")
        img_count = 0
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M")

        # ข้อความหัวกระดาษแบบ 2 บรรทัด
        header_line1 = f"U{unit} | MC: {machine_no} | Size: {size_code} | Date: {timestamp_str}"
        header_line2 = f"Condition: {condition_type} | Result: {result_status} | Remark: {remark}"

        def draw_header(canvas_img, l1, l2):
            draw_ctx = ImageDraw.Draw(canvas_img)
            font_size = 65
            font = None
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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

            # บรรทัดที่ 1
            bbox1 = draw_ctx.textbbox((0, 0), l1, font=font)
            w1 = bbox1[2] - bbox1[0]
            x1 = (2480 - w1) // 2
            draw_ctx.text((x1, 40), l1, fill=(0, 0, 0), font=font)

            # บรรทัดที่ 2
            bbox2 = draw_ctx.textbbox((0, 0), l2, font=font)
            w2 = bbox2[2] - bbox2[0]
            x2 = (2480 - w2) // 2
            draw_ctx.text((x2, 120), l2, fill=(0, 0, 0), font=font)

        draw_header(current_canvas, header_line1, header_line2)

        label_font = None
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arial.ttf",
        ]:
            try:
                label_font = ImageFont.truetype(path, 36)
                break
            except IOError:
                continue

        for i, file in enumerate(files):
            with Image.open(file) as raw_img:
                img = raw_img.convert("RGB")
                img.thumbnail((1160, 1580), Image.Resampling.LANCZOS)

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
                    draw_header(current_canvas, header_line1, header_line2)

        if img_count % 4 != 0:
            pages.append(current_canvas)

        # รูปแบบชื่อไฟล์ PDF: U[Unit]_[MC]_[Size]_[Condition]_[Result]_[Remark]_[Date].pdf
        date_str = now.strftime("%d%b%Y") 
        clean_remark = remark.replace(" ", "_")
        filename = f"U{unit}_{machine_no}_{size_code}_{condition_type}_{result_status}_{clean_remark}_{date_str}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, filename)

        if pages:
            pages[0].save(
                pdf_path,
                "PDF",
                resolution=300.0,
                save_all=True,
                append_images=pages[1:],
            )

        email_status = "ระบบกำลังส่งอีเมลเบื้องหลัง..."
        if RECEIVER_EMAIL:
            file_url = url_for("download", filename=filename, _external=True)
            send_pdf_email_async(RECEIVER_EMAIL, filename, pdf_path, file_url)
            email_status = f"ระบบกำลังส่งอีเมลไปยัง {RECEIVER_EMAIL}"

        redirect_url = url_for("result", filename=filename, status=email_status)
        return jsonify({"redirect_url": redirect_url})

    except Exception as e:
        return jsonify({"error": f"เกิดข้อผิดพลาดใน Hot Press: {e}"}), 500