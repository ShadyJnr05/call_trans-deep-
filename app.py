from flask import Flask, request, jsonify, send_file, session, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from deep_translator import GoogleTranslator
import requests, time, os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this in production

# --- DATABASE SETUP ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///soundscript.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    transcripts = db.relationship("Transcript", backref="user", lazy=True)

class Transcript(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), default="en")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

with app.app_context():
    db.create_all()

# --- ASSEMBLYAI CONFIG ---
ASSEMBLYAI_API_KEY = "ae9805d3abda4566bf6221dbdf98699f"

def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"status": "error", "message": "You must be logged in to perform this action."})
        return func(*args, **kwargs)
    return wrapper


def transcribe_with_assemblyai(audio_file):
    """Handles upload and transcription via AssemblyAI"""
    headers = {"authorization": ASSEMBLYAI_API_KEY}

    # Step 1: Upload audio
    upload_response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, data=audio_file)
    if upload_response.status_code != 200:
        raise Exception("Audio upload failed.")
    audio_url = upload_response.json()["upload_url"]

    # Step 2: Start transcription
    transcript_response = requests.post("https://api.assemblyai.com/v2/transcript", headers=headers, json={"audio_url": audio_url})
    if transcript_response.status_code != 200:
        raise Exception("Failed to start transcription.")
    transcript_id = transcript_response.json()["id"]

    # Step 3: Poll until done
    while True:
        polling_response = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
        status = polling_response.json()["status"]
        if status == "completed":
            return polling_response.json()["text"]
        elif status == "error":
            raise Exception(polling_response.json().get("error", "Transcription failed."))
        time.sleep(3)


@app.route("/")
def index():
    return render_template("index.html")


# --- AUTH ROUTES ---
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status": "error", "message": "Please fill in all fields."})
    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Username already exists."})

    new_user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"status": "success", "message": "Signup successful! Please login."})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"status": "error", "message": "Invalid username or password."})

    session["user_id"] = user.id
    session["username"] = user.username
    return jsonify({"status": "success", "message": f"Welcome back, {user.username}!"})


# --- UPLOAD & TRANSCRIBE ---
@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."})

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected."})

    try:
        transcription = transcribe_with_assemblyai(file)
        new_t = Transcript(text=transcription, user_id=session["user_id"])
        db.session.add(new_t)
        db.session.commit()
        return jsonify({"status": "success", "transcript": transcription})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# --- TRANSLATE ---
@app.route("/translate", methods=["POST"])
@login_required
def translate_text():
    data = request.get_json()
    transcript = data.get("transcript", "")
    target_lang = data.get("target_lang", "en")

    if not transcript:
        return jsonify({"status": "error", "message": "No transcript to translate."})

    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(transcript)
        return jsonify({"status": "success", "translation": translated})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# --- DOWNLOAD ---
@app.route("/download", methods=["GET"])
@login_required
def download_transcript():
    user = User.query.get(session["user_id"])
    last_t = Transcript.query.filter_by(user_id=user.id).order_by(Transcript.id.desc()).first()
    if not last_t:
        return jsonify({"status": "error", "message": "No transcript available to download."})

    filename = "transcript.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(last_t.text)
    return send_file(filename, as_attachment=True)


# --- OPTIONAL: View History ---
@app.route("/history", methods=["GET"])
@login_required
def history():
    user = User.query.get(session["user_id"])
    data = [{"id": t.id, "text": t.text[:100] + "...", "language": t.language} for t in user.transcripts]
    return jsonify({"status": "success", "history": data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
