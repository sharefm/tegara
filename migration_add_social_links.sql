-- Migration script to replace social_media_url with three specific social media URLs

-- Add new columns
ALTER TABLE domains ADD COLUMN facebook_url VARCHAR;
ALTER TABLE domains ADD COLUMN instagram_url VARCHAR;
ALTER TABLE domains ADD COLUMN tiktok_url VARCHAR;

-- Migrate existing social_media_url data to facebook_url (assuming most were facebook or general)
UPDATE domains SET facebook_url = social_media_url;

-- Drop the old column
ALTER TABLE domains DROP COLUMN social_media_url;
