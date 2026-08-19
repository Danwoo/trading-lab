"""데이터 소스 자격 조회 — **`.env` 가 정본이다** (2026-08-07 리드 결정).

2026-07-29 의 두 결정(「데이터 API 키=워크스페이스 설정」·「데이터 소스 API 키=암호화 저장」)을
뒤집은 자리다. 제품 정의가 바뀐 것이 근거다 — 2026-07-28 결정으로 이 제품은 **오픈소스 로컬
배포판 우선**이고 「각자 자기 컴퓨터에서 자기 계좌로」 굴린다. 1인 로컬 설치에서 워크스페이스마다
키를 따로 두는 것은 의미가 없고, `.env` 가 그 배포 형태의 관용구다. 그래서
워크스페이스별 키 표도, 저장 암호화도 짓지 않는다 — `.env` 값을 다시 암호화하면 그
복호화 키를 둘 자리가 결국 같은 `.env` 라 자물쇠와 열쇠를 한 상자에 넣는 꼴이 된다.

**감수**: 이 선택은 **호스팅 모드에서 성립하지 않는다.** 여러 사람이 한 인스턴스를 쓰면 한 사람의
키로 전원이 조회하게 되고, 그것은 원 결정의 근거였던 「data.go.kr·KRX 등이 비상업·제3자 제공을
금지한다」와 정면으로 충돌한다. 호스팅 모드를 열 때 이 결정을 다시 판단해야 한다.

`workspace_id` 인자는 남는다 — 호출부(`CapabilityService`·`IngestService`·`QuoteBatchService`)의
시그니처를 흔들지 않기 위해서이고, 위 감수를 되돌릴 때 값이 들어올 자리이기도 하다. 지금은
전역 설정이라 어느 워크스페이스든 같은 값이 나온다.

**키가 프로세스 안에서 살아나는 유일한 자리이므로 가림 등록도 여기서 한다**
(`utils/redaction/redactor.register_secret`). 로드와 가림이 같은 곳에 있어야 "등록을 빠뜨린 키"가
구조적으로 생기지 않는다 — 그 뒤로는 로그 포매터·예외 핸들러가 알아서 지운다.

**한 가지 예외 — 비밀이 아닌 자격 문자열**: SEC 는 API 키 대신 "연락처가 담긴 User-Agent"를
요구한다. 공개해도 무방한 식별 문자열이라 가림 대상이 아니다(가리면 오히려 로그가 못 읽힌다).
어댑터가 아니라 **이 서비스가** 읽는다는 점은 그대로다 — MD-AD-20 이 막는 것 중 유효하게 남은
절반은 "어댑터가 `settings.` 를 읽는 것"이고, 자격 주입의 소유자는 언제나 이 자리다.
"""

import datetime as _dt
from pathlib import Path

from core.exceptions import BadRequestError, ForbiddenError, HTTPError
from core.logger import logger
from providers import get_provider
from utils.env_file.env_writer import EnvWriteRejected, set_env_value
from utils.redaction.redactor import install_log_redaction, register_secret

# 소스 → `.env` 설정 이름. 이 표가 「어느 키가 어느 소스로 가나」의 유일한 정의다.
# 설정 이름 문자열이 `core/config.py` 와 이 파일 밖에 나오면 경계 검증이 실패한다.
SOURCE_KEY_SETTINGS: dict[str, str] = {
    "data_go_kr": "MARKET_DATA_GOKR_SERVICE_KEY",
    "alpaca": "MARKET_DATA_ALPACA_KEY",
    "openfigi": "MARKET_DATA_OPENFIGI_KEY",
}

# 키가 없을 때 리드가 어디서 무엇을 받아야 하는지. 소스 이름 문자열이 `providers/` 밖에 나오는
# 유일한 자리인데, 이것은 **사람에게 보여줄 안내문의 키**이지 어댑터 선택 로직이 아니다.
# (어댑터 선택은 언제나 레지스트리 조회다 — `providers/__init__.py`.)
# 절차 전문은 `.docs/5-인프라셋팅/시세-데이터-소스-키-발급.md`.
KEY_ACQUISITION_HINT: dict[str, str] = {
    "data_go_kr": "공공데이터포털(data.go.kr) 금융위원회 주식시세정보 활용신청 → 일반 인증키(Encoding)",
    "alpaca": "Alpaca 계정(paper) → API Keys → 'KEYID:SECRET' 형식으로 한 줄",
    "openfigi": "OpenFIGI(openfigi.com) → Request an API Key. 없어도 동작하며 배치 한도만 낮다",
}

# 비밀이 아니라 "우리가 누구인지"인 소스 — settings 의 연락처 문자열을 그대로 넘긴다.
#: 「연결 확인」이 물어보는 구간 — 짧게 잡는다. 키가 통하는지만 보는 호출이다.
PROBE_WINDOW_DAYS = 7

NON_SECRET_CONTACT_SOURCES = ("sec",)
CONTACT_SETTING = "MARKET_DATA_CONTACT"


class DataKeyService:
    def __init__(self, config):
        self.config = config
        # 순서가 곧 불변식이다 — 관문을 먼저 세우고 비밀을 들인다.
        install_log_redaction()
        self._register_secrets()

    def _register_secrets(self) -> None:
        """설정에 채워진 키를 전부 가림 대상으로 올린다 — 호출 한 번이라도 나가기 전에."""
        for setting in SOURCE_KEY_SETTINGS.values():
            register_secret(getattr(self.config, setting, ""))

    def get_key(self, workspace_id: int | None, source: str) -> str | None:
        """어댑터에 넘길 자격 문자열. 비어 있으면 `None` — 어댑터가 사유를 들고 스스로 막는다."""
        if source in NON_SECRET_CONTACT_SOURCES:
            return (getattr(self.config, CONTACT_SETTING, "") or "").strip() or None

        setting = SOURCE_KEY_SETTINGS.get(source)
        if setting is None:
            logger.debug(f"데이터 소스 키 조회 — workspace={workspace_id} source={source}: 키를 쓰지 않는 소스")
            return None

        value = (getattr(self.config, setting, "") or "").strip()
        if not value:
            logger.debug(f"데이터 소스 키 조회 — workspace={workspace_id} source={source}: {setting} 비어 있음")
            return None
        # 값 자체는 절대 로그에 싣지 않는다 — 있음/없음만이 로그가 알아야 할 전부다.
        register_secret(value)
        return value

    def list_key_status(self) -> list[dict]:
        """어느 키가 어디에 있고 지금 채워졌는지 — **값은 싣지 않는다.**

        화면이 「어디에 무엇을 넣어야 하나」를 답하려면 이 표가 필요하다. 지금은 그 지식이
        서비스 안에만 있어 사용자가 문서를 뒤져야 한다 (#225).

        `filled` 는 불리언이다. 앞자리 몇 글자도 내지 않는다 — 이 응답은 API 로 나가고,
        키의 일부는 전체를 좁히는 단서가 된다.
        """
        rows = [
            {
                "source": source,
                "setting": setting,
                "filled": bool((getattr(self.config, setting, "") or "").strip()),
                "secret": True,
                "guidance": KEY_ACQUISITION_HINT.get(source),
            }
            for source, setting in SOURCE_KEY_SETTINGS.items()
        ]
        rows.extend(
            {
                "source": source,
                "setting": CONTACT_SETTING,
                "filled": bool((getattr(self.config, CONTACT_SETTING, "") or "").strip()),
                # 비밀이 아니라 「우리가 누구인지」다 — 화면이 마스킹으로 감출 값이 아니다.
                "secret": False,
                "guidance": "소스가 우리를 식별하는 연락처입니다 — 비밀값이 아닙니다",
            }
            for source in NON_SECRET_CONTACT_SOURCES
        )
        return rows

    # `.env` 를 쓰는 것은 **로컬판 전용**이다 (결정 로그 2026-08-19 — 앱이 파일을 쓰므로
    # 호스팅에서는 쓰기 권한을 주지 않는다). 모르는 환경은 막는다 — fail-closed 다.
    WRITABLE_APP_ENV = "development"

    def can_write_keys(self) -> bool:
        """이 설치에서 화면이 키를 넣을 수 있는가. **모르면 False** 다."""
        return (getattr(self.config, "APP_ENV", "") or "").strip() == self.WRITABLE_APP_ENV

    def _env_path(self) -> Path:
        """이 서비스의 `.env` — 설정이 읽는 그 파일이다.

        경로를 요청이 정하지 못한다. `core/config.py` 가 `env_file=f".env.{APP_ENV}"` 를
        **cwd 상대**로 읽으므로 같은 규칙으로 만든다 (기동은 언제나 `app` 에서 한다).
        """
        return Path.cwd() / f".env.{self.WRITABLE_APP_ENV}"

    def save_key(self, source: str, value: str) -> dict:
        """소스의 키를 이 서비스의 `.env` 에 쓴다 — **변수 이름은 표에서 꺼낸다.**

        요청은 소스 id 와 값만 준다. 파일 경로도 변수 이름도 요청이 정하지 못하므로, 경로
        조작이나 임의 변수 덮어쓰기가 도달할 수 없다.

        되돌릴 사본을 남기지 않으므로(백업 미사용 판정) 쓰기는 최소다 — 그 경계는
        `utils/env_file/env_writer.py` 가 지킨다.
        """
        if not self.can_write_keys():
            raise ForbiddenError("이 설치에서는 화면으로 키를 넣을 수 없습니다 — 로컬 개발에서만 열립니다")

        setting = self._writable_setting(source)
        cleaned = value.strip()
        if not cleaned:
            raise BadRequestError("값이 비어 있습니다 — 지우려면 .env 에서 직접 지우세요")

        try:
            action = set_env_value(self._env_path(), setting, cleaned)
        except EnvWriteRejected as exc:
            # 사유는 값을 담지 않는다 (`env_writer` 의 계약) — 그대로 화면에 낸다.
            raise BadRequestError(str(exc)) from exc

        register_secret(cleaned)
        logger.info(f"데이터 소스 키 저장 — source={source} setting={setting} action={action}")
        return {"source": source, "setting": setting, "action": action, "restart_required": True}

    def _writable_setting(self, source: str) -> str:
        """쓸 수 있는 변수 이름. **표에 없으면 거부한다** — 요청이 이름을 정하지 못한다."""
        if source in NON_SECRET_CONTACT_SOURCES:
            return CONTACT_SETTING
        setting = SOURCE_KEY_SETTINGS.get(source)
        if setting is None:
            raise BadRequestError(f"{source} 는 화면에서 키를 넣을 수 있는 소스가 아닙니다")
        return setting

    # 「연결 확인」이 무엇으로 물어볼지. **시장마다 확실히 상장돼 있는 종목** 하나면 된다 —
    # 값이 맞는지가 아니라 **키가 통하는지**만 보는 호출이다.
    PROBE_SYMBOL_BY_MARKET: dict[str, str] = {
        "KOSPI": "005930",
        "KOSDAQ": "005930",
        "KONEX": "005930",
        "NASDAQ": "AAPL",
        "NYSE": "AAPL",
        "AMEX": "AAPL",
    }

    async def probe_key(self, source: str, value: str) -> dict:
        """**넣으려는 값으로** 소스에 한 번 물어본다 — 저장 전에 확인할 수 있게.

        설정에서 읽지 않고 인자로 받는 이유: 방금 `.env` 에 쓴 값은 재기동 전까지 설정에
        안 들어온다. 값을 그대로 태우면 「저장했는데 되는지 모른다」가 안 생긴다.

        호출은 **한 번**이고 결과는 통했는지·왜 안 통했는지뿐이다. 값은 응답·로그에 없다.
        """
        if not self.can_write_keys():
            raise ForbiddenError("이 설치에서는 화면으로 키를 확인할 수 없습니다 — 로컬 개발에서만 열립니다")

        self._writable_setting(source)  # 표에 없는 소스를 먼저 거부한다
        cleaned = value.strip()
        if not cleaned:
            raise BadRequestError("확인할 값이 없습니다")
        register_secret(cleaned)

        try:
            provider = get_provider(source, cleaned)
        except HTTPError:
            # 키는 쓰는데 시세 어댑터가 없는 소스가 있다 (`openfigi` — 종목 마스터 보조용).
            # 그런 소스는 확인할 호출이 없다. 404 를 화면에 내면 「고장」으로 읽힌다.
            return {"ok": False, "checked": False, "detail": f"{source} 는 확인 호출이 없는 소스입니다 — 저장만 됩니다"}

        target = self._probe_target(provider)
        if target is None:
            return {"ok": False, "checked": False, "detail": f"{source} 는 확인 호출이 없는 소스입니다 — 저장만 됩니다"}

        market, symbol = target
        date_to = _dt.date.today()
        date_from = date_to - _dt.timedelta(days=PROBE_WINDOW_DAYS)
        try:
            bars = await provider.fetch_daily(symbol, market, date_from, date_to)
        except HTTPError as exc:
            # 어댑터가 만든 사유는 사람이 읽을 문장이고 값을 담지 않는다 (`ProviderKeyMissing` 등).
            return {"ok": False, "checked": True, "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001 — 어떤 실패든 화면에 사유가 있어야 한다
            logger.warning(f"키 확인 호출 실패 — source={source} error={type(exc).__name__}")
            return {"ok": False, "checked": True, "detail": f"확인 호출이 실패했습니다 ({type(exc).__name__})"}

        # 빈 응답도 실패가 아니다 — 주말·휴장이면 봉이 없을 수 있다. 키가 막혔으면 위에서 던진다.
        return {"ok": True, "checked": True, "detail": f"{market} {symbol} 로 확인했습니다 (봉 {len(bars)}개)"}

    def _probe_target(self, provider) -> tuple[str, str] | None:
        """이 어댑터가 일봉을 주는 첫 시장과 그 시장의 확인용 종목."""
        for capability in provider.capabilities():
            if capability.data_kind != "daily_bar" or not capability.available:
                continue
            symbol = self.PROBE_SYMBOL_BY_MARKET.get(capability.market.upper())
            if symbol:
                return capability.market, symbol
        return None

    def unavailable_reason(self, source: str) -> str:
        """키가 없는 이유 + 리드가 무엇을 하면 열리는지. 화면이 그대로 보여줄 문장이다.

        **키 값도, 앞자리 몇 글자도 싣지 않는다** — 이 문장은 API 응답으로 나간다.
        """
        if source in NON_SECRET_CONTACT_SOURCES:
            return f".env 의 {CONTACT_SETTING} 에 연락처를 채우세요 (비밀값이 아닙니다 — 소스가 우리를 식별하는 문자열)"

        setting = SOURCE_KEY_SETTINGS.get(source)
        if setting is None:
            return f"{source} 는 키로 여는 소스가 아닙니다"
        hint = KEY_ACQUISITION_HINT.get(source)
        reason = f".env 의 {setting} 이 비어 있습니다"
        return f"{reason}. 발급 경로: {hint}" if hint else reason
