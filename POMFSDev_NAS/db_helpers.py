import os
import sqlite3
import psycopg2
from db_config import get_db_connection
from utils import save_local_image

import json

def get_dev_db_connection():
    """Get connection to MusicFeedPlatform Development Database."""
    db_url = os.environ.get("MUSICFEED_DB_URL")
    if not db_url:
        return None
    return psycopg2.connect(db_url)

def get_all_registered_events():
    """Get all events from MusicFeedPlatform Development Database (new schema v2.4.0)."""
    try:
        # Check environment for local testing
        if os.environ.get('POMFS_ENV') == 'TEST':
            conn = get_db_connection() # Local SQLite
        else:
            conn = get_dev_db_connection() # Production Postgres
            
        if not conn:
            print("[DevDB] Connection failed (URL not set)")
            return []
        
        cur = conn.cursor()
        
        # v2.4.0: Query event_ai table
        cur.execute('''
            SELECT id, event_name, venue_name, event_dates, content, image_url,
                   performing_artists, created_at, instagram_link, shortcode
            FROM event_ai
            ORDER BY created_at DESC
        ''')
        
        columns = ['id', 'event_name', 'venue_name', 'event_dates', 'content', 'image_url',
                   'performing_artists', 'created_at', 'instagram_link', 'shortcode']
        rows = cur.fetchall()
        
        events = []
        for row in rows:
            event = dict(zip(columns, row))
            
            # Normalize performing_artists (TEXT[] or JSON string to list)
            if event.get('performing_artists'):
                if isinstance(event['performing_artists'], str):
                    try:
                        event['performing_artists'] = json.loads(event['performing_artists'])
                    except:
                        # Postgres array string format check: {a,b}
                        if event['performing_artists'].startswith('{') and event['performing_artists'].endswith('}'):
                             # Simple CSV parse for {a,b,c} style if needed, or just leave as string list
                             pass
                        else:
                            event['performing_artists'] = [event['performing_artists']]
            
            # Normalize event_dates (JSON string -> List[Dict])
            if event.get('event_dates'):
                 if isinstance(event['event_dates'], str):
                     try:
                         event['event_dates'] = json.loads(event['event_dates'])
                     except:
                         pass
            
            # Add legacy fields for compatibility
            event['is_draft'] = False # event_ai entries are usually active
            event['category'] = 'pomfs_ai' 
            event['genre'] = 'pomfs_ai'
            
            events.append(event)
        
        cur.close()
        conn.close()
        return events
        
    except Exception as e:
        print(f"[DevDB] Error fetching events: {e}")
        import traceback
        traceback.print_exc()
        return []

def save_to_dev_db(venue_name, event_name, event_date, event_dates_json, content, image_url, artists_json, instagram_id=None, instagram_post_url=None, event_location=None, is_draft=False, latitude=None, longitude=None, formatted_address=None, place_id=None, event_time=None, event_country=None):
    """
    Save event to MusicFeedPlatform Development Database.
    
    New schema mapping:
    - category = 'pomfs_ai'
    - genre = 'pomfs_ai'
    - event_venue = venue_name
    - event_date = timestamp
    - event_time = time string (HH:MM format)
    - event_country = country code (KR, JP, US, etc.)
    - instagram_link = post URL
    - performing_artists = artists array
    - is_draft = False (auto-publish by default for AI-collected events)
    - post_kind = 'event'
    - latitude/longitude = Geocoding 결과 좌표 (지도 표시용)
    """
    try:
        conn = get_dev_db_connection()
        if not conn:
            print("[DevDB] MUSICFEED_DB_URL not set, skipping MusicFeedPlatform DB save")
            return False
        
        # Convert JSON string to Python list for PostgreSQL array
        artists_list = []
        if artists_json:
            try:
                parsed = json.loads(artists_json) if isinstance(artists_json, str) else artists_json
                if isinstance(parsed, list):
                    artists_list = parsed
            except:
                artists_list = [artists_json] if artists_json else []
        
        cur = conn.cursor()
        
        # Check for duplicate using instagram_link (shortcode-based URL)
        if instagram_post_url:
            cur.execute('SELECT id FROM posts WHERE instagram_link = %s', (instagram_post_url,))
            if cur.fetchone():
                print(f"[DevDB] Duplicate instagram_link skipped: {instagram_post_url}")
                cur.close()
                conn.close()
                return False
        
        # Ensure user exists in users table (foreign key constraint)
        user_id = instagram_id or 'pomfs_ai'
        cur.execute('SELECT id FROM users WHERE id = %s', (user_id,))
        if not cur.fetchone():
            cur.execute(
                '''INSERT INTO users (id, nickname, user_rank, artist_profile_completed, instagram_handle) 
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING''',
                (user_id, user_id, 'user', False, user_id)
            )
        
        # Convert event_date string to timestamp (YYYY-MM-DD -> YYYY-MM-DD HH:MM:SS)
        # Use event_time if provided and valid, otherwise default to 19:00:00
        event_timestamp = None
        if event_date:
            try:
                from datetime import datetime
                import re
                # Validate time format (HH:MM)
                time_str = '19:00'
                if event_time and re.match(r'^\d{2}:\d{2}$', event_time):
                    time_str = event_time
                if len(time_str) == 5:  # HH:MM format
                    time_str = time_str + ':00'
                if len(event_date) == 10:  # YYYY-MM-DD format
                    event_timestamp = datetime.strptime(event_date + ' ' + time_str, '%Y-%m-%d %H:%M:%S')
                else:
                    event_timestamp = datetime.strptime(event_date, '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"[DevDB] Date parsing error: {e}, using default 19:00")
                # Fallback: try with default time
                try:
                    from datetime import datetime
                    event_timestamp = datetime.strptime(event_date + ' 19:00:00', '%Y-%m-%d %H:%M:%S')
                except:
                    event_timestamp = None
        
        # Clean venue name
        clean_venue_name = venue_name.strip() if venue_name else None
        
        # Check for duplicates using event_venue + event_name + event_date
        if clean_venue_name and event_timestamp:
            cur.execute('''
                SELECT id FROM posts 
                WHERE event_venue = %s AND event_name = %s AND DATE(event_date) = DATE(%s)
            ''', (clean_venue_name, event_name, event_timestamp))
            if cur.fetchone():
                print(f"[DevDB] Duplicate event skipped: {event_name}")
                cur.close()
                conn.close()
                return False
        
        # Insert with snake_case column names (MusicFeedPlatform DB schema)
        cur.execute('''
            INSERT INTO posts (
                user_id, category, genre, post_kind,
                event_name, event_venue, event_date, event_location,
                event_time, event_country,
                content, image_url, 
                performing_artists, 
                instagram_link,
                is_draft, ticket_options,
                latitude, longitude, formatted_address, place_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            user_id,
            'pomfs_ai',
            'pomfs_ai',
            'event',
            event_name,
            clean_venue_name,
            event_timestamp,
            event_location,
            event_time or '',
            event_country or 'KR',
            content or event_name,
            image_url,
            artists_list,
            instagram_post_url,
            is_draft,
            json.dumps({}),
            latitude,
            longitude,
            formatted_address,
            place_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DevDB] Event saved: {event_name} at {clean_venue_name}")
        return True
        
    except Exception as e:
        print(f"[DevDB] Error saving to Development DB: {e}")
        import traceback
        traceback.print_exc()
        return False

def publish_events(ids):
    """Publish draft events by setting is_draft = false."""
    try:
        conn = get_dev_db_connection()
        if not conn:
            print("[DevDB] MUSICFEED_DB_URL not set")
            return 0
        
        cur = conn.cursor()
        
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f'''
            UPDATE posts 
            SET is_draft = false, updated_at = NOW() 
            WHERE id IN ({placeholders}) AND is_draft = true
        ''', ids)
        
        updated_count = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[DevDB] Published {updated_count} events")
        return updated_count
        
    except Exception as e:
        print(f"[DevDB] Error publishing events: {e}")
        return 0

def delete_events(ids):
    """Delete events from the database (both draft and published)."""
    try:
        conn = get_dev_db_connection()
        if not conn:
            print("[DevDB] MUSICFEED_DB_URL not set")
            return 0
        
        cur = conn.cursor()
        
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f'''
            DELETE FROM posts 
            WHERE id IN ({placeholders})
        ''', ids)
        
        deleted_count = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[DevDB] Deleted {deleted_count} events")
        return deleted_count
        
    except Exception as e:
        print(f"[DevDB] Error deleting events: {e}")
        return 0

def save_single_event(data):
    """
    Saves a single event to the P.O.MFS 'posts' table.
    
    Args:
        data (dict): Dictionary containing event details:
            - venue_id (int/str): ID of the venue or 'NEW'
            - new_venue (str): Name of new venue if venue_id is 'NEW'
            - event_name (str): Name of the event
            - event_date (str): Date of the event (YYYY-MM-DD)
            - content (str): Caption/Content
            - filename (str): Source filename (for image handling)
            - image_src_folder (str): Path to source images
            - artist_id, new_artist: (Optional, handled as performingArtists)
            - shortcode (str): Instagram post shortcode for URL
        
    Returns:
        bool: True if saved, False if duplicate or incomplete
    """
    try:
        f_venue_id = data.get('venue_id')
        f_new_venue = data.get('new_venue')
        f_event_name = data.get('event_name')
        f_date = data.get('event_date') # YYYY-MM-DD
        f_event_time = data.get('event_time')  # HH:MM format
        f_event_location = data.get('event_location')
        f_event_country = data.get('event_country', 'KR')  # Country code
        f_content = data.get('content')
        f_name = data.get('filename')
        image_src_folder = data.get('image_src_folder')
        f_shortcode = data.get('shortcode')
        
        # Artist info (Optional)
        f_new_artist = data.get('new_artist')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Handle New Venue
        if f_venue_id == 'NEW' and f_new_venue:
            exist = cursor.execute('SELECT id FROM venues WHERE venueName = ?', (f_new_venue,)).fetchone()
            if exist:
                f_venue_id = exist['id']
            else:
                # Insert minimal venue info
                cursor.execute('INSERT INTO venues (venueName, status) VALUES (?, ?)', (f_new_venue, 'active'))
                f_venue_id = cursor.lastrowid
        
        # 2. Check Prerequisites
        if not f_venue_id or not f_date:
            conn.close()
            return False

        # 3. Check Duplicates in 'posts' table
        # We check venueId and if eventDates contains this date
        date_query = f'%"{f_date}"%' # Simple JSON string check like [{"date": "2025-..."}]
        
        dup = cursor.execute('''
            SELECT id FROM posts 
            WHERE venueId=? 
            AND eventDates LIKE ? 
            AND eventName=?
        ''', (f_venue_id, date_query, f_event_name)).fetchone()
        
        if dup:
            conn.close()
            return False

        # 4. Prepare Data for Insertion
        
        # Image Handling - Upload to GCS (ai-post-img folder)
        db_image_url = ""
        if f_name and image_src_folder:
            src_path = os.path.join(image_src_folder, f_name)
            if os.path.exists(src_path):
                try:
                    from gcs_uploader import upload_image_to_gcs
                    gcs_url = upload_image_to_gcs(src_path, user_id="pomfs_ai", folder="ai-post-img")
                    if gcs_url:
                        db_image_url = gcs_url
                        print(f"[GCS] Image uploaded: {gcs_url}")
                    else:
                        saved_path = save_local_image(src_path, f_name)
                        if saved_path:
                            db_image_url = saved_path
                except Exception as gcs_err:
                    print(f"[GCS] Upload failed, using local: {gcs_err}")
                    saved_path = save_local_image(src_path, f_name)
                    if saved_path:
                        db_image_url = saved_path
        
        # JSON fields
        event_dates_json = json.dumps([{"date": f_date, "time": "19:00"}]) # Default time or parse?
        
        performing_artists = []
        if f_new_artist:
            # Just store name for now in test DB
            performing_artists.append(f_new_artist)
        artists_json = json.dumps(performing_artists)
        
        if not f_content:
            f_content = f_event_name

        # 4.5. Geocoding - 장소명/주소를 좌표로 변환
        latitude = None
        longitude = None
        formatted_address = None
        place_id = None
        try:
            from geocoder import geocode_location
            venue_for_geocoding = f_new_venue
            if not venue_for_geocoding and f_venue_id and f_venue_id != 'NEW':
                venue_row = cursor.execute('SELECT venueName FROM venues WHERE id = ?', (f_venue_id,)).fetchone()
                if venue_row:
                    venue_for_geocoding = venue_row['venueName']
            
            latitude, longitude, formatted_address, place_id = geocode_location(
                location=f_event_location,
                venue=venue_for_geocoding
            )
            if latitude and longitude:
                print(f"[Geocoder] 좌표 획득: {latitude}, {longitude}")
        except Exception as geo_err:
            print(f"[Geocoder] Error: {geo_err}")

        # 5. Insert into 'event_ai' (New Schema)
        
        # Helper to get DB connection for proper table
        # If TEST, we use local sqlite. existing `cursor` is from `conn = get_db_connection()` which is correct.
        
        # Check if event_ai exists (it should due to migration)
        # We assume schema v2.4.0 is applied.
        
        try:
            cursor.execute('''
                INSERT INTO event_ai (
                    bot_id, event_name, venue_name, event_dates, 
                    event_location, content, image_url, 
                    performing_artists, source_username, shortcode, 
                    instagram_link, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                'pomfs-bot',
                f_event_name,
                f_new_venue if f_new_venue else (venue_row['venueName'] if 'venue_row' in locals() and venue_row else None),
                event_dates_json,
                f_event_location,
                f_content,
                db_image_url,
                artists_json,
                'scraper', # source_username fallback
                f_shortcode,
                f_shortcode if not f_shortcode or 'instagram.com' in f_shortcode else f"https://www.instagram.com/p/{f_shortcode}/"
            ))
            conn.commit()
        except sqlite3.OperationalError as e:
            if 'no such table: event_ai' in str(e):
                print("[Warning] 'event_ai' table missing in SQLite. Falling back to 'posts'.")
                # Fallback to old posts table for backward compatibility if migration failed/skipped
                cursor.execute('''
                    INSERT INTO posts (
                        userId, category, subcategory, 
                        venueId, eventName, eventDates, 
                        content, imageUrl, 
                        performingArtists, 
                        isDraft, createdAt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    'pomfs_ai', 'perform', 'concert', f_venue_id, f_event_name, event_dates_json, 
                    f_content, db_image_url, artists_json, 1
                ))
                conn.commit()
            else:
                raise e

        # 6. Get venue name for Development DB
        venue_name = f_new_venue
        if not venue_name and f_venue_id:
            # Re-fetch if needed (though we tried above)
            if f_venue_id != 'NEW':
                venue_row = cursor.execute('SELECT venueName FROM venues WHERE id = ?', (f_venue_id,)).fetchone()
                if venue_row:
                    venue_name = venue_row['venueName']
        
        conn.close()
        
        # 7. Generate Instagram post URL from shortcode
        instagram_post_url = None
        if f_shortcode:
            instagram_post_url = f"https://www.instagram.com/p/{f_shortcode}/"
        
        # 8. Also save to Development Database (MusicFeedPlatform)
        # We now use a NEW function to save to event_ai in Dev DB
        save_ai_event_to_dev_db(
            venue_name, f_event_name, event_dates_json, f_content, db_image_url, artists_json,
            instagram_post_url=instagram_post_url,
            event_location=f_event_location,
            shortcode=f_shortcode
        )
        
        return True

    except Exception as e:
        print(f"Error saving single event: {e}")
        return False

def save_ai_event_to_dev_db(venue_name, event_name, event_dates_json, content, image_url, artists_json, instagram_post_url=None, event_location=None, shortcode=None):
    """
    Save event to MusicFeedPlatform Development Database (event_ai table).
    """
    try:
        conn = get_dev_db_connection()
        if not conn:
            print("[DevDB] MUSICFEED_DB_URL not set")
            return False
            
        cur = conn.cursor()
        
        # Parse JSONs
        import json
        
        # PostgreSQL Arrays/JSON handling makes this simpler or complex depending on driver
        # psycopg2 handles JSON string fine for JSONB
        
        cur.execute('''
            INSERT INTO event_ai (
                bot_id, event_name, venue_name, event_dates, 
                event_location, content, image_url, 
                performing_artists, instagram_link, shortcode
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            'pomfs-bot',
            event_name,
            venue_name,
            event_dates_json, # JSON string
            event_location,
            content,
            image_url,
            # performing_artists is TEXT[]
            # If artists_json is a JSON string "[a, b]", we need list
            json.loads(artists_json) if artists_json else [],
            instagram_post_url,
            shortcode
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DevDB] Saved to event_ai: {event_name}")
        return True
    
    except Exception as e:
        print(f"[DevDB] Error saving to event_ai: {e}")
        return False
