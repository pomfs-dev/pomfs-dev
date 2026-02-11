# P.O.MFS 개발 센터

> **Performance Organization AI Management For System**
> 
> 인스타그램 공연/이벤트 정보를 자동으로 수집하고, AI로 분석하여 MusicFeedPlatform 데이터베이스에 자동 발행하는 올인원 자동화 솔루션입니다.
>
> **버전**: v2.3.1 (Server Restart Recovery)  
> **최종 업데이트**: 2026-01-22

---

## 목차

1. [개요 (Overview)](#1-개요-overview)
2. [로드맵 & 일정](#2-로드맵--일정)
3. [워크플로우](#3-워크플로우)
4. [주요 기능](#4-주요-기능)
5. [업데이트 로그](#5-업데이트-로그)
6. [개발자 노트](#6-개발자-노트)

---

## 1. 개요 (Overview)

### 🎯 프로젝트 목표

> 핵심 목표: 수작업으로 진행하던 공연 정보 수집을 자동화하여, 운영 인력을 대폭 줄이고 실시간에 가까운 이벤트 정보 업데이트를 가능하게 합니다.

- **자동화**: 인스타그램 계정 수백 개를 한 번에 수집하고 분석
- **정확도**: OCR + LLM 조합으로 포스터 이미지에서 정확한 이벤트 정보 추출
- **중복 방지**: Shortcode 기반 중복 체크로 동일 게시물 재수집 방지
- **자동 발행**: 이벤트 포스터로 판단된 게시물은 자동으로 MusicFeedPlatform에 발행 (is_draft=False)
- **지도 표시**: Geocoding API로 장소 좌표를 자동 변환하여 지도에 표시 가능

### 🏗️ 기술 스택

| 영역 | 기술 | 용도 |
|------|------|------|
| Backend | Python Flask | API 서버, 비동기 작업 처리 |
| Frontend | Jinja2 + Bootstrap 5 | 관리자 UI, 다크 모드 디자인 |
| Scraping | Apify Cloud | Instagram 데이터 수집 (IP 차단 우회) |
| AI/OCR | Mistral API | 이미지 OCR + LLM 기반 이벤트 정보 추출 |
| Storage | Google Cloud Storage | 이벤트 이미지 호스팅 |
| Database (임시) | Neon PostgreSQL | scraped_posts 임시 저장 |
| Database (운영) | MusicFeedPlatform PostgreSQL | 최종 이벤트 데이터 저장 |
| Geocoding | Google Geocoding API | 장소명 → 좌표 변환 |

### 📊 현재 프로젝트 상태

> **현재 버전: v2.3.1 (Server Restart Recovery)**
> 
> 서버 재시작 복구, 404 에러 자동 처리, 스마트 스킵 로직, 비디오 게시물 캡션 분석, 완화된 이벤트 판정(OR 조건), 전체 파이프라인 통합으로 안정적인 대량 수집이 가능합니다.

#### Status Board

| 🔥 Priority | 🚀 In Progress | ✅ Completed |
|-------------|----------------|--------------|
| find_local_image 캐시 구현 | 배포 패키징 및 안정화 테스트 | 서버 재시작 복구 (v2.3.1) |
| app.py Blueprint 분리 | | 404 에러 자동 처리 (v2.3.1) |
| JavaScript 파일 분리 | | 스마트 스킵 로직 (v2.2.0) |
| 알림 봇 연동 고도화 | | 비디오 캡션 분석 (v2.1.0) |
| 지도 기반 이벤트 표시 UI | | 전체 파이프라인 통합 (v2.0.0) |
| | | OR 이벤트 판정 로직 |
| | | Discovery API 통합 |
| | | Geocoding 자동화 |
| | | 중복 방지 메커니즘 |
| | | 세션 유지 (localStorage) |

### 🔑 필수 환경 변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `APIFY_TOKEN` | Apify Cloud API 토큰 | O |
| `MISTRAL_API_KEY` | Mistral OCR/LLM API 키 | O |
| `NEON_DB_URL` | Neon PostgreSQL 연결 URL | O |
| `MUSICFEED_DB_URL` | MusicFeedPlatform DB 연결 URL | O |
| `GOOGLE_CLOUD_PROJECT_ID` | GCP 프로젝트 ID | O |
| `GOOGLE_CLOUD_BUCKET_NAME` | GCS 버킷명 (기본: communitystorage2) | O |
| `GOOGLE_CLOUD_CREDENTIALS` | GCP 서비스 계정 JSON | O |
| `GOOGLE_PLACES_API_KEY` | Google Geocoding API 키 | O |

---

## 2. 로드맵 & 일정

### 📅 버전 히스토리 타임라인

| 버전 | 날짜 | 코드명 | 주요 변경사항 |
|------|------|--------|--------------|
| v2.1.0 | 2026-01-22 | Video Caption | 비디오 게시물 캡션 수집 및 분석 지원 |
| v2.0.0 | 2026-01-22 | Full Pipeline | 3개 핵심 기능 전체 파이프라인 통합, OR 이벤트 판정 |
| v1.9.6 | 2026-01-22 | Bug Fixes | filename 버그 수정, 재분석 파이프라인 완성 |
| v1.8.0 | 2026-01-19 | Session & Geocoding | Geocoding 자동화, 중복 방지, localStorage 세션 유지 |
| v1.7.0 | 2026-01-16 | Migration & Ops Upgrade | 마이그레이션 도구, 배치 리포트, 이미지 프리뷰 |
| v1.6.1 | 2026-01-16 | Venue Discovery Update | 공연장 찾기 UI 개편, 비동기 엔진, 진행률 바 |
| v1.6.0 | 2026-01-16 | Cloud Beta | Apify Scraper 연동, 다크 모드, 병렬 처리 |
| v1.0.0 | 2025-12-01 | Initial Release | Selenium 기반 로컬 수집기, 기본 OCR, Flask 서버 |

### 🎯 2026 Q1 목표

#### Phase 1: 안정성 확보 ✅ (완료)
- [x] Selenium → Apify 전환 (IP 차단 우회)
- [x] 다크 모드 UI 디자인 시스템
- [x] 병렬 처리 및 동시성 제어
- [x] 실시간 진행률 모니터링

#### Phase 2: 데이터 품질 ✅ (완료)
- [x] Shortcode 기반 중복 방지
- [x] Geocoding 자동화 (3단계 검색)
- [x] MusicFeedPlatform 자동 발행
- [x] GCS 이미지 업로드

#### Phase 3: UX 개선 ✅ (완료)
- [x] localStorage 기반 세션 유지
- [x] 배치 설정 자동 저장
- [x] 페이지 이동 후 작업 상태 복원
- [x] 슬라이더/숫자 입력 동기화

#### Phase 4: 고도화 🚀 (진행 중)
- [ ] 지도 기반 이벤트 표시 UI
- [ ] 알림 봇 연동 (Telegram/Email)
- [ ] 배포 패키징 및 최종 안정화
- [ ] 모바일 전용 뷰어 (PWA)

### 🚀 Future Ideas (Backlog)
- 티켓 예매 사이트 자동 매칭
- 공연 포스터 자동 디자인 생성 (Gen AI)
- 아티스트 프로필 자동 생성
- 이벤트 추천 알고리즘
- 다국어 지원 (영어, 일본어)

---

## 3. 워크플로우

### 📊 전체 데이터 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           P.O.MFS Data Pipeline                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Excel 파일   │────▶│ Apify Cloud  │────▶│  Neon DB     │────▶│  Mistral AI  │
│  계정 목록    │     │  Scraper     │     │ scraped_posts│     │   OCR/LLM    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                     │                     │
                            ▼                     ▼                     ▼
                     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
                     │  로컬 이미지  │     │ 중복 체크    │     │ is_event?    │
                     │  다운로드     │     │ (shortcode)  │     │ 이벤트 판별  │
                     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                                          ┌───────────────────────────┼───────────────┐
                                          │                           │               │
                                          ▼                           ▼               ▼
                                   ┌──────────────┐           ┌──────────────┐ ┌──────────────┐
                                   │   Skip       │           │   GCS 업로드  │ │   Geocoding  │
                                   │ (Not Event)  │           │  이미지 저장  │ │  좌표 변환   │
                                   └──────────────┘           └──────────────┘ └──────────────┘
                                                                      │               │
                                                                      └───────┬───────┘
                                                                              ▼
                                                                   ┌──────────────────┐
                                                                   │ MusicFeedPlatform│
                                                                   │   DB 저장        │
                                                                   │  (is_draft=False)│
                                                                   └──────────────────┘
                                                                              │
                                                                              ▼
                                                                   ┌──────────────────┐
                                                                   │  메인 캐러셀카드  │
                                                                   │     표시         │
                                                                   └──────────────────┘
```

### 🔄 단계별 상세 설명

#### Step 1. 리스트 업 (Targeting)

관리자가 엑셀(XLSX) 파일을 업로드하면 시스템이 Instagram 계정 목록을 파싱합니다. 또는 '공연장 찾기(Venue Discovery)' 기능으로 키워드 기반 계정 발굴이 가능합니다.

- 지원 포맷: XLSX (엑셀)
- 필수 컬럼: instagram_id (또는 username)
- 선택 컬럼: venue_name, city, category

#### Step 2. 병렬 수집 (Parallel Scraping)

```
[Frontend] Concurrency 설정 (1~5) → [Backend] Thread Pool → [Apify API] → [Instagram]
```

사용자가 설정한 동시성(Concurrency) 수만큼 Apify Instagram Scraper를 병렬 호출합니다.

- **Apify Actor**: apify/instagram-post-scraper
- **수집 데이터**: 게시물 이미지, 캡션, 날짜, shortcode
- **프록시 관리**: Apify 자동 처리 (IP 차단 우회)
- **속도 제어**: 슬라이더로 수집 속도 조절 가능

#### Step 3. 중복 체크 (Deduplication)

수집된 게시물의 shortcode를 기준으로 중복 여부를 확인합니다.

- **1차 체크**: Neon DB scraped_posts 테이블 (UNIQUE 제약조건)
- **2차 체크**: MusicFeedPlatform posts 테이블 (instagram_link 컬럼)
- **중복 시**: Skip 처리 및 로그 기록

#### Step 4. AI 분석 (Intelligence)

수집된 포스터 이미지에서 OCR로 텍스트를 추출하고, LLM으로 구조화된 이벤트 정보를 생성합니다.

```
[이미지] → Mistral OCR → [텍스트] → Mistral LLM → [JSON 구조화]
```

- **OCR 모델**: Mistral (한국어/일본어 지원)
- **LLM 분석**: 이벤트 포스터 여부 판별 + 정보 추출
- **추출 필드**: event_name, event_venue, event_date, event_location, artists
- **Rate Limit**: 1 request/second (전역 Rate Limiter 적용)

#### Step 5. Geocoding (좌표 변환)

이벤트 장소 정보를 Google Geocoding API로 좌표(위도/경도)로 변환합니다.

- **1단계**: event_location (상세 주소) 검색
- **2단계**: venue_name + city 조합 검색 (Fallback)
- **3단계**: 검색 실패 시 NULL 저장
- **저장 필드**: latitude, longitude, formatted_address, place_id

#### Step 6. 저장 및 발행 (Publishing)

이벤트 포스터로 판별된 게시물은 GCS에 이미지를 업로드하고 MusicFeedPlatform DB에 자동 저장됩니다.

- **GCS 경로**: `gs://communitystorage2/ai-post-img/{user_id}/{timestamp}-{unique_id}-{filename}`
- **DB 저장**: is_draft=False (즉시 발행)
- **user_id**: 'pomfs_ai' (AI 자동 발행 식별자)
- **genre**: 'pomfs_ai' (AI 분류 식별자)

---

## 4. 주요 기능

### 1. 📦 배치 수집 (Batch Collection)

> 수백 개의 Instagram 계정을 한 번에 수집하고 분석하는 핵심 기능입니다.

- **엑셀 업로드**: XLSX 파일로 계정 목록 일괄 등록
- **페이지네이션**: 현재 페이지부터 수집 시작 가능
- **동시성 제어**: 1~5개 작업 병렬 처리
- **실시간 진행률**: 각 계정별 진행률 바 및 타이머 표시
- **터미널 로그**: 실시간 로그 스트리밍
- **세션 유지**: 페이지 이동 후에도 작업 상태 복원
- **배치 설정 저장**: 수집 개수, 동시성, 스크래핑 제한 자동 저장

### 2. 🔍 공연장 찾기 (Venue Discovery)

> 키워드 기반으로 새로운 공연장/클럽 Instagram 계정을 자동 발굴합니다.

- **키워드 검색**: "홍대 라이브클럽" 같은 키워드 입력
- **네이버 검색 연동**: 네이버 검색 API로 장소 정보 수집
- **Instagram 매칭**: 장소명으로 Instagram 계정 자동 검색
- **비동기 처리**: 화면 멈춤 없이 부드러운 검색
- **자동 추가**: 발견된 계정을 엑셀 파일 상단에 추가

### 3. 🤖 AI 분석 (Smart Parsing)

> Mistral API를 활용한 OCR + LLM 기반 이벤트 정보 추출 시스템입니다.

- **OCR 추출**: 포스터 이미지에서 텍스트 추출 (한국어/일본어 지원)
- **이벤트 판별**: is_event_poster 여부 자동 분류
- **정보 추출**: 공연명, 날짜, 장소, 아티스트 자동 파싱
- **날짜 정규화**: 다양한 형식을 YYYY-MM-DD로 변환
- **Fallback 로직**: LLM 실패 시 정규식 기반 휴리스틱 적용

### 4. 🚀 자동 발행 (Auto Publishing)

> 이벤트 포스터로 판별된 게시물을 MusicFeedPlatform에 자동 발행합니다.

- **GCS 업로드**: 이미지를 Google Cloud Storage에 저장
- **DB 저장**: MusicFeedPlatform posts 테이블에 저장
- **즉시 발행**: is_draft=False로 저장하여 즉시 노출
- **Geocoding**: 장소 좌표 자동 변환 및 저장
- **중복 방지**: shortcode 기반 중복 체크

### 5. 🔒 중복 방지 (Deduplication)

> 동일한 게시물이 중복 저장되지 않도록 다층 체크를 수행합니다.

- **Shortcode 기반**: Instagram 게시물 고유 ID로 중복 판별
- **Neon DB 체크**: scraped_posts 테이블 UNIQUE 제약조건
- **MusicFeed DB 체크**: instagram_link 컬럼으로 최종 확인
- **Skip 처리**: 중복 시 저장 건너뛰기 및 로그 기록

### 6. 🗺️ Geocoding (좌표 변환)

> 이벤트 장소를 지도에 표시하기 위해 좌표로 자동 변환합니다.

- **Google Geocoding API**: 주소/장소명 → 위도/경도 변환
- **3단계 검색 전략**: 상세 주소 → 장소명+도시 → NULL
- **저장 필드**: latitude, longitude, formatted_address, place_id
- **지도 표시**: 좌표로 이벤트 위치 시각화 (예정)

### 7. 💾 세션 유지 (Session Persistence)

> 페이지 이동 후에도 진행 중인 작업 상태를 유지합니다.

- **localStorage 저장**: 진행 중인 task 정보 클라이언트 저장
- **UI 복원**: 진행률 바, 타이머, 상태 텍스트 복원
- **배치 설정 저장**: 수집 개수, 동시성, 스크래핑 제한 유지
- **폴링 재개**: 페이지 복귀 시 자동 폴링 재시작

### 8. 📤 데이터 마이그레이션 (Migration Tool)

> 로컬 데이터를 운영 서버(Neon DB)로 원클릭 전송합니다.

- **원클릭 전송**: 간편한 마이그레이션 UI
- **스트리밍 로그**: 실시간 전송 상태 모니터링
- **중복 방지**: 이미 존재하는 데이터 건너뛰기

---

## 5. 업데이트 로그

### v2.3.1 (Server Restart Recovery) - 2026-01-22 🔴 Latest

**[Core] 서버 재시작 복구 기능**
- 404 에러 자동 감지 및 처리 (3회 연속 시 다음 작업으로 진행)
- 서버 재시작 감지 함수 `checkServerRestartAndCleanup()` 추가
- 페이지 로드 시 stale task 자동 정리
- 사용자에게 서버 재시작 알림 표시

**[UX] 중지 버튼 개선**
- `isProcessing` 상태와 무관하게 강제 중지 가능
- localStorage 정리, 서버 세션 종료, 강제 새로고침 지원
- `resetBatchUI()` 함수로 일관된 UI 복구

---

### v2.3.0 (Batch Report Fix) - 2026-01-22 🟣

**[Fix] 배치 리포트 수정**
- 성공/저장 건수가 0으로 표시되는 버그 수정
- status 정규화: 백엔드 'completed' → 프론트엔드 'success' 매핑

**[Core] 페이지별 수집 통계**
- page 파라미터 지원 API 추가
- 현재 페이지 기준 통계 조회 가능

**[Core] 스킵 추적 상세화**
- 스킵 이유 분류: 중복, 이미 수집됨 등

---

### v2.2.0 (Smart Skip Logic) - 2026-01-22 🟡

**[Core] 스마트 스킵 로직**
- 이미 수집된 계정 자동 감지 및 스킵
- 페이지별 스마트 스킵 적용
- 스킵된 계정 수 통계 표시

**[Core] 배치 세션 관리**
- 서버 측 배치 세션 ID 발급
- 세션별 수집 상태 추적

---

### v2.1.0 (Video Caption Support) - 2026-01-22 🔵

**[Core] 비디오 게시물 캡션 분석**
- 비디오 게시물의 캡션 텍스트 수집 및 저장
- 비디오 콘텐츠 다운로드 스킵 (캡션만 저장)
- OCR 없이 캡션 텍스트로 직접 LLM 분석
- 이벤트 감지 시 GCS 업로드 없이 DB 저장 (image_url = NULL)
- is_video 플래그 추가로 비디오/이미지 구분

**[Test] 비디오 분석 검증**
- 054soundville 계정 비디오 게시물 테스트
- 이벤트명 "미리메리크리스마스", 날짜 2025-11-01 추출 성공
- MusicFeed DB 저장 확인

---

### v2.0.0 (Full Pipeline) - 2026-01-22 🟣

**[Core] 3개 핵심 기능 전체 파이프라인 통합**
- Batch Collection: 엑셀 기반 대량 계정 수집 → 완전 파이프라인
- Scrape: 단일 계정 수집 → 완전 파이프라인
- Discovery: 베뉴 Instagram ID 발견 + 수집 → 완전 파이프라인

**[Core] 이벤트 판정 조건 완화 (OR 로직)**
- 기존: 공연명 AND 날짜 AND 장소 (너무 엄격)
- 변경: 공연명만 OR 공연명+날짜 OR 장소+날짜
- 이벤트 저장률 대폭 개선

**[API] Discovery API 추가**
- `/api/discovery/scrape_venue`: 단일 베뉴 Instagram ID 수집 + 전체 파이프라인
- `/api/discovery/batch_scrape`: 발견된 모든 베뉴 일괄 수집

**[Fix] 재분석 워크플로우 완성**
- Geocoding, GCS 업로드, MusicFeed DB 저장 누락 수정

---

### v1.9.6 (Bug Fixes) - 2026-01-22 🔵

**[Fix] filename 변수 미정의 버그 수정**
- existing_valid_images[0] 할당 누락 문제 해결
- 이미지 처리 시 오류 방지

**[Fix] 재분석 파이프라인 완성**
- Geocoding 자동화 연동
- GCS 업로드 연동
- MusicFeed DB 저장 연동

---

### v1.8.0 (Session & Geocoding) - 2026-01-19 🟢

**[Core] Geocoding 자동화 구현**
- Google Geocoding API 연동
- 3단계 검색 전략: 상세 주소 → 장소명+도시 → NULL
- 이벤트 저장 시 자동 좌표 변환
- 저장 필드: latitude, longitude, formatted_address, place_id

**[Core] 중복 방지 메커니즘**
- Shortcode 기반 중복 체크 (Instagram 게시물 고유 ID)
- Neon DB: scraped_posts 테이블 UNIQUE 제약조건
- MusicFeedPlatform DB: instagram_link 컬럼으로 중복 확인

**[UX] 배치 수집 페이지 세션 유지**
- localStorage 기반 진행 중 task 저장 및 복원
- 페이지 이동 후에도 진행률 바, 타이머, 상태 텍스트 유지
- 배치 설정(수집 개수, 동시성, 스크래핑 제한) 자동 저장
- saveRunningTask, removeRunningTask, getRunningTasks 함수 구현

**[UX] 자동 수집 개수 입력 개선**
- 슬라이더와 숫자 입력 양방향 동기화
- 직접 숫자 입력 시 min/max 범위 자동 조정

**[Fix] 복원된 작업의 진행률 중복 카운팅 방지**
- pollTaskStatusWithRowUI에서 globalCompletedTasks++ 제거
- 서버 세션 completed_count 신뢰

---

### v1.7.0 (Migration & Ops Upgrade) - 2026-01-16 🔵

**[Ops] 데이터 마이그레이션 도구 (Migration Tool)**
- 로컬 데이터를 운영 서버(Neon DB)로 원클릭 전송
- 스트리밍 기반 로그 모니터링
- 중복 방지 로직 적용

**[UX] 배치 작업 리포트 (Batch Report)**
- 일괄 수집 완료 시 성과 요약 리포트 팝업
- 소요시간, 성공률, 저장 건수 표시

**[Fix] 수집 목록 이미지 프리뷰 개선**
- /load_image 파이프라인 구축
- 검토 데이터 저장 시 이미지 경로 유실 버그 수정

**[Doc] 아티스트/공연장용 Posting Guide 작성**

---

### v1.6.1 (Venue Discovery Update) - 2026-01-16 🟢

**[UX] 공연장 찾기(Discovery) UI 전면 개편**
- 일괄 수집 페이지와 동일한 진행 대시보드 & 터미널 로그
- 각 검색 항목별 실시간 진행률 그래프(Progress Bar)

**[Core] 검색/수집 엔진 비동기(Async) 전환**
- 화면 멈춤 없이 부드러운 병렬 처리
- 직접 키워드 검색(Manual Search) 시 엑셀 파일 상단에 자동 추가

**[Fix] 데이터 초기화 버튼 클릭 시 업로드 된 엑셀 리스트까지 완전 삭제**

---

### v1.6.0 (Cloud Beta) - 2026-01-16 🟡

**[Core] Apify Serverless Scraper 연동**
- Selenium → Apify 전환으로 IP 차단 문제 해결
- 클라우드 기반 안정적인 스크래핑

**[UI] 다크 모드(Dark Mode) 디자인 시스템 적용**
- 전체 UI 다크 테마 적용
- 눈의 피로 감소

**[Feat] 배치 작업 병렬 처리(Parallelism)**
- 동시성 제어 슬라이더 (1~5)
- Thread Pool 기반 병렬 처리

**[Feat] 실시간 경과 시간 및 상세 통계 표시 (Timer)**

**[Doc] 개발자 노트(Notion Style) 추가**

---

### v1.5.x (Pre-Cloud) - 2026-01 초 ⚫

- Mistral OCR/LLM 분석 파이프라인 구축
- GCS 이미지 업로드 기능
- MusicFeedPlatform DB 연동
- 검토 페이지(Review) 구현
- 등록된 이벤트 목록(Registered) 페이지

---

### v1.0.0 (Initial) - 2025-12-01 ⚫

- Selenium 기반 로컬 수집기 구현
- 기본적인 OCR 및 키워드 매칭 분석
- Flask 웹 서버 구축
- SQLite 기반 로컬 데이터 저장
- 기본 UI (밝은 테마)

---

## 6. 개발자 노트

### 🏛️ Architecture Decision Records (ADR)

#### ADR-001: Selenium → Apify 전환

| 항목 | 내용 |
|------|------|
| **결정** | 로컬 Selenium 크롤러를 Apify Cloud로 전환 |
| **배경** | Instagram의 강력한 봇 탐지 시스템으로 인해 Selenium 기반 수집이 빈번하게 차단됨. IP 차단, 로그인 챌린지, CAPTCHA 등의 문제가 지속적으로 발생. |
| **대안 검토** | Proxy Rotation (비용 대비 효과 미흡), Headless Browser Farm (인프라 관리 부담), Apify (건당 비용 발생하지만 안정성 확보) |
| **결론** | 유지보수 비용과 안정성을 고려하여 Apify 도입 결정. 건당 비용이 발생하지만 인력 비용 절감으로 상쇄. |

#### ADR-002: Mistral API 선택

| 항목 | 내용 |
|------|------|
| **결정** | OCR 및 LLM 분석에 Mistral API 사용 |
| **배경** | 포스터 이미지에서 한국어/일본어 텍스트를 정확하게 추출하고, 비정형 텍스트에서 이벤트 정보를 구조화해야 함. |
| **대안 검토** | Google Vision API (OCR 품질 우수하나 비용 높음), OpenAI GPT-4V (품질 우수하나 비용 매우 높음), Mistral (OCR 품질 양호, 비용 효율적, 한국어/일본어 지원) |
| **결론** | 비용 대비 품질이 우수한 Mistral 선택. Rate Limit (1 req/sec) 대응을 위해 전역 Rate Limiter 구현. |

#### ADR-003: Shortcode 기반 중복 방지

| 항목 | 내용 |
|------|------|
| **결정** | Instagram shortcode를 중복 판별 기준으로 사용 |
| **배경** | 동일한 게시물이 반복 수집되어 DB에 중복 저장되는 문제 발생. |
| **대안 검토** | URL 기반 (URL 형식 변경 시 중복 인식 실패 가능), 이미지 해시 (같은 이미지라도 다른 게시물일 수 있음), Shortcode (Instagram 게시물 고유 ID, 변경 없음) |
| **결론** | Shortcode를 UNIQUE 키로 사용. Neon DB와 MusicFeedPlatform DB 양쪽에서 중복 체크. |

#### ADR-004: localStorage 기반 세션 유지

| 항목 | 내용 |
|------|------|
| **결정** | 클라이언트 localStorage로 진행 중인 작업 상태 저장 |
| **배경** | 배치 수집 중 다른 페이지로 이동했다가 돌아오면 진행 상태가 사라지는 UX 문제. |
| **대안 검토** | 서버 세션 only (서버 재시작 시 상태 손실), DB 저장 (과도한 복잡성), localStorage + 서버 세션 (클라이언트 상태 복원 + 서버 상태 보완) |
| **결론** | localStorage로 UI 상태(진행률 바, 타이머 등) 저장하고, 서버 세션으로 작업 상태 보완. 하이브리드 접근. |

#### ADR-005: 이벤트 판정 조건 완화 (v2.0.0)

| 항목 | 내용 |
|------|------|
| **결정** | AND 조건에서 OR 조건으로 이벤트 판정 로직 변경 |
| **배경** | 기존 AND 조건(공연명 AND 날짜 AND 장소)이 너무 엄격하여 이벤트 저장률 0% |
| **대안 검토** | 조건 유지 (저장률 낮음), 모든 게시물 저장 (정확도 저하), OR 조건 (공연명만 OR 장소+날짜) |
| **결론** | OR 조건으로 완화하여 이벤트 저장률 대폭 개선. 공연명만 있어도 이벤트로 판정. |

#### ADR-006: 비디오 게시물 캡션 분석 (v2.1.0)

| 항목 | 내용 |
|------|------|
| **결정** | 비디오 게시물의 캡션만 수집하여 LLM 분석 |
| **배경** | 비디오 게시물이 완전히 스킵되어 공연 정보 손실. 비디오 콘텐츠는 다운로드/분석 불가하지만 캡션에 공연 정보 포함. |
| **대안 검토** | 비디오 완전 스킵 (정보 손실), 비디오 다운로드 (용량/비용 문제), 캡션만 수집 (효율적) |
| **결론** | 비디오 이미지 다운로드 스킵, 캡션만 수집 및 LLM 분석. 이벤트 감지 시 GCS 없이 DB 저장. |

---

### ⚠️ Known Issues (알려진 이슈)

| 심각도 | 이슈 | 원인 | 해결 방안 |
|--------|------|------|-----------|
| 🟡 Medium | 동시성(concurrency > 1) 시 completed_count 레이스 컨디션 가능 | 다중 스레드에서 동시에 카운터 업데이트 | 원자적 카운터 또는 락 적용 예정 |
| 🟡 Medium | 서버 재시작 시 배치 세션 상태 손실 | BATCH_SESSION이 메모리에만 저장됨 | 필요 시 Redis 또는 DB 저장으로 전환 |
| 🟡 Medium | app.py 거대 파일 (2,000+ 라인) | 기능 추가에 따른 파일 비대화 | 블루프린트 분리 예정 |
| 🟢 Low | 빈 캡션 비디오 게시물 처리 | 캡션 없는 비디오 게시물 존재 | 스킵 처리 (의도된 동작) |
| 🟢 Low | localStorage는 다른 브라우저/기기에서 복원 불가 | 클라이언트 저장 방식의 특성 | 의도된 동작 (단일 브라우저 세션 기준) |

---

### 📁 주요 파일 구조

#### 🐍 Core Python Files

| 파일 | 설명 |
|------|------|
| `app.py` | Flask 메인 앱, 모든 API 엔드포인트 |
| `automation.py` | 자동 처리 파이프라인, 비디오 캡션 분석 포함 |
| `analyzer.py` | Mistral OCR/LLM 분석 파이프라인 |
| `scraper_apify.py` | Apify Instagram 스크래핑, 비디오 캡션 수집 지원 |
| `geocoder.py` | Google Geocoding API 연동 |
| `db_helpers.py` | MusicFeedPlatform DB 헬퍼 |
| `db_utils.py` | Neon DB 유틸리티 |
| `db_config.py` | 데이터베이스 설정 |
| `gcs_uploader.py` | Google Cloud Storage 업로드 |
| `utils.py` | 공통 유틸리티 함수 |
| `venue_discovery.py` | 베뉴 디스커버리 기능 |
| `marketing_generator.py` | 마케팅 콘텐츠 생성 |

#### 📂 templates/

| 파일 | 설명 |
|------|------|
| `batch_collection.html` | 배치 수집 페이지 |
| `dashboard.html` | 메인 대시보드 |
| `events.html` | 이벤트 관리 |
| `review.html` | 스크랩 게시물 검토 |
| `registered.html` | 등록된 이벤트 목록 |
| `components/developer_log.html` | 개발자 노트 |

#### 📂 docs/

| 파일 | 설명 |
|------|------|
| `API_ENDPOINTS.md` | API 엔드포인트 문서 |
| `DUPLICATE_PREVENTION.md` | 중복 방지 전략 |
| `GEOCODING_STRATEGY.md` | Geocoding 전략 |
| `BATCH_PAGE_IMPROVEMENT.md` | 배치 페이지 개선 문서 |
| `DEVELOPER_CENTER.md` | 개발 센터 문서 (현재 파일) |

#### 📂 scraped_data/ (수정 금지)

수집된 데이터 저장 폴더  
구조: `YYYY-MM-DD/username/*.jpg, *.png`

---

### 🔧 개발 가이드

#### 코드 수정 시 주의사항

**수정 금지 파일:**
- app.py, automation.py, analyzer.py, scraper_apify.py, scraper.py
- db_helpers.py, db_utils.py, db_config.py, gcs_uploader.py, utils.py

**수정 금지 폴더:**
- scraped_data/

**기타:**
- 대규모 아키텍처 변경 시 사전 협의 필요

#### 테스트 방법

- **배치 수집**: 소수 계정(3~5개)으로 먼저 테스트
- **Geocoding**: 좌표 변환 결과 확인 (latitude, longitude 필드)
- **중복 방지**: 동일 shortcode 재수집 시 Skip 확인

---

### 📞 연락처

기술적 문의나 버그 리포트는 개발팀에 연락해주세요.

**David Kwon** | Chief AI Officer

| 항목 | 정보 |
|------|------|
| Tel | +82-10-4395-3344 |
| Email | david.kwon@prideofmisfits.com |
| OFFICE | 1332, Gongdeok Building, 11, Saechang-ro, Mapo-gu, Seoul, Korea |
| STUDIO | A1019, Pine Square, 22, Magokjungang 4-ro, Gangseo-gu, Seoul, Korea |

---

*이 문서는 developer_log.html의 내용을 마크다운으로 정리한 것입니다.*
