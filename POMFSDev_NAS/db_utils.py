import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_neon_connection():
    """Get connection to Neon DB using NEON_DB_URL environment variable."""
    db_url = os.environ.get("NEON_DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("NEON_DB_URL or DATABASE_URL not set")
    
    # Clean up db_url if it contains psql command prefix
    if db_url.startswith("psql "):
        # Extract the actual connection string from psql command
        import re
        match = re.search(r"'(postgresql://[^']+)'", db_url)
        if match:
            db_url = match.group(1)
        else:
            # Try without quotes
            db_url = db_url.replace("psql ", "").strip().strip("'\"")
    
    return psycopg2.connect(db_url)

def init_scraped_posts_table():
    """Create scraped_posts table matching MusicFeedPlatform posts structure."""
    conn = get_neon_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scraped_posts (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(100),
            content TEXT,
            genre VARCHAR(100),
            image_url VARCHAR(500),
            external_link VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW(),
            link_platform VARCHAR(50) DEFAULT 'other',
            category VARCHAR(50) DEFAULT 'perform',
            subcategory VARCHAR(50) DEFAULT 'concert',
            event_location VARCHAR(200),
            event_venue VARCHAR(200),
            event_date TIMESTAMP,
            event_name VARCHAR(300),
            youtube_link VARCHAR(500),
            instagram_link VARCHAR(500),
            tiktok_link VARCHAR(500),
            other_link VARCHAR(500),
            updated_at TIMESTAMP DEFAULT NOW(),
            latitude NUMERIC,
            longitude NUMERIC,
            place_id VARCHAR(200),
            formatted_address TEXT,
            event_time VARCHAR(50),
            ticket_sales_enabled BOOLEAN DEFAULT FALSE,
            ticket_options JSONB DEFAULT '[]'::jsonb,
            event_country VARCHAR(100),
            event_region VARCHAR(100),
            has_guest_list BOOLEAN DEFAULT FALSE,
            venue_id INTEGER,
            performing_artists TEXT[],
            is_draft BOOLEAN DEFAULT TRUE,
            event_dates JSONB,
            shortcode VARCHAR(50) UNIQUE,
            post_url VARCHAR(500),
            source_username VARCHAR(100)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_scraped_posts_source_username 
        ON scraped_posts(source_username)
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] scraped_posts table initialized (MusicFeedPlatform structure).")

def save_scraped_post(username, post_data, analyzed_data=None):
    """Save a scraped post to Neon DB (MusicFeedPlatform structure)."""
    from datetime import datetime
    import json
    
    conn = get_neon_connection()
    cur = conn.cursor()
    
    # Parse post_date - handle various formats
    post_date = post_data.get('date')
    if post_date:
        if isinstance(post_date, str):
            try:
                post_date = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
            except ValueError:
                try:
                    post_date = datetime.strptime(post_date[:19], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    post_date = None
        elif not isinstance(post_date, datetime):
            post_date = None
    
    # Extract analyzed data if available
    event_name = None
    event_venue = None
    event_dates_json = None
    performing_artists = None
    
    if analyzed_data:
        event_name = analyzed_data.get('event_name') or analyzed_data.get('eventName')
        event_venue = analyzed_data.get('venue') or analyzed_data.get('venueName')
        
        # Build event_dates JSON
        event_date_str = analyzed_data.get('event_date') or analyzed_data.get('date')
        event_time_str = analyzed_data.get('event_time') or analyzed_data.get('time')
        if event_date_str:
            event_dates_json = json.dumps([{
                "date": event_date_str,
                "time": event_time_str or ""
            }])
        
        # Artists
        artists = analyzed_data.get('artists') or analyzed_data.get('performingArtists') or []
        if isinstance(artists, list) and artists:
            performing_artists = artists
    
    # Extract event time if available
    event_time = None
    if analyzed_data:
        event_time = analyzed_data.get('event_time') or analyzed_data.get('time')
    
    try:
        shortcode = post_data.get('shortcode')
        if shortcode:
            cur.execute("SELECT id FROM scraped_posts WHERE shortcode = %s", (shortcode,))
            if cur.fetchone():
                print(f"[DB] Duplicate shortcode skipped: {shortcode}")
                cur.close()
                conn.close()
                return None
        
        cur.execute("""
            INSERT INTO scraped_posts 
            (source_username, shortcode, event_date, content, post_url, image_url, 
             event_name, event_venue, event_dates, performing_artists, category, subcategory,
             user_id, link_platform, is_draft, event_time, instagram_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            username,
            post_data.get('shortcode'),
            post_date,
            post_data.get('caption'),
            post_data.get('url'),
            post_data.get('image_filepath'),
            event_name,
            event_venue,
            event_dates_json,
            performing_artists,
            'perform',
            'concert',
            f'scraper_{username}',
            'instagram',
            True,
            event_time,
            post_data.get('url')
        ))
        
        result = cur.fetchone()
        conn.commit()
        return result[0] if result else None
        
    except Exception as e:
        conn.rollback()
        print(f"[DB] Error saving post: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def upsert_scraped_post(username, post_data, analyzed_data=None):
    """Upsert a scraped post to Neon DB (INSERT or UPDATE on conflict).
    
    This function handles both initial scraping (without analysis) and
    post-analysis updates using PostgreSQL's ON CONFLICT DO UPDATE.
    """
    from datetime import datetime
    import json
    
    conn = get_neon_connection()
    cur = conn.cursor()
    
    post_date = post_data.get('date')
    if post_date:
        if isinstance(post_date, str):
            try:
                post_date = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
            except ValueError:
                try:
                    post_date = datetime.strptime(post_date[:19], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    post_date = None
        elif not isinstance(post_date, datetime):
            post_date = None
    
    event_name = None
    event_venue = None
    event_dates_json = None
    performing_artists = None
    event_time = None
    event_country = None
    event_location = None
    
    if analyzed_data:
        event_name = analyzed_data.get('event_name') or analyzed_data.get('eventName')
        event_venue = analyzed_data.get('venue') or analyzed_data.get('venueName')
        
        event_date_str = analyzed_data.get('event_date') or analyzed_data.get('date')
        event_time_str = analyzed_data.get('event_time') or analyzed_data.get('time')
        if event_date_str:
            event_dates_json = json.dumps([{
                "date": event_date_str,
                "time": event_time_str or ""
            }])
        
        artists = analyzed_data.get('artists') or analyzed_data.get('performingArtists') or []
        if isinstance(artists, list) and artists:
            performing_artists = artists
        
        event_time = analyzed_data.get('event_time') or analyzed_data.get('time')
        event_country = analyzed_data.get('event_country') or analyzed_data.get('country')
        event_location = analyzed_data.get('event_location') or analyzed_data.get('location')
    
    try:
        shortcode = post_data.get('shortcode')
        if not shortcode:
            print("[DB] No shortcode provided, skipping upsert")
            return None
        
        cur.execute("""
            INSERT INTO scraped_posts 
            (source_username, shortcode, event_date, content, post_url, image_url, 
             event_name, event_venue, event_dates, performing_artists, category, subcategory,
             user_id, link_platform, is_draft, event_time, instagram_link, event_country, event_location)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (shortcode) DO UPDATE SET
                source_username = COALESCE(EXCLUDED.source_username, scraped_posts.source_username),
                event_date = COALESCE(EXCLUDED.event_date, scraped_posts.event_date),
                event_name = COALESCE(EXCLUDED.event_name, scraped_posts.event_name),
                event_venue = COALESCE(EXCLUDED.event_venue, scraped_posts.event_venue),
                event_dates = COALESCE(EXCLUDED.event_dates, scraped_posts.event_dates),
                performing_artists = COALESCE(EXCLUDED.performing_artists, scraped_posts.performing_artists),
                event_time = COALESCE(EXCLUDED.event_time, scraped_posts.event_time),
                content = COALESCE(EXCLUDED.content, scraped_posts.content),
                image_url = COALESCE(EXCLUDED.image_url, scraped_posts.image_url),
                post_url = COALESCE(EXCLUDED.post_url, scraped_posts.post_url),
                instagram_link = COALESCE(EXCLUDED.instagram_link, scraped_posts.instagram_link),
                event_country = COALESCE(EXCLUDED.event_country, scraped_posts.event_country),
                event_location = COALESCE(EXCLUDED.event_location, scraped_posts.event_location)
            RETURNING id
        """, (
            username,
            shortcode,
            post_date,
            post_data.get('caption'),
            post_data.get('url'),
            post_data.get('image_filepath'),
            event_name,
            event_venue,
            event_dates_json,
            performing_artists,
            'perform',
            'concert',
            f'scraper_{username}',
            'instagram',
            True,
            event_time,
            post_data.get('url'),
            event_country,
            event_location
        ))
        
        result = cur.fetchone()
        conn.commit()
        action = "inserted/updated"
        print(f"[DB] Post {shortcode} {action} successfully")
        return result[0] if result else None
        
    except Exception as e:
        conn.rollback()
        print(f"[DB] Error upserting post: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def get_scraped_posts(username=None, limit=50):
    """Get scraped posts from DB."""
    conn = get_neon_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if username:
        cur.execute("""
            SELECT * FROM scraped_posts 
            WHERE source_username = %s 
            ORDER BY event_date DESC 
            LIMIT %s
        """, (username, limit))
    else:
        cur.execute("""
            SELECT * FROM scraped_posts 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def get_account_events(username, events_only=True):
    """Get analyzed events for a specific account.
    
    Args:
        username: Instagram account username
        events_only: If True, only return posts with event_name (detected as events)
    
    Returns:
        List of event data dictionaries
    """
    conn = get_neon_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if events_only:
        cur.execute("""
            SELECT shortcode, event_name, event_venue, event_dates, 
                   event_time, event_location, event_country,
                   latitude, longitude, formatted_address,
                   performing_artists, content, image_url,
                   post_url, created_at
            FROM scraped_posts 
            WHERE source_username = %s 
              AND event_name IS NOT NULL
            ORDER BY created_at DESC
        """, (username,))
    else:
        cur.execute("""
            SELECT shortcode, event_name, event_venue, event_dates, 
                   event_time, event_location, event_country,
                   latitude, longitude, formatted_address,
                   performing_artists, content, image_url,
                   post_url, created_at
            FROM scraped_posts 
            WHERE source_username = %s
            ORDER BY created_at DESC
        """, (username,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def get_scraped_post_by_shortcode(shortcode):
    """Get a single scraped post by shortcode.
    
    Returns:
        Dict with post data or None if not found
    """
    conn = get_neon_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM scraped_posts 
        WHERE shortcode = %s
    """, (shortcode,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def recreate_scraped_posts_table():
    """Drop and recreate scraped_posts table with new structure."""
    conn = get_neon_connection()
    cur = conn.cursor()
    
    cur.execute("DROP TABLE IF EXISTS scraped_posts CASCADE")
    conn.commit()
    cur.close()
    conn.close()
    
    init_scraped_posts_table()
    print("[DB] scraped_posts table recreated with new structure.")

def delete_all_scraped_posts():
    """Delete all scraped posts from DB."""
    conn = get_neon_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM scraped_posts")
    deleted_count = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"[DB] Deleted {deleted_count} scraped posts.")
    return deleted_count

def get_collection_stats_by_usernames(usernames):
    """Get collection stats for multiple usernames.
    
    Args:
        usernames: List of Instagram usernames
        
    Returns:
        Dict mapping username to {post_count, last_collected_at}
    """
    if not usernames:
        return {}
    
    conn = get_neon_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    placeholders = ','.join(['%s'] * len(usernames))
    cur.execute(f"""
        SELECT source_username,
               COUNT(*) as post_count,
               MAX(created_at) as last_collected_at
        FROM scraped_posts 
        WHERE source_username IN ({placeholders})
        GROUP BY source_username
    """, tuple(usernames))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    stats = {}
    for row in results:
        stats[row['source_username']] = {
            'post_count': row['post_count'],
            'last_collected_at': row['last_collected_at'].isoformat() if row['last_collected_at'] else None
        }
    
    return stats


if __name__ == "__main__":
    init_scraped_posts_table()
    print("Done.")
