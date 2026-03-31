import mysql.connector

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "robovoice"
}

def create_database():
    """Create the robovoice database if it doesn't exist"""
    try:
        # Connect without specifying database
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        cursor = conn.cursor()

        # Create database
        cursor.execute("CREATE DATABASE IF NOT EXISTS robovoice")
        print("--- Database 'robovoice' created or already exists")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"--- Error creating database: {err}")
        return False

    return True

def create_tables():
    """Create the necessary tables"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                location VARCHAR(255),
                profile_photo TEXT,
                otp VARCHAR(10),
                otp_expiry DATETIME,
                otp_verified TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("--- Users table created or already exists")

        # Create command_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                command VARCHAR(255) NOT NULL,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ensure 'user_id' and 'response' columns exist in command_history
        cursor.execute("SHOW COLUMNS FROM command_history LIKE 'user_id'")
        if not cursor.fetchone():
            print("--- Migrating: Adding 'user_id' column to command_history")
            cursor.execute("ALTER TABLE command_history ADD COLUMN user_id INT AFTER id")

        cursor.execute("SHOW COLUMNS FROM command_history LIKE 'response'")
        if not cursor.fetchone():
            print("--- Migrating: Adding 'response' column to command_history")
            cursor.execute("ALTER TABLE command_history ADD COLUMN response TEXT AFTER command")
        
        print("--- Command history table verified")

        # Create terminal_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terminal_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                command_text TEXT NOT NULL,
                response_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure 'user_id' exists in terminal_logs
        cursor.execute("SHOW COLUMNS FROM terminal_logs LIKE 'user_id'")
        if not cursor.fetchone():
            print("--- Migrating: Adding 'user_id' column to terminal_logs")
            cursor.execute("ALTER TABLE terminal_logs ADD COLUMN user_id INT AFTER id")

        print("--- Terminal logs table verified")

        conn.commit()
        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"--- Error creating tables: {err}")
        return False

    return True

def test_connection():
    """Test database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        if result:
            print("--- Database connection successful")

        cursor.close()
        conn.close()
        return True

    except mysql.connector.Error as err:
        print(f"--- Database connection failed: {err}")
        return False

if __name__ == "__main__":
    print("Setting up RoboVoice Database...")
    print()

    # Test MySQL connection first
    if not test_connection():
        print("--- Please make sure MySQL is running and credentials are correct")
        exit(1)

    # Create database and tables
    if create_database() and create_tables():
        print()
        print("Database setup complete!")
        print("--- Tables created/verified:")
        print("   - users (id, full_name, email, password, phone, location, otp, otp_verified, created_at)")
        print("   - command_history (id, command, response, created_at)")
        print("   - terminal_logs (id, command_text, response_text, created_at)")
        print()
        print("--- You can now run the Flask app: python app.py")
        print("--- Open profile.html in your browser to manage user profiles")
    else:
        print("❌ Database setup failed")