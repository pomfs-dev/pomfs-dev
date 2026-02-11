# MusicFeedPlatform 이벤트 포스트 자동화 시스템 - 상세 개발 노트

> **버전**: v2.3.1 (Server Restart Recovery)  
> **최종 업데이트**: 2026-01-22

## Overview
**MusicFeedPlatform의 이벤트 포스트 작성 자동화**를 위한 Flask 기반 백엔드 시스템입니다.

### 핵심 목표
1. **Instagram 자동 수집**: Apify를 통해 공연/이벤트 관련 인스타그램 계정에서 포스트 수집
2. **AI 이미지 분석**: Mistral API로 이미지 OCR 및 공연 정보 추출 (공연 포스터 자동 판별)
3. **자동 데이터 마이닝**: 수집된 데이터를 MusicFeedPlatform 포맷에 맞게 자동 변환
4. **자동 게시**: MusicFeedPlatform DB에 저장하여 메인 캐러셀카드에 자동 표시

---

## System Architecture

### 데이터 흐름 다이어그램
```
[Excel 계정 목록]
       |
       v
[Apify Instagram Scraper] --> [scraped_data/YYYY-MM-DD/username/]
       |                                    |
       v                                    v
[Neon DB: scraped_posts]              [이미지 파일들 (.jpg, .png)]
       |                                    |
       +--------------> [Mistral OCR API] <-+
                            |
                            v
                   [Mistral LLM 분석]
                            |
                +--- is_event_poster? ---+
                |                        |
                v                        v
             [True]                   [False]
                |                        |
                v                        v
    [GCS 이미지 업로드]         [Skipped (Not Event)]
                |
                v
    [MusicFeedPlatform DB 저장]
        (is_draft=False)
                |
                v
    [메인 캐러셀카드 표시]
```

### 주요 컴포넌트
1. **Web Frontend** (Flask + Jinja2) - 배치 수집 UI, 검토 페이지, 등록된 이벤트 목록
2. **Scraping Engine** (Apify Cloud / instagrapi fallback) - Instagram 포스트 및 이미지 수집
3. **AI Analysis Pipeline** (Mistral API) - OCR 텍스트 추출 + LLM 구조화 분석
4. **Storage Layer** - Neon PostgreSQL (임시), MusicFeedPlatform PostgreSQL (최종), GCS (이미지)

---

## Project Structure

### 핵심 파일

| 파일명 | 역할 | 주요 함수/클래스 |
|--------|------|-----------------|
| `app.py` | Flask 메인 앱, API 라우팅 | `/batch`, `/review`, `/registered`, `/api/*` |
| `automation.py` | 자동화 파이프라인 오케스트레이션 | `run_full_scrape_process()` |
| `analyzer.py` | AI 분석 (OCR + LLM) | `MistralAnalyzer`, `parse_date_info()` |
| `scraper_apify.py` | Apify 클라우드 스크래핑 | `ApifyScraper.get_recent_posts_iter()` |
| `scraper.py` | 로컬 스크래핑 (fallback) | `InstagramScraper` |
| `db_helpers.py` | MusicFeedPlatform DB 헬퍼 | `save_to_dev_db()`, `save_single_event()` |
| `geocoder.py` | Google Geocoding API 모듈 | `geocode_location()`, `geocode_batch()` |
| `db_utils.py` | Neon DB CRUD | `save_scraped_post()` |
| `db_config.py` | SQLite 로컬 DB 설정 | `get_db_connection()` |
| `gcs_uploader.py` | GCS 이미지 업로드 | `upload_image_to_gcs()` |
| `utils.py` | 유틸리티 함수들 | `save_local_image()` |
| `venue_discovery.py` | 장소 Instagram ID 검색 | `search_instagram_id()` |
| `selenium_search.py` | Google 심층 검색 (Selenium) | `search_venue_google()` |
| `marketing_generator.py` | 마케팅 이미지/캡션 생성 | `MarketingGenerator` |
| `migrate_to_neon.py` | SQLite→PostgreSQL 마이그레이션 | `migrate_venues()`, `migrate_posts()` |

### 템플릿 파일

| 파일명 | 역할 |
|--------|------|
| `templates/batch_collection.html` | 배치 수집 UI (엑셀 업로드, 슬라이더, 진행률) |
| `templates/scrape.html` | 단일 계정 수집 UI (다크 테마, 결과 리포트 카드, 터미널 로그) |
| `templates/review.html` | 수집 데이터 검토 (Neon DB) |
| `templates/registered.html` | 등록된 이벤트 목록 (MusicFeedPlatform DB) |
| `templates/index.html` | 메인 페이지 |
| `templates/discovery.html` | 장소 Instagram ID 검색 UI |
| `templates/marketing.html` | 마케팅 이미지/캡션 생성 UI |
| `templates/migration.html` | 데이터 마이그레이션 UI |

### 데이터 폴더 구조
```
scraped_data/
+-- YYYY-MM-DD/                    # 수집 날짜별 폴더
    +-- {username}/                # 계정별 폴더
    |   +-- {shortcode}_0.jpg      # 첫 번째 이미지
    |   +-- {shortcode}_1.jpg      # 캐러셀 두 번째 이미지
    |   +-- {shortcode}_0_ocr.txt  # OCR 결과 텍스트
    +-- {username}_results.csv     # 분석 결과 CSV
```

---

## 환경 변수

### 필수 (Required)

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `APIFY_TOKEN` | Apify API 토큰 | `apify_api_xxxxx` |
| `MISTRAL_API_KEY` | Mistral AI API 키 | `xxxxx` |
| `MUSICFEED_DB_URL` | MusicFeedPlatform PostgreSQL URL | `postgresql://user:pass@host/db` |
| `NEON_DB_URL` | Neon PostgreSQL URL (임시 저장) | `postgresql://user:pass@host/db` |

### 선택 (Optional)

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `GOOGLE_CLOUD_PROJECT_ID` | GCP 프로젝트 ID | - |
| `GOOGLE_CLOUD_BUCKET_NAME` | GCS 버킷 이름 | `communitystorage2` |
| `GOOGLE_CLOUD_CREDENTIALS` | GCP 서비스 계정 JSON | - |

---

## External API Limits

### Apify (Instagram 스크래핑) - Starter Plan ($39/월)

| 항목 | 값 |
|------|-----|
| 월 크레딧 | $29 prepaid platform usage |
| Actor RAM | 32 GB |
| 동시 Actor 수 | 최대 32개 |
| **권장 동시 작업 수** | **5-6개** (안정성) |
| Compute Unit 비용 | $0.30/CU |

**주의**: Free 플랜(8GB RAM)에서는 동시 작업 3-4개가 한계

### Mistral API (OCR/분석)

| 항목 | 값 |
|------|-----|
| **Rate Limit** | **초당 1 요청 (1 req/sec)** |
| 월 한도 | $150 |
| 분당 토큰 | 500,000 |
| 처리 방식 | 순차 처리 + 1초 딜레이 |

---

## AI 분석 파이프라인

### 1단계: OCR 텍스트 추출
```python
# analyzer.py - MistralAnalyzer.extract_text()
response = self.client.ocr.process(
    model="mistral-ocr-latest",
    document={
        "type": "image_url",
        "image_url": f"data:image/jpeg;base64,{base64_img}"
    }
)
```
- 이미지를 Base64로 인코딩하여 전송
- Markdown 형식으로 텍스트 반환

### 2단계: LLM 구조화 분석
```python
# analyzer.py - MistralAnalyzer.parse_info()
prompt = """
Analyze the text below and extract event information into a JSON object.

FIRST, determine if this is a concert/performance/event poster:
- Event posters typically contain: dates, venue names, artist/performer names, ticket info
- NOT event posters: personal photos, food/restaurant posts, travel photos, product ads

Fields required:
- "is_event_poster": true/false
- "dates": List of dates in "YYYY-MM-DD" format
- "venue": Name of the venue (short name, NOT full address)
- "location": Full address if available
- "artist": Name of the artist or "Various" if multiple
- "title": Event title
"""
```

### 3단계: Fallback 휴리스틱 (LLM 실패 시)
```python
# analyzer.py - parse_date_info()
# 정규식 기반 날짜/장소/아티스트 추출
# is_event_poster 판별 조건: dates AND venue가 모두 있으면 True
if info['dates'] and info['venue']:
    info['is_event_poster'] = True
```

### 4단계: 날짜 연도 스마트 추론
연도가 명시되지 않은 날짜(예: "12.04", "1월 15일")에 대해 스마트한 연도 추론을 적용합니다.

```python
# analyzer.py - infer_year_for_month()
def infer_year_for_month(event_month):
    """
    연초/연말 경계 전환만 특별 처리, 나머지는 올해로 유지
    
    규칙:
    - 연초(1-3월)에 10-12월 이벤트 수집 → 지난해
    - 연말(10-12월)에 1-3월 이벤트 수집 → 내년
    - 그 외 모든 경우 → 올해
    """
    is_early_year = current_month <= 3   # Jan-Mar
    is_late_year = current_month >= 10   # Oct-Dec
    is_early_event = event_month <= 3    # Jan-Mar
    is_late_event = event_month >= 10    # Oct-Dec
    
    if is_early_year and is_late_event:
        return current_year - 1          # 지난해
    elif is_late_year and is_early_event:
        return current_year + 1          # 내년
    else:
        return current_year              # 올해
```

**예시 (현재 1월 기준)**:
| 이벤트 월 | 조건 | 결과 |
|----------|-----|------|
| 12월     | early_year + late_event | 2025 (지난해) |
| 11월     | early_year + late_event | 2025 (지난해) |
| 8월      | neither | 2026 (올해) |
| 4월      | neither | 2026 (올해) |

**예시 (현재 12월 기준)**:
| 이벤트 월 | 조건 | 결과 |
|----------|-----|------|
| 1월      | late_year + early_event | 2027 (내년) |
| 2월      | late_year + early_event | 2027 (내년) |
| 9월      | neither | 2026 (올해) |

### Rate Limiting 구현
```python
# Global rate limiter (threading-safe)
_mistral_rate_lock = threading.Lock()
_mistral_last_request_time = 0

def _wait_for_rate_limit():
    global _mistral_last_request_time
    with _mistral_rate_lock:
        current_time = time.time()
        time_since_last = current_time - _mistral_last_request_time
        if time_since_last < 1.0:
            wait_time = 1.0 - time_since_last
            time.sleep(wait_time)
        _mistral_last_request_time = time.time()
```

---

## Database Schemas

### Neon PostgreSQL: scraped_posts (임시 저장)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| username | VARCHAR | Instagram 계정명 |
| shortcode | VARCHAR | 포스트 고유 ID |
| caption | TEXT | 캡션 원문 |
| image_url | VARCHAR | 로컬 이미지 경로 |
| post_date | TIMESTAMP | 포스트 게시일 |
| event_name | VARCHAR | 추출된 이벤트명 |
| venue | VARCHAR | 추출된 장소명 |
| artists | JSONB | 아티스트 배열 |
| event_date | DATE | 추출된 이벤트 날짜 |
| created_at | TIMESTAMP | 수집 시간 |

### MusicFeedPlatform PostgreSQL: posts (최종 저장) - **snake_case 스키마**

**중요**: MusicFeedPlatform DB는 snake_case 컬럼명을 사용합니다.

| 컬럼명 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| user_id | VARCHAR | 'pomfs_ai' (고정) |
| category | VARCHAR | 'pomfs_ai' (고정) |
| genre | VARCHAR | 'pomfs_ai' (고정) |
| post_kind | VARCHAR | 'event' (고정) |
| event_name | VARCHAR | 이벤트 제목 |
| event_venue | VARCHAR | 장소명 |
| event_date | TIMESTAMP | 이벤트 일시 |
| event_location | VARCHAR | 상세 주소 |
| content | TEXT | Instagram 캡션만 저장 (OCR 텍스트는 분석용으로만 사용) |
| image_url | VARCHAR | GCS 이미지 URL |
| performing_artists | TEXT[] | 아티스트 배열 |
| instagram_link | VARCHAR | 원본 Instagram URL |
| is_draft | BOOLEAN | False (자동 게시) |
| ticket_options | JSONB | 티켓 옵션 (빈 객체 {}) |
| created_at | TIMESTAMP | 생성 시간 |
| updated_at | TIMESTAMP | 수정 시간 |

### MusicFeedPlatform PostgreSQL: users - **snake_case 스키마**

| 컬럼명 | 타입 | 설명 |
|------|------|------|
| id | VARCHAR | Primary Key (Instagram username) |
| nickname | VARCHAR | 닉네임 |
| user_rank | VARCHAR | 'user' (기본값) |
| artist_profile_completed | BOOLEAN | False (기본값) |
| instagram_handle | VARCHAR | Instagram 계정명 |

### 로컬 SQLite: posts, venues (레거시)
- 로컬 테스트용으로 남아있음
- 실제 운영에는 MusicFeedPlatform DB 사용

### 🚀 새 DB 스키마 (v2.4.0 예정)

> **변경 예정**: 기존 `posts` 테이블이 용도별로 분리됩니다.

| 테이블 | 용도 | 주요 필드 | P.O.MFS 관련 |
|--------|------|----------|-------------|
| `feed_user` | 사용자 피드 글 | content, imageUrl, links, category | ❌ |
| `feed_ai` | Bot 피드 글 | botId, content, imageUrl, links | ❌ |
| `event_user` | 유저 공연정보 | eventName, venue, dates, location, tickets | ❌ |
| `event_ai` | AI/Staff 공연정보 | botId, eventName, venue, dates | ✅ **저장 대상** |
| `event_venue` | 공연장 공연정보 | venueId, eventName, dates, tickets | 🔶 연관 |

**마이그레이션 계획**:
- 기존 `posts` 데이터 → `event_ai` 테이블로 이전
- `userId` → `botId='pomfs-bot'` 변환
- 회원 가입 문제 해결 (AI 수집 데이터 명확히 구분)

---

## Image Storage (Google Cloud Storage)

### 업로드 경로
```
gs://communitystorage2/ai-post-img/{user_id}/{timestamp}-{unique_id}-{filename}
```

### 버킷 설정 - **Uniform Bucket-Level Access**

**중요**: `communitystorage2` 버킷은 Uniform Bucket-Level Access가 활성화되어 있습니다.
- 개별 객체 ACL(`blob.make_public()`)은 사용 불가
- 버킷 IAM에서 `allUsers`에 `Storage Object Viewer` 역할 부여 필요
- 업로드된 모든 객체는 자동으로 공개 접근 가능

### 구현 상세
```python
# gcs_uploader.py - upload_image_to_gcs()
def upload_image_to_gcs(local_file_path, user_id="pomfs_ai", folder="ai-post-img"):
    bucket_name = os.environ.get("GOOGLE_CLOUD_BUCKET_NAME", "communitystorage2")
    
    # 파일명 생성: {timestamp}-{uuid}-{sanitized_name}
    timestamp = int(time.time() * 1000)
    unique_id = str(uuid.uuid4())[:8]
    blob_name = f"{folder}/{user_id}/{timestamp}-{unique_id}-{sanitized_name}"
    
    blob.upload_from_filename(local_file_path, content_type=content_type)
    # blob.make_public() 제거됨 - Uniform Bucket-Level Access 사용
    
    # 공개 URL 직접 생성
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
```

### GCS 권한 설정 방법
```bash
# GCS 버킷에 공개 읽기 권한 추가 (Google Cloud Console 또는 gcloud CLI)
gcloud storage buckets add-iam-policy-binding gs://communitystorage2 \
    --member="allUsers" \
    --role="roles/storage.objectViewer"
```

---

## API Endpoints

### 페이지 라우트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 메인 페이지 (대시보드) |
| GET | `/events` | 전체 이벤트 목록 |
| GET | `/scrape` | 단일 계정 수집 페이지 (다크 테마, 실시간 로그) |
| GET | `/batch` | 배치 수집 페이지 (엑셀 업로드, 자동 수집) |
| GET | `/review` | 수집 데이터 검토 페이지 (Neon DB) |
| GET | `/registered` | 등록된 공연 정보 목록 (MusicFeedPlatform Dev DB) |
| GET | `/upload` | 파일 업로드 페이지 (엑셀/이미지) |
| GET | `/discovery` | 장소 Instagram ID 검색 페이지 |
| GET | `/marketing` | 마케팅 이미지/캡션 생성 페이지 |
| GET | `/migration` | 데이터 마이그레이션 페이지 (SQLite→PostgreSQL) |
| GET | `/health` | 헬스 체크 |
| POST | `/admin/reset_db` | 테스트 DB 리셋 (TEST 모드 전용) |

### API 라우트 - 스크래핑

| Method | Path | 설명 |
|--------|------|------|
| GET | `/scrape_stream` | SSE 스트림 - 단일 계정 수집 (실시간 로그 + 결과 데이터) |
| POST | `/api/scrape` | Instagram 스크래핑 시작 (단일 계정, 레거시) |
| POST | `/api/scrape_background` | 백그라운드 스크래핑 시작 |
| POST | `/api/auto_process_async` | 비동기 자동 수집 (배치) |
| GET | `/api/task_status/<task_id>` | 작업 상태 조회 |
| GET | `/api/batch_accounts` | 페이지네이션된 계정 목록 조회 |
| GET | `/api/posts` | Neon DB에서 스크랩 포스트 조회 |

### API 라우트 - 리뷰/등록

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/review/delete-all-scraped` | 수집된 모든 포스트 삭제 |
| POST | `/api/review/upload-to-dev-db` | 선택한 포스트를 MusicFeedPlatform DB로 업로드 |
| POST | `/api/registered/publish` | 임시저장 이벤트 게시 (is_draft=False) |
| POST | `/api/registered/delete` | 이벤트 삭제 |
| POST | `/api/save_event_manual` | 수동 이벤트 저장 |

### API 라우트 - 장소 검색 (Venue Discovery)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/search_venue` | Naver 검색으로 장소 Instagram ID 검색 |
| GET | `/api/search_venue_google` | Google 심층 검색 (Selenium 사용) |
| POST | `/api/save_manual_id` | 수동으로 장소 Instagram ID 저장 |
| POST | `/api/add_manual_venue` | 새 장소 수동 추가 |
| POST | `/api/reset_discovery` | Discovery JSON 맵 리셋 |
| POST | `/api/reset_excel` | 업로드된 장소 엑셀 삭제 |

### API 라우트 - 마케팅

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/marketing/generate` | 마케팅 이미지 + 캡션 생성 |

### API 라우트 - 마이그레이션

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/run_migration_stream` | SSE 스트림 - SQLite→PostgreSQL 마이그레이션 진행 |

### SSE 스트림 데이터 형식 (`/api/scrape_stream`)

```javascript
// 로그 메시지
data: {"type": "log", "message": "[Apify] 스크래핑 시작..."}

// 진행 상황
data: {"type": "progress", "current": 3, "total": 10}

// 개별 결과
data: {"type": "item_result", "status": "saved", "event_name": "공연명", "venue": "장소명"}
data: {"type": "item_result", "status": "skipped", "reason": "Not Event"}

// 최종 결과
data: {"type": "result", "saved_count": 5, "skip_count": 3, "total_collected": 8, "details": [...]}

// 완료
data: {"type": "done"}
```

---

## 수집 워크플로우

### 단일 계정 수집 (Scrape 페이지)

**URL**: `/scrape`

**UI 특징**:
- 다크 테마 디자인
- 터미널 스타일 실시간 로그 콘솔
- 결과 리포트 카드 (저장/skip/총 수집 통계)
- 개별 항목 상세 상태 표시

**사용자 플로우**:
1. Instagram 계정명 입력
2. 수집할 포스트 수 설정 (1-10개)
3. "수집 시작" 클릭
4. 실시간 로그로 진행 상황 확인
5. 완료 시 결과 리포트 카드 표시

### 배치 수집 (Batch Collection 페이지)

**URL**: `/batch`

**사용자 플로우**:
1. **엑셀 업로드**: 계정 목록 (username 컬럼 필수)
2. **슬라이더 설정**:
   - 계정당 포스트 수 (1-10개)
   - 동시 작업 수 (1-6개, 권장 5)
   - 자동 수집 계정 수 (전체 계정 중)
3. **자동 수집 시작**: 50개씩 배치 처리
4. **AI 자동 필터링**: 공연 포스터가 아닌 이미지는 자동 skip
5. **자동 저장**: 공연 포스터 -> MusicFeedPlatform DB (is_draft=False)
6. **결과 표시**: "저장 N개 / skip N개"

### 내부 처리 순서
```
1. Excel 파싱 -> 계정 목록 추출
2. 50개씩 배치 분할
3. 각 배치에 대해:
   a. Apify 스크래핑 (동시 5-6개)
   b. 이미지 다운로드 -> scraped_data/ 저장
   c. Neon DB에 raw 데이터 저장
   d. Mistral OCR -> 텍스트 추출
   e. Mistral LLM -> 구조화 분석
   f. is_event_poster 판별
   g. True -> GCS 업로드 -> MusicFeedPlatform 저장
   h. False -> "Skipped (Not Event)"
4. 결과 집계 및 반환
```

---

## Error Handling

### Apify 에러

| 에러 | 원인 | 처리 |
|------|------|------|
| Memory Exceeded | RAM 부족 | 동시 작업 수 감소 (5-6개 권장) |
| Rate Limited | API 호출 과다 | 자동 재시도 (exponential backoff) |
| Account Private | 비공개 계정 | Skip 후 다음 계정 진행 |

### Mistral API 에러

| 에러 | 원인 | 처리 |
|------|------|------|
| Rate Limit | 1 req/sec 초과 | `_wait_for_rate_limit()` 적용 |
| JSON Parse Error | LLM 응답 형식 오류 | `parse_date_info()` fallback |
| OCR Failure | 이미지 인식 실패 | 빈 텍스트로 처리, 캡션만 분석 |

### GCS 에러

| 에러 | 원인 | 처리 |
|------|------|------|
| Upload Failed | 네트워크/권한 문제 | 로컬 저장 fallback |
| Credentials Invalid | 환경변수 누락 | 에러 로그 후 진행 |

---

## Venue Discovery (장소 Instagram ID 검색)

### 기능 개요
공연장/클럽의 Instagram 계정 ID를 자동으로 검색하는 기능입니다. 배치 수집 전 대상 계정 목록을 확보할 때 사용합니다.

### 검색 방식

#### 1단계: Naver 검색 (기본)
```python
# venue_discovery.py - search_instagram_id()
def search_instagram_id(venue_name):
    """
    Naver 검색으로 장소의 Instagram ID를 찾습니다.
    DuckDuckGo는 403 차단되어 Naver 사용.
    """
    queries = [
        f"{venue_name} instagram",
        f"{venue_name} official instagram"
    ]
    
    # Naver 검색 결과에서 instagram.com 링크 추출
    # 패턴: instagram.com/username
    match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', href)
```

#### 2단계: Google 심층 검색 (Selenium)
```python
# selenium_search.py - search_venue_google()
# Naver에서 못 찾으면 Google 검색 (Selenium WebDriver 사용)
# 더 정확하지만 느림 (브라우저 자동화)
```

### 워크플로우
```
1. 장소 엑셀 업로드 (venue_list.xlsx)
2. /discovery 페이지에서 검색 시작
3. Naver 검색 → 결과 없으면 → Google 검색
4. 발견된 ID를 JSON 맵에 저장 (discovery_map.json)
5. 수동 입력 옵션: 자동 검색 실패 시 직접 입력
6. 최종 결과를 batch_targets.xlsx로 내보내기
```

### 데이터 저장
- `DB/discovery_map.json`: 장소명 → Instagram ID 매핑
- `DB/venue_list.xlsx`: 장소 목록 원본
- `DB/batch_targets.xlsx`: 배치 수집용 최종 계정 목록

---

## Marketing Generator (마케팅 이미지/캡션 생성)

### 기능 개요
수집된 이벤트 데이터를 기반으로 Instagram 홍보용 이미지와 캡션을 자동 생성합니다.

### 이미지 생성
```python
# marketing_generator.py - MarketingGenerator.generate_image()
def generate_image(self, events, output_path="static/marketing_output.jpg"):
    """
    최대 4개 이벤트를 2x2 그리드 이미지로 생성 (1080x1080)
    
    레이아웃:
    +----------+----------+
    | Event 1  | Event 2  |
    +----------+----------+
    | Event 3  | Event 4  |
    +----------+----------+
    
    각 셀: 540x540 픽셀
    - 포스터 이미지 (Center Crop)
    - 하단 오버레이 (제목, 장소, 날짜)
    """
```

### 캡션 생성 (AI)
```python
# marketing_generator.py - MarketingGenerator.generate_caption()
def generate_caption(self, events):
    """
    Mistral API로 Instagram 캡션 생성
    
    프롬프트 특성:
    - 톤: 힙한 인디 음악 매거진 스타일
    - 언어: 한국어 (키워드는 영어)
    - 구조: 훅 → 하이라이트 → CTA → 해시태그 10개
    """
```

### 사용 예시
```python
events = [
    {'eventName': '공연명', 'venueName': '장소', 'date': '2026-01-20', 
     'performers': '아티스트', 'image_path': '/path/to/poster.jpg'},
    # ... 최대 4개
]

generator = MarketingGenerator(api_key=MISTRAL_API_KEY)
image_path = generator.generate_image(events)
caption = generator.generate_caption(events)
```

---

## Migration Tool (데이터 마이그레이션)

### 기능 개요
로컬 SQLite 테스트 데이터베이스에서 Neon PostgreSQL로 데이터를 마이그레이션합니다.

### 마이그레이션 대상
1. **venues 테이블**: 공연장 정보
2. **posts 테이블**: 이벤트 포스트 정보

### 마이그레이션 로직
```python
# migrate_to_neon.py
def migrate_venues(local_conn, pg_conn):
    """
    1. 로컬 SQLite venues 조회
    2. PostgreSQL에 존재 여부 확인 (venueName 기준)
    3. 없으면 INSERT, 있으면 Skip
    4. venue_map 반환 (local_id → remote_id 매핑)
    """

def migrate_posts(local_conn, pg_conn, venue_map):
    """
    1. 로컬 SQLite posts 조회
    2. venue_map으로 venueId 변환
    3. 중복 체크 (venueId + eventName)
    4. 없으면 INSERT
    """
```

### 실행 방법
```bash
# CLI 직접 실행
python migrate_to_neon.py

# 웹 UI (/migration 페이지)
# SSE 스트림으로 실시간 진행 상황 표시
```

### 환경 변수
- `LOCAL_DB_PATH`: SQLite 파일 경로 (기본: `test_pomfs.db`)
- `NEON_DB_URL` 또는 `DATABASE_URL`: PostgreSQL 연결 URL

---

## Technical Decisions

### 왜 Apify를 선택했나?
- **신뢰성**: Instagram API 변경에 빠른 대응
- **확장성**: 32GB RAM으로 대규모 수집 가능
- **편의성**: 프록시/세션 관리 자동화

### 왜 Mistral API를 선택했나?
- **OCR 품질**: 한글/일본어 인식률 우수
- **LLM 통합**: OCR + 분석을 한 서비스에서
- **비용 효율**: GPT-4 대비 저렴

### 왜 is_draft=False (자동 게시)?
- AI 필터링 신뢰도가 충분히 높음
- 수동 검토 단계 제거로 워크플로우 단순화
- 잘못된 게시물은 나중에 삭제 가능

### 왜 순차 처리 (No Parallel)?
- Mistral API가 1 req/sec 제한
- 병렬 처리 시 429 에러 빈발
- 순차 처리 + 1초 딜레이로 안정성 확보

### 왜 Gemini API를 사용하지 않나?
- Mistral OCR + LLM 조합만으로 충분한 정확도 달성
- 추가 API 비용 절감
- 단일 API 의존으로 유지보수 단순화
- 한글/일본어 OCR 품질이 Mistral에서 우수

---

## 캐러셀 표시 조건 (MusicFeedPlatform)

### 필수 조건
1. **category = 'pomfs_ai'** - AI 수집 이벤트 카테고리
2. **"isDraft" = False** - 게시 상태 (자동 게시)
3. **"postKind" = 'event'** - 이벤트 타입

### 캐러셀 카드 표시 필드
| 필드 | 용도 | 필수 여부 |
|------|------|----------|
| "eventName" | 이벤트 제목 | 필수 |
| "eventVenue" | 장소명 | 필수 |
| "eventDate" | 이벤트 일시 | 필수 |
| "imageUrl" | GCS 이미지 URL | 필수 |
| "performingArtists" | 출연 아티스트 | 선택 |
| "instagramLink" | 원본 포스트 링크 | 선택 |

### 좌표 (coordinates) 참고
- **맵 마커 표시에만 필요**
- **캐러셀 카드에는 불필요**
- 현재 AI 수집은 좌표 없이 저장

### "전체" 필터에 표시되는 조건
- `category IN ('pomfs_ai', 'perform', ...)`
- 새 카테고리 추가 시 프론트엔드 필터 쿼리 확인 필요

---

## Troubleshooting Guide

### 문제: 스크래핑이 멈춤
**원인**: Apify 메모리 부족 또는 Instagram 차단
**해결**:
1. 동시 작업 수를 5개로 줄임
2. Apify 대시보드에서 Actor 상태 확인
3. 다른 계정으로 테스트

### 문제: OCR 결과가 빈 문자열
**원인**: 이미지 형식 문제 또는 API 에러
**해결**:
1. 이미지 파일이 정상인지 확인 (scraped_data/ 폴더)
2. Mistral API 키 유효성 확인
3. `_ocr.txt` 파일 확인

### 문제: 공연 포스터인데 skip됨
**원인**: AI가 이벤트 포스터로 인식 못함
**해결**:
1. OCR 텍스트 확인 (`_ocr.txt`)
2. 날짜/장소 정보가 추출되었는지 확인
3. fallback 휴리스틱 조건 검토 (dates AND venue)

### 문제: GCS 업로드 실패
**원인**: 환경변수 누락 또는 권한 문제
**해결**:
1. `GOOGLE_CLOUD_CREDENTIALS` 확인
2. 서비스 계정에 Storage Object Creator 권한 확인
3. 버킷 이름 확인 (`communitystorage2`)

### 문제: MusicFeedPlatform DB 저장 실패
**원인**: Foreign key 제약 또는 중복
**해결**:
1. `users` 테이블에 'pomfs_ai' 사용자 존재 확인
2. 중복 이벤트 체크 (venue + name + date)
3. DB 연결 상태 확인

---

## Running the Server
서버는 포트 5000에서 실행됩니다.

```bash
python app.py
```

---

## 구현 완료 기능
- [x] AI 자동 필터링: is_event_poster 필드로 공연 포스터 자동 판별
- [x] 자동 게시: 검토 없이 바로 MusicFeedPlatform에 게시 (isDraft=False)
- [x] GCS 이미지 업로드: ai-post-img 폴더에 자동 업로드
- [x] Uniform Bucket-Level Access 지원: blob.make_public() 제거
- [x] snake_case DB 스키마 지원: MusicFeedPlatform DB 컬럼명 매칭
- [x] 단일 계정 수집 UI: 다크 테마, 터미널 로그, 결과 리포트 카드
- [x] 배치 수집 UI: 엑셀 업로드, 동시 작업 수 조절, 진행률 표시
- [x] Mistral API 순차 처리: 1 req/sec 제한 준수
- [x] content 필드 개선: OCR 텍스트 제거, Instagram 캡션만 저장
- [x] SSE 오류 핸들링 개선: 완료 플래그로 정상 종료 시 경고 방지
- [x] 날짜 연도 스마트 추론: 연초/연말 경계 특별 처리 (infer_year_for_month)
- [x] **Geocoding 자동화**: 장소명/주소 → 좌표 변환하여 지도 마커 표시
- [x] **중복 저장 방지**: shortcode/instagram_link 기준 중복 체크로 같은 게시물 재저장 방지

## 예정 기능
- [ ] 유사 이미지 해시 비교 (동일 이미지 다른 게시물 감지)
- [ ] 스케줄러: 매일 자동 수집 (cron)
- [ ] 알림 기능: 수집 완료 시 Slack/Discord 알림
- [ ] 통계 대시보드: 일별/주별 수집 현황 차트

---

## Recent Changes

### 2026-01-19 (최신)
- **Geocoding 자동화 기능 추가**: 이벤트 저장 시 장소명/주소를 좌표로 변환하여 지도에 마커 표시
  - 새 파일: `geocoder.py` - Google Geocoding API 호출 모듈
  - 수정: `db_helpers.py` - `save_single_event()`에서 geocoder 호출 후 좌표 저장
  - 환경변수: `GOOGLE_PLACES_API_KEY` 사용
  
- **3단계 검색 전략 구현**:
  ```
  1단계: event_location (상세 주소) → 성공률 95%+
  2단계: event_venue + ", Seoul, South Korea" → 성공률 70-80%
  3단계: 실패 시 NULL → 캐러셀만 표시, 지도 마커 없음
  ```

- **API 호출 최적화**: 
  - `region=KR`, `language=ko`, `components=country:KR` 파라미터 적용
  - 한국 주소/장소명에 최적화된 검색 결과 반환

- **DB 스키마 연동**: MusicFeedPlatform posts 테이블의 `latitude`, `longitude`, `formatted_address`, `place_id` 컬럼에 저장

- **문서화**: `docs/GEOCODING_STRATEGY.md` 전략 기획안 저장

- **중복 저장 방지 기능 추가**: 같은 Instagram 게시물이 여러 번 저장되는 것 방지
  - `db_utils.py`: Neon DB 저장 전 shortcode 중복 체크 추가
  - `db_helpers.py`: MusicFeedPlatform DB 저장 전 instagram_link 중복 체크 추가
  - 중복 발견 시 INSERT 스킵하고 로그 출력

### 2026-01-18
- **content 필드 변경**: `automation.py`에서 content 필드에 OCR 텍스트 제거, **Instagram 캡션만** 저장하도록 수정
  - 변경 전: `content = caption + "\n[OCR]\n" + ocr_text`
  - 변경 후: `content = caption_text[:3000] if caption_text else ""`
  - OCR 텍스트는 AI 분석용으로만 사용, DB에는 저장하지 않음
  
- **SSE 오류 핸들링 개선**: `scrape.html`에서 완료 플래그 추가
  - 문제: 수집 완료 후 서버가 SSE 연결을 닫으면 브라우저에서 "서버 연결 오류" 경고 발생
  - 해결: `isCompleted` 플래그로 정상 완료와 실제 오류 구분
  ```javascript
  let isCompleted = false;
  
  source.onmessage = function(event) {
      if (data.complete) {
          isCompleted = true;
          source.close();
          // ...
      }
  };
  
  source.onerror = function(err) {
      source.close();
      if (!isCompleted) {  // 정상 완료가 아닐 때만 경고 표시
          alert('서버 연결 오류');
      }
  };
  ```

- **날짜 연도 추론 로직 추가**: `analyzer.py`에 `infer_year_for_month()` 함수 추가
  - 문제: 1월에 12월 이벤트 수집 시 2026-12-04로 저장 (11개월 후 미래)
  - 실제: 2025-12-04 (1개월 전 과거)가 맞음
  - 해결: 연초/연말 경계 특별 처리
    - 연초(1-3월)에 10-12월 이벤트 → 지난해
    - 연말(10-12월)에 1-3월 이벤트 → 내년
    - 그 외 → 올해
  - LLM 프롬프트도 동일 규칙으로 업데이트

### 2026-01-22 (v2.3.1) - Server Restart Recovery
- **404 에러 자동 처리** - 3회 연속 404 응답 시 다음 작업으로 자동 진행
- **서버 재시작 감지** - `checkServerRestartAndCleanup()` 함수로 stale task 자동 정리
- **중지 버튼 개선** - `isProcessing` 상태와 무관하게 강제 중지 가능
- **UI 복구 함수** - `resetBatchUI()` 헬퍼로 일관된 UI 상태 복구

### 2026-01-22 (v2.3.0) - Batch Report Fix
- **배치 리포트 수정** - 성공/저장 건수가 0으로 표시되는 버그 수정
- **status 정규화** - 백엔드 'completed' → 프론트엔드 'success' 매핑
- **페이지별 수집 통계** - page 파라미터 지원 API 추가

### 2026-01-22 (v2.2.0) - Smart Skip Logic
- **스마트 스킵 로직** - 이미 수집된 계정 자동 감지 및 스킵
- **페이지별 스킵 적용** - 현재 페이지 기준 스킵 통계
- **배치 세션 관리** - 서버 측 세션 ID 발급 및 추적

### 2026-01-22 (v2.1.0) - Video Caption Support
- **비디오 캡션 분석** - 비디오 게시물 캡션 수집 및 LLM 분석
- **is_video 플래그** - 비디오/이미지 콘텐츠 타입 구분
- **OCR 스킵** - 비디오는 캡션 텍스트로 직접 분석

### 2026-01-22 (v2.0.0) - Full Pipeline
- **전체 파이프라인 통합** - Batch/Scrape/Discovery 모든 경로 완전 자동화
- **OR 이벤트 판정** - 공연명만 OR 공연명+날짜 OR 장소+날짜
- **Discovery API** - 베뉴 Instagram ID 수집

### 2026-01-17~18 (이전)
- **DB 스키마 확정** - MusicFeedPlatform DB는 snake_case 사용 확인, `db_helpers.py` snake_case로 복구
- **GCS 업로드 버그 수정** - `blob.make_public()` 제거 (Uniform Bucket-Level Access 호환). 버킷 IAM에서 allUsers 읽기 권한 설정 필요
- **scrape 페이지 UI 전면 개선** - 다크 테마 적용, 결과 리포트 카드 추가 (저장/skip/총 수집 통계), 상세 내역 목록, 터미널 스타일 로그 콘솔
- **scrape 페이지 자동화 로직 통합** - scrape_stream에서 결과 데이터(saved_count, skip_count, details) 클라이언트 전달 추가
- AI 자동 필터링 완성 - parse_date_info fallback에도 is_event_poster 휴리스틱 추가
- skip_count 정확도 개선 - "Skipped (Not Event)"만 카운트
- 자동 게시 기능 완성 - is_draft=False 기본값
- 프론트엔드 타임아웃 버그 수정
- Apify Starter 플랜 구독 시작 ($39/월)
- Mistral API 순차 처리 + 1초 딜레이 적용
- GCS 이미지 업로드 기능 추가
- MusicFeedPlatform DB 연동
- 초기 Flask 백엔드 설정 완료

---

## Known Issues & Technical Debt

### Critical Priority
| 이슈 | 영향 | 해결 방안 |
|------|------|----------|
| `find_local_image()` 성능 | 리뷰 페이지 5초+ 로딩 | 이미지 경로 캐시 구현 |
| `app.py` 비대화 (2,484줄) | 유지보수 어려움 | Flask Blueprint 분리 |

### High Priority
| 이슈 | 영향 | 해결 방안 |
|------|------|----------|
| `batch_collection.html` (2,506줄) | 인라인 JS 테스트 불가 | static/js/ 파일 분리 |
| 동기 I/O 블로킹 | Mistral/GCS/Geocoding 호출 지연 | 비동기 처리 |
| 메모리 기반 task_store | 서버 재시작 시 유실 | Redis 또는 DB 저장 |

### Medium Priority
| 이슈 | 영향 | 해결 방안 |
|------|------|----------|
| N+1 쿼리 패턴 | 리뷰/등록 페이지 느림 | JOIN 쿼리 최적화 |
| scraped_data 무한 증가 | 디스크 공간 부족 | 정리 스케줄러 |
| localStorage 의존 | 브라우저 간 동기화 안됨 | 서버 세션 저장 |

---

## Improvement Roadmap

### Phase 1 (1주)
- [ ] `find_local_image()` 캐시 구현 → 90% 성능 개선
- [ ] 하드코딩된 시크릿 제거

### Phase 2 (1개월)
- [ ] `app.py` Blueprint 분리 (routes/, services/, utils/)
- [ ] JavaScript 파일 분리 (static/js/batch.js 등)
- [ ] `event_ai` 테이블 마이그레이션

### Phase 3 (3개월)
- [ ] Type hints 추가 (mypy 호환)
- [ ] 테스트 코드 작성 (pytest)
- [ ] 비동기 처리 도입 (asyncio/Celery)
