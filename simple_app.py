from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

# Database configuration
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

@app.route("/")
def home():
    return jsonify({"server": "RoboVoice backend running"})

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
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

@app.route("/update-profile", methods=["POST"])
def update_profile():
    data = request.json
    cur = get_cursor()

    cur.execute(
        """
        UPDATE users
        SET full_name=%s, phone=%s, location=%s
        WHERE email=%s
        """,
        (
            data["full_name"],
            data["phone"],
            data["location"],
            data["email"]
        ),
    )

    get_db_connection().commit()
    return jsonify({"message": "Profile updated"})

@app.route("/change-password", methods=["POST"])
def change_password():
    data = request.json
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

if __name__ == "__main__":
    print("Server started")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)