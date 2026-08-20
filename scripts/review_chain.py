"""리뷰어 체인의 실패 분류·집계 — I/O 없는 순수 함수 (stdlib 전용).

## 왜 있나

`cross-review.yml` 은 후보 리뷰어를 순차로 시도하다 실패하면 다음 후보로 넘어간다. 그
「넘어갈 것인가」 판정이 YAML 안 bash `case` 에 있었고, **한도(10)·일시장애(20) 두 종만
폴백 대상**이었다. 그 밖의 모든 실패는 `confirmed` 로 접혀 **첫 후보에서 체인이 끝났다**.

실측 (run 31815113895, PR #70 — 2026-08-14):

    경로 가용성: ORCA_OK=yes (런타임-ok+ready) / 체인: kimi claude
    리뷰 후보 실행: kimi
    ##[error]CI 교차 리뷰 실패 — 판정 없음 (원인 confirmed / 막힌 지점:
      kimi: 에이전트 TUI 준비 실패(60s — 입력 상자가 화면에 나타나지 않았다) )

`리뷰 후보 실행:` 은 **한 줄뿐**이다. 체인에 claude 가 있는데 시도조차 하지 않았다.
kimi 의 TUI 가 안 뜬 것은 **그 리뷰어를 못 쓴다**는 뜻이지 **리뷰가 불가능하다**는 뜻이
아니다. 그런데 `unable` 로 접히면 낡은 `CHANGES_REQUESTED` 가 살아남아 PR 이 교착에 빠진다.

## 무엇을 가르나 — 확정 실패의 정의를 좁힌다

**확정 실패(`fatal`)는 「어느 후보로도 리뷰를 실행할 수 없다」일 때만이다.** 특정 후보 하나가
기동에 실패한 것은 그 후보의 문제이므로 다음 후보로 넘어간다. 체인은 유한하고, 전부 실패하면
종전대로 `unable` 이다 — 줄이려는 것은 **첫 후보에서의 조기 종결**뿐이다.

    rc  종류        다음 후보로  무엇
     0  ok          -            판정 산출 (체인 종료, 성공)
    10  limit       예           한도 확증 (깨끗한 채널 stderr 프로브)
    20  transient   예           워커 타임아웃 · 판정 폴링 조회 불가
    21  startup     예           **리뷰어 기동 실패** — 이 판본이 새로 가른 것
     1  fatal       아니오       어느 후보도 못 돈다 (Orca 불가용 · 판정부 번들 부재)
    30  budget      아니오       체인 예산 소진 — 남은 시간이 한 홉을 못 담는다
     그 밖         unknown      아니오       미지 rc — fail-closed (조용히 폴백하지 않는다)

`startup` 에 들어가는 것 (전부 「그 리뷰어가 뜨지도 못했다」):

  · 리뷰 워크트리 생성 실패
  · 리뷰어 터미널 생성 실패 (claude 2단계 경로)
  · 에이전트 핸들 취득 실패
  · 에이전트 TUI 준비 실패 (입력 상자가 화면에 나타나지 않음)
  · 리뷰 지시 전달 실패 (`orca-ide terminal send` 명령 자체가 실패)

`fatal` 에 남는 것 (후보를 갈아도 결과가 같다):

  · Orca 런타임 불가용 — 리뷰 워커를 세우는 경로가 그것 하나다
  · 준비·접수 판정부(`ctx/terminal_state.py`) 번들 부재 — 후보와 무관한 번들 결손

**판정 산출물의 형식 위반은 여기 들어오지 않는다.** 그건 리뷰어가 **돌긴 돌았다**는 뜻이라
축이 다르다. 형식 위반 마커는 폴링 파서가 인정하지 않아 마커 미검출로 남고, 그 경로는
타임아웃(rc 20 · `transient`)으로 접힌다 — 종전 분류 그대로다. 산출물이 끝내 유효하지 않으면
`cross-review.yml` 의 「판정 정규화」 스텝이 fail-closed 로 `unable` 을 쓴다.

## 무엇을 기록하나 — 폴백해도 첫 후보의 실패 사유는 남는다

지금 이 결함을 찾을 수 있었던 것은 annotation 이 「막힌 지점: kimi」를 적어 준 덕이다. 폴백이
성공해 체인이 초록으로 끝나면 그 기록이 사라질 수 있는데, 그러면 **kimi 가 매번 기동에
실패하는 상태가 조용히 상시화**된다. 그래서 집계는 성공했을 때도 `attempts_note`(시도 이력)에
후보별 결과를 남기고, 폴백 사유(`fallback_cause`)에 실패한 후보의 **사유 원문**을 싣는다.

CLI (bash 호출부용 — 시도 이력 TSV `모델<TAB>rc<TAB>사유` 를 stdin 으로 받는다):

    printf '%s\\t%s\\t%s\\n' kimi 21 "에이전트 TUI 준비 실패(60s)" >> attempts.tsv
    python3 scripts/review_chain.py step      < attempts.tsv   # 마지막 시도의 처분
    python3 scripts/review_chain.py summarize "kimi claude" < attempts.tsv

`step` 은 `kind=` 와 `continue=yes|no` 두 줄을, `summarize` 는 `$GITHUB_OUTPUT` 에 그대로
붙일 수 있는 `key=value` 줄들을 낸다. 값에는 개행이 들어가지 않는다 (아래 `_flatten`).
"""

from __future__ import annotations

import sys

# ── 분류표 (단일 출처) ────────────────────────────────────────────────────────────
# rc → (종류, 다음 후보로 갈 것인가)
RC_KINDS: dict[int, tuple[str, bool]] = {
    0: ("ok", False),
    10: ("limit", True),
    20: ("transient", True),
    21: ("startup", True),
    1: ("fatal", False),
    30: ("budget", False),
}
UNKNOWN = ("unknown", False)

# 종류 → 사람이 읽는 이름. 폴백 사유·시도 이력·요약이 전부 이 어휘를 쓴다.
KIND_KO: dict[str, str] = {
    "ok": "판정 산출",
    "limit": "한도 소진",
    "transient": "일시 장애(타임아웃·연결 끊김)",
    "startup": "기동 실패",
    "fatal": "확정 실패(어느 후보도 실행 불가)",
    "budget": "체인 예산 소진",
    "unknown": "미지 실패(분류 불가 — fail-closed)",
}

# 사유 원문의 상한 — 코멘트 첫 줄·annotation 한 줄에 실린다. 종전 bash 의 `head -c 160` 승계.
REASON_MAX = 160


def disposition(rc: int) -> tuple[str, bool]:
    """종료 코드 하나의 처분 — (종류, 다음 후보로 갈 것인가)."""
    return RC_KINDS.get(rc, UNKNOWN)


def _flatten(text: str) -> str:
    """한 줄로 편다 — `$GITHUB_OUTPUT` 은 줄 단위 형식이고 TSV 는 탭이 구분자다."""
    return " ".join(text.replace("\t", " ").split())


def _clip(text: str) -> str:
    flat = _flatten(text)
    return flat if len(flat) <= REASON_MAX else flat[:REASON_MAX] + "…"


def parse_attempts(text: str) -> list[tuple[str, int, str]]:
    """시도 이력 TSV → [(모델, rc, 사유)]. 빈 줄·형식 위반 줄은 버린다."""
    attempts: list[tuple[str, int, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        model, raw_rc = parts[0].strip(), parts[1].strip()
        reason = parts[2] if len(parts) > 2 else ""
        try:
            rc = int(raw_rc)
        except ValueError:
            continue
        attempts.append((model, rc, _clip(reason)))
    return attempts


def _cause_phrase(kind: str, entries: list[tuple[str, str]]) -> str:
    """한 종류의 실패들을 사람이 읽는 한 조각으로. entries=[(모델, 사유)]."""
    models = "·".join(model for model, _ in entries)
    if kind in ("limit", "transient"):
        # 한도·일시장애는 사유 원문이 정형이라 모델 이름만으로 충분하다 (종전 문구 유지).
        return f"{models} {KIND_KO[kind]}"
    reasons = " / ".join(reason for _, reason in entries if reason)
    if reasons:
        return f"{models} {KIND_KO[kind]}({reasons})"
    return f"{models} {KIND_KO[kind]}"


def summarize(chain: list[str], attempts: list[tuple[str, int, str]]) -> dict[str, str]:
    """체인 시도 이력 → 워크플로 출력 키.

    호출부(bash)가 분기를 늘리지 않도록 **사람이 읽는 문구까지** 여기서 만든다.
    """
    effective = ""
    stop_kind = ""
    stop_at = ""
    by_kind: dict[str, list[tuple[str, str]]] = {}
    notes: list[str] = []

    for model, rc, reason in attempts:
        kind, go_on = disposition(rc)
        if kind == "ok":
            effective = model
            notes.append(f"{model}: {KIND_KO['ok']}")
            break
        by_kind.setdefault(kind, []).append((model, reason))
        notes.append(f"{model}: {KIND_KO[kind]}" + (f" — {reason}" if reason else ""))
        if not go_on:
            stop_kind = kind
            stop_at = f"{model}: {reason}" if reason else model
            break

    first_hop = chain[0] if chain else ""
    fallback = bool(effective) and effective != first_hop

    exhausted = "·".join(m for m, _ in by_kind.get("limit", []))
    degraded = "·".join(m for m, _ in by_kind.get("transient", []))
    startup_failed = "·".join(m for m, _ in by_kind.get("startup", []))

    # 실패 분류 — 어휘는 종전 그대로다 (판정 코멘트의 「원인 분류」가 이 값을 싣는다).
    if effective:
        failure_kind = ""
    elif stop_kind == "budget":
        failure_kind = "budget"
    elif stop_kind:
        failure_kind = "confirmed"
    else:
        failure_kind = "chain-exhausted"
        stop_at = f"체인 전체({' '.join(chain)})"
        detail = "; ".join(notes)
        if detail:
            stop_at = f"{stop_at} — {detail}"

    # 폴백 사유 — 실패한 후보들을 종류별로 묶어 적는다. 사람이 취할 행동이 종류마다 다르다:
    # 한도는 충전·리뷰어 공급, 일시 장애는 재실행, 기동 실패는 그 리뷰어의 런타임 점검.
    causes = [
        _cause_phrase(kind, by_kind[kind]) for kind in ("limit", "transient", "startup", "unknown") if by_kind.get(kind)
    ]
    fallback_cause = " + ".join(causes)
    if fallback and not fallback_cause:
        # 폴백이 났는데 사유가 하나도 안 남았다면 그 자체가 이상 신호다 — 지어내지 않는다.
        fallback_cause = "1순위 리뷰어 실패(사유 미기록 — 잡 로그 확인 필요)"

    unable_reason = ""
    if not effective:
        head = {
            "chain-exhausted": "리뷰어 체인 소진 — 모든 후보가 실패했다",
            "confirmed": "리뷰어 실행이 확정 실패 (어느 후보로도 리뷰를 실행할 수 없다)",
            "budget": "체인 예산 소진 (리뷰가 상한 시간 내에 끝나지 않음)",
        }[failure_kind]
        unable_reason = (
            head
            + (f". 한도 소진: {exhausted}" if exhausted else "")
            + (f". 일시 장애: {degraded}" if degraded else "")
            + (f". 기동 실패: {startup_failed}" if startup_failed else "")
            + (f". 막힌 지점: {stop_at}" if stop_at else "")
            + " — fail-closed(리뷰 불가)"
        )

    return {
        "effective": effective,
        "fallback": "yes" if fallback else "no",
        "exhausted": exhausted,
        "degraded": degraded,
        "startup_failed": startup_failed,
        "failure_kind": failure_kind,
        "stuck_at": _flatten(stop_at),
        "attempts_note": _flatten("; ".join(notes)),
        "fallback_cause": _flatten(fallback_cause),
        "unable_reason": _flatten(unable_reason),
    }


def main(argv: list[str], stdin_text: str) -> int:
    if len(argv) < 2 or argv[1] not in ("step", "summarize"):
        print(
            "usage: review_chain.py step|summarize [<chain>] < attempts.tsv",
            file=sys.stderr,
        )
        return 2

    attempts = parse_attempts(stdin_text)

    if argv[1] == "step":
        if not attempts:
            print("::error::시도 이력이 비어 있다 — 처분을 판정할 수 없다")
            print("kind=unknown")
            print("continue=no")
            return 1
        kind, go_on = disposition(attempts[-1][1])
        print(f"kind={kind}")
        print(f"continue={'yes' if go_on else 'no'}")
        return 0

    chain = argv[2].split() if len(argv) > 2 else []
    for key, value in summarize(chain, attempts).items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv, sys.stdin.read()))
