"""토큰 밖의 색을 쓰는 `.tsx` 를 검출한다 — fail-closed (stdlib 전용).

## 왜 있나

디자인 시스템(`.docs/4-아키텍처/디자인-시스템.md` §8)이 못박은 그물이다. 화면이 쓰는 색은
`globals.css` 의 토큰뿐이어야 하는데, Tailwind 기본 팔레트(`bg-gray-500`)와 hex 리터럴
(`#2C64F8`)은 **아무 설정 없이 그냥 써진다** — 타입체커도 린터도 조용하다. 그래서 규율은
문서에만 남고 화면은 화면마다 즉흥적으로 색을 고른다.

실측(이 스크립트 최초 실행): `frontend/components`·`frontend/app` 의 `.tsx` 158개 중
**64개**가 토큰 밖 색을 쓴다. 이 그물이 없으면 그 수는 줄지 않고 는다.

## 무엇을 위반으로 보나

1. **Tailwind 기본 팔레트 유틸리티** — `bg-gray-500` · `text-blue-600` 류. 색 이름 + **숫자
   음영**의 조합이라, 이 레포의 커스텀 토큰(`bg-bg-panel` · `text-ink-muted` — 음영이
   숫자가 아니다)과 구조적으로 갈린다.
2. **`black` · `white` 유틸리티** — `text-white` · `bg-black`. 기본 팔레트의 일부이고,
   디자인 시스템은 순백·순흑을 쓰지 않는다(`--ink-strong` 은 `#F5F3EF` 로 일부러 살짝 눅였다).
3. **hex 리터럴** — 문자열 안의 `#RRGGBB` · `#RGB` 류.

## 오탐을 막는 두 가지

- **주석을 걷어내고 본다.** 안 그러면 이 레포가 주석에 흔히 적는 이슈 번호(`#242` · `#341`)가
  3자리 hex 로 읽힌다(숫자는 전부 유효한 hex 문자다). 실측으로 오탐 파일이 65 → 23 으로 줄었다.
- **hex 는 문자열 리터럴 안에서만 센다.** 색은 `className` · `style` · JSX 속성 어디에 있든
  문자열 안에 있다. 문자열 밖의 `#숫자` 는 색이 아니다.

주석을 걷을 때 문자열을 먼저 보호한다 — 안 그러면 `"https://..."` 의 `//` 가 주석 시작으로
읽혀 그 줄의 뒷부분이 통째로 사라진다(그러면 그 줄의 위반을 놓친다).

## allowlist — 등록은 하되 늘지는 못한다

기존 위반 64건을 여기서 다 고칠 수는 없다(화면을 바꾸는 것은 `#73` S2~S5 의 일이다). 그렇다고
그물을 안 걸면 그 사이 새 위반이 계속 들어온다. 그래서 **현재 위반을 상한과 함께 등록**한다:

- **낡은 항목은 실패한다** — allowlist 에 적힌 파일이 더는 위반이 아니거나 아예 없으면 실패한다.
  낡은 예외가 남아 새 위반을 덮는 것이 이 그물의 유일한 우회로이므로 막는다
  (`run_verify_scripts.py` 의 `--skip` 규칙과 같은 이유).
- **늘어나면 실패한다** — `ALLOWLIST_CAP` 이 상한이다. 새 위반을 등록하려면 상한도 같이 올려야
  하고, 그 한 줄이 리뷰에 보인다. 조용히 느슨해지지 않는다.
- **상한은 내려가기만 한다** — S2~S5 가 화면을 토큰으로 옮길 때마다 등록분을 지우고 상한을 내린다.

실행: `python3 scripts/verify_color_token_usage.py` (cwd 무관).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
# `lib` 이 늦게 들어온 이유: 색이 화면 파일에만 산다고 봤는데, **차트 색은 여기 산다**
# (`lib/terminal/*.ts` 가 캔들·프리셋 색을 정한다). `.tsx` 만 훑으면 그 자리는 스캔 밖이라
# 조용히 샌다 — 지금은 위반이 0이지만 「안 보는 자리」로 남겨 두는 것이 결함이다.
SCAN_ROOTS = ("components", "app", "lib")
# 확장자도 함께 넓힌다 — `lib` 은 `.ts` 다.
SCAN_SUFFIXES = ("*.tsx", "*.ts")

# 스캔 대상이 통째로 사라지면(경로 변경·리네임) 조용히 초록이 되지 않게 하는 하한.
# 정당하게 줄였다면 하한도 함께 내린다.
MIN_SCANNED_FILES = 100

# allowlist 상한. **내려가기만 한다** — 머리 주석 「allowlist」 참조.
# `lib` 스캔 확장(#166)이 56 으로 올렸고, 이 PR 이 Dashboard 4건을 지워 다시 내린다.
# 실측으로 정한다 — 손으로 고르면 어긋난다.
ALLOWLIST_CAP = 49

# 위반 사유별 문구. 지금 등록분은 전부 「디자인 시스템 적용 전」이라 사유가 갈리지 않는다 —
# 자리마다 다른 이유를 지어내기보다 무엇을 기다리는 등록인지 한 줄로 밝힌다.
TEMPLATE_SCREEN = "디자인 시스템 이전의 템플릿 화면(회원가입·인증·약관·마이페이지) — #73 S2~S5 가 토큰으로 옮긴다."
SYSTEM_SCREEN = "시스템관리 화면 — #73 S2~S5 가 토큰으로 옮긴다."
FEATURE_SCREEN = "업무 화면 — #73 S2~S5 가 토큰으로 옮긴다."
SHARED_COMPONENT = "공용 컴포넌트 — 토큰 전환이 이 컴포넌트를 쓰는 화면 전부에 걸리므로 #73 S2~S5 에서 한꺼번에 옮긴다."
# `lib` 을 스캔에 넣자 드러난 것들. **스캔 밖이라 안 보였던 것이지 새로 생긴 위반이 아니다.**
NON_DOM_COLOR = (
    "DOM 밖에서 색을 정하는 자리(캔버스 차트·메일 템플릿) — Tailwind 클래스가 안 닿아 "
    "토큰을 CSS 변수로 읽어 넘겨야 한다. #73 S2~S5 가 그 통로와 함께 옮긴다."
)

# 알고 남겨 둔 위반. 키는 `frontend/` 기준 상대 경로.
ALLOWLIST: dict[str, str] = {
    "components/features/Common/Auth/Agreettac.tsx": TEMPLATE_SCREEN,
    "components/features/Common/Auth/Signup.tsx": TEMPLATE_SCREEN,
    "components/features/Common/Auth/Signupcmpl.tsx": TEMPLATE_SCREEN,
    "components/features/Common/Auth/Signupinfo.tsx": TEMPLATE_SCREEN,
    "components/features/Common/Mypage/Mypage.tsx": TEMPLATE_SCREEN,
    "components/features/Common/System/Author/AuthorDetailForm.tsx": SYSTEM_SCREEN,
    "components/features/Common/System/Author/AuthorMenuGrid.tsx": SYSTEM_SCREEN,
    "components/features/Common/System/Menu/MenuDetailForm.tsx": SYSTEM_SCREEN,
    "components/features/ResearchChat/ConversationPanel.tsx": FEATURE_SCREEN,
    "components/features/ResearchChat/MessageBubble.tsx": FEATURE_SCREEN,
    "components/features/ResearchChat/SessionListPanel.tsx": FEATURE_SCREEN,
    "components/features/ResearchChat/SourceCards.tsx": FEATURE_SCREEN,
    "components/features/ResearchDocument/ResearchDocumentDetailView.tsx": FEATURE_SCREEN,
    "components/shared/DataGrid/DetailGrid.tsx": SHARED_COMPONENT,
    "components/shared/DataGrid/DualSelectGrid.tsx": SHARED_COMPONENT,
    "components/shared/DataPanel/DetailPanel.tsx": SHARED_COMPONENT,
    "components/shared/DataPanel/MasterPanel.tsx": SHARED_COMPONENT,
    "components/shared/DataTable/DataTableBody.tsx": SHARED_COMPONENT,
    "components/shared/DataTable/DataTableFilterRow.tsx": SHARED_COMPONENT,
    "components/shared/DataTable/DataTableHeader.tsx": SHARED_COMPONENT,
    "components/shared/DataTable/DataTablePager.tsx": SHARED_COMPONENT,
    "components/shared/Feedback/Alert.tsx": SHARED_COMPONENT,
    "components/shared/Feedback/Loading.tsx": SHARED_COMPONENT,
    "components/shared/Feedback/ToastNotification.tsx": SHARED_COMPONENT,
    "components/shared/Layout/ConditionBar.tsx": SHARED_COMPONENT,
    "components/shared/Layout/GlobalTabs.tsx": SHARED_COMPONENT,
    "components/shared/Layout/Header.tsx": SHARED_COMPONENT,
    "components/shared/Layout/Sidebar.tsx": SHARED_COMPONENT,
    "components/shared/Layout/SplitPane.tsx": SHARED_COMPONENT,
    "components/shared/Layout/TableCell.tsx": SHARED_COMPONENT,
    "components/shared/Layout/TableGroup.tsx": SHARED_COMPONENT,
    "components/shared/ui/Button.tsx": SHARED_COMPONENT,
    "components/shared/ui/CheckBox.tsx": SHARED_COMPONENT,
    "components/shared/ui/CheckBoxGroup.tsx": SHARED_COMPONENT,
    "components/shared/ui/ExpandableCard.tsx": SHARED_COMPONENT,
    "components/shared/ui/FileListDisplay.tsx": SHARED_COMPONENT,
    "components/shared/ui/FileUploader.tsx": SHARED_COMPONENT,
    "components/shared/ui/MarkdownRenderer.tsx": SHARED_COMPONENT,
    "components/shared/ui/NumberBox.tsx": SHARED_COMPONENT,
    "components/shared/ui/Popup.tsx": SHARED_COMPONENT,
    "components/shared/ui/TabPanel.tsx": SHARED_COMPONENT,
    "components/shared/ui/TextBox.tsx": SHARED_COMPONENT,
    "components/shared/ui/primitives/FieldShell.tsx": SHARED_COMPONENT,
    "components/shared/ui/primitives/FileTypeIcon.tsx": SHARED_COMPONENT,
    "components/shared/ui/primitives/SelectMenu.tsx": SHARED_COMPONENT,
    "components/shared/ui/primitives/dialog.tsx": SHARED_COMPONENT,
    "app/api/common/email/route.ts": NON_DOM_COLOR,
    "lib/auth/auth.ts": NON_DOM_COLOR,
    "lib/terminal/candleChart.ts": NON_DOM_COLOR,
}

# Tailwind v3 기본 팔레트의 색 이름. 이 레포의 커스텀 색(slate.void·ink.primary 등)은 음영이
# 숫자가 아니라 이름이므로 아래 숫자 음영 패턴에 안 걸린다.
PALETTE_COLORS = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|"
    "teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
# 색을 받는 유틸리티 접두. `to` 를 포함하므로 앞에 `\b` 를 두어 낱말 중간(`photo-black`)을 피한다.
COLOR_PREFIXES = (
    "bg|text|border|ring|ring-offset|divide|outline|from|via|to|fill|stroke|"
    "shadow|accent|caret|decoration|placeholder"
)

PALETTE_UTILITY = re.compile(
    rf"\b(?:{COLOR_PREFIXES})-(?:{PALETTE_COLORS})-(?:50|[1-9]00|950)\b"
)
MONOCHROME_UTILITY = re.compile(rf"\b(?:{COLOR_PREFIXES})-(?:black|white)\b")
HEX_LITERAL = re.compile(
    r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])"
)

STRING_LITERAL = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|`[^`]*`", re.S)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"//[^\n]*")
PLACEHOLDER = re.compile(r"\x00(\d+)\x00")


def _fail(message: str) -> None:
    print(f"::error::{message}")


def strip_comments(source: str) -> str:
    """주석을 걷는다. 문자열을 먼저 자리표시자로 빼 두어 URL 의 `//` 를 주석으로 읽지 않는다."""
    held: list[str] = []

    def hold(match: re.Match[str]) -> str:
        held.append(match.group(0))
        return f"\x00{len(held) - 1}\x00"

    source = STRING_LITERAL.sub(hold, source)
    source = BLOCK_COMMENT.sub(" ", source)
    source = LINE_COMMENT.sub(" ", source)
    return PLACEHOLDER.sub(lambda m: held[int(m.group(1))], source)


def find_violations(source: str) -> dict[str, list[str]]:
    """파일 하나의 위반을 종류별로 낸다 (없으면 빈 dict)."""
    code = strip_comments(source)
    found: dict[str, list[str]] = {}

    palette = sorted(set(PALETTE_UTILITY.findall(code)))
    if palette:
        found["기본 팔레트"] = palette

    monochrome = sorted(set(MONOCHROME_UTILITY.findall(code)))
    if monochrome:
        found["흑백 유틸리티"] = monochrome

    hexes = sorted(
        {h for s in STRING_LITERAL.findall(code) for h in HEX_LITERAL.findall(s)}
    )
    if hexes:
        found["hex 리터럴"] = hexes

    return found


def main() -> int:
    missing_roots = [r for r in SCAN_ROOTS if not (FRONTEND / r).is_dir()]
    if missing_roots:
        for root in missing_roots:
            _fail(f"스캔 대상 디렉터리가 없습니다: frontend/{root}")
        _fail(
            "경로가 바뀌었을 수 있습니다 — 이 스크립트의 SCAN_ROOTS 를 함께 고치세요."
        )
        return 1

    files = sorted(
        path
        for root in SCAN_ROOTS
        for suffix in SCAN_SUFFIXES
        for path in (FRONTEND / root).rglob(suffix)
    )

    if len(files) < MIN_SCANNED_FILES:
        _fail(
            f"소스 파일을 {len(files)}건 수집했습니다 (하한 {MIN_SCANNED_FILES}) — fail-closed 종료"
        )
        _fail(
            "파일이 이동·삭제됐거나 스캔 경로가 현실과 어긋났을 수 있습니다. "
            "정당한 삭제라면 MIN_SCANNED_FILES 도 함께 내리세요."
        )
        return 1

    violators: dict[str, dict[str, list[str]]] = {}
    for path in files:
        found = find_violations(path.read_text(encoding="utf-8"))
        if found:
            violators[path.relative_to(FRONTEND).as_posix()] = found

    print(
        f"`.tsx` {len(files)}건 검사 (frontend/{', frontend/'.join(SCAN_ROOTS)}) · "
        f"위반 {len(violators)}건 · allowlist {len(ALLOWLIST)}건 (상한 {ALLOWLIST_CAP})"
    )
    print()

    ok = True

    # allowlist 가 상한을 넘었나 — 새 위반을 조용히 등록하는 길을 막는다.
    if len(ALLOWLIST) > ALLOWLIST_CAP:
        _fail(
            f"allowlist 가 {len(ALLOWLIST)}건으로 상한 {ALLOWLIST_CAP}건을 넘었습니다 — "
            "등록을 늘리려면 상한도 같이 올려야 하고, 그 판단은 사람이 합니다."
        )
        ok = False

    # 낡은 항목 — 더는 위반이 아니거나 파일이 없다.
    stale_clean = sorted(set(ALLOWLIST) - set(violators))
    stale_missing = sorted(p for p in ALLOWLIST if not (FRONTEND / p).is_file())
    stale_clean = [p for p in stale_clean if p not in stale_missing]

    if stale_missing:
        _fail(
            f"allowlist 에 적힌 파일이 없습니다 {len(stale_missing)}건 — 항목을 지우세요:"
        )
        for path in stale_missing:
            _fail(f"  · {path}")
        ok = False

    if stale_clean:
        _fail(
            f"allowlist 에 적힌 파일이 더는 위반이 아닙니다 {len(stale_clean)}건 — "
            f"항목을 지우고 ALLOWLIST_CAP 을 {ALLOWLIST_CAP - len(stale_clean)} 로 내리세요:"
        )
        for path in stale_clean:
            _fail(f"  · {path}")
        ok = False

    # 등록되지 않은 새 위반.
    unexpected = sorted(set(violators) - set(ALLOWLIST))
    if unexpected:
        _fail(f"토큰 밖 색을 쓰는 파일 {len(unexpected)}건 — 토큰으로 바꾸세요:")
        for path in unexpected:
            detail = " / ".join(
                f"{kind}: {', '.join(hits[:5])}{' …' if len(hits) > 5 else ''}"
                for kind, hits in violators[path].items()
            )
            _fail(f"  · {path} — {detail}")
        _fail(
            "색은 frontend/styles/globals.css 의 토큰만 씁니다 "
            "(디자인 시스템 .docs/4-아키텍처/디자인-시스템.md §1·§8)."
        )
        ok = False

    if ok:
        print(
            f"판정: 등록되지 않은 위반 0건 (allowlist {len(ALLOWLIST)}건 제외, 상한 {ALLOWLIST_CAP})"
        )
        print(
            "allowlist 는 #73 S2~S5 가 줄인다 — 줄일 때 ALLOWLIST_CAP 도 함께 내린다."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
