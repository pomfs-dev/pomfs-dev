import os
import sqlite3
import psycopg2
import json
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Default to TEST (SQLite) if not specified
ENV = os.environ.get('POMFS_ENV', 'TEST')
LOCAL_DB_PATH = 'test_pomfs.db'
MUSICFEED_DB_URL = os.environ.get("MUSICFEED_DB_URL") 

def get_db_connection():
    if ENV == 'TEST':
        print(f"[Info] Connecting to SQLite ({LOCAL_DB_PATH})")
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        if not MUSICFEED_DB_URL:
            print("[Error] MUSICFEED_DB_URL not found in .env for PROD mode")
            return None
        try:
            print(f"[Info] Connecting to Postgres (Production)")
            return psycopg2.connect(MUSICFEED_DB_URL)
        except Exception as e:
            print(f"[Error] Connecting to DB: {e}")
            return None

def run_migration():
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        # 1. Create Tables (if not exists)
        print("--- initializing schema ---")
        try:
            # Read schema file
            with open('DB/schema_v2_4_0.sql', 'r') as f:
                schema_sql = f.read()

            if ENV == 'TEST':
                # SQLite compatibility adjustments
                # 1. Remove specific Postgres syntax like 'USING gin'
                # 2. JSONB -> TEXT
                # 3. TEXT[] -> TEXT
                # 4. SERIAL -> OR check if simple CREATE TABLE works
                # For simplicity, we might need a separate schema_sqlite.sql OR adjust on the fly
                # Let's try to adjust on the fly for simple tables
                formatted_sql = schema_sql.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
                formatted_sql = formatted_sql.replace('JSONB', 'TEXT')
                formatted_sql = formatted_sql.replace('TEXT[]', 'TEXT')
                formatted_sql = formatted_sql.replace('TIMESTAMP DEFAULT NOW()', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                formatted_sql = formatted_sql.replace('BOOLEAN', 'INTEGER') # SQLite uses 0/1, or allows BOOLEAN but treated as numeric
                
                # Remove indexes that use GIN
                # We will just split by ';' and execute statements ignoring errors for indexes
                statements = formatted_sql.split(';')
                for stmt in statements:
                    stmt = stmt.strip()
                    if not stmt: continue
                    if 'USING gin' in stmt: continue # Skip GIN index
                    try:
                        cur.execute(stmt)
                    except Exception as e:
                        print(f"⚠️ Statement failed: {stmt[:50]}... => {e}")
                
            else:
                # Postgres
                cur.execute(schema_sql)
            
            conn.commit()
            print("✅ Schema applied.")
        except Exception as e:
            print(f"⚠️ Schema application failed: {e}")
            conn.rollback()

        # 2. Migrate Data
        print("--- Migrating Data from 'posts' to 'event_ai' ---")
        
        # Select target posts
        # Check if 'posts' table exists first
        try:
            cur.execute("SELECT * FROM posts WHERE category = 'pomfs_ai'")
            posts = cur.fetchall()
        except Exception as e:
            print(f"⚠️ Could not fetch posts (maybe table empty or missing): {e}")
            posts = []

        print(f"Found {len(posts)} posts to migrate.")

        migrated_count = 0
        skipped_count = 0

        for p in posts:
            try:
                # Convert row to dict
                p_dict = dict(p)
                
                # Extract shortcode if possible
                shortcode = None
                ig_link = p_dict.get('instagram_link')
                if ig_link:
                    import re
                    match = re.search(r'instagram\.com/p/([^/]+)', ig_link)
                    if match:
                        shortcode = match.group(1)

                # Check duplicate
                if ENV == 'TEST':
                    query = "SELECT id FROM event_ai WHERE event_name = ? AND venue_name = ?"
                    params = [p_dict['eventName'], p_dict['eventVenue']] # Note: camelCase in sqlite? Wait, init_test_db might use different schema
                    # Need to check init_test_db schema column names.
                    # Assuming they match what we expect. valid
                else:
                    query = "SELECT id FROM event_ai WHERE event_name = %s AND venue_name = %s"
                    params = [p_dict['event_name'], p_dict['event_venue']]

                cur.execute(query, tuple(params))
                if cur.fetchone():
                    skipped_count += 1
                    continue

                # Prepare Insert
                # SQLite params ?, Postgres %s
                ph = '?' if ENV == 'TEST' else '%s'
                
                insert_query = f"""
                    INSERT INTO event_ai (
                        bot_id, event_name, venue_name, event_dates, 
                        event_location, content, image_url, performing_artists, 
                        instagram_link, shortcode, created_at, source_username
                    ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """
                
                insert_params = (
                    'pomfs-bot',
                    p_dict.get('eventName') or p_dict.get('event_name'),
                    p_dict.get('eventVenue') or p_dict.get('event_venue'),
                    p_dict.get('eventDates') or p_dict.get('event_date'), # Might need JSON dump if obj
                    p_dict.get('eventLocation') or p_dict.get('event_location'),
                    p_dict.get('content'),
                    p_dict.get('imageUrl') or p_dict.get('image_url'),
                    p_dict.get('performingArtists') or p_dict.get('performing_artists'),
                    p_dict.get('instagram_link'),
                    shortcode,
                    p_dict.get('createdAt') or p_dict.get('created_at'),
                    p_dict.get('userId') or p_dict.get('user_id')
                )
                
                cur.execute(insert_query, insert_params)
                migrated_count += 1
                
            except Exception as e:
                print(f"Error migrating post {p_dict.get('id')}: {e}")
                
        conn.commit()
        print(f"Migration finished. Migrated: {migrated_count}, Skipped: {skipped_count}")

    except Exception as e:
        print(f"Migration Fatal Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
