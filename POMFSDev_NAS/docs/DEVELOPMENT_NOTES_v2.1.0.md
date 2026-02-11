# P.O.MFS Development Notes (v2.1.0)

## Current Version
**Version:** v2.1.0 (Video Caption Support)  
**Last Updated:** 2026-01-22

---

## Overview

P.O.MFS is a Flask-based backend system designed to automatically collect music performance information from Instagram and publish it to the MusicFeedPlatform.

**Key Capabilities:**
- Automatic collection of performance posters from Instagram accounts using Apify Cloud.
- AI-driven image analysis (Mistral OCR + LLM) for event detection.
- **Video post support (v2.1.0):** Caption-based event extraction for video posts without image download.
- Structured extraction of event information (event name, venue, dates, artists, time, country).
- Automated geocoding via Google Geocoding API.
- Google Cloud Storage (GCS) image upload and automatic publishing to MusicFeedPlatform DB.
- Duplicate prevention using a shortcode-based UPSERT pattern.
- Background batch processing for re-analysis and bulk OCR.

---

## User Preferences

- 상세한 설명과 명확한 커뮤니케이션 선호
- 점진적 개발과 지속적인 피드백 루프
- 주요 아키텍처 변경이나 핵심 의존성 추가 전 사전 확인 요청
- scraped_data/ 폴더 수정 금지
- 보호된 파일: app.py, automation.py, analyzer.py, scraper_apify.py, scraper.py, db_helpers.py, db_utils.py, db_config.py, gcs_uploader.py, utils.py (수정 시 사전 승인 필요)

---

## System Architecture

### Data Flow Overview

**For Image Posts:**
Images are processed by Mistral OCR, and the extracted text is analyzed by Mistral LLM for event detection. If an event is identified, the image is uploaded to GCS and structured event data is saved to MusicFeedPlatform database.

**For Video Posts (v2.1.0):**
Video content is skipped (not downloaded), but captions are collected and stored. The caption text is directly passed to Mistral LLM for event detection without OCR processing. Events from video posts are saved without image files.

### Background Processing Architecture
User interface actions trigger Flask API endpoints, which initiate background threads for tasks like batch processing or re-analysis. The API responds immediately while the thread performs the work, updating a shared, lock-protected state. The UI polls a status API endpoint to display real-time progress.

### Core Components
- **Web Frontend:** Flask + Jinja2 for UI
- **Scraping Engine:** Primarily Apify Cloud, with instagrapi as a fallback. Supports both image and video posts (v2.1.0).
- **AI Analysis:** Mistral OCR for text extraction (images only) and Mistral LLM for event detection.
- **Storage Layer:** Neon PostgreSQL for temporary scraped data, MusicFeedPlatform PostgreSQL for final event data, and Google Cloud Storage for images.
- **Geocoding:** Google Places API with a 3-step search strategy.
- **Duplicate Prevention:** Instagram shortcode UPSERT pattern.

### Database Schemas
- **Neon PostgreSQL (scraped_posts):** Includes is_video flag for video posts. Uses shortcode as a unique identifier.
- **MusicFeedPlatform PostgreSQL (posts):** GCS image URLs (NULL for video posts), is_draft=False for immediate publishing.

---

## Core Features - All Using Full Pipeline

### Three Core Features (All Working)

| Feature | Route | Description | Status |
|---------|-------|-------------|--------|
| **Batch Collection** | /batch_collection | Excel 기반 대량 계정 수집 | Full Pipeline |
| **Scrape** | /scrape | 단일 계정 수집 | Full Pipeline |
| **Discovery** | /discovery | 베뉴 Instagram ID 발견 + 수집 | Full Pipeline |

### Full Pipeline Flow

**Image Posts:**
```
Instagram -> Apify Scraping -> Neon DB -> OCR -> LLM Analysis -> 
If Event: GCS Upload + Geocoding -> MusicFeed DB (is_draft=False)
```

**Video Posts (v2.1.0):**
```
Instagram -> Apify Scraping (caption only) -> Neon DB -> LLM Analysis (caption) -> 
If Event: Geocoding -> MusicFeed DB (is_draft=False, no image)
```

### Event Detection Logic (v2.0.0 - OR 조건)
```
조건 1: 공연명만 있어도 이벤트 (title alone)
조건 2: 공연명 + 날짜 (title + dates)
조건 3: 장소 + 날짜 (venue + dates)
```

### Video Post Handling (v2.1.0)
```
1. Apify에서 게시물 수집 시 is_video 플래그 확인
2. 비디오 게시물: 이미지 다운로드 스킵, 캡션만 저장
3. 분석 시: OCR 스킵, 캡션 텍스트로 직접 LLM 분석
4. 이벤트 감지 시: GCS 업로드 없이 DB 저장 (image_url = NULL)
```

---

## Current Status (2026-01-22)

### Recent Activities
- **v2.1.0 Video Caption Support (2026-01-22):** Video posts now analyzed using captions only
- **Full Pipeline Integration (2026-01-22):** All three core features now use complete pipeline
- **Event Detection Relaxed:** Changed from AND to OR logic for better event capture
- **Discovery API Added:** /api/discovery/scrape_venue and /api/discovery/batch_scrape
- **Bug Fixes:** Fixed undefined filename variable, reanalysis workflow completion
- **MusicFeed DB:** Contains pomfs_ai records with is_draft=False, coordinates, GCS URLs

### All Issues Resolved

| 심각도 | 이슈 | 원인 | 상태 |
|--------|------|------|------|
| Resolved | 비디오 게시물 완전 스킵됨 | is_video 시 early return | 캡션 수집으로 수정 |
| Resolved | filename 변수 미정의 | existing_valid_images[0] 할당 누락 | 수정 완료 |
| Resolved | MusicFeed DB에 pomfs_ai 레코드 없음 | 버그로 저장 호출 안됨 | 수정 완료 |
| Resolved | 재분석 워크플로우 불완전 | Geocoding, GCS, MusicFeed 누락 | 수정 완료 |
| Resolved | 이벤트 판정 조건 너무 엄격 | AND 로직 사용 | OR 로직으로 완화 |
| Resolved | Discovery 전체 파이프라인 미연동 | API 엔드포인트 없음 | API 추가 완료 |

### Known Technical Debt (Remaining)

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| 동시성 레이스 컨디션 (concurrency > 1) | Medium | 미해결 |
| 서버 재시작 시 세션 손실 | Medium | 미해결 |
| app.py 거대 파일 (2,000+ 라인) | Medium | 미해결 |
| 빈 캡션 비디오 게시물 처리 | Low | 미해결 (스킵 처리) |

---

## API Endpoints

### Core Collection APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| /scrape_stream | GET | SSE 스트림으로 단일 계정 수집 + 분석 |
| /api/scrape_background | POST | 백그라운드 단일 계정 수집 |
| /api/batch/start | POST | 배치 수집 시작 |
| /api/batch/status | GET | 배치 수집 상태 확인 |

### Discovery APIs (v2.0.0)
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/discovery/scrape_venue | POST | 단일 베뉴 Instagram ID 수집 + 전체 파이프라인 |
| /api/discovery/batch_scrape | POST | 발견된 모든 베뉴 일괄 수집 |

### Reanalysis APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/reanalyze/start | POST | 재분석 시작 (전체 파이프라인 적용) |
| /api/reanalyze/status | GET | 재분석 상태 확인 |

---

## File Structure

### Core Python Files (수정 시 사전 승인 필요)
- app.py - Flask 메인 앱, 모든 API 엔드포인트
- automation.py - 자동 처리 파이프라인, 비디오 캡션 분석 포함
- analyzer.py - Mistral OCR/LLM 분석 파이프라인
- scraper_apify.py - Apify Instagram 스크래핑, 비디오 캡션 수집 지원
- geocoder.py - Google Geocoding API 연동
- db_helpers.py - MusicFeedPlatform DB 헬퍼
- db_utils.py - Neon DB 유틸리티
- gcs_uploader.py - Google Cloud Storage 업로드

### Templates
- templates/batch_collection.html - 배치 수집 페이지
- templates/dashboard.html - 메인 대시보드
- templates/review.html - 스크랩 게시물 검토
- templates/scrape.html - 단일 계정 수집 페이지
- templates/venue_discovery.html - 베뉴 발견 페이지

---

## Development Notes

### Architecture Decision Records

#### ADR-001: Selenium to Apify 전환
- **배경**: Instagram 봇 탐지로 Selenium 차단 빈발
- **결론**: Apify Cloud 도입으로 안정성 확보

#### ADR-002: Mistral API 선택
- **배경**: 한국어/일본어 포스터 OCR + 이벤트 정보 구조화 필요
- **결론**: 비용 대비 품질 우수, Rate Limit (1 req/sec) 대응 구현

#### ADR-003: Shortcode 기반 중복 방지
- **배경**: 동일 게시물 중복 저장 문제
- **결론**: Instagram shortcode를 UNIQUE 키로 사용

#### ADR-004: localStorage 기반 세션 유지
- **배경**: 페이지 이동 시 진행 상태 손실 UX 문제
- **결론**: 하이브리드 접근 (localStorage + 서버 세션)

#### ADR-005: 이벤트 판정 조건 완화 (v2.0.0)
- **배경**: AND 조건이 너무 엄격하여 이벤트 저장률 0%
- **결론**: OR 조건으로 완화 (공연명만 OR 장소+날짜)

#### ADR-006: 비디오 게시물 캡션 분석 (v2.1.0)
- **배경**: 비디오 게시물이 완전히 스킵되어 공연 정보 손실
- **문제**: 비디오 콘텐츠는 다운로드/분석 불가, 하지만 캡션에 공연 정보 포함
- **결론**: 
  - 비디오 게시물: 이미지 다운로드 스킵, 캡션 텍스트만 수집
  - OCR 스킵, 캡션으로 직접 LLM 분석
  - 이벤트 감지 시 GCS 업로드 없이 MusicFeed DB 저장
- **영향받는 파일**: scraper_apify.py, automation.py

---

## Version History

| 버전 | 날짜 | 코드명 | 주요 변경사항 |
|------|------|--------|--------------|
| v2.1.0 | 2026-01-22 | Video Caption | 비디오 게시물 캡션 수집 및 분석 지원 |
| v2.0.0 | 2026-01-22 | Full Pipeline | 3개 핵심 기능 전체 파이프라인 통합, OR 이벤트 판정 |
| v1.9.6 | 2026-01-22 | Bug Fixes | filename 버그 수정, 재분석 파이프라인 완성 |
| v1.8.0 | 2026-01-19 | Session Geocoding | Geocoding 자동화, 중복 방지, localStorage 세션 |
| v1.7.0 | 2026-01-16 | Migration Ops | 마이그레이션 도구, 배치 리포트 |
| v1.6.0 | 2026-01-16 | Cloud Beta | Apify Scraper 연동, 다크 모드 |

---

## Environment Variables Required

| 변수명 | 설명 | 필수 |
|--------|------|------|
| APIFY_TOKEN | Apify Cloud API 토큰 | O |
| MISTRAL_API_KEY | Mistral OCR/LLM API 키 | O |
| NEON_DB_URL | Neon PostgreSQL 연결 URL | O |
| MUSICFEED_DB_URL | MusicFeedPlatform DB 연결 URL | O |
| GOOGLE_CLOUD_PROJECT_ID | GCP 프로젝트 ID | O |
| GOOGLE_CLOUD_BUCKET_NAME | GCS 버킷명 | O |
| GOOGLE_CLOUD_CREDENTIALS | GCP 서비스 계정 JSON | O |
| GOOGLE_PLACES_API_KEY | Google Geocoding API 키 | O |

---

## Testing Results (2026-01-22)

### Full Pipeline Test - Image Post
```
Account: 001_club
Result: 
  - is_event_poster: True
  - event_name: WO.B[우비]
  - dates: ['2025-07-18']
  - venue: 001클럽
  - location: 서울 마포구 와우산로18길 20
  - db_status: Duplicate (already saved)
```

### Full Pipeline Test - Video Post (v2.1.0)
```
Account: 054soundville
Shortcode: DR_jgDXE10O
Result:
  - is_video: True
  - image_download: Skipped
  - caption_collected: Yes (296 chars)
  - ocr_performed: No (video post)
  - llm_analysis: Caption only
  - is_event_poster: True
  - event_name: 미리메리크리스마스
  - dates: ['2025-11-01']
  - venue: N/A (캡션에 명시 안됨)
  - db_status: Saved to MusicFeed DB
```

### MusicFeed DB Status
```
Total pomfs_ai posts: 5
- 미리메리크리스마스 @ N/A | coords: NULL | draft: False (VIDEO)
- WO.B[우비] @ 001클럽 | coords: 37.5510, 126.9240 | draft: False
- 1959 MUSIC PIECE @ N/A | coords: NULL | draft: False
- MOB @ N/A | coords: NULL | draft: False
```

---

## Implementation Details

### Video Caption Processing Flow

**scraper_apify.py - 비디오 게시물 감지 및 캡션 수집:**
```python
if post.get('isVideo', False):
    print(f"[ApifyScraper] Video post {shortcode} - skipping image download, keeping caption")
    post_data['is_video'] = True
    # Caption is still saved, images list remains empty
```

**automation.py - 비디오 게시물 분석:**
```python
if post_data.get('is_video'):
    print(f"[Automation] Video post {shortcode} - analyzing caption only")
    # Skip OCR, use caption text directly for LLM analysis
    analysis = analyzer.extract_structured_info(caption_text)
    # If event detected, save without GCS upload
```

### Key Code Changes (v2.1.0)

**scraper_apify.py:**
- Video posts no longer skipped entirely
- Caption and metadata preserved
- is_video flag added to post_data
- Image download only skipped for video posts

**automation.py:**
- Video posts analyzed using caption only
- OCR step skipped for videos
- Events can be saved without image files
- filename_prefix generated for videos without images
- Full pipeline (Geocoding -> MusicFeed DB) works for both image and video posts

---

## External Dependencies

| 의존성 | 용도 | 비고 |
|--------|------|------|
| Apify Cloud | Instagram 스크래핑 | 이미지/비디오 게시물 지원 |
| Mistral AI API | OCR (이미지) + LLM (이벤트 감지) | Rate limit: 1 req/sec |
| Neon PostgreSQL | 임시 스크랩 데이터 저장 | UPSERT 패턴 사용 |
| MusicFeedPlatform PostgreSQL | 최종 이벤트 데이터 | is_draft=False 자동 게시 |
| Google Cloud Storage | 이벤트 이미지 저장 | 비디오는 이미지 없음 |
| Google Places API | 위치 좌표 조회 | 3단계 검색 전략 |
| instagrapi | 백업 스크래핑 | Apify 실패 시 사용 |
