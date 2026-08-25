#!/usr/bin/env python3
"""정문 문서(`README.md` · 루트 `CLAUDE.md`)가 말하는 사실을 코드와 대조한다 — fail-closed.

이 그물이 존재하는 이유: 정문의 사실 주장 7건이 동시에 낡아 있었다(#329). 그중 둘은 아키텍처
규칙(「어떤 서비스도 외부 금융 API 를 직접 안 부른다」)과 안전 주장(「출처 없는 수치는 막는다」)이라
읽는 사람을 **틀린 자리로 보냈다.** 사람이 손으로 고치는 것 말고 갱신 경로가 없어서 낡은 것이다.

`verify_stage_claims.py` 가 제품 **단계** 주장을 잠그듯, 여기서는 정문의 **인벤토리와 규칙** 주장을
잠근다. 그쪽은 독스트링에 정문을 적어 놓고도 실제로는 `stages.ts` 와 `modules.py` 만 읽는다.

## 무엇을 잠그나 (셀 수 있는 것)

A. **서비스 표 전수** — README 표의 이름·포트 ↔ `*/app/main.py` 실재 + `process-compose.yaml` 의
   `PORT`. 표에 없는 서비스 디렉터리가 있으면 실패한다(#329 ④ — `bot-agent-service` 가 그렇게
   빠져 있었다). 반대로 표에 있는데 디렉터리가 없어도 실패한다.
B. **「마지막 N 개는 process-compose 에 없다」** — 그 N 과 실제 부재 개수, 그리고 그것들이 표의
   **마지막 N 행**인지까지 센다(#329 ④ — 실제로 셋인데 「둘」이라 적혀 있었다).
C. **루트 `CLAUDE.md` 의 backend 모듈 목록** ↔ `modules.py` 등록 라우터 전수 + 개수(#329 ⑥ —
   14개 중 8개만 적혀 있었다).
D. **코드가 거짓으로 만드는 문구** — 아래 `FALSIFIED` 의 각 항목은 「이 증거가 성립하면 이 문구는
   거짓」이라는 쌍이다. 증거는 매번 코드에서 계산한다(#329 ①②⑤⑦).
E. **정문이 이름으로 부르는 CI 잡** — README 가 백틱으로 인용한 `` `test: …` `` 잡 이름은
   워크플로에 실재해야 한다. 잡을 통합·개명하면 정문이 조용히 낡는다 (실측 2026-08-25:
   `test: repo-lint` 를 `test: repo` 라고 적은 문장이 리뷰에서 잡혔다 — 그때 이 축이 없었다).

## 무엇을 못 잡나 (정직하게)

- **D 는 문구 단위다.** 같은 거짓말을 다른 낱말로 다시 쓰면 못 잡는다. 여기서 잡는 것은 「고친
  것이 되돌아오는 것」이지 「거짓의 의미」가 아니다. 의미를 세려면 문서를 파싱해야 하는데, 그건
  이 그물이 감당할 층이 아니다.
- **#329 ③(리서치 챗에 LLM 키가 필요하다)은 그물 밖이다.** 「키 없이 답한다」의 반례는 런타임
  사실(닿지 않는 주소로 나간다)이라 정적으로 셀 수 없다. `.env.example` 의 기본 주소가
  RFC 5737 인지 정도는 셀 수 있지만, 그 주소가 바뀌어도 「키가 필요하다」는 사실은 그대로다 —
  즉 세는 대상이 주장과 다르다. 이 항목은 사람이 지키는 것으로 남는다.

    python3 scripts/verify_front_door_claims.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
ROOT_CLAUDE = REPO_ROOT / "CLAUDE.md"
PROCESS_COMPOSE = REPO_ROOT / "process-compose.yaml"
MODULES = REPO_ROOT / "backend-service" / "app" / "modules.py"
AGENT_SERVICE = REPO_ROOT / "multi-agent-service" / "app" / "services" / "agent" / "agent_service.py"
PROVIDERS = REPO_ROOT / "backend-service" / "app" / "providers"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
FRONTEND = REPO_ROOT / "frontend"

#: 서비스 디렉터리인데 `app/main.py` 가 없는 것 — 표에는 있어야 한다.
EXTRA_SERVICE_DIRS = {"frontend"}

#: README 서비스 표의 한 행: 이름(백틱)과 4자리 포트. 데모 계정 표는 2열이 포트가 아니라 안 걸린다.
TABLE_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|\s*(\d{4})\s*\|", re.M)
#: process-compose 의 프로세스 키와 그 아래 `PORT: <n>`
PC_BLOCK_RE = re.compile(r"^  ([a-z0-9-]+):\s*$(.*?)(?=^  [a-z0-9-]+:\s*$|\Z)", re.M | re.S)
PC_PORT_RE = re.compile(r"^\s+PORT:\s*(\d+)\s*$", re.M)
#: "The last three aren't in `process-compose.yaml`"
LAST_N_RE = re.compile(r"The last (one|two|three|four|five|six) (?:aren't|isn't) in `process-compose\.yaml`")
WORD_TO_INT = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
#: README 가 백틱으로 부르는 CI 잡 이름 — `` `test: repo-lint` `` 처럼.
README_TEST_JOB_RE = re.compile(r"`(test: [a-z0-9-]+)`")
#: 워크플로 잡의 `name: "test: …"` (홑·겹따옴표·맨따옴표 전부)
WORKFLOW_JOB_NAME_RE = re.compile(r'^\s{4}name:\s*["\']?(test: [^"\'\n]+?)["\']?\s*$', re.M)
#: modules.py 의 `"routers.<도메인>.<모듈>"`
ROUTER_RE = re.compile(r'"routers\.([a-z_]+)\.[a-z_]+"')
#: 루트 CLAUDE.md 의 backend-service 불릿과 그 안의 "등록된 **14개가 전부**"
BACKEND_BULLET_RE = re.compile(r"^- `backend-service` \(:8000\).*$", re.M)
MODULE_COUNT_RE = re.compile(r"등록된 \*\*(\d+)개가 전부\*\*")


def _providers_calling_vendors_directly() -> int:
    """`app/providers/<소스>/client.py` 중 외부 https 주소를 상수로 든 것의 수."""
    return sum(
        1
        for client in sorted(PROVIDERS.glob("*/client.py"))
        if 'BASE_URL = "https' in client.read_text(encoding="utf-8")
    )


def _answer_leaves_before_grounding_is_counted() -> bool:
    """답이 이미 스트림으로 나간 **뒤에** 근거를 센다 = 구조적으로 차단일 수 없다."""
    text = AGENT_SERVICE.read_text(encoding="utf-8").splitlines()
    first_text_event = next((i for i, line in enumerate(text) if "yield text_event(" in line), None)
    first_no_evidence = next((i for i, line in enumerate(text) if '"no_evidence"' in line), None)
    if first_text_event is None or first_no_evidence is None:
        return False
    return first_text_event < first_no_evidence


def _ci_scans_for_credentials() -> bool:
    return any("gitleaks" in path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml")))


def _frontend_calls_bot_agent() -> int:
    hits = 0
    for path in sorted(FRONTEND.rglob("*.ts")) + sorted(FRONTEND.rglob("*.tsx")):
        if "node_modules" in path.parts or "tests" in path.parts:
            continue
        if "BOT_AGENT_SERVICE_URL" in path.read_text(encoding="utf-8"):
            hits += 1
    return hits


#: (문서, 코드가 거짓으로 만드는 문구, 증거 설명, 증거 판정)
FALSIFIED: list[tuple[Path, str, str, callable]] = [
    (
        README,
        "no service calls an external financial API directly",
        "app/providers/*/client.py 가 벤더 https 주소를 직접 든다",
        lambda: _providers_calling_vendors_directly() > 0,
    ),
    (
        README,
        "unsourced figures are blocked",
        "agent_service 가 답을 먼저 내보낸 뒤 근거를 센다 (차단 불가)",
        _answer_leaves_before_grounding_is_counted,
    ),
    (
        README,
        "CI blocks credential patterns",
        ".github/workflows 에 gitleaks 가 없다",
        lambda: not _ci_scans_for_credentials(),
    ),
    (
        ROOT_CLAUDE,
        "프론트가 아직 안 부른다",
        "frontend 가 BOT_AGENT_SERVICE_URL 을 참조한다",
        lambda: _frontend_calls_bot_agent() > 0,
    ),
]

#: 증거가 성립할 때 정문이 **반드시** 짚어야 하는 자리 (문구를 지우고 끝내는 것을 막는다)
REQUIRED: list[tuple[Path, str, str, callable]] = [
    (
        README,
        "backend-service/app/providers/",
        "적재용 시세 어댑터가 벤더를 직접 부른다 — 정문이 그 자리를 짚어야 한다",
        lambda: _providers_calling_vendors_directly() > 0,
    ),
]


def _service_dirs() -> set[str]:
    return {p.parent.parent.name for p in REPO_ROOT.glob("*/app/main.py")} | EXTRA_SERVICE_DIRS


def _compose_ports() -> dict[str, int]:
    """process-compose 의 프로세스 → 포트. 키는 서비스 디렉터리 이름으로 정규화한다."""
    text = PROCESS_COMPOSE.read_text(encoding="utf-8")
    ports: dict[str, int] = {}
    for name, body in PC_BLOCK_RE.findall(text):
        port = PC_PORT_RE.search(body)
        if not port:
            continue
        directory = name if (REPO_ROOT / name).is_dir() else f"{name}-service"
        ports[directory] = int(port.group(1))
    return ports


def main() -> int:
    for path in (README, ROOT_CLAUDE, PROCESS_COMPOSE, MODULES, AGENT_SERVICE):
        if not path.is_file():
            print(f"::error::필수 경로가 없습니다: {path} — fail-closed 종료", file=sys.stderr)
            return 1
    for directory in (PROVIDERS, WORKFLOWS, FRONTEND):
        if not directory.is_dir():
            print(f"::error::필수 경로가 없습니다: {directory} — fail-closed 종료", file=sys.stderr)
            return 1

    readme = README.read_text(encoding="utf-8")
    violations: list[str] = []

    # ── A. 서비스 표 전수 ────────────────────────────────────────────────────
    table = [(name, int(port)) for name, port in TABLE_ROW_RE.findall(readme)]
    if not table:
        print("::error::README 서비스 표에서 0행을 찾았습니다 — 표 모양이 바뀌었을 수 있습니다", file=sys.stderr)
        return 1
    listed = {name for name, _ in table}
    actual = _service_dirs()
    if not actual:
        print("::error::`*/app/main.py` 를 0건 찾았습니다 — fail-closed 종료", file=sys.stderr)
        return 1
    for missing in sorted(actual - listed):
        violations.append(f"서비스 표에 `{missing}` 이 없습니다 — 실재하는 서비스는 정문에 다 적힌다")
    for ghost in sorted(listed - actual):
        violations.append(f"서비스 표의 `{ghost}` 에 해당하는 디렉터리가 없습니다")

    compose_ports = _compose_ports()
    for name, port in table:
        declared = compose_ports.get(name)
        if declared is not None and declared != port:
            violations.append(f"`{name}` 포트가 갈렸습니다 — README {port} vs process-compose {declared}")
        elif declared is None:
            service_readme = REPO_ROOT / name / "README.md"
            if service_readme.is_file() and str(port) not in service_readme.read_text(encoding="utf-8"):
                violations.append(
                    f"`{name}` 은 process-compose 에 없는데 {name}/README.md 에도 포트 {port} 가 없습니다"
                )

    # ── B. 「마지막 N 개는 process-compose 에 없다」 ─────────────────────────
    last_n = LAST_N_RE.search(readme)
    if not last_n:
        violations.append("README 에서 「The last N aren't in `process-compose.yaml`」 문장을 못 찾았습니다")
    else:
        claimed = WORD_TO_INT[last_n.group(1)]
        absent = [name for name, _ in table if name not in compose_ports]
        if len(absent) != claimed:
            violations.append(
                f"process-compose 에 없는 서비스는 {len(absent)}개({', '.join(absent)})인데 README 는 {claimed}개라고 말합니다"
            )
        tail = [name for name, _ in table[-claimed:]]
        if sorted(tail) != sorted(absent):
            violations.append(f"「마지막 {claimed}개」가 실제 부재 목록과 다릅니다 — 표 끝 {tail} vs 부재 {absent}")

    # ── C. 루트 CLAUDE.md 의 backend 모듈 목록 ──────────────────────────────
    registered = sorted(set(ROUTER_RE.findall(MODULES.read_text(encoding="utf-8"))))
    if not registered:
        print("::error::modules.py 에서 라우터 0건을 찾았습니다 — fail-closed 종료", file=sys.stderr)
        return 1
    root_claude = ROOT_CLAUDE.read_text(encoding="utf-8")
    bullet = BACKEND_BULLET_RE.search(root_claude)
    if not bullet:
        violations.append("루트 CLAUDE.md 에서 backend-service 불릿을 못 찾았습니다")
    else:
        bullet_text = bullet.group(0)
        count = MODULE_COUNT_RE.search(bullet_text)
        if not count:
            violations.append("backend-service 불릿에 「등록된 **N개가 전부**」가 없습니다 — 개수를 못 셉니다")
        elif int(count.group(1)) != len(registered):
            violations.append(
                f"backend-service 모듈 수가 갈렸습니다 — CLAUDE.md {count.group(1)}개 vs modules.py {len(registered)}개"
            )
        for domain in registered:
            if f"`{domain}`" not in bullet_text:
                violations.append(f"backend-service 불릿에 모듈 `{domain}` 이 없습니다")

    # ── E. 정문이 이름으로 부르는 CI 잡이 실재하는가 ────────────────────────
    declared_jobs: set[str] = set()
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        declared_jobs.update(WORKFLOW_JOB_NAME_RE.findall(wf.read_text(encoding="utf-8")))
    if not declared_jobs:
        print("::error::워크플로에서 `test: ` 잡 이름을 0건 찾았습니다 — fail-closed 종료", file=sys.stderr)
        return 1
    named_in_readme = sorted(set(README_TEST_JOB_RE.findall(readme)))
    for name in named_in_readme:
        if name not in declared_jobs:
            violations.append(
                f"README 가 부르는 CI 잡 `{name}` 이 워크플로에 없습니다 — "
                f"실재하는 이름: {', '.join(sorted(declared_jobs))}"
            )

    # ── D. 코드가 거짓으로 만드는 문구 ──────────────────────────────────────
    for path, phrase, why, evidence in FALSIFIED:
        if evidence() and phrase in path.read_text(encoding="utf-8"):
            violations.append(f"{path.name}: 「{phrase}」 — {why}")
    for path, needle, why, evidence in REQUIRED:
        if evidence() and needle not in path.read_text(encoding="utf-8"):
            violations.append(f"{path.name}: 「{needle}」 를 짚지 않습니다 — {why}")

    print(
        f"서비스 표 {len(table)}행 · 실재 서비스 {len(actual)}개 · backend 모듈 {len(registered)}개 · "
        f"문구 대조 {len(FALSIFIED) + len(REQUIRED)}건 · "
        f"정문이 부르는 CI 잡 {len(named_in_readme)}건 ↔ 선언된 잡 {len(declared_jobs)}개"
    )
    for line in violations:
        print(f"::error::{line}", file=sys.stderr)
    if violations:
        print("::error::정문 문서가 코드와 어긋납니다 — README.md·CLAUDE.md 를 고치세요 (#329)", file=sys.stderr)
        return 1
    print("위반 0건 — 정문이 말하는 인벤토리와 규칙이 코드와 맞습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
