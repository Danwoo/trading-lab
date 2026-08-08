"""THIRD-PARTY-NOTICES.md 의 기계 소관 구간을 실측 스캔에서 생성한다 — fail-closed.

## 왜 있나

이 문서의 개수·목록은 **사람이 손으로 세어 적어 왔다.** `verify_notice_counts.py` 는 그것이
현실과 어긋나면 빨간불을 켜지만, 어긋난 것을 **되돌리는 일은 여전히 사람 몫**이었다. 그래서
의존성이 하나 올라갈 때마다(dependabot PR 하나마다) 사람이 목록째 다시 옮겨 적어야 했다.

여기서 그 손일을 없앤다: **생성기가 만들고 검사기가 검증한다.** 둘은 대체 관계가 아니다 —
생성기는 「문서를 실측에 맞춘다」, 검사기는 「문서가 실측과 맞는지 독립적으로 본다」.
검사기가 생성기의 출력을 그냥 믿으면 두 스크립트가 같은 버그를 공유하게 되므로,
검사기는 문서를 **다시 파싱해서** 본다 (그 관계를 유지하려고 이 파일은 검사기를 고치지 않는다).

## 기계 소관 / 사람 소관 경계

**기계가 쓰는 것** — 실측(`license-checker-rseidelsohn` 산출물)에서 결정론적으로 나오는 것뿐:

  · 최상단 총계 (`프로덕션 의존성 N개` · `§1·§2 가 그 N개고`)
  · §1 Apache-2.0 의 머리 개수·변형 종수, 그리고 `<details>` 변형 블록 전체
    (변형 = **라이선스 원문이 같은 패키지들의 묶음**이므로 원문 텍스트도 실측 산출물이다)
  · §1 나머지 절(MPL·LGPL·듀얼·퍼블릭도메인 등)의 **표 행**
  · §2 의 머리 개수·본문 서술 숫자·예외 표·나머지 표

**사람이 쓰는 것** — 기계가 만들 수 없는 판단·서술. 생성기는 **한 글자도 건드리지 않는다**:

  · 라이선스 **분류**(어떤 SPDX 가 §1 의 어느 절로 가는지)와 그 절의 제목·설명 산문.
    분류는 법적 판단이다 — 그래서 아래 `SECTION1_GROUPS`·`PERMISSIVE` 에 **명시**해 두고,
    표에 없는 라이선스가 나오면 §2 로 흘려보내지 않고 **실패**한다 (fail-closed).
  · 최상단의 갱신 이력 문단, `## ✅ 상용 라이선스 없음` 절, 각 절의 도입 산문
  · **§3 번들 정적 자산 전체** — npm 을 안 거쳐 실측 스캔 범위 밖이다. 이 절의 숫자는
    `verify_notice_counts.py` 의 축 ④ 가 저장소 파일과 직접 대조한다.

## fail-closed

  · 스캔이 실패하거나 0건이면 실패한다. **「스캔이 안 돌았다」는 「위반이 없다」가 아니다.**
  · 문서의 앵커(치환 자리)가 정확히 1회 매치되지 않으면 실패한다. 문장이 바뀌어 앵커가
    조용히 0건이 되면, 생성기는 「갱신했다」면서 아무것도 안 갱신한 채 통과한다.
  · 분류표에 없는 라이선스, 패키지가 0건인 §1 절, 원문 파일이 없는 Apache 패키지는 실패다.
  · 갱신한 구간 수를 출력에 남긴다 — 통과가 「일치했다」인지 「아무것도 안 봤다」인지 구분되게.

## 실행

    python3 scripts/generate_notices.py                    # 문서를 갱신한다 (node 필요)
    python3 scripts/generate_notices.py --check            # 갱신하지 않고 어긋나면 실패한다 (CI)
    python3 scripts/generate_notices.py --licenses X.json  # 이미 뜬 산출물을 쓴다

스캐너와 그 인자는 `verify_notice_counts.py` 에서 **가져다 쓴다** — 문서 최상단의 재현 명령 ·
검사기 · 생성기가 같은 명령을 봐야 하고, 세 벌로 적으면 그중 하나가 조용히 낡는다.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tempfile
from pathlib import Path

# 같은 디렉터리의 검사기에서 스캐너 정의를 가져온다 (스크립트로 실행하면 sys.path[0] 이
# 이 디렉터리지만, 다른 곳에서 import 될 때를 위해 명시적으로 넣는다).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_notice_counts import (  # noqa: E402
    MIN_PACKAGES,
    MIN_VARIANTS,
    NOTICES,
    Problem,
    load_scan,
    run_scan,
)

# ── 사람의 판단 — 라이선스 분류 ───────────────────────────────────────────────
# §1 은 「고지·확인이 필요한 라이선스」다. 어떤 SPDX 가 어느 절로 가는지는 법적 판단이라
# 기계가 정하지 않는다. 이 표가 그 판단을 명시하고, 생성기는 표대로 **분배만** 한다.
# 제목은 문서의 `### ` 헤더와 byte-identical 이어야 한다 (앵커).
SECTION1_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("### Apache License 2.0", ("Apache-2.0",)),
    ("### Mozilla Public License 2.0", ("MPL-2.0",)),
    ("### GNU Lesser General Public License 3.0", ("LGPL-3.0-or-later",)),
    ("### jszip — 듀얼 라이선스", ("(MIT OR GPL-3.0-or-later)",)),
    ("### pako — MIT + Zlib 결합", ("(MIT AND Zlib)",)),
    (
        "### caniuse-lite — 데이터(코드 아님), Creative Commons Attribution 4.0",
        ("CC-BY-4.0",),
    ),
    ("### mdn-data — 퍼블릭 도메인 동등", ("CC0-1.0",)),
    ("### postgres — 퍼블릭 도메인 동등", ("Unlicense",)),
]
APACHE_HEADING = SECTION1_GROUPS[0][0]

# §2 로 보내도 되는 것 — 「저작권·허가 고지 보존 외 추가 의무 없음」이라 사람이 판정한 부류.
# 여기 없는 라이선스는 §2 로 흘러가지 않고 실패한다: 새 카피레프트가 permissive 목록에
# 조용히 섞이는 것이 이 문서에서 가장 비싼 사고다.
PERMISSIVE: frozenset[str] = frozenset(
    {
        "0BSD",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BlueOak-1.0.0",
        "ISC",
        "MIT",
        "MIT-0",
        "MIT*",
    }
)


def one(pattern: str, text: str, what: str) -> re.Match[str]:
    """정확히 1회 매치되는 앵커를 뽑는다. 0건·2건 이상이면 치환 자리가 깨진 것이다."""
    found = list(re.finditer(pattern, text, re.MULTILINE))
    if len(found) != 1:
        raise Problem(
            f"{what}: 앵커가 {len(found)}회 매치됐다 (기대 1회) — 문서 문장이 바뀌어 "
            f"생성기가 조용히 아무것도 안 고치는 자리다. 패턴: {pattern!r}"
        )
    return found[0]


def substitute(text: str, pattern: str, what: str, *replacements: str) -> str:
    """앵커의 캡처 그룹을 순서대로 갈아 끼운다 (앵커 밖의 산문은 건드리지 않는다)."""
    match = one(pattern, text, what)
    if len(match.groups()) != len(replacements):
        raise Problem(
            f"{what}: 캡처 {len(match.groups())}개 · 치환값 {len(replacements)}개"
        )
    rebuilt = match.group(0)
    # 뒤에서부터 갈아야 앞 그룹 치환이 뒤 그룹의 오프셋을 흔들지 않는다.
    for index in range(len(replacements), 0, -1):
        start = match.start(index) - match.start()
        end = match.end(index) - match.start()
        rebuilt = rebuilt[:start] + replacements[index - 1] + rebuilt[end:]
    return text[: match.start()] + rebuilt + text[match.end() :]


# ── 실측 → 자료 구조 ─────────────────────────────────────────────────────────
def license_text(entry: dict, package: str) -> str:
    """패키지가 동봉한 라이선스 원문. 줄끝만 정규화하고 내용은 그대로 둔다."""
    path = entry.get("licenseFile")
    if not path or not Path(path).is_file():
        raise Problem(
            f"{package}: 라이선스 원문 파일이 없다 ({path!r}) — §1 은 원문을 실어야 하는 절이라 "
            "본문 없이 만들 수 없다. 사람이 업스트림에서 확인해야 한다"
        )
    return (
        Path(path)
        .read_text(encoding="utf-8", errors="replace")
        .replace("\r\n", "\n")
        .strip()
    )


def classify(scanned: dict[str, dict]) -> tuple[dict[str, list[str]], list[str]]:
    """(§1 절 제목 → 패키지 목록, §2 패키지 목록). 분류표에 없는 라이선스는 Problem."""
    by_heading: dict[str, list[str]] = {heading: [] for heading, _ in SECTION1_GROUPS}
    license_to_heading = {
        spdx: heading for heading, spdxs in SECTION1_GROUPS for spdx in spdxs
    }
    section2: list[str] = []
    unknown: dict[str, list[str]] = {}

    for package in sorted(scanned):
        declared = scanned[package].get("licenses")
        name = declared if isinstance(declared, str) else str(declared)
        if name in license_to_heading:
            by_heading[license_to_heading[name]].append(package)
        elif name in PERMISSIVE:
            section2.append(package)
        else:
            unknown.setdefault(name, []).append(package)

    if unknown:
        detail = " · ".join(
            f"{name}: {', '.join(packages[:5])}"
            for name, packages in sorted(unknown.items())
        )
        raise Problem(
            f"분류표에 없는 라이선스 {len(unknown)}종이 실측에 나왔다 — {detail}. "
            "permissive 로 흘려보내지 않는다: 사람이 판단해 SECTION1_GROUPS 에 절을 만들거나 "
            "PERMISSIVE 에 추가하라 (fail-closed)"
        )

    for heading, packages in by_heading.items():
        if not packages:
            raise Problem(
                f"{heading}: 해당하는 패키지가 실측에 0건이다 — 그 절을 지울지, 분류표를 고칠지 "
                "사람이 판단해야 한다 (생성기가 빈 절을 만들지 않는다)"
            )
    return by_heading, section2


def apache_variants(
    packages: list[str], scanned: dict[str, dict]
) -> list[tuple[list[str], str]]:
    """라이선스 원문이 같은 것끼리 묶는다 → [(패키지 목록, 원문)] (개수 내림차순)."""
    groups: dict[str, list[str]] = {}
    for package in packages:
        groups.setdefault(license_text(scanned[package], package), []).append(package)
    ordered = sorted(
        ((sorted(names), body) for body, names in groups.items()),
        key=lambda item: (-len(item[0]), item[0][0]),
    )
    if len(ordered) < MIN_VARIANTS:
        raise Problem(
            f"Apache-2.0 본문 변형을 {len(ordered)}종 묶었다 — 하한 {MIN_VARIANTS} 미만 "
            "(원문 읽기가 헛돌아 전부 한 덩어리가 된 것은 아닌지 확인하라)"
        )
    return ordered


# ── 렌더링 ───────────────────────────────────────────────────────────────────
def package_list(packages: list[str]) -> str:
    return ", ".join(f"`{package}`" for package in packages)


def split_name_version(package: str) -> tuple[str, str]:
    name, _, version = package.rpartition("@")
    if not name or not version:
        raise Problem(f"패키지 키를 이름@버전으로 가를 수 없다: {package!r}")
    return name, version


def table_rows(
    packages: list[str], scanned: dict[str, dict], with_license: bool
) -> str:
    rows = []
    for package in packages:
        name, version = split_name_version(package)
        cells = [f"`{name}`", version]
        if with_license:
            cells.append(str(scanned[package].get("licenses")))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def replace_table(text: str, what: str, rows: str) -> str:
    """`| 패키지 | 버전 | …` 표의 **행만** 갈아 끼운다 (머리·구분줄·주변 산문 보존)."""
    pattern = r"^\| 패키지 \| 버전 \|.*\n\|[-| ]+\|\n((?:\|.*\n)+)"
    match = one(pattern, text, what)
    return text[: match.start(1)] + rows + "\n" + text[match.end(1) :]


def render_variants(variants: list[tuple[list[str], str]]) -> str:
    blocks = []
    for number, (packages, body) in enumerate(variants, start=1):
        blocks.append(
            f"<details><summary>변형 {number} — {len(packages)}개 패키지: "
            f"{package_list(packages)}</summary>\n\n"
            f"```\n{body}\n```\n</details>"
        )
    return "\n\n".join(blocks)


# ── 문서 조립 ────────────────────────────────────────────────────────────────
def split_sections(text: str) -> tuple[str, dict[str, str], list[str]]:
    """(머리말, {절 번호: 본문}, 절 번호 순서). 검사기와 같은 `## N. ` 머리로 가른다."""
    marks = [m.start() for m in re.finditer(r"^## (\d)\. ", text, re.MULTILINE)]
    if len(marks) != 3:
        raise Problem(
            f"절 머리(`## N. `)를 {len(marks)}개 찾았다 — 기대 3개 (§1·§2·§3)"
        )
    head = text[: marks[0]]
    bodies = [
        text[start : marks[index + 1] if index + 1 < len(marks) else len(text)]
        for index, start in enumerate(marks)
    ]
    return head, {"1": bodies[0], "2": bodies[1], "3": bodies[2]}, ["1", "2", "3"]


def rewrite_section1(
    section: str, by_heading: dict[str, list[str]], scanned: dict[str, dict]
) -> tuple[str, int]:
    """§1 — Apache 변형 블록과 나머지 절의 표 행. 절 제목·설명 산문은 보존한다."""
    starts = [m.start() for m in re.finditer(r"^### ", section, re.MULTILINE)]
    if len(starts) != len(SECTION1_GROUPS):
        raise Problem(
            f"§1 의 `### ` 절을 {len(starts)}개 찾았다 — 분류표는 {len(SECTION1_GROUPS)}개다. "
            "절을 더하거나 뺐다면 SECTION1_GROUPS 도 함께 고쳐야 한다"
        )
    bounds = starts + [len(section)]
    preamble = section[: starts[0]]  # `## 1.` 머리와 도입 산문 — 사람 소관
    chunks = [section[bounds[i] : bounds[i + 1]] for i in range(len(starts))]

    updated = 0
    for index, (heading, _) in enumerate(SECTION1_GROUPS):
        chunk = chunks[index]
        if not chunk.startswith(heading + "\n"):
            raise Problem(
                f"§1 의 {index + 1}번째 절 제목이 분류표와 다르다 — 문서: "
                f"{chunk.splitlines()[0]!r} · 분류표: {heading!r}"
            )
        packages = by_heading[heading]
        if heading == APACHE_HEADING:
            variants = apache_variants(packages, scanned)
            chunk = substitute(
                chunk,
                r"^(\d+)개 패키지\. Apache-2\.0 은",
                "§1 Apache-2.0 머리 개수",
                str(len(packages)),
            )
            chunk = substitute(
                chunk,
                r"본문 텍스트 변형 (\d+)종",
                "§1 Apache-2.0 변형 종수",
                str(len(variants)),
            )
            first = chunk.index("<details>")
            last = chunk.rindex("</details>") + len("</details>")
            chunk = chunk[:first] + render_variants(variants) + chunk[last:]
            updated += 3
        else:
            chunk = replace_table(
                chunk, f"§1 {heading} 표", table_rows(packages, scanned, False)
            )
            updated += 1
        chunks[index] = chunk
    return preamble + "".join(chunks), updated


def rewrite_section2(
    section: str, packages: list[str], scanned: dict[str, dict]
) -> tuple[str, int]:
    """§2 — 머리 개수·본문 서술 숫자·예외 표·나머지 표. 도입 산문은 보존한다."""
    without_file = [
        package
        for package in packages
        if not scanned[package].get("licenseFile")
        or not Path(scanned[package]["licenseFile"]).is_file()
    ]
    with_file = [package for package in packages if package not in set(without_file)]

    # 원문 파일이 없는 패키지는 소수여야 한다. 대량이면 「그 패키지들이 원문을 뺐다」가 아니라
    # **경로가 이 환경에서 안 풀린 것**이다 (다른 곳에서 뜬 산출물을 `--licenses` 로 준 경우).
    # 그대로 쓰면 예외 표에 수백 개를 실은 문서가 만들어진다 — 검사기가 잡기 전에 여기서 멈춘다.
    if len(without_file) > len(packages) // 5:
        raise Problem(
            f"§2 에서 원문 파일이 없는 패키지가 {len(without_file)}/{len(packages)}개다 — "
            "licenseFile 경로가 이 환경에서 안 풀린 것으로 본다 (다른 곳에서 뜬 산출물을 "
            "`--licenses` 로 준 것은 아닌지 확인하라)"
        )

    total, exceptions, rest = len(packages), len(without_file), len(with_file)
    section = substitute(
        section,
        r"^## 2\. 그 외 permissive 라이선스 \((\d+)개\)",
        "§2 머리 개수",
        str(total),
    )
    section = substitute(
        section,
        r"(\d+)개 중 (\d+)개는 npm 배포본에",
        "§2 본문 서술 (총계·동봉)",
        str(total),
        str(rest),
    )
    section = substitute(
        section,
        r", (\d+)개는 `package\.json` 의",
        "§2 본문 서술 (예외)",
        str(exceptions),
    )
    section = substitute(
        section,
        r"원문 파일 없이 선언만 있는 패키지 \((\d+)개\)",
        "§2 예외 절 머리",
        str(exceptions),
    )
    section = substitute(
        section,
        r"^이 (\d+)개는 `node_modules/<pkg>/`",
        "§2 예외 절 본문 서술",
        str(exceptions),
    )
    section = substitute(
        section,
        r"<summary>펼치기 — 나머지 (\d+)개",
        "§2 나머지 머리",
        str(rest),
    )

    # 예외 표는 `<details>` 앞, 나머지 표는 그 안이다 (검사기가 같은 경계로 읽는다).
    head, marker, tail = section.partition("<details>")
    if not marker:
        raise Problem(
            "§2 에 `<details>` 가 없다 — 예외 표와 나머지 표의 경계가 사라졌다"
        )
    head = replace_table(head, "§2 예외 표", table_rows(without_file, scanned, True))
    tail = replace_table(tail, "§2 나머지 표", table_rows(with_file, scanned, True))
    return head + marker + tail, 8


def build(text: str, scanned: dict[str, dict]) -> tuple[str, int]:
    """실측을 반영한 문서 전문과, 갱신한 구간 수."""
    if len(scanned) < MIN_PACKAGES:
        raise Problem(
            f"실측이 {len(scanned)}개다 — 하한 {MIN_PACKAGES} 미만 (스캔 범위가 어긋났다)"
        )
    by_heading, section2_packages = classify(scanned)

    head, sections, order = split_sections(text)
    # 최상단 총계는 **문서 전역에서** 1회여야 한다. 절 안에 같은 문장이 또 생기면 여기서 고친
    # 숫자와 그 문장이 어긋난 채로 남고, 검사기(전역에서 1회를 요구한다)와도 갈린다.
    for pattern, what in (
        (r"프로덕션 의존성 (\d+)개", "최상단 총계"),
        (r"§1·§2 가 그 (\d+)개고", "최상단 총계 재언급"),
    ):
        one(pattern, text, f"{what} (문서 전역)")
        head = substitute(head, pattern, what, str(len(scanned)))

    sections["1"], updated1 = rewrite_section1(sections["1"], by_heading, scanned)
    sections["2"], updated2 = rewrite_section2(
        sections["2"], section2_packages, scanned
    )
    # §3 은 손대지 않는다 — npm 스캔 범위 밖이고, 검사기 축 ④ 가 저장소 파일과 대조한다.
    return head + "".join(sections[key] for key in order), 2 + updated1 + updated2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="갱신하지 않고 대조만 한다 — 어긋나면 실패 (CI 는 이 모드로 돈다)",
    )
    parser.add_argument(
        "--licenses",
        type=Path,
        default=None,
        help="이미 뜬 license-checker 산출물(JSON). 없으면 직접 돌린다",
    )
    parser.add_argument(
        "--notices",
        type=Path,
        default=NOTICES,
        help="대상 문서 (기본: 레포 루트 THIRD-PARTY-NOTICES.md) — 회귀 테스트가 사본을 준다",
    )
    args = parser.parse_args(argv)

    if not args.notices.is_file():
        print(f"::error::{args.notices} 가 없다 — 생성 대상이 사라졌다 (fail-closed)")
        return 1
    current = args.notices.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="generate-notices-") as tmp:
        try:
            if args.licenses is not None:
                scanned = load_scan(args.licenses)
                source = str(args.licenses)
            else:
                scanned = run_scan(Path(tmp) / "licenses-prod.json")
                source = "license-checker (cwd=frontend)"
            rebuilt, updated = build(current, scanned)
        except Problem as error:
            print(f"::error::{error}")
            return 1

    print(f"  · 실측 {len(scanned)}개 ← {source}")
    print(
        f"  · 갱신 대상 구간 {updated}개 (총계 · §1 절 {len(SECTION1_GROUPS)}개 · §2)"
    )

    if rebuilt == current:
        print(f"{args.notices.name} 는 이미 실측과 같습니다 (변경 없음).")
        return 0

    if args.check:
        diff = list(
            difflib.unified_diff(
                current.splitlines(),
                rebuilt.splitlines(),
                f"{args.notices.name} (커밋된 것)",
                "생성기 출력 (실측)",
                lineterm="",
            )
        )
        print(
            f"::error::{args.notices.name} 가 실측과 어긋났습니다 (diff {len(diff)}줄):"
        )
        for line in diff[:40]:
            print(f"::error::  {line[:300]}")
        if len(diff) > 40:
            print(f"::error::  … ({len(diff) - 40}줄 더)")
        print(
            "::error::`python3 scripts/generate_notices.py` 로 다시 만들어 커밋하세요 "
            "(손으로 숫자만 고치지 마세요 — 목록이 어긋난 채 남습니다)."
        )
        return 1

    args.notices.write_text(rebuilt, encoding="utf-8")
    changed = sum(
        1
        for line in difflib.unified_diff(current.splitlines(), rebuilt.splitlines())
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
    print(f"{args.notices.name} 를 갱신했습니다 ({changed}줄 변경).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
