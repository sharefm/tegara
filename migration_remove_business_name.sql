-- Migration script to remove business_name from users and add store_name to domains
-- Run this on your existing database to apply the schema changes

-- Add store_name column to domains table
ALTER TABLE domains ADD COLUMN IF NOT EXISTS store_name VARCHAR(255);

-- Remove business_name column from users table
-- WARNING: This will delete all existing business_name data
ALTER TABLE users DROP COLUMN IF EXISTS business_name;
