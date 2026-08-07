"""로컬 기동 정의의 포트 위생 검사 — 남의 프로세스를 죽이지 않는가 + 프론트 포트 lockstep (#308).

배경: `process-compose.yaml` 의 전 프로세스가 `fuser -k {{.PORT}}/tcp` 로 시작해, 그 포트를 쓰는
것이 자기 이전 인스턴스인지 남의 프로젝트인지 구분하지 않고 죽였다. 실제로 프론트의 3000번이
다른 프로젝트 컨테이너를 죽이는 사고가 났다. 그래서 두 가지를 고정한다:

  (1) 기동 정의(process-compose.yaml·compose.*.yaml)의 **명령 영역에 포트 강탈 명령이 없다**.
      점유된 포트는 "죽이고 뺏는" 대신 바인딩 실패로 드러나야 한다(fail-closed). 이전 인스턴스가
      포트를 물고 있으면 사람이 `ss -ltnp` 로 소유자를 확인한 뒤 직접 정리한다.
      주석 줄(`#` 로 시작)은 검사 대상이 아니다 — 이 결정을 설명하는 산문이 그 안에 산다.
  (2) `process-compose.yaml` 의 프로세스 포트가 **남의 포트**(RESERVED_FOREIGN_PORTS)가 아니고,
      프론트 포트가 소비자 전부와 **lockstep** 이다: 전 서비스 `app/core/config.py` 의
      `CORS_ALLOW_ORIGINS` 기본값, `frontend/.env.example` 의 `BETTER_AUTH_URL`.
      포트를 옮길 때 소비자를 안 옮기면 로컬 CORS·인증 콜백이 조용히 깨진다 — 그 드리프트를 막는다.

**fail-closed**: 검사 대상 파일이 없거나 프로세스·서비스 수가 기대 하한 미만이면 통과가 아니라
실패다. 검사한 개수를 출력해, 초록이 "위반 없음"인지 "아무것도 안 봤음"인지 구분되게 한다.

stdlib 전용 (렉시컬 스캔 + AST, import 없음): `python3 scripts/verify_dev_port_hygiene.py` (cwd 무관).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESS_COMPOSE = "process-compose.yaml"
# 기동 정의 — 여기 명령 영역에 포트 강탈 패턴이 있으면 위반. 파일이 없으면(이름 변경·삭제) 실패한다.
STARTUP_DEFINITIONS = [PROCESS_COMPOSE, "compose.staging.yaml", "compose.prod.yaml"]
# 포트 번호만 보고 점유자를 죽이는 명령들 — 소유자를 구분하지 못한다는 것이 공통 결함이다.
PORT_KILL_PATTERNS = [
    (re.compile(r"\bfuser\s+-k\b"), "fuser -k"),
    (re.compile(r"\bpkill\b"), "pkill"),
    (re.compile(r"\bkillall\b"), "killall"),
    (re.compile(r"\bkill\s+-9\b"), "kill -9"),
    (re.compile(r"\bkill-port\b"), "kill-port"),
    (re.compile(r"\blsof\b[^\n]*\bkill\b"), "lsof | kill"),
]
# 이 레포 것이 아닌 포트 — 3000 은 Node 의 사실상 기본 포트라 다른 프로젝트와 겹친다(#308 사고).
# 로컬 프론트는 3010 을 쓴다. 여기에 포트를 추가하면 process-compose 가 그 포트를 못 쓰게 된다.
RESERVED_FOREIGN_PORTS = {3000}
# 프로세스가 지워지거나 글롭이 어긋나면 조용히 초록이 되지 않도록 하는 하한 (현재 11개).
EXPECTED_MIN_PROCESSES = 11
# app/core/config.py 를 가진 서비스 하한 (현재 10개) — verify_auth_lockstep.py 와 같은 취지.
EXPECTED_MIN_SERVICES = 10
FRONTEND_PROCESS = "frontend"

_PROCESS_HEADER_RE = re.compile(r"^  (?P<name>[A-Za-z0-9_-]+):\s*$")
_PORT_VAR_RE = re.compile(r"^\s+PORT:\s*(?P<port>\d+)\s*$")
_COMMAND_KEY_RE = re.compile(r"^\s+command:")
_LOCALHOST_ORIGIN_RE = re.compile(r"^http://localhost:(?P<port>\d+)/?$")
_BETTER_AUTH_URL_RE = re.compile(
    r'^BETTER_AUTH_URL="?http://localhost:(?P<port>\d+)/?"?\s*$'
)


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def check_no_port_kill(problems: list[str]) -> tuple[int, int]:
    """(1) 기동 정의의 비주석 줄에 포트 강탈 명령이 없는지. (검사 파일 수, 검사 줄 수) 반환."""
    files_checked = 0
    lines_checked = 0
    for name in STARTUP_DEFINITIONS:
        path = REPO_ROOT / name
        if not path.is_file():
            problems.append(
                f"{name}: 기동 정의 파일 없음 (이름 변경·삭제? 목록을 갱신할 것)"
            )
            continue
        files_checked += 1
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _is_comment(line):
                continue
            lines_checked += 1
            for pattern, label in PORT_KILL_PATTERNS:
                if pattern.search(line):
                    problems.append(
                        f"{name}:{lineno}: 포트 강탈 명령 `{label}` — 점유자를 죽이지 말고 "
                        f"바인딩 실패로 두라 (#308): {line.strip()}"
                    )
    return files_checked, lines_checked


def _parse_process_ports(problems: list[str]) -> dict[str, int]:
    """process-compose.yaml 의 프로세스별 `vars.PORT` (선언한 프로세스만)."""
    path = REPO_ROOT / PROCESS_COMPOSE
    if not path.is_file():
        problems.append(f"{PROCESS_COMPOSE}: 파일 없음")
        return {}
    ports: dict[str, int] = {}
    current: str | None = None
    commands = 0
    for line in path.read_text().splitlines():
        if _is_comment(line):
            continue
        header = _PROCESS_HEADER_RE.match(line)
        if header:
            current = header.group("name")
            continue
        if _COMMAND_KEY_RE.match(line):
            commands += 1
        port = _PORT_VAR_RE.match(line)
        if port and current is not None:
            ports[current] = int(port.group("port"))
    if commands < EXPECTED_MIN_PROCESSES:
        problems.append(
            f"{PROCESS_COMPOSE}: command 를 가진 프로세스 {commands}개 — 기대 하한 "
            f"{EXPECTED_MIN_PROCESSES}개 미만이다 (프로세스가 사라졌거나 파싱이 어긋났다)"
        )
    return ports


def check_frontend_port_lockstep(problems: list[str]) -> tuple[int | None, int]:
    """(2) 프론트 포트가 예약 포트가 아니고, 소비자 기본값과 일치하는지. (포트, 검사 서비스 수)."""
    ports = _parse_process_ports(problems)
    for name, port in sorted(ports.items()):
        if port in RESERVED_FOREIGN_PORTS:
            problems.append(
                f"{PROCESS_COMPOSE}: 프로세스 {name} 가 예약 포트 {port} 를 쓴다 — 이 레포 것이 아닌 포트다 (#308)"
            )
    frontend_port = ports.get(FRONTEND_PROCESS)
    if frontend_port is None:
        problems.append(
            f"{PROCESS_COMPOSE}: {FRONTEND_PROCESS} 프로세스의 vars.PORT 를 못 찾음 (이름 변경? 이 검사의 기준점이다)"
        )
        return None, 0

    services = sorted(REPO_ROOT.glob("*/app/core/config.py"))
    if len(services) < EXPECTED_MIN_SERVICES:
        problems.append(
            f"config.py 를 가진 서비스 {len(services)}개 — 기대 하한 {EXPECTED_MIN_SERVICES}개 "
            "미만이다 (글롭이 어긋났거나 서비스가 사라졌다)"
        )
    for path in services:
        service = path.parents[2].name
        origins = _cors_default_origins(path, service, problems)
        for origin in origins:
            match = _LOCALHOST_ORIGIN_RE.match(origin)
            if match and int(match.group("port")) != frontend_port:
                problems.append(
                    f"{service}/app/core/config.py: CORS_ALLOW_ORIGINS 기본값 {origin} 의 포트가 "
                    f"{PROCESS_COMPOSE} 의 frontend PORT({frontend_port})와 다르다"
                )

    _check_better_auth_url(frontend_port, problems)
    return frontend_port, len(services)


def _cors_default_origins(path: Path, service: str, problems: list[str]) -> list[str]:
    prefix = f"{service}/app/core/config.py"
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        problems.append(
            f"{prefix}: 파싱 불가 (SyntaxError: {exc.msg}, line {exc.lineno})"
        )
        return []
    settings = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings"),
        None,
    )
    if settings is None:
        problems.append(f"{prefix}: Settings 클래스 없음")
        return []
    for node in settings.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "CORS_ALLOW_ORIGINS"
            and isinstance(node.value, ast.List)
        ):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    problems.append(f"{prefix}: CORS_ALLOW_ORIGINS 리터럴 기본값을 못 찾음")
    return []


def _check_better_auth_url(frontend_port: int, problems: list[str]) -> None:
    path = REPO_ROOT / "frontend" / ".env.example"
    if not path.is_file():
        problems.append("frontend/.env.example: 파일 없음")
        return
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.startswith("BETTER_AUTH_URL"):
            continue
        match = _BETTER_AUTH_URL_RE.match(line.strip())
        if match is None:
            problems.append(
                f"frontend/.env.example:{lineno}: BETTER_AUTH_URL 이 http://localhost:<포트> 형태가 "
                f"아니라 대조 불가: {line.strip()}"
            )
        elif int(match.group("port")) != frontend_port:
            problems.append(
                f"frontend/.env.example:{lineno}: BETTER_AUTH_URL 포트가 {PROCESS_COMPOSE} 의 "
                f"frontend PORT({frontend_port})와 다르다"
            )
        return
    problems.append("frontend/.env.example: BETTER_AUTH_URL 줄이 없음")


def main() -> int:
    problems: list[str] = []
    files_checked, lines_checked = check_no_port_kill(problems)
    frontend_port, services_checked = check_frontend_port_lockstep(problems)

    if problems:
        print("dev 포트 위생 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"dev 포트 위생 OK — 기동 정의 {files_checked}개({lines_checked}줄)에 포트 강탈 명령 없음, "
        f"프론트 포트 {frontend_port} 가 서비스 {services_checked}개의 CORS_ALLOW_ORIGINS 기본값·"
        "frontend/.env.example 의 BETTER_AUTH_URL 과 일치"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
