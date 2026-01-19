"""
Database initialization script
Creates all tables from scratch using SQLAlchemy models
"""
from database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("✅ Database initialized successfully!")
    print("\nAll tables created:")
    print("  - users")
    print("  - domains")
    print("  - otp_sessions")
    print("\nYou can now run the migration scripts to add additional columns.")
