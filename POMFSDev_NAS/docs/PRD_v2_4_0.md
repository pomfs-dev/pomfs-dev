# Product Requirement Document (PRD) - P.O.M.F.S v2.4.0

## 1. Project Overview
**Product Name:** P.O.M.F.S (Performance Organization AI Management For System)
**Version:** v2.4.0
**Status:** Implementation Phase
**Owner:** Backend Architecture Team

## 2. Executive Summary
v2.4.0 aims to resolve technical debt regarding database scalability and enhance monitoring capabilities. The monolithic `posts` table will be normalized into specialized tables (`event_ai`, `event_user`, etc.), and a secure email notification system will be implemented for development tracking.

## 3. Key Objectives
1.  **Database Normalization:** Segregate AI-collected data from user-generated content to improve query performance and data integrity.
2.  **Monitoring Enhancement:** Implement an automated email notification system for `DEV_NOTES.md` updates.
3.  **Legacy Compatibility:** Ensure existing API endpoints function correctly with the new schema via an abstraction layer or direct updates.

## 4. Feature Specifications

### 4.1. Schema Migration (Core)
**Description:** Transition from single `posts` table to multi-table architecture.
**Requirements:**
-   **New Tables:**
    -   `event_ai`: Stores events scraped and analyzed by AI (Bot).
    -   `event_user`: Stores events manually registered by users.
    -   `feed_ai` / `feed_user`: Stores non-event feed posts.
-   **Migration Script (`migrate_v2_4_0.py`):**
    -   Must define `bot_id` for converted records.
    -   Must handle JSON serialization differences between SQLite and PostgreSQL.
    -   Must be idempotent (safe to run multiple times).

### 4.2. Email Notification System
**Description:** Notify administrator when critical documentation changes.
**Requirements:**
-   **Trigger:** Updates to `DEV_NOTES.md`.
-   **Transport:** Replit Mail API (via `replitmail.py` utility).
-   **Security:** `ADMIN_API_KEY` required for trigger endpoints.
-   **Endpoints:**
    -   `GET /api/dev_notes`: Retrieve current notes.
    -   `POST /api/dev_notes`: Update notes and trigger email.

## 5. Technical Constraints (Golden Rules)
-   **No Hardcoded Keys:** All API keys (Mistral, Admin, DB) must be in `.env`.
-   **Environment Parity:** Logic must support both SQLite (Test) and Neon PostgreSQL (Prod).
-   **Performance:** usage of `event_ai` should not degrade read performance compared to `posts`.

## 6. Success Metrics
-   **Data Integrity:** 100% of valid `pomfs_ai` category posts migrated to `event_ai`.
-   **API Uptime:** Critical endpoints (`/registered`, `/api/save_event_manual`) pass regression tests.
-   **Notification:** Email delivered within 1 minute of `DEV_NOTES.md` update.

## 7. Migration Strategy
1.  **Backup:** Snapshot `posts` table.
2.  **Schema Apply:** Run `schema_v2_4_0.sql`.
3.  **Data Transfer:** Execute `migrate_v2_4_0.py`.
4.  **Verification:** Run `test_v2_4_0.py` and manual UI check.
5.  **Deprecation:** Rename `posts` to `posts_legacy` after 1 week of stability.
