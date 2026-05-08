-- Add the email column to the users table.
ALTER TABLE users ADD COLUMN email VARCHAR(255);
CREATE INDEX users_email_idx ON users(email);
