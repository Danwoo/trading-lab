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


def run(files: dict[str, dict] | None, baseline: list[dict] | None = None) -> tuple[int, str]:
    """`files` 가 None 이면 디렉터리 자체를 만들지 않는다.

    베이스라인은 **테스트가 쥔다** — 레포의 실제 목록을 읽으면 그 파일이 바뀔 때마다 이 그물의
    판정이 따라 흔들린다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "results"
        if files is not None:
            target.mkdir()
            for name, body in files.items():
                (target / name).write_text(json.dumps(body), encoding="utf-8")
        base_path = Path(tmp) / "baseline.json"
        if baseline is not None:
            base_path.write_text(json.dumps({"항목": baseline}, ensure_ascii=False), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(target), "--language", "python", "--baseline", str(base_path)],
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

    # ── 위치 없는 결과가 앞의 결과를 물려받지 않는다 ──────────────────
    # `locations` 가 빈 result 는 실재한다. 그것이 직전 결과의 파일을 물려받으면, 베이스라인
    # 대조가 (규칙, 파일) 키라서 **엉뚱한 새 발견이 「기존」으로 삼켜진다** (#488 리뷰 지적).
    no_loc = {"ruleId": "r9", "level": "error"}
    code, out = run({"python.sarif": sarif([no_loc])})
    check("첫 결과에 위치가 없어도 죽지 않는다", code, 1)
    check("위치를 모른다고 말한다", "(위치 미상)" in out, True)

    mixed = sarif([result("error", rule="r1"), no_loc])
    code, out = run({"python.sarif": mixed}, baseline=[{"rule": "r1", "path": "app/x.py"}])
    check("위치 없는 결과가 앞의 파일을 물려받지 않는다 — 베이스라인에 안 삼켜진다", code, 1)
    check("물려받았다면 나왔을 줄이 없다", "r9 — app/x.py" in out, False)

    # ── 베이스라인: 이미 받아들인 것만 넘긴다 ────────────────────────
    # 이 게이트를 켜는 시점에 이미 발견이 17건 있었다(실측). 그대로 켜면 첫 push 부터 영영
    # 빨갛고, 상시 빨간 잡은 아무도 안 본다 — 그래서 그날의 발견을 고정하고 **새것만** 막는다.
    same = [{"rule": "r1", "path": "app/x.py"}]
    code, out = run({"python.sarif": sarif([result("error")])}, baseline=same)
    check("베이스라인에 있는 발견은 막지 않는다", code, 0)
    check("그래도 화면에는 남는다", "베이스라인" in out, True)

    code, _ = run({"python.sarif": sarif([result("error", rule="r2")])}, baseline=same)
    check("같은 파일의 **다른 규칙**은 새 발견이다", code, 1)

    other_file = {"ruleId": "r1", "locations": [{"physicalLocation": {"artifactLocation": {"uri": "app/y.py"}}}]}
    other_file["level"] = "error"
    code, _ = run({"python.sarif": sarif([other_file])}, baseline=same)
    check("같은 규칙의 **다른 파일**은 새 발견이다", code, 1)

    code, out = run({"python.sarif": sarif([result("error")])}, baseline=None)
    check("베이스라인을 못 읽으면 전부 막는다", code, 1)
    check("못 읽었다는 사실을 말한다", "베이스라인을 못 읽었다" in out, True)

    code, _ = run({"python.sarif": sarif([result("note")])}, baseline=same)
    check("note 는 베이스라인과 무관하게 막지 않는다", code, 0)

    # ── 실물 CodeQL 의 모양 ──────────────────────────────────────────
    # 규칙은 `driver.rules` 가 아니라 `tool.extensions[]` 에 실린다 — 합성 픽스처만 보고
    # 「규칙 0개 = 분석 안 됨」으로 막았다가 첫 실물 실행에서 헛불이 났다(발견 18건은 정상
    # 파싱됐다). 이 경계를 실물 모양으로 고정한다.
    def real_shape(results):
        return {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {"name": "CodeQL", "rules": []},
                        "extensions": [{"name": "codeql/python-queries", "rules": [{"id": "r1"}]}],
                    },
                    "results": results,
                }
            ],
        }

    code, out = run({"python.sarif": real_shape([result("error")])}, baseline=[{"rule": "r1", "path": "app/x.py"}])
    check("규칙이 extensions 에 있어도 읽는다", code, 0)
    check("규칙 수를 0으로 세지 않는다", "규칙 0개" in out, False)

    code, _ = run(
        {"python.sarif": real_shape([result("error", rule="r2")])}, baseline=[{"rule": "r1", "path": "app/x.py"}]
    )
    check("실물 모양에서도 새 발견은 막는다", code, 1)

    # ── fail-closed ────────────────────────────────────────────────
    code, out = run({})
    check("SARIF 0건은 통과가 아니다", code, 1)
    check("0건일 때 사유를 말한다", "분석이 안 돈 것" in out, True)

    code, _ = run(None)
    check("디렉터리가 없어도 통과가 아니다", code, 1)

    code, out = run({"python.sarif": sarif([], rules=[])})
    check("규칙도 발견도 0이면 통과가 아니다", code, 1)
    check("그 사유를 말한다", "질의 묶음이 안 실렸을 수 있다" in out, True)
    code, out = run({"python.sarif": {"version": "2.1.0", "runs": []}})
    check("run 이 0개면 통과가 아니다", code, 1)
    check("run 0개의 사유를 말한다", "run 이 0개다" in out, True)

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
