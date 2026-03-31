import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "robovoice"
}

def migrate():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Adding missing columns to 'users' table...")
        
        # Add profile_photo
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT AFTER location")
            print("[SUCCESS] Added 'profile_photo'")
        except mysql.connector.Error:
            print("[INFO] 'profile_photo' already exists or other error")

        # Add otp
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN otp VARCHAR(10) AFTER profile_photo")
            print("[SUCCESS] Added 'otp'")
        except mysql.connector.Error:
            print("[INFO] 'otp' already exists or other error")

        # Add otp_expiry
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN otp_expiry DATETIME AFTER otp")
            print("[SUCCESS] Added 'otp_expiry'")
        except mysql.connector.Error:
            print("[INFO] 'otp_expiry' already exists or other error")

        # Add otp_verified
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN otp_verified TINYINT(1) DEFAULT 0 AFTER otp_expiry")
            print("[SUCCESS] Added 'otp_verified'")
        except mysql.connector.Error:
            print("[INFO] 'otp_verified' already exists or other error")

        conn.commit()
        print("[DONE] Migration complete!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")

if __name__ == "__main__":
    migrate()
