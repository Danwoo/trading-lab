"""HTTP status 에 대응하는 도메인 예외.

Service / Repository 에서 raise. `core/exception_handler.py` 가 HTTP 응답으로 변환.

각 클래스는 자기 `status_code` 와 `default_message` 보유. raise 시 메시지 생략 가능.

예시:
    raise NotFoundError("사용자를 찾을 수 없습니다.")  # 404 + 명시 메시지
    raise NotFoundError()                              # 404 + 디폴트 메시지
"""

from fastapi import status


class HTTPError(Exception):
    """모든 HTTP 도메인 예외의 베이스."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "처리 중 오류가 발생했습니다."
    default_headers: dict[str, str] | None = None

    def __init__(self, message: str | None = None, *, headers: dict[str, str] | None = None):
        super().__init__(message or self.default_message)
        self.headers = headers if headers is not None else self.default_headers


# 4xx — 클라이언트 오류
class BadRequestError(HTTPError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "잘못된 요청입니다."


class UnauthorizedError(HTTPError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "인증이 필요합니다."
    default_headers = {"WWW-Authenticate": "Bearer"}  # RFC 6750


class ForbiddenError(HTTPError):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "접근 권한이 없습니다."


class NotFoundError(HTTPError):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "요청한 데이터를 찾을 수 없습니다."


class MethodNotAllowedError(HTTPError):
    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    default_message = "허용되지 않은 요청 방식입니다."


class RequestTimeoutError(HTTPError):
    status_code = status.HTTP_408_REQUEST_TIMEOUT
    default_message = "요청 시간이 초과되었습니다."


class ConflictError(HTTPError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "이미 존재하거나 다른 데이터와 충돌이 발생했습니다."


class GoneError(HTTPError):
    status_code = status.HTTP_410_GONE
    default_message = "이 데이터는 더 이상 사용할 수 없습니다."


class RequestEntityTooLargeError(HTTPError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    default_message = "요청 데이터가 너무 큽니다."


class UnsupportedMediaTypeError(HTTPError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_message = "지원하지 않는 형식입니다."


class RequestedRangeNotSatisfiableError(HTTPError):
    status_code = status.HTTP_416_RANGE_NOT_SATISFIABLE
    default_message = "요청한 범위가 올바르지 않습니다."


class UnprocessableEntityError(HTTPError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    default_message = "입력 값을 확인해주세요."


class TooManyRequestsError(HTTPError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."


# 5xx — 서버 오류
class InternalServerError(HTTPError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "서버 내부 오류가 발생했습니다."


class BadGatewayError(HTTPError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = "외부 서비스 응답이 올바르지 않습니다."


class ServiceUnavailableError(HTTPError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "서비스에 일시적으로 연결할 수 없습니다."


class GatewayTimeoutError(HTTPError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_message = "외부 서비스 응답 시간이 초과되었습니다."
