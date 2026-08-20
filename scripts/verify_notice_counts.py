"""THIRD-PARTY-NOTICES.md 의 숫자를 실측과 대조한다 — fail-closed (#365).

## 왜 있나

이 문서의 개수·목록은 **오래 사람이 손으로 세어 적었다.** 그리고 이 레포가 반복해 온 결함
클래스가 정확히 그것이다 — 「손으로 유지하는 숫자가 현실과 어긋나도 아무 신호가 없다」.
legal notice 에서 이미 두 번 어긋났고 (§3 의 화면 개수 7 vs 실측 8 · woff2 검증 서술),
**둘 다 사람이 우연히 눈치채서** 잡혔다. 그물이 없으면 다음엔 못 잡는다.

지금은 §1·§2 를 `generate_notices.py` 가 만든다. 그래도 이 검사기는 **그대로 남는다** —
생성기 출력을 믿지 않고 문서를 **다시 파싱해서** 실측과 맞춰 본다. 생성기로 생성기를 검증하면
두 스크립트가 같은 버그를 공유하고, §3 처럼 생성기가 손대지 않는 절은 아무도 안 본다.
(생성기는 이 파일에서 스캐너 정의를 가져다 쓴다 — 의존 방향은 생성기 → 검사기 한쪽이다.)

## 무엇을 대조하나 — 네 축

  ① **문서 ↔ 실측** (가장 센 축) — `license-checker-rseidelsohn` 을 문서에 적힌 그 명령으로
     다시 돌려, **문서가 열거한 `이름@버전` 집합과 실측 집합이 같은지**를 양방향으로 본다.
     개수만 맞추면 「하나 빠지고 하나 더 들어온」 상태가 통과한다. 집합이 같으면 개수는 따라온다.
  ② **문서 내부 정합** — 최상단 총계 = §1 합 + §2 합, 각 절 머리의 선언 개수 = 그 절이 실제로
     열거한 항목 수. 실측 없이도 어긋남이 드러나는 축이라, 실측이 못 도는 환경에서도 값이 있다.
  ③ **§2 예외 축** — 「원문 파일 없이 선언만 있는 패키지」 목록. 어떤 패키지가 조용히 라이선스
     파일을 빼도 ①의 집합 대조는 통과하므로 따로 본다 (`licenseFile` 키 + 그 경로의 파일 실재).
  ④ **§3 번들 자산** — npm 을 안 거쳐 실측 스캔 범위 밖인 절. 폰트 파일 수·`@font-face` 수는
     저장소 안에서 셀 수 있으므로 문서의 선언과 대조한다.

## fail-closed

  · 스캔 명령이 실패하면 실패한다. **「스캔이 안 돌았다」는 「위반이 없다」가 아니다.**
  · 문서에서 패키지를 0건 파싱하거나 실측이 0건이면 실패한다.
  · **선언 패턴이 정확히 1회 매치되지 않으면 실패한다.** 문서를 고쳐 쓰다 문장이 바뀌면
    정규식이 조용히 0건이 되고, 그 순간 이 스크립트는 자기가 막으려던 클래스를 스스로 저지른다.
  · 축마다 **검사한 건수를 출력에 남긴다** — 통과가 「일치했다」인지 「아무것도 안 봤다」인지
    읽는 사람이 구분할 수 있어야 한다.

## 실행

    python3 scripts/verify_notice_counts.py                 # 스캔을 직접 돌린다 (node 필요)
    python3 scripts/verify_notice_counts.py --licenses X.json  # 이미 뜬 산출물을 쓴다

스캐너 버전은 아래 `SCANNER` 에 **박아 둔다** — 버전이 바뀌면 산출물이 달라질 수 있고, 그때는
문서와 함께 사람이 판단해야 한다. 레지스트리가 주는 대로 받으면 그 판단 자리가 사라진다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTICES = REPO_ROOT / "THIRD-PARTY-NOTICES.md"
FRONTEND = REPO_ROOT / "frontend"
FONTS_CSS = FRONTEND / "styles" / "fonts.css"

# 문서 최상단의 재현 명령과 같은 것을 쓴다 (버전만 박는다).
SCANNER = "license-checker-rseidelsohn@5.0.1"
SCAN_ARGS = ["--production", "--excludePrivatePackages", "--json"]

# 파싱 하한 — 이보다 적으면 문서 구조가 바뀌어 정규식이 헛돈 것이다 (fail-closed).
MIN_PACKAGES = 400
MIN_VARIANTS = 10


class Problem(Exception):
    """검사를 계속할 수 없는 상태 — 파싱 실패·스캔 실패."""


def fail(message: str) -> None:
    print(f"::error::{message}")


def one(pattern: str, text: str, what: str) -> re.Match[str]:
    """정확히 1회 매치되는 선언을 뽑는다. 0건·2건 이상이면 파싱이 깨진 것이다."""
    found = list(re.finditer(pattern, text, re.MULTILINE))
    if len(found) != 1:
        raise Problem(
            f"{what}: 선언 패턴이 {len(found)}회 매치됐다 (기대 1회) — 문서 문장이 바뀌어 "
            f"이 검사가 조용히 죽는 자리다. 패턴: {pattern!r}"
        )
    return found[0]


def table_packages(text: str) -> list[str]:
    """`| \\`이름\\` | 버전 | …` 표 행에서 `이름@버전` 을 뽑는다."""
    rows = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*([^|\s]+)\s*\|", text, re.MULTILINE)
    return [f"{name}@{version}" for name, version in rows]


def split_sections(text: str) -> dict[str, str]:
    """`## N.` 머리로 문서를 절로 가른다 (§3 의 표는 npm 패키지가 아니다 — 섞이면 안 된다)."""
    marks = [(m.group(1), m.start()) for m in re.finditer(r"^## (\d)\. ", text, re.MULTILINE)]
    if len(marks) != 3:
        raise Problem(f"절 머리(`## N. `)를 {len(marks)}개 찾았다 — 기대 3개 (§1·§2·§3)")
    sections: dict[str, str] = {}
    for index, (number, start) in enumerate(marks):
        end = marks[index + 1][1] if index + 1 < len(marks) else len(text)
        sections[number] = text[start:end]
    return sections


# ── ② 문서 내부 정합 ──────────────────────────────────────────────────────────
def parse_document(text: str) -> tuple[set[str], set[str], list[str]]:
    """(문서가 열거한 `이름@버전` 집합, §2 예외 집합, 판정 줄). 어긋나면 Problem."""
    lines: list[str] = []
    sections = split_sections(text)

    total = int(one(r"프로덕션 의존성 (\d+)개", text, "최상단 총계").group(1))

    # §1 Apache-2.0 — 머리의 개수 = 변형별 선언 합 = 변형이 실제로 열거한 패키지 수
    apache_declared = int(one(r"^(\d+)개 패키지\. Apache-2\.0 은", sections["1"], "§1 Apache-2.0 머리").group(1))
    variants = re.findall(r"<summary>변형 (\d+) — (\d+)개 패키지: (.+?)</summary>", sections["1"])
    if len(variants) < MIN_VARIANTS:
        raise Problem(f"§1 본문 변형을 {len(variants)}개 파싱했다 — 하한 {MIN_VARIANTS} 미만")
    apache: set[str] = set()
    for number, declared, body in variants:
        listed = re.findall(r"`([^`]+)`", body)
        if len(listed) != int(declared):
            raise Problem(
                f"§1 변형 {number}: 「{declared}개 패키지」라 적혀 있는데 실제로 열거한 것은 {len(listed)}개다"
            )
        apache |= set(listed)
    if len(apache) != apache_declared:
        raise Problem(f"§1 Apache-2.0: 머리는 {apache_declared}개 · 변형 열거 합은 {len(apache)}개")
    lines.append(f"§1 Apache-2.0 {apache_declared}개 = 본문 변형 {len(variants)}종의 열거 합")

    # §1 나머지 (MPL·LGPL·듀얼·퍼블릭도메인 등) — 표로만 적힌 절
    others = table_packages(sections["1"])
    section1 = apache | set(others)
    if len(section1) != apache_declared + len(others):
        raise Problem("§1 에 같은 패키지가 두 번 적혀 있다 (변형 목록과 표가 겹친다)")
    lines.append(f"§1 표 절 {len(others)}개 → §1 합계 {len(section1)}개")

    # §2 — 머리 개수 = 예외 표 + 나머지 표
    section2_declared = int(one(r"^## 2\. 그 외 permissive 라이선스 \((\d+)개\)", sections["2"], "§2 머리").group(1))
    exception_declared = int(
        one(
            r"원문 파일 없이 선언만 있는 패키지 \((\d+)개\)",
            sections["2"],
            "§2 예외 머리",
        ).group(1)
    )
    rest_declared = int(one(r"<summary>펼치기 — 나머지 (\d+)개", sections["2"], "§2 나머지 머리").group(1))
    body_declared, file_declared = one(r"(\d+)개 중 (\d+)개는 npm 배포본에", sections["2"], "§2 본문 서술").groups()
    if int(body_declared) != section2_declared or int(file_declared) != rest_declared:
        raise Problem(
            f"§2 본문 서술({body_declared} 중 {file_declared})이 머리 선언"
            f"({section2_declared} · 나머지 {rest_declared})과 어긋난다"
        )
    if exception_declared + rest_declared != section2_declared:
        raise Problem(f"§2: 예외 {exception_declared} + 나머지 {rest_declared} ≠ 머리 {section2_declared}")
    section2 = set(table_packages(sections["2"]))
    if len(section2) != section2_declared:
        raise Problem(f"§2 표 행 {len(section2)}개 · 머리 선언 {section2_declared}개")
    # 예외 표(원문 파일 없이 선언만 있는 것)는 `<details>` 앞에만 있다 — 실측과 따로 대조한다.
    exceptions = set(table_packages(sections["2"].split("<details>")[0]))
    if len(exceptions) != exception_declared:
        raise Problem(f"§2 예외 표 행 {len(exceptions)}개 · 머리 선언 {exception_declared}개")
    lines.append(
        f"§2 permissive {section2_declared}개 = 예외 {exception_declared} + 나머지 {rest_declared} (표 행 수와 일치)"
    )

    declared_packages = section1 | section2
    if len(declared_packages) != len(section1) + len(section2):
        raise Problem("§1 과 §2 에 같은 패키지가 중복으로 적혀 있다")
    if len(declared_packages) != total:
        raise Problem(f"최상단 총계 {total}개 · §1({len(section1)}) + §2({len(section2)}) = {len(declared_packages)}개")
    if len(declared_packages) < MIN_PACKAGES:
        raise Problem(
            f"문서에서 패키지를 {len(declared_packages)}개 파싱했다 — 하한 {MIN_PACKAGES} 미만 "
            "(표 형식이 바뀌어 파싱이 헛돈 것이다)"
        )
    lines.append(f"최상단 총계 {total}개 = §1 {len(section1)} + §2 {len(section2)}")
    return declared_packages, exceptions, lines


# ── ③ §3 번들 정적 자산 (npm 스캔 범위 밖 — 저장소에서 직접 센다) ──────────────
def check_bundled_assets(text: str) -> tuple[list[str], list[str]]:
    """(판정 줄, 위반). 폰트 파일 수·`@font-face` 수의 선언 ↔ 실측."""
    section3 = split_sections(text)["3"]
    problems: list[str] = []

    weights, formats, files = one(
        r"굵기 (\d+)종\(Thin~Black\) × 포맷 (\d+)종\(woff/woff2\), 총 (\d+)개 파일",
        section3,
        "§3 폰트 파일 수 선언",
    ).groups()
    faces = one(r"`@font-face` (\d+)개", section3, "§3 @font-face 선언").group(1)

    actual_woff = len(list((FRONTEND / "public" / "font" / "woff").glob("*.woff")))
    actual_woff2 = len(list((FRONTEND / "public" / "font" / "woff2").glob("*.woff2")))
    if actual_woff == 0 or actual_woff2 == 0:
        problems.append(
            f"폰트 파일을 woff {actual_woff}개 · woff2 {actual_woff2}개 찾았다 — 0건은 경로가 바뀐 것이다 (fail-closed)"
        )
    if actual_woff != int(weights) or actual_woff2 != int(weights):
        problems.append(f"§3: 굵기 {weights}종이라 적혀 있는데 실측은 woff {actual_woff}개 · woff2 {actual_woff2}개다")
    if actual_woff + actual_woff2 != int(files):
        problems.append(f"§3: 총 {files}개 파일이라 적혀 있는데 실측 합은 {actual_woff + actual_woff2}개다")
    if int(weights) * int(formats) != int(files):
        problems.append(f"§3: {weights}종 × {formats}포맷 ≠ {files}개")

    if not FONTS_CSS.is_file():
        problems.append(f"§3: {FONTS_CSS.relative_to(REPO_ROOT)} 가 없다 — 선언을 대조할 수 없다")
        actual_faces = 0
    else:
        actual_faces = len(re.findall(r"@font-face", FONTS_CSS.read_text(encoding="utf-8")))
        if actual_faces != int(faces):
            problems.append(f"§3: `@font-face` {faces}개라 적혀 있는데 {FONTS_CSS.name} 의 실측은 {actual_faces}개다")

    return [
        f"§3 폰트 파일 {actual_woff + actual_woff2}개 실측 (woff {actual_woff} · "
        f"woff2 {actual_woff2}) · `@font-face` {actual_faces}개 — 선언 {files}개 · {faces}개",
    ], problems


# ── ① 실측 스캔 ───────────────────────────────────────────────────────────────
def run_scan(destination: Path) -> dict[str, dict]:
    """문서에 적힌 재현 명령을 그대로 돌린다. 실패는 그대로 실패다 (fail-closed)."""
    if not (FRONTEND / "node_modules").is_dir():
        raise Problem(
            f"{FRONTEND.relative_to(REPO_ROOT)}/node_modules 가 없다 — 스캔 대상이 없는 상태로 "
            "통과시키지 않는다. `npm ci --ignore-scripts` 를 먼저 돌려라"
        )
    result = subprocess.run(
        ["npx", "--yes", SCANNER, *SCAN_ARGS, "--out", str(destination)],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise Problem(
            f"라이선스 스캔 실패 (exit {result.returncode}): {(result.stderr or result.stdout).strip()[:400]}"
        )
    return load_scan(destination)


def load_scan(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Problem(f"스캔 산출물을 읽을 수 없다 ({path}): {error}") from error
    if not isinstance(data, dict) or not data:
        raise Problem(f"스캔 산출물이 비었다 ({path}) — 0건은 통과가 아니다 (fail-closed)")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--licenses",
        type=Path,
        default=None,
        help=f"이미 뜬 {SCANNER} 산출물(JSON). 없으면 직접 돌린다",
    )
    args = parser.parse_args(argv)

    if not NOTICES.is_file():
        fail(f"{NOTICES} 가 없다 — 대조 대상이 사라졌다 (fail-closed)")
        return 1
    text = NOTICES.read_text(encoding="utf-8")

    problems: list[str] = []
    try:
        declared, exceptions, notes = parse_document(text)
    except Problem as error:
        fail(str(error))
        return 1
    for note in notes:
        print(f"  · {note}")

    asset_notes, asset_problems = check_bundled_assets(text)
    for note in asset_notes:
        print(f"  · {note}")
    problems += asset_problems

    with tempfile.TemporaryDirectory(prefix="notice-counts-") as tmp:
        try:
            if args.licenses is not None:
                scanned = load_scan(args.licenses)
                source = str(args.licenses)
            else:
                scanned = run_scan(Path(tmp) / "licenses-prod.json")
                source = f"{SCANNER} {' '.join(SCAN_ARGS)} (cwd=frontend)"
        except Problem as error:
            fail(str(error))
            return 1

    print(f"  · 실측 {len(scanned)}개 ← {source}")

    missing = sorted(declared - set(scanned))
    extra = sorted(set(scanned) - declared)
    if missing:
        problems.append(
            f"문서에 있는데 실측에 없는 패키지 {len(missing)}개: {', '.join(missing[:20])}"
            + (" …" if len(missing) > 20 else "")
        )
    if extra:
        problems.append(
            f"실측에 있는데 문서에 없는 패키지 {len(extra)}개: {', '.join(extra[:20])}"
            + (" …" if len(extra) > 20 else "")
        )

    # §2 예외 축 — 「원문 파일을 동봉하지 않는 것」이 문서의 3개 그대로인지. 개수·목록 축과
    # 별개다: 어떤 패키지가 조용히 라이선스 파일을 빼도 위 집합 대조는 통과한다.
    without_file = {
        name for name, meta in scanned.items() if not meta.get("licenseFile") or not Path(meta["licenseFile"]).is_file()
    }
    if without_file != exceptions:
        detail = f"실측에만 {sorted(without_file - exceptions)} · 문서에만 {sorted(exceptions - without_file)}"
        if len(without_file) > len(scanned) // 5:
            detail += (
                " (실측의 licenseFile 경로가 이 환경에서 안 풀린다 — 다른 곳에서 뜬 "
                "산출물을 `--licenses` 로 준 것은 아닌지 확인하라)"
            )
        problems.append(
            f"§2 「원문 파일 없이 선언만 있는 패키지」가 문서 {len(exceptions)}개 · "
            f"실측 {len(without_file)}개로 어긋난다 — {detail}"
        )

    print(
        f"판정: 문서 열거 {len(declared)}개 ↔ 실측 {len(scanned)}개 · "
        f"문서에만 {len(missing)}개 · 실측에만 {len(extra)}개 · "
        f"원문 파일 없는 패키지 {len(without_file)}개 (문서 선언 {len(exceptions)}개)"
    )
    if problems:
        fail(f"THIRD-PARTY-NOTICES.md 의 손유지 숫자가 현실과 어긋났습니다 ({len(problems)}건):")
        for problem in problems:
            fail(f"  · {problem}")
        fail(
            "문서 최상단의 재현 명령을 다시 돌려 산출물을 정본으로 삼아 갱신하세요 "
            "(개수만 고치면 목록이 어긋난 채로 남습니다)."
        )
        return 1
    print("THIRD-PARTY-NOTICES.md 의 개수·목록이 실측과 일치합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
