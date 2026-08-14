import os
import uuid

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

from analyze import analyze_audio
import db

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"webm", "ogg", "wav", "mp3", "m4a", "mp4", "aac", "flac"}

app = Flask(__name__)
app.secret_key = "dev-secret-not-for-prod"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB per submission


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    audio_file = request.files.get("audio")

    if not name or not phone:
        flash("Name and phone number are both required.")
        return redirect(url_for("index"))
    if not audio_file or audio_file.filename == "":
        flash("Please record or upload an audio clip.")
        return redirect(url_for("index"))

    orig_name = audio_file.filename
    ext = orig_name.rsplit(".", 1)[-1].lower() if "." in orig_name else "webm"
    if ext not in ALLOWED_EXT:
        ext = "webm"  # browser MediaRecorder blobs often arrive without a clean extension

    saved_name = f"{uuid.uuid4()}.{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)
    audio_file.save(saved_path)

    try:
        props = analyze_audio(saved_path)
    except Exception as e:
        db.save_submission({
            "person_id": None,
            "submitted_name": name,
            "submitted_phone": phone,
            "file_path": saved_path,
            "original_filename": orig_name,
            "status": "failed",
        })
        flash(f"Audio saved, but we couldn't analyze it (unsupported/corrupt file?): {e}")
        return redirect(url_for("index"))

    person_id = None
    try:
        person_id = db.find_or_create_person(name, phone)
    except Exception:
        pass  # linking to Task 1's people table is best-effort; submission still gets saved

    db.save_submission({
        "person_id": person_id,
        "submitted_name": name,
        "submitted_phone": phone,
        "file_path": saved_path,
        "original_filename": orig_name,
        "duration_seconds": props["duration_seconds"],
        "sample_rate_hz": props["sample_rate_hz"],
        "bitrate_kbps": props["bitrate_kbps"],
        "loudness_db": props["loudness_db"],
        "noise_estimate": props["noise_estimate"],
        "status": "processed",
    })

    flash("Thanks! Your recording was submitted and analyzed.")
    return redirect(url_for("submissions"))


@app.route("/submissions")
def submissions():
    rows = db.list_submissions()
    return render_template("submissions.html", rows=rows)


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    print(f"Storage backend: {'Supabase' if db.USE_SUPABASE else 'local SQLite (local.db)'}")
    # use_reloader=False: the reloader's file-watcher otherwise restarts the
    # server every time local.db or uploads/ change (i.e. on every submission)
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5050)
