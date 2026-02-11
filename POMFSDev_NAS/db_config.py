import sqlite3
import os

# Configuration switch: 'sqlite' or 'postgres'
# Change this to 'postgres' when deploying to Replit or production

# Environment: 'TEST' (Local SQLite) vs 'PROD' (Production/Replit)
# You can switch this manually or via os.environ
ENV = os.environ.get('POMFS_ENV', 'TEST')

if ENV == 'TEST':
    DB_TYPE = 'sqlite'
    SQLITE_DB_PATH = 'test_pomfs.db' # The "Notebook" (Practice DB)
else:
    # PROD settings (Placeholder)
    DB_TYPE = 'postgres'
    # PG_CONFIG = ...

# SQLite Config
# SQLITE_DB_PATH is defined above based on ENV

def get_db_connection():
    """
    Returns a database connection object based on DB_TYPE.
    """
    if DB_TYPE == 'sqlite':
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn
    elif DB_TYPE == 'postgres':
        # import psycopg2
        # conn = psycopg2.connect(**PG_CONFIG)
        # return conn
        raise NotImplementedError("PostgreSQL connection not yet implemented. Please install psycopg2 and configure PG_CONFIG.")
    else:
        raise ValueError(f"Unknown DB_TYPE: {DB_TYPE}")
