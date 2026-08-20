"""로컬 개발용 `.env.development` 부트스트랩 — `.env.example` 복사 + 자동 생성 가능한 값 채우기.

배경: `.env.*` 는 gitignore 대상(시크릿)이라 레포에는 `.env.example` 만 있다. 그래서 클론 직후
`process-compose up` 을 하면 각 서비스가 `.env.development` 를 찾지 못해 pydantic-settings /
`frontend/env.ts` 의 필수 필드(`JWT_SECRET`·`*_SQL_DB_*`·`DATABASE_URL` …) 검증에서 즉시 죽는다.
이 스크립트가 그 "최초 1회 복사"를 대신한다.

채워 넣는 값 3종 (판단 근거 포함 — 나머지는 손대지 않고 끝에 목록으로 보고):
  (1) `JWT_SECRET` — **전 파일 동일값**. frontend 가 이 키로 서명한 JWT 를 backend·MCP 서비스가
      같은 키로 검증하고 서비스 간 토큰도 같은 키를 쓴다(auth lockstep). 한 곳만 달라도 401 이
      되므로 한 번 생성해 전 파일에 같은 값을 넣는다.
  (2) `BETTER_AUTH_SECRET`·`EMAIL_SECRET` — **파일별 독립값**. `frontend/env.ts` 에만 선언돼 있고
      (`lib/auth/auth.ts` 의 better-auth `secret`) 서명·검증이 frontend 프로세스 안에서 끝난다 —
      다른 서비스가 같은 값을 요구하지 않으므로 공유할 이유가 없다.
  (3) `*_SQL_DB_USER`/`*_SQL_DB_PASSWORD` — 로컬 Postgres(process-compose 의 `fintech-pg` 컨테이너)
      자격증명 `fintech`/`fintech`. host·port·db 는 `.env.example` 이 이미 `localhost:5442/fintech`
      라 그대로 둔다(어긋나면 값을 바꾸지 않고 경고만 — 사람이 판단할 문제).

"값이 없는 자리"는 `CHANGE_ME` 와 **빈 값**(`KEY=`) 둘 다다 — 위 3종에 해당하면 채우고, 나머지
(LLM·DART·Tavily API 키·SMTP·SFTP … 외부 서비스 자격증명)는 자동 생성이 불가능하므로 그대로 두고
끝에 "직접 채워야 하는 키" 목록으로 출력한다. 값이 없어도 필수 필드 "존재" 검증은 통과하므로
서비스는 뜬다 — 그 기능을 실제로 쓸 때만 채우면 된다.

안전 규칙:
  - 이미 있는 `.env.development` 는 **건드리지 않고 건너뛴다**(로컬 설정 파괴 금지).
    `--force` 를 줄 때만 `.env.development.bak` 로 백업한 뒤 다시 만든다.
    **기존 백업은 덮어쓰지 않는다** — `.bak` 이 이미 있으면 타임스탬프를 붙여
    (`.env.development.bak.20260727-101530`) 최초 원본을 지킨다.
  - 생성한 시크릿 값은 화면에 찍지 않는다(생성했다는 사실만 알린다).
  - 만드는 파일은 전부 gitignore(`.env.*`, `!.env.example`) 대상이라 커밋되지 않는다.

stdlib 전용 — uv 없이 `python3 scripts/bootstrap_local_env.py` (cwd 무관).
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_NAME = ".env.example"
TARGET_NAME = ".env.development"
BACKUP_NAME = TARGET_NAME + ".bak"
PLACEHOLDER = "CHANGE_ME"
# "아직 값이 없다"로 보는 것 — 빈 값(`KEY=`)도 placeholder 와 같이 취급한다. 빈 값을 통과시키면
# `JWT_SECRET=` 같은 줄이 채워지지도, 경고되지도 않은 채 남아 기동 후 401 로만 드러난다.
UNSET_TOKENS = (PLACEHOLDER, "")

# 전 파일이 같은 값이어야 하는 키 / 파일별 독립 생성 키 (근거는 모듈 독스트링 (1)(2))
SHARED_SECRET_KEYS = ("JWT_SECRET",)
PER_FILE_SECRET_KEYS = ("BETTER_AUTH_SECRET", "EMAIL_SECRET")
SECRET_BYTES = 48

# 로컬 Postgres (process-compose 의 fintech-pg) — 자격증명은 채우고, 접속 좌표는 검증만 한다.
# PORT 의 SoT 는 process-compose.yaml 의 postgres `vars.PORT` 이고,
# scripts/verify_dev_port_hygiene.py 가 이 값과 대조한다 (#294).
LOCAL_DB_CREDENTIALS = {"USER": "fintech", "PASSWORD": "fintech"}
LOCAL_DB_ENDPOINT = {"HOST": "localhost", "PORT": "5442", "NAME": "fintech"}
DB_KEY_RE = re.compile(r"^[A-Z0-9_]+_SQL_DB_(?P<part>USER|PASSWORD|HOST|PORT|NAME)$")

ASSIGN_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<rest>.*)$")


def discover_examples() -> list[Path]:
    """`.env.development` 를 만들어야 할 `.env.example` 목록 (서비스가 늘어도 glob 이 흡수).

    대상은 python 서비스의 `*/app/.env.example` 과 `frontend/.env.example` — `APP_ENV=development`
    로 뜨는 프로세스들이 읽는 파일이다. `platform/litellm/.env.example` 은 대상이 아니다:
    그쪽 사본은 `.env.development` 가 아니라 docker compose 가 자동 로드하는 `.env` 이고,
    process-compose 스택 밖(선택적 LLM 게이트웨이)이다.
    """
    targets = sorted(REPO_ROOT.glob(f"*/app/{EXAMPLE_NAME}"))
    frontend = REPO_ROOT / "frontend" / EXAMPLE_NAME
    if frontend.is_file():
        targets.append(frontend)
    return targets


def split_value(rest: str) -> tuple[str, str]:
    """`KEY=` 뒤쪽을 (값 토큰, 꼬리) 로 나눈다. 꼬리(인라인 주석·정렬 공백)는 원문 그대로 보존한다.

    값 토큰은 따옴표를 포함한 원문이다 (`"CHANGE_ME"` 처럼) — 쓸 때 같은 인용 스타일을 유지하려고.
    """
    if rest[:1] in ('"', "'"):
        quote = rest[0]
        end = rest.find(quote, 1)
        if end != -1:
            return rest[: end + 1], rest[end + 1 :]
        return rest, ""  # 닫는 따옴표가 없는 이상한 줄 — 손대지 않는다
    body = rest.split("#", 1)[0].rstrip()
    return body, rest[len(body) :]


def unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


def requote(token: str, value: str) -> str:
    """원문의 인용 스타일을 유지한 채 값만 바꾼다."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return f"{token[0]}{value}{token[0]}"
    return value


def parse_assignments(text: str) -> dict[str, str]:
    """`KEY=VALUE` 줄을 {키: 값} 으로. 주석·빈 줄은 무시하고, 뒤 정의가 앞 정의를 덮는다(dotenv 관례)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        match = ASSIGN_RE.match(line.strip())
        if match:
            out[match["key"]] = unquote(split_value(match["rest"])[0])
    return out


def resolve_managed_value(key: str, shared: dict[str, str], per_file: dict[str, str]) -> str | None:
    """이 스크립트가 자동으로 채울 값 (대상이 아니면 None)."""
    if key in shared:
        return shared[key]
    if key in PER_FILE_SECRET_KEYS:
        return per_file.setdefault(key, secrets.token_urlsafe(SECRET_BYTES))
    db = DB_KEY_RE.match(key)
    if db:
        return LOCAL_DB_CREDENTIALS.get(db["part"])
    return None


def render(example_text: str, shared: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """`.env.example` 본문 → (`.env.development` 본문, 채운 키, 값 없이 남은 키).

    값을 바꾸는 것은 **값이 없는 줄뿐**이다(`CHANGE_ME` 또는 빈 값). `.env.example` 이 이미 실제
    값을 담고 있으면 (예: frontend `DATABASE_URL`, DB host/port/name) 그 값을 존중해 그대로 둔다.
    자동 생성 대상이 아닌 빈 자리는 그대로 두고 `leftover` 로 보고한다.
    """
    per_file: dict[str, str] = {}
    filled: list[str] = []
    leftover: list[str] = []
    lines: list[str] = []

    for line in example_text.splitlines():
        match = ASSIGN_RE.match(line)
        if not match:
            lines.append(line)
            continue
        key = match["key"]
        token, tail = split_value(match["rest"])
        if unquote(token) not in UNSET_TOKENS:
            lines.append(line)
            continue
        value = resolve_managed_value(key, shared, per_file)
        if value is None:
            leftover.append(key)
            lines.append(line)
            continue
        filled.append(key)
        lines.append(f"{key}={requote(token, value)}{tail}")

    text = "\n".join(lines)
    if example_text.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text, filled, leftover


def file_warnings(shown: Path, text: str, shared: dict[str, str]) -> list[str]:
    """생성 결과에서 사람이 봐야 할 어긋남 (값은 바꾸지 않는다 — 판단은 사람 몫).

    (ㄱ) DB 접속 좌표가 로컬 Postgres 와 다름, (ㄴ) 공유 시크릿을 `.env.example` 이 자체 값으로
    이미 갖고 있어 전 서비스 동일값이 깨짐.
    """
    warnings: list[str] = []
    for key, value in parse_assignments(text).items():
        db = DB_KEY_RE.match(key)
        if db:
            expected = LOCAL_DB_ENDPOINT.get(db["part"])
            if expected is not None and value != expected:
                warnings.append(
                    f"{shown}: {key}={value} — 로컬 Postgres 는 {expected} ({EXAMPLE_NAME} 가 로컬 기본값과 어긋남)"
                )
        elif key in shared and value not in UNSET_TOKENS and value != shared[key]:
            warnings.append(
                f"{shown}: {key} 가 {EXAMPLE_NAME} 에 자체 값으로 박혀 있어 공유값을 넣지 못했다 "
                "— 전 서비스 동일값이 깨진다(서비스 간 토큰 검증 실패)"
            )
    return warnings


def pick_shared_secrets(targets: list[Path], force: bool) -> tuple[dict[str, str], list[str]]:
    """공유 시크릿 값을 정한다 — 이미 있는 `.env.development` 의 값을 최대한 재사용한다.

    일부 파일만 이미 존재하는 상태에서 새 값을 생성하면 기존 파일과 값이 갈려 서비스 간 JWT 검증이
    깨진다(부분 부트스트랩 함정). 그래서 기존 값이 있으면 그것을 새 파일에 이어 쓴다.
    `--force` 는 전 파일을 다시 쓰므로 새로 생성해도 정합이 유지된다.
    """
    secrets_by_key: dict[str, str] = {}
    notes: list[str] = []
    existing = [] if force else [t.with_name(TARGET_NAME) for t in targets]
    existing = [p for p in existing if p.is_file()]

    for key in SHARED_SECRET_KEYS:
        found: list[tuple[Path, str]] = []
        for path in existing:
            value = parse_assignments(path.read_text(encoding="utf-8")).get(key, "")
            if value not in UNSET_TOKENS:
                found.append((path, value))
        counts = Counter(value for _, value in found)
        if not counts:
            secrets_by_key[key] = secrets.token_urlsafe(SECRET_BYTES)
            continue
        chosen, _ = counts.most_common(1)[0]
        secrets_by_key[key] = chosen
        notes.append(f"{key}: 기존 {TARGET_NAME} {len(found)}개의 값을 재사용 (새로 만드는 파일에 같은 값)")
        odd = [str(p.relative_to(REPO_ROOT)) for p, v in found if v != chosen]
        if odd:
            notes.append(
                f"⚠ {key} 가 기존 파일들 사이에서 이미 갈려 있다 — 다수값을 새 파일에 쓴다. "
                f"다른 값을 가진 파일: {', '.join(odd)} (서비스 간 토큰 검증 실패 원인)"
            )
    return secrets_by_key, notes


def choose_backup_path(target: Path) -> Path:
    """덮어쓰지 않을 백업 경로를 고른다.

    `--force` 를 두 번 돌리면 두 번째 백업이 첫 백업(= 사람이 손으로 채운 원본)을 덮어써
    원본이 사라진다. 그래서 `.bak` 이 이미 있으면 타임스탬프를 붙여 새 이름을 쓴다.
    (백업도 `.env.*` 라 gitignore 대상이다.)
    """
    first = target.with_name(BACKUP_NAME)
    if not first.exists():
        return first

    stamp = time.strftime("%Y%m%d-%H%M%S")  # 로컬 시각 — 사람이 백업 순서를 알아보는 용도
    candidate = target.with_name(f"{BACKUP_NAME}.{stamp}")
    serial = 2
    while candidate.exists():  # 같은 초에 두 번 돌린 경우
        candidate = target.with_name(f"{BACKUP_NAME}.{stamp}-{serial}")
        serial += 1
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"각 서비스의 {EXAMPLE_NAME} 로부터 로컬 개발용 {TARGET_NAME} 를 만든다."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"이미 있는 {TARGET_NAME} 도 다시 만든다 (기존 파일은 {BACKUP_NAME} 로 백업)",
    )
    args = parser.parse_args()

    targets = discover_examples()
    if not targets:
        print(f"{EXAMPLE_NAME} 을 하나도 찾지 못했다 — 레포 루트({REPO_ROOT})가 맞는지 확인하라.")
        return 1

    shared, notes = pick_shared_secrets(targets, args.force)
    print(f"{EXAMPLE_NAME} {len(targets)}개 발견 → {TARGET_NAME} 생성")
    for note in notes:
        print(f"  {note}")

    created = 0
    skipped = 0
    manual: list[tuple[Path, list[str], bool]] = []
    warnings: list[str] = []

    for example in targets:
        target = example.with_name(TARGET_NAME)
        shown = target.relative_to(REPO_ROOT)
        if target.is_file() and not args.force:
            skipped += 1
            print(f"  ↷ 건너뜀 {shown} (이미 있음 — 덮어쓰려면 --force)")
            continue

        text, filled, leftover = render(example.read_text(encoding="utf-8"), shared)
        backup = ""
        if target.is_file():
            backup_path = choose_backup_path(target)
            target.replace(backup_path)
            backup = f", 기존 파일 → {backup_path.name}"
        target.write_text(text, encoding="utf-8")
        created += 1
        summary = f"자동 채움 {len(filled)}개" if filled else "자동 채움 없음"
        print(f"  ✓ 생성  {shown} ({summary}{backup})")

        warnings.extend(file_warnings(shown, text, shared))
        if leftover:
            mock_ok = parse_assignments(text).get("USE_REAL_API") == "false"
            manual.append((shown, leftover, mock_ok))

    if warnings:
        print(f"\n⚠ 확인 필요 — {EXAMPLE_NAME} 값이 로컬 기동 전제와 어긋난다:")
        for warning in warnings:
            print(f"  - {warning}")

    if manual:
        print(f"\n직접 채워야 하는 키 ({PLACEHOLDER} 이거나 빈 값으로 남음 — 외부 서비스 자격증명이라 자동 생성 불가):")
        for shown, keys, mock_ok in manual:
            hint = " · USE_REAL_API=false 라 로컬 MOCK 으로 뜬다" if mock_ok else ""
            print(f"  - {shown}{hint}")
            print(f"      {', '.join(keys)}")
        print(
            "  (값이 없어도 필수 키 '존재' 검증은 통과해 서비스는 기동한다 — "
            "해당 외부 기능을 실제로 쓸 때 채우면 된다.)"
        )

    print(f"\n요약: 생성 {created}개 · 건너뜀 {skipped}개 · 수동 입력 필요 파일 {len(manual)}개")
    if created:
        print("생성한 시크릿 값은 출력하지 않는다. 만들어진 파일은 gitignore(.env.*) 대상이라 커밋되지 않는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
