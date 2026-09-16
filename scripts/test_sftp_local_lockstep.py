"""로컬 SFTP 의 세 자리가 같은 것을 말하는지 대조한다 — fail-closed (stdlib 전용).

## 왜 있나

`#436 F28` 은 「서버는 떠 있는데 인증만 실패한다」였다. 그 상태는 화면에서 「파일 기능이
없는 것」과 구별되지 않는다 — 업로드가 안 되는 이유를 아무도 말해 주지 않기 때문이다.

같은 사실이 세 곳에 흩어져 있어서 벌어진 일이다:

  1. `platform/sftp/compose.yaml` — 컨테이너가 **실제로 만드는** 계정·포트·디렉터리
  2. `scripts/bootstrap_local_env.py` 의 `LOCAL_SFTP_CREDENTIALS` — `.env.development` 에 **써 넣는** 값
  3. `backend-service/app/.env.example` 의 `SFTP_*` — 앱이 **읽는** 좌표의 본보기

1 이 SoT 다 (staging+ 의 `compose.staging.yaml`·`compose.prod.yaml` 도 그 파일이 만드는
external 네트워크에 붙는다). 2·3 이 1 과 어긋나면 컨테이너는 정상이고 앱만 못 붙는데, 그
실패는 런타임의 인증 오류로만 드러난다. 이 그물은 그 어긋남을 커밋 시점에 잡는다.

`process-compose.yaml` 의 `sftp` 프로세스가 **그 compose 파일을 부르는지**도 함께 본다 —
정의를 옮겨 적으면 1 이 둘이 되어 대조의 뜻이 사라진다.

## 무엇을 대조하지 않나

**실제로 접속되는지는 보지 않는다.** 도커가 없는 CI 러너에서도 돌아야 하고, 이 파일이 답하는
질문은 「세 자리가 같은 말을 하는가」이지 「지금 그 서버가 살아 있는가」가 아니다.

    python3 scripts/test_sftp_local_lockstep.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESS_COMPOSE = REPO_ROOT / "process-compose.yaml"
SFTP_COMPOSE = REPO_ROOT / "platform" / "sftp" / "compose.yaml"
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap_local_env.py"
BACKEND_EXAMPLE = REPO_ROOT / "backend-service" / "app" / ".env.example"

# atmoz/sftp 의 사용자 지정: `사용자:비밀번호:uid:gid:디렉터리` (uid·gid 는 비울 수 있다).
USER_SPEC_RE = re.compile(
    r"^\s*(?P<user>[A-Za-z0-9_.-]+):(?P<password>[^:\s]+):[^:\s]*:[^:\s]*:(?P<dir>[A-Za-z0-9_./-]+)\s*$", re.M
)
PUBLISH_RE = re.compile(r"^\s*-\s*\"?(?P<host>\d+):(?P<container>\d+)\"?\s*$", re.M)
CRED_RE = re.compile(
    r'LOCAL_SFTP_CREDENTIALS = \{"SFTP_USERNAME": "(?P<user>[^"]+)", "SFTP_PASSWORD": "(?P<password>[^"]+)"\}'
)
# process-compose 가 그 compose 파일을 부르는가 — 정의를 옮겨 적었으면 이 문자열이 없다.
CALLS_COMPOSE = "docker compose -f platform/sftp/compose.yaml up"
# `processes:` 아래 프로세스 하나의 시작 — 들여쓰기 2칸 + 이름 + `:`.
PROCESS_KEY_RE = re.compile(r"^  (?P<name>[a-z][a-z0-9-]*):$", re.M)


def process_command(compose: str, name: str) -> str | None:
    """그 프로세스의 **명령 영역**. 주석은 뺀다.

    파일 전체에 문자열을 찾으면 **주석 한 줄이 검사를 만족시킨다** — 실제로 그렇게 통과했다:
    「종전에는 이 명령을 손으로 쳐야 했다」는 설명문이 「지금 이 명령을 부른다」로 읽혔다.
    """
    keys = [(m["name"], m.start(), m.end()) for m in PROCESS_KEY_RE.finditer(compose)]
    for index, (found, _, end) in enumerate(keys):
        if found != name:
            continue
        stop = keys[index + 1][1] if index + 1 < len(keys) else len(compose)
        body = compose[end:stop]
        return "\n".join(line for line in body.split("\n") if not line.lstrip().startswith("#"))
    return None


checked = 0
failures: list[str] = []


def check(label: str, ok: bool) -> None:
    global checked
    checked += 1
    if not ok:
        failures.append(label)


def env_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}=(?P<value>.*)$", text, re.M)
    return None if match is None else match["value"].strip()


def main() -> int:
    for path in (PROCESS_COMPOSE, SFTP_COMPOSE, BOOTSTRAP, BACKEND_EXAMPLE):
        if not path.is_file():
            print(f"::error::대조 대상 파일이 없습니다: {path.relative_to(REPO_ROOT)}")
            return 1

    process_compose = PROCESS_COMPOSE.read_text(encoding="utf-8")
    sftp_compose = SFTP_COMPOSE.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    example = BACKEND_EXAMPLE.read_text(encoding="utf-8")

    sftp_command = process_command(process_compose, "sftp")
    if sftp_command is None:
        print("::error::process-compose.yaml 에 `sftp` 프로세스가 없습니다 — 스택이 SFTP 를 세우지 않습니다")
        return 1

    spec = USER_SPEC_RE.search(sftp_compose)
    publish = PUBLISH_RE.search(sftp_compose)
    creds = CRED_RE.search(bootstrap)

    # 대상을 못 읽으면 통과시키지 않는다 — 「검사 0건」이 초록이 되는 자리다.
    if spec is None or publish is None or creds is None:
        missing = [
            name
            for name, found in (
                ("platform/sftp/compose.yaml 의 사용자 지정(`사용자:비밀번호:::디렉터리`)", spec),
                ("platform/sftp/compose.yaml 의 포트 발행(`2022:22` 꼴)", publish),
                ("bootstrap 의 LOCAL_SFTP_CREDENTIALS", creds),
            )
            if found is None
        ]
        for name in missing:
            print(f"::error::{name} 을 찾지 못했습니다 — 형식이 바뀌었으면 이 그물도 함께 고쳐야 합니다")
        return 1

    port = publish["host"]

    check(
        f"부트스트랩이 써 넣는 사용자가 컨테이너가 만드는 계정과 같다 ({spec['user']})",
        creds["user"] == spec["user"],
    )
    check("부트스트랩이 써 넣는 비밀번호가 컨테이너가 만드는 것과 같다", creds["password"] == spec["password"])
    check("컨테이너 안쪽은 SSH 기본 포트 22 다", publish["container"] == "22")
    check(f".env.example 의 SFTP_PORT 가 발행 포트와 같다 ({port})", env_value(example, "SFTP_PORT") == port)
    check("`.env.example` 의 SFTP_HOST 는 localhost 다", env_value(example, "SFTP_HOST") == "localhost")
    check(
        f"`.env.example` 의 SFTP_BASE_PATH 가 컨테이너가 만드는 디렉터리와 같다 (/{spec['dir']})",
        env_value(example, "SFTP_BASE_PATH") == f"/{spec['dir']}",
    )
    # 자리표시자가 남아 있으면 부트스트랩이 채우지 못한 것이다 — F28 이 되살아난 상태다.
    check(
        "`.env.example` 의 SFTP 자격증명 자리는 부트스트랩이 채우는 자리로 남아 있다",
        env_value(example, "SFTP_USERNAME") == "CHANGE_ME",
    )
    check("부트스트랩이 SFTP_USERNAME 을 채우는 대상으로 안다", "SFTP_USERNAME" in bootstrap)
    check("부트스트랩이 SFTP_PASSWORD 를 채우는 대상으로 안다", "SFTP_PASSWORD" in bootstrap)
    check("로컬 스택이 SFTP 를 스스로 띄운다 — 손으로 먼저 치게 하지 않는다", CALLS_COMPOSE in sftp_command)
    check(
        "process-compose 가 컨테이너 정의를 옮겨 적지 않는다 — SoT 는 compose 파일 하나다",
        "atmoz/sftp" not in sftp_command,
    )

    print(f"검사한 단언 {checked}건 중 {checked - len(failures)}건 통과")
    for line in failures:
        print(f"::error::{line}")
    if failures:
        return 1
    print("판정: 컨테이너가 만드는 계정·포트·디렉터리를 부트스트랩과 `.env.example` 이 같이 말한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
