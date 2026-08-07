from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")


def format_kst(time: datetime | None = None) -> str:
    """datetime 을 KST 문자열로 (없으면 현재 시각). 마이크로초 포함."""
    dt = time.astimezone(_KST) if time else datetime.now(_KST)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def format_kst_seconds(time: datetime | None = None) -> str:
    """datetime 을 KST 문자열로 (초 단위, 마이크로초 없음)."""
    dt = time.astimezone(_KST) if time else datetime.now(_KST)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_kst_compact(time: datetime | None = None) -> str:
    """datetime 을 compact KST 문자열로 (`YYYYMMDD_HHMMSS`, 파일명/ID 용)."""
    dt = time.astimezone(_KST) if time else datetime.now(_KST)
    return dt.strftime("%Y%m%d_%H%M%S")


def now_kst() -> datetime:
    """현재 KST datetime (tz-aware)."""
    return datetime.now(_KST)


def to_kst(time: datetime) -> datetime:
    """tz-aware datetime 을 KST 로 변환."""
    return time.astimezone(_KST)


def assume_kst(dt) -> datetime:
    """naive datetime → KST aware (tzinfo 부착, 시각 변환 없음). pd.Timestamp 지원."""
    if hasattr(dt, "to_pydatetime"):
        dt = dt.to_pydatetime()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_KST)
    return dt


def parse_iso_to_kst(s: str | None) -> datetime | None:
    """ISO 문자열을 KST aware datetime 으로. Z suffix 처리, naive 입력은 UTC 가정, 파싱 실패/None 은 None."""
    if not s or s == "None":
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(_KST)


def parse_iso_to_kst_naive(s: str | None) -> datetime | None:
    """ISO 문자열을 KST naive datetime 으로. Z suffix 처리, naive 입력은 UTC 가정, 파싱 실패/None 은 None."""
    dt = parse_iso_to_kst(s)
    return dt.replace(tzinfo=None) if dt else None
