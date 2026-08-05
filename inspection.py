import base64
import gc
import os
import threading
from datetime import datetime
from flask import redirect, url_for
from PIL import Image, ImageDraw, ImageFont
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = "godtitle@gmail.com"
SENDER_NAME = "Photo Report System"
RECEIVER_EMAIL = "ptcuringfac1@hotmail.com"

configuration = sib_api_v3_sdk.Configuration()
if BREVO_API_KEY:
    configuration.api_key['api-key'] = BREVO_API_KEY


def send_pdf_email_async(receiver_email, filename, pdf_path, pdf_url):
    def send_task():
        if not BREVO_API_KEY:
            return

        try:
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
            
            sender = {"name": SENDER_NAME, "email": SENDER_EMAIL}
            to = [{"email": receiver_email}]
            subject = f"📄 รายงาน Inspection PDF: {filename}"

            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f8fafc;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0;">
                    <h2 style="color: #059669; margin-top: 0;">✅ สร้างไฟล์ Inspection PDF สำเร็จแล้ว</h2>
                    <p style="font-size: 16px; color: #334155;">ชื่อไฟล์: <strong>{filename}</strong></p>
                    <p style="font-size: 16px; color: #334155;">ระบบได้แนบไฟล์ PDF มากับอีเมลฉบับนี้เรียบร้อยแล้วครับ</p>
                    <br>
                    <div style="text-align: center;">
                        <a href="{pdf_url}" style="padding: 12px 24px; background-color: #059669; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                            🌐 ดูและดาวน์โหลดผ่านเว็บไซต์
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
                attachment_list.append(
                    {"content": encoded_file, "name": filename}
                )

            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=to,
                sender=sender,
                subject=subject,
                html_content=html_content,
                attachment=attachment_list,
            )

            api_instance.send_transac_email(send_smtp_email)
            print(f"Async email sent successfully for {filename}")
            
        except Exception as e:
            print(f"Error sending email async: {e}")

    thread = threading.Thread(target=send_task)
    thread.start()


def process_inspection(request):
    try:
        machine_no = request.form.get("machine_no", "").strip()
        unit = request.form.get("unit", "").strip()
        files = request.files.getlist("photos")

        if not files or files[0].filename == "":
            return "กรุณาเลือกไฟล์ภาพอย่างน้อย 1 รูป", 400

        # ตำแหน่งวางรูปในหน้า A4 (2480x3508)
        positions = [(40, 180), (1280, 180), (40, 1840), (1280, 1840)]
        
        pages = [] 
        current_canvas = Image.new("RGB", (2480, 3508), "white") 
        img_count = 0
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M")

        header_title = f"MC: {machine_no} | UNIT: {unit}"

        # Font
        font_path = None
        possible_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "arial.ttf",
        ]
        for path in possible_fonts:
            if os.path.exists(path):
                font_path = path
                break

        try:
            if font_path:
                header_font = ImageFont.truetype(font_path, 100)
                label_font = ImageFont.truetype(font_path, 36)
            else:
                header_font = label_font = ImageFont.load_default()
        except Exception:
            header_font = label_font = ImageFont.load_default()

        def draw_header(canvas_img, text_to_draw):
            draw_ctx = ImageDraw.Draw(canvas_img)
            bbox = draw_ctx.textbbox((0, 0), text_to_draw, font=header_font)
            text_width = bbox[2] - bbox[0]
            x_pos = (2480 - text_width) // 2
            draw_ctx.text((x_pos, 45), text_to_draw, fill=(0, 0, 0), font=header_font)

        draw_header(current_canvas, header_title)

        for i, file in enumerate(files):
            try:
                # เปิดรูปทีละรูป
                raw_img = Image.open(file)
                img = raw_img.convert("RGB")
                raw_img.close() # ปิดไฟล์ดิบทันทีเพื่อคืน RAM

                # เปลี่ยน resample เป็น BILINEAR เพื่อประหยัด RAM มหาศาล
                img.thumbnail((1160, 1600), Image.Resampling.BILINEAR)

                draw = ImageDraw.Draw(img)
                label_text = f"#{i+1} | {timestamp_str}"
                w, h = img.size

                draw.rectangle([(w - 450, h - 60), (w, h)], fill=(0, 0, 0))
                draw.text(
                    (w - 430, h - 50),
                    label_text,
                    fill=(255, 255, 255),
                    font=label_font,
                )

                pos_idx = img_count % 4
                current_canvas.paste(img, positions[pos_idx])
                
                # ทำลายวัตถุรูปชั่วคราวทิ้ง และล้าง RAM
                del img
                gc.collect()

                img_count += 1

                if img_count % 4 == 0:
                    pages.append(current_canvas)
                    current_canvas = Image.new("RGB", (2480, 3508), "white")
                    draw_header(current_canvas, header_title)
                        
            except Exception as img_err:
                print(f"Error processing image {i+1}: {img_err}")

        if img_count % 4 != 0:
            pages.append(current_canvas)

        day_str = str(now.day)
        date_str = f"{day_str}{now.strftime('%b%Y')}" 
        filename = f"Inspection_{machine_no}_Unit{unit}_{date_str}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, filename)

        if pages:
            pages[0].save(
                pdf_path,
                "PDF",
                resolution=300.0,
                save_all=True,
                append_images=pages[1:],
            )
            # ล้าง RAM ของ pages
            del pages
            gc.collect()
        else:
            return "ไม่สามารถสร้าง PDF ได้เนื่องจากไม่มีรูปภาพที่ใช้งานได้", 500

        email_status = "กำลังส่งอีเมลเบื้องหลัง..."
        if RECEIVER_EMAIL:
            file_url = url_for("download", filename=filename, _external=True)
            send_pdf_email_async(RECEIVER_EMAIL, filename, pdf_path, file_url)
            email_status = f"ระบบกำลังส่งอีเมลไปยัง {RECEIVER_EMAIL}"

        return redirect(
            url_for("result", filename=filename, status=email_status)
        )

    except Exception as e:
        print(f"Error in process_inspection: {e}")
        return f"เกิดข้อผิดพลาดบนเซิร์ฟเวอร์: {e}", 500