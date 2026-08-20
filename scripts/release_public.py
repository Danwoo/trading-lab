"""공개 배포 — 개발 레포의 현재 트리를 공개 레포로 내보낸다 (#360 · #287).

**이사 1회용 도구이고, 이미 그 한 번을 돌았다** (2026-08-07, `trading-lab` 첫 커밋). 리드
결정(2026-08-07)으로 개발 자리 자체가 공개 레포로 옮겨왔다 — 그 뒤의 변경은 이 공개 레포의
보통 커밋·PR 이다. 「매번 하는 릴리스」는 없다. 옛 개발 레포는 보관용으로 남았다.
이것을 다시 돌리면 목적지 트리를 통째로 덮으므로(아래 ②), **다시 쓰지 않는다.**
남겨 둔 이유는 공개 트리가 어떻게 만들어졌는지의 실행 가능한 기록이기 때문이다 —
`THIRD-PARTY-NOTICES.md` 「히스토리 노출면」이 이 파일을 출처로 인용하고,
`scripts/test_public_release_gate.py`(매 PR CI)가 이 모듈을 import 해 게이트 우회를 재현한다.

기본 동작은 **드라이런**이다. 실제로 밀려면 `--execute` 를 붙여야 한다.
공개 push 는 되돌릴 수 없으므로, 아무 인자도 안 준 실행이 사고가 되지 않게 한다.

    python3 scripts/release_public.py --remote <url|경로>            # 드라이런
    python3 scripts/release_public.py --remote <url|경로> --execute  # 실제 push

──────────────────────────────────────────────────────────────────────────────
## ① 무엇을 미는가 — `git archive` 한 갈래뿐

내보내기 트리는 **오직** `git archive <커밋>` 으로 만든다. 이 명령은 그 커밋의 **트리만**
tar 로 뱉는다 — `.git` 도, 히스토리도, gitignore 대상도, 워킹트리의 미커밋 변경도 담기지
않는다. 「히스토리를 안 내보낸다」가 **의도가 아니라 사용한 명령의 성질**이 된다.

이 스크립트에는 `push --mirror`·`--force`·`--tags`·`--all` 이 **한 줄도 없다.** 개발 레포의
`.git` 을 공개 원격에 연결하는 경로도 없다 (공개 원격은 **별도 임시 클론**에만 붙는다).
리드 결정(#360, 2026-08-04)의 「히스토리 포함 경로를 구조적으로 못 쓰게」가 이것이다 —
사람이 손으로 다른 명령을 치는 것까지는 못 막지만, **정상 경로가 명령 한 줄이면 그걸 안 쓸
이유가 없다**.

내보내는 커밋은 기본이 `origin/main` 이다. `--source-ref` 로 바꿀 수 있지만, **`origin/main`
에서 도달 가능한 커밋이어야 한다**(fail-closed). 미머지 브랜치·로컬 실험 커밋이 공개본으로
새는 경로를 닫는다. 워킹트리가 더러우면 애초에 멈춘다 — 내보내기가 `git archive` 라 더티
변경은 실리지 않지만, 「지금 보고 있는 것」과 「나가는 것」이 다른 상태에서 사람이 확인 버튼을
누르는 상황 자체를 만들지 않는다.

──────────────────────────────────────────────────────────────────────────────
## ② 한 번만 민다 — **쌓는다. force push 하지 않는다.**

**판단: 빈 공개 레포 위에 커밋 하나를 얹는다 (fast-forward 전용, force push 없음).**
그 커밋이 공개본의 초기 커밋이고, 그 뒤로는 사람과 에이전트가 공개 레포에 평범하게 커밋한다.

1회용인데 구현이 「목적지 기본 브랜치 위에 append」인 이유 3가지:

  · **첫 push 자체가 append 다.** 빈 레포에 커밋을 얹는 것은 「직전이 없는 append」이지
    특별한 경로가 아니다. 1회용이라고 다른 코드를 쓸 이유가 없다.
  · **재실행 안전성이 이사 당일의 복구 경로다.** 드라이런과 실행 사이에서 무엇이 어긋나
    중간에 멈춰도 같은 명령을 다시 돌리면 된다 (내용이 같으면 빈 커밋을 만들지 않는다).
  · **force push 가 없다는 사실 자체가 방어다.** 목적지에 예상 못 한 커밋이 있으면
    non-fast-forward 로 **실패한다** — 조용히 덮어쓰는 것보다 낫다. 되돌릴 수 없는
    연산을 이 스크립트에 두지 않는다.

커밋 메시지에는 출처 개발 커밋 SHA 를 `Source-Commit:` 트레일러로 적는다 (google/copybara 가
목적지 커밋에 원본 식별자를 라벨로 남기는 것과 같은 역할). 공개본의 초기 커밋만 보고도
「이 스냅샷이 개발 레포의 어느 커밋인지」를 알 수 있으면서, 개발 히스토리 자체는 한 커밋도
넘어가지 않는다.

구현: 공개 원격을 임시 디렉터리에 **클론**하고(이사 대상이면 빈 레포), 그 워킹트리의 추적
파일을 전부 지운 뒤 내보내기 트리를 복사하고 `git add -A` 한다. 삭제된 파일도 자동으로
반영되고, 결과 트리는 항상 개발 트리와 **정확히 일치**한다. push 는 `--force` 없이 하므로
누가 그 사이에 공개본에 손댔으면 **non-fast-forward 로 실패**한다 (fail-closed).

내보낼 내용이 목적지와 같으면 빈 커밋을 만들지 않고 그냥 끝낸다 (멱등).

**⚠ 이사가 끝난 뒤에는 돌리지 마라.** 위 구현이 목적지 워킹트리를 개발 트리로 통째로
교체하므로, 공개 레포에 쌓인 커밋의 **내용이 덮인다** (커밋 자체는 조상으로 남는다 — 실측
확인). 이것은 트리를 옮기는 1회용 도구이지 동기화 도구가 아니다.

**어느 브랜치에 쌓는가는 목적지가 정한다 (#410).** 릴리스 브랜치를 `main` 으로 박아 두면,
공개 레포의 기본 브랜치가 다른 이름일 때 두 가지가 동시에 어긋난다 — 릴리스가 **아무도 안 보는
브랜치**에 쌓이고, 매니페스트의 「직전 릴리스 대비」가 **엉뚱한 브랜치와의 비교**가 된다
(로컬 `main` 을 원격 HEAD 위로 옮긴 뒤 그것과 대조했다). 그래서 목적지의 **실제 기본 브랜치**를
조회해 비교 기준과 push 대상 **양쪽에** 쓰고, 비교 기준은 항상 `origin/<브랜치>` 에서 다시
세운다. 판정이 불가능하면(원격 HEAD 없음) 추측하지 않고 멈춘다 — 그때는 `--branch` 로 사람이
명시한다. 매니페스트는 **어느 브랜치와 비교했는지를 숫자와 함께 적는다**: 「직전 릴리스 대비」가
무엇 대비인지 안 보이면 그 숫자는 읽는 사람을 오도한다.

**기여는 공개 레포에서 직접 받는다.** 개발 자리가 그쪽으로 옮겨가므로, 공개 레포에 온 이슈·PR 이
곧 이 프로젝트의 이슈·PR 이다 — 이관 뒤 그 내용을 지우는 후속 push 가 없기 때문이다(위 ⚠).
받는 자리·로컬 기동·라이선스·API 키 전제는 루트 `README.md` 의 「기여」 절이 안내한다.

──────────────────────────────────────────────────────────────────────────────
## ③ 무엇을 확인하고 미는가

  1. 워킹트리 청결 · 소스 커밋이 `origin/main` 에서 도달 가능
  2. **내용 게이트** — `scripts/verify_public_release_tree.py` 를 내보내기 트리에 돌린다.
     제거 대상 blob 재유입 · 자격증명 · 출처 미등록 자산 · 필수 파일. 실패하면 멈춘다.
     검사기를 못 찾으면 **준비를 시작하지 않는다** (fail-closed — 게이트 없이 밀지 않는다).
  3. **`LICENSE`·`THIRD-PARTY-NOTICES.md` 신선도** — 고지 문서가 `frontend/package-lock.json`
     보다 오래된 커밋이면 의존성이 바뀐 뒤 고지가 안 갱신된 것이므로 멈춘다.
  4. **CI 워크플로 보고** — 공개본에서 어떻게 도는지를 사람이 보고 판단하게 목록을 낸다
     (아래 「CI 판단」 참조).
  5. **릴리스 브랜치 판정** — 목적지의 기본 브랜치를 조회한다. 못 정하면 멈춘다 (#410).
  6. 매니페스트 — 최상위 디렉터리별 파일 수·크기, **어느 브랜치 대비** 추가/변경/삭제 몇 건인지.

## CI 판단 (리드 결정 「전부 넣는다」를 따르되, 판단은 적는다)

워크플로를 **제외하지 않는다** — 리드 결정이 「전부 넣는다」이고, 빌드·테스트 워크플로
(`ci.yml`·`frontend-ci.yml`·`repo-scans.yml`)는 공개본에서도 그대로 값이 있다. 다만 하네스
자동화 워크플로(`cross-review`·`plan`·`review-record`·`merge-delegate`·
`orphaned-branch-scan`)는 **시크릿·라벨·프로젝트 보드·self-hosted 러너를 새 레포에
다시 붙이기 전까지** 실패하거나 아무 일도 하지 않는다 (붙이는 절차는 이사 런북 §5).
그래서 스크립트가 워크플로별로 「시크릿 필요 / self-hosted 러너 / 쓰기 권한」을 표로 뽑아
보여주고, 공개 레포 설정에서 Actions 를 어떻게 둘지는 **사람이 정한다.**

보안 표면은 이관 시점 기준으로 확인해 뒀다: `pull_request_target` 사용 0건이고,
self-hosted 러너를 쓰는 유일한 잡(`cross-review.yml` 의 `review`)은
`head.repo.full_name == github.repository` 가드가 걸려 있어 **포크 PR 이 self-hosted 러너에
도달하지 못한다.** 공개 레포에서 포크 PR 이 자기 머신에서 임의 코드를 돌리는 전형적 사고
경로는 닫혀 있다. 이 사실이 바뀌면 아래 `audit_workflows()` 의 출력이 달라진다.

## 이 절차가 못 막는 것 (우회 경로를 스스로 적는다)

  · **사람이 이 스크립트를 안 쓰는 것.** `git push --mirror` 를 손으로 치면 막을 것이 없다.
    보호는 「정상 경로를 쉽게」와 문서뿐이다 (강도: 자동화 단, 하드 게이트 아님).
  · **공개 원격 주소를 잘못 주는 것.** `--remote` 는 필수이고 기본값이 없어 「실수로 어딘가에」
    가는 경로는 없지만, 틀린 주소를 명시적으로 주면 그대로 간다. **다만 「개발 레포 자신」
    이라는 가장 비싼 오타는 막는다** (#406 ② — 아래 「원격 자기 지정 가드」). 막지 못하는
    것은 **제3자의 엉뚱한 레포**다 — 우리가 아는 주소 목록 밖이라 대조할 것이 없다.
    (그쪽으로 밀려면 push 권한이 있어야 하므로 실현 조건이 훨씬 좁다.)
  · **가드 A 가 못 잡는 표기** (PR #409 리뷰 ③ + 그 전수 조사 — 실측 결과를 그대로 적는다).
    「정규화로 표기 차이를 다 잡는다」는 **사실이 아니고**, 아래는 가드 B(내용 대조)가 받는다:
      - **git 설정의 URL 재작성** — `url.<base>.insteadOf`·`.gitconfig` 의 별칭은 git 이
        클론 직전에 적용한다. 가드 A 는 사용자가 준 문자열만 보므로 재작성 결과를 모른다.
      - **IDNA 매핑으로 같은 호스트가 되는 표기** — `github．com`(U+FF0E)·`github。com`(U+3002)
        같은 유니코드 마침표. UTS46 매핑을 하는 클라이언트에서는 같은 곳이 된다.
        **다만 실측(읽기 전용 `ls-remote`)으로는 git 이 이 표기를 풀지 못해 도달 실패했다** —
        지금 뚫리는 경로가 아니라 「우리가 정규화하지 않는다」는 사실만 적는다.
      - **DNS·hosts·프록시로 같은 곳을 가리키게 만든 별개 호스트명** — 주소 문자열만으로는
        구분할 수 없다. 원리적으로 정규화의 사정거리 밖이다.
      - **ssh config 별칭**(`gh:owner/repo.git`) — 호스트에 `.` 도 `user@` 도 없어 원격이
        아니라 로컬 경로로 읽힌다. `~/.ssh/config` 를 읽어야 풀 수 있어 사정거리 밖이다.
    아래는 **읽기 전용 `ls-remote` 실측으로 뚫렸고 막았다** (전부 개발 레포와 같은 SHA
    `3a16553…` 를 돌려줬다): FQDN 후행 점(`github.com.`) · `.GIT` 대문자 접미 ·
    퍼센트 인코딩 **경로**(`fintech%2Dai%2Dplatform`) · 퍼센트 인코딩 **호스트**
    (`github%2Ecom` — 경로에만 넣었던 처방이 호스트에 빠져 있던 비대칭) ·
    **닷 세그먼트**(`/x/../Danwoo/…` — HTTP 클라이언트가 RFC 3986 §5.2.4 대로 지우고 보낸다)
    · **선두 닷 세그먼트**(`/../Danwoo/…`·`/%2e%2e/Danwoo/…` — 상대 경로로 해소하던 탓에
    선두 `..` 만 남아 있던 자리, PR #409 3라운드)
    · **`.git` 접미 뒤의 닷 세그먼트**(`…/repo.git/.`·`…/repo.git/x/..`·`…/repo.git/%2e` —
    접미 제거를 해소보다 먼저 해서 제거가 실패하던 자리, PR #409 4라운드).
    읽을 수 없는 표기(깨진 IPv6·전각 슬래시)는 **거부**로 끝난다 — 종전엔 traceback 이 샜다.
  · **개발 레포와 커밋을 공유하지 않는 미러**는 가드 B 가 못 잡는다 — 소스 커밋이 없는
    독립 레포는 「정상 공개 레포」와 구분되지 않는다. 가드 A(주소 대조)가 그 층을 맡는다.
  · **텍스트 안의 민감 정보** — 게이트의 한계는 `verify_public_release_tree.py` 독스트링 참조.
  · **이미 공개된 것의 회수.** 한 번 push 된 것은 되돌릴 수 없다. 그래서 기본이 드라이런이다.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = REPO_ROOT / "scripts" / "verify_public_release_tree.py"

DEFAULT_PUBLIC_NAME = "trading-lab"

# 고지 문서가 이보다 오래되면 멈춘다 — 의존성이 바뀌었는데 고지가 안 따라온 상태다.
NOTICE_FRESHNESS_PAIRS = [
    ("THIRD-PARTY-NOTICES.md", "frontend/package-lock.json"),
]


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def fail(message: str) -> int:
    print(f"\n중단: {message}")
    return 1


# ── 원격 자기 지정 가드 (#406 ②) ──────────────────────────────────────────────
# `--remote` 에 개발 레포 자신을 주면 릴리스 커밋이 **개발 레포 main 에 얹힌다.** 로컬
# non-bare 클론은 git 기본 `receive.denyCurrentBranch=refuse` 가 막아 주지만, **bare 레포는
# (= GitHub 가 동작하는 방식) 그 보호가 없어 fast-forward push 가 조용히 성공한다** (#406 재현).
# `--remote` 는 기본값도 환경변수 fallback 도 없어 「실수로 어딘가에」 새는 자동 경로는 없다 —
# 위험은 **명시적으로 잘못 주는 것**(클립보드 재사용·오타 한 글자)이라, 가드는 두 층으로 둔다.
#
#   가드 A (클론 전, 주소 동일성) — 정규화한 `--remote` 가 개발 레포의 remote URL 중 하나이거나
#     개발 레포 자신의 경로면 거부한다. 같은 곳을 가리키는 표기가 여럿이라 정규화가 필요하다:
#     `https://github.com/x/y.git` · `https://github.com/x/y` · `git@github.com:x/y` ·
#     `ssh://git@github.com/x/y.git` · `file:///path` · 상대 경로 · 심링크 · 후행 슬래시 ·
#     대소문자 · 기본 포트 명시 · 유저인포 · 이중 슬래시 · 쿼리/프래그먼트, 그리고
#     **FQDN 후행 점(`github.com.`) · `.GIT` 대문자 접미 · 퍼센트 인코딩 경로·호스트 ·
#     닷 세그먼트(`/x/../owner/repo` 와 선두 `/../owner/repo` 둘 다)**
#     (뒤 넷은 PR #409 리뷰와 그 전수 조사·3라운드가 뚫은 자리다).
#     **여기서 못 잡는 표기는 위 모듈 독스트링 「이 절차가 못 막는 것」에 적었다** —
#     가드 B 가 상쇄한다는 사실이 가드 A 의 서술을 참으로 만들지는 않는다.
#   가드 B (클론 후, 내용 동일성) — 목적지가 **소스 커밋을 이미 갖고 있으면** 거부한다.
#     주소만 대조하면 「개발 레포의 bare 미러를 다른 경로에 둔 것」을 못 잡는다(#406 재현이
#     정확히 그 모양이다). 이사 대상인 빈 공개 레포에는 개발 커밋이 한 개도 없다 — 이관 커밋은
#     `Source-Commit:` 트레일러만 남기고 개발 히스토리를 조상으로 갖지 않기 때문이다.
#     클론은 읽기 전용이라 이 검사는 **아무것도 쓰기 전에** 끝난다.

_SCP_LIKE = re.compile(r"^(?P<user>[^/@]+@)?(?P<host>[^/:]+):(?P<path>.+)$")


class RemoteParseError(ValueError):
    """`--remote` 표기를 정규화할 수 없다 — 대조가 불가능하므로 거부한다.

    깨진 IPv6(`https://[::1`)·전각 슬래시(`／`)처럼 `urlsplit` 이 거절하는 표기가 종전에는
    **traceback 으로 새 나갔다.** 프로세스가 죽으니 fail-closed 방향이긴 했지만, 가드
    함수라면 「무엇을 왜 거부했는지」가 읽히는 메시지로 끝나는 것이 맞다 (PR #409 리뷰 다듬기).
    """


def _split_url(text: str) -> urllib.parse.SplitResult:
    try:
        return urllib.parse.urlsplit(text)
    except ValueError as error:  # 깨진 IPv6 괄호·NFKC 검사 위반 등
        raise RemoteParseError(f"URL 로 읽을 수 없다 ({error})") from error


def _normalize_host(host: str) -> str:
    """호스트 표기를 한 형태로 — **퍼센트 디코딩** → 소문자 → **FQDN 후행 루트 라벨 점 제거**.

    · **퍼센트 디코딩** (PR #409 리뷰 뒤 지휘자 실측). 종전 라운드가 **경로**에는 퍼센트
      디코딩을 넣고 호스트에는 안 넣은 비대칭이 남아 있었다. git 은 호스트의 `%XX` 도 풀고
      접속한다 — 실측(읽기 전용):
      `git ls-remote https://github%2Ecom/Danwoo/fintech-ai-platform.git HEAD` 가
      점 표기와 **같은 SHA(`3a16553…`)** 를 돌려준다.
    · **후행 루트 라벨 점** (PR #409 리뷰 ③). `github.com.` 의 끝점은 DNS 루트 라벨 표기라
      `github.com` 과 같은 곳으로 풀린다 — 실측으로 같은 SHA 를 확인했다.

    두 층 다 「거부」 판정에만 쓰이므로 넓게 모으는 쪽이 안전하다. 여기서도 **못 잡는 표기**는
    모듈 독스트링 「이 절차가 못 막는 것」에 적었다 (IDNA 매핑·DNS 별칭 등).

    포트는 여기 안 들어온다 — `urlsplit().hostname` 이 이미 떼고, scp 형식엔 포트가 없다.
    """
    return urllib.parse.unquote(host).lower().rstrip(".")


def _normalize_url_path(path: str) -> str:
    """URL 경로를 한 형태로 — 퍼센트 디코딩 → 소문자 → 후행 슬래시·`.git` 제거 → 닷 세그먼트 해소.

    **순서가 load-bearing 이다** (PR #409 리뷰 ③ 전수 조사에서 나온 구멍들):

      · 소문자화를 `.git` 제거보다 **뒤에** 하면 `…/repo.GIT` 이 접미로 안 읽혀 다른 값으로
        정규화된다. (GitHub 은 이 표기를 404 로 돌려주지만, 대소문자를 덜 가리는 호스트에서
        같은 구멍이 열린다 — 거부 판정이라 넓게 잡는 쪽이 안전하다.)
      · 퍼센트 디코딩을 안 하면 `fintech%2Dai%2Dplatform` 이 빠져나간다. **실측(읽기 전용):
        `git ls-remote https://github.com/Danwoo/fintech%2Dai%2Dplatform.git HEAD` 가 개발
        레포와 같은 SHA 를 돌려준다.**
      · **닷 세그먼트(`/x/../owner/repo`)를 안 풀면 빠져나간다.** HTTP 클라이언트는 RFC 3986
        §5.2.4 대로 `..` 를 지우고 보내므로 실제로 개발 레포에 도달한다 — 실측(읽기 전용):
        `git ls-remote https://github.com/x/../Danwoo/fintech-ai-platform.git HEAD` 가
        **같은 SHA(`3a16553…`)** 를 돌려준다. 해소는 `posixpath.normpath` 로 하되 이건
        **순수 문자열 연산**이라 파일시스템·심링크와 무관하다 (URL 에 맞는 성질이다).
      · **해소는 절대 경로로 한다** (PR #409 3라운드). 종전에는 앞 슬래시를 떼고 **상대**
        경로로 normpath 를 돌려서, `posixpath` 의 상대 경로 규칙대로 **선두 `..` 가 그대로
        남았다** — `/../Danwoo/…`·`/%2e%2e/Danwoo/…` 가 다른 값으로 정규화돼 가드 A 를
        통과했다(가드 B 가 상쇄하지만 가드 A 의 서술이 거짓이 되는 자리다). URL 경로는
        절대 경로이고 RFC 3986 §5.2.4 는 **버퍼가 빈 상태의 `..` 를 버리므로**, `/` 를
        붙여 해소하면 클라이언트가 실제로 보내는 것과 같아진다.
    """
    decoded = urllib.parse.unquote(path).lower()
    # **해소를 `.git` 제거보다 먼저** 한다 (PR #409 4라운드 리뷰 비차단 1). 접미를 먼저 떼면
    # 접미 **뒤에** 닷 세그먼트가 붙은 표기(`…/repo.git/.` · `…/repo.git/x/..` · `…/repo.git/%2e`)
    # 에서 제거가 실패하고, 뒤이은 해소가 닷 세그먼트만 지워 **`.git` 이 남은 다른 값**이 됐다.
    # 그 표기는 실제로 개발 레포에 도달한다 (읽기 전용 실측:
    # `git ls-remote "https://github.com/Danwoo/fintech-ai-platform.git/." HEAD` 가 같은 SHA).
    resolved = posixpath.normpath("/" + decoded.strip("/"))
    return resolved.rstrip("/").removesuffix(".git").strip("/")


def normalize_remote(raw: str, base: Path) -> str:
    """원격 표기를 대조 가능한 한 형태로 만든다.

    URL 이면 `호스트/소유자/레포` (스킴·사용자·포트·퍼센트 인코딩·`.git`·후행 슬래시·
    호스트 후행 점 제거, 소문자), 로컬 경로면 심링크까지 푼 절대 경로 문자열.

    **소문자화·후행 점 제거는 의도적으로 과하게 잡는 쪽이다.** 이 값은 「거부」 판정에만
    쓰이므로 같은 곳을 가리킬 수 있는 표기를 한데 모으는 편이 안전하다 (fail-closed 방향).
    여기서 **못 잡는 표기**는 release_public 모듈 독스트링 「이 절차가 못 막는 것」에 적었다.

    읽을 수 없는 표기에는 `RemoteParseError` 를 던진다 — 호출자가 「대조 불가 = 거부」로
    바꾼다 (traceback 을 흘리지 않는다).
    """
    text = raw.strip()
    if text.startswith("file://"):
        text = urllib.parse.unquote(_split_url(text).path)
    else:
        parsed = _split_url(text)
        if parsed.scheme in ("http", "https", "ssh", "git", "ftp", "ftps"):
            return f"{_normalize_host(parsed.hostname or '')}/{_normalize_url_path(parsed.path)}"
        if parsed.scheme == "" and "://" not in text:
            scp = _SCP_LIKE.match(text)
            # `C:\repo` 같은 윈도 경로·`./a:b` 는 scp 형식이 아니다 — 호스트에 `.` 나
            # 사용자 표기가 있을 때만 원격으로 읽는다.
            if scp and (scp.group("user") or "." in scp.group("host")):
                return f"{_normalize_host(scp.group('host'))}/{_normalize_url_path(scp.group('path'))}"
    # 로컬 경로 — 심링크·상대경로·`..` 를 풀어 실제 위치로 맞춘다 (없는 경로도 정규화된다).
    try:
        path_obj = Path(text)
        if not path_obj.is_absolute():
            path_obj = base / path_obj
        return str(path_obj.resolve())
    except (OSError, ValueError) as error:  # NUL 바이트·너무 긴 경로 등
        raise RemoteParseError(f"경로로도 읽을 수 없다 ({error})") from error


def self_targets(repo: Path) -> list[tuple[str, str]]:
    """거부해야 할 대상 (정규화 값, 사람이 읽을 설명) 목록.

    개발 레포의 **모든** remote 를 넣는다 (origin 만이 아니라) — 설정된 remote 는 이미
    「우리가 미는 곳」이고, 공개 배포 목적지가 그중 하나일 이유가 없다.
    """
    targets: list[tuple[str, str]] = []
    resolved = repo.resolve()
    targets.append((str(resolved), f"개발 레포 자신 ({resolved})"))
    git_dir = resolved / ".git"
    if git_dir.exists():
        targets.append((str(git_dir.resolve()), f"개발 레포의 .git ({git_dir})"))
    listing = git("remote", "-v", cwd=repo, check=False)
    for line in listing.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        try:
            normalized = normalize_remote(url, resolved)
        except RemoteParseError:
            # 저장된 remote 를 못 읽는 것은 설정 이상이다. 대조에서 빼지 않고 **원문 그대로**
            # 넣는다 — 같은 문자열을 `--remote` 로 주면 여전히 잡힌다 (조용히 줄지 않게).
            normalized = url.strip()
        targets.append((normalized, f"개발 레포의 remote `{name}` ({url})"))
    return targets


def check_remote_not_self(remote: str, repo: Path) -> tuple[int, str | None]:
    """(대조한 대상 수, 거부 사유 또는 None). 출력은 호출자가 한다."""
    targets = self_targets(repo)
    # fail-closed — 대조 대상이 0건이면 검사가 없는 것과 같다. **지금은 도달하지 않는다**:
    # `self_targets` 가 개발 레포 경로를 무조건 먼저 넣기 때문이다 (PR #409 리뷰가 두 번 지적).
    # 그럼에도 남기는 이유는 이 가드가 막는 것이 「현재 구현」이 아니라 「목록을 만드는 방식이
    # 바뀌었을 때」이기 때문이다 — 도달 가능해지는 순간이 곧 이 가드가 필요한 순간이다.
    # (뮤테이션으로 이 분기를 확인하려면 `self_targets` 자체를 갈아야 한다. 회귀 그물의
    #  뮤테이션 표는 그래서 이 분기를 주장하지 않는다.)
    if not targets:
        return 0, "원격 자기 지정 대조 대상 0건 — 검사가 존재하지 않는 상태다"
    try:
        normalized = normalize_remote(remote, Path.cwd())
    except RemoteParseError as error:
        return len(targets), (
            f"`--remote` 표기를 정규화할 수 없다 — {error}. 대조할 수 없는 주소는 "
            "개발 레포가 아니라고 말할 근거가 없으므로 받지 않는다"
        )
    for target, why in targets:
        if normalized == target:
            return len(targets), (
                f"`--remote` 가 개발 레포를 가리킨다 — {why}. "
                f"정규화 결과가 일치한다 ({normalized}). "
                "릴리스 커밋이 개발 레포 main 에 얹힌다 (#406 ②)"
            )
    return len(targets), None


def check_destination_not_dev_repo(clone: Path, source_sha: str) -> str | None:
    """목적지가 소스 커밋을 이미 갖고 있으면 개발 레포(또는 그 미러)다."""
    found = git("cat-file", "-e", f"{source_sha}^{{commit}}", cwd=clone, check=False)
    if found.returncode == 0:
        return (
            f"목적지가 개발 소스 커밋 {source_sha[:8]} 을 이미 갖고 있다 — 공개 레포가 아니라 "
            "개발 레포이거나 그 미러다. 정상적인 공개 레포에는 개발 커밋이 한 개도 없다 (#406 ②)"
        )
    return None


# ── 사전 점검 ──────────────────────────────────────────────────────────────────
def preflight(repo: Path, source_ref: str) -> tuple[str, str] | None:
    if not (repo / ".git").exists():
        print(f"  ✗ {repo} 가 git 레포가 아니다")
        return None

    dirty = git("status", "--porcelain", cwd=repo).stdout.strip()
    if dirty:
        print(f"  ✗ 워킹트리가 더럽다 ({len(dirty.splitlines())}건) — 커밋하거나 정리하고 다시 실행하라")
        return None

    resolved = git("rev-parse", "--verify", f"{source_ref}^{{commit}}", cwd=repo, check=False)
    if resolved.returncode != 0:
        print(f"  ✗ 소스 ref 를 못 찾는다: {source_ref}")
        return None
    sha = resolved.stdout.strip()

    main_ref = git("rev-parse", "--verify", "origin/main^{commit}", cwd=repo, check=False)
    if main_ref.returncode != 0:
        print("  ✗ origin/main 을 못 찾는다 — fetch 후 다시 실행하라")
        return None
    reachable = git(
        "merge-base",
        "--is-ancestor",
        sha,
        main_ref.stdout.strip(),
        cwd=repo,
        check=False,
    )
    if reachable.returncode != 0:
        print(f"  ✗ 소스 커밋 {sha[:8]} 이 origin/main 에서 도달 불가 — 미머지 코드는 공개본에 내보내지 않는다")
        return None

    subject = git("log", "-1", "--format=%s", sha, cwd=repo).stdout.strip()
    print(f"  · 소스 커밋: {sha[:8]} ({source_ref}) — {subject}")
    print("  · 워킹트리 청결 · origin/main 에서 도달 가능")
    return sha, subject


def check_notice_freshness(repo: Path, sha: str) -> list[str]:
    """고지 문서가 그것이 서술하는 파일보다 오래됐으면 위반."""
    problems: list[str] = []
    checked = 0
    for notice, watched in NOTICE_FRESHNESS_PAIRS:
        notice_time = git("log", "-1", "--format=%ct", sha, "--", notice, cwd=repo).stdout.strip()
        watched_time = git("log", "-1", "--format=%ct", sha, "--", watched, cwd=repo).stdout.strip()
        if not notice_time:
            problems.append(f"{notice}: 이 커밋의 히스토리에 없다")
            continue
        if not watched_time:
            problems.append(f"{watched}: 이 커밋의 히스토리에 없다 — 신선도 대조 대상이 사라졌다")
            continue
        checked += 1
        if int(notice_time) < int(watched_time):
            problems.append(f"{notice} 가 {watched} 보다 오래됐다 — 의존성이 바뀐 뒤 고지가 갱신되지 않았다")
    if checked == 0:
        problems.append("신선도 대조 0건 — 대조 쌍 지정이 현실과 어긋났다 (fail-closed)")
    print(f"  · 고지 신선도 대조 {checked}쌍")
    return problems


# ── 내보내기 ──────────────────────────────────────────────────────────────────
def export_tree(repo: Path, sha: str, destination: Path) -> tuple[int, int]:
    """`git archive` — 트리만. 히스토리·.git·gitignore 대상은 구조적으로 담기지 않는다.

    (일반 파일 수, 심링크 수)를 돌려준다. 둘을 나눠 세는 이유: 내용 게이트는 심링크를
    검사하지 않으므로(내용이 없다) 게이트가 출력하는 파일 수와 여기 수가 어긋난다.
    그 차이가 설명 없이 보이면 읽는 사람이 「누락」으로 오해한다.
    """
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / "export.tar"
    with archive.open("wb") as handle:
        subprocess.run(["git", "archive", "--format=tar", sha], cwd=repo, stdout=handle, check=True)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        tar.extractall(destination, filter="data")
    archive.unlink()
    return (
        sum(1 for member in members if member.isfile()),
        sum(1 for member in members if member.issym()),
    )


# ── 워크플로 감사 ─────────────────────────────────────────────────────────────
def audit_workflows(tree: Path) -> list[tuple[str, str]]:
    workflow_dir = tree / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return []
    rows: list[tuple[str, str]] = []
    for path in sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        flags = []
        if re.search(r"^\s*runs-on:.*self-hosted", text, re.MULTILINE):
            flags.append("self-hosted 러너")
        secrets = sorted(set(re.findall(r"secrets\.([A-Z_][A-Z0-9_]*)", text)))
        if secrets:
            flags.append("시크릿 " + "·".join(secrets))
        if re.search(r"^\s*(contents|issues|pull-requests|statuses):\s*write", text, re.MULTILINE):
            flags.append("쓰기 권한")
        if "pull_request_target" in text:
            flags.append("⚠ pull_request_target")
        rows.append((path.name, ", ".join(flags) if flags else "빌드·테스트 전용"))
    return rows


# ── 목적지 준비 ───────────────────────────────────────────────────────────────
# 릴리스 브랜치를 상수로 박지 않는다 (#410). 아래 값은 **빈 레포에서 원격이 기본 브랜치 이름을
# 알려주지 않을 때만** 쓰는 최후 fallback 이다 — 커밋이 있는 레포에서는 절대 쓰이지 않는다.
FALLBACK_PUBLIC_BRANCH = "main"


def remote_branches(clone: Path) -> list[str]:
    """목적지에 실재하는 브랜치 이름 (origin/ 접두 제거, origin/HEAD 심볼릭 제외)."""
    listing = git("for-each-ref", "--format=%(refname:strip=3)", "refs/remotes/origin", cwd=clone)
    return sorted({name for name in listing.stdout.split() if name != "HEAD"})


def resolve_release_branch(clone: Path, override: str | None) -> tuple[str, bool, str]:
    """(릴리스 브랜치, 기존 릴리스 있음, 판정 근거). 못 정하면 RuntimeError (#410).

    「main 이겠지」로 추측하지 않는다. 추측이 틀리면 **조용히** 두 가지가 어긋난다 —
    릴리스가 아무도 안 보는 브랜치에 쌓이고, 매니페스트가 엉뚱한 브랜치와의 비교가 된다.
    둘 다 사람이 숫자를 보고 판단하는 것을 무의미하게 만들므로 fail-closed 로 멈춘다.

    판정 순서:
      ① `--branch` 가 있으면 그것 (사람이 명시한 것이 가장 세다)
      ② 커밋이 하나도 없으면 첫 릴리스 — 클론의 unborn HEAD 이름을 쓴다. `git clone` 이
         원격의 unborn HEAD 를 그대로 받아 오므로(실측: `git init --bare -b trunk` 를 클론하면
         `symbolic-ref HEAD` 가 `refs/heads/trunk`) 이것이 목적지가 기대하는 이름이다.
         원격이 안 알려주면 클론이 로컬 `init.defaultBranch` 로 떨어지므로 그때만 fallback 이 된다.
      ③ 커밋이 있으면 `refs/remotes/origin/HEAD` — 클론이 원격 HEAD 에서 채운 값이다.
      ④ 원격 HEAD 가 없거나 실재하지 않는 브랜치를 가리키면 **멈춘다.**
    """
    branches = remote_branches(clone)

    if override:
        if branches and override not in branches:
            raise RuntimeError(
                f"`--branch {override}` 가 목적지에 없다. 목적지의 브랜치 {len(branches)}개: "
                f"{'·'.join(branches)}. 없는 브랜치를 첫 릴리스로 취급하면 매니페스트가 "
                "「직전 릴리스 대비」가 아니라 「전부 새로 추가」로 나온다 (#410)"
            )
        return override, bool(branches), "--branch 로 명시"

    if not branches:
        unborn = git("symbolic-ref", "--short", "HEAD", cwd=clone, check=False).stdout.strip()
        branch = unborn or FALLBACK_PUBLIC_BRANCH
        why = "빈 레포의 unborn HEAD" if unborn else f"fallback 기본값 {FALLBACK_PUBLIC_BRANCH}"
        return branch, False, why

    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=clone, check=False)
    default = head.stdout.strip().removeprefix("origin/") if head.returncode == 0 else ""
    if not default or default not in branches:
        raise RuntimeError(
            "목적지의 기본 브랜치를 판정할 수 없다 — 원격 HEAD 가 없거나 실재하지 않는 브랜치를 "
            f"가리킨다{f' ({default})' if default else ''}. 목적지의 브랜치 {len(branches)}개: "
            f"{'·'.join(branches)}. 어디에 쌓을지 추측하지 않는다 — `--branch <이름>` 으로 "
            "명시하라 (#410)"
        )
    return default, True, "원격 기본 브랜치(origin/HEAD)"


def prepare_destination(remote: str, workdir: Path, override: str | None = None) -> tuple[Path, str, bool, str]:
    """공개 원격을 클론하고 릴리스 브랜치를 세운다.

    커밋이 있으면 로컬 브랜치를 **`origin/<브랜치>` 에서 다시 세운다** — 클론이 체크아웃해 둔
    것을 그대로 믿지 않는다. 종전 코드는 `checkout -B main` 을 시작점 없이 불러 로컬 `main` 을
    **현재 HEAD(= 원격 기본 브랜치) 위로 옮겼고**, 그래서 이후의 `diff --cached` 가 직전
    릴리스가 아니라 그 브랜치와의 비교가 됐다 (#410 재현).
    """
    clone = workdir / "public"
    result = subprocess.run(
        ["git", "clone", "--quiet", remote, str(clone)],
        capture_output=True,
        text=True,
        check=False,  # 실패는 아래에서 메시지로 바꿔 던진다
    )
    if result.returncode != 0:
        raise RuntimeError(f"공개 원격 클론 실패: {result.stderr.strip()}")

    branch, has_commits, why = resolve_release_branch(clone, override)
    if has_commits:
        git("checkout", "-q", "-B", branch, f"refs/remotes/origin/{branch}", cwd=clone)
    else:
        git("checkout", "-q", "-B", branch, cwd=clone, check=False)
    return clone, branch, has_commits, why


def stage_tree(export: Path, clone: Path) -> None:
    """공개 클론의 워킹트리를 내보내기 트리로 **완전히 교체**한다 (삭제도 반영)."""
    for entry in clone.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for entry in export.iterdir():
        target = clone / entry.name
        if entry.is_dir() and not entry.is_symlink():
            shutil.copytree(entry, target, symlinks=True)
        else:
            shutil.copy2(entry, target, follow_symlinks=False)
    git("add", "-A", cwd=clone)


def summarize_diff(clone: Path, first_release: bool, branch: str) -> str:
    """매니페스트 한 줄. **무엇과 비교했는지를 숫자와 같은 줄에 적는다** (#410).

    「직전 릴리스 대비 추가 1016」은 그 자체로는 참·거짓을 가릴 수 없는 문장이다 — 비교 기준이
    안 보이면 사람이 「초기 릴리스인가」로 읽고 넘어간다. 기준을 적으면 기준이 틀렸을 때
    숫자가 아니라 **문장이** 이상해 보인다.
    """
    if first_release:
        staged = git("diff", "--cached", "--name-only", cwd=clone).stdout.split()
        return f"첫 릴리스 ({branch} 신규) — 초기 커밋에 파일 {len(staged)}개"
    stat = git("diff", "--cached", "--name-status", cwd=clone).stdout.splitlines()
    added = sum(1 for line in stat if line.startswith("A"))
    modified = sum(1 for line in stat if line.startswith("M"))
    deleted = sum(1 for line in stat if line.startswith("D"))
    if not stat:
        return f"직전 릴리스(origin/{branch})와 내용이 같다 — 변경 0건"
    return f"직전 릴리스(origin/{branch}) 대비 추가 {added} · 변경 {modified} · 삭제 {deleted}"


def tree_report(export: Path) -> list[tuple[str, int, int]]:
    """최상위 항목별 파일 수·크기. 심링크는 lstat 로 세어 끊긴 링크에도 죽지 않는다."""
    rows: list[tuple[str, int, int]] = []
    for entry in sorted(export.iterdir()):
        if entry.is_dir() and not entry.is_symlink():
            members = [p for p in entry.rglob("*") if p.is_symlink() or p.is_file()]
            rows.append(
                (
                    entry.name + "/",
                    len(members),
                    sum(p.lstat().st_size for p in members),
                )
            )
        else:
            rows.append((entry.name, 1, entry.lstat().st_size))
    return rows


# ── 본체 ─────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="공개 배포 레포로 현재 트리를 내보낸다")
    parser.add_argument(
        "--remote",
        required=True,
        help="공개 레포 URL 또는 로컬 경로 (기본값 없음 — 명시 필수)",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_PUBLIC_NAME,
        help=f"공개 레포 이름 (기본 {DEFAULT_PUBLIC_NAME})",
    )
    parser.add_argument("--source-ref", default="origin/main", help="내보낼 ref (기본 origin/main)")
    parser.add_argument(
        "--branch",
        default=None,
        help="공개 레포의 릴리스 브랜치 (기본: 목적지의 기본 브랜치를 조회. 판정 불가면 멈춘다)",
    )
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="개발 레포 경로")
    parser.add_argument("--execute", action="store_true", help="실제로 push 한다 (기본은 드라이런)")
    args = parser.parse_args(argv)

    mode = "실행 (push 한다)" if args.execute else "드라이런 (아무것도 쓰지 않는다)"
    print(f"== 공개 배포: {args.name} ← {args.repo.name} ==")
    print(f"  · 모드: {mode}")
    print(f"  · 원격: {args.remote}")

    if not GATE_SCRIPT.is_file():
        return fail(f"내용 게이트를 못 찾는다 ({GATE_SCRIPT}) — 게이트 없는 릴리스는 하지 않는다")

    print("\n-- 1. 사전 점검 --")
    # 가드 A — 아무것도 만들기 전에 원격 자기 지정부터 본다 (#406 ②)
    compared, self_target = check_remote_not_self(args.remote, args.repo)
    print(f"  · 원격 자기 지정 대조 {compared}건 (개발 레포 경로·.git·remote 전부)")
    if self_target:
        return fail(self_target)

    checked = preflight(args.repo, args.source_ref)
    if checked is None:
        return fail("사전 점검 실패")
    sha, _subject = checked

    problems = check_notice_freshness(args.repo, sha)
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}")
        return fail("고지 문서 신선도 실패")

    with tempfile.TemporaryDirectory(prefix="public-release-") as tmp:
        workdir = Path(tmp)
        export = workdir / "export"

        print("\n-- 2. 내보내기 (git archive — 트리만) --")
        files, symlinks = export_tree(args.repo, sha, export)
        print(
            f"  · 일반 파일 {files}개 + 심링크 {symlinks}개 = {files + symlinks}개 전개 "
            "(히스토리·.git·gitignore 대상 없음)"
        )
        print(f"  · 내용 게이트가 검사하는 것은 일반 파일 {files}개 — 심링크는 내용이 없다")

        print("\n-- 3. 내용 게이트 --")
        gate = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--tree", str(export)],
            capture_output=True,
            text=True,
            check=False,  # 위반은 returncode 로 읽고 멈춘다
        )
        for line in gate.stdout.rstrip().splitlines():
            print(f"  {line}")
        if gate.returncode != 0:
            if gate.stderr.strip():
                print(gate.stderr.rstrip())
            return fail("내용 게이트 실패 — 공개본에 들어가면 안 되는 것이 있다 (#360)")

        print("\n-- 4. 내보내는 것 --")
        for name, files, size in tree_report(export):
            print(f"  {name:<28} {files:>5}개  {size / 1024:>10.1f} KiB")

        print("\n-- 5. CI 워크플로 (공개본에서도 Actions 가 돈다 — 설정은 사람이 정한다) --")
        rows = audit_workflows(export)
        if not rows:
            print("  · 워크플로 없음")
        for name, flags in rows:
            print(f"  {name:<28} {flags}")

        print("\n-- 6. 목적지 --")
        try:
            clone, branch, has_commits, why = prepare_destination(args.remote, workdir, args.branch)
        except RuntimeError as error:
            return fail(str(error))
        print(f"  · 릴리스 브랜치: {branch} ({why})")
        print(f"  · 기존 릴리스 커밋: {'있음' if has_commits else '없음 (첫 릴리스)'}")

        # 가드 B — 주소가 달라도 내용이 개발 레포면 거부한다 (#406 ②).
        # 클론은 읽기 전용이라 여기까지 아무것도 쓰지 않았다.
        mirror = check_destination_not_dev_repo(clone, sha)
        if mirror:
            return fail(mirror)
        print("  · 목적지에 개발 소스 커밋 없음 — 개발 레포·그 미러가 아니다")

        stage_tree(export, clone)
        print(f"  · {summarize_diff(clone, not has_commits, branch)}")

        if not git("diff", "--cached", "--name-only", cwd=clone).stdout.strip():
            print("\n== 변경 없음 — 릴리스를 만들지 않는다 ==")
            return 0

        message = (
            f"release: {args.name} {date.today().isoformat()}\n\n"
            f"개발 레포의 현재 트리 스냅샷. 개발 히스토리는 포함되지 않는다 (#360 리드 결정 ㉡).\n\n"
            f"Source-Commit: {sha}\n"
        )
        print("\n-- 7. 릴리스 커밋 --")
        print("  " + message.splitlines()[0])
        print(f"  Source-Commit: {sha}")

        if not args.execute:
            print(
                "\n== 드라이런 종료 — 아무것도 쓰지 않았다 ==\n"
                "  개발 레포·공개 원격 모두 그대로다 (작업은 임시 디렉터리에서만 일어났고 지워졌다).\n"
                "  실제로 밀려면: --execute 를 붙여 다시 실행하라."
            )
            return 0

        git("commit", "--quiet", "-m", message, cwd=clone)
        new_sha = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
        print(f"  · 커밋 {new_sha[:8]}")

        print(f"\n-- 8. push → {branch} (force 없음 — non-fast-forward 면 실패한다) --")
        pushed = git("push", "origin", f"HEAD:refs/heads/{branch}", cwd=clone, check=False)
        if pushed.returncode != 0:
            print(pushed.stderr.rstrip())
            return fail("push 실패 — 그 사이 공개본이 앞서 나갔을 수 있다. force 로 덮지 말고 원인을 확인하라")
        print(f"  · {branch} ← {new_sha[:8]} 완료")
        print(f"\n== 릴리스 완료: {args.name} {branch} {new_sha[:8]} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
