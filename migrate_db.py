"""
Database migration script to add social_media_url and is_active columns to domains table
"""
import sqlite3
import sys

def migrate_database(db_path='tegara.db'):
    """Add social_media_url and is_active columns to domains table if they don't exist"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(domains)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add social_media_url column if it doesn't exist
        if 'social_media_url' not in columns:
            print("Adding social_media_url column to domains table...")
            cursor.execute("""
                ALTER TABLE domains 
                ADD COLUMN social_media_url TEXT NOT NULL DEFAULT ''
            """)
            print("✓ social_media_url column added")
        else:
            print("✓ social_media_url column already exists")
        
        # Add is_active column if it doesn't exist
        if 'is_active' not in columns:
            print("Adding is_active column to domains table...")
            cursor.execute("""
                ALTER TABLE domains 
                ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
            """)
            print("✓ is_active column added")
        else:
            print("✓ is_active column already exists")
        
        conn.commit()
        conn.close()
        print("\n✅ Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'tegara.db'
    success = migrate_database(db_path)
    sys.exit(0 if success else 1)
