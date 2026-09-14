"""`judge_codeql_sarif.py` 가 무엇을 빨갛게 만드는지 (standalone, fail-closed).

이 판정부가 private 전환 뒤 **코드 스캐닝의 유일한 출구**다. Security 탭이 경보를 안 받으므로,
이 스크립트가 조용히 초록이면 탐지가 통째로 사라진 것과 같다. 그래서 합성 SARIF 로 경계를
직접 확인한다 — CodeQL 을 돌리지 않고도 판정 규칙만 재현한다.

    python3 scripts/test_judge_codeql_sarif.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "judge_codeql_sarif.py"

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def sarif(results: list[dict], *, rules: list[dict] | None = None) -> dict:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "CodeQL", "rules": rules if rules is not None else [{"id": "r1"}]}},
                "results": results,
            }
        ],
    }


def run(files: dict[str, dict] | None) -> tuple[int, str]:
    """`files` 가 None 이면 디렉터리 자체를 만들지 않는다."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "results"
        if files is not None:
            target.mkdir()
            for name, body in files.items():
                (target / name).write_text(json.dumps(body), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(target), "--language", "python"],
            capture_output=True,
            text=True,
        )
        return done.returncode, done.stdout + done.stderr


def result(level: str | None, rule: str = "r1") -> dict:
    out: dict = {"ruleId": rule, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "app/x.py"}}}]}
    if level is not None:
        out["level"] = level
    return out


def main() -> int:
    code, out = run({"python.sarif": sarif([])})
    check("발견 0건이면 통과", code, 0)
    check("무엇을 몇 건 봤는지 남긴다", "SARIF 1개" in out, True)

    code, out = run({"python.sarif": sarif([result("error")])})
    check("error 는 빨갛게 만든다", code, 1)
    check("규칙과 위치를 남긴다", "app/x.py" in out, True)

    code, _ = run({"python.sarif": sarif([result("warning")])})
    check("warning 도 빨갛게 만든다", code, 1)

    code, _ = run({"python.sarif": sarif([result("note")])})
    check("note 는 막지 않는다 — 기본 묶음의 스타일 지적이다", code, 0)

    # 수준이 결과에 없으면 규칙 기본값에서 읽는다. 없다고 **통과시키지 않는다.**
    code, _ = run({"python.sarif": sarif([result(None)], rules=[{"id": "r1"}])})
    check("수준이 없으면 warning 으로 본다", code, 1)
    code, _ = run(
        {"python.sarif": sarif([result(None)], rules=[{"id": "r1", "defaultConfiguration": {"level": "note"}}])}
    )
    check("규칙 기본값이 note 면 막지 않는다", code, 0)

    # ── fail-closed ────────────────────────────────────────────────
    code, out = run({})
    check("SARIF 0건은 통과가 아니다", code, 1)
    check("0건일 때 사유를 말한다", "분석이 안 돈 것" in out, True)

    code, _ = run(None)
    check("디렉터리가 없어도 통과가 아니다", code, 1)

    code, out = run({"python.sarif": sarif([], rules=[])})
    check("규칙 0개로 분석된 것은 통과가 아니다", code, 1)
    check("규칙 0개의 사유를 말한다", "질의 묶음이 안 실린" in out, True)

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "results"
        target.mkdir()
        (target / "broken.sarif").write_text("{ not json", encoding="utf-8")
        done = subprocess.run([sys.executable, str(SCRIPT), "--dir", str(target)], capture_output=True, text=True)
        CHECKED_BEFORE = CHECKED
        check("읽지 못한 SARIF 는 통과가 아니다", done.returncode, 1)
        assert CHECKED == CHECKED_BEFORE + 1

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if FAILURES:
        print("판정: SARIF 판정부가 기대와 다르게 동작한다 — 위 FAIL 을 보라")
        return 1
    print("판정: 발견이 있으면 빨개지고, 아무것도 못 읽으면 통과하지 않는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
