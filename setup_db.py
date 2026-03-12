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
        print("✅ Database 'robovoice' created or already exists")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ Error creating database: {err}")
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Users table created or already exists")

        # Create command_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                command VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Command history table created or already exists")

        conn.commit()
        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ Error creating tables: {err}")
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
            print("✅ Database connection successful")

        cursor.close()
        conn.close()
        return True

    except mysql.connector.Error as err:
        print(f"❌ Database connection failed: {err}")
        return False

if __name__ == "__main__":
    print("🔧 Setting up RoboVoice Database...")
    print()

    # Test MySQL connection first
    if not test_connection():
        print("❌ Please make sure MySQL is running and credentials are correct")
        exit(1)

    # Create database and tables
    if create_database() and create_tables():
        print()
        print("🎉 Database setup complete!")
        print("📊 Tables created:")
        print("   - users (id, full_name, email, password, phone, location, created_at)")
        print("   - command_history (id, command, created_at)")
        print()
        print("🌐 You can now run the Flask app: python app.py")
        print("🌐 Open profile.html in your browser to manage user profiles")
    else:
        print("❌ Database setup failed")