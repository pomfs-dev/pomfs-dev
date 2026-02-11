import sqlite3
import os
from db_config import SQLITE_DB_PATH

def init_test_db():
    print(f"⚠️  RESETTING TEST DATABASE: {SQLITE_DB_PATH}")
    
    if os.path.exists(SQLITE_DB_PATH):
        os.remove(SQLITE_DB_PATH)
        print(f"   - Deleted existing database file.")
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    
    with open('schema_test.sql', 'r', encoding='utf-8') as f:
        schema_sql = f.read()
        
    try:
        conn.executescript(schema_sql)
        print("   - ✅ Tables created successfully (venues, posts, venueEvents).")
        
        # Seed basic venue data for testing if needed
        # (Optional: Add some dummy venues matching the known accounts)
        # conn.execute("""
        #     INSERT INTO venues (venueName, instagramId, venueAddress) VALUES 
        #     ('The Roof Seoul', 'theroofseoul_', 'Seoul, Korea'),
        #     ('Leejean', 'leejeanius', 'Artist Profile'),
        #     ('Loozbone', 'loozbone', 'Venue Profile')
        # """)
        # print("   - ✅ Seed data inserted (3 venues).")
        print("   - ✅ DB initialized (Empty).")
        
        conn.commit()
    except Exception as e:
        print(f"   - ❌ Error initializing DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_test_db()
