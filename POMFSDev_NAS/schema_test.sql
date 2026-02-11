-- P.O.MFS Test Database Schema (SQLite)
-- Mirrored from db_schema_performance.json

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- 1. Venues Table
CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userId VARCHAR(255), -- Nullable for staff
    venueName VARCHAR(200),
    venueAddress TEXT,
    venueIntroduction TEXT,
    venueType VARCHAR(50),
    genre VARCHAR(50),
    instagramId VARCHAR(100),
    profileImageUrl TEXT,
    coverImageUrl TEXT,
    guestListEnabled BOOLEAN DEFAULT 0,
    ticketSalesEnabled BOOLEAN DEFAULT 0,
    latitude REAL,
    longitude REAL,
    formattedAddress TEXT,
    placeId VARCHAR(255),
    country VARCHAR(100),
    region VARCHAR(100),
    timezone VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Posts Table
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userId VARCHAR(255),
    botId INTEGER,
    content TEXT,
    category VARCHAR(50), -- explore, perform, etc.
    subcategory VARCHAR(50),
    imageUrl VARCHAR(500),
    eventName VARCHAR(100),
    eventLocation VARCHAR(100),
    eventVenue VARCHAR(100),
    eventDate VARCHAR(20), -- Deprecated but kept for legacy
    eventTime VARCHAR(20), -- Deprecated
    eventDates TEXT, -- JSONB -> TEXT in SQLite
    latitude REAL,
    longitude REAL,
    formattedAddress TEXT,
    placeId VARCHAR(255),
    countryCode VARCHAR(2),
    eventCountry VARCHAR(100),
    eventRegion VARCHAR(100),
    hasGuestList BOOLEAN DEFAULT 0,
    maxGuestListQR INTEGER DEFAULT 0,
    issuedGuestListQR INTEGER DEFAULT 0,
    ticketSalesEnabled BOOLEAN DEFAULT 0,
    ticketSalesStartDate VARCHAR(20),
    ticketSalesStartTime VARCHAR(20),
    ticketSalesEndDate VARCHAR(20),
    ticketSalesEndTime VARCHAR(20),
    refundPolicyType VARCHAR(20) DEFAULT 'flexible',
    ticketOptions TEXT, -- JSONB -> TEXT
    venueId INTEGER,
    performingArtists TEXT, -- Array -> TEXT (JSON/CSV)
    mentionedUserIds TEXT, -- Array -> TEXT
    taggedEventPostId INTEGER,
    youtubeLink VARCHAR(500),
    instagramLink VARCHAR(500),
    tiktokLink VARCHAR(500),
    otherLink VARCHAR(500),
    isDraft BOOLEAN DEFAULT 1,
    publishedAt DATETIME,
    scheduledDate DATETIME,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venueId) REFERENCES venues(id)
);

-- 3. VenueEvents Table
CREATE TABLE IF NOT EXISTS venueEvents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venueId INTEGER NOT NULL,
    userId VARCHAR(255) NOT NULL,
    eventName VARCHAR(200) NOT NULL,
    eventDate VARCHAR(20) NOT NULL,
    eventTime VARCHAR(20),
    content TEXT NOT NULL,
    imageUrl VARCHAR(500),
    youtubeLink VARCHAR(500),
    instagramLink VARCHAR(500),
    tiktokLink VARCHAR(500),
    soundcloudLink VARCHAR(500),
    otherLink VARCHAR(500),
    hasGuestList BOOLEAN DEFAULT 0,
    maxGuestListQR INTEGER DEFAULT 0,
    issuedGuestListQR INTEGER DEFAULT 0,
    ticketSalesEnabled BOOLEAN DEFAULT 0,
    ticketSalesStartDate VARCHAR(20),
    ticketSalesStartTime VARCHAR(20),
    ticketSalesEndDate VARCHAR(20),
    ticketSalesEndTime VARCHAR(20),
    refundPolicyType VARCHAR(20) DEFAULT 'flexible',
    ticketOptions TEXT, -- JSONB -> TEXT
    status VARCHAR(20) DEFAULT 'active',
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venueId) REFERENCES venues(id)
);

-- Indexes (Simplified for SQLite)
CREATE INDEX IF NOT EXISTS idx_posts_userId ON posts(userId);
CREATE INDEX IF NOT EXISTS idx_posts_venueId ON posts(venueId);
CREATE INDEX IF NOT EXISTS idx_venues_instagramId ON venues(instagramId);
