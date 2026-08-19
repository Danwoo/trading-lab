"""소스명 → 어댑터 팩토리 레지스트리.

두 레지스트리를 나란히 둔다 — 시세 어댑터(`MarketDataProvider`)와 식별자 매핑 소스
(`AliasResolver`). 나눈 이유는 `providers/base.py` 의 `AliasResolver` docstring 에 적었다.

등록된 소스는 키 유무로 갈린다:

| 소스 | 키 | 이 레포에서의 역할 |
|---|---|---|
| `sec` | 불요 (연락처 User-Agent 만) | 미국 종목 마스터 + CIK 별칭 |
| `openfigi` | 불요 (있으면 한도 상향) | FIGI 별칭 매핑 |
| `data_go_kr` | **필요** | 국내 종목 마스터·일봉 |
| `alpaca` | **필요** | 미국 일봉·분봉·시세 |

키가 필요한 소스도 **등록은 된다** — 없는 것은 어댑터가 아니라 키다. 키 없이 만들어진 어댑터는
`capabilities()` 가 `available=False` + "키 없음" 사유를 돌려주고, 화면은 그 사유를 그대로
보여준다(FR-013·FR-021). 키는 `.env` 에서 오고 읽는 곳은 `services/data_key/` 하나다
(리드 결정 2026-08-07 — 워크스페이스별 암호화 저장소는 짓지 않는다).

`get_provider` 는 **키를 인자로 받는다** — 어댑터는 `settings.` 를 읽지 않는다(MD-AD-20 에서
유효하게 남은 절반). 자격 주입의 소유자를 한 자리로 묶어 두는 것이 이 시그니처의 목적이고,
그래야 키가 가림 대상으로 등록되는 지점도 하나로 유지된다(`utils/redaction/`).
"""

from collections.abc import Callable
from importlib import import_module

from core.exceptions import NotFoundError

from providers.base import AliasResolver, MarketDataProvider

ProviderFactory = Callable[[str | None], MarketDataProvider]
AliasResolverFactory = Callable[[str | None], AliasResolver]

_REGISTRY: dict[str, ProviderFactory] = {}
_ALIAS_REGISTRY: dict[str, AliasResolverFactory] = {}

# 어댑터 모듈 목록 — 등록은 import 부작용이므로 누군가 한 번은 import 해야 한다. 목록을 여기 두는
# 이유는 두 가지다: ① 소스 이름 문자열이 `providers/` 밖으로 새지 않는다(구현설계 §5.2 위험 #1),
# ② "무엇이 붙어 있나"가 코드 한 곳에서 읽힌다. `providers/__init__` 하단에서 import 하면 어댑터가
# 다시 이 모듈의 `register_provider` 를 import 하며 순환하므로, 지연 import 로 끊는다.
_SOURCE_MODULES: tuple[str, ...] = (
    # 샘플은 **키 없이** 도는 유일한 시세 소스다 (#217) — 먼저 등록해 두면
    # 키가 하나도 없는 기동에서도 캐패빌리티 표에 「가능」이 하나는 뜬다.
    "providers.sample.adapter",
    "providers.sec.adapter",
    "providers.openfigi.resolver",
    "providers.data_go_kr.adapter",
    "providers.alpaca.adapter",
    "providers.toss.adapter",
)

_loaded = False


def load_adapters() -> None:
    """어댑터 모듈을 전부 import 해 레지스트리를 채운다 (idempotent)."""
    global _loaded
    if _loaded:
        return
    for module_path in _SOURCE_MODULES:
        import_module(module_path)
    _loaded = True


def register_provider(source: str, factory: ProviderFactory) -> None:
    """어댑터 모듈이 자기 팩토리를 등록하는 진입점. 소스 이름 문자열은 `providers/` 안에서만
    정의한다(구현설계 §5.2 위험 #1) — 이 함수를 부르는 쪽(어댑터 자신)도 그 규율 안에 있다."""
    _REGISTRY[source] = factory


def register_alias_resolver(source: str, factory: AliasResolverFactory) -> None:
    """식별자 매핑 전용 소스(`AliasResolver`)의 등록 진입점 — 시세 어댑터와 레지스트리를 나눈다."""
    _ALIAS_REGISTRY[source] = factory


def list_sources() -> list[str]:
    """등록된 시세 소스 이름 목록 — capability 조회가 "무엇을 물어볼 수 있나"를 정하는 근거."""
    load_adapters()
    return sorted(_REGISTRY)


def list_alias_sources() -> list[str]:
    """등록된 식별자 매핑 소스 이름 목록."""
    load_adapters()
    return sorted(_ALIAS_REGISTRY)


def get_provider(source: str, api_key: str | None) -> MarketDataProvider:
    """등록된 소스명으로 어댑터 인스턴스를 만든다. 등록되지 않은 소스는 조용히 `None` 을 반환하지
    않고 명시적으로 실패한다 — 오타·아직 안 붙은 소스를 호출부가 바로 알아챌 수 있게."""
    load_adapters()
    try:
        factory = _REGISTRY[source]
    except KeyError:
        raise NotFoundError(f"등록되지 않은 시세 소스입니다: {source!r}") from None
    return factory(api_key)


def get_alias_resolver(source: str, api_key: str | None) -> AliasResolver:
    """등록된 식별자 매핑 소스명으로 리졸버 인스턴스를 만든다."""
    load_adapters()
    try:
        factory = _ALIAS_REGISTRY[source]
    except KeyError:
        raise NotFoundError(f"등록되지 않은 식별자 매핑 소스입니다: {source!r}") from None
    return factory(api_key)
