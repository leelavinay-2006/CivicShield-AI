from pathlib import Path
import os
import sqlite3
import uuid
import secrets

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DATABASE = BASE_DIR / "civicshield.db"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

CATEGORIES = [
    "Pothole / Road Damage",
    "Garbage / Illegal Dumping",
    "Blocked Drain / Waterlogging",
    "Water Leakage",
    "Broken Streetlight / Damaged Infrastructure",
]

LANGUAGES = {"English", "Telugu", "Hindi", "Other"}


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_code TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                language TEXT NOT NULL,
                location TEXT NOT NULL,
                image_filename TEXT,
                status TEXT NOT NULL DEFAULT 'Submitted',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/report", methods=["GET", "POST"])
def report():
    if request.method == "GET":
        return render_template("report.html", categories=CATEGORIES)

    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    language = request.form.get("language", "").strip()
    location = request.form.get("location", "").strip()

    image = request.files.get("image")
    image_filename = None

    if category not in CATEGORIES:
        flash("Please choose a valid issue category.", "error")
        return redirect(url_for("report"))

    if not description or len(description) < 5:
        flash("Please enter a description of at least 5 characters.", "error")
        return redirect(url_for("report"))

    if language not in LANGUAGES:
        flash("Please choose a valid language.", "error")
        return redirect(url_for("report"))

    if not location:
        flash("Please enter a general location.", "error")
        return redirect(url_for("report"))

    if image and image.filename:
        if not allowed_file(image.filename):
            flash(
                "Unsupported image format. Use PNG, JPG, JPEG, or WEBP.",
                "error",
            )
            return redirect(url_for("report"))

        safe_name = secure_filename(image.filename)

        if not safe_name or "." not in safe_name:
            flash("Invalid image filename.", "error")
            return redirect(url_for("report"))

        extension = safe_name.rsplit(".", 1)[1].lower()
        image_filename = f"{uuid.uuid4().hex}.{extension}"

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        image.save(UPLOAD_DIR / image_filename)

    report_code = f"CS-{uuid.uuid4().hex[:8].upper()}"

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO reports (
                    report_code,
                    category,
                    description,
                    language,
                    location,
                    image_filename
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report_code,
                    category,
                    description,
                    language,
                    location,
                    image_filename,
                ),
    )
    except sqlite3.Error:
        app.logger.exception("Could not save the report")
        flash("Unable to save your report. Please try again.", "error")
        return redirect(url_for("report"))

    flash(
        f"Report submitted successfully. Your reference ID is {report_code}.",
        "success",
    )
    return redirect(url_for("reports"))


@app.route("/reports")
def reports():
    with get_connection() as connection:
        all_reports = connection.execute(
            """
            SELECT *
            FROM reports
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return render_template("reports.html", reports=all_reports)


@app.errorhandler(413)
def file_too_large(_error):
    flash("Image is too large. The maximum allowed size is 5 MB.", "error")
    return redirect(url_for("report"))


initialize_database()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )