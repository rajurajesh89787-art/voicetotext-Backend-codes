import mysql.connector

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "robovoice"
}

def test_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Test select
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"✅ Database connected. Users table has {count} records")

        # Test insert
        cursor.execute("INSERT INTO users(full_name,email,password) VALUES(%s,%s,%s)",
                      ("Test User", "test@example.com", "password123"))
        conn.commit()
        print("✅ Test user inserted")

        # Test update
        cursor.execute("UPDATE users SET phone=%s WHERE email=%s",
                      ("1234567890", "test@example.com"))
        conn.commit()
        print("✅ Test user updated")

        # Clean up
        cursor.execute("DELETE FROM users WHERE email=%s", ("test@example.com",))
        conn.commit()
        print("✅ Test user deleted")

        cursor.close()
        conn.close()

        return True

    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")
        return False

if __name__ == "__main__":
    print("Testing database connection...")
    test_db()