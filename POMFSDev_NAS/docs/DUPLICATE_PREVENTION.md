# 중복 방지 전략 문서

> 작성일: 2026-01-19  
> 버전: 1.0  
> 목적: Instagram 게시물의 중복 저장 방지 메커니즘 설명

---

## 1. 개요

동일한 Instagram 게시물이 여러 번 스크래핑되어도 중복 저장되지 않도록 하는 전략입니다.

### 핵심 원리
- **Shortcode**: Instagram 게시물의 고유 식별자
- 예: `https://instagram.com/p/ABC123/` → shortcode = `ABC123`
- 모든 게시물은 고유한 shortcode를 가짐

---

## 2. 중복 체크 위치

### 2.1 Neon DB (scraped_posts 테이블)

**파일**: `db_utils.py`

```python
# INSERT 전 shortcode 존재 여부 확인
shortcode = post_data.get('shortcode')
if shortcode:
    cur.execute("SELECT id FROM scraped_posts WHERE shortcode = %s", (shortcode,))
    if cur.fetchone():
        print(f"[DB] Duplicate shortcode skipped: {shortcode}")
        return None  # 중복이면 저장하지 않고 종료
```

**테이블 스키마**:
```sql
CREATE TABLE scraped_posts (
    id SERIAL PRIMARY KEY,
    shortcode VARCHAR(50) UNIQUE,  -- UNIQUE 제약조건
    ...
);
```

### 2.2 MusicFeedPlatform DB (posts 테이블)

**파일**: `db_helpers.py`

```python
# instagram_link (shortcode 기반 URL)로 중복 체크
if instagram_post_url:
    cur.execute('SELECT id FROM posts WHERE instagram_link = %s', (instagram_post_url,))
    if cur.fetchone():
        # 중복이면 저장하지 않음
        return False
```

**Instagram Link 생성**:
```python
# shortcode → Instagram URL 변환
if f_shortcode:
    instagram_post_url = f"https://www.instagram.com/p/{f_shortcode}/"
```

---

## 3. 데이터 흐름에서의 중복 체크

```
[Instagram 게시물 스크래핑]
         |
         v
[shortcode 추출] ─── "ABC123"
         |
         v
┌────────────────────────────────────┐
│ Neon DB 중복 체크                  │
│ SELECT * FROM scraped_posts        │
│ WHERE shortcode = 'ABC123'         │
└────────────┬───────────────────────┘
             │
     ┌───────┴───────┐
     │               │
  [있음]          [없음]
     │               │
     v               v
  [SKIP]       [INSERT to Neon DB]
                     │
                     v
            [AI 분석 (OCR/LLM)]
                     │
                     v
       ┌─────────────┴─────────────┐
       │                           │
   [이벤트 포스터]           [이벤트 아님]
       │                           │
       v                           v
┌──────────────────────┐      [SKIP]
│ MusicFeedPlatform    │
│ 중복 체크            │
│ instagram_link 확인  │
└──────────┬───────────┘
           │
   ┌───────┴───────┐
   │               │
[있음]          [없음]
   │               │
   v               v
[SKIP]    [INSERT + GCS 업로드]
```

---

## 4. 중복 상태 반환값

### automation.py 결과 상태

| 상태 | 설명 |
|------|------|
| `Saved` | 새 게시물 저장 완료 |
| `Duplicate` | 중복으로 인해 저장 건너뜀 |
| `Skipped (Not Event)` | 이벤트 포스터가 아님 |
| `Error` | 처리 중 오류 발생 |

---

## 5. 장점

1. **데이터 무결성**: 동일한 게시물이 DB에 중복 저장되지 않음
2. **효율성**: INSERT 전 빠른 조회로 불필요한 처리 방지
3. **비용 절감**: 중복 게시물에 대한 AI 분석 및 GCS 업로드 비용 절약
4. **일관성**: 두 개의 DB (Neon, MusicFeedPlatform) 모두 중복 방지

---

## 6. 제한사항

1. **삭제 후 재수집**: 게시물이 삭제된 후 다시 수집하면 새로운 것으로 인식
2. **shortcode 없는 게시물**: 극히 드물지만 shortcode가 없으면 중복 체크 불가
3. **수동 입력**: 수동으로 입력한 이벤트는 shortcode가 없어 중복 체크 대상 아님

---

## 7. 모니터링

로그에서 중복 발생 확인:
```
[DB] Duplicate shortcode skipped: ABC123
```

배치 수집 결과에서 확인:
```json
{
    "scraped_count": 10,
    "saved_count": 3,
    "skip_count": 7,  // 중복 또는 비이벤트
    "details": [
        {"shortcode": "ABC123", "db_status": "Duplicate"},
        {"shortcode": "DEF456", "db_status": "Saved"}
    ]
}
```

---

**저장 위치**: `docs/DUPLICATE_PREVENTION.md`
