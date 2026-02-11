# Project Context & Operations

**P.O.MFS (Performance Organization AI Management For System)**
Central backend for automating venue discovery, event extraction, and blog publishing.
**Tech Stack:** Python (Flask), SQLite (Dev), PostgreSQL (Neon/Prod), Apify, Mistral AI.

**Operational Commands**
- **Start Server:** `python app.py`
- **Run Tests:** `python test_v2_4_0.py`
- **Run Migration:** `python migrate_v2_4_0.py`
- **Reset DB:** `python init_test_db.py`

# Golden Rules

**Immutable**
- **Security:** API keys must NEVER be hardcoded. Use `.env`.
- **Data Integrity:** `scraped_data/` is immutable via manual edits; use scripts.
- **Circuit Breaker:** Stop scraping for 10 min after 3 consecutive Tier 1 (Apify) failures.
- **Schema Authority:** `schema_v2_4_0.sql` is the source of truth.

**Do's & Don'ts**
- **DO** use `db_helpers.py` for all DB interactions.
- **DO** respect 1 req/sec rate limit for Mistral AI.
- **DO NOT** commit large asset files (use `.gitignore`).
- **DO NOT** mix sync/async DB cursors without explicit context.

# Standards & References

- **Code Style:** PEP 8.
- **Versioning:** Semantic Versioning (Current: v2.4.0).
- **Maintenance:** Update this file on architecture changes.

# Context Map (Action-Based Routing)

- **[Database Logic](./DB/AGENTS.md)** — Schema definitions and migration scripts.
- **[Documentation](./docs/AGENTS.md)** — Project history and specific guides.
