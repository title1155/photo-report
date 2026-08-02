from flask import Flask, render_template, request, send_file
from PIL import Image

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create_pdf():

    files = request.files.getlist("photos")

    if len(files) == 0:
        return "กรุณาเลือกไฟล์"

    canvas = Image.new("RGB", (2480, 3508), "white")

    positions = [
        (0, 0),
        (1240, 0),
        (0, 1754),
        (1240, 1754)
    ]

    for i, file in enumerate(files[:4]):

        img = Image.open(file).convert("RGB")

        img.thumbnail((1200, 1700))

        canvas.paste(img, positions[i])

    pdf_name = "Photo_Report.pdf"

    canvas.save(pdf_name, "PDF")

    return send_file(
        pdf_name,
        as_attachment=True
    )

if __name__ == "__main__":
    app.run(debug=True)