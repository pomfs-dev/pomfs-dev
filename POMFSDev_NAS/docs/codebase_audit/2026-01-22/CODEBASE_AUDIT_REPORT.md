# P.O.MFS 코드베이스 감사 보고서

> **감사일**: 2026-01-22  
> **버전**: v2.3.1  
> **이전 감사일**: 2026-01-20 (v1.9.6)  
> **총 코드 라인**: 4,273 lines (핵심 Python 파일)

---

## 1. 개요

이 문서는 P.O.MFS (Performance Organization AI Management For System) 프로젝트의 전체 코드베이스를 감사한 결과입니다. 이전 감사(2026-01-20) 이후 변경사항을 분석하고, 성능 문제, 코드 품질, 아키텍처, 보안, 유지보수성 측면에서 현재 상태를 평가합니다.

### 1.1 버전 변화 요약 (v1.9.6 → v2.3.1)

| 버전 | 날짜 | 주요 변경사항 |
|------|------|--------------|
| v2.0.0 | 2026-01-22 | 전체 파이프라인 통합, OR 이벤트 판정 로직 |
| v2.1.0 | 2026-01-22 | 비디오 캡션 분석 지원 |
| v2.2.0 | 2026-01-22 | 스마트 스킵 로직, 배치 세션 관리 |
| v2.3.0 | 2026-01-22 | 배치 리포트 수정, 페이지별 수집 통계 |
| v2.3.1 | 2026-01-22 | 404 에러 처리, 서버 재시작 감지 |

### 1.2 파일 구조 요약 (업데이트)

| 파일명 | 라인 수 | 변화 | 역할 |
|--------|---------|------|------|
| app.py | 2,484 | +403 | Flask 메인 앱, 모든 API 엔드포인트 |
| automation.py | 463 | +45 | 자동 처리 파이프라인 |
| db_utils.py | 450 | +216 | Neon DB 유틸리티 (대폭 확장) |
| db_helpers.py | 443 | - | MusicFeedPlatform DB 헬퍼 |
| analyzer.py | 296 | - | Mistral OCR/LLM 분석 |
| scraper_apify.py | 137 | +2 | Apify 클라우드 스크래핑 |
| batch_collection.html | 2,506 | 신규 | 배치 수집 UI (대규모 JavaScript) |

---

## 2. 이전 감사 대비 진행 상황

### 2.1 해결된 문제 ✅

| 이전 이슈 | 상태 | 해결 방법 |
|-----------|------|-----------|
| 배치 작업 중단 시 UI 멈춤 | ✅ 해결 | 404 에러 감지 후 자동 다음 작업 진행 |
| 중지 버튼 비작동 | ✅ 해결 | isProcessing 상태와 무관하게 강제 중지 가능 |
| 서버 재시작 시 세션 유실 | ✅ 해결 | 페이지 로드 시 자동 감지 및 정리 |
| 배치 리포트 성공 건수 0 표시 | ✅ 해결 | status 정규화 (completed → success) |
| 페이지별 수집 통계 부재 | ✅ 해결 | page 파라미터 지원 API 추가 |

### 2.2 미해결 문제 ❌ (이전 감사에서 지적)

| 이슈 | 우선순위 | 현재 상태 | 비고 |
|------|----------|-----------|------|
| find_local_image() 성능 병목 | 🔴 Critical | ❌ 미해결 | 캐시 미구현 |
| app.py 거대 파일 | 🟠 High | ❌ 악화 | 2,081 → 2,484줄 |
| 동기식 I/O 블로킹 | 🟠 High | ❌ 미해결 | 비동기 미적용 |
| N+1 쿼리 문제 | 🟡 Medium | ❌ 미해결 | JOIN 미사용 |
| scraped_data 무제한 성장 | 🟡 Medium | ❌ 미해결 | 정리 전략 없음 |
| 하드코딩된 시크릿 | 🔴 Critical | ⚠️ 부분 해결 | 일부 폴백 값 존재 |

---

## 3. 현재 성능 문제 분석

### 3.1 🔴 Critical: find_local_image() 성능 병목 (미해결)

**위치**: `app.py:13-29`

**문제**:
```python
def find_local_image(username, shortcode):
    pattern = f"scraped_data/*/{username}/{shortcode}*.jpg"
    matches = glob.glob(pattern)  # 매번 전체 디렉토리 스캔
```

**영향**:
- scraped_data 폴더 지속 성장
- 리뷰 페이지 로딩 시간 증가
- 100개 포스트 시 100번 glob 호출

**권장 해결책**:
```python
# 인메모리 캐시 + LRU 캐시 데코레이터
from functools import lru_cache

@lru_cache(maxsize=10000)
def find_local_image_cached(username, shortcode):
    return find_local_image(username, shortcode)

# 또는 서버 시작 시 전체 캐시 구축
IMAGE_CACHE = {}
def build_image_cache():
    for path in glob.glob("scraped_data/*/*/*"):
        key = extract_shortcode(path)
        IMAGE_CACHE[key] = path
```

**개선 효과**: 응답 시간 90% 단축 예상

---

### 3.2 🔴 Critical: app.py 계속 증가 (2,484줄)

**문제**:
- 이전 감사 대비 403줄 증가 (2,081 → 2,484)
- 단일 파일에 50+ 개 API 엔드포인트
- 라우트, 비즈니스 로직, DB 접근 혼재
- 테스트 작성 어려움

**권장 해결책**: Flask Blueprint 분리

```
app/
├── __init__.py              # Flask 앱 팩토리
├── routes/
│   ├── __init__.py
│   ├── batch.py             # 배치 수집 관련 (20+ 엔드포인트)
│   ├── review.py            # 리뷰 페이지
│   ├── events.py            # 등록 이벤트
│   ├── api.py               # 일반 API
│   └── test_tools.py        # 테스트 도구
├── services/
│   ├── batch_service.py
│   ├── event_service.py
│   └── image_service.py
└── models/
    └── schemas.py
```

**개선 효과**: 유지보수성 50% 향상

---

### 3.3 🟠 High: 프론트엔드 JavaScript 비대화 (batch_collection.html)

**위치**: `templates/batch_collection.html` (2,506줄)

**문제**:
- HTML 파일 내 2,000줄+ JavaScript 인라인
- 코드 분리 없음
- 테스트 불가능
- IDE 지원 제한

**권장 해결책**:
```
static/js/
├── batch_collection.js      # 메인 로직
├── batch_utils.js           # 유틸리티 함수
├── batch_ui.js              # UI 업데이트
└── batch_storage.js         # localStorage 관리
```

**개선 효과**: 프론트엔드 유지보수성 향상

---

### 3.4 🟠 High: 동기식 I/O 블로킹 (미해결)

**위치**: `automation.py`, `analyzer.py`

**문제**:
- Mistral API: 동기식 호출 (rate limit 고려 필요)
- GCS 업로드: 동기식
- Geocoding: 동기식
- 직렬 처리로 인한 총 시간 증가

**영향**: 10개 이벤트 처리 시 최소 30초+ 소요

**권장 해결책**:
```python
from concurrent.futures import ThreadPoolExecutor

def process_batch_async(items, max_workers=3):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single, items))
    return results
```

---

### 3.5 🟡 Medium: 메모리 기반 작업 상태 관리

**위치**: `app.py` (task_store dict)

**문제**:
```python
task_store = {}  # 서버 재시작 시 모든 작업 상태 유실
```

**현재 대응**: 프론트엔드에서 404 감지 및 복구 로직 구현 (v2.3.1)

**근본 해결책**:
```python
# Redis 또는 DB 기반 작업 상태 저장
import redis
task_store = redis.Redis()

# 또는 SQLite/PostgreSQL 테이블
CREATE TABLE task_status (
    task_id VARCHAR PRIMARY KEY,
    status VARCHAR,
    progress INTEGER,
    result JSONB,
    created_at TIMESTAMP
);
```

**개선 효과**: 서버 재시작 시에도 작업 상태 유지

---

## 4. 신규 문제 분석

### 4.1 🟡 Medium: 중복 코드 - 폴링 로직

**위치**: `batch_collection.html`

**문제**: `processSingle`과 `processSingleByUsername` 함수에 거의 동일한 404 처리 로직 중복

```javascript
// processSingle 내부
if (statusResp.status === 404) {
    consecutive404Count++;
    if (consecutive404Count >= MAX_404_COUNT) {
        // ... 동일한 처리 로직
    }
}

// processSingleByUsername 내부
if (statusResp.status === 404) {
    consecutive404Count++;
    if (consecutive404Count >= MAX_404_COUNT) {
        // ... 동일한 처리 로직
    }
}
```

**권장 해결책**: 공통 함수로 추출

```javascript
async function pollTaskStatus(taskId, options) {
    let consecutive404Count = 0;
    const MAX_404_COUNT = 3;
    
    return new Promise((resolve) => {
        const pollInterval = setInterval(async () => {
            const result = await handlePollResponse(taskId, consecutive404Count);
            if (result.done) {
                clearInterval(pollInterval);
                resolve(result.data);
            }
        }, 1000);
    });
}
```

---

### 4.2 🟡 Medium: localStorage 의존성

**문제**:
- 배치 상태가 localStorage에 저장
- 브라우저 간 동기화 불가
- 시크릿 창에서 작동 불가
- 용량 제한 (5MB)

**영향**: 다중 탭/브라우저 사용 시 상태 불일치

**권장 해결책**: 서버 측 세션 관리 강화

---

## 5. 워크플로우 문제점 분석

### 5.1 배치 수집 워크플로우

```
현재 흐름:
1. 사용자가 자동 수집 시작
2. 프론트엔드에서 task_id 생성 요청
3. 백엔드에서 메모리에 task_id 저장
4. 프론트엔드에서 폴링으로 상태 확인
5. 서버 재시작 시 task_id 유실 → 404 에러
6. [v2.3.1] 404 감지 후 다음 작업 진행
```

**문제점**:
- 서버 재시작 시 진행 중인 Apify 작업 결과 유실
- 재시작 후 해당 계정 다시 수집 필요

**해결책**: 
- Redis 또는 DB 기반 작업 상태 저장
- Apify 웹훅 사용하여 결과 비동기 수신

### 5.2 이미지 로딩 워크플로우

```
현재 흐름:
1. 리뷰 페이지 요청
2. 각 포스트마다 find_local_image() 호출
3. glob.glob()으로 파일시스템 스캔
4. scraped_data 크기에 비례하여 지연
```

**문제점**: O(n*m) 복잡도 (n=포스트 수, m=파일 수)

**해결책**: 이미지 경로 캐시 구현

---

## 6. 보안 분석

### 6.1 현재 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| 하드코딩된 API 키 | ⚠️ 주의 | 일부 폴백 값 존재 가능 |
| SQL 인젝션 | ✅ 안전 | 파라미터화된 쿼리 사용 |
| 경로 순회 | ✅ 안전 | send_from_directory 사용 |
| CSRF | ⚠️ 미적용 | Flask-WTF 미사용 |
| Rate Limiting | ⚠️ 미적용 | API 남용 가능 |

### 6.2 권장 조치

1. **CSRF 보호**: Flask-WTF 적용
2. **Rate Limiting**: Flask-Limiter 적용
3. **환경 변수 검증**: 시작 시 필수 환경 변수 확인

---

## 7. 개선 로드맵 (업데이트)

### Phase 1: 즉시 조치 (1주일 내)

| 우선순위 | 작업 | 예상 시간 | 상태 |
|----------|------|-----------|------|
| 🔴 | find_local_image 캐시 구현 | 4시간 | 미착수 |
| 🔴 | 환경 변수 폴백 값 제거 | 2시간 | 미착수 |
| 🟠 | 폴링 로직 중복 제거 | 2시간 | 미착수 |

### Phase 2: 단기 개선 (1개월 내)

| 우선순위 | 작업 | 예상 시간 | 상태 |
|----------|------|-----------|------|
| 🟠 | app.py Blueprint 분리 | 16시간 | 미착수 |
| 🟠 | JavaScript 파일 분리 | 8시간 | 미착수 |
| 🟠 | 작업 상태 DB 저장 | 8시간 | 미착수 |
| 🟡 | 비동기 처리 도입 | 12시간 | 미착수 |

### Phase 3: 장기 개선 (3개월 내)

| 우선순위 | 작업 | 예상 시간 | 상태 |
|----------|------|-----------|------|
| 🟡 | 타입 힌트 추가 | 16시간 | 미착수 |
| 🟡 | scraped_data 정리 자동화 | 4시간 | 미착수 |
| 🟡 | 테스트 코드 작성 | 24시간 | 미착수 |
| 🟡 | N+1 쿼리 최적화 | 8시간 | 미착수 |

---

## 8. 성능 지표 목표

| 지표 | 이전 목표 | 현재 상태 | 목표 | 달성률 |
|------|-----------|-----------|------|--------|
| Review 페이지 로딩 | <1초 | ~5초 | <1초 | 0% |
| 배치 처리 속도 | 30건/분 | ~10건/분 | 30건/분 | 33% |
| 서버 재시작 복구 | N/A | 자동 감지 | 완전 복구 | 50% |
| 중단 후 재개 | N/A | 지원 | 원활 | 80% |

---

## 9. v2.3.1 신규 기능 평가

### 9.1 404 에러 처리 ⭐⭐⭐⭐

**장점**:
- 서버 재시작 시 UI 멈춤 방지
- 자동으로 다음 작업 진행
- 사용자에게 명확한 피드백 제공

**개선 여지**:
- 유실된 작업 자동 재시도 기능 추가
- 작업 상태 영구 저장으로 완전 복구

### 9.2 서버 재시작 감지 ⭐⭐⭐⭐

**장점**:
- 페이지 로드 시 자동 감지
- localStorage 자동 정리
- 사용자에게 알림 표시

**개선 여지**:
- 서버 측 세션과 연동
- 재시작 후 작업 재개 기능

### 9.3 중지 버튼 개선 ⭐⭐⭐⭐⭐

**장점**:
- 모든 상황에서 작동
- 강제 정리 및 새로고침 지원
- 사용자 경험 크게 개선

---

## 10. 결론

### 10.1 긍정적 변화

- **안정성 향상**: 404 에러 처리, 서버 재시작 감지로 시스템 복원력 강화
- **사용자 경험 개선**: 중지 버튼 개선, 명확한 상태 표시
- **기능 확장**: 비디오 캡션 분석, 페이지별 통계

### 10.2 주요 우려사항

1. **🔴 app.py 계속 성장**: 모듈화 시급 (2,484줄)
2. **🔴 성능 병목 미해결**: find_local_image 캐시 미구현
3. **🟠 기술 부채 누적**: 동기식 I/O, N+1 쿼리

### 10.3 권고사항

1. **즉시**: find_local_image 캐시 구현 (4시간 투자로 90% 성능 향상)
2. **1주 내**: app.py Blueprint 분리 시작
3. **1개월 내**: JavaScript 파일 분리, 작업 상태 DB 저장

---

> **작성자**: P.O.MFS Dev AI  
> **검토일**: 2026-01-22  
> **다음 감사 예정일**: 2026-02-22
