import os
from flask import Flask, render_template, request, send_file, url_for
from hotpress import process_hotpress
from inspection import process_inspection

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # Limit 64MB

OUTPUT_DIR = "generated"


@app.route("/")
def index():
    return render_template("index.html")


# --- Hot Press Report ---
@app.route("/hotpress")
def hotpress_form():
    return render_template("hotpress.html")


@app.route("/hotpress/create", methods=["POST"])
def hotpress_create():
    return process_hotpress(request)


# --- Inspection Report ---
@app.route("/inspection")
def inspection_form():
    return render_template("inspection.html")


@app.route("/inspection/create", methods=["POST"])
def inspection_create():
    return process_inspection(request)


# --- Shared Result & Download ---
@app.route("/result/<filename>")
def result(filename):
    status = request.args.get("status", "")
    file_url = url_for("download", filename=filename, _external=True)
    return render_template(
        "result.html", filename=filename, status=status, file_url=file_url
    )


@app.route("/download/<filename>")
def download(filename):
    pdf_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(pdf_path):
        return "ไม่พบไฟล์ที่ต้องการดาวน์โหลด", 404

    response = send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=filename,
    )
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


if __name__ == "__main__":
    app.run(debug=True)