from flask import Flask, request, jsonify, send_file, session, render_template
import os
import requests
import time
from deep_translator import GoogleTranslator
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"  # You can make this random for production

latest_transcript = ""
users = {}

# Use your AssemblyAI API key directly
ASSEMBLYAI_API_KEY = "ae9805d3abda4566bf6221dbdf98699f"

def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"status": "error", "message": "You must be logged in to perform this action."})
        return func(*args, **kwargs)
    return wrapper

def transcribe_with_assemblyai(audio_file):
    """Transcribe using AssemblyAI API"""
    headers = {"authorization": ASSEMBLYAI_API_KEY}
    # Step 1: Upload audio
    upload_response = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers=headers,
        data=audio_file.read()
    )
    if upload_response.status_code != 200:
        raise Exception(f"Upload failed: {upload_response.json()}")
    audio_url = upload_response.json()["upload_url"]

    # Step 2: Start transcription
    transcript_response = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=headers,
        json={"audio_url": audio_url}
    )
    if transcript_response.status_code != 200:
        raise Exception(f"Transcription start failed: {transcript_response.json()}")
    transcript_id = transcript_response.json()["id"]

    # Step 3: Poll for completion
    while True:
        polling_response = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers=headers
        )
        status = polling_response.json()["status"]
        if status == "completed":
            return polling_response.json()["text"]
        elif status == "error":
            raise Exception(f"Transcription failed: {polling_response.json().get('error','Unknown error')}")
        else:
            time.sleep(3)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username in users:
        return jsonify({"status": "error", "message": "Username already exists."})
    users[username] = generate_password_hash(password)
    return jsonify({"status": "success", "message": "Signup successful! Please login."})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username not in users or not check_password_hash(users[username], password):
        return jsonify({"status": "error", "message": "Invalid username or password."})
    session['user'] = username
    return jsonify({"status": "success", "message": f"Logged in as {username}."})

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    global latest_transcript
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"})
    try:
        transcription = transcribe_with_assemblyai(file)
        latest_transcript = transcription
        return jsonify({
            "status": "success",
            "message": "Transcription completed!",
            "transcript": transcription
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/translate', methods=['POST'])
@login_required
def translate_text():
    global latest_transcript
    data = request.get_json()
    transcript = data.get("transcript", latest_transcript)
    target_lang = data.get("target_lang", "en")
    if not transcript:
        return jsonify({"status": "error", "message": "Transcript is empty."})
    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(transcript)
        latest_transcript = translated
        return jsonify({"status": "success", "translation": translated})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/download', methods=['GET'])
@login_required
def download_transcript():
    global latest_transcript
    if not latest_transcript:
        return jsonify({"status": "error", "message": "No transcript available to download."})
    filename = "transcript.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(latest_transcript)
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
