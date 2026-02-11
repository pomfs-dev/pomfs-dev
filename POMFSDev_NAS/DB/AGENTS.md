# Module Context

This directory (`DB/`) contains database schema definitions (`.sql`), migration logic, and batch targets.
Crucial for v2.4.0 transition (Posts -> Event_AI/Event_User split).

# Tech Stack & Constraints
- SQL Dialect: PostgreSQL (Neon) primarily, compatible with SQLite for local dev.
- Migration Scripts: Python (`migrate_*.py`) located in root but rely on schemas here.

# Implementation Patterns
- Schema Files: Named as `schema_vX_Y_Z.sql`.
- Targets: `batch_targets.xlsx` drives the scraping target list.

# Local Golden Rules

**Do's & Don'ts**
- DO ensure all `CREATE TABLE` statements use `IF NOT EXISTS`.
- DO NOT modify `batch_targets.xlsx` structure (columns) without updating `app.py`.
- DO test SQL compatibility with both SQLite and PostgreSQL where possible.
