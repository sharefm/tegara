-- Migration script to add email and address to the domains table

ALTER TABLE domains ADD COLUMN email VARCHAR;
ALTER TABLE domains ADD COLUMN address VARCHAR;
