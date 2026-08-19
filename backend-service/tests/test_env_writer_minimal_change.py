"""#225 — **`.env` 쓰기가 최소한만 건드린다** (DB·네트워크 없음).

백업 파일을 남기지 않기로 했으므로(결정 로그 2026-08-19) **되돌릴 사본이 없다.** 그래서
쓰기가 최소여야 한다 — 한 줄만 갈고 나머지는 그대로여야 한다. 이 그물이 그것을 잠근다.

잠그는 것:
  ① 이름이 같은 줄 하나만 갈린다 · 주석·빈 줄·다른 변수·순서가 보존된다
  ② 없는 이름은 끝에 더해진다 (다른 줄은 그대로)
  ③ 같은 이름이 두 번 있으면 **쓰지 않고 거부한다** — 잘못 고르면 되돌릴 수 없다
  ④ 줄바꿈이 든 값은 거부한다 — 그대로 쓰면 다음 줄이 다른 설정으로 읽힌다
  ⑤ 예외 메시지에 값이 담기지 않는다 — 이 예외는 API 응답이 된다
  ⑥ 파일 권한이 유지된다 — 600 인 `.env` 가 644 로 넓어지지 않는다
  ⑦ 파일이 없으면 거부한다 — 만드는 것은 부트스트랩의 일이다

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_env_writer_minimal_change.py
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from utils.env_file.env_writer import EnvWriteRejected, set_env_value  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0

SECRET = "sk-live-CANARY-0123456789"

SAMPLE = """# 주석은 보존된다
FIRST="keep me"

# 빈 줄도 보존된다
MARKET_DATA_ALPACA_KEY="old-value"
LAST=tail
"""


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def given(content: str, mode: int = 0o600) -> Path:
    fd, name = tempfile.mkstemp(prefix="envtest.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    path = Path(name)
    os.chmod(path, mode)
    return path


def main() -> int:
    # ── ① 한 줄만 갈리고 나머지가 그대로다 ────────────────────────────────
    path = given(SAMPLE)
    action = set_env_value(path, "MARKET_DATA_ALPACA_KEY", SECRET)
    after = path.read_text(encoding="utf-8")

    check("갈아 끼웠다고 답한다", action, "replaced")
    check("새 값이 들어갔다", f'MARKET_DATA_ALPACA_KEY="{SECRET}"' in after, True)
    check("옛 값이 남지 않았다", "old-value" in after, False)
    check("주석이 보존된다", "# 주석은 보존된다" in after, True)
    check("빈 줄이 보존된다", "\n\n# 빈 줄도" in after, True)
    check("다른 변수가 그대로다", 'FIRST="keep me"' in after and "LAST=tail" in after, True)
    check("줄 수가 그대로다", len(after.split("\n")), len(SAMPLE.split("\n")))
    check(
        "줄 순서가 그대로다",
        [ln.split("=")[0] for ln in after.split("\n")],
        [ln.split("=")[0] for ln in SAMPLE.split("\n")],
    )
    path.unlink()

    # ── ② 없는 이름은 끝에 더해진다 ───────────────────────────────────────
    path = given(SAMPLE)
    action = set_env_value(path, "MARKET_DATA_OPENFIGI_KEY", "figi-1")
    after = path.read_text(encoding="utf-8")

    check("더했다고 답한다", action, "appended")
    check("끝에 한 줄 늘었다", len(after.split("\n")), len(SAMPLE.split("\n")) + 1)
    check("기존 줄은 그대로다", SAMPLE.rstrip("\n") in after, True)
    check("파일 끝 개행이 보존된다", after.endswith("\n"), True)
    path.unlink()

    # ── ③ 같은 이름이 둘이면 거부한다 ─────────────────────────────────────
    path = given('DUP="a"\nOTHER=1\nDUP="b"\n')
    before = path.read_text(encoding="utf-8")
    try:
        set_env_value(path, "DUP", SECRET)
        check("중복이면 거부한다", "예외 없음", "EnvWriteRejected")
    except EnvWriteRejected as exc:
        check("중복이면 거부한다", True, True)
        check("거부 사유에 값이 없다", SECRET in str(exc), False)
    check("거부했으면 파일이 그대로다", path.read_text(encoding="utf-8"), before)
    path.unlink()

    # ── ④⑤ 줄바꿈이 든 값은 거부하고 값을 안 흘린다 ──────────────────────
    for bad in (f"{SECRET}\nINJECTED=1", f"{SECRET}\r\nINJECTED=1", f"{SECRET}\0"):
        path = given(SAMPLE)
        before = path.read_text(encoding="utf-8")
        try:
            set_env_value(path, "MARKET_DATA_ALPACA_KEY", bad)
            check("줄바꿈 값 거부", "예외 없음", "EnvWriteRejected")
        except EnvWriteRejected as exc:
            check("줄바꿈 값 거부", True, True)
            check("사유에 값이 없다", SECRET in str(exc), False)
        check("거부했으면 파일이 그대로다", path.read_text(encoding="utf-8"), before)
        check("주입이 안 들어갔다", "INJECTED" in path.read_text(encoding="utf-8"), False)
        path.unlink()

    # ── 값에 따옴표·백슬래시가 있어도 한 줄로 남는다 ──────────────────────
    path = given(SAMPLE)
    tricky = 'a"b\\c d'
    set_env_value(path, "MARKET_DATA_ALPACA_KEY", tricky)
    after = path.read_text(encoding="utf-8")
    check("따옴표·백슬래시가 있어도 줄 수가 그대로다", len(after.split("\n")), len(SAMPLE.split("\n")))
    path.unlink()

    # ── ⑥ 권한이 유지된다 ────────────────────────────────────────────────
    #
    # **두 방향을 다 본다.** `mkstemp` 는 기본이 0600 이라, 600 만 확인하면 권한을 옮기는
    # 코드를 지워도 통과한다(실측 — 그물이 엉뚱한 이유로 초록이었다). 넓은 권한도 그대로
    # 옮겨지는지 봐야 「옮긴다」가 검사된다.
    for mode in (0o600, 0o644):
        path = given(SAMPLE, mode=mode)
        set_env_value(path, "MARKET_DATA_ALPACA_KEY", SECRET)
        check(f"{oct(mode)} 이 유지된다", stat.S_IMODE(path.stat().st_mode), mode)
        path.unlink()

    # ── ⑦ 파일이 없으면 거부한다 ─────────────────────────────────────────
    missing = Path(tempfile.gettempdir()) / "envtest-does-not-exist-225"
    missing.unlink(missing_ok=True)
    try:
        set_env_value(missing, "ANY", "x")
        check("없는 파일 거부", "예외 없음", "EnvWriteRejected")
    except EnvWriteRejected:
        check("없는 파일 거부", True, True)
    check("없는 파일을 만들지 않는다", missing.exists(), False)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 30:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: .env 쓰기가 최소한만 건드리고, 위험한 값은 쓰지 않고 거부한다 (#225)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
