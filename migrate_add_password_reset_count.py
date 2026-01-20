"""
Migration script to add password_reset_count column to users table
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/tejara.db')
cursor = conn.cursor()

try:
    # Check if password_reset_count column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'password_reset_count' not in columns:
        print("Adding password_reset_count column to users table...")
        
        # Add the password_reset_count column
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN password_reset_count INTEGER DEFAULT 0
        """)
        
        # Set default value for existing users
        cursor.execute("""
            UPDATE users 
            SET password_reset_count = 0
            WHERE password_reset_count IS NULL
        """)
        
        conn.commit()
        print("✓ Added password_reset_count column")
        print("✓ Set default value 0 for existing users")
    else:
        print("password_reset_count column already exists")
    
except Exception as e:
    print(f"Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\nMigration completed!")
