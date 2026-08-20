"""인증 lockstep 정적 검증 — 전 서비스 security.py·auth_context.py 동일본 + config.py 강화 델타.

배경: 62194b9 인증 강화(fail-closed·Authorization 헤더 전용·서비스 토큰 typ·AUTH_DEV_BYPASS opt-in)는
backend-service 가 SoT 이고 전 backend 서비스가 이와 동일해야 한다. 서비스별 행동 검증 스크립트를
복사하는 대신 SoT 와의 정적 대조 1개로 표류를 막는다 (verify_mcp_lockstep.py·schema-parity 와 같은 철학).
행동 검증(무효 토큰 401, query param 미수용 등)은 multi-agent-service/scripts/verify_auth_hardening.py 가
담당 — 대상 파일이 byte-identical 이므로 한 서비스의 행동 검증이 전 서비스를 대표한다.

검사 4가지 (대상: app/core/security.py 를 가진 모든 *-service):
  (1) app/core/security.py·auth_context.py 가 backend-service 와 byte-identical
  (1') REPLICA_GROUPS 에 선언된 `members` 가 byte-identical (#256 — 목록 자체가 "이건
       복제본이다" 라는 문서다. 파일이 하나라도 없으면 통과가 아니라 위반 — fail-closed).
       그리고 **선언된 `members`·`known_divergent` 밖에서 같은 상대경로에 파일을 가진 서비스가
       glob 으로 새로 발견되면 그 자체를 위반으로 본다** — 새 파일이 기존 내용과 같은지 다른지는
       안 본다, 존재 자체가 "선언 안 된 무언가가 생겼다"는 신호이기 때문이다 (#290 — 손으로 쓴
       서비스 목록 밖에 심어진 3번째 복제본이 검사를 피해가던 구멍. `known_divergent` 는 처음부터
       의도적으로 다른 구현이라고 확인된 서비스를 명시적으로 예외 처리한 것 — 예: middlewares.py 는
       backend-service·single-agent-service 가 자체 미들웨어 스택을 쓴다).
  (1'') REPLICA_GROUPS 밖에서 서비스 2개 이상에 byte-identical 로 존재하는 app/ 하위 .py 파일을
       찾아 위반으로 보고한다 (#290 — "미선언 복제군" 자체가 검사 밖에 있던 구멍. 이 레포에서
       반복된 부류: CLAUDE.md 4종·exception_handler.py·database_utils.py 처럼 목록에 없는 복제가
       계속 생겨왔다). 오탐 방지: byte-identical 인 것만 잡는다 — config.py·main.py 처럼 같은
       이름이라도 서비스마다 내용이 다르게 설계된 파일은 해시가 갈리므로 걸리지 않는다.
  (2) app/core/config.py 에 강화 델타 존재 (AST — 파싱 불가면 traceback 대신 위반으로 보고):
      - APP_ENV 기본값 "production" (미설정 배포가 fail-open dev 우회로 서는 사고 차단)
      - env_file=f".env.{os.getenv('APP_ENV', 'production')}" 의 fallback 리터럴도 "production"
        (기본값만 맞고 이 fallback 이 'development' 로 표류하면 APP_ENV 미설정 시 dev env 를 물어 fail-open).
        검사는 env_file 키워드의 값 서브트리로 한정 — 클래스 안 다른 APP_ENV getenv 필드에 좌표가 밀려
        env_file 표류를 놓치는 fail-open 거짓음성을 막는다.
      - AUTH_DEV_BYPASS: bool = False 필드 (dev 우회는 opt-in)
      - _forbid_dev_bypass_outside_dev validator (비-dev 에서 bypass=true 기동 거부)

stdlib 전용 (AST 파싱, import 없음) — 의존성·env 없이 어디서든:
`python3 scripts/verify_auth_lockstep.py` (cwd 무관).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SERVICE = "backend-service"
AUTH_FILES = ["security.py", "auth_context.py"]
BYPASS_VALIDATOR = "_forbid_dev_bypass_outside_dev"
# 인증 외 복제 파일군 — `members` 는 이 상대경로에서 byte-identical 이어야 하는 서비스들
# (#256). `known_divergent` 는 같은 경로에 파일이 있지만 의도적으로 다른 구현을 쓰는 것으로
# 확인된 서비스 — 복제군이 아니라고 명시적으로 인정하는 것이지, 조용히 빼먹는 것이 아니다
# (여기 없는 서비스가 이 경로에 새 파일을 갖게 되면 known_divergent 로도 안 걸러지므로
# 위반으로 뜬다 — #290). 실측(2026-08) 전수 스캔으로 발견 — database_utils.py 외 나머지는
# #290 에서 미선언 상태로 검사 밖에 있던 것들 (retry_utils.py·time_utils.py 는 9벌,
# exceptions.py·exception_handler.py·logger.py·middlewares.py 는 10벌까지 있었다). 새 복제를
# 만들거나 없애면 이 목록을 함께 고친다 — 그 전엔 (1'') 의 미선언 스캔이 빨갛게 대신 알려준다.
REPLICA_GROUPS: dict[str, dict[str, list[str]]] = {
    "app/utils/common/database_utils.py": {
        "members": ["backend-service", "multi-agent-service"],
    },
    "app/utils/common/retry_utils.py": {
        "members": [
            "backend-service",
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "multi-agent-service",
            "news-mcp-service",
            "portfolio-mcp-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
    },
    "app/utils/common/time_utils.py": {
        "members": [
            "backend-service",
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "multi-agent-service",
            "news-mcp-service",
            "portfolio-mcp-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
    },
    "app/utils/common/few_shot.py": {
        "members": [
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "news-mcp-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
    },
    "app/utils/common/staged_search.py": {
        "members": [
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "news-mcp-service",
            "template-mcp-service",
        ],
    },
    "app/core/exceptions.py": {
        "members": [
            "backend-service",
            "bot-agent-service",
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "multi-agent-service",
            "news-mcp-service",
            "portfolio-mcp-service",
            "single-agent-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
    },
    "app/core/exception_handler.py": {
        "members": [
            "backend-service",
            "bot-agent-service",
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "multi-agent-service",
            "news-mcp-service",
            "portfolio-mcp-service",
            "single-agent-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
    },
    "app/core/logger.py": {
        "members": [
            "backend-service",
            "bot-agent-service",
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "multi-agent-service",
            "news-mcp-service",
            "portfolio-mcp-service",
            "single-agent-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
    },
    "app/core/mcp_token.py": {
        "members": ["backend-service", "multi-agent-service"],
    },
    # middlewares.py·mcp_auth.py — backend-service(통합 앱)·single-agent-service(경량 구성)는
    # 처음부터 자체 미들웨어/토큰 흐름을 쓴다 (전자는 미들웨어가 더 많고, 후자는 onbehalf 테넌트
    # 토큰 대신 단순 서비스 토큰을 쓴다) — known_divergent 로 명시해 위반이 아니라고 밝힌다.
    "app/core/middlewares.py": {
        "members": [
            "disclosure-mcp-service",
            "doc-search-mcp-service",
            "market-data-mcp-service",
            "multi-agent-service",
            "news-mcp-service",
            "portfolio-mcp-service",
            "template-mcp-service",
            "web-mcp-service",
        ],
        "known_divergent": ["backend-service", "bot-agent-service", "single-agent-service"],
    },
    "app/clients/mcp/mcp_auth.py": {
        "members": ["backend-service", "multi-agent-service"],
        "known_divergent": ["single-agent-service"],
    },
}
# 미선언 복제 스캔에서 제외할 상대경로 — 이미 전용 검사(check_byte_identical)가 있어 (1'')
# 이 다시 잡으면 같은 위반이 두 번 보고된다.
_AUTH_LOCKSTEP_RELATIVE_PATHS = {f"app/core/{name}" for name in AUTH_FILES}
# 미선언 복제 스캔이 무시할 파일 크기 — 이 바이트 미만은 우연히 같은 빈 스텁일 가능성이 커
# 노이즈가 된다 (실측 최소 실파일 324바이트 — 20은 여유를 넉넉히 둔 하한).
_TRIVIAL_FILE_BYTES = 20
# 신규 *-service 는 glob 이 자동 흡수 — 이 목록은 security.py 삭제·이름변경 감지용 하한
EXPECTED_SERVICES = [
    "backend-service",
    "multi-agent-service",
    "portfolio-mcp-service",
    "market-data-mcp-service",
    "disclosure-mcp-service",
    "news-mcp-service",
    "web-mcp-service",
    "doc-search-mcp-service",
    "single-agent-service",
    "template-mcp-service",
]


def discover_services() -> list[str]:
    return sorted(p.parents[2].name for p in REPO_ROOT.glob("*-service/app/core/security.py"))


def check_byte_identical(services: list[str]) -> list[str]:
    problems: list[str] = []
    for name in AUTH_FILES:
        reference = (REPO_ROOT / REFERENCE_SERVICE / "app" / "core" / name).read_bytes()
        for service in services:
            if service == REFERENCE_SERVICE:
                continue
            path = REPO_ROOT / service / "app" / "core" / name
            if not path.is_file():
                problems.append(f"{service}/app/core/{name}: 파일 없음")
            elif path.read_bytes() != reference:
                problems.append(f"{service}/app/core/{name}: {REFERENCE_SERVICE} 와 내용 다름")
    return problems


def _services_with_relative_path(relative_path: str) -> list[str]:
    """relative_path 를 실제로 가진 서비스 목록 — 매 실행 손으로 안 세고 glob 으로 다시 찾는다."""
    return sorted(
        p.parents[len(Path(relative_path).parts) - 1].name for p in REPO_ROOT.glob(f"*-service/{relative_path}")
    )


def check_replica_groups() -> list[str]:
    problems: list[str] = []
    for relative_path, spec in REPLICA_GROUPS.items():
        members = spec["members"]
        known_divergent = set(spec.get("known_divergent", []))
        if len(members) < 2:
            problems.append(
                f"REPLICA_GROUPS[{relative_path}]: members {len(members)}개 — 복제군이 아니다 (목록 정비 필요)"
            )
            continue
        reference_service, *others = members
        reference_path = REPO_ROOT / reference_service / relative_path
        if not reference_path.is_file():
            problems.append(f"{reference_service}/{relative_path}: SoT 파일 없음")
            continue
        reference = reference_path.read_bytes()
        for service in others:
            path = REPO_ROOT / service / relative_path
            if not path.is_file():
                problems.append(f"{service}/{relative_path}: 파일 없음")
            elif path.read_bytes() != reference:
                problems.append(f"{service}/{relative_path}: {reference_service} 와 내용 다름")
        # members·known_divergent 밖에서 같은 경로에 파일을 가진 서비스가 새로 나타났다 —
        # 내용이 같은지는 안 본다, 선언 안 된 존재 자체가 위반이다 (#290 의 3번째 복제본 구멍).
        discovered = set(_services_with_relative_path(relative_path))
        unexpected = discovered - set(members) - known_divergent
        if unexpected:
            problems.append(
                f"{relative_path}: 선언 안 된 서비스에도 파일 존재 {sorted(unexpected)} — "
                "REPLICA_GROUPS members/known_divergent 갱신 필요 (#290)"
            )
    return problems


def check_undeclared_replicas() -> list[str]:
    """REPLICA_GROUPS·AUTH_FILES 밖에서 byte-identical 로 서비스 2개 이상에 존재하는 .py 파일 (#290).

    복제 자체는 잡을 가치와 무관하다 — "이건 복제본이다"라고 아무도 선언하지 않은 채로
    존재하는 것이 문제다(그래야 한쪽만 고치는 드리프트가 조용히 난다). config.py·main.py 처럼
    서비스마다 내용이 다르게 설계된 동명 파일은 해시가 갈려 여기 걸리지 않는다.
    """
    declared = set(REPLICA_GROUPS) | _AUTH_LOCKSTEP_RELATIVE_PATHS
    by_relative_path: dict[str, dict[str, bytes]] = {}
    scanned = 0
    for app_dir in sorted(REPO_ROOT.glob("*-service/app")):
        service = app_dir.parent.name
        for path in sorted(app_dir.rglob("*.py")):
            relative_path = str(path.relative_to(REPO_ROOT / service))
            if relative_path in declared:
                continue
            size = path.stat().st_size
            if size < _TRIVIAL_FILE_BYTES:
                continue
            scanned += 1
            by_relative_path.setdefault(relative_path, {})[service] = path.read_bytes()

    problems: list[str] = []
    for relative_path, by_service in by_relative_path.items():
        by_hash: dict[bytes, list[str]] = {}
        for service, content in by_service.items():
            by_hash.setdefault(content, []).append(service)
        for services in by_hash.values():
            if len(services) >= 2:
                problems.append(
                    f"미선언 복제군: {relative_path} — {sorted(services)} 가 byte-identical인데 "
                    "REPLICA_GROUPS 에 없다 (선언하거나 의도적으로 다르게 만들 것)"
                )
    if scanned == 0:
        problems.append("미선언 복제 스캔: 대상 .py 파일 0건 — *-service/app 글롭이 어긋났다")
    return problems


def _field_defaults(settings: ast.ClassDef) -> dict[str, ast.expr]:
    """Settings 본문의 `이름: 타입 = 기본값` 클래스 필드를 {이름: 기본값 expr} 로 수집."""
    out: dict[str, ast.expr] = {}
    for node in settings.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            out[node.target.id] = node.value
    return out


def _env_file_value(settings: ast.ClassDef) -> ast.expr | None:
    """Settings 의 env_file 설정값 expr (없으면 None).

    현행 pydantic v2 idiom 인 `model_config = SettingsConfigDict(env_file=..., ...)` 의
    env_file 키워드 인자, 또는 구식 내부 `class Config: env_file = ...` 대입값을 찾는다.
    """
    for node in ast.walk(settings):
        if isinstance(node, ast.keyword) and node.arg == "env_file":
            return node.value
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "env_file" for t in node.targets):
            return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "env_file"
            and node.value is not None
        ):
            return node.value
    return None


def _app_env_fallback(subtree: ast.expr) -> ast.expr | None:
    """주어진 서브트리 안 os.getenv("APP_ENV", <fallback>) 의 두 번째 인자 expr (없으면 None).

    env_file=f".env.{os.getenv('APP_ENV', 'production')}" 의 fallback 리터럴 — 이쪽만
    'development' 로 표류하면 APP_ENV 미설정 배포가 dev env 파일을 물어 fail-open 이 된다.
    클래스 전체가 아니라 env_file 서브트리로 한정해야 다른 APP_ENV getenv 에 좌표가
    밀리지 않는다 (첫-매칭 반환의 fail-open 거짓음성 방지).
    """
    for node in ast.walk(subtree):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        func = node.func
        is_getenv = (isinstance(func, ast.Attribute) and func.attr == "getenv") or (
            isinstance(func, ast.Name) and func.id == "getenv"
        )
        first = node.args[0]
        if is_getenv and isinstance(first, ast.Constant) and first.value == "APP_ENV":
            return node.args[1]
    return None


def check_config_delta(service: str) -> list[str]:
    path = REPO_ROOT / service / "app" / "core" / "config.py"
    prefix = f"{service}/app/core/config.py"
    if not path.is_file():
        return [f"{prefix}: 파일 없음"]
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        return [f"{prefix}: 파싱 불가 (SyntaxError: {exc.msg}, line {exc.lineno})"]
    settings = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings"),
        None,
    )
    if settings is None:
        return [f"{prefix}: Settings 클래스 없음"]

    problems: list[str] = []
    defaults = _field_defaults(settings)
    app_env = defaults.get("APP_ENV")
    if not (isinstance(app_env, ast.Constant) and app_env.value == "production"):
        problems.append(f'{prefix}: APP_ENV 기본값이 "production" 이 아님')
    env_file = _env_file_value(settings)
    if env_file is None:
        problems.append(f"{prefix}: model_config 에 env_file 설정 없음")
    else:
        fallback = _app_env_fallback(env_file)
        if fallback is None:
            problems.append(
                f'{prefix}: env_file 에서 os.getenv("APP_ENV", <리터럴>) fallback 을 '
                "인식 못 함 (누락이거나 인식 못 하는 형태)"
            )
        elif not (isinstance(fallback, ast.Constant) and fallback.value == "production"):
            problems.append(f'{prefix}: env_file fallback 이 "production" 이 아님 (미설정 배포가 dev env 로 fail-open)')
    bypass = defaults.get("AUTH_DEV_BYPASS")
    if not (isinstance(bypass, ast.Constant) and bypass.value is False):
        problems.append(f"{prefix}: AUTH_DEV_BYPASS: bool = False 필드 없음")
    if not any(isinstance(n, ast.FunctionDef) and n.name == BYPASS_VALIDATOR for n in settings.body):
        problems.append(f"{prefix}: {BYPASS_VALIDATOR} validator 없음")
    return problems


def main() -> int:
    services = discover_services()
    problems = [
        f"{s}: app/core/security.py 미발견 (삭제·이름변경?)" for s in sorted(set(EXPECTED_SERVICES) - set(services))
    ]
    problems.extend(check_byte_identical(services))
    problems.extend(check_replica_groups())
    problems.extend(check_undeclared_replicas())
    for service in services:
        problems.extend(check_config_delta(service))

    if problems:
        print("auth lockstep 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    replica_files = sum(len(spec["members"]) for spec in REPLICA_GROUPS.values())
    print(
        f"auth lockstep OK — 서비스 {len(services)}개의 security.py·auth_context.py 가 {REFERENCE_SERVICE} 와 동일, "
        f"복제 파일군 {len(REPLICA_GROUPS)}종({replica_files}개 파일) 동일, 미선언 복제 없음, "
        f'config.py 델타(APP_ENV "production" 기본·AUTH_DEV_BYPASS 필드·{BYPASS_VALIDATOR} validator) 전부 존재'
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
