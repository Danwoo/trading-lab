# Backend Anti-Patterns

작업 중 위반 회피, review 시 위반 검출의 **단일 진실의 원천 (SoT)**.

## 이 파일의 역할

- **평상시 작업 (Claude 메인)**: 작업 중 패턴 위반 회피용. 각 backend 폴더 (`app/main.py` 가 있는 폴더 — `backend/` / `etl-pipeline/` / `daemon-service/` 등 서비스별) 의 `CLAUDE.md` 체크리스트에서 룰 번호로 점프해 상세 확인.
- **review-backend 에이전트**: 모든 룰을 1번부터 순차 실행. 각 룰의 `**Detection**` 박스 명령 그대로 실행 → 후보 Read → `**예외**` 인용 후 분류 (위반/의심/통과).
- **scaffold-backend 에이전트**: 코드 생성 시 이 docs + [`design-patterns-backend.md`](design-patterns-backend.md) 따르면 자동 회피.

## 각 룰의 4섹션 구조 (모두 통일)

1. **예시** — ❌ 위반 / ✅ 올바른 패턴 (코드 블록)
2. **룰** — 한 줄 statement (굵게 시작)
3. **Detection** — review-backend 가 실행하는 grep 명령 + 0 hit / 1+ hit 후처리 안내
4. **예외** — Phase B 판정 시 반드시 인용. 단일 예외는 한 줄, 다중은 bullet list, 예외 없으면 `**예외**: 없음 (이유)`

## 헤더 일치 규칙

`### N. {룰명}` 헤더의 **번호와 텍스트는 review-backend.md 출력 표 + backend `CLAUDE.md` 공통부의 체크리스트와 정확히 동일**. 룰 추가/삭제 시 3곳 동시 갱신 필수. 공통부는 전 backend 서비스가 byte-identical 이라 한 벌만 고치면 되고(정본 `backend-service/CLAUDE.md`), 전 서비스 반영 여부는 `scripts/verify_backend_claude_md.py` 가 검사한다.

## Placeholder

`{backend}` 는 `app/main.py` 가 있는 폴더 (예: `backend/`, `api/`). 프로젝트마다 여러 개 가능 — review 에이전트가 디스커버리로 찾아서 치환.

## Pathspec — `:(glob)` 를 붙인 채로 실행한다

Detection 의 pathspec 은 전부 `':(glob)...'` 로 시작한다. **이 접두를 떼면 같은 글자가 다른 뜻이 된다** — git 기본 매직에서는 `*` 가 `/` 를 넘고 `**/` 는 「디렉터리가 한 단계 이상」이 되어 **깊이 1 파일이 통째로 빠진다**. `':(glob)'` 아래에서만 `*` 가 한 세그먼트 안에 머물고 `/**/` 가 「0개 이상의 디렉터리」로 읽힌다.

```bash
git ls-files 'backend-service/app/**/*.py'         | wc -l   # 127 — main.py·modules.py 가 없다 (pathspec-check: 반례)
git ls-files ':(glob)backend-service/app/**/*.py'  | wc -l   # 129
```

접두가 빠지거나 pathspec 이 한 파일도 못 맞히면 `scripts/verify_detection_pathspec.py` 가 실패한다.

## 목차

**레이어 분리**
- [1. Router 에 비즈니스 로직 / SQL](#1-router-에-비즈니스-로직--sql)
- [2. Repository 의 비즈니스 디폴트/검증](#2-repository-의-비즈니스-디폴트검증)
- [3. 반환값 안 쓰는 self.select_X 호출](#3-반환값-안-쓰는-selfselect_x-호출)

**데이터베이스 / 스키마**
- [4. ORM Session/Model/query runtime 사용](#4-orm-sessionmodelquery-runtime-사용)
- [5. 공통 감사 컬럼 누락](#5-공통-감사-컬럼-누락)
- [6. 페이지네이션 누락](#6-페이지네이션-누락)

**응답 / 인증 / 에러**
- [7. Pydantic Response 모델 / list wrapper 누락](#7-pydantic-response-모델--list-wrapper-누락)
- [8. 인증 누락](#8-인증-누락)
- [9. catch-all try/except Exception (handler 우회)](#9-catch-all-tryexcept-exception-handler-우회)
- [10. fastapi.HTTPException 직접 raise (Service/Repository)](#10-fastapihttpexception-직접-raise-servicerepository)

**DI / I/O**
- [11. DI 우회 (직접 인스턴스화)](#11-di-우회-직접-인스턴스화)
- [12. DB I/O 패턴 (sync 표준)](#12-db-io-패턴-sync-표준)
- [13. async 컨텍스트에서 sync blocking → run_in_threadpool 누락](#13-async-컨텍스트에서-sync-blocking--run_in_threadpool-누락)

**모듈 경계**
- [14. 모듈 경계 침범](#14-모듈-경계-침범)
- [15. provider 경계 침범 (소스 이름 누출)](#15-provider-경계-침범-소스-이름-누출)

---

## 레이어 분리

### 1. Router 에 비즈니스 로직 / SQL

```python
# ❌ — SQL 직접 + 사전 check 까지 router 가 수행
@router.get("/{id}")
async def get_user(id: int, conn = Depends(...)):
    result = await conn.execute(text("SELECT ..."))
    if not result.first():
        raise HTTPException(404)

# ✅ — service 위임만. 존재 검증/도메인 예외는 service 책임
@router.get("/{id}", response_model=UserOut)
async def get_user(id: int, user_service: UserService = Depends(...)):
    return user_service.select_user({"id": id})  # 미존재 시 service 가 NotFoundError raise
```

**룰**: Router 는 controller 역할. SQL 직접 작성 / Repository 직접 호출 / 도메인 규칙 / 사전 exist 체크 후 도메인 예외 raise / 트랜잭션 일관성 필요한 다단 비즈니스 흐름 → 전부 service 위임.

**Detection**:
```bash
git grep --untracked -nE 'conn\.execute|\btext\(|raw_connection' -- ':(glob){backend}/app/routers/**/*.py'
```
0 hit → SQL 직접 사용 측면 통과. 1+ hit → 각 후보 Read 후 아래 분류 적용.

router 파일 Read 시 다음만 위반으로 판정 (controller 정상 역할은 통과):

❌ **금지 (Router 안에 두면 안 되는 것)**:
- SQL 쿼리 직접 작성 / Repository 직접 호출 (Service 우회)
- **도메인 규칙** 을 router 안에 박기 — 예: "HWP 파일은 Upstage 필수" 같은 도메인 지식
- 사전 exist/null 체크 후 도메인 예외 raise — service 책임
- 트랜잭션 일관성이 필요한 **다단 비즈니스 흐름** — service 가 하나의 단위로 책임

✅ **허용 (controller 정상 역할)**:
- 여러 service 호출 + 결과 조합 / 변환 / 다음 service 에 전달
- HTTP-level 입력 검증 (filename / JSON parse / size 등 format-level)
- HTTP-level 분기 (`if auto_sync: trigger background`)
- 병렬 호출 / 결과 집계 (`asyncio.gather` + aggregation)
- Permission service 호출 후 결과 사용

**예외**: 위의 ✅ 항목들이 통과 케이스. HTTP status 변환은 `core/exception_handler.py` 가 일괄 처리하므로 Router 의 `raise HTTPException` 은 룰 10 허용 케이스에만 한정.

### 2. Repository 의 비즈니스 디폴트/검증

```python
# ❌ — Repository 가 Pydantic schema (is_active=True) 와 다른 디폴트로 덮어쓰기
def insert_X(self, args):
    params = {"is_active": args.get("is_active", 0), ...}  # Pydantic 은 True
    conn.execute(text(sql), params)

# ✅ — args 직접 전달, 디폴트는 Pydantic schema / Service 책임
def insert_X(self, args):
    conn.execute(text(sql), args)
```

**룰**: Repository = thin SQL wrapper (실행만). 디폴트값/검증은 Pydantic schema 또는 Service 책임.

**Detection**:
```bash
git grep --untracked -nE '^\s*params\s*=\s*\{' -- ':(glob){backend}/app/repositories/**/*.py'
```
0 hit → 통과. 1+ hit → Read 후 `args.get(..., default)` 같이 Pydantic 디폴트 덮어쓰는지 검사.

**예외**: 없음 (Pydantic 디폴트와 다른 값 덮어쓰기는 모두 위반). 단순 `params = {}` 또는 SQL bind 변수 이름 매핑용 dict 구성은 위반 아님.

### 3. 반환값 안 쓰는 self.select_X 호출

```python
# ❌ — raise 부수효과만 의존, 의도 불명확
def update_X(self, args):
    self.select_X({"id": args["id"]})  # 반환값 미사용
    self.X_repository.update_X(args)

# ✅ — repository 직접 호출 + 도메인 예외 raise
def update_X(self, args):
    if not self.X_repository.select_X({"id": args["id"]}):
        raise NotFoundError("데이터를 찾을 수 없습니다.")
    self.X_repository.update_X(args)
```

**룰**: Service 내부 존재 검증은 `repository.select_X()` 결과를 명시적으로 체크 + 도메인 예외 (`NotFoundError`, `ConflictError`) raise. `HTTPException` 직접 사용 금지 — handler 가 status 매핑 처리.

**Detection**:
```bash
git grep --untracked -nE '^\s*(await\s+)?self\.select_\w+\(' -- ':(glob){backend}/app/services/**/*.py'
```
0 hit → 통과. 1+ hit → Read 후 반환값 미할당이면 위반 (sync `self.select_X(...)` / async `await self.select_X(...)` 둘 다 대상).

**예외**: 다른 Service 의 `select_X` 호출 (cross-service) 은 layer 경계 보호 차원에서 raise 의존 OK.

---

## 데이터베이스 / 스키마

### 4. ORM Session/Model/query runtime 사용

```python
# ❌ — runtime 에 ORM query 호출
from sqlalchemy.orm import Session
db.query(User).filter(...).all()
session.add(user); session.commit()

# ✅ — Core text() + 결과 매핑
from sqlalchemy import text
with self.sql_client.connect() as conn:
    result = conn.execute(text("SELECT * FROM TN_USER WHERE ...")).mappings().all()
```

**룰**: Runtime 에서 `Session.query()` / `session.add()` / `session.commit()` 등 ORM API 호출 금지. Repository 는 Core (`text()` + `.mappings()`) only.

**Detection**:
```bash
git grep --untracked -nE 'db\.query\(|session\.(add|commit|merge|delete|flush|refresh|rollback)\(' -- ':(glob){backend}/app/**/*.py'
```
0 hit → 통과. 1+ hit → 모두 위반.

**예외**: `models/schema.py` 의 `DeclarativeBase` 모델 정의는 schema push (마이그레이션) 용도로 정상 패턴. 룰 대상은 **실행되는 ORM 쿼리** 만 (정의에는 위 토큰이 안 나와서 자연 매치 안 됨).

### 5. 공통 감사 컬럼 누락

```sql
-- ❌
INSERT INTO TN_X (..., reg_dt) VALUES (..., CURRENT_TIMESTAMP)
UPDATE TN_X SET ..., mod_dt = CURRENT_TIMESTAMP WHERE id = :id

-- ✅
INSERT INTO TN_X (..., reg_id, reg_dt, mod_id, mod_dt)
       VALUES (..., :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP)
UPDATE TN_X SET ..., mod_id = :mod_id, mod_dt = CURRENT_TIMESTAMP WHERE id = :id
```

**룰**: INSERT 시 `reg_dt` + `reg_id` 누락 금지. UPDATE 시 `mod_dt` + `mod_id` 누락 금지.

**Detection** (negative-pattern 📍 — hit 자체는 정상, Read 후 누락 검사가 본질):
```bash
git grep --untracked -lE 'INSERT\s+INTO\s+\w+|UPDATE\s+\w+\s+SET' -- ':(glob){backend}/app/repositories/**/*.py'
```
hit = 후보 파일 목록. 각 파일 Read 후 INSERT/UPDATE 마다 컬럼 포함 여부 검사.

**source-of-truth 조회 순서** (위반 판정 시):
1. `{backend}/app/models/schema.py` 의 해당 테이블 `Mapped` 컬럼 확인
2. 없으면 `frontend/prisma/schema.prisma` 의 model 확인
3. 양쪽 모두 정의 안 됨이면 의도된 설계 (위반 아님)

**예외**:
- **Background-only update** (router 경로 없이 background 작업에서만 호출): SQL 에 `mod_id = 'system'` 하드코딩 허용. Service 단에서 인자 전달 불필요.
- 스키마 양쪽 모두 컬럼 정의 안 됨 → 의도된 설계, 위반 아님.
- **대용량 시계열 테이블** (캔들·틱 등 행 수가 수백만 단위로 늘어나는 적재 테이블): 감사 컬럼 4종을 두지 않는다. 행당 비용이 데이터 자체와 맞먹고, `source`·`ingest_run_id` 같은 적재 출처 컬럼이 더 정확한 provenance 를 준다. 이 예외는 위 source-of-truth 조회 순서의 3번(스키마 양쪽 모두 정의 안 됨)에 해당하는 의도된 설계다.

### 6. 페이지네이션 누락

```python
# ❌ — 필터/skip/take 무시한 전체 SELECT
SELECT * FROM TN_X

# ✅ — ROW_NUMBER() + skip/take
SELECT * FROM (
  SELECT ROW_NUMBER() OVER (ORDER BY ...) AS rn, TB.* FROM (...) TB
) WHERE rn BETWEEN :skip + 1 AND :skip + :take
```

**룰**: DevExtreme 그리드 데이터 반환 시 반드시 `ROW_NUMBER()` + `skip`/`take`.

**Detection** (negative-pattern 📍):
```bash
git grep --untracked -nE 'def\s+select_\w+_list\(' -- ':(glob){backend}/app/repositories/**/*.py'
```
hit = list 반환 메서드. 각 함수 Read 후 `ROW_NUMBER()` + `:skip` + `:take` 포함 여부 검사. 누락 시 위반.

**예외**: 작은 고정 리스트 — 행 수가 본질적으로 제한된 케이스 (예: `select_file_detail_list({atch_file_id})` — 한 첨부파일 묶음의 file detail). "작은" 의 기준은 보통 수십 건 이내, 비즈니스 규칙상 폭증 불가능한 경우.

---

## 응답 / 인증 / 에러

### 7. Pydantic Response 모델 / list wrapper 누락

```python
# ❌ — response_model 누락
@router.get("/{id}")
async def get_user(id: int) -> dict: ...

# ❌ — list[T] 직접 (단일 객체 BaseModel 아님)
@router.get("", response_model=list[SampleOut])
async def list_samples(...) -> list[SampleOut]: ...

# ✅ — wrapper BaseModel 정의
class SamplesOut(BaseModel):
    items: list[SampleOut]
    total_count: int

@router.get("", response_model=SamplesOut)
async def list_samples(...) -> SamplesOut:
    return SamplesOut(items=items, total_count=total)
```

**룰**:
- 모든 endpoint 에 `response_model=` 명시
- list 응답은 `{ items, total_count }` wrapper BaseModel — `list[T]` 직접 사용 금지 (페이지 메타 못 담음, DevExtreme `{ data, totalCount }` 형식 매핑 불가)

**Detection** (negative-pattern 📍):
```bash
git grep --untracked -nE '@router\.(get|post|put|delete|patch)' -- ':(glob){backend}/app/routers/**/*.py'
```
hit = endpoint 모음. 각 endpoint Read 후 `response_model=` 명시 + list 응답 wrapper 여부 검사.

**예외**:
- `StreamingResponse` / `FileResponse` / `Response(content=bytes)` 등 binary 응답은 `response_class=` 사용 (response_model 대신).

### 8. 인증 누락

```python
# ❌ — 인증 없는 endpoint (마이페이지/시스템 외 모든 비즈니스 router)
@router.get(...)
async def secret_data(...): ...

# ✅ — Router 레벨 또는 endpoint 레벨에 verify_access_token
router = APIRouter(dependencies=[Depends(verify_access_token)])
# 또는
@router.get(..., dependencies=[Depends(verify_access_token)])
```

**룰**: 비즈니스 router 는 router 레벨 또는 endpoint 레벨에 `Depends(verify_access_token)` 필수.

**Detection** (negative-pattern 📍):
```bash
git grep --untracked -nE 'APIRouter\(|@router\.(get|post|put|delete|patch)' -- ':(glob){backend}/app/routers/**/*.py'
```
hit = router/endpoint 모음. 각 router 파일 Read 후 인증 dependency 존재 여부 검사.

**예외**:
- 마이페이지 / 시스템 외부 노출 router (로그인, 회원가입, 공개 API 등) 는 의도된 미인증 — 위반 아님.

### 9. catch-all try/except Exception (handler 우회)

```python
# ❌ — catch-all 로 모든 예외 500 변환. 도메인 예외 (NotFoundError 등) 가 500 으로 silent 변환
def delete_X(self, args):
    try:
        x = self.X_repository.select_X(args)
        if not x:
            raise NotFoundError("...")
        self.X_repository.delete_X(args)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # NotFoundError → 500 BUG

# ✅ — try/except 없음. 도메인/표준 예외 그대로 전파, handler 가 status 매핑
def delete_X(self, args):
    if not self.X_repository.select_X(args):
        raise NotFoundError("데이터를 찾을 수 없습니다.")
    self.X_repository.delete_X(args)
```

**룰**: Repository / Service / Router 모두 `try/except Exception` 형태 금지. 예외는 자연 전파시키고 `core/exception_handler.py` 가 도메인 예외 (`NotFoundError`→404, `ConflictError`→409) / 표준 예외 (`ValueError`→400, `PermissionError`→403, `ConnectionError`→503) / 그 외 (`Exception`→500) 로 일괄 변환.

**Detection**:
```bash
git grep --untracked -nE 'except\s+Exception' -- ':(glob){backend}/app/**/*.py'
```
0 hit → 통과. 1+ hit → Read 후 block 안에서 `raise HTTPException(...)` 변환 또는 silent swallow 시 위반.

**예외**: catch-all 이어도 정당한 케이스 ↓
- **Resource cleanup**: I/O 리소스 (connection / file / lock 등) lifecycle 정리의 `try/finally` 또는 best-effort cleanup. 원본 예외 마스킹하지 않는 형태.
  - 판정 완료 ([#330](https://github.com/Danwoo/trading-lab/issues/330)): `backend-service/app/main.py` 의 `_stop_managers()` · `_dispose_sql_client()` · `lifespan` 의 매니저 start 롤백 3건이 여기 해당한다 — 정리만 하고 원본 예외를 `raise` 로 그대로 올린다. 매번 다시 판정하지 않는다.
- **Daemon loop continuation**: 무한 루프 / 백그라운드 worker 의 iteration 격리 (`log + back-off + continue`). 한 회차 실패가 전체 worker 종료 막아야 할 때.
- **Bulk skip-and-continue**: 일괄 처리에서 항목별 실패 격리. 일부 실패해도 나머지 진행이 의도된 설계.
- **Router 의 client-disconnect → `HTTPException(499)`**: `except asyncio.CancelledError` 변환, 또는 endpoint 진입 시 `if await request.is_disconnected(): raise HTTPException(499)` 사전 체크.
- **Logging handler emit()**: Python `logging.Handler.emit()` 는 예외를 던지면 logging 시스템이 무한 recursion. 표준 규약상 `except Exception: pass` (또는 `self.handleError(record)`) 만 허용.
- **외부 라이브러리 예외 → 표준/도메인 예외 통일 변환**: `raise X(...) from e` 로 chain 보존하면서 광역 catch (asyncssh, mlflow 등 specific 예외 종류가 너무 많아 enumerate 비실용적인 경우).

Specific 예외 (`except FooError`) 는 룰 대상 아님 (catch-all 아니므로 자연 통과).

### 10. fastapi.HTTPException 직접 raise (Service/Repository)

```python
# ❌ — Service / Repository 에서 HTTPException 직접 raise (handler 우회)
from fastapi import HTTPException, status

def select_X(self, args):
    item = self.X_repository.select_X(args)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="...")
    return item

# ✅ — 도메인 예외 사용. handler 가 status 매핑
from core.exceptions import NotFoundError

def select_X(self, args):
    item = self.X_repository.select_X(args)
    if not item:
        raise NotFoundError("데이터를 찾을 수 없습니다.")
    return item
```

**룰**: Service / Repository 는 `fastapi.HTTPException` import / raise 금지 (HTTP-free 유지 — background task / unit test 안전성). `core/exceptions.py` 도메인 예외 (`NotFoundError`, `ConflictError`) 또는 Python 표준 예외 (`ValueError`, `PermissionError`, `ConnectionError`, `RuntimeError`) 사용. 선택 가이드는 `design-patterns-backend.md` 의 "예외 선택 가이드" 참조.

**Detection**:
```bash
git grep --untracked -nE 'from\s+fastapi\s+import.*HTTPException|HTTPException\(' -- ':(glob){backend}/app/services/**/*.py' ':(glob){backend}/app/repositories/**/*.py'
```
0 hit → Service/Repository 측면 통과 (Router 는 grep 대상 외 — HTTP 경계라 자연스러움). 1+ hit (Service/Repository) → 위반.

**예외**: Router 의 HTTPException 허용 케이스 (Router 는 grep 대상 외지만 참고) ↓
- **client-disconnect** → `HTTPException(499)`: `except asyncio.CancelledError` 변환 또는 `request.is_disconnected()` 사전 체크.
- **구조화 detail (dict) 응답**: frontend 가 status code 외 추가 분류 필드 (`error_code` 등) 로 UX 차등 처리 시. 도메인 예외의 `str(exc)` 로는 dict 표현 불가. 예: `raise HTTPException(status_code=410, detail={"message": "공유 만료됨", "error_code": "expired"})`
- **Response shaping**: binary stream 등 status 가 응답 시작 전 결정되어야 하는 케이스. 예: 이미지 파일 미존재 → `HTTPException(404, "썸네일 파일이 없습니다.")`

도메인/표준 예외로 충분한 케이스 (예: "데이터 찾을 수 없음" → `NotFoundError`, "입력 잘못" → `ValueError`) 에 Router 에서 HTTPException 쓰는 건 부자연.

---

## DI / I/O

### 11. DI 우회 (직접 인스턴스화)

```python
# ❌
service = UserService(repo=UserRepository(sql_client))

# ✅
@inject
async def endpoint(
    service: UserService = Depends(Provide[Container.user_service])
): ...
```

**룰**: 새 Service/Repository 추가 시 반드시 `core/container.py` 등록 + `main.py` wire.

**Detection**:
```bash
git grep --untracked -nE '=\s*\w+(Service|Repository)\(' -- ':(glob){backend}/app/**/*.py' \
  | grep -v 'core/container.py' \
  | grep -vE 'Depends\(|Provide\['
```
0 hit → 통과. 1+ hit → Service/Repository 직접 인스턴스화 위반.

**예외**: `core/container.py` 는 정상 (provider 등록 자체). `Depends(...)` / `Provide[...]` 를 통한 주입도 정상.

### 12. DB I/O 패턴 (sync 표준)

```python
# ❌ — async DB 메서드 (동기 Engine 이라 async 로 감싸도 blocking)
async def select_user(self, args):
    async with self.sql_client.connect() as conn:
        result = await conn.execute(text("SELECT ..."))

# ✅ — sync def + engine.connect()
def select_user(self, args):
    with self.sql_client.connect() as conn:
        return conn.execute(text("SELECT ..."), args).mappings().first()
```

**룰**: 업무 DB 접근이 SQLAlchemy 동기 Engine (PostgreSQL + psycopg) 기반이라 Service/Repository 의 DB 메서드는 **sync `def` + `engine.connect()` 가 표준 패턴**.

HTTP/파일 외부 I/O 는 async 가 기본 (`httpx.AsyncClient`, `asyncssh` 등). `urllib.parse` (`quote`, `urlencode` 등) 는 string utility 라 자유 사용.

**Detection**:
```bash
git grep --untracked -nE '^\s*async\s+def\s+(select|insert|update|delete)_' -- ':(glob){backend}/app/repositories/**/*.py'
```
0 hit → 통과. 1+ hit → repository DB 메서드는 sync `def` 가 표준이므로 위반.

**예외**: 프로젝트별 정책에 따라 async driver (asyncpg, aiomysql 등) 채택 시는 의심으로만 분류. sync 사용 (예: `requests`, `httpx.Client`) 은 외부 I/O 룰 대상이지 본 룰 대상 아님 — review 시 의심 정도로만 표시.

### 13. async 컨텍스트에서 sync blocking → run_in_threadpool 누락

```python
# ❌ — async background task 안에서 heavy 동기 호출 → 이벤트 루프 블록 (다른 모든 요청 지연)
async def _process_dataset_background(self, data_id: int, recipe_id: str):
    df = self.rawdata_service.build_recipe_dataframe(...)         # heavy join (DB 측 sync, 초 단위)
    for col in columns_info:                                       # N+1 sync DB
        self.dataset_repository.insert_dataset_column(col)

# ❌ — asyncio.to_thread / loop.run_in_executor(None, ...) 도 금지 (asyncio 기본 executor → FastAPI AnyIO 풀과 분리: 스레드 예산 이원화, run_in_executor(None)은 ContextVar 미복사)
df = await asyncio.to_thread(self.rawdata_service.build_recipe_dataframe, ...)
df = await asyncio.get_running_loop().run_in_executor(None, self.rawdata_service.build_recipe_dataframe, ...)

# ✅ — fastapi.concurrency.run_in_threadpool (AnyIO 풀 공유: sync def handler / sync Depends / BackgroundTasks 와 동일)
from fastapi.concurrency import run_in_threadpool

async def _process_dataset_background(self, data_id: int, recipe_id: str):
    df = await run_in_threadpool(self.rawdata_service.build_recipe_dataframe, ...)

    def _insert_columns():                                          # 루프 통째로 wrap
        for col in columns_info:
            self.dataset_repository.insert_dataset_column(col)
    await run_in_threadpool(_insert_columns)
```

**룰**: `async def` 안에서 sync blocking 호출 (sync DB / CPU 작업) 시 `fastapi.concurrency.run_in_threadpool` 로 wrap. `asyncio.to_thread`·`loop.run_in_executor(None, ...)` 금지 (둘 다 asyncio 기본 executor → FastAPI AnyIO 풀과 분리). 통일 기준은 "스레드냐 프로세스냐" — CPU 바운드를 GIL 밖으로 빼는 `run_in_executor(ProcessPoolExecutor, ...)` 만 정당한 예외. **단, critical path 만 적용** — 단일 5ms sync DB op 까지 wrap 하지 말 것 (오버헤드 100-200µs, 가성비 ↓ + 코드 노이즈).

**wrap 대상 (critical path 3가지)**:
1. **Heavy CPU** — pandas/numpy 무거운 연산 (`build_recipe_dataframe`, `StatisticsUtils.calculate_*`, `ImageTransformer.transform`, `crop_images_from_pdf`, `image_preprocessing_stage*`, `extract_text` 등 ms-단위+ CPU 작업)
2. **N+1 sync DB loop** — `for ...: repo.insert_X()` / `for ...: repo.update_X()` 같이 N 회 누적 (column insert × 100 등). 루프 함수 통째로 wrap (`def _do(): for ...; await run_in_threadpool(_do)`)
3. **Polling loop with sync DB** — `while elapsed < max: repo.select_X(); await asyncio.sleep(2)` 같이 매 iteration 반복 sync 호출

**wrap 금지 (가성비 ↓)**:
- 단일 select/insert/update/delete (5ms — HTTP handler / background task 안 모두)
- `np.frombuffer`, `cv2.imdecode` 같은 µs 단위 CPU
- 작은 dict/list 파싱 (parse_images_from_elements 같은 가벼운 변환)

**Detection** (negative-pattern 📍):
```bash
# asyncio.to_thread / run_in_executor(None) 잔존 검출 (스레드 offload 는 전부 run_in_threadpool 로 통일; ProcessPoolExecutor 만 예외)
git grep --untracked -nE 'asyncio\.to_thread|run_in_executor\(\s*None' -- ':(glob){backend}/app/**/*.py'
```
0 hit → 통과. 1+ hit → `run_in_threadpool` 로 변환 필요.

heavy path 검사는 background task / N+1 loop / polling loop 들여다보고 critical 한 sync 호출 wrap 여부 확인.

**예외**: 라이브러리 코드 (framework-agnostic) 면 `asyncio.to_thread`/`run_in_executor` 허용. FastAPI app 내부면 `run_in_threadpool` 통일. CPU 바운드를 GIL 밖으로 빼는 `run_in_executor(ProcessPoolExecutor, ...)` 는 thread 풀이 아니므로 통일 대상 아님.

**관련 가이드 (BackgroundTasks vs asyncio.create_task)**:
- 응답 후 후속 처리 → `BackgroundTasks` (request 핸들러에 주입). `asyncio.create_task` fire-and-forget 금지 (GC 위험 + silent fail)
- 앱 수명 백그라운드 루프 (시세 틱 스트림 poller / Kafka consumer 등) → `lifespan` 에서 `asyncio.create_task` + instance attr (`self.task`) 보관 + shutdown 시 `task.cancel()` + `await task`
- 동적 fire-and-forget task 다수 생성 → `set` + `add_done_callback(set.discard)` 패턴 (GC 방지)

## 모듈 경계

### 14. 모듈 경계 침범

```python
# ❌ — services/scheduler/ 가 남의 모듈 리포지토리를 직접 주입받는다
class SchedulerService:
    def __init__(self, scheduler_repository, portfolio_repository): ...   # portfolio 는 남의 모듈

# ❌ — 리포지토리가 서비스를 부른다 (레이어 역류 + 모듈 결합)
# repositories/scheduler/scheduler_repository.py
from services.portfolio.portfolio_service import PortfolioService

# ✅ — 자기 모듈 리포지토리만 주입받고, 남의 모듈은 service → service 로 부른다
class SchedulerService:
    def __init__(self, scheduler_repository, portfolio_service): ...
```

**룰**: 프로세스가 갈려 있을 때는 "남의 모듈 테이블을 직접 읽는 코드"를 물리적으로 쓸 수 없었다. 한 앱으로 합친 뒤에는 그 보호막이 없으므로 import 방향으로 강제한다.

1. 서비스는 **자기 모듈의 리포지토리만** 주입받는다 (`services/<M>/` 안의 `from repositories.<N>` 은 `N != M` 이면 위반).
2. 모듈 간 호출은 **service → service** 만 — `app/repositories/` 안의 `from services.` 는 언제나 위반.
3. 남의 모듈 테이블을 내 리포지토리 SQL 에서 직접 조회하지 않는다 (테이블명↔모듈 매핑 표로 대조).

**Detection**:
```bash
# (1) 서비스가 남의 모듈 리포지토리를 import — 파일 경로의 모듈명과 import 의 모듈명 비교
git grep --untracked -nE '^\s*from repositories\.' -- ':(glob){backend}/app/services/**/*.py'
# (2) 리포지토리가 서비스를 import — hit 자체가 위반
git grep --untracked -nE '^\s*from services\.' -- ':(glob){backend}/app/repositories/**/*.py'
# (3) file 모듈 우회 — FileService 를 안 거치고 SFTP 클라이언트·file 리포지토리를 직접 잡는다
git grep --untracked -nE '^\s*from (clients\.file|repositories\.file)\.' -- ':(glob){backend}/app/**/*.py'
```
(1) hit = 후보. 각 hit 의 파일 경로 `services/<M>/` 와 import 의 `repositories.<N>` 을 대조해 `N != M` 이면 위반. (2) 0 hit → 통과, 1+ hit → 위반.
(3) hit = 후보. `core/container.py`(DI 배선이 그 일)·`services/file/`·`repositories/file/`(file 모듈 자기 것) 은 정상. 그 밖의 모듈에서 나오면 위반 — 아래 「file 모듈 접근」 예외가 금지한 경로다.

들여쓰기 import 도 잡도록 세 명령 모두 `^\s*` 로 앵커한다 (다른 룰과 같은 형식). 함수 안 지역 import 는 지금 이 repo 에 없지만, 순환참조를 피하려 넣는 순간 `^from` 앵커로는 안 보인다.

**예외**:
- **cross-service `select_X` 호출** — 룰 3 이 이미 "다른 Service 의 `select_X` 호출은 layer 경계 보호 차원에서 raise 의존 OK"로 인정한다. 모듈 간 존재 검증은 이 경로를 쓴다.
- **file 모듈 접근** — 다른 모듈은 `FileService` 를 DI 로 주입받아 호출한다. `SftpClient`·`FileRepository` 직접 호출은 위반 (흡수 전 "HTTP 프록시로만 접근" 규약이 서비스 계층으로 옮겨온 것).

### 15. provider 경계 침범 (소스 이름 누출)

```python
# ❌ — 소비자가 특정 소스 어댑터를 직접 import 한다
# app/services/bar/bar_service.py
from providers.data_go_kr.adapter import DataGoKrProvider

# ✅ — 레지스트리에 문자열로 묻는다. 어느 소스인지는 소비자가 모른다
from providers import get_provider
provider = get_provider(source, api_key)   # source 는 잡·설정에서 온 런타임 값
```

**룰**: 시세 소스 어댑터(`app/providers/<소스>/`)는 `providers/` 밖에서 import 되지 않는다. 소비자(service·repository·router·manager)가 아는 것은 정규화 모델(`providers.models`)·계약(`providers.base`)·레지스트리(`providers.get_provider`)뿐이다. 어댑터를 하나 더 붙여도 소비자 코드가 바뀌지 않는 것이 이 경계의 값이다 [Source: .docs/4-아키텍처/시세적재-구현설계.md §5.2].

같은 이유로 **어댑터는 `settings.` 를 읽지 않는다** — 키는 생성자 인자로 주입된다(MD-AD-20). 어댑터 안에 `from core.config import settings` 가 나오면 키의 출처가 여러 자리로 흩어지고, 그 값은 가림 등록(`utils/redaction/`)을 거치지 않아 로그·응답 관문 밖으로 흘러나간다. 키를 읽는 자리는 `services/data_key/` 하나이며 그 경계는 `backend-service/scripts/verify_data_key_env_boundary.py` 가 지킨다.

**Detection**:
```bash
# 소스 패키지 목록을 파일시스템에서 읽어 그 이름만 금지한다 (fail-closed — 0건 수집 시 실패)
uv run python scripts/verify_provider_boundary.py
# 어댑터가 settings 를 읽는가 — hit 자체가 위반
git grep --untracked -nE '^\s*from core\.config import' -- ':(glob){backend}/app/providers/**/*.py'
```
첫 명령은 검사한 소스 패키지 수·파일 수를 출력에 남긴다(통과가 "위반 없음"인지 "아무것도 안 봤음"인지 구분하기 위해). 두 번째는 0 hit → 통과, 1+ hit → 위반.

**예외**:
- `providers.models`·`providers.base`·`providers.merge` — 소스가 아니라 계약·공용 규칙이다. 소비자가 import 해도 무방하다.
- **소스 **이름 문자열**은 위반이 아니다** — `get_provider("sec", key)` 처럼 레지스트리 조회 키로 쓰는 것, 화면에 보여줄 표시값, 잡 레코드의 `source` 컬럼은 어댑터 **코드에 대한 의존**이 아니다. 금지 대상은 import 다.
