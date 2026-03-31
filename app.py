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
import re

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
        # If conn exists, try pinging it to ensure it's alive
        if mysql_conn and mysql_conn.is_connected():
            try:
                mysql_conn.ping(reconnect=True, attempts=3, delay=1)
                return mysql_conn
            except:
                pass # reconnect below
        
        # Connect with auto-reconnect
        mysql_conn = mysql.connector.connect(**DB_CONFIG)
        return mysql_conn
    except mysql.connector.Error as e:
        print(f"CRITICAL DB ERROR: {e}")
        raise e

def get_cursor(dictionary=False):
    conn = get_db_connection()
    if conn:
        return conn.cursor(dictionary=dictionary)
    return None

@app.route("/db-health")
def db_health():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SHOW TABLES")
        tables = cur.fetchall()
        
        cur.execute("DESCRIBE users")
        columns = cur.fetchall()
        
        return jsonify({
            "status": "connected",
            "database": DB_CONFIG["database"],
            "tables": tables,
            "users_schema": columns
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "config": {k: v for k, v in DB_CONFIG.items() if k != "password"}
        }), 500

# ===============================
# OTP STORAGE
# ===============================

otp_store = {}

# ===============================
# EMAIL CONFIG
# ===============================

EMAIL_ADDRESS = "rajurajesh89787@gmail.com"
EMAIL_PASSWORD = "klswanmrhhhaxzfq"

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
        print(f"Connecting to SMTP server for {receiver_email}...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.set_debuglevel(1)  # Enable debug logic to see SMTP traffic in console
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, receiver_email, msg.as_string())
        server.quit()

        print(f"✅ OTP email sent successfully to {receiver_email}")
        return True

    except Exception as e:
        print(f"❌ Email send error for {receiver_email}: {e}")
        return False

import serial
import serial.tools.list_ports
import time

# ===============================
# ROBOT SERIAL CONFIG
# ===============================

SERIAL_PORT = "COM5"
BAUD_RATE = 115200

ser = None

VALID_COMMANDS = ["forward", "back", "backward", "left", "right", "stop", "f", "b", "l", "r", "s", "u", "d", "U", "D", "F", "B", "L", "R", "S"]


# ===============================
# CONNECT FUNCTION
# ===============================

def connect_robot(port=None):
    global ser, SERIAL_PORT
    
    target_port = port if port else SERIAL_PORT
    baud = 115200 # Default for ESP32

    try:
        if ser and ser.is_open:
            ser.close()
            
        ser = serial.Serial(target_port, baud, timeout=1)
        time.sleep(2)  # allow ESP32 reset
        print(f"✅ Robot connected on {target_port}")
        return True
    except Exception as e:
        ser = None
        print(f"❌ Robot connection failed on {target_port}: {e}")
        return False


# ===============================
# SEND COMMAND FUNCTION
# ===============================

def send_command(cmd, user_id=None):
    global ser

    cmd = cmd.strip().lower()

    # 🚫 Validate command
    if cmd not in VALID_COMMANDS:
        print("⚠️ Invalid command:", cmd)
        return {"status": "error", "message": "Invalid command"}

    try:
        # 🔄 Reconnect if needed
        if ser is None or not ser.is_open:
            print("⚠️ Serial not open, reconnecting...")
            connect_robot()

        if ser and ser.is_open:
            print("➡️ Sending command:", cmd)

            # Send command with newline
            ser.write((cmd + "\n").encode())

            # ⏳ Wait for ESP32 response
            time.sleep(0.3)

            response = ""

            while ser.in_waiting:
                line = ser.readline().decode(errors='ignore').strip()
                if line:
                    response += line + " "

            response = response.strip()

            print("⬅️ Response:", response)

            # 💾 Save to DB safely (command_history)
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                if cur and conn:
                    cur.execute(
                        "INSERT INTO command_history(user_id, command, response) VALUES(%s, %s, %s)",
                        (user_id, cmd, response)
                    )
                    conn.commit()
                    cur.close()
                    print(f"--- SUCCESS: Logged to command_history: {cmd}")
            except Exception as db_error:
                print(f"--- ERROR: DB error in send_command: {db_error}")

            return {
                "status": "success",
                "command": cmd,
                "response": response
            }

        else:
            raise Exception("Serial not available")

    except Exception as e:
        print("❌ Send failed:", e)
        return {
            "status": "error",
            "message": str(e)
        }

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

def is_valid_password(password):
    if not password or len(password) < 8:
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[^a-zA-Z0-9]', password):
        return False
    return True

def is_valid_email(email):
    if not email:
        return False
    return re.match(r"^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email) is not None

def is_valid_name(name):
    if not name:
        return False
    return re.match(r"^[A-Za-z]+$", name) is not None

def is_valid_phone(phone):
    if not phone:
        return False
    return re.match(r"^\d{10}$", str(phone)) is not None

@app.route("/signup", methods=["POST"])
def signup():

    data = request.get_json()
    password = data.get("password")
    email = data.get("email")
    full_name = data.get("full_name")
    
    if not is_valid_email(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
        
    if not is_valid_name(full_name):
        return jsonify({"error": "Full Name can only contain letters without spaces."}), 400
    
    phone = data.get("phone")
    if phone and str(phone).strip() != "":
        if not is_valid_phone(phone):
            return jsonify({"error": "Phone number must be exactly 10 digits."}), 400

    if not is_valid_password(password):
        return jsonify({"error": "Password must be at least 8 characters and contain 1 uppercase, 1 lowercase, and 1 special character."}), 400

    try:
        conn = get_db_connection()
        if not conn:
             return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

    try:
        cur.execute("""
            INSERT INTO users 
            (full_name, email, password, phone, location, otp_verified)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data.get("full_name"),
            data.get("email"),
            data.get("password"),
            data.get("phone", ""),       # avoid NULL
            data.get("location", ""),    # avoid NULL
            0
        ))

        conn.commit()

        return jsonify({"message": "Signup successful"})

    except mysql.connector.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400

# ===============================
# LOGIN
# ===============================

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

    cur.execute(
        "SELECT id,email,password FROM users WHERE email=%s",
        (data["email"],)
    )

    user = cur.fetchone()

    if user and user[2] == data["password"]:
        return jsonify({
            "status": "success",
            "user": {
                "id": str(user[0]),
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
    new_password = data.get("new_password")
    
    if not is_valid_password(new_password):
        return jsonify({"error": "Password must be at least 8 characters and contain 1 uppercase, 1 lowercase, and 1 special character."}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

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

#---------------get profile------------
@app.route("/profile", methods=["GET"])
def get_profile():
    email = request.args.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
        
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, full_name as name, email, phone, location, profile_photo FROM users WHERE LOWER(TRIM(email))=%s", (email.strip().lower(),))
    user = cur.fetchone()
    
    if user:
        return jsonify(user)
        
    return jsonify({"error": "User not found"}), 404

#---------------update profile------------
@app.route("/update-profile", methods=["POST"])
def update_profile():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON received"}), 400

        print("Incoming Data:", data)

        # ✅ Email check
        email = data.get("email")
        if not is_valid_email(email):
            return jsonify({"error": "Please enter a valid email address."}), 400

        email = email.strip().lower()

        # ✅ DB connection
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "DB connection failed"}), 500

        cur = conn.cursor(dictionary=True)

        # ✅ Get user
        cur.execute("SELECT * FROM users WHERE LOWER(TRIM(email))=%s", (email,))
        user = cur.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # ===============================
        # 🔥 FIXED FIELD HANDLING
        # ===============================

        full_name = data.get("full_name")
        if full_name and str(full_name).strip() != "":
            if not is_valid_name(full_name):
                return jsonify({"error": "Full Name can only contain letters without spaces."}), 400
        else:
            full_name = user.get("full_name") or ""

        phone = data.get("phone")
        if phone and str(phone).strip() != "":
            if not is_valid_phone(phone):
                return jsonify({"error": "Phone number must be exactly 10 digits."}), 400
        else:
            phone = user.get("phone") or ""

        location = data.get("location")
        if not location or location.strip() == "":
            location = user.get("location") or ""

        profile_photo = data.get("profile_photo")
        if not profile_photo or str(profile_photo).strip() == "":
            profile_photo = user.get("profile_photo") or ""

        print("Final Values:", full_name, phone, location)

        # ===============================
        # ✅ UPDATE QUERY
        # ===============================

        cur.execute("""
            UPDATE users
            SET 
                full_name=%s,
                phone=%s,
                location=%s,
                profile_photo=%s
            WHERE LOWER(TRIM(email))=%s
        """, (full_name, phone, location, profile_photo, email))

        conn.commit()

        print("Rows updated:", cur.rowcount)

        return jsonify({"message": "Profile updated successfully"})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
# ===============================
# FORGOT PASSWORD
# ===============================

from datetime import datetime, timedelta

@app.route("/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json()
    email = data.get("email")

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

    cur.execute("SELECT email FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    user = cur.fetchone()

    if not user:
        return jsonify({"error": "Email not found"}), 404

    print(f"Attempting to generate OTP for: {email}")

    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=5)

    print(f"Generated OTP: {otp} for {email}")

    print(f"Calling send_otp_email for {email}...")
    send_success = send_otp_email(email, otp)
    print(f"send_otp_email result: {send_success}")

    try:
        cur.execute("""
            UPDATE users 
            SET otp=%s, otp_expiry=%s, otp_verified=0
            WHERE LOWER(email)=LOWER(%s)
        """, (otp, expiry, email))

        conn.commit()
        print(f"Database update rows affected: {cur.rowcount}")

        if cur.rowcount == 0:
            print(f"⚠️ Warning: No row found for email {email}. OTP not saved in DB.")
            return jsonify({"error": "Email not found in database record"}), 404

    except Exception as db_err:
        print(f"❌ Database update error: {db_err}")
        return jsonify({"error": f"Database error: {str(db_err)}"}), 500

    if not send_success:
        print("❌ Returning 500: OTP generated but failed to send email.")
        return jsonify({"message": "OTP generated but failed to send email. Please check server console for SMTP errors."}), 500

    print("✅ Returning 200: OTP sent.")
    return jsonify({"message": "OTP sent successfully"})
# ===============================
# VERIFY OTP
# ===============================
@app.route("/verify-otp", methods=["POST"])
def verify_otp():

    data = request.get_json()
    email = data.get("email")
    user_otp = data.get("otp")

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

    cur.execute("SELECT otp, otp_expiry FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    user = cur.fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    db_otp = str(user[0])
    db_expiry = user[1]

    print("DB OTP:", db_otp)
    print("User OTP:", user_otp)

    if db_otp != str(user_otp):
        return jsonify({"error": "Invalid OTP"}), 400

    if datetime.now() > db_expiry:
        return jsonify({"error": "OTP expired"}), 400

    # ✅ mark verified
    cur.execute("""
        UPDATE users 
        SET otp_verified=1 
        WHERE LOWER(email)=LOWER(%s)
    """, (email,))

    conn.commit()

    print("OTP verified updated:", cur.rowcount)

    return jsonify({"message": "OTP verified"})


@app.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json()
    email = data.get("email")
    new_password = data.get("new_password")
    
    if not is_valid_password(new_password):
        return jsonify({"error": "Password must be at least 8 characters and contain 1 uppercase, 1 lowercase, and 1 special character."}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

    cur.execute("SELECT otp_verified FROM users WHERE LOWER(email)=LOWER(%s)", (email,))
    user = cur.fetchone()

    if not user or user[0] != 1:
        return jsonify({"error": "OTP not verified"}), 400

    # ✅ Only update password (DO NOT TOUCH OTP)
    cur.execute("""
        UPDATE users 
        SET password=%s
        WHERE LOWER(email)=LOWER(%s)
    """, (new_password, email))

    conn.commit()

    print("Rows updated:", cur.rowcount)

    return jsonify({"message": "Password reset successful"})


# ===============================
# ROBOT MOVE
# ===============================

@app.route("/move", methods=["POST"])
def move():
    data = request.get_json()
    direction_map = {
        "forward": "F",
        "backward": "B",
        "left": "L",
        "right": "R",
        "stop": "S"
    }

    direction = data.get("direction")
    user_id = data.get("user_id")

    if direction not in direction_map:
        return jsonify({"error": "Invalid direction"}), 400

    cmd = direction_map[direction]
    res = send_command(cmd, user_id)
    
    if res.get("status") == "success":
        return jsonify({"message": "Command sent", "robot_response": res.get("response")})

    return jsonify({"error": res.get("message") or "Robot not connected"}), 500

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

@app.route("/available-ports")
def get_available_ports():
    ports = serial.tools.list_ports.comports()
    return jsonify([
        {"port": p.device, "description": p.description} 
        for p in ports
    ])

@app.route("/connect-device", methods=["POST"])
def connect_device():
    data = request.get_json()
    port = data.get("port")
    
    if connect_robot(port):
        return jsonify({"status": "success", "message": f"Connected to robot on {port or SERIAL_PORT}"})
    
    return jsonify({
        "status": "error", 
        "error": f"Failed to connect to {port or SERIAL_PORT}. Check if robot is plugged in and you selected the correct port."
    })

@app.route("/device-status")
def device_status():
    return jsonify({
        "device": "connected" if ser and ser.is_open else "disconnected"
    })

@app.route("/robot/battery")
def get_battery():
    # Since robot firmare only supports basic movement commands currently,
    # we return a static 100% when connected.
    if ser and ser.is_open:
        return jsonify({"level": 100, "status": "Real-time"})
    return jsonify({"level": 0, "status": "Offline"})

# ===============================
# COMMAND HISTORY
# ===============================
def interpret_command(text):
    text = text.lower().strip()

    # Move Forward variations
    if any(phrase in text for phrase in ["forward", "move forward", "go forward", "straight", "front"]):
        return "F"
    # Move Backward variations
    elif any(phrase in text for phrase in ["back", "backward", "move back", "go back", "reverse"]):
        return "B"
    # Turn Left variations
    elif any(phrase in text for phrase in ["left", "turn left", "go left"]):
        return "L"
    # Turn Right variations
    elif any(phrase in text for phrase in ["right", "turn right", "go right"]):
        return "R"
    # Stop variations
    elif any(phrase in text for phrase in ["stop", "halt", "wait", "freeze", "s"]):
        return "S"
    
    # Speed variations
    elif any(phrase in text for phrase in ["speed up", "increase speed", "faster", "go faster", "more speed", "u"]):
        return "U"
    elif any(phrase in text for phrase in ["slow down", "decrease speed", "slower", "go slower", "less speed", "d"]):
        return "D"

    # Direct code handling (in case raw F, B, L, R, S, U, D are sent)
    if text.upper() in ["F", "B", "L", "R", "S", "U", "D"]:
        return text.upper()

    return None



@app.route("/terminal", methods=["POST"])
def terminal():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    voice_text = data.get("command")
    if not voice_text:
        return jsonify({"error": "No command provided"}), 400

    user_id = data.get("user_id")
    if not user_id or str(user_id).strip() == "":
        user_id = None
        
    print(f"Received terminal command: '{voice_text}' (user_id: {user_id})")
    robot_command = interpret_command(voice_text)
    response = ""
    
    if not robot_command:
        response = f"I heard '{voice_text}', but I don't know that command yet."
        print(f"⚠️ {response}")
    else:
        try:
            print(f"Sending interpreted command to robot: {robot_command} (user_id: {user_id})")
            cmd_res = send_command(robot_command, user_id)
            if cmd_res.get("status") == "success":
                response = f"Command '{robot_command}' executed successfully"
            else:
                # If serial is not available, provide a simulation response for the submission
                error_msg = cmd_res.get("message", "")
                if "Serial not available" in error_msg or "not open" in error_msg:
                    response = f"Command '{robot_command}' sent (Simulated: Robot offline)"
                else:
                    response = error_msg or "Robot command failed"
        except Exception as e:
            print(f"Robot execution error: {e}")
            response = f"Error: {str(e)}"

    # 💾 Save to DB safely (terminal_logs) - Non-blocking for the API response
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if cursor and conn:
            cursor.execute(
                "INSERT INTO terminal_logs (user_id, command_text, response_text) VALUES (%s, %s, %s)",
                (user_id, voice_text, response)
            )
            conn.commit()
            cursor.close()
    except Exception as db_err:
        print(f"--- DB ERROR (terminal_logs): {db_err}")

    return jsonify({
        "voice_command": voice_text,
        "robot_command": robot_command,
        "response": response,
        "success": robot_command is not None and "Error" not in response and "failed" not in response.lower()
    })

@app.route("/terminal/logs", methods=["GET"])
def get_terminal_logs():
    user_id = request.args.get("user_id")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Fetch last 50 commands for this user
        if user_id:
            cursor.execute("SELECT id, command_text as text, response_text as status_msg, created_at FROM terminal_logs WHERE user_id = %s ORDER BY created_at DESC LIMIT 50", (user_id,))
        else:
            cursor.execute("SELECT id, command_text as text, response_text as status_msg, created_at FROM terminal_logs ORDER BY created_at DESC LIMIT 50")
            
        logs = cursor.fetchall()
        
        # Transform for frontend format
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                "id": str(log["id"]),
                "text": log["text"],
                "response": log["status_msg"] or "",
                "status": "success" if "success" in (log["status_msg"] or "").lower() else "error",
                "timestamp": log["created_at"].strftime("%I:%M %p") if log["created_at"] else ""
            })
        
        return jsonify(formatted_logs)
    except Exception as e:
        print(f"Error fetching terminal logs: {e}")
        return jsonify([])

@app.route("/command-history", methods=["GET"])
def get_command_history():
    user_id = request.args.get("user_id")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if user_id:
            cursor.execute("SELECT * FROM command_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 50", (user_id,))
        else:
            cursor.execute("SELECT * FROM command_history ORDER BY created_at DESC LIMIT 50")
        history = cursor.fetchall()
        return jsonify(history)
    except Exception as e:
        print(f"Error fetching command history: {e}")
        return jsonify([])
    
#----------saved commands----------------
@app.route('/save-command', methods=['POST'])
def save_command():
    data = request.get_json()

    email = data.get("email")
    command = data.get("command")

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="robovoice"
    )
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO command_history (email, command)
        VALUES (%s, %s)
    """, (email, command))

    conn.commit()

    return jsonify({"message": "Command saved"})

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
    app.run(host="0.0.0.0", port=5000)