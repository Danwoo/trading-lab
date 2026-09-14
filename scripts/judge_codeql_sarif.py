#!/usr/bin/env python3
"""CodeQL 이 낸 SARIF 를 읽어 **이 잡을 빨갛게 만든다** (#420, fail-closed · stdlib 전용).

## 왜 있나

private 에서 코드 스캐닝 **업로드**는 Code Security 라이선스를 요구한다. 결제하지 않기로 했으므로
(리드 결정 2026-08-29) 업로드를 빼고 분석만 돌린다. 그러면 경보가 갈 곳이 없어지므로 — Security
탭이 안 받는다 — 결과를 **여기서** 읽어 판정한다.

종전보다 약해지는 것이 아니다. 업로드하던 시절 이 체크는 12일 내내 실패 0이었다(경보는 탭으로만
갔다). 이제는 발견이 하나라도 있으면 워크플로가 빨개진다 — 발각이 행동으로 이어지는 자리가
생긴다(`.docs/4-아키텍처/main-보호-위협모델.md` §4.3 이 적은 조건).

## fail-closed

**SARIF 파일이 0건이면 실패한다.** 분석이 조용히 안 돌았거나 출력 경로가 어긋난 상태를
「위반 없음」으로 읽으면, 이 그물은 초록으로 죽는다 — 이 레포가 반복해서 덴 바로 그 모양이다.
읽은 파일 수·규칙 수·발견 수를 항상 출력한다.

## 실행

    python3 scripts/judge_codeql_sarif.py --dir <SARIF 디렉터리> --language <언어>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / ".codeql-baseline.json"

#: 이 수준 이상만 잡을 빨갛게 한다. CodeQL 기본 묶음은 `note` 로 스타일 지적도 낸다.
BLOCKING_LEVELS = {"error", "warning"}


def load_baseline(path: Path) -> set[tuple[str, str]] | None:
    """베이스라인의 (규칙, 파일) 집합. 못 읽으면 `None`.

    **왜 베이스라인이 필요한가** — 이 게이트를 켜는 시점에 이미 발견이 17건 있었다(실측).
    그대로 켜면 첫 push 부터 영영 빨갛고, 상시 빨간 잡은 아무도 안 본다(위협 모델 §4.3).
    그래서 그날의 발견을 목록으로 고정하고 **새것만** 막는다.

    **목록은 줄어들기만 한다.** 한 줄을 더하는 것은 「새 발견을 받아들인다」는 뜻이고 리뷰에서
    보인다. 못 읽으면 목록이 없는 것으로 보고 **전부 막는다** — 조용히 넓어지는 쪽으로 틀리지
    않는다.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entries = data.get("항목")
    if not isinstance(entries, list):
        return None
    return {(e.get("rule"), e.get("path")) for e in entries if isinstance(e, dict)}


def findings_of(sarif: dict) -> list[tuple[str, str, str, str]]:
    """(규칙, 수준, 위치, 파일) 목록. `level` 은 결과에 없으면 규칙 기본값에서 읽는다."""
    found: list[tuple[str, str, str, str]] = []
    for run in sarif.get("runs", []):
        driver = (run.get("tool") or {}).get("driver") or {}
        default_level = {
            rule.get("id"): ((rule.get("defaultConfiguration") or {}).get("level") or "warning")
            for rule in driver.get("rules", [])
        }
        for result in run.get("results", []):
            rule_id = result.get("ruleId") or "(규칙 미상)"
            level = result.get("level") or default_level.get(rule_id) or "warning"
            # **위치 없는 결과가 앞의 결과를 물려받지 않게 한다.** `uri`·`line` 을 매 결과마다
            # 새로 만든다 — 루프 밖에 두면 위치 없는 결과가 직전 파일에 귀속되고, 베이스라인
            # 대조가 (규칙, 파일) 키라서 **엉뚱한 새 발견이 「기존」으로 삼켜진다.**
            # 첫 결과가 위치 없으면 아예 죽는다(`UnboundLocalError`).
            physical = {}
            line = None
            locations = result.get("locations") or []
            if locations:
                first = locations[0].get("physicalLocation") or {}
                physical = first.get("artifactLocation") or {}
                line = (first.get("region") or {}).get("startLine")
            # 파일을 모르면 베이스라인에 맞을 수 없는 값을 쓴다 — 모르는 것이 조용히 면제되면
            # 안 된다. 이 값은 어떤 베이스라인 항목과도 일치하지 않는다.
            uri = str(physical.get("uri") or "(위치 미상)")
            where = f"{uri}:{line}" if line else uri
            found.append((rule_id, level, where, uri))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--language", default="(미상)")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="이미 받아들인 발견 목록")
    args = parser.parse_args()

    root = Path(args.dir)
    files = sorted(root.glob("*.sarif")) if root.is_dir() else []
    if not files:
        print(f"::error::SARIF 0건 — `{root}` 에서 분석 결과를 못 찾았다. 통과가 아니라 분석이 안 돈 것이다.")
        return 1

    baseline = load_baseline(Path(args.baseline))
    findings: list[tuple[str, str, str, str]] = []
    rules = 0
    for path in files:
        try:
            sarif = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"::error::{path.name} 을 읽지 못했다 ({error}) — 판독 불가는 통과가 아니다.")
            return 1
        for run in sarif.get("runs", []):
            rules += len(((run.get("tool") or {}).get("driver") or {}).get("rules", []))
        findings.extend(findings_of(sarif))

    at_level = [f for f in findings if f[1] in BLOCKING_LEVELS]
    if baseline is None:
        known: list[tuple[str, str, str, str]] = []
        blocking = at_level
        print(f"::warning::베이스라인을 못 읽었다({Path(args.baseline).name}) — 이번에는 전부 막는다")
    else:
        known = [f for f in at_level if (f[0], f[3]) in baseline]
        blocking = [f for f in at_level if (f[0], f[3]) not in baseline]
    print(
        f"CodeQL({args.language}) — SARIF {len(files)}개 · 규칙 {rules}개 · "
        f"발견 {len(findings)}건 (차단 수준 {len(at_level)}건 · 기존 {len(known)}건 · 새 {len(blocking)}건)"
    )
    if rules == 0:
        print("::error::규칙 0개로 분석됐다 — 질의 묶음이 안 실린 것이다. 통과가 아니다.")
        return 1

    blocking_set = set(blocking)
    for finding in findings:
        rule_id, level, where, _uri = finding
        line = f"  [{level}] {rule_id} — {where}"
        if finding in blocking_set:
            print(f"::error::{line.strip()}")
        elif finding in known:
            print(f"{line}  (베이스라인)")
        else:
            print(line)

    if blocking:
        print(
            "::error::베이스라인에 없는 CodeQL 발견이다 — 고치거나, 받아들일 것이면 "
            f"{Path(args.baseline).name} 에 사유와 함께 더해라. 경보를 받을 Security 탭이 private 에는 없다"
        )
        return 1
    print(f"판정: 새 발견 없음 (기존 {len(known)}건은 베이스라인에 고정돼 있다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
