import base64
import os
import threading
from datetime import datetime
from flask import redirect, url_for, request
from PIL import Image, ImageDraw, ImageFont
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# ตั้งค่าโฟลเดอร์สำหรับเก็บไฟล์ PDF ที่สร้าง
OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# การตั้งค่าอีเมล (Brevo)
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_EMAIL = "godtitle@gmail.com"
SENDER_NAME = "Photo Report System"
RECEIVER_EMAIL = "ptcuringfac1@hotmail.com" # อีเมลผู้รับปลายทาง

# ตั้งค่า Configuration สำหรับ Brevo API
configuration = sib_api_v3_sdk.Configuration()
if BREVO_API_KEY:
    configuration.api_key['api-key'] = BREVO_API_KEY


def send_pdf_email_async(receiver_email, filename, pdf_path, pdf_url):
    """ฟังก์ชันสำหรับส่งอีเมลเบื้องหลัง (Background Thread) เพื่อไม่ให้หน้าเว็บค้าง"""
    def send_task():
        if not BREVO_API_KEY:
            print("Skipping email send: BREVO_API_KEY not set.")
            return

        try:
            # สร้าง API Instance
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )
            
            # ข้อมูลผู้ส่งและผู้รับ
            sender = {"name": SENDER_NAME, "email": SENDER_EMAIL}
            to = [{"email": receiver_email}]
            subject = f"📄 รายงาน Inspection PDF: {filename}"

            # เนื้อหาอีเมลแบบ HTML
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
                            🌐 หรือกดดูและดาวน์โหลดผ่านเว็บไซต์
                        </a>
                    </div>
                    <p style="font-size: 12px; color: #94a3b8; margin-top: 30px; text-align: center;">
                        นี่คืออีเมลอัตโนมัติจากระบบ Photo Report ไม่ต้องตอบกลับอีเมลนี้
                    </p>
                </div>
              </body>
            </html>
            """

            # เตรียมไฟล์แนบ
            attachment_list = []
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    encoded_file = base64.b64encode(f.read()).decode("utf-8")
                attachment_list.append(
                    {"content": encoded_file, "name": filename}
                )

            # สร้าง SmtpEmail Object
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=to,
                sender=sender,
                subject=subject,
                html_content=html_content,
                attachment=attachment_list,
            )

            # ส่งอีเมล
            api_instance.send_transac_email(send_smtp_email)
            print(f"Async email sent successfully to {receiver_email} for {filename}")
            
        except ApiException as e:
            print(f"Error sending email async: {e}")
        except Exception as e:
            print(f"General error in email thread: {e}")

    # เริ่มรัน Thread เบื้องหลัง
    thread = threading.Thread(target=send_task)
    thread.start()


def process_inspection(request):
    """ฟังก์ชันหลักในการประมวลผลข้อมูลฟอร์มและสร้าง PDF"""
    try:
        # รับค่าจากฟอร์ม
        machine_no = request.form.get("machine_no", "").strip()
        unit = request.form.get("unit", "").strip()
        files = request.files.getlist("photos")

        # ตรวจสอบว่ามีการเลือกรูปภาพหรือไม่
        if not files or files[0].filename == "":
            return "กรุณาเลือกไฟล์ภาพอย่างน้อย 1 รูป", 400

        # กำหนดตำแหน่งวางรูป 4 รูปต่อหน้า A4 (หน่วยเป็นพิกเซลที่ 300 DPI)
        # ขนาดหน้า A4 ที่ 300 DPI คือ 2480x3508 พิกเซล
        positions = [(40, 180), (1280, 180), (40, 1840), (1280, 1840)]
        
        pages = [] # เก็บหน้า A4 แต่ละหน้า
        current_canvas = Image.new("RGB", (2480, 3508), "white") # สร้างหน้าว่าง
        img_count = 0
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M") # เวลาสำหรับ Label บนรูป

        # ข้อความหัวกระดาษ
        header_title = f"MC: {machine_no} | UNIT: {unit}"

        # พยายามโหลด Font ภาษาไทย/English (DejaVuSans มีติดมากับ Linux ส่วนใหญ่)
        font_path = None
        possible_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "arial.ttf", # สำหรับ Windows
        ]
        for path in possible_fonts:
            if os.path.exists(path):
                font_path = path
                break

        # ตั้งค่า Font Size
        try:
            if font_path:
                header_font = ImageFont.truetype(font_path, 100)
                label_font = ImageFont.truetype(font_path, 36)
            else:
                header_font = label_font = ImageFont.load_default()
        except Exception:
            header_font = label_font = ImageFont.load_default()

        # ฟังก์ชันสำหรับวาดหัวกระดาษ (วาดซ้ำทุกหน้า)
        def draw_header(canvas_img, text_to_draw):
            draw_ctx = ImageDraw.Draw(canvas_img)
            # คำนวณให้ข้อความอยู่ตรงกลาง
            bbox = draw_ctx.textbbox((0, 0), text_to_draw, font=header_font)
            text_width = bbox[2] - bbox[0]
            x_pos = (2480 - text_width) // 2
            draw_ctx.text(
                (x_pos, 45), text_to_draw, fill=(0, 0, 0), font=header_font
            )

        # วาดหัวกระดาษหน้าแรก
        draw_header(current_canvas, header_title)

        # วนลูปประมวลผลรูปภาพทีละรูป
        for i, file in enumerate(files):
            try:
                with Image.open(file) as raw_img:
                    # แปลงเป็น RGB และปรับขนาดให้พอดีช่อง (thumbnail)
                    img = raw_img.convert("RGB")
                    # thumbnail จะรักษาอัตราส่วนภาพไว้ ไม่ให้ภาพบี้
                    img.thumbnail((1160, 1600), Image.Resampling.LANCZOS)

                    # วาด Label (ลำดับรูป + เวลา) ลงบนรูปภาพ
                    draw = ImageDraw.Draw(img)
                    label_text = f"#{i+1} | {timestamp_str}"
                    w, h = img.size

                    # วาดแถบพื้นหลังสีดำตรงมุมขวาล่างเพื่อให้เห็นข้อความชัดเจน
                    draw.rectangle([(w - 450, h - 60), (w, h)], fill=(0, 0, 0))
                    # วาดข้อความสีขาว
                    draw.text(
                        (w - 430, h - 50),
                        label_text,
                        fill=(255, 255, 255),
                        font=label_font,
                    )

                    # แปะรูปภาพลงบนหน้า A4 ตามตำแหน่งที่กำหนด
                    pos_idx = img_count % 4
                    current_canvas.paste(img, positions[pos_idx])
                    img_count += 1

                    # ถ้าครบ 4 รูป ให้บันทึกหน้านี้แล้วสร้างหน้าใหม่
                    if img_count % 4 == 0:
                        pages.append(current_canvas)
                        current_canvas = Image.new("RGB", (2480, 3508), "white")
                        draw_header(current_canvas, header_title) # วาดหัวกระดาษหน้าใหม่
                        
            except Exception as img_err:
                print(f"Error processing image {i+1}: {img_err}")
                # ข้ามรูปที่เสียไป

        # ถ้ามีรูปเหลือแต่ไม่ครบ 4 รูป ให้เพิ่มหน้านั้นเข้าไปด้วย
        if img_count % 4 != 0:
            pages.append(current_canvas)

        # ตั้งชื่อไฟล์ PDF
        day_str = str(now.day)
        date_str = f"{day_str}{now.strftime('%b%Y')}" # เช่น 5Aug2026
        filename = f"Inspection_{machine_no}_Unit{unit}_{date_str}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, filename)

        # บันทึกรูปภาพทั้งหมดเป็นไฟล์ PDF (300 DPI)
        if pages:
            pages[0].save(
                pdf_path,
                "PDF",
                resolution=300.0,
                save_all=True,
                append_images=pages[1:],
            )
        else:
            return "ไม่สามารถสร้าง PDF ได้เนื่องจากไม่มีรูปภาพที่ใช้งานได้", 500

        # เริ่มกระบวนการส่งอีเมลเบื้องหลัง
        email_status = "กำลังส่งอีเมลเบื้องหลัง..."
        if RECEIVER_EMAIL:
            # สร้าง URL สำหรับดูไฟล์บนเว็บ
            file_url = url_for("download", filename=filename, _external=True)
            send_pdf_email_async(RECEIVER_EMAIL, filename, pdf_path, file_url)
            email_status = f"ระบบกำลังส่งอีเมลไปยัง {RECEIVER_EMAIL}"

        # **สำคัญ** กลับไปใช้ redirect แบบเดิมที่เสถียรที่สุด ไม่ต้องผ่าน JSON
        return redirect(
            url_for("result", filename=filename, status=email_status)
        )

    except Exception as e:
        print(f"Error in process_inspection: {e}")
        return f"เกิดข้อผิดพลาดร้ายแรง: {e}", 500