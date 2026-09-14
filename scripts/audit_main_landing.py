#!/usr/bin/env python3
"""main 에 착륙한 커밋이 규약을 거쳤는지 **사후에** 판정한다 (#420 P2, fail-closed).

## 왜 있나

이 계정은 GitHub Free 라 **private 으로 돌리는 순간 `main protection` ruleset 이 사라진다** —
PR 필수·승인 1건·게이트 3종이 통째로 없어진다. 리드 결정은 결제하지 않는다(2026-08-29)이므로
예방(서버 규칙)의 일부를 **발각**(사후 감사)으로 옮긴다.

예방이 약해지는 것을 감수하는 근거는 위협 모델이다 — 이 레포의 적대자는 침입자가 아니라
**실수**다(1인 레포, 에이전트가 리드와 같은 계정으로 민다). 실수는 조용히 지나가면 굳고,
시끄럽게 잡히면 즉시 되돌려진다. 그래서 「막지 못해도 반드시 발각된다」가 성립하면 교환이 선다.

`.githooks` 계열 예방층(P1, `scripts/reject_push_to_main.py`)이 짝이다. 그쪽은 `--no-verify` 로
지나갈 수 있고, 지나간 것을 잡는 것이 여기다.

## 무엇을 판정하나

착륙한 커밋마다 셋을 본다. **하나라도 못 읽으면 통과가 아니다.**

1. **PR 을 거쳤는가** — 그 커밋을 담은 머지된 PR 이 있는가.
2. **리뷰 통과 마커가 있는가** — 그 PR 에 `verdict=merge_ok sha=<머지된 head>` 마커가 있는가.
   `sha=` 가 어긋나면 **리뷰 뒤에 커밋이 더 얹힌 것**이므로 그 리뷰는 그 코드를 안 봤다.
3. **게이트가 초록이었는가** — required 체크 3종(`test: backend`·`test: frontend`·`test: repo`)이
   그 head 에서 전부 성공인가.

문서 전용 PR 은 면제 규약(루트 `CLAUDE.md`)대로 리뷰 마커 대신 App 승인으로 선다 — 그 경우
리뷰 마커를 요구하지 않되, **게이트는 그대로 요구한다.** 「문서 전용」이 무엇인지는 여기서
정하지 않고 `review_notice.py` 를 부른다 — 그 판정이 실제로 App 승인·리뷰 건너뜀을 만드는
자리이고, 감사가 자기 정의를 두면 정당한 착륙이 영영 위반으로 적힌다.

## fail-closed

검사한 커밋이 0건이면 실패한다. 「볼 것이 없었다」와 「위반이 없었다」는 다르고, 조회가 깨져
0건이 되는 경로가 실제로 있다(API 한도·권한·경로 변경). 검사한 수를 항상 출력한다.

## 실행

    # CI (push: main) — 이 push 가 옮긴 커밋들을 본다
    python3 scripts/audit_main_landing.py --repo Danwoo/trading-lab --commits <sha>...

    # 오프라인 판정 (테스트·재현) — 조회 결과를 파일로 준다
    python3 scripts/audit_main_landing.py --input evidence.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_notice import decide as judge_docs_only  # noqa: E402
from review_record import _FULL_SHA, _MARKER, is_trusted_author  # noqa: E402
from verify_upstream_gate import CHECK_NAME_PREFIX, latest_by_name  # noqa: E402

#: ruleset 이 required 로 걸고 있던 것과 같은 이름 — 사라져도 여기서 계속 요구한다.
REQUIRED_CHECKS = ("test: backend", "test: frontend", "test: repo")
# 최신값 판정(`latest_by_name`)은 이 접두로 체크런을 거른다. 접두 밖 이름을 required 로 넣으면
# 그 체크는 영영 「없다」로 읽히므로, 두 목록이 갈리는 순간 기동에서 막는다.
assert all(name.startswith(CHECK_NAME_PREFIX) for name in REQUIRED_CHECKS), (
    f"REQUIRED_CHECKS 가 '{CHECK_NAME_PREFIX}' 로 시작하지 않는다 — latest_by_name 이 그 체크를 거른다"
)

#: 리뷰 통과 마커 — 문법도 `review_record` 것을 그대로 쓴다.
#: 종전에는 여기서 느슨한 정규식을 따로 짰는데, `model=` 도 닫는 `-->` 도 요구하지 않아
#: 기존 층이 거부하는 모양을 통과시켰다. **마지막 방어선의 파서가 앞 층보다 느슨하면**
#: 앞을 조여도 뒤가 열려 있다.
MARKER = _MARKER


def _marker_of(comments: list[dict[str, Any]]) -> tuple[str, str, bool] | None:
    """가장 마지막 리뷰 마커의 (verdict, sha, 수동 여부). 없으면 None.

    **누가 썼는지를 본다.** 마커는 텍스트일 뿐이고 head sha 는 공개 정보라, 저자를 안 가르면
    아무 GitHub 사용자나 코멘트 하나로 「리뷰 통과」를 만들어 낼 수 있다. 이 감사는 private
    전환으로 사라지는 승인 규칙을 대신하는 마지막 방어선이므로, 그 자리가 뚫리면 이 층 전체가
    뜻을 잃는다.

    판정은 **여기서 새로 짜지 않고** `review_record.is_trusted_author` 를 그대로 쓴다 — 같은
    마커를 읽는 자리가 둘이 되면 한쪽만 조여도 다른 쪽이 열려 있다.
    """
    found: tuple[str, str, bool] | None = None
    for comment in comments:
        if not isinstance(comment, dict) or not is_trusted_author(_authorship_of(comment)):
            continue
        for match in MARKER.finditer(comment.get("body") or ""):
            found = (match.group("verdict"), match.group("sha"), bool(match.group("manual")))
    return found


def _authorship_of(comment: dict[str, Any]) -> dict[str, Any]:
    """`is_trusted_author` 가 읽는 평평한 모양으로 옮긴다 — GitHub 응답은 `user` 가 중첩이다.

    없는 값은 없는 채로 넘긴다. 채워 넣으면 「저자를 몰랐다」가 「믿을 만한 저자였다」로 바뀐다.
    """
    user = comment.get("user")
    user = user if isinstance(user, dict) else {}
    return {
        "author_association": comment.get("author_association"),
        "user_login": comment.get("user_login", user.get("login")),
        "user_type": comment.get("user_type", user.get("type")),
    }


def _is_docs_only(files: list[str] | None) -> bool:
    """문서 전용인가 — **정의를 여기 두지 않는다.**

    면제를 실제로 만들어 내는 것은 `review_notice.py` 다: `ci.yml` 의 docs-notice 잡이 그
    판정으로 App 승인 + 자동 머지 arm 을 걸고, `cross-review.yml` 의 `paths-ignore` 가 같은
    목록으로 리뷰를 건너뛴다. 감사가 자기 정의를 따로 가지면 **셋째 정의**가 되어, 정당하게
    착륙한 md-only PR 을 영구히 위반으로 적는다 — 그리고 고칠 방법이 없다(그 PR 들에는 리뷰
    마커를 달 경로가 애초에 안 돈다). 상시 빨간 감사는 위협 모델 §4.3 이 적은 「발각이 행동으로
    이어지지 않는」 상태 그 자체다.

    fail-closed 극성도 그쪽 것을 그대로 쓴다 — 목록을 못 읽었으면 문서 전용이 아니다.
    """
    if files is None:
        return False
    return bool(judge_docs_only({"files": files}).get("docs_only"))


def judge_commit(evidence: dict[str, Any]) -> dict[str, Any]:
    """커밋 하나의 판정. **순수 함수** — 네트워크를 타지 않는다.

    evidence: {sha, pulls: [{number, merged, merge_commit_sha, head_sha, files, comments, checks}]}
    """
    sha = evidence.get("sha") or ""
    verdict: dict[str, Any] = {"sha": sha, "violations": [], "notes": []}

    pulls = evidence.get("pulls")
    if pulls is None:
        # 조회 자체가 안 된 것과 「PR 이 없다」는 다르다 — 뭉개면 fail-open 이 된다.
        verdict["violations"].append("PR 조회 결과를 못 읽었다 — 판정할 근거가 없다")
        return verdict

    merged = [p for p in pulls if p.get("merged")]
    if not merged:
        verdict["violations"].append("PR 을 거치지 않고 착륙했다")
        return verdict

    pr = merged[0]
    verdict["pr"] = pr.get("number")
    head = (pr.get("head_sha") or "").lower()

    # ── 게이트 — 문서 면제와 무관하게 요구한다 ────────────────────
    checks = pr.get("checks")
    if checks is None:
        verdict["violations"].append(f"PR #{pr.get('number')}: 체크 결과를 못 읽었다")
    else:
        # **같은 이름의 체크런이 여럿일 수 있다** — 재실행이 이 레포의 정규 운용이다
        # (루트 CLAUDE.md 「쓸어담기」의 `gh run rerun --failed`). 그냥 딕셔너리로 접으면
        # API 가 준 순서에서 나중 것이 이기는데, 그 순서는 어디에서도 보장되지 않는다.
        # 재실행으로 통과한 착륙이 영영 빨갛게 남거나, 반대로 실패가 초록으로 읽힌다.
        # 판정은 `verify_upstream_gate.latest_by_name` — 같은 엔드포인트를 같은 목적으로 읽는
        # 정본이고, 주석이 「재실행 대비」를 명시한다.
        by_name = {name: (record.get("conclusion") or "").lower() for name, record in latest_by_name(checks).items()}
        for name in REQUIRED_CHECKS:
            got = by_name.get(name)
            if got is None:
                verdict["violations"].append(f"PR #{pr.get('number')}: 게이트 「{name}」 가 없다")
            elif got not in ("success", "skipped"):
                verdict["violations"].append(f"PR #{pr.get('number')}: 게이트 「{name}」 가 {got}")

    # ── 리뷰 — 문서 전용이면 면제 (App 승인이 그 자리를 받는다) ──────
    # 파일 목록을 **못 읽었으면**(`None`) 면제하지 않는다 — `review_notice.decide` 가 빈 목록을
    # fail-closed 로 처리하지만, 여기서 `or []` 로 뭉개면 「못 읽었다」와 「바뀐 파일이 없다」가
    # 같은 값이 되어 의도가 안 보인다.
    if _is_docs_only(pr.get("files")):
        verdict["notes"].append("문서 전용 — 리뷰 마커 면제 (게이트는 요구함)")
        return verdict

    comments = pr.get("comments")
    if comments is None:
        verdict["violations"].append(f"PR #{pr.get('number')}: 코멘트를 못 읽었다 — 리뷰 여부를 판정할 수 없다")
        return verdict

    marker = _marker_of(comments)
    if marker is None:
        verdict["violations"].append(f"PR #{pr.get('number')}: 리뷰 통과 마커가 없다")
        return verdict

    got_verdict, marker_sha, manual = marker
    if got_verdict != "merge_ok":
        verdict["violations"].append(f"PR #{pr.get('number')}: 리뷰 판정이 merge_ok 가 아니다 ({got_verdict})")
    # **sha 는 40자 동등 비교다** — 접두 비교는 앞자리만 같은 다른 커밋의 판정을 통과시킨다.
    # `review_record` 가 같은 마커에 거는 규칙과 한 글자도 다르지 않아야 한다.
    elif not _FULL_SHA.match(marker_sha or ""):
        verdict["violations"].append(f"PR #{pr.get('number')}: 마커의 sha 가 40자가 아니다 ({marker_sha})")
    elif head and marker_sha != head:
        # 리뷰 뒤에 커밋이 더 얹혔다 — 그 리뷰는 머지된 코드를 본 적이 없다.
        verdict["violations"].append(
            f"PR #{pr.get('number')}: 리뷰가 본 커밋({marker_sha[:7]})과 머지된 커밋({head[:7]})이 다르다"
        )
    if manual:
        # 수동 마커는 **자동 머지 권한을 얻지 못한다**(#285 규약). 그러나 리뷰가 없었던 것은
        # 아니다 — 신뢰 저자가 붙인 판정이므로 감사는 통과시키되 기록에 남긴다. 「사람이 손으로
        # 붙였다」와 「CI 가 판정했다」를 같은 줄로 적으면 나중에 구분할 근거가 사라진다.
        verdict["notes"].append("수동 리뷰 마커(source=manual) — 자동 머지 경로가 아니다")
    return verdict


def judge_all(evidences: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """전체 판정과 종료 코드. **검사 0건은 실패다.**"""
    results = [judge_commit(e) for e in evidences]
    if not results:
        return results, 1
    return results, 1 if any(r["violations"] for r in results) else 0


# ── 조회 (얇게) ─────────────────────────────────────────────────


def _gh(path: str) -> Any:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


#: 한 페이지 상한. GitHub 의 최대값이고, 이보다 크게 주면 무시된다.
PER_PAGE = 100
#: 페이지를 무한히 따라가지 않는다 — 한도에 닿으면 **못 읽은 것으로 본다**(fail-closed).
MAX_PAGES = 50


def _gh_paged(path: str, key: str | None = None) -> list[Any] | None:
    """모든 페이지를 이어 붙인다. 한 페이지라도 못 읽으면 `None`.

    **한 페이지만 읽으면 fail-open 이 된다.** 앞 100개가 문서이고 101번째가 코드인 PR 은
    잘린 목록만 보면 「문서 전용」이 되어 리뷰 마커를 면제받는다 (#420 리뷰 지적). 체크런도
    같다 — 2페이지의 빨간 체크를 못 보면 「게이트가 초록이었다」가 된다.

    못 읽은 것은 빈 목록이 아니라 `None` 으로 낸다. 빈 목록으로 뭉개면 「볼 것이 없었다」가
    「위반이 없었다」로 읽힌다.
    """
    out: list[Any] = []
    joiner = "&" if "?" in path else "?"
    for page in range(1, MAX_PAGES + 1):
        chunk = _gh(f"{path}{joiner}per_page={PER_PAGE}&page={page}")
        if chunk is None:
            return None
        items = chunk.get(key) if key else chunk
        if not isinstance(items, list):
            return None
        out.extend(items)
        if len(items) < PER_PAGE:
            return out
    # 한도까지 왔다 = 아직 남았을 수 있다. 여기서 멈추면 잘린 목록을 완전한 것으로 쓰게 된다.
    return None


def collect(repo: str, sha: str) -> dict[str, Any]:
    pulls_raw = _gh(f"repos/{repo}/commits/{sha}/pulls")
    if pulls_raw is None:
        return {"sha": sha, "pulls": None}

    pulls = []
    for pr in pulls_raw:
        number = pr.get("number")
        head_sha = (pr.get("head") or {}).get("sha")
        files_raw = _gh_paged(f"repos/{repo}/pulls/{number}/files")
        comments_raw = _gh_paged(f"repos/{repo}/issues/{number}/comments")
        checks_raw = _gh_paged(f"repos/{repo}/commits/{head_sha}/check-runs", key="check_runs") if head_sha else None
        pulls.append(
            {
                "number": number,
                "merged": bool(pr.get("merged_at")),
                "head_sha": head_sha,
                # 못 읽었으면 빈 목록이 아니라 `None` — 문서 전용 면제로 새지 않는다.
                "files": [f.get("filename") for f in files_raw] if files_raw is not None else None,
                "comments": comments_raw,
                "checks": checks_raw,
            }
        )
    return {"sha": sha, "pulls": pulls}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="main 착륙 커밋 사후 감사 (fail-closed)")
    parser.add_argument("--repo", help="owner/name")
    parser.add_argument("--commits", nargs="*", default=[], help="판정할 커밋 sha")
    parser.add_argument("--input", help="조회 결과 JSON (오프라인 판정)")
    args = parser.parse_args(argv)

    if args.input:
        with open(args.input, encoding="utf-8") as handle:
            evidences = json.load(handle)
    elif args.repo and args.commits:
        evidences = [collect(args.repo, sha) for sha in args.commits]
    else:
        print("::error::--input 또는 --repo/--commits 가 필요하다", file=sys.stderr)
        return 1

    results, code = judge_all(evidences)

    print(f"검사한 착륙 커밋 {len(results)}건")
    for result in results:
        head = f"  {result['sha'][:7]}"
        if result.get("pr"):
            head += f" (PR #{result['pr']})"
        if result["violations"]:
            print(f"{head} — 위반 {len(result['violations'])}건")
            for line in result["violations"]:
                print(f"::error::{result['sha'][:7]}: {line}")
        else:
            note = f" — {result['notes'][0]}" if result["notes"] else ""
            print(f"{head} — 규약대로 착륙{note}")

    if not results:
        print("::error::검사한 커밋이 0건 — 조회가 깨졌거나 대상을 못 읽었다 (fail-closed)", file=sys.stderr)
    print("판정: " + ("위반 있음" if code else "전부 규약대로 착륙"))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
