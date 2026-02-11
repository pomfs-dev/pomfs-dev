# P.O.MFS (Performance Organization AI Management For System)

> **Version**: v2.3.1 (Server Restart Recovery)  
> **Last Updated**: 2026-01-22

## Overview

P.O.MFS is a Flask-based backend system designed to automatically collect music performance information from Instagram and publish it to the MusicFeedPlatform. It automates event discovery and dissemination through scraping, AI analysis, and data integration, aiming to streamline music event promotion and accessibility.

**Key Capabilities:**
- Batch collection of hundreds of Instagram accounts simultaneously
- OCR + LLM powered event information extraction from poster images
- Video caption analysis for event detection
- Automatic geocoding and map positioning
- Shortcode-based duplicate prevention
- Automatic publishing to MusicFeedPlatform

## User Preferences

- 상세한 설명과 명확한 커뮤니케이션 선호
- 점진적 개발과 지속적인 피드백 루프
- 주요 아키텍처 변경이나 핵심 의존성 추가 전 사전 확인 요청
- scraped_data/ 폴더 수정 금지
- 보호된 파일: app.py, automation.py, analyzer.py, scraper_apify.py, scraper.py, db_helpers.py, db_utils.py, db_config.py, gcs_uploader.py, utils.py (수정 시 사전 승인 필요)

## System Architecture

### Data Flow Overview

```
Excel/Discovery → Apify Cloud → Neon DB → Mistral AI → GCS + MusicFeed DB
     ↓               ↓             ↓           ↓              ↓
  계정 목록      스크래핑       임시저장    OCR/LLM분석    최종 발행
```

1. **Image Posts**: Scrape → Local storage → Mistral OCR → LLM analysis → GCS upload → MusicFeed DB
2. **Video Posts**: Scrape caption only → LLM analysis → MusicFeed DB (no image)

### Background Processing

User interface actions initiate background threads via Flask API endpoints for long-running tasks. The API responds immediately while threads process work, updating a shared, lock-protected state. The UI polls a status API for real-time progress.

**Task Store Architecture:**
```python
task_store = {}  # In-memory task state (volatile)
# Structure: {task_id: {status, progress, result, error}}
```

**Known Limitation:** Task store is memory-based and lost on server restart. v2.3.1 adds client-side recovery.

### Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Frontend | Flask + Jinja2 + Bootstrap 5 | Admin UI with dark mode |
| Scraping Engine | Apify Cloud (primary), instagrapi (fallback) | Instagram data collection |
| AI Analysis | Mistral OCR + LLM | Image text extraction + event detection |
| Storage | Neon PostgreSQL + MusicFeed PostgreSQL + GCS | Data persistence |
| Geocoding | Google Places API | Address to coordinates conversion |

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| app.py | 2,484 | Flask main app, all API endpoints |
| automation.py | 463 | Auto-processing pipeline |
| db_utils.py | 450 | Neon DB utilities |
| db_helpers.py | 443 | MusicFeed DB helpers |
| analyzer.py | 296 | Mistral OCR/LLM analysis |
| batch_collection.html | 2,506 | Batch collection UI (large inline JS) |

### Database Schemas

**Neon PostgreSQL (`scraped_posts`):**
- Temporary storage for scraped data
- Fields: shortcode (unique), username, caption, image_path, is_event, event_*, is_video, processed
- UPSERT on shortcode for duplicate prevention

**MusicFeedPlatform PostgreSQL (`posts`):**
- Final published event data
- Fields: eventName, eventDates, venueId, performingArtists, image_url, latitude, longitude, etc.
- instagram_link used for duplicate check

### Event Detection Logic

Event detection uses OR condition (v2.0.0+):
- Title alone → Event
- Title + Dates → Event
- Venue + Dates → Event

### Batch Collection System

**Features:**
- Excel-based target management (`DB/batch_targets.xlsx`)
- Configurable concurrency (1-5 parallel workers)
- Configurable scrape limit per account
- Page-specific smart skip logic
- Real-time progress tracking with timers
- Batch session management

**Server Restart Recovery (v2.3.1):**
- 404 error detection: 3 consecutive 404s trigger graceful handling
- `checkServerRestartAndCleanup()`: Detects stale tasks on page load
- `stopProcessing()`: Works regardless of `isProcessing` state
- `resetBatchUI()`: Consistent UI state recovery
- Auto-cleanup of localStorage and user notification

**Batch Session API:**
- `/api/batch/start`: Start new batch session
- `/api/batch/end`: End batch session
- `/api/collection_stats`: Get collection statistics

## Recent Changes

### v2.3.1 (2026-01-22) - Server Restart Recovery
- **404 Error Handling**: Auto-detection after 3 consecutive 404 responses
- **Stop Button Fix**: Works even when `isProcessing` is false
- **Server Restart Detection**: `checkServerRestartAndCleanup()` on page load
- **UI Reset Function**: `resetBatchUI()` for consistent recovery

### v2.3.0 (2026-01-22) - Batch Report Fix
- Fixed batch report success/saved counts showing 0
- Added page-specific collection statistics
- Enhanced skip tracking with reason breakdown

### v2.2.0 (2026-01-22) - Smart Skip Logic
- Smart skip for already-collected accounts
- Page-specific skip application
- Batch session management

### v2.4.0 (2026-02-04) - Email Notification System
- DEV_NOTES.md 업데이트 시 자동 이메일 알림 기능 추가
- Replit Mail API 기반 Python 이메일 유틸리티 (replitmail.py)
- API 키 기반 인증 보호 (ADMIN_API_KEY 환경변수)
- 새 API 엔드포인트: /api/dev_notes (GET/POST), /api/dev_notes/test_email

### v2.1.0 (2026-01-22) - Video Caption Support
- Video caption collection and analysis
- LLM analysis without OCR for videos
- is_video flag for content type distinction

### v2.0.0 (2026-01-22) - Full Pipeline
- Complete pipeline integration for all 3 entry points
- OR-based event detection logic (less strict)
- Discovery API for venue scraping

## Known Issues & Technical Debt

### Critical Priority
1. **find_local_image() Performance**: O(n*m) glob scanning, needs caching
2. **app.py Size**: 2,484 lines, needs Blueprint refactoring

### High Priority
1. **batch_collection.html Size**: 2,506 lines of inline JavaScript
2. **Synchronous I/O**: Mistral/GCS/Geocoding calls block main thread
3. **Memory-based Task Store**: Lost on server restart

### Medium Priority
1. **N+1 Query Pattern**: In review/registered pages
2. **Unbounded scraped_data Growth**: No cleanup strategy
3. **localStorage Dependency**: No cross-browser sync

## API Endpoints Reference

### Batch Collection
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/batch_collection` | GET/POST | Batch collection page |
| `/api/batch_accounts` | GET | Get accounts list with pagination |
| `/api/batch_collection_status` | GET | Get task status |
| `/api/collection_stats` | POST | Get collection statistics |
| `/api/batch/start` | POST | Start batch session |
| `/api/batch/end` | POST | End batch session |

### Scraping
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/scrape` | GET/POST | Single account scraping |
| `/api/scrape_background` | POST | Background scraping task |

### Events
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/review` | GET | Review scraped posts |
| `/registered` | GET | View registered events |
| `/api/registered/publish` | POST | Publish event |
| `/api/registered/delete` | POST | Delete event |

### Documentation
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/docs` | GET | Codebase audit report viewer |

## External Dependencies

- **Apify Cloud:** Instagram scraping with proxy management
- **Mistral AI API:** OCR + LLM for event detection (1 req/sec rate limit)
- **Neon PostgreSQL:** Temporary scraped data storage
- **MusicFeedPlatform PostgreSQL:** Final event data storage
- **Google Cloud Storage:** Event image hosting
- **Google Places API:** Geocoding (3-step search strategy)
- **instagrapi:** Backup scraping method
- **pandas:** Excel file processing
- **Bootstrap 5:** Frontend UI framework

## Development Notes

### Code Conventions
- Dark mode UI design system (CSS variables)
- Korean language for user-facing text
- English for code comments and technical docs
- Flask Blueprint pattern recommended (not yet implemented)

### Testing
- Test mode: `ENV=TEST` uses SQLite instead of PostgreSQL
- Test DB reset: `POST /admin/reset_db`
- Test tool page: `/test_tool` for manual testing

### Performance Targets
| Metric | Current | Target |
|--------|---------|--------|
| Review page load | ~5s | <1s |
| Batch processing | 10/min | 30/min |
| Server restart recovery | Partial | Full |

### Improvement Roadmap
1. **Phase 1 (1 week)**: find_local_image cache, hardcoded secrets removal
2. **Phase 2 (1 month)**: app.py Blueprint split, JavaScript separation
3. **Phase 3 (3 months)**: Type hints, test coverage, async processing
