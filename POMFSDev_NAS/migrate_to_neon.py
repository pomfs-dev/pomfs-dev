import os
import sqlite3
import psycopg2
import json
from dotenv import load_dotenv

load_dotenv()

# Configuration
LOCAL_DB_PATH = "test_pomfs.db"
NEON_DB_URL = os.environ.get("NEON_DB_URL") or os.environ.get("DATABASE_URL")


def get_sqlite_conn():
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_postgres_conn():
    if not NEON_DB_URL:
        print("[Error] NEON_DB_URL or DATABASE_URL not found in .env")
        print(
            "Please add 'NEON_DB_URL=postgres://user:pass@...' to your .env file."
        )
        return None
    try:
        return psycopg2.connect(NEON_DB_URL)
    except Exception as e:
        print(f"[Error] Connecting to Postgres: {e}")
        return None


def migrate_venues(local_conn, pg_conn):
    print("\n--- Migrating Venues ---")
    local_cur = local_conn.cursor()
    pg_cur = pg_conn.cursor()

    local_cur.execute("SELECT * FROM venues")
    venues = local_cur.fetchall()

    venue_map = {}  # Local ID -> Remote ID

    for v in venues:
        local_id = v['id']
        name = v['venueName']
        alias = v['alias'] if 'alias' in v.keys() else None

        # Check existence in Postgres
        pg_cur.execute("SELECT id FROM venues WHERE \"venueName\" = %s",
                       (name, ))
        exists = pg_cur.fetchone()

        if exists:
            remote_id = exists[0]
            print(f"[Skip] Venue '{name}' exists (ID: {remote_id})")
        else:
            print(f"[Insert] Venue '{name}'...")
            # Adjust column names based on standard schema
            # Assuming standard schema has: venueName, alias, status, etc.
            pg_cur.execute(
                "INSERT INTO venues (\"venueName\", status) VALUES (%s, %s) RETURNING id",
                (name, 'active'))
            remote_id = pg_cur.fetchone()[0]

        venue_map[local_id] = remote_id

    pg_conn.commit()
    print(f"Venues migrated. Map size: {len(venue_map)}")
    return venue_map


def migrate_posts(local_conn, pg_conn, venue_map):
    print("\n--- Migrating Posts ---")
    local_cur = local_conn.cursor()
    pg_cur = pg_conn.cursor()

    local_cur.execute("SELECT * FROM posts")
    posts = local_cur.fetchall()

    migrated_count = 0
    skipped_count = 0

    for p in posts:
        local_venue_id = p['venueId']
        remote_venue_id = venue_map.get(local_venue_id)

        if not remote_venue_id:
            print(
                f"[Warn] No venue mapping for Local Venue ID {local_venue_id}. Skipping post '{p['eventName']}'"
            )
            continue

        # Check duplication
        # Using same logic: venueId + eventName (simple check)
        pg_cur.execute(
            "SELECT id FROM posts WHERE \"venueId\" = %s AND \"eventName\" = %s",
            (remote_venue_id, p['eventName']))
        if pg_cur.fetchone():
            skipped_count += 1
            # print(f"[Skip] Post '{p['eventName']}' exists.")
            continue

        # Insert
        try:
            # Fixing JSON fields if they are strings in SQLite
            performers = p['performingArtists']
            dates = p['eventDates']

            # Helper to ensure valid JSON string for Postgres JSONB
            # If it's already a string in SQLite, pass it. If it's bytes/obj, convert?
            # SQLite stores JSON as TEXT. Postgres expects JSON/JSONB.
            # psycopg2 handles JSON automatically if using Json adapter, or pass string.

            pg_cur.execute(
                """
                INSERT INTO posts (
                    "userId", category, subcategory, 
                    "venueId", "eventName", "eventDates", 
                    content, "imageUrl", "performingArtists", 
                    "isDraft", "createdAt"
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    'admin_migration',  # Distinct userId
                    p['category'],
                    p['subcategory'],
                    remote_venue_id,
                    p['eventName'],
                    dates,  # Pass raw JSON string
                    p['content'],
                    p['imageUrl'],
                    performers,  # Pass raw JSON string
                    p['isDraft']))
            migrated_count += 1
        except Exception as e:
            print(f"[Error] Failed to insert post '{p['eventName']}': {e}")
            pg_conn.rollback()  # Rollback transaction to save previous
            continue

    pg_conn.commit()
    print(
        f"Migration Complete. Imported: {migrated_count}, Skipped: {skipped_count}"
    )


if __name__ == "__main__":
    print("Starting Migration...")

    l_conn = get_sqlite_conn()
    p_conn = get_postgres_conn()

    if l_conn and p_conn:
        v_map = migrate_venues(l_conn, p_conn)
        migrate_posts(l_conn, p_conn, v_map)

        l_conn.close()
        p_conn.close()
        print("Done.")
