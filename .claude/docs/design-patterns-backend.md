# Backend CRUD Patterns

신규 CRUD 엔티티 생성 시 따라야 할 코드 패턴 (단일 진실의 원천). 1:1 (단일) + 1:N (parent → children).

## 이 파일의 역할

- **scaffold-backend 에이전트**: 신규 엔티티 생성 시 1:1 / 1:N 섹션의 코드 블록 그대로 적용 + placeholder 치환.
- **평상시 작업 (Claude 메인)**: 도메인 필드 추가/변경 시 시그니처/네이밍 일관성 유지. 새 레이어 함수 작성 시 동일 시그니처 패턴 사용.
- **review-backend Phase C**: 시그니처/네이밍 표준과 다른 구현 발견 시 의심 보고.

레이어 구조 / DI / anti-pattern 룰은 각 backend 폴더 `CLAUDE.md` + [`anti-patterns-backend.md`](anti-patterns-backend.md). 여기는 **구조 패턴 (코드 블록)** 만.

## 목차

- [네이밍 컨벤션](#네이밍-컨벤션) — placeholder 치환 규칙
- [라우트 (REST) 컨벤션](#라우트-rest-컨벤션) — kebab 리소스 경로 + frontend 라우트 SoT
- [생성 파일 목록](#생성-파일-목록) — 1:1 / 1:N 별 신규/수정 파일
- [예시 비즈니스 필드](#예시-비즈니스-필드) — UI 타입 다양성 샘플 (도메인에 맞게 교체)
- [공통 응답 (`schemas/common_schema.py`)](#공통-응답-schemascommon_schemapy) — 재사용 base 모델
- [1:1 단일 엔티티 CRUD](#11-단일-엔티티-crud) — schemas / repositories / services / routers / DI / main.py
- [1:N (parent → children) CRUD](#1n-parent--children-crud) — 단일 대비 차이 + 자식 패턴
- [백그라운드 매니저](#백그라운드-매니저) — 앱 수명 루프 (단일 프로세스 `--workers=1`)

`{backend}` 는 `app/main.py` 가 있는 폴더 (서비스별로 `backend/` / `etl-pipeline/` / `daemon-service/` 등). 프로젝트마다 여러 개 가능.

## 네이밍 컨벤션

| Placeholder | 케이스 | 출처 / 변환 | 예 (`Todo`) | 예 (`OrderItem`) |
|---|---|---|---|---|
| `{Entity}`, `{Parent}`, `{Child}` | PascalCase | 사용자 invocation (단수) | `Todo` | `Order`, `OrderItem` |
| `{entity}`, `{parent}`, `{child}` | snake_case | `{Entity}` 변환 (모듈명, 함수명, args 키) | `todo` | `order`, `order_item` |
| `{route}`, `{parent_route}`, `{child_route}` | kebab-case | `{Entity}` 케밥 변환 (**URL 전용** — prefix/tags/nested segment) | `todo` | `order`, `order-item` |
| `{table}`, `{parent_table}`, `{child_table}` | UPPER snake | `TN_{entity}` | `TN_todo` | `TN_order`, `TN_order_item` |
| `{pk}`, `{parent_pk}`, `{child_pk}` | snake_case | `{entity}` (PK 컬럼명 = entity 이름과 동일) | `todo` | `order`, `order_item` |

**파일명**: `{entity}_router.py`, `{entity}_service.py`, `{entity}_repository.py`, `{entity}_schema.py` (전부 동일 basename, 1:N 도 부모 basename 하나만 사용).

**폴더 구조**: 각 레이어 안에 도메인 폴더로 분리 — `{레이어}/{도메인}/{파일}.py`. 단일 엔티티 신규는 `{entity}/` 를 도메인 폴더로 사용. 기존 그룹 도메인(예: `data/`, `messaging/`, `mlflow/`) 안에 추가하려면 그쪽 폴더에 둠.

## 라우트 (REST) 컨벤션

`APIRouter(prefix=...)` 의 경로가 frontend 라우트의 **단일 출처(SoT)**. frontend proxy route 가 이 prefix 를 `{SERVICE}_SERVICE_URL + "{prefix}"` 로 **byte-identical** 호출한다. backend prefix 를 바꾸면 frontend proxy route + client `BASE_URL` (+ admin page) 를 lockstep 으로 수정.

- **CRUD 리소스 = flat kebab-case 명사** (`{route}`, 다단어 `order-item`) — **단수 기본** (`/document`, `/chat-session`, `/dataset`). 파일/모듈/변수/PK 는 snake_case (`{entity}`), URL 만 kebab (단어 1개면 동일). 스캐폴드 default.
- **CRUD 액션은 HTTP 동사로** — `GET` 목록 / `GET /{pk}` 단건 / `POST` 생성 / `PUT /{pk}` 수정 / `DELETE /{pk}` 삭제. CRUD path 에 동사 금지 (`/get-todo`, `/todo-list` ❌).
- **PK 는 path param** (`/{route}/{pk}`), 필터·정렬·페이지는 query (`skip`/`take`/`filter`/`sort`).
- **1:N 은 부모 PK 아래 중첩** — `/{parent_route}/{parent_pk}/{child_route}` (자식을 별도 top-level prefix 로 분리 금지).
- **비-CRUD 도메인(트랜잭션·스트림·집계)은 `/domain/sub` 계층형 + 동사 prefix 허용** — 에이전트 실행/스트림/집계 (`/agent/run`, `/market/stream`, `/nav/aggregate`, `/data/dataset`). CRUD 명사 규칙 강제 대상 아님 (정상 패턴).
- **외부 API 미러는 그 API 표기 따름** — 예: MLflow (`/mlflow/experiments`, `/models`, `/runs`) 복수형 유지.

## 생성 파일 목록

**1:1 단일** (4 신규 + 2 수정)
- `{backend}/app/routers/{entity}/{entity}_router.py`
- `{backend}/app/services/{entity}/{entity}_service.py`
- `{backend}/app/repositories/{entity}/{entity}_repository.py`
- `{backend}/app/schemas/{entity}/{entity}_schema.py`
- 수정: `{backend}/app/core/container.py` — `{entity}_repository`, `{entity}_service` provider 추가
- 수정: `{backend}/app/main.py` — `{entity}_router` import + `include_router` + `wire`

**1:N** (1:1 과 동일한 4 파일, 단 부모 basename 하나에 부모/자식 통합)
- `{backend}/app/routers/{parent}/{parent}_router.py` (부모 router 안에 자식 nested 라우트 포함)
- `{backend}/app/services/{parent}/{parent}_service.py` (부모/자식 메서드 모두)
- `{backend}/app/repositories/{parent}/{parent}_repository.py` (부모/자식 메서드 모두)
- `{backend}/app/schemas/{parent}/{parent}_schema.py` (부모/자식 모델 모두)
- 수정: container.py / main.py — 부모 한 쌍만 등록 (자식 전용 service/repository 만들지 않음)

## 예시 비즈니스 필드

스캐폴드가 빈 골조에 채워주는 **예시 placeholder** — UI 타입 다양성을 보여주는 샘플일 뿐, "필수 default" 가 아님. 사용자가 도메인에 맞게 자유롭게 교체/추가/삭제:

| 필드 | 타입 | UI |
|---|---|---|
| `name` | `str(max=200)` | TextBox |
| `category` | `str(max=5)` | SelectBox + codeList |
| `due_date` | `str` (date) | DateBox |
| `amount` | `int` | NumberBox |
| `description` | `str(max=1000)` | TextArea |
| `use_at` | `str(default="Y", max=1)` | SelectBox(Y/N) |
| `photo_atch_file_id` | `str(max=20)` | FileUploader (image) |
| `document_atch_file_id` | `str(max=20)` | FileUploader (document) |

**공통 감사 컬럼** (항상 포함, `CommonEntity` 상속): `reg_dt`, `reg_id`, `mod_dt`, `mod_id`. INSERT `reg_id` / UPDATE `mod_id` 는 `from core.auth_context import get_email` 의 `get_email()` (현재 요청자 email) 로 채운다 — `request.state` 사용 안 함. 비즈니스 소유/식별 컬럼(`user_id` 등)은 `get_user_id()` (uuid), 테넌트 격리는 `get_workspace_id()`.

**테넌트 격리** (멀티테넌트): 워크스페이스 단위로 격리할 비즈니스 테이블은 `workspace_id` 컬럼 포함 — INSERT 시 `get_workspace_id()` 채우고, SELECT/UPDATE/DELETE 의 WHERE 에 `workspace_id` 조건 추가. 어떤 테이블을 격리할지는 도메인별 판단.

---

## 공통 응답 (`schemas/common_schema.py`)

이미 존재하는 base 사용 — 재정의 금지:
- `TrimmedBaseModel` — 빈 문자열 → None 자동 변환
- `CommonEntity` — `rn`, `reg_dt`, `reg_id`, `mod_dt`, `mod_id` 출력 필드 (모든 `*Out` 에 포함)
- `CreateOut`, `UpdateOut`, `DeleteOut` — 변경 응답 wrapper

---

## 1:1 단일 엔티티 CRUD

### `schemas/{entity}/{entity}_schema.py`
```python
from pydantic import BaseModel, Field
from schemas.common_schema import CommonEntity, TrimmedBaseModel

class {Entity}(TrimmedBaseModel):
    # UI 타입별 placeholder 1개씩 — 도메인에 맞게 교체/추가
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=5)
    due_date: str | None = Field(None)
    amount: int | None = Field(None)
    description: str | None = Field(None, max_length=1000)
    use_at: str = Field(default="Y", max_length=1)
    photo_atch_file_id: str | None = Field(None, max_length=20)
    document_atch_file_id: str | None = Field(None, max_length=20)

class {Entity}Out({Entity}, CommonEntity):
    {pk}: str  # PK 타입에 맞게

class {Entity}sOut(BaseModel):
    items: list[{Entity}Out]
    total_count: int

class {Entity}CreateIn({Entity}):
    {pk}: str = Field(..., max_length=20)

class {Entity}UpdateIn({Entity}):
    pass
```

### `repositories/{entity}/{entity}_repository.py`
```python
from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort

class {Entity}Repository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def query_select_{entity}(self) -> str:
        return """
            SELECT *
              FROM (
                SELECT {pk}, name, category, due_date, amount, description, use_at,
                       photo_atch_file_id, document_atch_file_id,
                       FORMAT(reg_dt, 'yyyy-MM-dd HH:mm:ss') AS reg_dt, reg_id,
                       FORMAT(mod_dt, 'yyyy-MM-dd HH:mm:ss') AS mod_dt, mod_id
                FROM {table}
              ) A
            WHERE 1 = 1
        """

    def select_{entity}_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_{entity}()
        sql_where, sql_params = build_filter_params(args)
        order_by = parse_sort(args.get("sort")) or "{pk} ASC"
        skip = int(args.get("skip", 0))
        take = args.get("take")

        count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_sql} {sql_where}) TB"

        if take is not None:
            take = int(take)
            final_sql = f"""
                SELECT * FROM (
                    SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn, TB.*
                    FROM ({base_sql} {sql_where}) TB
                ) TB WHERE rn BETWEEN {skip + 1} AND {skip + take}
            """
        else:
            final_sql = f"""
                SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn, TB.*
                FROM ({base_sql} {sql_where}) TB
            """

        with self.sql_client.connect() as conn:
            rows = conn.execute(text(final_sql), sql_params).mappings().all()
            total = conn.execute(text(count_sql), sql_params).scalar()
            return [dict(r) for r in rows], total

    def select_{entity}(self, args: dict) -> dict | None:
        sql = self.query_select_{entity}() + " AND {pk} = :{pk}"
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), args).mappings().fetchone()
            return dict(row) if row else None

    def insert_{entity}(self, args: dict) -> tuple:
        sql = """
            INSERT INTO {table} (
                {pk}, name, category, due_date, amount, description, use_at,
                photo_atch_file_id, document_atch_file_id,
                reg_id, reg_dt, mod_id, mod_dt
            )
            OUTPUT INSERTED.{pk}
            VALUES (
                :{pk}, :name, :category, :due_date, :amount, :description, :use_at,
                :photo_atch_file_id, :document_atch_file_id,
                :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP
            )
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                return conn.execute(text(sql), args).fetchone()

    def update_{entity}(self, args: dict) -> None:
        sql = """
            UPDATE {table}
               SET name                  = :name,
                   category              = :category,
                   due_date              = :due_date,
                   amount                = :amount,
                   description           = :description,
                   use_at                = :use_at,
                   photo_atch_file_id    = :photo_atch_file_id,
                   document_atch_file_id = :document_atch_file_id,
                   mod_id                = :mod_id,
                   mod_dt                = CURRENT_TIMESTAMP
             WHERE {pk} = :{pk}
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_{entity}(self, args: dict) -> None:
        sql = "DELETE FROM {table} WHERE {pk} = :{pk}"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)
```

### `services/{entity}/{entity}_service.py`
```python
from core.exceptions import ConflictError, NotFoundError
from repositories.{entity}.{entity}_repository import {Entity}Repository

class {Entity}Service:
    def __init__(self, {entity}_repository: {Entity}Repository):
        self.{entity}_repository = {entity}_repository

    def select_{entity}_list(self, args: dict) -> tuple[list, int]:
        """
        {Entity} 리스트를 조회하는 메소드
        """
        return self.{entity}_repository.select_{entity}_list(args)

    def select_{entity}(self, args: dict) -> dict:
        """
        개별 {Entity}를 조회하는 메소드
        """
        item = self.{entity}_repository.select_{entity}(args)
        if not item:
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        return item

    def insert_{entity}(self, args: dict) -> tuple:
        """
        {Entity}를 생성하는 메소드
        """
        if self.{entity}_repository.select_{entity}(args):
            raise ConflictError("이미 존재하는 데이터입니다.")
        return self.{entity}_repository.insert_{entity}(args)

    def update_{entity}(self, args: dict) -> None:
        """
        {Entity}를 업데이트하는 메소드
        """
        if not self.{entity}_repository.select_{entity}(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.{entity}_repository.update_{entity}(args)

    def delete_{entity}(self, args: dict) -> None:
        """
        {Entity}를 삭제하는 메소드
        """
        if not self.{entity}_repository.select_{entity}(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.{entity}_repository.delete_{entity}(args)
```

#### 예외 선택 가이드

Service 에서 raise 할 예외는 상황에 따라 골라 사용. `core/exception_handler.py` 가 status 매핑 일괄 처리 — `HTTPException` 직접 사용 금지.

| 상황 | 예외 | HTTP | 예시 |
|---|---|---|---|
| 리소스 미존재 | `NotFoundError` | 404 | 조회·수정·삭제 시 `select_X` 결과가 None |
| 리소스 중복 / 종속 충돌 | `ConflictError` | 409 | insert 시 PK 이미 존재, 사용중인 데이터 삭제 |
| 입력값 검증 실패 | `ValueError` | 400 | "이미지 파일이 아닙니다", 비즈니스 규칙 위반 |
| 권한 부족 | `PermissionError` | 403 | SFTP 권한 거부, 작성자 아닌 사용자 수정 |
| 외부 서비스 연결 실패 | `ConnectionError` | 503 | LLM/Milvus 클라이언트 미설정·연결 불가 |
| 의도적 user-facing 500 | `RuntimeError` | 500 | "재시도해주세요" 같이 사용자에게 노출해야 하는 일시적 실패. **메시지 노출되므로 민감 정보 금지** |
| 예측 못 한 오류 | (raise 안 함, 자연 전파) | 500 | handler 가 `Exception` catch 후 generic 메시지로 응답 |

- **도메인 예외** (`NotFoundError`, `ConflictError`): `core/exceptions.py` 정의, `from core.exceptions import ...` 로 import
- **표준 예외** (`ValueError`, `PermissionError`, `ConnectionError`): Python builtin 그대로 사용
- **Router 의 예외**: client-disconnect 처리용 `asyncio.CancelledError` → `HTTPException(499)` 변환만 허용. 그 외 try/except 금지.

### `routers/{entity}/{entity}_router.py`
```python
from core.container import Container
from core.auth_context import get_email
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.common_schema import CreateOut, DeleteOut, UpdateOut
from schemas.{entity}.{entity}_schema import (
    {Entity}CreateIn, {Entity}Out, {Entity}sOut, {Entity}UpdateIn,
)
from services.{entity}.{entity}_service import {Entity}Service
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(prefix="/{route}", tags=["{route}"])

@router.get("", response_model={Entity}sOut, dependencies=[Depends(verify_access_token)])
@inject
async def select_{entity}_list(
    request: Request,
    skip: int = Query(0), take: int | None = None,
    filter: str | None = None, sort: str | None = None,
    {entity}_service: {Entity}Service = Depends(Provide[Container.{entity}_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}
    items, total = {entity}_service.select_{entity}_list(args)
    return {Entity}sOut(items=items, total_count=total)

@router.post("", response_model=CreateOut, dependencies=[Depends(verify_access_token)])
@inject
async def insert_{entity}(
    request: Request, body: {Entity}CreateIn,
    {entity}_service: {Entity}Service = Depends(Provide[Container.{entity}_service]),
):
    args = body.model_dump()
    args["reg_id"] = get_email()
    keys = {entity}_service.insert_{entity}(args)
    return CreateOut(data={"{pk}": keys[0]} if keys else None)

@router.get("/{{pk}}", response_model={Entity}Out, dependencies=[Depends(verify_access_token)])
@inject
async def select_{entity}(
    request: Request, {pk}: str,
    {entity}_service: {Entity}Service = Depends(Provide[Container.{entity}_service]),
):
    args = {"{pk}": {pk}}
    return {entity}_service.select_{entity}(args)

@router.put("/{{pk}}", response_model=UpdateOut, dependencies=[Depends(verify_access_token)])
@inject
async def update_{entity}(
    request: Request, {pk}: str, body: {Entity}UpdateIn,
    {entity}_service: {Entity}Service = Depends(Provide[Container.{entity}_service]),
):
    args = body.model_dump()
    args["{pk}"] = {pk}
    args["mod_id"] = get_email()
    {entity}_service.update_{entity}(args)
    return UpdateOut()

@router.delete("/{{pk}}", response_model=DeleteOut, dependencies=[Depends(verify_access_token)])
@inject
async def delete_{entity}(
    request: Request, {pk}: str,
    {entity}_service: {Entity}Service = Depends(Provide[Container.{entity}_service]),
):
    args = {"{pk}": {pk}}
    {entity}_service.delete_{entity}(args)
    return DeleteOut()
```

### DI 등록 (`{backend}/app/core/container.py`)
```python
{entity}_repository = providers.Factory({Entity}Repository, sql_client=backend_sql_client)
{entity}_service = providers.Factory({Entity}Service, {entity}_repository={entity}_repository)
```

### modules.py
```python
# app/modules.py 의 ROUTER_MODULES 에 한 줄 추가 (등록·wiring 이 한 목록에서 나온다)
ROUTER_MODULES: list[str] = [
    ...,
    "routers.{entity}.{entity}_router",
]
```
`main.py` 는 `register_routers(app)` 로 이 목록을 순회하므로 손대지 않는다. 같은 prefix 가 이미 있으면 기동이 `RuntimeError` 로 거부된다.

---

## 1:N (parent → children) CRUD

부모-자식 1:N. **하나의 router 안에 부모 라우트 + 자식 nested 라우트** 정의 (자식 별도 router 만들지 않음).

### 단일 대비 차이

**모든 레이어를 부모 파일 하나에 통합** (자식 전용 파일 만들지 않음):

1. **Schema** — `{parent}_schema.py` 한 파일에 부모/자식 모델 모두.
2. **Repository** — `{parent}_repository.py` 한 파일에 부모/자식 메서드 모두 (`select_{child}_list`, `insert_{child}`, ...). 자식 SELECT 는 항상 `WHERE {parent_pk} = :{parent_pk}` 포함.
3. **Service** — `{parent}_service.py` 한 파일에 부모/자식 메서드 모두. repository 한 개만 주입.
4. **Router** — `{parent}_router.py` 한 파일, 부모 router 안에 자식 라우트 nested:
   - 부모: `GET/POST /{parent_route}`, `GET/PUT/DELETE /{parent_route}/{parent_pk}`
   - 자식: `GET/POST /{parent_route}/{parent_pk}/{child_route}`, `GET/PUT/DELETE /{parent_route}/{parent_pk}/{child_route}/{child_pk}`

### Repository — 부모/자식 메서드 한 클래스에 통합

```python
class {Parent}Repository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    # 부모: 단일 패턴 그대로 (query_select_{parent}, select_{parent}_list, select_{parent}, insert_{parent}, update_{parent})

    # 부모 삭제 시 자식 cascade
    def delete_{parent}(self, args: dict) -> None:
        sql_children = "DELETE FROM {child_table} WHERE {parent_pk} = :{parent_pk}"
        sql_parent = "DELETE FROM {parent_table} WHERE {parent_pk} = :{parent_pk}"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql_children), args)
                conn.execute(text(sql_parent), args)

    # 자식 SELECT — 항상 부모 PK 포함
    def query_select_{child}(self) -> str:
        return """
            SELECT *
              FROM (
                SELECT c.*, ...
                FROM {child_table} c
                INNER JOIN {parent_table} p ON c.{parent_pk} = p.{parent_pk}
              ) A
             WHERE 1 = 1
               AND {parent_pk} = :{parent_pk}
        """

    # 자식 select_{child}_list / select_{child} / insert_{child} / update_{child} / delete_{child}
    # — 단일 패턴과 동일하되 args 에 {parent_pk} 항상 포함
```

### Router — 부모 안에 자식 nested
```python
router = APIRouter(prefix="/{parent_route}", tags=["{parent_route}"])

# 부모: 단일 패턴 그대로 (GET ""/POST ""/GET "/{{parent_pk}}"/PUT/DELETE)

# 자식 (parent PK nested):
@router.get("/{{parent_pk}}/{child_route}", response_model={Child}sOut, dependencies=[Depends(verify_access_token)])
@inject
async def select_{child}_list(
    request: Request,
    {parent_pk}: str,
    skip: int = Query(0), take: int | None = None,
    filter: str | None = None, sort: str | None = None,
    {parent}_service: {Parent}Service = Depends(Provide[Container.{parent}_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"{parent_pk}": {parent_pk}, "skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}
    items, total = {parent}_service.select_{child}_list(args)
    return {Child}sOut(items=items, total_count=total)

@router.post("/{{parent_pk}}/{child_route}", response_model=CreateOut, dependencies=[Depends(verify_access_token)])
@inject
async def insert_{child}(
    request: Request, {parent_pk}: str, body: {Child}CreateIn,
    {parent}_service: {Parent}Service = Depends(Provide[Container.{parent}_service]),
):
    args = body.model_dump()
    args["{parent_pk}"] = {parent_pk}
    args["reg_id"] = get_email()
    keys = {parent}_service.insert_{child}(args)
    return CreateOut(data={"{parent_pk}": {parent_pk}, "{child_pk}": keys[0]} if keys else None)

# GET/PUT/DELETE /{{parent_pk}}/{child_route}/{{child_pk}} — 동일 패턴, args 에 {parent_pk}+{child_pk} 모두 주입
```

### DI 등록 (단일 패턴과 동일 — repository/service 각 한 개)
```python
{parent}_repository = providers.Factory({Parent}Repository, sql_client=backend_sql_client)
{parent}_service = providers.Factory({Parent}Service, {parent}_repository={parent}_repository)
```

### main.py
부모 router 만 등록 — 자식 라우트는 부모 안에 정의됨:
```python
# app/modules.py 의 ROUTER_MODULES 에 부모만 추가
ROUTER_MODULES: list[str] = [
    ...,
    "routers.{parent}.{parent}_router",
]
```

---

## 백그라운드 매니저

큐 폴링·발행 / 외부 구독 / 주기 작업 등 **앱 수명 동안 도는 백그라운드 루프**는 매니저로 캡슐화한다 — `{backend}/app/managers/{도메인}/{name}_manager.py`, **모듈 레벨 싱글톤 인스턴스**. (CRUD 아님 — scaffold 대상 아니고 패턴 참고용)

### 단일 프로세스 (`--workers=1`)
매니저는 앱(`main.py`) lifespan 에서 기동한다. 매니저가 앱 안에서 돌므로 **매니저 있는 서비스는 `--workers=1`(단일 프로세스)로 운영** — 멀티워커면 매니저가 워커마다 떠서 중복 실행된다. (router HTTP 동시성을 워커로 키워야 하면, router 가 매니저-자원을 직접 제어하지 않는 경우에 한해 web/worker 분리를 별도 검토 — 기본은 단일 프로세스.)

### 매니저 패턴 (async)
```python
# managers/{도메인}/{name}_manager.py
import asyncio
from core.container import Container
from core.logger import logger
from dependency_injector.wiring import Provide, inject
from fastapi.concurrency import run_in_threadpool

INTERVAL = 5

class {Name}Manager:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.should_stop = False

    @inject
    async def start(self, {x}_service: {X}Service = Provide[Container.{x}_service]) -> None:
        if self.task and not self.task.done():
            logger.warning("{Name} already running")
            return
        self.should_stop = False

        async def loop():
            while not self.should_stop:
                await run_in_threadpool({x}_service.do_batch)   # 루프 내 sync DB/CPU 는 run_in_threadpool (anti-pattern 13)
                await asyncio.sleep(INTERVAL)

        self.task = asyncio.create_task(loop())   # self.task 보관 — bare fire-and-forget 금지 (GC/silent fail)

    async def stop(self) -> None:
        self.should_stop = True
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

{name}_manager = {Name}Manager()   # 모듈 레벨 싱글톤
```
- **등록 1곳**: `app/modules.py` 의 `MANAGER_MODULES` 에 `("managers.{도메인}.{name}_manager", "{name}_manager")` 추가. lifespan 이 목록 순서로 `await start()`, 역순으로 `await stop()` 하고 wiring 대상도 같은 목록에서 나온다 — `start()`·`stop()` 은 둘 다 코루틴이어야 한다.
- 루프 내 sync blocking(DB/CPU)은 `run_in_threadpool` — `asyncio.to_thread`·`loop.run_in_executor(None, ...)` 금지 (ProcessPoolExecutor 만 예외, anti-pattern 13).
- **커플드 매니저**(연결↔구독처럼 in-process 세션/이벤트 공유, 예: 시세 스트림 connection↔tick subscription)도 같은 프로세스 안에 함께 두면 그대로 동작.
- **router 가 매니저-자원을 HTTP 로 제어**(예: 연결 connect/disconnect)하면 그 자원이 매니저와 같은 프로세스여야 하므로 **반드시 단일 프로세스** — 워커를 늘리지 않는다.
