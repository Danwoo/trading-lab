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
    "23505": ConflictError("이미 등록된 값입니다."),  # unique_violation
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


def get_exception_handlers():
    return {
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
