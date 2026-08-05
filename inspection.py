import io
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ฟังก์ชันย่อรูปภาพใน Memory เพื่อเพิ่มความเร็วอย่างก้าวกระโดด
def process_and_compress_image(photo_file, max_size=(800, 800), quality=75):
    """
    อ่านไฟล์รูป ปรับ Orientation ตาม EXIF ปรับขนาด ไม่ให้เกิน max_size 
    และบีบอัดคุณภาพลงเหลือ quality% ใน RAM (BytesIO)
    """
    img = Image.open(photo_file)
    
    # หมุนภาพให้ตรงตามค่า EXIF ของกล้องมือถือ
    img = ImageOps.exif_transpose(img)
    
    # แปลงเป็น RGB หากเป็น RGBA หรือไฟล์ชนิดอื่น
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    # ย่อขนาดรูปภาพ (Thumbnail/Resize)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # บันทึกเป็น BytesIO ใน RAM
    img_io = io.BytesIO()
    img.save(img_io, format='JPEG', quality=quality, optimize=True)
    img_io.seek(0)
    return img_io

def generate_inspection_pdf(machine_no, unit, photos, output_stream):
    """
    สร้าง PDF Inspection Report แบบรวดเร็ว
    - machine_no: เลขเครื่อง
    - unit: Unit
    - photos: List ของไฟล์รูปภาพที่อัปโหลดเข้ามา
    - output_stream: Stream/Path สำหรับเซฟ PDF
    """
    # 1. ใช้ Multi-threading เพื่อย่อและบีบอัดรูปภาพ 14 รูปพร้อมๆ กัน
    with ThreadPoolExecutor() as executor:
        compressed_photos = list(executor.map(process_and_compress_image, photos))

    # 2. ตั้งค่า Document (ระยะขอบ)
    doc = SimpleDocTemplate(
        output_stream,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    
    # Style สำหรับหัวข้อและข้อความ
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#059669'),
        alignment=1, # Center
        spaceAfter=10
    )
    
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e293b')
    )

    story = []

    # หัวข้อรายงาน
    story.append(Paragraph("<b>INSPECTION REPORT</b>", title_style))
    story.append(Spacer(1, 10))

    # ตารางแสดงข้อมูล Machine No. & Unit
    info_data = [
        [
            Paragraph(f"<b>Machine No:</b> {machine_no}", info_style),
            Paragraph(f"<b>Unit:</b> {unit}", info_style)
        ]
    ]
    info_table = Table(info_data, colWidths=[270, 270])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    # 3. จัดการวางรูปภาพเป็น Grid (2 คอลัมน์ต่อแถว)
    grid_data = []
    row = []
    
    # กำหนดขนาดรูปภาพใน PDF (กว้าง 260px, สูง 195px เพื่อให้อยู่ในหน้า A4 สวยงาม)
    target_width = 260
    target_height = 195

    for idx, img_bytes in enumerate(compressed_photos):
        rl_img = RLImage(img_bytes, width=target_width, height=target_height)
        
        # ใส่รูปและป้ายกำกับลำดับรูป
        cell_content = [
            rl_img,
            Paragraph(f"<font size=9 color='#64748b'>Photo #{idx+1}</font>", info_style)
        ]
        row.append(cell_content)

        if len(row) == 2:
            grid_data.append(row)
            row = []

    # หากมีรูปเศษเหลือ 1 รูปในแถบสุดท้าย
    if row:
        row.append("") # ใส่ช่องว่างให้ครบ 2 คอลัมน์
        grid_data.append(row)

    # สร้าง Table สำหรับรูปภาพ
    if grid_data:
        photo_table = Table(grid_data, colWidths=[270, 270])
        photo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(photo_table)

    # 4. สร้างไฟล์ PDF
    doc.build(story)