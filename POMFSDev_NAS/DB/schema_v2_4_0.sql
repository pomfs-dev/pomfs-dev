-- Schema v2.4.0 Migration
-- Separating 'posts' table into specialized tables

-- 1. AI Collected Events (formerly posts where category='pomfs_ai')
CREATE TABLE IF NOT EXISTS event_ai (
    id SERIAL PRIMARY KEY,
    bot_id VARCHAR(100) DEFAULT 'pomfs-bot', -- Replaces userId
    event_name VARCHAR(300) NOT NULL,
    venue_name VARCHAR(200),
    event_venue_id INTEGER, -- Optional link to venues table
    event_dates JSONB, -- [{"date": "YYYY-MM-DD", "time": "HH:MM"}]
    event_location VARCHAR(200),
    content TEXT,
    image_url VARCHAR(500),
    performing_artists TEXT[], -- Array of strings
    source_username VARCHAR(100), -- Original scraper source
    shortcode VARCHAR(50), -- Instagram shortcode
    instagram_link VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- 2. User Submitted Events (User uploads)
CREATE TABLE IF NOT EXISTS event_user (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL, -- References users(id)
    event_name VARCHAR(300) NOT NULL,
    venue_name VARCHAR(200),
    event_dates JSONB,
    event_location VARCHAR(200),
    ticket_info JSONB, -- {"price": ..., "link": ...}
    content TEXT,
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'pending' -- pending, approved, rejected
);

-- 3. User Feed (General SNS posts)
CREATE TABLE IF NOT EXISTS feed_user (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    content TEXT,
    image_urls TEXT[], -- Array of image URLs
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    likes_count INTEGER DEFAULT 0
);

-- 4. AI Feed (Bot general posts, notifications)
CREATE TABLE IF NOT EXISTS feed_ai (
    id SERIAL PRIMARY KEY,
    bot_id VARCHAR(100) DEFAULT 'pomfs-bot',
    content TEXT,
    image_url VARCHAR(500),
    link_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_event_ai_dates ON event_ai USING gin (event_dates);
CREATE INDEX IF NOT EXISTS idx_event_ai_bot_id ON event_ai(bot_id);
CREATE INDEX IF NOT EXISTS idx_event_user_user_id ON event_user(user_id);
