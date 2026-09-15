import re

from core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    HTTPError,
    InternalServerError,
    NotFoundError,
    RequestTimeoutError,
    ServiceUnavailableError,
)
from core.logger import logger
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

# 이 파일이 행 데이터를 로그로 흘리지 않는 두 축:
#  (1) 무결성·데이터 오류는 드라이버 메시지 대신 아래 allowlist 진단만 남긴다 (#216, DIAG_FIELDS 참조).
#  (2) exc_info=True 로 트레이스백을 찍는 핸들러(5xx·연결 오류·미분류 예외)의 마지막 줄은 SQLAlchemy
#      StatementError.__str__ 인데, 거기 실리던 `[parameters: {...}]` 는 엔진의 hide_parameters=True 가
#      지운다 (#234). 설정 지점은 이 파일이 아니라 **각 서비스의 엔진 팩토리**다 — 파일명은 서비스마다
#      다르고(동기 Engine·AsyncEngine·alembic), SQL 엔진이 없는 서비스에는 그 지점 자체가 없다.
#      드라이버 메시지·SQLSTATE·`[SQL: ...]` 문장은 그대로 남아, 트레이스백을 포기하지 않고도 값은
#      새지 않는다.

# PostgreSQL SQLSTATE → 도메인 예외 매핑. psycopg 는 네이티브 에러 번호가 아니라 SQLSTATE 로
# 원인을 알려 주므로, 코드를 메시지 문자열에서 긁지 않고 예외 객체의 sqlstate 를 읽는다.
SQLSTATE_MAP: dict[str, HTTPError] = {
    # 문구는 서비스 경로(`select` 로 먼저 걸러내는 쪽)와 같아야 한다 — 사용자에게는 같은 사건이다.
    "23505": ConflictError("이미 존재하는 데이터입니다."),  # unique_violation
    "23503": ConflictError("참조 중인 데이터가 있어 처리할 수 없습니다."),  # foreign_key_violation
    "23502": BadRequestError("필수 입력 항목이 누락되었습니다."),  # not_null_violation
    "23514": BadRequestError("입력 값이 허용된 범위를 벗어났습니다."),  # check_violation
    "22001": BadRequestError("입력 값이 허용된 길이를 초과했습니다."),  # string_data_right_truncation
    "22003": BadRequestError("입력 값이 허용된 범위를 벗어났습니다."),  # numeric_value_out_of_range
    "22P02": BadRequestError("입력 값의 형식이 올바르지 않습니다."),  # invalid_text_representation
    "22007": BadRequestError("입력 값의 형식이 올바르지 않습니다."),  # invalid_datetime_format
}

# 로그에 남길 드라이버 진단 필드 (라벨, psycopg diag 속성명) — 스키마 식별자만 고른다.
# diag 의 message_detail·message_hint 에는 PostgreSQL 이 붙이는 DETAIL 이 들어 있고,
# 거기에 `Key (code)=(AAA)`·`Failing row contains (...)` 처럼 삽입하려던 행 값이 통째로 실린다.
DIAG_FIELDS: tuple[tuple[str, str], ...] = (
    ("constraint", "constraint_name"),
    ("table", "table_name"),
    ("column", "column_name"),
)

# pyodbc 는 진단 객체가 없어 메시지 본문에서 제약명만 뽑는다 (값이 실리는 나머지 문장은 버린다).
# MSSQL 은 이 레포에서 완전히 걷어냈다(#166·#182) — 현재는 도달하지 않지만, database_utils.py 의
# 범용 멀티 DB 헬퍼와 같은 근거로 로깅용 코드 추출만 남기고 도메인 예외 매핑은 두지 않는다(#258).
MSSQL_CONSTRAINT_PATTERN = re.compile(r"constraint '([^']+)'", re.IGNORECASE)


async def handle_http_error(request: Request, exc: HTTPError):
    """도메인 HTTPError → JSON 응답. 모든 HTTPError 서브클래스 자동 매칭."""
    status_code = exc.status_code
    message = str(exc)
    if 500 <= status_code < 600:
        logger.error(f"{request.method} {request.url.path} {status_code}: {exc}", exc_info=True)
    else:
        logger.warning(f"{request.method} {request.url.path} {status_code}: {exc}")
    return JSONResponse(status_code=status_code, content={"detail": message}, headers=exc.headers)


async def handle_http_exception(request: Request, exc: HTTPException):
    if 500 <= exc.status_code < 600:
        logger.error(f"{request.method} {request.url.path} {exc.status_code}: {exc.detail}", exc_info=True)
    elif 400 <= exc.status_code < 500:
        logger.warning(f"{request.method} {request.url.path} {exc.status_code}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


def _sqlstate(orig) -> str | None:
    """드라이버 예외에서 SQLSTATE 를 꺼낸다 (psycopg3 는 `sqlstate`, psycopg2 는 `pgcode`)."""
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _mssql_error_code(orig) -> int | None:
    """pyodbc 메시지 꼬리의 `(2627)` 형태 네이티브 에러 번호를 꺼낸다."""
    match = re.search(r"\((\d{2,5})\)", str(orig or ""))
    return int(match.group(1)) if match else None


def _safe_diagnostics(orig) -> str:
    """드라이버 예외에서 값이 실리지 않는 진단만 뽑는다 — 제약·테이블·컬럼명 (원문에는 DETAIL 로 행 값이 딸려 온다)."""
    diag = getattr(orig, "diag", None)  # psycopg2/3 진단 객체
    if diag is not None:
        found = ((label, getattr(diag, attr, None)) for label, attr in DIAG_FIELDS)
        return " ".join(f"{label}={value}" for label, value in found if value)
    match = MSSQL_CONSTRAINT_PATTERN.search(str(orig or ""))
    return f"constraint={match.group(1)}" if match else ""


async def _handle_constraint_error(request: Request, exc: DataError | IntegrityError, fallback: HTTPError):
    """DB 제약/데이터 오류를 드라이버 코드로 분기한다. SQLSTATE 가 있으면 그쪽이 우선이다."""
    if sqlstate := _sqlstate(exc.orig):
        code, domain_exc = sqlstate, SQLSTATE_MAP.get(sqlstate)
    else:
        code, domain_exc = _mssql_error_code(exc.orig), None
    logger.warning(f"{request.method} {request.url.path} DB {code} {_safe_diagnostics(exc.orig)}".rstrip())
    return await handle_http_error(request, domain_exc or fallback)


async def handle_integrity_error(request: Request, exc: IntegrityError):
    return await _handle_constraint_error(request, exc, ConflictError("데이터 제약 조건을 위반했습니다."))


async def handle_data_error(request: Request, exc: DataError):
    return await _handle_constraint_error(request, exc, BadRequestError("입력 값이 올바르지 않습니다."))


async def handle_operational_error(request: Request, exc: OperationalError):
    logger.error(f"{request.method} {request.url.path} DB connection: {exc.orig}", exc_info=True)
    return await handle_http_error(request, ServiceUnavailableError("데이터베이스에 일시적으로 연결할 수 없습니다."))


async def handle_value_error(request: Request, exc: ValueError):
    return await handle_http_error(request, BadRequestError(str(exc) if re.search(r"[가-힣]", str(exc)) else None))


async def handle_permission_error(request: Request, exc: PermissionError):
    return await handle_http_error(request, ForbiddenError(str(exc) if re.search(r"[가-힣]", str(exc)) else None))


async def handle_file_not_found_error(request: Request, exc: FileNotFoundError):
    return await handle_http_error(request, NotFoundError(str(exc) if re.search(r"[가-힣]", str(exc)) else None))


async def handle_timeout_error(request: Request, exc: TimeoutError):
    return await handle_http_error(request, RequestTimeoutError(str(exc) if re.search(r"[가-힣]", str(exc)) else None))


async def handle_connection_error(request: Request, exc: ConnectionError):
    return await handle_http_error(
        request, ServiceUnavailableError(str(exc) if re.search(r"[가-힣]", str(exc)) else None)
    )


async def handle_runtime_error(request: Request, exc: RuntimeError):
    return await handle_http_error(request, InternalServerError(str(exc) if re.search(r"[가-힣]", str(exc)) else None))


async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.error(f"{request.method} {request.url.path} unexpected: {repr(exc)}", exc_info=True)
    return await handle_http_error(request, InternalServerError())


def _body_field_hints(request: Request) -> dict[str, str]:
    """이 요청이 받는 본문 모델의 `필드명 → 설명`. 못 찾으면 빈 dict (fail-open).

    설명은 **모델에 이미 적혀 있다** — 그것을 422 응답까지 들고 나오는 것이 이 함수의 전부다.
    실패해도 기본 메시지로 떨어질 뿐이라, 여기서 예외를 밖으로 내보내지 않는다.
    """
    try:
        route = request.scope.get("route")
        params = getattr(getattr(route, "dependant", None), "body_params", None) or []
        hints: dict[str, str] = {}
        for param in params:
            # pydantic v2 를 쓰는 FastAPI 에서 `ModelField.type_` 는 비어 있다 —
            # 실제 타입은 `field_info.annotation` 에 있다 (0.141 실측).
            model = getattr(getattr(param, "field_info", None), "annotation", None)
            fields = getattr(model, "model_fields", None) or {}
            for name, field in fields.items():
                if field.description:
                    hints.setdefault(name, field.description)
        return hints
    except Exception:  # noqa: BLE001 — 안내를 못 붙이는 것이 요청을 죽일 이유는 아니다
        return {}


async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 에 **무엇을 넣어야 하는지**를 함께 낸다.

    기본 응답은 「scope: Field required」로 끝나서, 형식이 자연스러운 추측과 다른 필드
    (`"KOSPI:005930,000660"` 처럼 두 축을 한 문자열에 합친 것)에서는 읽어도 다음 수를 모른다.
    모델의 `description` 을 그대로 실어, 스키마와 오류 메시지가 두 벌이 되지 않게 한다.
    """
    hints = _body_field_hints(request)
    details = []
    for error in exc.errors():
        item = {"loc": list(error.get("loc", ())), "msg": error.get("msg", ""), "type": error.get("type", "")}
        location = item["loc"]
        if len(location) >= 2 and location[0] == "body":
            hint = hints.get(str(location[1]))
            if hint:
                item["hint"] = hint
        details.append(item)
    logger.info(f"요청 형식 오류 — path={request.url.path} fields={[d['loc'] for d in details]}")
    return JSONResponse(status_code=422, content={"detail": details})


def get_exception_handlers():
    return {
        RequestValidationError: handle_request_validation_error,
        HTTPError: handle_http_error,
        ValueError: handle_value_error,
        PermissionError: handle_permission_error,
        FileNotFoundError: handle_file_not_found_error,
        TimeoutError: handle_timeout_error,
        ConnectionError: handle_connection_error,
        RuntimeError: handle_runtime_error,
        IntegrityError: handle_integrity_error,
        DataError: handle_data_error,
        OperationalError: handle_operational_error,
        HTTPException: handle_http_exception,
        Exception: handle_unexpected_exception,
    }
