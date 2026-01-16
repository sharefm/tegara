"""
Migration script to add subscription_status column to domains table
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/tejara.db')
cursor = conn.cursor()

try:
    # Check if subscription_status column exists
    cursor.execute("PRAGMA table_info(domains)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'subscription_status' not in columns:
        print("Adding subscription_status column to domains table...")
        
        # Add the subscription_status column
        cursor.execute("""
            ALTER TABLE domains 
            ADD COLUMN subscription_status VARCHAR DEFAULT 'trial'
        """)
        
        # Set default value for existing domains
        cursor.execute("""
            UPDATE domains 
            SET subscription_status = 'trial'
            WHERE subscription_status IS NULL
        """)
        
        conn.commit()
        print("✓ Added subscription_status column")
        print("✓ Set default status 'trial' for existing domains")
    else:
        print("subscription_status column already exists")
    
except Exception as e:
    print(f"Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\nMigration completed!")
