-- PostgreSQL Database Initialization Script for Tejara Application
-- This script creates all tables and relationships

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    mobile_number VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    verified INTEGER DEFAULT 0,
    password_reset_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on mobile_number for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_mobile_number ON users(mobile_number);

-- Create domains table
CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    domain_type VARCHAR(50) NOT NULL,
    facebook_url TEXT,
    instagram_url TEXT,
    tiktok_url TEXT,
    email VARCHAR(255),
    address TEXT,
    store_name VARCHAR(255),
    is_active INTEGER DEFAULT 1,
    subscription_status VARCHAR(50) DEFAULT 'trial',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP,
    CONSTRAINT fk_domains_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

-- Create indexes on domains table
CREATE INDEX IF NOT EXISTS idx_domains_user_id ON domains(user_id);
CREATE INDEX IF NOT EXISTS idx_domains_domain_name ON domains(domain_name);

-- Create otp_sessions table
CREATE TABLE IF NOT EXISTS otp_sessions (
    id SERIAL PRIMARY KEY,
    mobile_number VARCHAR(20) NOT NULL,
    otp_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified INTEGER DEFAULT 0
);

-- Create index on mobile_number for faster OTP lookups
CREATE INDEX IF NOT EXISTS idx_otp_sessions_mobile_number ON otp_sessions(mobile_number);

-- Grant privileges to the current database user (works with any POSTGRES_USER)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;
