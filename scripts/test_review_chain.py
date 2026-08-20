"""review_chain 회귀 그물 — 「그 리뷰어를 못 쓴다」와 「리뷰가 불가능하다」가 갈려 있는지.

뒤집히기 쉬운 자리를 케이스로 잡는다:
  ① **기동 실패는 다음 후보로 간다** — 이 그물의 계기다. TUI 준비 실패로 첫 후보가 죽었을 때
     체인이 거기서 끝나면(실측: run 31815113895) 낡은 CHANGES_REQUESTED 가 살아남아 PR 이
     교착에 빠진다. rc 21 이 `continue=no` 로 되돌아가면 여기가 빨간불이 된다
  ② **`unable` 은 없어지지 않는다** — 체인의 **모든** 후보가 실패하면 여전히 판정 없음이다.
     양방향으로 못박는다: 기동 실패 하나 → 폴백 / 전부 실패 → chain-exhausted
  ③ **확정 실패는 「어느 후보도 못 돈다」일 때만** — Orca 불가용·판정부 번들 부재. 이 자리가
     넓어지면 ①이 다시 막히고, 좁아지면 못 도는 경로에 예산만 태운다
  ④ **폴백해도 첫 후보의 실패 사유가 남는다** — 폴백이 성공하면 체인은 초록으로 끝나는데,
     그때 사유가 사라지면 「첫 후보가 매번 기동 실패」가 조용히 상시화된다. 이 결함을 찾을 수
     있었던 것 자체가 annotation 의 「막힌 지점」 덕이다
  ⑤ **미지 rc 는 fail-closed** — 분류표에 없는 값이 조용히 폴백을 타면, 진짜로 고장난 리뷰어가
     아무도 모르게 claude 자기리뷰로 대체된다 (이 레포가 이름 붙인 「경로가 사라져도 초록」 부류)
  ⑥ **출력에 개행·탭이 새지 않는다** — `$GITHUB_OUTPUT` 은 줄 단위 형식이라, 사유 원문(신뢰
     경계 밖 문자열이 섞일 수 있다)이 개행을 실으면 뒤 키를 위조할 수 있다

케이스를 0건 모으면 실패한다 (fail-closed).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_chain as rc  # noqa: E402

TUI_FAIL = "에이전트 TUI 준비 실패(60s — 입력 상자가 화면에 나타나지 않았다)"

failures: list[str] = []
checks = 0


def check(label: str, actual: object, expected: object) -> None:
    global checks
    checks += 1
    if actual != expected:
        failures.append(f"{label}\n    기대: {expected!r}\n    실제: {actual!r}")


def summarize(chain: str, rows: list[tuple[str, int, str]]) -> dict[str, str]:
    tsv = "".join(f"{m}\t{code}\t{reason}\n" for m, code, reason in rows)
    return rc.summarize(chain.split(), rc.parse_attempts(tsv))


# ── ① 처분표 — 어떤 rc 가 다음 후보로 가는가 ─────────────────────────────────────
for code, kind, go_on in [
    (0, "ok", False),
    (10, "limit", True),
    (20, "transient", True),
    (21, "startup", True),  # ← 이 줄이 이번 개정의 전부다
    (1, "fatal", False),
    (30, "budget", False),
    (2, "unknown", False),  # ⑤ 분류표에 없는 값
    (99, "unknown", False),
]:
    check(f"① rc {code} 의 처분", rc.disposition(code), (kind, go_on))

# ── ② 기동 실패 → 다음 후보로, 그리고 그 후보가 성공하면 폴백이다 ────────────────
out = summarize("kimi claude", [("kimi", 21, TUI_FAIL), ("claude", 0, "")])
check("② 기동 실패 뒤 다음 후보가 판정을 냈다", out["effective"], "claude")
check("② 폴백으로 표기된다", out["fallback"], "yes")
check("② 판정이 났으므로 failure_kind 는 비어 있다", out["failure_kind"], "")
check("② 기동 실패한 후보가 기록된다", out["startup_failed"], "kimi")
check(
    "② 한도·일시장애 축은 오염되지 않는다",
    (out["exhausted"], out["degraded"]),
    ("", ""),
)

# ── ④ 폴백해도 첫 후보의 실패 사유가 남는다 ──────────────────────────────────────
check(
    "④ 폴백 사유에 첫 후보의 사유 원문이 실린다",
    TUI_FAIL in out["fallback_cause"],
    True,
)
check("④ 폴백 사유가 기동 실패임을 밝힌다", "기동 실패" in out["fallback_cause"], True)
check("④ 시도 이력에 첫 후보의 사유가 남는다", TUI_FAIL in out["attempts_note"], True)
check(
    "④ 시도 이력에 성공한 후보도 남는다",
    "claude: 판정 산출" in out["attempts_note"],
    True,
)

# ── ② 반대 방향 — 체인의 모든 후보가 실패하면 여전히 unable ─────────────────────
out = summarize("kimi claude", [("kimi", 21, TUI_FAIL), ("claude", 21, "리뷰 워크트리 생성 실패")])
check("② 전부 실패 → 판정 낸 모델 없음", out["effective"], "")
check("② 전부 실패 → 체인 소진", out["failure_kind"], "chain-exhausted")
check("② 전부 실패 → 폴백 아님", out["fallback"], "no")
check("② 전부 실패 → 두 후보가 다 기록된다", out["startup_failed"], "kimi·claude")
check(
    "② 전부 실패 → unable 사유가 산출된다",
    out["unable_reason"].endswith("fail-closed(리뷰 불가)"),
    True,
)
check("② 전부 실패 → 막힌 지점에 후보별 사유가 실린다", TUI_FAIL in out["stuck_at"], True)

# 체인이 한 명뿐이어도(claude 작성 → 폴백 없음) 기동 실패는 unable 로 끝난다
out = summarize("claude", [("claude", 21, TUI_FAIL)])
check("② 후보 1명 체인의 기동 실패 → unable", out["failure_kind"], "chain-exhausted")
check("② 후보 1명 체인 → 폴백 아님", out["fallback"], "no")

# ── ③ 확정 실패는 폴백하지 않는다 (어느 후보도 못 도는 상태) ────────────────────
out = summarize(
    "kimi claude",
    [("kimi", 1, "Orca 경로 불가용(런타임-불가용) — 리뷰 워커를 세울 수 없다")],
)
check("③ fatal 은 체인을 끊는다", out["failure_kind"], "confirmed")
check("③ fatal 은 기동 실패로 집계되지 않는다", out["startup_failed"], "")
check("③ fatal 의 막힌 지점에 사유가 실린다", "Orca 경로 불가용" in out["stuck_at"], True)

out = summarize("kimi claude", [("kimi", 30, "남은 예산 부족")])
check("③ 예산 소진은 체인을 끊는다", out["failure_kind"], "budget")

out = summarize("kimi claude", [("kimi", 7, "알 수 없는 실패")])
check("⑤ 미지 rc 는 폴백하지 않는다", out["failure_kind"], "confirmed")
check("⑤ 미지 rc 도 사유는 남는다", "알 수 없는 실패" in out["stuck_at"], True)

# ── 종전 두 분류(한도·일시장애)의 동작이 그대로인지 ───────────────────────────────
out = summarize(
    "codex kimi claude",
    [("codex", 10, "usage limit"), ("kimi", 20, "타임아웃"), ("claude", 0, "")],
)
check("한도 후보가 exhausted 로 남는다", out["exhausted"], "codex")
check("일시장애 후보가 degraded 로 남는다", out["degraded"], "kimi")
check("세 홉 뒤 폴백 성공", (out["effective"], out["fallback"]), ("claude", "yes"))
check(
    "폴백 사유가 종류별로 갈려 적힌다",
    out["fallback_cause"],
    "codex 한도 소진 + kimi 일시 장애(타임아웃·연결 끊김)",
)

# 첫 후보가 판정을 냈으면 폴백이 아니다
out = summarize("kimi claude", [("kimi", 0, "")])
check("1순위가 성공하면 폴백 아님", (out["effective"], out["fallback"]), ("kimi", "no"))
check("1순위 성공이면 폴백 사유가 없다", out["fallback_cause"], "")
check("1순위 성공이면 unable 사유가 없다", out["unable_reason"], "")

# ── ⑥ 개행·탭이 출력으로 새지 않는다 (신뢰 경계 밖 문자열 방어) ─────────────────
INJECT = "터미널 출력\nfallback=yes\neffective=claude\t끝"
out = summarize("kimi claude", [("kimi", 21, INJECT), ("claude", 21, "x")])
for key, value in out.items():
    check(f"⑥ {key} 에 개행이 없다", "\n" in value, False)
    check(f"⑥ {key} 에 탭이 없다", "\t" in value, False)

# 사유가 아무리 길어도 한 줄 상한을 넘지 않는다
out = summarize("kimi claude", [("kimi", 21, "가" * 500), ("claude", 0, "")])
check(
    "긴 사유는 잘린다",
    len(rc.parse_attempts("kimi\t21\t" + "가" * 500 + "\n")[0][2]) <= rc.REASON_MAX + 1,
    True,
)

# ── TSV 파싱 — 형식 위반 줄은 버리고 나머지를 살린다 ─────────────────────────────
parsed = rc.parse_attempts("kimi\t21\t사유\n\n형식위반\nclaude\t안숫자\tx\ncodex\t0\n")
check(
    "형식 위반 줄은 버린다",
    [(m, code) for m, code, _ in parsed],
    [("kimi", 21), ("codex", 0)],
)
check("사유 없는 줄도 읽힌다", parsed[1][2], "")

# ── CLI — 호출부(bash)가 실제로 읽는 형식 ────────────────────────────────────────
import io  # noqa: E402


def run_cli(argv: list[str], stdin_text: str) -> tuple[int, str]:
    buf, saved = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        code = rc.main(argv, stdin_text)
    finally:
        sys.stdout = saved
    return code, buf.getvalue()


code, out_text = run_cli(["review_chain.py", "step"], f"kimi\t21\t{TUI_FAIL}\n")
check("CLI step — 기동 실패는 계속", (code, out_text), (0, "kind=startup\ncontinue=yes\n"))
code, out_text = run_cli(["review_chain.py", "step"], "kimi\t1\tOrca 불가용\n")
check("CLI step — 확정 실패는 중단", (code, out_text), (0, "kind=fatal\ncontinue=no\n"))
code, out_text = run_cli(["review_chain.py", "step"], "")
check("CLI step — 이력이 비면 fail-closed", (code, "continue=no" in out_text), (1, True))
code, out_text = run_cli(
    ["review_chain.py", "summarize", "kimi claude"],
    f"kimi\t21\t{TUI_FAIL}\nclaude\t0\t\n",
)
keys = [line.split("=", 1)[0] for line in out_text.strip().splitlines()]
check(
    "CLI summarize — 워크플로가 읽는 키 전량",
    keys,
    [
        "effective",
        "fallback",
        "exhausted",
        "degraded",
        "startup_failed",
        "failure_kind",
        "stuck_at",
        "attempts_note",
        "fallback_cause",
        "unable_reason",
    ],
)
code, _ = run_cli(["review_chain.py", "bogus"], "")
check("CLI — 미지 하위명령은 거절", code, 2)

# ── fail-closed: 케이스를 0건 모으면 실패한다 ────────────────────────────────────
print(f"검사한 케이스 {checks}건 · 실패 {len(failures)}건")
if checks == 0:
    print("::error::케이스를 0건 모았습니다 — fail-closed 종료")
    raise SystemExit(1)
if failures:
    for f in failures:
        print(f"::error::{f}")
    raise SystemExit(1)
print("리뷰어 체인 분류·집계 회귀 그물 통과")
