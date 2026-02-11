# Instagram 이벤트 Geocoding 전략 기획안 (최종)

> 작성일: 2026-01-19  
> 버전: 1.1 (사전 체크 완료)  
> 목적: Instagram에서 수집한 이벤트의 장소명/주소를 좌표로 변환하여 지도에 표시

---

## 1. 현재 시스템 분석

### 1.1 데이터 추출 현황 (analyzer.py)

현재 Mistral LLM이 OCR 텍스트에서 추출하는 장소 관련 필드:

| 필드 | 설명 | 예시 |
|------|------|------|
| `venue` | 장소명 (짧은 이름) | "Club Soap", "Rolling Hall", "Mudance" |
| `location` | 상세 주소 | "서울특별시 용산구 이태원로27가길 42 3층" |

### 1.2 데이터 품질 추정

| 상태 | 예상 비율 | Geocoding 가능성 |
|------|----------|-----------------|
| 상세 한국어 주소 있음 | ~60% | 높음 (95%+ 성공률) |
| 장소명만 있음 | ~30% | 중간 (국가/도시 추가 필요) |
| 주소 정보 없음 | ~10% | 불가 (캐러셀만 표시) |

### 1.3 핵심 문제점

**장소명만으로 검색 시 모호성 발생:**
```
❌ "Crocodile" → 결과 없음 또는 잘못된 결과
✅ "Crocodile, Seattle, USA" → 정확한 결과

❌ "Shape Seoul" → 불확실한 결과
✅ "Shape Seoul, Seoul, South Korea" → 정확한 결과
```

---

## 2. API 설정

### 2.1 환경변수

| 변수명 | 용도 | 상태 |
|--------|------|------|
| `GOOGLE_PLACES_API_KEY` | Geocoding API 인증 | ✅ 설정완료 |

### 2.2 Google Geocoding API 비용

| 항목 | 내용 |
|------|------|
| 무료 크레딧 | 월 $200 (약 40,000건) |
| 초과 시 | $5 / 1,000건 ($0.005/건) |
| 속도 제한 | 분당 3,000건 |

### 2.3 비용 예측

| 시나리오 | 월간 호출 수 | 예상 비용 |
|---------|-------------|----------|
| 소규모 (일 10건) | ~300건 | 무료 |
| 중규모 (일 100건) | ~3,000건 | 무료 |
| 대규모 (일 500건) | ~15,000건 | ~$25/월 |

---

## 3. Geocoding 전략

### 3.1 API 호출 베스트 프랙티스

Google 공식 문서 기반 권장 설정:

```python
params = {
    "address": "주소 또는 장소명",
    "region": "KR",           # 한국 결과 우선
    "language": "ko",         # 한국어 응답
    "components": "country:KR", # 한국 내 결과만
    "key": GOOGLE_PLACES_API_KEY
}
```

**주요 파라미터:**
- `region=KR`: 한국 지역 결과 우선 (바이어스)
- `language=ko`: 한국어 주소 반환
- `components=country:KR`: 검색 범위를 한국으로 제한

### 3.2 3단계 검색 전략

```
┌──────────────────────────────────────────────────────┐
│              1단계: 상세 주소 검색                    │
│  조건: event_location이 있는 경우                    │
│  검색어: event_location 그대로                       │
│  예시: "서울특별시 용산구 이태원로27가길 42"          │
│  성공률: 95%+                                        │
└────────────────────┬─────────────────────────────────┘
                     │ 실패 또는 location 없음
                     ▼
┌──────────────────────────────────────────────────────┐
│              2단계: 장소명 + 도시 검색                │
│  조건: event_venue가 있는 경우                       │
│  검색어: "{event_venue}, Seoul, South Korea"         │
│  예시: "Shape Seoul, Seoul, South Korea"             │
│  성공률: 70-80%                                      │
│  추가: components=country:KR로 한국 결과 제한        │
└────────────────────┬─────────────────────────────────┘
                     │ 실패
                     ▼
┌──────────────────────────────────────────────────────┐
│              3단계: 좌표 없이 저장                    │
│  latitude = NULL, longitude = NULL                   │
│  결과: 캐러셀에만 표시, 지도 마커 없음               │
└──────────────────────────────────────────────────────┘
```

### 3.3 국제 장소 처리 (향후 확장)

현재 시스템은 한국 이벤트 중심이지만, 해외 이벤트 처리 시:

```python
DEFAULT_CITIES = {
    "KR": "Seoul, South Korea",
    "JP": "Tokyo, Japan",
    "US": "New York, USA"
}
```

---

## 4. 구현 상세

### 4.1 새 파일: geocoder.py

```python
import os
import requests
from typing import Optional, Tuple

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY')
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def geocode_location(
    location: Optional[str] = None,
    venue: Optional[str] = None,
    default_city: str = "Seoul, South Korea"
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    장소 정보를 좌표로 변환.
    
    Returns:
        (latitude, longitude, formatted_address, place_id) 또는 모두 None
    """
    
    # 1단계: 상세 주소로 검색
    if location:
        result = _geocode_query(location)
        if result:
            return result
    
    # 2단계: 장소명 + 도시로 검색
    if venue:
        query = f"{venue}, {default_city}"
        result = _geocode_query(query)
        if result:
            return result
    
    # 3단계: 실패
    return (None, None, None, None)

def _geocode_query(query: str) -> Optional[Tuple]:
    """Google Geocoding API 호출."""
    try:
        params = {
            "address": query,
            "region": "KR",
            "language": "ko",
            "components": "country:KR",
            "key": GOOGLE_PLACES_API_KEY
        }
        
        response = requests.get(GEOCODING_URL, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            return (
                location["lat"],
                location["lng"],
                result.get("formatted_address"),
                result.get("place_id")
            )
        
        return None
        
    except Exception as e:
        print(f"[Geocoder] Error: {e}")
        return None
```

### 4.2 automation.py 연동

이벤트 저장 시 geocoder 호출:

```python
from geocoder import geocode_location

# 이벤트 분석 후
lat, lng, formatted_addr, place_id = geocode_location(
    location=event_info.get('location'),
    venue=event_info.get('venue')
)

# DB 저장 시 좌표 포함
save_to_musicfeed_db(
    event_name=event_info['title'],
    event_venue=event_info['venue'],
    event_location=event_info['location'],
    latitude=lat,
    longitude=lng,
    formatted_address=formatted_addr,
    place_id=place_id,
    # ... 기타 필드
)
```

### 4.3 DB 스키마 (posts 테이블)

| 컬럼명 | 타입 | 용도 |
|--------|------|------|
| `event_venue` | varchar | 장소명 (AI 추출) |
| `event_location` | varchar | 상세 주소 (AI 추출) |
| `latitude` | numeric | 위도 좌표 (Geocoding 결과) |
| `longitude` | numeric | 경도 좌표 (Geocoding 결과) |
| `formatted_address` | text | Google 표준화 주소 |
| `place_id` | varchar | Google Place ID |

---

## 5. 에러 처리

| 상황 | 처리 방법 |
|------|----------|
| API 호출 실패 (네트워크) | 로그 기록 후 NULL 저장 |
| 결과 없음 (ZERO_RESULTS) | 다음 단계 전략 시도 |
| 여러 결과 반환 | 첫 번째 결과 사용 (한국 우선) |
| API 할당량 초과 | 로그 기록 후 NULL 저장 |
| partial_match 응답 | 결과 사용 (정확도 낮을 수 있음 경고 로그) |

---

## 6. 예상 결과

### 6.1 최종 Geocoding 성공률

| 데이터 상태 | 예상 성공률 |
|------------|------------|
| 상세 한국어 주소 | 95%+ |
| 장소명 + 도시 조합 | 70-80% |
| 장소명만 | 50-60% |
| **전체 평균** | **75-85%** |

### 6.2 지도 표시 결과

```
전체 pomfs_ai 이벤트 100건 가정:
├── 좌표 있음 (지도 + 캐러셀): ~80건
└── 좌표 없음 (캐러셀만): ~20건
```

---

## 7. 사전 체크 완료 요약

### ✅ 1. 주소 추출 현황 (analyzer.py 분석)
- **venue**: 장소명 추출 (예: "Club Soap", "Shape Seoul")
- **location**: 상세 주소 추출 (예: "서울특별시 용산구 이태원로27가길 42")
- 추정 성공률: 상세 주소 ~60%, 장소명만 ~30%, 없음 ~10%

### ✅ 2. 핵심 문제점 & 해결책
**문제**: 장소명만으로 검색 시 모호성
```
❌ "Crocodile" → 잘못된 결과
✅ "Crocodile, Seattle, USA" → 정확한 결과
```

**해결**: 3단계 검색 전략 + 국가/도시 자동 추가
```
1단계: event_location (상세 주소) → 성공률 95%
2단계: event_venue + ", Seoul, South Korea" → 성공률 70-80%
3단계: 실패 시 좌표 없이 저장 (캐러셀만 표시)
```

### ✅ 3. API 설정 권장사항 (Google 공식 문서 기반)
- `region=KR`: 한국 결과 우선
- `language=ko`: 한국어 응답
- `components=country:KR`: 한국 내 결과 제한

### ✅ 4. 비용
- 월 $200 무료 크레딧 (약 40,000건)
- 일 100건 기준 충분히 무료 범위 내

---

## 8. 구현 순서 및 상태

1. ✅ API 키 설정 확인 (`GOOGLE_PLACES_API_KEY`)
2. ✅ `geocoder.py` 생성 (3단계 검색 전략 구현)
3. ✅ `automation.py` 연동 (이벤트 저장 시 자동 Geocoding)
4. ✅ `db_helpers.py` 수정 - lat/lng 저장 추가
5. ✅ 테스트 및 검증 완료

**구현 완료일: 2026-01-19**

---

## 9. 주의사항

1. **API 키 보안**: 서버 사이드에서만 사용, 클라이언트 노출 금지
2. **캐싱 정책**: Google 정책상 좌표 캐싱은 30일 제한
3. **한국 주소 형식**: 도로명 주소가 지번 주소보다 정확도 높음
4. **Rate Limit**: 분당 3,000건 제한 (현재 사용량으로는 충분)

---

## 10. 승인 체크리스트

- [x] Geocoding API 활성화 확인
- [x] API 키 환경변수 설정 (`GOOGLE_PLACES_API_KEY`)
- [x] 3단계 검색 전략 확정
- [x] 국가/도시 정보 추가 방식 확정
- [x] 사전 체크 완료
- [x] 구현 시작 승인
- [x] geocoder.py 생성 완료
- [x] automation.py 연동 완료
- [x] db_helpers.py 수정 완료

---

**저장 위치**: `docs/GEOCODING_STRATEGY.md`  
**구현 완료: 2026-01-19**
