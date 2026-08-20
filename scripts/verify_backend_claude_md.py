"""backend CLAUDE.md 공통부 정적 검증 — 전 backend 서비스가 같은 규율 문서를 읽는지 대조.

배경: `review-backend`·`scaffold-backend` 에이전트는 대상 서비스의 `<service>/CLAUDE.md` 를 규율
소스로 읽는다. 복제본이 갈리면 서비스마다 다른 기준으로 리뷰·스캐폴드하게 되고, anti-patterns 의
"룰 번호/이름 헤더 일치" 규칙도 전제가 깨진다. 링크 한 줄로 대체하지 않는 이유는 이 파일이 에이전트
컨텍스트에 자동 주입되는 자리라서다 — 그래서 복제를 유지하되 정적 대조로 표류를 막는다
(verify_auth_lockstep.py 와 같은 철학).

파일 구조 — 마커 한 줄이 개별부/공통부를 가른다:

    # Backend CLAUDE.md

    > **이 서비스**: ...            ← 개별부(선택). 그 서비스 고유 맥락만.

    <!-- 여기부터 끝까지는 ... -->  ← 마커
    ## 환경 ...                     ← 공통부. 전 서비스 byte-identical.

검사 3가지 (대상: app/main.py 를 가진 모든 *-service — 루트 CLAUDE.md 의 "backend 폴더" 정의):
  (1) CLAUDE.md 존재
  (2) 마커 아래 공통부가 backend-service 와 byte-identical
  (3) 마커 위 개별부에 `## ` 섹션이 없음 (공통 규율과 경쟁하는 별도 규율 유입 차단)

stdlib 전용 — 의존성·env 없이 어디서든: `python3 scripts/verify_backend_claude_md.py` (cwd 무관).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SERVICE = "backend-service"
MARKER = "<!-- 여기부터 끝까지는 전 backend 서비스 공통부"
# 신규 *-service 는 glob 이 자동 흡수 — 이 목록은 삭제·이름변경 감지용 하한.
# 서비스를 의도적으로 없앨 때는 여기서도 지운다 (#244 의 file·devactivity 흡수가 그 경우였다).
EXPECTED_SERVICES = [
    "backend-service",
    "disclosure-mcp-service",
    "doc-search-mcp-service",
    "market-data-mcp-service",
    "multi-agent-service",
    "news-mcp-service",
    "portfolio-mcp-service",
    "single-agent-service",
    "template-mcp-service",
    "web-mcp-service",
]


def discover_services() -> list[str]:
    return sorted(p.parents[1].name for p in REPO_ROOT.glob("*-service/app/main.py"))


def split_at_marker(text: str) -> tuple[str, str] | None:
    """(개별부, 공통부) — 마커가 없거나 여러 개면 None."""
    parts = text.split(MARKER)
    if len(parts) != 2:
        return None
    return parts[0], MARKER + parts[1]


def check_service(service: str, reference_common: str) -> list[str]:
    path = REPO_ROOT / service / "CLAUDE.md"
    prefix = f"{service}/CLAUDE.md"
    if not path.is_file():
        return [f"{prefix}: 파일 없음 (backend 서비스는 규율 문서를 가져야 한다)"]
    split = split_at_marker(path.read_text())
    if split is None:
        return [f"{prefix}: 공통부 마커가 없거나 2개 이상 — 마커는 파일에 정확히 하나"]
    own, common = split

    problems: list[str] = []
    if common != reference_common:
        problems.append(f"{prefix}: 공통부가 {REFERENCE_SERVICE} 와 다름")
    if "\n## " in own:
        problems.append(
            f"{prefix}: 마커 위 개별부에 `## ` 섹션이 있음 (개별부는 서비스 맥락 블록만 — 규율 섹션은 공통부로)"
        )
    return problems


def main() -> int:
    reference_path = REPO_ROOT / REFERENCE_SERVICE / "CLAUDE.md"
    reference_split = split_at_marker(reference_path.read_text())
    if reference_split is None:
        print(f"{REFERENCE_SERVICE}/CLAUDE.md: 공통부 마커가 없거나 2개 이상 — 대조 불가")
        return 1
    reference_common = reference_split[1]

    services = discover_services()
    if not services:
        # 검사 0건은 통과가 아니다 — 글롭이 못 찾으면 "위반 없음"이 아니라 그물이 끊긴 것이다.
        # EXPECTED_SERVICES 하한이 대개 먼저 걸리지만, 그 목록까지 비면 조용히 초록이 되므로 여기서 막는다.
        print(
            f"backend CLAUDE.md 검사 대상 0개 — glob '*-service/app/main.py' 가 "
            f"{REPO_ROOT} 에서 아무것도 못 찾았다 (경로 규약 변경?). 검사할 게 없으면 실패다."
        )
        return 1
    problems = [f"{s}: app/main.py 미발견 (삭제·이름변경?)" for s in sorted(set(EXPECTED_SERVICES) - set(services))]
    for service in services:
        problems.extend(check_service(service, reference_common))

    if problems:
        print("backend CLAUDE.md 공통부 위반:")
        for p in problems:
            print(f"  - {p}")
        print(
            f"  → 공통부 정본은 {REFERENCE_SERVICE}/CLAUDE.md 다. 규율을 바꿨으면 전 서비스에 같은 내용을 "
            "반영하고, 새 backend 서비스면 그 공통부를 그대로 복사해 CLAUDE.md 를 만드세요."
        )
        return 1
    print(f"backend CLAUDE.md OK — 서비스 {len(services)}개의 공통부가 {REFERENCE_SERVICE} 와 동일")
    return 0


if __name__ == "__main__":
    sys.exit(main())
