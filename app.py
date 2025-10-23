from flask import Flask, request, jsonify, send_file, session, render_template
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import time
from deep_translator import GoogleTranslator
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ✅ Database setup
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///soundscript.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# 🧠 Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Transcript(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), default="en")

# 🔑 AssemblyAI API Key
ASSEMBLYAI_API_KEY = "ae9805d3abda4566bf6221dbdf98699f"

# Create tables before first request
@app.before_first_request
def create_tables():
    db.create_all()
