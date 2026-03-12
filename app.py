from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from faster_whisper import WhisperModel
from gtts import gTTS

import os
import uuid
import serial
import time
import random
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===============================
# DATABASE CONFIG
# ===============================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "robovoice"
}

mysql_conn = None

def get_db_connection():
    global mysql_conn
    try:
        if mysql_conn is None or not mysql_conn.is_connected():
            mysql_conn = mysql.connector.connect(**DB_CONFIG)
        return mysql_conn
    except mysql.connector.Error as e:
        print("DB ERROR:", e)
        return None

def get_cursor():
    conn = get_db_connection()
    if conn:
        return conn.cursor()
    return None

# ===============================
# OTP STORAGE
# ===============================

otp_store = {}

# ===============================
# EMAIL CONFIG
# ===============================

EMAIL_ADDRESS = "rajurajesh89787@gmail.com"
EMAIL_PASSWORD = "ogfxrnwislikxefn"

def send_otp_email(receiver_email, otp):

    subject = "RoboVoice Password Reset OTP"

    body = f"""
Hello,

Your OTP for password reset is:

{otp}

Do not share this OTP with anyone.

- RoboVoice System
"""

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = receiver_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, receiver_email, msg.as_string())
        server.quit()

        print("OTP email sent")

    except Exception as e:
        print("Email send error:", e)

# ===============================
# ROBOT SERIAL CONFIG
# ===============================

SERIAL_PORT = "COM5"
BAUD_RATE = 9600

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print("Robot connected")
except:
    ser = None
    print("Robot not connected")

def send_command(cmd):

    if ser and ser.is_open:
        ser.write(cmd.encode())

        cur = get_cursor()
        if cur:
            cur.execute(
                "INSERT INTO command_history(command) VALUES(%s)",
                (cmd,)
            )
            get_db_connection().commit()

        return True

    return False

# ===============================
# WHISPER MODEL
# ===============================

model = None

def get_model():
    global model
    if model is None:
        print("Loading Whisper model...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Model loaded")
    return model

# ===============================
# SERVER STATUS
# ===============================

@app.route("/")
def home():
    return jsonify({"server": "RoboVoice backend running"})

# ===============================
# SIGNUP
# ===============================

@app.route("/signup", methods=["POST"])
def signup():

    data = request.get_json()
    cur = get_cursor()

    try:
        cur.execute(
            "INSERT INTO users(full_name,email,password) VALUES(%s,%s,%s)",
            (data["full_name"], data["email"], data["password"]),
        )
        get_db_connection().commit()

        return jsonify({"message": "Signup successful"})

    except mysql.connector.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400

# ===============================
# LOGIN
# ===============================

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()
    cur = get_cursor()

    cur.execute(
        "SELECT id,email,password FROM users WHERE email=%s",
        (data["email"],)
    )

    user = cur.fetchone()

    if user and user[2] == data["password"]:
        return jsonify({
            "status": "success",
            "user": {
                "id": user[0],
                "email": user[1]
            }
        })

    return jsonify({"error": "Invalid email or password"}), 401

# ===============================
# CHANGE PASSWORD
# ===============================

@app.route("/change-password", methods=["POST"])
def change_password():

    data = request.get_json()
    cur = get_cursor()

    cur.execute(
        "SELECT password FROM users WHERE email=%s",
        (data["email"],)
    )

    user = cur.fetchone()

    if user and user[0] == data["current_password"]:

        cur.execute(
            "UPDATE users SET password=%s WHERE email=%s",
            (data["new_password"], data["email"])
        )

        get_db_connection().commit()

        return jsonify({"message": "Password changed"})

    return jsonify({"error": "Wrong password"}), 400

# ===============================
# FORGOT PASSWORD
# ===============================

@app.route("/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json()
    cur = get_cursor()

    cur.execute("SELECT email FROM users WHERE email=%s", (data["email"],))
    user = cur.fetchone()

    if not user:
        return jsonify({"error": "Email not found"}), 404

    otp = str(random.randint(100000, 999999))
    otp_store[data["email"]] = otp

    send_otp_email(data["email"], otp)

    return jsonify({"message": "OTP sent to email"})

# ===============================
# VERIFY OTP
# ===============================

@app.route("/verify-otp", methods=["POST"])
def verify_otp():

    data = request.get_json()

    if data["email"] not in otp_store:
        return jsonify({"error": "OTP not requested"}), 400

    if otp_store[data["email"]] != data["otp"]:
        return jsonify({"error": "Invalid OTP"}), 400

    return jsonify({"message": "OTP verified"})

# ===============================
# RESET PASSWORD
# ===============================

@app.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json()

    if data["email"] not in otp_store:
        return jsonify({"error": "OTP not verified"}), 400

    cur = get_cursor()

    cur.execute(
        "UPDATE users SET password=%s WHERE email=%s",
        (data["new_password"], data["email"])
    )

    get_db_connection().commit()

    otp_store.pop(data["email"])

    return jsonify({"message": "Password reset successful"})

# ===============================
# ROBOT MOVE
# ===============================

@app.route("/move", methods=["POST"])
def move():

    direction_map = {
        "forward": "F",
        "backward": "B",
        "left": "L",
        "right": "R",
        "stop": "S"
    }

    direction = request.get_json().get("direction")

    if direction not in direction_map:
        return jsonify({"error": "Invalid direction"}), 400

    if send_command(direction_map[direction]):
        return jsonify({"message": "Command sent"})

    return jsonify({"error": "Robot not connected"}), 500

# ===============================
# TERMINAL
# ===============================

# @app.route("/terminal", methods=["POST"])
# def terminal():

#     command = request.get_json().get("command")

#     if send_command(command):
#         return jsonify({"message": "Command executed"})

#     return jsonify({"error": "Robot not connected"}), 500

# ===============================
# DEVICE STATUS
# ===============================

@app.route("/device-status")
def device_status():

    return jsonify({
        "device": "connected" if ser and ser.is_open else "disconnected"
    })

# ===============================
# COMMAND HISTORY
# ===============================
def interpret_command(text):
    
    if not text:
        return None

    text = text.lower()

    if "forward" in text:
        return "F"

    elif "back" in text or "backward" in text:
        return "B"

    elif "left" in text:
        return "L"

    elif "right" in text:
        return "R"

    elif "stop" in text:
        return "S"

    return None

@app.route("/terminal", methods=["POST"])
def terminal():

    data = request.get_json()

    voice_text = data.get("command")

    robot_command = interpret_command(voice_text)

    if robot_command is None:
        return jsonify({"error": "Command not recognized"}), 400

    send_command(robot_command)

    return jsonify({
        "voice_command": voice_text,
        "robot_command": robot_command,
        "message": "Command executed"
    })

# ===============================
# VOICE TO TEXT
# ===============================

@app.route("/voice-to-text", methods=["POST"])
def voice_to_text():

    model = get_model()

    if "audio" not in request.files:
        return jsonify({"error": "No audio uploaded"}), 400

    audio = request.files["audio"]

    filename = str(uuid.uuid4()) + ".wav"
    path = os.path.join(UPLOAD_FOLDER, filename)

    audio.save(path)

    segments, _ = model.transcribe(path)

    text = " ".join([s.text.strip() for s in segments])

    return jsonify({"text": text})

# ===============================
# TEXT TO VOICE
# ===============================

@app.route("/text-to-voice", methods=["POST"])
def text_to_voice():

    text = request.get_json().get("text")

    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    gTTS(text=text, lang="en").save(filepath)

    return jsonify({"file": filename})

# ===============================
# MAIN
# ===============================

if __name__ == "__main__":

    print("RoboVoice Backend Started")

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    