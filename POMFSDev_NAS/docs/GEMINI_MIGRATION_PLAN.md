# Gemini 3 Pro 전환 계획 문서

> **문서 상태**: TBD (To Be Decided) - 검토 후 진행 예정  
> **작성일**: 2026-01-19  
> **작성자**: P.O.MFS AI Development Team

---

## 1. 개발 로드맵 배경

### 1.1 초기 개발 전략: Mistral API 선택

P.O.MFS 프로젝트는 **단계별 개발 전략**을 채택하여, 초기 개발 및 테스트 단계에서는 **Mistral API**를 선택했습니다.

#### Mistral API 선택 이유

| 요인 | 설명 |
|------|------|
| **비용 효율성** | 초기 개발 시 수백~수천 장의 이미지로 반복 테스트 필요. Mistral은 상대적으로 저렴한 API 비용으로 충분한 테스트 가능 |
| **빠른 프로토타이핑** | OCR과 LLM 분석을 별도 단계로 분리하여 각 단계별 디버깅 용이 |
| **API 안정성** | Mistral API는 안정적인 서비스 제공, Rate Limit(1 req/s)도 명확하여 설계 용이 |
| **테스트 데이터 축적** | 저비용으로 대량의 분석 결과 데이터를 축적하여 품질 기준 수립 |

#### 초기 파이프라인 구조 (현재)

```
[Instagram 포스터 이미지]
        │
        ▼
[Mistral OCR API] ──────────────── 텍스트 추출
        │
        ▼
[Mistral LLM API] ──────────────── 구조화된 정보 추출
        │                          (is_event_poster, event_name,
        │                           event_venue, event_date, etc.)
        ▼
[MusicFeedPlatform DB 저장]
```

### 1.2 고도화 전략: Gemini 3 Pro 전환

개발 로드맵 기획 시, **고도화 단계에서 Gemini Vision API로 전환**하여 이벤트 포스터의 복잡한 디자인/레이아웃/텍스트를 더 정확하게 분석하는 방향을 계획했습니다.

#### 전환 타이밍 기준

- 충분한 테스트 데이터 축적 완료 (수백 개 이상의 분석 결과)
- Mistral 분석의 한계점 파악 및 문서화
- 이벤트 포스터 판별 정확도 기준 수립
- Production 환경 안정화 후

---

## 2. P.O.MFS 프로젝트 현재 상황 vs 모델 특성

### 2.1 P.O.MFS 프로젝트 요구사항

| 요구사항 | 상세 |
|----------|------|
| **대상 이미지** | Instagram 이벤트 포스터 (음악 공연, DJ 파티, 클럽 이벤트 등) |
| **언어** | 한국어, 일본어, 영어 혼합 |
| **이미지 특성** | 다양한 디자인, 그라데이션 배경, 예술적 폰트, 복잡한 레이아웃 |
| **추출 정보** | 이벤트명, 장소, 날짜/시간, 아티스트, 티켓 가격, 입장료 등 |
| **판별 기능** | is_event_poster (이벤트 포스터 여부 판별) |
| **정확도 요구** | 높음 (잘못된 데이터가 Production DB에 저장되면 안 됨) |

### 2.2 모델 특성 비교

| 항목 | Mistral OCR + LLM | Gemini 3.0 Pro Vision |
|------|-------------------|----------------------|
| **기본 철학** | 문서 특화 OCR + 별도 LLM | 멀티모달 LLM (OCR + 이해 통합) |
| **파이프라인** | 2단계 (OCR → LLM) | 1단계 (원샷) |
| **인식 대상** | 스캔 문서, 표, 폼에 최적화 | UI, 소셜미디어 이미지에 강함 |
| **시각적 맥락** | 텍스트만 추출 | 디자인 + 텍스트 동시 이해 |
| **한국어/일본어** | 양호 | 더 안정적 |
| **벤치마크** | 일부 데이터셋에서 Gemini보다 낮은 정확도 | 인쇄 텍스트 OCR 98.2% (Flash 2.0 기준) |
| **비용** | 저렴 (테스트에 적합) | 중간 (Production에 적합) |

### 2.3 현재 Mistral 파이프라인의 한계

1. **2단계 처리의 정보 손실**: OCR에서 추출된 텍스트만 LLM에 전달되므로, 이미지의 시각적 맥락(레이아웃, 강조 표시, 디자인 요소) 손실
2. **복잡한 디자인 대응 어려움**: 예술적 폰트, 그라데이션 텍스트, 비정형 레이아웃에서 OCR 정확도 저하
3. **맥락 기반 판단 한계**: 텍스트만으로는 "이벤트 포스터인지" 판단하기 어려운 경우 존재

---

## 3. Gemini 3.0 Pro 추천 이유

### 3.1 P.O.MFS 요구사항과의 적합성

| P.O.MFS 요구사항 | Gemini 3.0 Pro 적합성 |
|-----------------|---------------------|
| Instagram 이벤트 포스터 분석 | ✅ 소셜미디어 이미지 OCR에 강함 |
| 한국어/일본어 혼합 텍스트 | ✅ 멀티모달 LLM으로 다국어 안정적 |
| 복잡한 디자인/레이아웃 | ✅ 시각적 맥락 + 텍스트 동시 이해 |
| OCR + 정보 추출 + 구조화 | ✅ 원샷 파이프라인 가능 |
| is_event_poster 판별 | ✅ 이미지 전체 이해 기반 판단 |
| 높은 정확도 요구 | ✅ Pro 모델의 추론 능력 우수 |

### 3.2 기대 효과

#### 파이프라인 단순화

**현재 (Mistral)**:
```
이미지 → OCR API → 텍스트 → LLM API → 구조화 데이터
        (1 req)           (1 req)
        = 2 API 호출
```

**전환 후 (Gemini Pro)**:
```
이미지 → Gemini Vision API → 구조화 데이터
                (1 req)
        = 1 API 호출
```

#### 주요 개선점

1. **정확도 향상**: 이미지 전체를 이해하고 텍스트를 추출하므로, 맥락 기반 정확한 정보 추출
2. **is_event_poster 판별 개선**: 텍스트뿐 아니라 디자인 요소(DJ 사진, 음악 관련 그래픽 등)도 고려
3. **API 호출 횟수 감소**: 2회 → 1회로 감소, 레이턴시 및 비용 효율화
4. **코드 단순화**: OCR + LLM 2단계 로직 → 단일 API 호출 로직

### 3.3 Gemini 3.0 Pro vs Flash 선택 이유

| 항목 | Gemini 3.0 Flash | Gemini 3.0 Pro |
|------|-----------------|----------------|
| 속도 | 매우 빠름 | 보통 |
| 정확도 | 양호 | 높음 |
| 복잡한 추론 | 보통 | 우수 |
| 비용 | 저렴 | 중간 |
| **P.O.MFS 적합성** | 대량 처리 시 | **품질 중시 시** ✅ |

**결론**: P.O.MFS는 잘못된 데이터가 Production DB에 저장되면 안 되므로, **정확도가 높은 Gemini 3.0 Pro** 선택

---

## 4. Gemini 3 Pro API 사용을 위한 준비사항

### 4.1 Google Cloud 설정 체크리스트

| # | 항목 | 상세 | 담당 | 상태 |
|---|------|------|------|------|
| 1 | Google Cloud 프로젝트 | Vertex AI 활성화된 프로젝트 | - | ✅ 이미 있음 |
| 2 | 결제 계정 | Vertex AI는 유료 서비스 | 사용자 | ⏳ 확인 필요 |
| 3 | Vertex AI API 활성화 | `aiplatform.googleapis.com` | 사용자 | ⏳ 확인 필요 |
| 4 | 서비스 계정 역할 | **Vertex AI User** 역할 추가 | 사용자 | ⏳ 필요 |

### 4.2 현재 사용 중인 Google Cloud 설정

P.O.MFS는 이미 GCS 업로드를 위해 Google Cloud 인증을 사용하고 있습니다:

| Secret | 용도 | 상태 |
|--------|------|------|
| `GOOGLE_CLOUD_PROJECT_ID` | 프로젝트 식별 | ✅ 설정됨 |
| `GOOGLE_CLOUD_CREDENTIALS` | 서비스 계정 JSON | ✅ 설정됨 |
| `GOOGLE_CLOUD_BUCKET_NAME` | GCS 버킷 | ✅ 설정됨 |

**추가 필요 작업**: 기존 서비스 계정에 **Vertex AI User** 역할 부여

### 4.3 Python 패키지 설치

```bash
pip install google-genai
```

> ⚠️ **주의**: 기존 `vertexai.generative_models` 모듈은 2025년 6월 deprecated, 2026년 6월 제거 예정  
> → **새 SDK `google-genai` 사용 권장**

### 4.4 코드 변경 범위 (analyzer.py)

| 변경 항목 | 현재 (Mistral) | 변경 후 (Gemini Pro) |
|----------|---------------|---------------------|
| API 클라이언트 | Mistral Client | Google Gen AI SDK |
| OCR 함수 | `extract_text_with_ocr()` | Gemini Vision API 호출 |
| LLM 분석 함수 | `analyze_with_llm()` | Gemini Pro 구조화 추출 |
| Rate Limiter | 1 req/s (Mistral) | Gemini 쿼터에 맞게 조정 |
| Fallback 로직 | regex 파싱 | 유지 (백업) |
| 응답 파싱 | Mistral JSON 형식 | Gemini JSON 형식 |

### 4.5 예상 비용 비교

| 모델 | 입력 (1M 토큰) | 출력 (1M 토큰) | 비고 |
|------|---------------|---------------|------|
| Mistral Large | ~$2 | ~$6 | 2 API 호출 필요 |
| **Gemini 3 Pro** | ~$1.25 | ~$5 | 1 API 호출 |
| Gemini 2.5 Flash | ~$0.075 | ~$0.30 | 정확도 다소 낮음 |

> **참고**: 이미지 분석은 토큰 수 계산 방식이 다르므로 실제 비용은 테스트 후 확정

---

## 5. 전환 작업 계획 (TBD)

### 5.1 작업 단계

| 단계 | 작업 | 상태 |
|------|------|------|
| 1 | Google Cloud 설정 확인 (Vertex AI API, 서비스 계정 역할) | ⏳ 대기 |
| 2 | `google-genai` 패키지 설치 | ⏳ 대기 |
| 3 | `analyzer.py` 수정 승인 | ⏳ **승인 필요** |
| 4 | Gemini Vision API 연동 코드 작성 | ⏳ 대기 |
| 5 | 테스트 이미지로 검증 (정확도, 비용) | ⏳ 대기 |
| 6 | Production 전환 | ⏳ 대기 |

### 5.2 승인 필요 항목

- [ ] Google Cloud Vertex AI API 활성화 확인
- [ ] 서비스 계정에 Vertex AI User 역할 추가
- [ ] `analyzer.py` 수정 승인 (수정 금지 파일 목록에 포함)
- [ ] 테스트 후 Production 전환 승인

---

## 6. 참고 자료

- [Vertex AI Gemini Quickstart](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart)
- [Google Gen AI SDK 문서](https://googleapis.github.io/python-genai/)
- [Gemini 3 시작 가이드](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/get-started-with-gemini-3)
- [Mistral vs Gemini OCR 비교](https://reducto.ai/blog/lvm-ocr-accuracy-mistral-gemini)

---

## 7. 문서 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-01-19 | v1.0 | 초안 작성 |

---

> **다음 단계**: 이 문서 검토 후 승인 시 작업 진행 예정
