# AI 이벤트 판정 로직 개선 계획

> **문서 상태**: 승인 대기  
> **작성일**: 2026-01-20  
> **작성자**: P.O.MFS AI Development Team

---

## 1. 배경 및 문제점

### 1.1 배치 테스트 결과 (1,859개 계정)

| 항목 | 결과 | 비고 |
|------|------|------|
| 총 분석 게시물 | 3,965개 | 정상 완료 |
| MusicFeedPlatform 저장 | **0개** | 핵심 문제 |
| 실패 계정 | 2개 (@undefined) | Excel 빈 셀 문제 |
| 성공 표시 | 0 | 서버 재시작으로 task 상태 손실 |

### 1.2 현재 이벤트 판정 조건 (automation.py 276번 줄)

```python
elif final_dates and (final_venue_id or final_venue) and filename:
    # 날짜 AND 장소 AND 파일명이 모두 필요
```

**문제점**: 조건이 너무 엄격하여 실제 이벤트 포스터도 저장되지 않음

- 날짜가 있어도 장소가 없으면 → 저장 안됨
- 장소가 있어도 날짜가 없으면 → 저장 안됨
- OCR에서 정보를 추출하지 못하면 → 저장 안됨

### 1.3 추가 문제점

| 문제 | 현상 | 원인 |
|------|------|------|
| Untitled Event | 공연명 없이 "Untitled Event"로 저장 | app.py 227번 줄 기본값 |
| 이미지 미표시 | Review 페이지 이미지 안 보임 | Instagram CDN URL 만료 |
| 캡션 미활용 | 캡션 텍스트 분석 안함 | OCR 결과만 LLM에 전달 |

---

## 2. 변경 요구사항

### 2.1 이벤트 판정 조건 변경 (OR 로직)

**현재 (AND 로직):**
```
날짜 AND 장소 AND 파일명 → 이벤트
```

**변경 후 (OR 로직):**
```
공연명만 OR (공연명 + 날짜) OR (장소 + 날짜) → 이벤트
```

| 조건 | 결과 | 비고 |
|------|------|------|
| **공연명만 있음** | ✅ 이벤트 | 날짜/장소 없어도 OK **(추가)** |
| 공연명 + 날짜 | ✅ 이벤트 | 장소 없어도 OK (나중에 결정될 수 있음) |
| 장소 + 날짜 | ✅ 이벤트 | 공연명 없어도 OK |

### 2.2 분석 소스 확장

**현재:**
- 이미지 OCR 결과만 분석

**변경 후:**
- 이미지 OCR 결과 **+** 캡션 텍스트 **모두** 분석
- 어느 쪽에서든 공연 정보가 나오면 이벤트로 판정

### 2.3 공연명 없는 경우 처리

**현재:**
```python
event_name = post.get('event_name') or 'Untitled Event'
```

**변경 후:**
- 공연명이 없으면 **아티스트명** 사용
- 아티스트명도 없으면 **장소명 + 날짜** 조합 사용
- 예: `@username Live at Club XYZ`

### 2.4 이미지 Preview 수정

**현재:**
```html
<img src="{{ post.image_url }}">  <!-- Instagram CDN URL (만료됨) -->
```

**변경 후:**
```html
<img src="{{ post.local_image_path }}">  <!-- 로컬 저장 이미지 -->
```

---

## 3. 수정 대상 파일

| 파일 | 수정 내용 | 수정 금지 | 승인 필요 |
|------|----------|----------|----------|
| `automation.py` | 이벤트 판정 조건 완화 (276번 줄) | ✅ | ✅ |
| `analyzer.py` | OCR + 캡션 통합 분석 | ✅ | ✅ |
| `app.py` | Untitled Event 대체 로직 | ✅ | ✅ |
| `db_helpers.py` | event_name 기본값 처리 | ✅ | ✅ |
| `templates/review.html` | 로컬 이미지 경로 사용 | ❌ | ❌ |

---

## 4. 상세 변경 계획

### 4.1 automation.py (276번 줄)

**현재 코드:**
```python
elif final_dates and (final_venue_id or final_venue) and filename:
```

**변경 코드:**
```python
# 이벤트 판정 조건: 공연명만 OR (공연명 + 날짜) OR (장소 + 날짜)
has_title = bool(final_title)  # 공연명만 있어도 이벤트
has_title_and_date = final_title and final_dates
has_venue_and_date = (final_venue_id or final_venue) and final_dates

elif has_title or has_title_and_date or has_venue_and_date:
```

### 4.2 analyzer.py

**변경 내용:**
- `analyze_with_llm()` 함수에 캡션 텍스트 파라미터 추가
- LLM 프롬프트에 캡션 텍스트 포함
- OCR 결과가 없어도 캡션에서 정보 추출 시도

**프롬프트 예시:**
```
Analyze the following sources and extract event information:

[Source 1: Image OCR Text]
{ocr_text}

[Source 2: Instagram Caption]
{caption_text}

Extract event information from EITHER source...
```

### 4.3 app.py (227번 줄)

**현재 코드:**
```python
event_name = post.get('event_name') or 'Untitled Event'
```

**변경 코드:**
```python
event_name = post.get('event_name')
if not event_name:
    artist = post.get('artist') or post.get('username', '')
    venue = post.get('event_venue', '')
    if artist:
        event_name = f"{artist} Live"
        if venue:
            event_name += f" at {venue}"
    elif venue:
        event_name = f"Event at {venue}"
    else:
        event_name = f"@{post.get('username', 'Unknown')} Event"
```

### 4.4 이미지 Preview - 로컬 경로 동적 구성

#### 현재 문제
- `image_url`에 Instagram CDN URL이 저장됨
- CDN URL은 시간이 지나면 만료되어 이미지가 표시되지 않음

#### 해결 방안: 로컬 이미지 경로 동적 구성

**이미지 저장 구조:**
```
scraped_data/
└── YYYY-MM-DD/
    └── username/
        ├── shortcode_0.jpg
        ├── shortcode_1.jpg
        └── shortcode_ocr.txt
```

**DB에 저장된 정보:**
- `source_username` - 계정명
- `shortcode` - 게시물 고유 ID
- `created_at` - 수집 날짜

#### 4.4.1 app.py 수정 (review 데이터 로딩)

**추가 로직:**
```python
import glob

def find_local_image(username, shortcode):
    """로컬 이미지 경로 동적 탐색"""
    pattern = f"scraped_data/*/{username}/{shortcode}*.jpg"
    matches = glob.glob(pattern)
    if matches:
        return matches[0]  # 첫 번째 이미지 반환
    return None

# review 데이터 로딩 시
for post in posts:
    local_path = find_local_image(post['source_username'], post['shortcode'])
    post['local_image_path'] = local_path
```

#### 4.4.2 app.py 수정 (정적 파일 경로 설정)

**scraped_data 폴더를 Flask 정적 파일로 제공:**
```python
from flask import send_from_directory

@app.route('/scraped_data/<path:filepath>')
def serve_scraped_image(filepath):
    return send_from_directory('scraped_data', filepath)
```

#### 4.4.3 templates/review.html 수정

**현재:**
```html
<img src="{{ post.image_url }}">  <!-- Instagram CDN URL -->
```

**변경:**
```html
{% if post.local_image_path %}
    <img src="/{{ post.local_image_path }}">
{% else %}
    <img src="/static/placeholder.png" alt="이미지 없음">
{% endif %}
```

---

## 5. 작업 계획

| # | 작업 | 상태 | 예상 시간 |
|---|------|------|----------|
| 0 | 본 문서 작성 및 저장 | ✅ 완료 | - |
| 1 | automation.py 이벤트 판정 조건 변경 | ⏳ 승인 대기 | 10분 |
| 2 | analyzer.py OCR + 캡션 통합 분석 | ⏳ 승인 대기 | 20분 |
| 3 | app.py Untitled Event 대체 로직 | ⏳ 승인 대기 | 10분 |
| 4 | app.py 로컬 이미지 경로 동적 구성 + Flask 정적 파일 설정 | ⏳ 승인 대기 | 15분 |
| 5 | review.html 로컬 이미지 경로 표시 | ⏳ 대기 | 10분 |
| 6 | 테스트 및 검증 | ⏳ 대기 | 15분 |

---

## 6. 승인 필요 항목

- [ ] `automation.py` 수정 승인
- [ ] `analyzer.py` 수정 승인
- [ ] `app.py` 수정 승인
- [ ] `db_helpers.py` 수정 승인 (필요 시)

---

## 7. 예상 효과

| 항목 | 현재 | 변경 후 |
|------|------|---------|
| 이벤트 감지율 | 매우 낮음 (0%) | 크게 향상 예상 |
| Untitled Event | 다수 발생 | 최소화 |
| 이미지 표시 | 만료로 안 보임 | 로컬 이미지로 항상 표시 |
| 정보 소스 | OCR만 | OCR + 캡션 |

---

## 8. 문서 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-01-20 | v1.0 | 초안 작성 |
| 2026-01-20 | v1.1 | 이벤트 판정 조건 추가: "공연명만 있어도 이벤트" |
| 2026-01-20 | v1.2 | 이미지 Preview 로컬 경로 동적 구성 방안 상세 추가 |
| 2026-01-20 | v1.3 | 구현 완료: automation.py, app.py, review.html 수정, 날짜 없는 이벤트는 "Ready to Review (No Date)" 상태로 처리 |

---

> **다음 단계**: 승인 후 작업 진행
