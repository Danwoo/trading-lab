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

from core.logger import logger
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
