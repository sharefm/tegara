"""
Migration script to add expiry_date column to domains table
and set default expiry dates for existing domains
"""
import sqlite3
from datetime import datetime, timedelta

# Connect to database
conn = sqlite3.connect('data/tejara.db')
cursor = conn.cursor()

try:
    # Check if expiry_date column exists
    cursor.execute("PRAGMA table_info(domains)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'expiry_date' not in columns:
        print("Adding expiry_date column to domains table...")
        
        # Add the expiry_date column
        cursor.execute("""
            ALTER TABLE domains 
            ADD COLUMN expiry_date TIMESTAMP
        """)
        
        # Set expiry_date for existing domains (7 days from now)
        expiry_date = datetime.utcnow() + timedelta(days=7)
        cursor.execute("""
            UPDATE domains 
            SET expiry_date = ?
            WHERE expiry_date IS NULL
        """, (expiry_date,))
        
        conn.commit()
        print(f"✓ Added expiry_date column")
        print(f"✓ Set expiry date for existing domains to: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("expiry_date column already exists")
        
        # Update any NULL expiry dates
        expiry_date = datetime.utcnow() + timedelta(days=7)
        cursor.execute("""
            UPDATE domains 
            SET expiry_date = ?
            WHERE expiry_date IS NULL
        """, (expiry_date,))
        
        rows_updated = cursor.rowcount
        if rows_updated > 0:
            conn.commit()
            print(f"✓ Updated {rows_updated} domains with NULL expiry dates")
        else:
            print("✓ All domains already have expiry dates")
    
except Exception as e:
    print(f"Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\nMigration completed!")
