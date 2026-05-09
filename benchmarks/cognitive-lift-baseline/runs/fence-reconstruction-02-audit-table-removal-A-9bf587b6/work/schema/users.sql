-- Core user table.
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    last_login TIMESTAMPTZ,
    role VARCHAR(50) DEFAULT 'user',
    password_hash VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX users_email_idx ON users(email);
