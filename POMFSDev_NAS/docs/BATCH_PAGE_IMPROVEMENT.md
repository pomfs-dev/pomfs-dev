# 배치 수집 페이지 개선 기획안

## 개요
batch_collection 페이지에서 발생하는 두 가지 문제를 해결하기 위한 기획안입니다.

---

## 문제 1: 페이지 기반 수집 (현재 페이지 계정만 처리)

### 현재 상태
```
accountsData = [전체 500개 계정]
processAllOnPage() → accountsData[0]부터 시작 (항상 1번째)
```
- 2페이지에서 수집을 시작해도 항상 1페이지(1~50번)부터 수집됨

### 목표 상태
```
2페이지에서 수집 시작 → accountsData[50~99]만 처리
3페이지에서 수집 시작 → accountsData[100~149]만 처리
```

### 필요한 수정

| 파일 | 수정 내용 |
|------|----------|
| `batch_collection.html` | `processAllOnPage()`에서 현재 페이지 번호 읽어서 시작 인덱스 계산 |
| `batch_collection.html` | 페이지네이션 상태 변수 추가 (`currentPage`, `itemsPerPage`) |

### 구현 방식
```javascript
// 현재 페이지 기준 시작/끝 인덱스 계산
const startIndex = (currentPage - 1) * itemsPerPage;  // 2페이지 → 50
const endIndex = Math.min(startIndex + itemsPerPage, accountsData.length);  // → 99

// 해당 범위만 처리
for (let i = startIndex; i < endIndex; i++) {
    await processSingle(accountsData[i].username, i);
}
```

---

## 문제 2: 수집 상태 유지 (페이지 이동 후 복원)

### 현재 상태
```
수집 중 → 다른 페이지 이동 → 돌아옴 → 상태 초기화됨
TASK_STORE는 서버에 있지만, 페이지 로드 시 확인 안함
```

### 목표 상태
```
수집 중 → 다른 페이지 이동 → 돌아옴 → "수집 중" 상태 표시 + 진행률 복원
```

### 필요한 수정

| 파일 | 수정 내용 |
|------|----------|
| `app.py` | 배치 세션 저장 API 추가 (`/api/batch_session`) |
| `app.py` | 진행 중인 배치 조회 API 추가 (`/api/batch_session/active`) |
| `batch_collection.html` | 페이지 로드 시 진행 중인 배치 확인 |
| `batch_collection.html` | 진행 중이면 UI 상태 복원 (진행률 바, 로그 등) |

### 서버 저장 데이터 구조
```python
BATCH_SESSION = {
    'session_id': 'uuid',
    'status': 'running',  # running, completed, stopped
    'start_page': 2,
    'accounts': ['account1', 'account2', ...],  # 처리 대상
    'completed': ['account1'],  # 완료된 계정
    'current_index': 5,
    'started_at': '2026-01-19T13:00:00',
    'task_ids': ['task-uuid-1', 'task-uuid-2', ...]  # 진행 중인 task ID들
}
```

### 페이지 로드 시 복원 로직
```javascript
window.onload = async function() {
    const session = await fetch('/api/batch_session/active').then(r => r.json());
    
    if (session && session.status === 'running') {
        // 진행 중인 작업 있음
        showProgressDashboard();
        restoreProgress(session);
        resumePolling(session.task_ids);
    }
};
```

---

## 구현 순서 및 상태

| 순서 | 작업 | 난이도 | 상태 |
|------|------|--------|------|
| 1 | 페이지네이션 상태 변수 추가 | 낮음 | ✅ 완료 |
| 2 | `startAutoCollect()` 수정 - 현재 페이지부터 처리 | 중간 | ✅ 완료 |
| 3 | 배치 세션 저장/조회 API 추가 (`app.py`) | 중간 | ✅ 완료 |
| 4 | 페이지 로드 시 세션 확인 로직 추가 | 중간 | ✅ 완료 |
| 5 | UI 상태 복원 로직 구현 | 중간 | ✅ 완료 |
| 6 | task_id 즉시 등록 | 중간 | ✅ 완료 |
| 7 | completed_count 정확한 업데이트 | 중간 | ✅ 완료 |
| 8 | localStorage 기반 진행 중 task 저장 | 중간 | ✅ 완료 |
| 9 | 행 UI 복원 (진행률 바, 타이머, 상태 표시) | 중간 | ✅ 완료 |
| 10 | 중복 카운팅 방지 | 낮음 | ✅ 완료 |

**구현 완료일: 2026-01-19**

---

## 고려사항 및 제한사항

### 1. 메모리 저장 한계
- 현재 `BATCH_SESSION`은 메모리에 저장되므로, 서버 재시작 시 상태 손실
- 해결: 필요 시 DB 저장 (현재는 메모리로 충분)
- **현재 상태**: 구현 완료 (메모리 저장)

### 2. 동시 배치 제한
- 한 번에 하나의 배치만 실행 가능하도록 제한
- 여러 배치 동시 실행 시 리소스 충돌 가능
- **현재 상태**: 구현 완료 (단일 세션만 허용)

### 3. 페이지 이동 시 자동 polling 재개
- 돌아왔을 때 진행 중인 task들의 상태를 다시 polling 시작
- **현재 상태**: 구현 완료 (checkActiveSession 함수)

### 4. 브라우저 새로고침 처리
- F5 또는 새로고침 시에도 상태 복원됨
- **현재 상태**: 구현 완료

### 5. 동시성(Concurrency) 관련 제한
- 동시 작업(concurrency > 1) 시 completed_count가 레이스 컨디션으로 부정확할 수 있음
- **해결책**: 서버 측 원자적 카운터 또는 순차적 업데이트 필요
- **현재 상태**: 알려진 제한사항 (향후 개선 예정)

---

## localStorage 기반 진행 중 task 세션 유지 (2026-01-19 추가)

### 개요
페이지 이동 후 돌아왔을 때 진행 중인 작업의 행 UI(진행률 바, 상태 텍스트, 타이머)를 복원하는 기능입니다.

### 저장 데이터 구조
```javascript
// localStorage key: 'batchRunningTasks'
{
    "task-uuid-1": {
        "taskId": "task-uuid-1",
        "username": "clubexample",
        "globalIndex": 5,
        "rowIndex": 5,
        "startTime": 1705672800000  // Date.now() 시작 시점
    },
    "task-uuid-2": { ... }
}
```

### 핵심 함수

| 함수명 | 설명 |
|--------|------|
| `saveRunningTask(taskId, username, globalIndex, rowIndex)` | 작업 시작 시 localStorage에 저장 |
| `removeRunningTask(taskId)` | 작업 완료/오류 시 localStorage에서 제거 |
| `getRunningTasks()` | 현재 진행 중인 모든 task 조회 |
| `clearAllRunningTasks()` | 배치 완료 시 모든 task 정보 삭제 |

### 복원 로직

1. 페이지 로드 시 `checkActiveSession()` 호출
2. localStorage에서 진행 중인 task 목록 조회
3. 각 task에 대해:
   - 행 UI 초기화 (진행률 바 활성화, 스피너 표시)
   - `pollTaskStatusWithRowUI()` 호출하여 폴링 재개
   - 저장된 `startTime`으로 경과 시간 계산

### 타이머 업데이트 개선
- 로그 없이도 매 폴링마다 경과 시간 업데이트
- `rowStatusText`에 `처리중 50% (25s)` 형식으로 표시

### 중복 카운팅 방지
- 복원된 작업에서 `globalCompletedTasks++` 제거
- 서버 세션의 `completed_count`를 신뢰하여 진행률 계산
- 페이지 로드 시 `globalCompletedTasks = session.completed_count`로 초기화

---

## API 명세

### POST /api/batch_session
배치 세션 시작/업데이트

**Request:**
```json
{
    "action": "start",  // start, update, stop
    "page": 2,
    "accounts": ["account1", "account2"]
}
```

**Response:**
```json
{
    "success": true,
    "session_id": "uuid"
}
```

### GET /api/batch_session/active
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
    "task_ids": ["task-1", "task-2"]
}
```

**Response (없음):**
```json
{
    "active": false
}
```

---

## 작성일
2026-01-19

## 관련 파일
- `templates/batch_collection.html`
- `app.py` (TASK_STORE, auto_process_async)
