"""
Migration script to add business_name column to users table
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/tejara.db')
cursor = conn.cursor()

try:
    # Check if business_name column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'business_name' not in columns:
        print("Adding business_name column to users table...")
        
        # Add the business_name column
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN business_name VARCHAR DEFAULT 'متجر'
        """)
        
        # Set default value for existing users
        cursor.execute("""
            UPDATE users 
            SET business_name = 'متجر'
            WHERE business_name IS NULL OR business_name = ''
        """)
        
        conn.commit()
        print("✓ Added business_name column")
        print("✓ Set default business name 'متجر' for existing users")
    else:
        print("business_name column already exists")
    
except Exception as e:
    print(f"Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\nMigration completed!")
