import os
from flask import Flask, render_template, send_from_directory, request
from hotpress import process_hotpress
from inspection import process_inspection

app = Flask(__name__, template_folder='templates')
OUTPUT_DIR = "generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/hotpress")
def hotpress_page():
    return render_template("hotpress.html")

@app.route("/hotpress/create", methods=["POST"])
def hotpress_create():
    return process_hotpress(request)

@app.route("/inspection")
def inspection_page():
    return render_template("inspection.html")

@app.route("/inspection/create", methods=["POST"])
def inspection_create():
    return process_inspection(request)

@app.route("/result")
def result():
    filename = request.args.get("filename", "")
    status = request.args.get("status", "")
    return render_template("result.html", filename=filename, status=status)

@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)