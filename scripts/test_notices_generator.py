"""고지 문서 생성기의 fail-closed 축을 케이스로 못박는다 — `generate_notices.py` 회귀 그물.

## 왜 있나

생성기가 초록인 것은 두 가지를 뜻할 수 있다: 「문서가 실측과 같다」 **또는** 「생성기가
아무것도 안 봤다」. 실제로 이 레포가 반복해 데인 자리가 그 둘의 구분이 없는 상태다.
생성기는 특히 위험하다 — 앵커(치환 자리)가 문장 변경으로 조용히 0건이 되면 「갱신했다」면서
한 글자도 안 고친 채 통과한다. 그 순간 생성기는 자기가 없애려던 손유지 상태로 되돌아간다.

그래서 **무엇을 막는지**를 케이스로 고정한다. exit 0 만으로는 증명이 안 된다.

## 무엇을 파나

  · 라운드트립·멱등 — 생성한 문서를 다시 넣으면 변화가 없다
  · 의존성 변경 반영 — 버전 상승(dependabot PR 이 만드는 그 모양)·추가·삭제
  · 사람 산문 보존 — §3 전체와 각 절의 설명 문장이 **바이트 그대로** 남는다
  · 검사기와의 교차 대조 — 생성한 문서를 `verify_notice_counts.py` 가 다시 파싱해 실측과 맞는다
  · fail-closed — 분류표에 없는 라이선스 · 0건이 된 §1 절 · 원문 파일 없는 Apache 패키지 ·
    앵커 파손(0회·2회 매치) · 하한 미만 실측 · `--check` 의 어긋남 탐지

**픽스처는 실측 스캔이 아니라 합성이다.** node_modules 없이 도는 stdlib 잡에서 실행되고,
버전 상승·라이선스 종류 같은 축을 실제 레지스트리 상태와 무관하게 직접 만들어 넣기 위함이다.
실제 산출물과의 대조는 CI 의 `generate_notices.py --check`(frontend 잡)가 맡는다.

**fail-closed**: 케이스를 0건 수집하면 실패한다.

    python3 scripts/test_notices_generator.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_notices as gen  # noqa: E402
import verify_notice_counts as checker  # noqa: E402

# 케이스가 이보다 적으면 수집이 깨진 것이다 (fail-closed — 「0건 통과」 방지).
MIN_CASES = 15

# 픽스처에 심는 사람 산문 — 생성기가 건드리면 안 되는 문장.
PROSE_MARK = "사람이 쓴 설명 문장 (생성기 소관 아님)"
SECTION3_MARK = "§3 산문 — 저장소에 직접 커밋된 자산이라 npm 스캔 범위 밖이다"

APACHE_HEADING = gen.APACHE_HEADING


def variant_text(index: int) -> str:
    """변형마다 다른 라이선스 원문 (내용이 다르면 다른 변형으로 묶여야 한다)."""
    return (
        f"Apache License\n   Version 2.0 — fixture variant {index}\n   (본문 {index})"
    )


def make_scan(
    root: Path,
    *,
    apache_variants: int = 10,
    permissive: int = 400,
    exceptions: int = 2,
) -> dict[str, dict]:
    """합성 실측 산출물. licenseFile 은 tmpdir 에 실제로 만든다 (경로 실재가 축이다)."""
    scan: dict[str, dict] = {}

    def add(package: str, license_name: str, body: str | None) -> None:
        entry: dict[str, str] = {"licenses": license_name}
        if body is not None:
            path = root / f"{len(scan)}.LICENSE"
            path.write_text(body, encoding="utf-8")
            entry["licenseFile"] = str(path)
        scan[package] = entry

    # Apache — 변형 1 만 3개 패키지, 나머지는 1개씩 (개수 내림차순 정렬 축을 판다).
    for index in range(apache_variants):
        body = variant_text(index)
        count = 3 if index == 0 else 1
        for member in range(count):
            add(f"apache-{index:02d}-{member}@1.{index}.{member}", "Apache-2.0", body)

    # §1 나머지 절 — 분류표에서 라이선스를 가져온다 (표가 늘면 픽스처도 따라 는다).
    for heading, licenses in gen.SECTION1_GROUPS:
        if heading == APACHE_HEADING:
            continue
        add(f"pkg-{licenses[0].lower().strip('()')[:12]}@2.0.0", licenses[0], "TEXT")

    # §2 permissive — 그중 `exceptions` 개는 원문 파일이 없다 (§2 예외 축).
    for index in range(permissive):
        add(
            f"perm-{index:04d}@0.{index}.0",
            "MIT" if index % 3 else "ISC",
            None if index < exceptions else f"MIT fixture {index}",
        )
    return scan


def make_document() -> str:
    """앵커 문법만 갖춘 최소 문서. 숫자·표 행은 일부러 틀리게 두고 생성기가 채우게 한다."""
    lines = [
        "# 서드파티 라이선스 고지 (픽스처)",
        "",
        "프로덕션 의존성 1개(전이 포함) 를 대상으로 한다. §1·§2 가 그 1개고, §3 은 번들 자산이다.",
        "",
        f"{PROSE_MARK} — 머리말.",
        "",
        "---",
        "",
        "## 1. 고지·확인이 필요한 라이선스",
        "",
    ]
    for heading, _ in gen.SECTION1_GROUPS:
        lines += [heading, ""]
        if heading == APACHE_HEADING:
            lines += [
                "1개 패키지. Apache-2.0 은 재배포 시 사본 동봉 의무가 있다.",
                "",
                f"본문 텍스트 변형 1종({PROSE_MARK})으로 묶는다.",
                "",
                "<details><summary>변형 1 — 1개 패키지: `placeholder@0.0.0`</summary>",
                "",
                "```",
                "placeholder",
                "```",
                "</details>",
                "",
            ]
        else:
            lines += [
                f"{PROSE_MARK} — {heading}.",
                "",
                "| 패키지 | 버전 |",
                "|---|---|",
                "| `placeholder` | 0.0.0 |",
                "",
            ]
    lines += [
        "---",
        "",
        "## 2. 그 외 permissive 라이선스 (1개)",
        "",
        f"{PROSE_MARK} — 1개 중 1개는 npm 배포본에 원문을 동봉하고, 1개는 `package.json` 의 "
        "선언만 있다.",
        "",
        "### 예외 — 원문 파일 없이 선언만 있는 패키지 (1개)",
        "",
        "이 1개는 `node_modules/<pkg>/` 안에 LICENSE 류 파일이 없다.",
        "",
        "| 패키지 | 버전 | `package.json` 선언 |",
        "|---|---|---|",
        "| `placeholder` | 0.0.0 | MIT |",
        "",
        "<details><summary>펼치기 — 나머지 1개: 패키지 · 버전 · 라이선스</summary>",
        "",
        "| 패키지 | 버전 | 라이선스 |",
        "|---|---|---|",
        "| `placeholder` | 0.0.0 | MIT |",
        "",
        "</details>",
        "",
        "---",
        "",
        "## 3. 번들 정적 자산 — npm 의존성 아님",
        "",
        SECTION3_MARK,
        "",
        "| 대상 | 파일 수 | 라이선스 |",
        "|---|---|---|",
        "| 폰트 | 9 | SIL OFL 1.1 |",
        "",
    ]
    return "\n".join(lines)


def section3(text: str) -> str:
    return text[text.index("## 3. ") :]


def expect_problem(name: str, run) -> list[str]:
    """Problem 이 나야 하는 케이스. 조용히 성공하면 그것이 실패다."""
    try:
        run()
    except checker.Problem:
        return []
    return [f"{name}: Problem 이 나야 하는데 조용히 성공했다"]


def run_cases() -> tuple[list[str], int]:
    failures: list[str] = []
    cases = 0

    with tempfile.TemporaryDirectory(prefix="notices-fixture-") as tmp:
        root = Path(tmp)
        scan = make_scan(root)
        document = make_document()
        built, updated = gen.build(document, scan)

        # ① 라운드트립 — 실측이 그대로 문서에 박힌다.
        cases += 1
        total = len(scan)
        if (
            f"프로덕션 의존성 {total}개" not in built
            or f"§1·§2 가 그 {total}개고" not in built
        ):
            failures.append(f"① 총계 {total} 이 최상단 두 자리에 박히지 않았다")
        if updated <= 0:
            failures.append(f"① 갱신 구간 수가 {updated} 이다 — 0건은 통과가 아니다")

        # ② 멱등 — 생성한 문서를 다시 넣으면 변화가 없다.
        cases += 1
        again, _ = gen.build(built, scan)
        if again != built:
            failures.append(
                "② 같은 실측으로 두 번 돌렸는데 결과가 달라졌다 (멱등 아님)"
            )

        # ③ 사람 산문 보존 — §3 은 바이트 그대로, 산문 표식도 남는다.
        cases += 1
        if section3(built) != section3(document):
            failures.append("③ §3 이 바뀌었다 — 생성기는 §3 을 건드리면 안 된다")
        if built.count(PROSE_MARK) != document.count(PROSE_MARK):
            failures.append("③ 사람 산문 문장이 사라지거나 늘었다")

        # ④ Apache 변형 묶기 — 원문이 같은 것끼리, 개수 내림차순.
        cases += 1
        if "본문 텍스트 변형 10종" not in built:
            failures.append("④ 변형 종수가 10종으로 적히지 않았다")
        if "<details><summary>변형 1 — 3개 패키지:" not in built:
            failures.append("④ 변형 1(3개 패키지)이 개수 내림차순 맨 앞에 오지 않았다")
        if variant_text(5) not in built:
            failures.append("④ 변형 본문이 실측 원문에서 실리지 않았다")

        # ⑤ 검사기 교차 대조 — 생성한 문서를 검사기가 다시 파싱해 실측과 맞는다.
        cases += 1
        declared, exceptions, _ = checker.parse_document(built)
        if declared != set(scan):
            missing = sorted(set(scan) - declared)[:3]
            failures.append(f"⑤ 검사기가 읽은 집합이 실측과 다르다 (예: {missing})")
        if exceptions != {"perm-0000@0.0.0", "perm-0001@0.1.0"}:
            failures.append(f"⑤ §2 예외 집합이 어긋난다: {sorted(exceptions)}")

        # ⑥ 버전 상승 (dependabot PR 이 만드는 그 모양) — 행이 갈리고 총계는 그대로다.
        cases += 1
        bumped = dict(scan)
        entry = bumped.pop("perm-0100@0.100.0")
        bumped["perm-0100@0.200.0"] = entry
        bumped_doc, _ = gen.build(built, bumped)
        if "| `perm-0100` | 0.200.0 |" not in bumped_doc:
            failures.append("⑥ 올라간 버전이 표에 반영되지 않았다")
        if "| `perm-0100` | 0.100.0 |" in bumped_doc:
            failures.append("⑥ 옛 버전 행이 남았다")
        if f"프로덕션 의존성 {total}개" not in bumped_doc:
            failures.append("⑥ 버전만 올랐는데 총계가 흔들렸다")

        # ⑦ 패키지 추가·삭제 — 총계·§2 선언 숫자가 함께 움직인다.
        cases += 1
        grown = dict(scan)
        grown["perm-9999@9.9.9"] = {
            "licenses": "MIT",
            "licenseFile": str(root / "0.LICENSE"),
        }
        grown_doc, _ = gen.build(built, grown)
        if f"프로덕션 의존성 {total + 1}개" not in grown_doc:
            failures.append("⑦ 추가된 패키지가 총계에 반영되지 않았다")
        if f"## 2. 그 외 permissive 라이선스 ({400 + 1}개)" not in grown_doc:
            failures.append("⑦ §2 머리 개수가 따라오지 않았다")

        # ⑧ §2 예외 축 — 원문 파일이 사라진 패키지가 예외 표로 옮겨진다.
        cases += 1
        lost = {k: dict(v) for k, v in scan.items()}
        lost["perm-0200@0.200.0"].pop("licenseFile")
        lost_doc, _ = gen.build(built, lost)
        if "원문 파일 없이 선언만 있는 패키지 (3개)" not in lost_doc:
            failures.append("⑧ 예외 개수가 3개로 갱신되지 않았다")
        if "이 3개는 `node_modules/<pkg>/`" not in lost_doc:
            failures.append("⑧ 예외 절 본문 서술의 숫자가 따라오지 않았다")

        # ⑨ fail-closed — 분류표에 없는 라이선스는 §2 로 흘려보내지 않는다.
        cases += 1
        unknown = dict(scan)
        unknown["copyleft@1.0.0"] = {
            "licenses": "GPL-3.0-only",
            "licenseFile": str(root / "0.LICENSE"),
        }
        failures += expect_problem(
            "⑨ 미분류 라이선스", lambda: gen.build(built, unknown)
        )

        # ⑩ fail-closed — §1 절 하나가 0건이 되면 빈 절을 만들지 않고 멈춘다.
        cases += 1
        dropped = {k: v for k, v in scan.items() if v["licenses"] != "MPL-2.0"}
        failures += expect_problem("⑩ §1 절 0건", lambda: gen.build(built, dropped))

        # ⑪ fail-closed — Apache 패키지의 원문 파일이 없으면 본문 없이 만들지 않는다.
        cases += 1
        nofile = {k: dict(v) for k, v in scan.items()}
        nofile["apache-00-0@1.0.0"]["licenseFile"] = str(root / "does-not-exist")
        failures += expect_problem(
            "⑪ Apache 원문 부재", lambda: gen.build(built, nofile)
        )

        # ⑫ fail-closed — 앵커가 0회 매치(문장이 바뀜)면 조용히 통과하지 않는다.
        cases += 1
        broken = built.replace("프로덕션 의존성", "프로덕션 디펜던시", 1)
        failures += expect_problem("⑫ 앵커 0회", lambda: gen.build(broken, scan))

        # ⑬ fail-closed — 앵커가 2회 매치(문장 중복)여도 멈춘다. 어느 쪽을 고칠지 모른다.
        cases += 1
        doubled = built.replace(
            "### 예외 — 원문 파일 없이 선언만 있는 패키지",
            "원문 파일 없이 선언만 있는 패키지 (9개)\n\n"
            "### 예외 — 원문 파일 없이 선언만 있는 패키지",
            1,
        )
        failures += expect_problem(
            "⑬ 앵커 2회(절 안)", lambda: gen.build(doubled, scan)
        )

        # ⑬-b 절 밖의 중복도 잡는다 — 총계는 문서 전역에서 1회여야 한다. 절 안에 같은 문장이
        # 또 생기면 최상단만 갱신되고 그 문장은 낡은 숫자로 남는다(검사기와도 갈린다).
        cases += 1
        echoed = built.replace(
            "## 3. 번들 정적 자산", "프로덕션 의존성 1개\n\n## 3. 번들 정적 자산", 1
        )
        failures += expect_problem(
            "⑬-b 앵커 2회(절 밖)", lambda: gen.build(echoed, scan)
        )

        # ⑭ fail-closed — 실측이 하한 미만이면 스캔 범위가 어긋난 것이다.
        cases += 1
        tiny = dict(list(scan.items())[:10])
        failures += expect_problem("⑭ 실측 하한", lambda: gen.build(built, tiny))

        # ⑮ `--check` — 어긋나면 1, 같으면 0. 그리고 **문서를 고치지 않는다**.
        cases += 1
        target = root / "NOTICES-under-test.md"
        licenses = root / "scan.json"
        licenses.write_text(json.dumps(scan), encoding="utf-8")
        target.write_text(
            built.replace("| `perm-0300` | 0.300.0 |", "| `perm-0300` | 9.9.9 |"),
            encoding="utf-8",
        )
        before = target.read_text(encoding="utf-8")
        argv = ["--check", "--licenses", str(licenses), "--notices", str(target)]
        if gen.main(argv) != 1:
            failures.append("⑮ 한 줄 틀린 문서에 --check 가 0 을 냈다")
        if target.read_text(encoding="utf-8") != before:
            failures.append("⑮ --check 가 문서를 고쳤다 (대조만 해야 한다)")
        if gen.main(argv[1:]) != 0:
            failures.append("⑮ 갱신 모드가 0 으로 끝나지 않았다")
        if target.read_text(encoding="utf-8") != built:
            failures.append("⑮ 갱신 모드가 문서를 실측대로 되돌리지 못했다")
        if gen.main(argv) != 0:
            failures.append("⑮ 갱신 뒤 --check 가 여전히 실패한다")

    return failures, cases


def main() -> int:
    failures, cases = run_cases()
    print(f"수집한 케이스 {cases}개 (하한 {MIN_CASES})")
    if cases < MIN_CASES:
        print(
            f"::error::케이스를 {cases}개만 수집했습니다 — 하한 {MIN_CASES} 미만 (fail-closed)"
        )
        return 1
    if failures:
        print(f"\n실패 {len(failures)}건:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(
        "통과 — 생성기는 기계 소관 구간만 갱신하고(§3·산문 보존), 앵커가 깨지거나 분류가 "
        "모자라면 조용히 통과하는 대신 멈춘다"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
