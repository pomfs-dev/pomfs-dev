import unittest
import os
import sqlite3
import json
from db_config import get_db_connection
from db_helpers import save_single_event

class TestV240Migration(unittest.TestCase):
    def setUp(self):
        # Use TEST environment
        os.environ['POMFS_ENV'] = 'TEST'
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()

    def test_01_table_exists(self):
        """Verify event_ai table exists in SQLite"""
        try:
            self.cur.execute("SELECT count(*) FROM event_ai")
            count = self.cur.fetchone()[0]
            print(f"event_ai row count: {count}")
            self.assertTrue(True)
        except sqlite3.OperationalError as e:
            self.fail(f"event_ai table does not exist or error: {e}")

    def test_02_save_single_event(self):
        """Test save_single_event writing to event_ai"""
        sample_data = {
            'event_name': 'Test Event V2.4',
            'venue_id': 'NEW',
            'new_venue': 'Test Venue',
            'event_date': '2026-12-31',
            'content': 'Test Content',
            'shortcode': 'test_v2_4_shortcode',
            'filename': 'test.jpg'
        }
        
        success = save_single_event(sample_data)
        self.assertTrue(success, "save_single_event failed")
        
        # Verify in DB
        row = self.cur.execute("SELECT * FROM event_ai WHERE shortcode='test_v2_4_shortcode'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['event_name'], 'Test Event V2.4')
        print("✅ Successfully saved and retrieved from event_ai")

    def test_03_get_events(self):
        """Test get_all_registered_events fetching from event_ai"""
        from db_helpers import get_all_registered_events
        # We assume test_02 ran or we insert a new one
        # Insert a fresh one to be sure
        self.test_02_save_single_event()
        
        events = get_all_registered_events()
        self.assertTrue(len(events) > 0)
        found = False
        for e in events:
            if e['event_name'] == 'Test Event V2.4':
                found = True
                break
        self.assertTrue(found, "Could not find the saved event in get_all_registered_events result")
        print("✅ get_all_registered_events working correctly with event_ai")

    def tearDown(self):
        self.conn.close()

if __name__ == '__main__':
    unittest.main()
