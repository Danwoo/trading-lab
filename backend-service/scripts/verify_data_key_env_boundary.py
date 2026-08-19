"""데이터 소스 키의 `.env` 경계 검증 — 커밋 축 + 단일 로더 축 (fail-closed, stdlib 전용).

2026-08-07 리드 결정으로 데이터 소스 키는 `.env` 가 정본이다. 저장 암호화를 하지 않는 대신
`.env` 는 **파일 권한과 gitignore 로** 지킨다 — 그러면 그 gitignore 가 실제로 막고 있는지가
방어의 전부이므로, 그것을 매 실행이 다시 확인해야 한다.

**이 스크립트가 보는 두 축** (나머지 셋 — 로그·응답·에러 — 은 실제 코드 경로를 태우는
`tests/test_data_source_key_leak.py` 가 본다. 정적 스캔으로는 우회를 못 잡기 때문이다):

1. **커밋 축** — `.env.*` 가 실제로 gitignore 되고(`git check-ignore` 로 확인, 패턴 문자열을
   눈으로 읽는 것이 아니다), 추적 중인 `.env` 파일이 `.env.example` 말고는 없으며,
   `.env.example` 의 키 항목은 **빈 값**이다.
2. **단일 로더 축** — 키 설정 이름이 정의처(`core/config.py`)·로더(`services/data_key/`)·
   예시(`.env.example`) 밖의 코드에 나오지 않는다. 다른 데서 `settings.<키>` 를 직접 읽으면
   그 값은 가림 등록을 거치지 않아 **로그·응답 관문 밖으로 흘러나간다** — 로드와 가림 등록이
   한 자리라는 전제가 거기서 깨진다.

**검사 대상 이름은 로더의 표에서 도출한다** — 이름 규칙(`MARKET_DATA_*KEY`)으로 긁으면 그
규칙을 안 따르는 새 자격이 조용히 사정권 밖에 남는다. 실제로 그 일이 있었다(합성 자격
`TOSS_CLIENT_ID`/`_SECRET` 이 규칙 밖이라 그물 셋이 초록인 채 커버리지만 안 늘었다). 표가
정본이면 소스를 늘리는 것만으로 그물이 따라온다.

**fail-closed**: 검사할 설정 이름이 0건이거나, 스캔한 파일이 0건이거나, git 을 못 부르면 실패한다.
검사한 개수를 항상 출력한다 — 통과가 "위반 없음"인지 "아무것도 안 봤음"인지 구분되도록.

실행: `cd backend-service && python3 scripts/verify_data_key_env_boundary.py`
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = _BACKEND_DIR.parent

CONFIG_FILE = "backend-service/app/core/config.py"
LOADER_FILE = "backend-service/app/services/data_key/data_key_service.py"
ENV_EXAMPLE = "backend-service/app/.env.example"

# 설정 이름이 나와도 되는 곳 — 정의·로더·예시, 그리고 그 경계를 검사하는 그물 자신.
ALLOWED_FILES = {
    CONFIG_FILE,
    LOADER_FILE,
    ENV_EXAMPLE,
    "backend-service/scripts/verify_data_key_env_boundary.py",
    "backend-service/tests/test_data_source_key_leak.py",
}

# 코드 축만 스캔한다 — 문서(`.docs/`·`*.md`)는 설정 이름을 적어야 하는 자리다.
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".cjs")

# gitignore 가 실제로 막아야 하는 것 / 막으면 안 되는 것.
MUST_BE_IGNORED = (
    "backend-service/app/.env",
    "backend-service/app/.env.development",
    "backend-service/app/.env.production",
)
MUST_NOT_BE_IGNORED = (ENV_EXAMPLE,)

#: `core/config.py` 가 선언한 설정 이름 — 표가 가리키는 이름이 실제로 있는지 대조한다.
CONFIG_FIELD = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*:\s*(?:str|bool|int)", re.MULTILINE)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def _string_leaves(node: ast.AST) -> list[str]:
    """dict/tuple/str 리터럴 안의 문자열을 전부 꺼낸다 — 표의 모양이 무엇이든."""
    out: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append(child.value)
    return out


def loader_tables() -> tuple[list[str], list[str]]:
    """로더가 선언한 (**비밀** 설정 이름, 비밀이 아닌 설정 이름).

    `ast` 로 읽는다 — 앱을 import 하지 않으므로 stdlib 전용이고 설정·DB 가 필요 없다.
    표 이름이 바뀌면 아래 `if not secret` 에서 fail-closed 로 걸린다.
    """
    tree = ast.parse((REPO_ROOT / LOADER_FILE).read_text(encoding="utf-8"))
    secret: list[str] = []
    plain: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names or node.value is None:
            continue
        if "SOURCE_KEY_SETTINGS" in names or "COMPOSITE_KEY_SETTINGS" in names:
            # 표는 {소스: 설정이름} 또는 {소스: (앞, 뒤)} — 소스 id 는 키 자리, 설정 이름은 값 자리다.
            values = node.value.values if isinstance(node.value, ast.Dict) else []
            for value in values:
                secret.extend(_string_leaves(value))
        elif "CONTACT_SETTING" in names:
            plain.extend(_string_leaves(node.value))
    return sorted(dict.fromkeys(secret)), sorted(dict.fromkeys(plain))


def config_declared_names() -> set[str]:
    """`core/config.py` 가 선언한 설정 이름 전부."""
    text = (REPO_ROOT / CONFIG_FILE).read_text(encoding="utf-8")
    return set(CONFIG_FIELD.findall(text))


def check_commit_axis(settings_names: list[str], plain_names: list[str]) -> list[str]:
    failures: list[str] = []

    for path in MUST_BE_IGNORED:
        if _git("check-ignore", "-q", path).returncode != 0:
            failures.append(f"{path} 가 gitignore 되지 않습니다 — 키가 담긴 파일이 커밋될 수 있습니다")
    for path in MUST_NOT_BE_IGNORED:
        if _git("check-ignore", "-q", path).returncode == 0:
            failures.append(f"{path} 가 gitignore 됩니다 — 예시 파일은 추적돼야 합니다")

    tracked = _git("ls-files", "--", "*.env", "*/.env", "*/.env.*", ".env.*")
    stray = [line for line in tracked.stdout.splitlines() if line and not line.endswith(".env.example")]
    if stray:
        failures.append(f"추적 중인 env 파일이 있습니다: {', '.join(stray)}")

    example = (REPO_ROOT / ENV_EXAMPLE).read_text(encoding="utf-8")
    declared = config_declared_names()
    for name in settings_names + plain_names:
        match = re.search(rf"^{re.escape(name)}=(.*)$", example, re.MULTILINE)
        if match is None:
            failures.append(f"{ENV_EXAMPLE} 에 {name} 항목이 없습니다 — 무엇을 채워야 하는지 알 수 없습니다")
        elif name in settings_names and match.group(1).strip():
            # 비밀만 빈 값이어야 한다 — 연락처는 「우리가 누구인지」라 예시 문자열이 안내다.
            failures.append(f"{ENV_EXAMPLE} 의 {name} 에 값이 들어 있습니다 — 예시는 빈 값이어야 합니다")
        if name not in declared:
            failures.append(f"{CONFIG_FILE} 에 {name} 선언이 없습니다 — 표가 없는 설정을 가리킵니다")
    return failures


def check_single_loader_axis(settings_names: list[str]) -> tuple[list[str], int]:
    listed = _git("ls-files")
    files = [line for line in listed.stdout.splitlines() if line.endswith(CODE_SUFFIXES)]
    if not files:
        return ["git ls-files 가 코드 파일을 0건 냈습니다"], 0

    pattern = re.compile("|".join(re.escape(name) for name in settings_names))
    failures: list[str] = []
    scanned = 0
    for relative in files:
        if relative in ALLOWED_FILES:
            continue
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        scanned += 1
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if pattern.search(line):
                failures.append(f"{relative}:{lineno}: {line.strip()}")
    return failures, scanned


def main() -> int:
    if _git("rev-parse", "--git-dir").returncode != 0:
        print(f"::error::{REPO_ROOT} 에서 git 을 실행할 수 없습니다 — 커밋 축을 검사할 수 없어 fail-closed 종료")
        return 1

    for relative in (CONFIG_FILE, LOADER_FILE, ENV_EXAMPLE):
        if not (REPO_ROOT / relative).is_file():
            print(f"::error::필수 파일이 없습니다: {relative} — fail-closed 종료")
            return 1

    settings_names, plain_names = loader_tables()
    if not settings_names:
        print(f"::error::{LOADER_FILE} 에서 비밀 키 설정을 0건 수집했습니다 — fail-closed 종료")
        print("::error::표 이름(SOURCE_KEY_SETTINGS·COMPOSITE_KEY_SETTINGS)이 바뀌었을 수 있습니다. 확인하세요.")
        return 1
    if not config_declared_names():
        print(f"::error::{CONFIG_FILE} 에서 설정 선언을 0건 읽었습니다 — fail-closed 종료")
        return 1

    commit_failures = check_commit_axis(settings_names, plain_names)
    loader_failures, scanned = check_single_loader_axis(settings_names)
    if scanned == 0:
        print("::error::단일 로더 축에서 코드 파일을 0건 스캔했습니다 — fail-closed 종료")
        return 1

    print(f"비밀 키 설정 {len(settings_names)}개: {', '.join(settings_names)}")
    print(f"비밀 아닌 설정 {len(plain_names)}개: {', '.join(plain_names) or '없음'}")
    print(
        f"커밋 축: gitignore 대상 {len(MUST_BE_IGNORED)}건 · 예외 {len(MUST_NOT_BE_IGNORED)}건 · .env.example 항목 대조"
    )
    print(f"단일 로더 축: 허용 파일 {len(ALLOWED_FILES)}개를 뺀 코드 파일 {scanned}개 스캔")

    failures = commit_failures + loader_failures
    if failures:
        print(f"::error::데이터 소스 키 경계 위반 {len(failures)}건")
        for failure in failures:
            print(f"::error::  {failure}")
        print("::error::키는 .env 가 정본이고 읽는 자리는 services/data_key/ 하나입니다 (2026-08-07 리드 결정).")
        return 1

    print("위반 0건 — .env 는 커밋되지 않고, 키를 읽는 자리는 하나다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
