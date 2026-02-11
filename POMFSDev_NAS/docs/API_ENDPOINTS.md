# API 엔드포인트 문서

> 작성일: 2026-01-19  
> 버전: 1.0  
> 목적: MusicFeedPlatform 이벤트 자동화 시스템의 모든 API 엔드포인트 정리

---

## 1. 페이지 라우트 (HTML 페이지)

| 경로 | 메서드 | 설명 | 템플릿 |
|------|--------|------|--------|
| `/` | GET | 메인 대시보드 | `dashboard.html` |
| `/events` | GET | 이벤트 관리 페이지 | `events.html` |
| `/registered` | GET | 등록된 이벤트 목록 | `registered.html` |
| `/review` | GET | 스크랩된 게시물 검토 페이지 | `review.html` |
| `/upload` | GET, POST | 수동 이벤트 업로드 | `upload.html` |
| `/batch_collection` | GET, POST | 배치 수집 페이지 | `batch_collection.html` |
| `/scrape` | GET, POST | 스크래핑 설정 페이지 | `scrape.html` |
| `/discovery` | GET, POST | 베뉴 디스커버리 | `discovery.html` |
| `/migration` | GET | 마이그레이션 페이지 | `migration.html` |
| `/marketing` | GET | 마케팅 생성 페이지 | `marketing.html` |
| `/load_result` | GET | 결과 로드 페이지 | `result.html` |
| `/load_image` | GET | 이미지 프록시 | - |

---

## 2. 배치 수집 API

### POST `/api/batch_session`
배치 세션 시작/업데이트/완료

**Request Body:**
```json
{
    "action": "start|update|stop|complete",
    "page": 2,                    // (start 시) 시작 페이지
    "total_accounts": 50,         // (start 시) 총 계정 수
    "task_id": "uuid",            // (update 시) 작업 ID
    "completed_count": 10         // (update 시) 완료된 작업 수
}
```

**Response:**
```json
{
    "success": true,
    "session_id": "uuid"
}
```

### GET `/api/batch_session/active`
진행 중인 배치 세션 조회

**Response (진행 중):**
```json
{
    "active": true,
    "session_id": "uuid",
    "status": "running",
    "page": 2,
    "total_accounts": 50,
    "completed_count": 15,
    "task_ids": ["task-1", "task-2"],
    "running_tasks": [
        {"task_id": "task-1", "status": "running", "progress": 50}
    ]
}
```

### GET `/api/batch_accounts`
배치 계정 목록 조회 (페이지네이션)

**Query Parameters:**
- `page`: 페이지 번호 (기본값: 1)
- `limit`: 페이지당 항목 수 (기본값: 50)

**Response:**
```json
[
    {"userName": "account1", "venueName": "Club A"},
    {"userName": "account2", "venueName": "Club B"}
]
```

---

## 3. 자동 처리 API

### POST `/api/auto_process_async`
비동기 자동 처리 시작 (Apify 스크래핑 + AI 분석 + DB 저장)

**Request Body:**
```json
{
    "venue_name": "Club Soap",      // 베뉴명 (선택)
    "instagram_id": "clubsoap",     // 인스타그램 ID
    "limit": 5                      // 스크래핑 게시물 수
}
```

**Response:**
```json
{
    "success": true,
    "task_id": "uuid"
}
```

### GET `/api/task_status/<task_id>`
작업 상태 조회

**Response:**
```json
{
    "status": "running|completed|error",
    "progress": 50,
    "logs": ["Step 1 완료", "Step 2 진행 중"],
    "result": {
        "scraped_count": 5,
        "saved_count": 3,
        "skip_count": 2,
        "details": [...]
    },
    "error": null
}
```

### POST `/api/auto_process_venue`
베뉴 기반 자동 처리

**Request Body:**
```json
{
    "venue_name": "Club Soap",
    "instagram_id": "clubsoap",
    "limit": 10
}
```

---

## 4. 등록 이벤트 관리 API

### POST `/api/registered/publish`
등록된 이벤트 발행 (is_draft → false)

**Request Body:**
```json
{
    "post_id": 123
}
```

### POST `/api/registered/delete`
등록된 이벤트 삭제

**Request Body:**
```json
{
    "post_id": 123
}
```

---

## 5. 리뷰 페이지 API

### POST `/api/review/delete-all-scraped`
모든 스크랩된 게시물 삭제

**Response:**
```json
{
    "success": true,
    "deleted_count": 50
}
```

### POST `/api/review/upload-to-dev-db`
스크랩된 게시물을 개발 DB로 업로드

**Request Body:**
```json
{
    "post_ids": [1, 2, 3]
}
```

---

## 6. 베뉴 디스커버리 API

### GET `/api/search_venue`
베뉴 검색 (Instagram)

**Query Parameters:**
- `q`: 검색 쿼리

### GET `/api/search_venue_google`
베뉴 검색 (Google Places)

**Query Parameters:**
- `q`: 검색 쿼리

### POST `/api/save_manual_id`
수동 Instagram ID 저장

**Request Body:**
```json
{
    "venue_name": "Club Soap",
    "instagram_id": "clubsoap"
}
```

### POST `/api/add_manual_venue`
수동 베뉴 추가

**Request Body:**
```json
{
    "venue_name": "New Club",
    "instagram_id": "newclub",
    "category": "club"
}
```

### POST `/api/reset_discovery`
디스커버리 데이터 초기화

### POST `/api/reset_excel`
엑셀 데이터 초기화

---

## 7. 마케팅 API

### POST `/api/marketing/generate`
마케팅 콘텐츠 생성

**Request Body:**
```json
{
    "event_id": 123,
    "type": "instagram|newsletter"
}
```

---

## 8. 기타 API

### GET `/api/posts`
게시물 목록 조회 (JSON)

### POST `/api/save_event_manual`
수동 이벤트 저장

### POST `/admin/reset_db`
데이터베이스 초기화 (관리자용)

### GET `/scrape_stream`
스크래핑 스트림 (Server-Sent Events)

### GET `/api/run_migration_stream`
마이그레이션 스트림 (Server-Sent Events)

---

## 9. 인증 및 보안

현재 시스템은 내부 사용 목적으로 별도 인증 없이 동작합니다.  
프로덕션 배포 시 인증 미들웨어 추가가 권장됩니다.

---

## 10. 에러 응답 형식

모든 API는 에러 발생 시 다음 형식으로 응답합니다:

```json
{
    "success": false,
    "error": "에러 메시지"
}
```

HTTP 상태 코드:
- `200`: 성공
- `400`: 잘못된 요청
- `404`: 리소스 없음
- `500`: 서버 오류

---

**저장 위치**: `docs/API_ENDPOINTS.md`
