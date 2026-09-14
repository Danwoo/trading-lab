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

#: 이 수준 이상만 잡을 빨갛게 한다. CodeQL 기본 묶음은 `note` 로 스타일 지적도 낸다.
BLOCKING_LEVELS = {"error", "warning"}


def findings_of(sarif: dict) -> list[tuple[str, str, str]]:
    """(규칙, 수준, 위치) 목록. `level` 은 결과에 없으면 규칙 기본값에서 읽는다."""
    found: list[tuple[str, str, str]] = []
    for run in sarif.get("runs", []):
        driver = (run.get("tool") or {}).get("driver") or {}
        default_level = {
            rule.get("id"): ((rule.get("defaultConfiguration") or {}).get("level") or "warning")
            for rule in driver.get("rules", [])
        }
        for result in run.get("results", []):
            rule_id = result.get("ruleId") or "(규칙 미상)"
            level = result.get("level") or default_level.get(rule_id) or "warning"
            locations = result.get("locations") or []
            where = "(위치 미상)"
            if locations:
                physical = (locations[0].get("physicalLocation") or {}).get("artifactLocation") or {}
                line = ((locations[0].get("physicalLocation") or {}).get("region") or {}).get("startLine")
                where = f"{physical.get('uri', '?')}:{line}" if line else str(physical.get("uri", "?"))
            found.append((rule_id, level, where))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--language", default="(미상)")
    args = parser.parse_args()

    root = Path(args.dir)
    files = sorted(root.glob("*.sarif")) if root.is_dir() else []
    if not files:
        print(f"::error::SARIF 0건 — `{root}` 에서 분석 결과를 못 찾았다. 통과가 아니라 분석이 안 돈 것이다.")
        return 1

    findings: list[tuple[str, str, str]] = []
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

    blocking = [f for f in findings if f[1] in BLOCKING_LEVELS]
    print(
        f"CodeQL({args.language}) — SARIF {len(files)}개 · 규칙 {rules}개 · "
        f"발견 {len(findings)}건 (차단 수준 {len(blocking)}건)"
    )
    if rules == 0:
        print("::error::규칙 0개로 분석됐다 — 질의 묶음이 안 실린 것이다. 통과가 아니다.")
        return 1

    for rule_id, level, where in findings:
        line = f"  [{level}] {rule_id} — {where}"
        print(f"::error::{line.strip()}" if level in BLOCKING_LEVELS else line)

    if blocking:
        print(
            "::error::CodeQL 발견을 고치거나, 오탐이면 질의 설정으로 걸러라 — "
            "경보를 받을 Security 탭이 private 에서는 없다"
        )
        return 1
    print("판정: 차단 수준 발견 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
