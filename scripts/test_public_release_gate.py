"""공개 배포 게이트 회귀 그물 — #406·PR #409 리뷰가 뚫은 우회가 다시 열리는지 본다.

PR #405 가 만든 게이트를 #406 리뷰가 두 자리에서 뚫었고, 그 수정(PR #409)을 다시 리뷰가
세 자리에서 뚫었다. 전부 **한 줄만 되돌리면 다시 열리는** 종류라, 재현을 사람의 기억이
아니라 실행되는 케이스로 못박는다.

  · ① 인라인 자산 — 텍스트 파일 안 `data:` URI·base64 런에 자산을 실어 파일 단위 검사를
    통째로 건너뛰는 경로 (`verify_public_release_tree.py` 의 (5)).
    - ①-a (#406): 감싸개·mime 위장·확장자별 구멍.
    - ①-b (PR #409 리뷰): **payload 안의 공백**. MIME 76컬럼 wrap 한 줄로 규칙 A·B 가 전부
      뚫렸다 — 브라우저는 공백을 지우고 원본을 되살리는데 정규식만 안 지웠다.
    - ①-c (PR #409 리뷰): **벡터의 바이트 문턱**. 문턱 근거는 래스터 한정인데 SVG 에도 걸려
      상표 로고가 511 B 로 통과했다.
    - ①-e (PR #409 3라운드): **payload 선두에 붙는 바이트**. 판정이 자산의 시작점을
      알아맞히려 해서, UTF-8 BOM·NUL·NEL 같은 바이트 **하나**로 SVG 스니핑이 통째로 죽었다.
      같은 절에서 UTF-16/32 인코딩(문턱 면제가 스니핑 성공에 종속되던 자리)도 함께 판다.
  · ② 원격 자기 지정 — `--remote` 에 개발 레포 자신을 주면 릴리스 커밋이 개발 레포 main 에
    얹히는 경로 (`release_public.py` 의 가드 A·B). PR #409 리뷰가 **FQDN 후행 점**으로 가드 A
    를 통과시켰고, 전수 조사로 `.GIT` 접미·퍼센트 인코딩 경로가 더 나왔다.
  · ④ 목적지 브랜치 (#410) — 릴리스 브랜치를 `main` 으로 박아 두면 공개 레포의 기본 브랜치가
    다른 이름일 때 **아무도 안 보는 브랜치에 쌓이고** 매니페스트가 **엉뚱한 브랜치와의 비교**가
    된다. 로컬 bare 레포 픽스처로 기본 브랜치 이름·0커밋 초기 릴리스·원격 HEAD 부재를 판다.

**픽스처에 base64 리터럴을 적지 않는다.** 검사기 자신도 인라인 스캔 대상이라(예외 없음)
리터럴을 적으면 이 파일이 자기 게이트에 걸린다. 그래서 자산 바이트를 코드로 만들어
실행 시점에 인코딩한다 — 덤으로 매직 넘버 표와 픽스처가 어긋날 수 없다.

**fail-closed**: 케이스를 0건 수집하면 실패한다. 어느 한 케이스라도 기대와 다르면 실패한다.

    python3 scripts/test_public_release_gate.py
"""

from __future__ import annotations

import ast
import base64
import html
import random
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import release_public as rp  # noqa: E402
import verify_public_release_tree as gate  # noqa: E402

# 케이스가 이보다 적으면 수집이 깨진 것이다 (fail-closed — 「0건 통과」 방지).
MIN_INLINE_CASES = 50
MIN_REMOTE_CASES = 38
MIN_DECODE_CASES = 8
# 선두 바이트 표는 **범위로** 판다 (C0 32종 + BOM·유니코드 공백류). 몇 개만 남기고 지우면
# 「하나만 붙여도 통째로 죽는다」는 성질을 다시 놓치므로 하한을 넉넉히 둔다.
MIN_LEAD_CASES = 40
MIN_ENCODING_CASES = 6

# 문턱은 **근거를 적고 고른 값**이라(검사기 독스트링 「인라인 자산」 절) 조용히 움직이면 안 된다.
# 아래 픽스처 크기도 이 값을 기준으로 절대값을 박아 뒀다 — 픽스처를 상수에서 유도하면
# 문턱을 10 MB 로 올려도 픽스처가 같이 커져 **그물이 버그를 따라간다** (실측으로 확인했다).
EXPECTED_MIN_BYTES = 1024

# 공백 집합도 **근거를 적고 고른 값**이다 — WHATWG 가 벗기는 것과 글자 단위로 맞춘 것이라
# `\s` 로 갈아 끼우면(유니코드 공백 포함) 브라우저 동작과 어긋난다. 상수도 절대값으로 박는다.
EXPECTED_B64_STRIP = "\t\n\f\r "  # U+0009 · U+000A · U+000C · U+000D · U+0020
EXPECTED_URL_STRIP = "\t\n\r"  # U+0009 · U+000A · U+000D

# 개행 위치를 난수로 고르되 **씨앗을 박아** 실패가 재현되게 한다.
RANDOM_WRAP_SEED = 406409


class FakeEntry:
    """`check_inline_assets` 가 경로만 읽으므로 그것만 준다."""

    def __init__(self, path: str) -> None:
        self.path = path


def png(size: int) -> bytes:
    """PNG 매직으로 시작하는 `size` 바이트 — 매직 넘버 표에서 직접 가져온다."""
    magic = next((m for m, name in gate.ASSET_MAGICS if name.startswith("PNG")), None)
    if magic is None:
        raise SystemExit("실패: ASSET_MAGICS 에 PNG 항목이 없다 — 매직 넘버 표에서 지워졌다 (#406 ①)")
    return magic + b"\x00" * (size - len(magic))


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


# 벡터 픽스처 — ①(인라인 자산)과 ①-e(선두 바이트·인코딩)가 같은 것을 쓴다. 두 벌로 적으면
# 한쪽만 손대도 두 절이 서로 다른 것을 재게 된다.
SVG_ART = '<svg xmlns="http://www.w3.org/2000/svg">' + '<path d="M0 0h1v1z"/>' * 90 + "</svg>"
SVG_ICON = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M2 8l4 4 8-8"/></svg>'  # 70 B, 문턱 아래

# 퍼센트로 접은 최소 SVG(`<svg/>`). **소스에 실물 표기를 적지 않고 이어 붙인다** — 이 그물
# 파일도 인라인 스캔 대상이라, `data:` URI 뒤에 실물을 적으면 게이트가 자기 픽스처에 걸린다
# (실측으로 그렇게 걸렸다). 조립하면 소스에는 마커가 없고 런타임 값에만 생긴다.
PCT_SVG_TINY = "%3c" + "svg/" + "%3e"


def wrap(text: str, width: int, separator: str = "\n") -> str:
    """`width` 글자마다 `separator` 를 끼운다 (MIME 76 · PEM 64 컬럼 wrap 재현).

    `textwrap` 을 쓰지 않는 이유: 그쪽은 **단어 경계**로 접고 공백을 정규화해서, base64 처럼
    공백 없는 한 덩어리에 무엇을 했는지가 불투명해진다. 여기서는 자른 위치가 곧 테스트 의미다.
    """
    return separator.join(text[i : i + width] for i in range(0, len(text), width))


def wrap_random(text: str, seed: int) -> str:
    """임의 위치(앵커 한가운데 포함)에 개행을 끼운다 — 표준 wrap 폭만 막는 수정을 잡는다."""
    rng = random.Random(seed)
    out: list[str] = []
    index = 0
    while index < len(text):
        step = rng.randint(1, 40)
        out.append(text[index : index + step])
        index += step
    return "\n".join(out)


def inline_cases() -> list[tuple[str, str, bool]]:
    """(이름, 파일 내용, 잡혀야 하나)."""
    banned = png(4096)  # denylist 에 있다고 가정할 자산 (아래에서 해시를 주입한다)
    unknown_big = png(5000)  # 문턱(1 KiB) 위 — 절대값 (위 EXPECTED_MIN_BYTES 주석 참조)
    unknown_small = png(900)  # 문턱 아래
    tiny_icon = png(68)  # 1x1 투명 PNG 크기 — 오차단이 나면 안 되는 자리
    # 매직 표에 없는 바이너리 — D2 앵커가 없어 **D1 만이 유일한 탐지기**인 자리.
    unknown_blob = b"\xfe\xed" + bytes(range(256)) * 5  # UTF-8 로 안 읽힘 = 바이너리, 1282 B
    svg_icon = SVG_ICON
    svg_art = SVG_ART
    # 네임스페이스 접두를 쓴 같은 아트워크 — 접두 이름은 선언만 하면 무엇이든 된다.
    svg_ns = '<n:svg xmlns:n="http://www.w3.org/2000/svg">' + '<n:path d="M0 0h1v1z"/>' * 90 + "</n:svg>"
    prefix = "data:image/png;base64,"
    payload = b64(banned)
    return [
        # ─ ①-a 이슈 재현 (#406): 확장자별로 같은 구멍이 열려 있었다 ─
        (".css 의 data: URI", f'.a{{background:url("{prefix}{payload}")}}', True),
        (".ts 의 문자열 상수", f'export const A = "{prefix}{payload}";', True),
        (".json 의 값", '{"a":"' + prefix + payload + '"}', True),
        (".md 의 이미지 문법", f"![a]({prefix}{payload})", True),
        # ─ ①-a 우회 시도 ─
        (
            "mime 을 text/plain 으로 위장",
            f'x = "data:text/plain;base64,{b64(banned)}"',
            True,
        ),
        ("data: 감싸개 없는 base64 런", f'const BG = "{payload}";', True),
        ("대소문자 뒤섞기", f'x = "DaTa:ImAgE/PnG;BaSe64,{payload}"', True),
        (
            "퍼센트 인코딩 data: URI",
            'x = "data:image/png,' + urllib.parse.quote_from_bytes(unknown_big) + '"',
            True,
        ),
        ("문턱 위 미등록 자산", f'x = "{prefix}{b64(unknown_big)}"', True),
        # ─ ①-b payload 안의 공백 (PR #409 리뷰) — 전부 **denylist 해시로** 잡혀야 한다.
        #   잡히기만 하면 되는 게 아니라 **공백 제거 후 원본과 바이트가 같아야** 규칙 A 가
        #   걸린다. 아래 run_inline_cases() 가 그 해시 일치까지 따로 확인한다.
        (
            "MIME 76컬럼 LF wrap",
            f'.a{{background:url("{prefix}{wrap(payload, 76)}")}}',
            True,
        ),
        (
            "PEM 64컬럼 CRLF wrap",
            f'x = "{prefix}{wrap(payload, 64, chr(13) + chr(10))}"',
            True,
        ),
        (
            "임의 위치 개행 (앵커 한가운데 포함)",
            f'x = "{prefix}{wrap_random(payload, RANDOM_WRAP_SEED)}"',
            True,
        ),
        ("탭 삽입", f'x = "{prefix}{wrap(payload, 40, chr(9))}"', True),
        ("스페이스 삽입", f'x = "{prefix}{wrap(payload, 40, " ")}"', True),
        ("폼피드 삽입", f'x = "{prefix}{wrap(payload, 40, chr(12))}"', True),
        (
            "TS 백틱 템플릿 리터럴 안의 개행",
            f"const BG = `{prefix}{wrap(payload, 76)}`;",
            True,
        ),
        # payload 밖(마임·`;base64,` 표시)의 공백과, 퍼센트로 적은 공백. URL 파서와 퍼센트
        # 디코딩 단계를 안 흉내 내면 여기가 뚫린다 (수정 직후 자체 공격에서 실제로 뚫렸다).
        (
            "마임과 ;base64 사이의 개행",
            f'x = "data:image/png\n;base64,{payload}"',
            True,
        ),
        ("마임 뒤 스페이스", f'x = "data:image/png ;base64,{payload}"', True),
        ("base64 낱말 한가운데 개행", f'x = "data:image/png;bas\ne64,{payload}"', True),
        # 위 셋은 매직 표에 있는 자산이라 D1 이 놓쳐도 D2 앵커가 받는다 — 즉 D1 의 접두부
        # 공백 처리를 되돌려도 그물이 안 울린다. **매직 표 밖 자산**으로 그 자리를 따로 판다.
        (
            "매직 표 밖 자산 + 마임 안 개행 (D2 가 못 받는 자리)",
            f'x = "data:application/octet-stream\n;base64,{b64(unknown_blob)}"',
            True,
        ),
        (
            "매직 표 밖 자산 + base64 낱말 안 개행 (D2 가 못 받는 자리)",
            f'x = "data:application/octet-stream;bas\ne64,{b64(unknown_blob)}"',
            True,
        ),
        (
            "매직 표 밖 자산 + payload 안 %0A (D2 가 못 받는 자리)",
            'x = "data:application/octet-stream;base64,'
            + b64(unknown_blob)[:40]
            + "%0A"
            + b64(unknown_blob)[40:]
            + '"',
            True,
        ),
        ("payload 안의 %0A", f'x = "{prefix}{payload[:40]}%0A{payload[40:]}"', True),
        ("payload 안의 %20", f'x = "{prefix}{payload[:40]}%20{payload[40:]}"', True),
        (
            "감싸개 없는 base64 런 + 76컬럼 wrap",
            f"const BG = `{wrap(payload, 76)}`;",
            True,
        ),
        # 앵커(PNG → `iVBORw0K`, 8글자) 한가운데를 자른다. 표준 wrap 폭은 앵커를 안 자르므로
        # 이 자리를 비워 두면 「앵커를 공백 비관용으로 되돌림」이 그물에 안 걸린다 (뮤테이션 실측).
        (
            "감싸개 없는 런 + 앵커 한가운데 개행",
            f"const BG = `{payload[:4]}\n{payload[4:]}`;",
            True,
        ),
        (
            "감싸개 없는 런 + 임의 위치 개행",
            f"const BG = `{wrap_random(payload, RANDOM_WRAP_SEED)}`;",
            True,
        ),
        (
            "퍼센트 인코딩 payload + 개행",
            'x = "data:image/png,' + wrap(urllib.parse.quote_from_bytes(unknown_big), 76) + '"',
            True,
        ),
        # ─ ①-c 벡터에는 바이트 문턱이 없다 (PR #409 리뷰) ─
        (
            "문턱 위 인라인 SVG 아트워크",
            'x = "data:image/svg+xml,' + urllib.parse.quote(svg_art) + '"',
            True,
        ),
        (
            f"문턱 아래 인라인 SVG ({len(svg_icon)}B — 벡터는 문턱 없음)",
            'x = "data:image/svg+xml,' + urllib.parse.quote(svg_icon) + '"',
            True,
        ),
        # ─ ①-d `data:` 파싱 구간의 「브라우저는 관용적인데 정규식은 엄격한」 자리
        #   (PR #409 kimi CI 리뷰 04:03·04:24 — 세 번 지적되도록 안 닫혔던 자리들).
        #   **전부 매직 표 밖 자산(SVG·비매직 바이너리)으로 판다.** 매직이 있으면 D1 이 놓쳐도
        #   D2 앵커가 받아 「잡힘」이 나오고, 그러면 D1 을 되돌려도 그물이 안 울린다.
        #
        #   ①-d-1 마임·파라미터 구간의 길이 — **상한을 다시 넣으면 여기가 빨간불이다.**
        (
            "마임 파라미터 199자 패딩 (구 200자 상한 경계)",
            'x = "data:image/svg+xml;x=' + "a" * 199 + ";base64," + b64(svg_art.encode()) + '"',
            True,
        ),
        (
            "마임 파라미터 250자 패딩",
            'x = "data:image/svg+xml;x=' + "a" * 250 + ";base64," + b64(svg_art.encode()) + '"',
            True,
        ),
        (
            "마임 파라미터 5000자 패딩 (상한은 상수만 바꿔도 다시 뚫린다)",
            'x = "data:image/svg+xml;x=' + "a" * 5000 + ";base64," + b64(svg_art.encode()) + '"',
            True,
        ),
        (
            "마임 파라미터 패딩 + 매직 표 밖 바이너리",
            'x = "data:application/octet-stream;x=' + "a" * 250 + ";base64," + b64(unknown_blob) + '"',
            True,
        ),
        #   ①-d-2 스킴 키워드 쪼개기 — URL 파서가 URL **전체**에서 tab·LF·CR 를 지운다.
        (
            "스킴 키워드 안 개행 da\\nta:",
            f'x = "da\nta:image/svg+xml;base64,{b64(svg_art.encode())}"',
            True,
        ),
        (
            "스킴 키워드 안 탭",
            f'x = "da\tta:image/svg+xml;base64,{b64(svg_art.encode())}"',
            True,
        ),
        (
            "스킴 키워드 안 CR",
            f'x = "da\rta:image/svg+xml;base64,{b64(svg_art.encode())}"',
            True,
        ),
        (
            "스킴 쪼개기 + 퍼센트 인코딩 판",
            'x = "da\nta:image/svg+xml,' + urllib.parse.quote(svg_art) + '"',
            True,
        ),
        #   ①-d-3 스니핑 창 — XML 은 루트 앞 주석을 크기 제한 없이 허용한다.
        (
            "선두 XML 주석 600 B + SVG (base64)",
            'x = "data:image/svg+xml;base64,' + b64(("<!--" + "p" * 600 + "-->" + svg_art).encode()) + '"',
            True,
        ),
        (
            "선두 XML 주석 600 B + SVG (퍼센트)",
            'x = "data:image/svg+xml,' + urllib.parse.quote("<!--" + "p" * 600 + "-->" + svg_art) + '"',
            True,
        ),
        (
            "<?xml + 주석 5000 B + SVG (구 4096 창 밖)",
            'x = "data:image/svg+xml;base64,'
            + b64(('<?xml version="1.0"?><!--' + "p" * 5000 + "-->" + svg_art).encode())
            + '"',
            True,
        ),
        (
            "DOCTYPE + 주석 + 처리명령을 섞은 프롤로그",
            'x = "data:image/svg+xml;base64,'
            + b64(("<!DOCTYPE svg><!--a--><?pi x?><!--" + "p" * 900 + "-->" + svg_art).encode())
            + '"',
            True,
        ),
        #   ①-d-4 네임스페이스 접두 — 접두 이름은 선언만 하면 무엇이든 되고 브라우저는 렌더한다.
        (
            "네임스페이스 접두 루트 <n:svg>",
            'x = "data:image/svg+xml;base64,' + b64(svg_ns.encode()) + '"',
            True,
        ),
        #   ①-d-5 퍼센트 인코딩하지 않은 원문 SVG — CSS·Tailwind 의 관용 표기다.
        (
            "인코딩 없는 원문 SVG (CSS url())",
            f'.a{{background:url("data:image/svg+xml,{svg_art}")}}',
            True,
        ),
        (
            "인코딩 없는 원문 SVG + 네임스페이스 접두",
            f'.a{{background:url("data:image/svg+xml,{svg_ns}")}}',
            True,
        ),
        # ─ ①-d 의 뒷면 — **브라우저가 못 되살리는 것까지 잡으면 그건 방어가 아니라 오탐이다.**
        #   여기가 통과로 유지돼야 「WHATWG 와 글자 단위로 맞췄다」가 참이다 (안 벗기는 것까지).
        #   URL 파서는 SPACE·FF 를 **안 지우고** 퍼센트 인코딩으로 남긴다 → 스킴·표시가 깨진다.
        (
            "스킴 안 SPACE — 브라우저도 못 되살린다 (통과)",
            'x = "da ta:image/svg+xml;base64,' + b64(svg_art.encode()) + '"',
            False,
        ),
        (
            "스킴 안 폼피드 — 못 되살린다 (통과)",
            'x = "da\fta:image/svg+xml;base64,' + b64(svg_art.encode()) + '"',
            False,
        ),
        (
            "`base64` 낱말 안 SPACE — 표시가 깨진다 (통과)",
            'x = "data:image/svg+xml;bas e64,' + b64(svg_art.encode()) + '"',
            False,
        ),
        (
            "`base64` 낱말 안 폼피드 — %0C 로 남는다 (통과)",
            'x = "data:image/svg+xml;bas\fe64,' + b64(svg_art.encode()) + '"',
            False,
        ),
        # 마커가 **아예 없는** XML 은 벡터가 아니다 — 판정을 넓혀도(아래 ①-e) 여기는 통과다.
        (
            "선두 주석 + SVG 아닌 XML 루트 (통과)",
            'x = "data:application/xml;base64,'
            + b64(("<!--" + "p" * 600 + "--><rss><item>" + "x" * 1500 + "</item></rss>").encode())
            + '"',
            False,
        ),
        # 판정이 마커의 **위치를 안 보게** 된 뒤로 잡히는 자리 (PR #409 3라운드). 루트가 svg 가
        # 아니고 마커가 선두 512 B 밖이라 종전에는 둘 다 놓쳤다 — 브라우저는 그대로 렌더한다.
        (
            "HTML 래퍼 + 1000 B 패딩 뒤에 박힌 SVG 아트워크",
            'x = "data:text/html;base64,'
            + b64(("<html><head><!--" + "q" * 1000 + "--></head><body>" + svg_art + "</body></html>").encode())
            + '"',
            True,
        ),
        # ─ 오차단이 나면 안 되는 자리 (문턱의 존재 이유 — 래스터 한정) ─
        (
            "문턱 아래 래스터 (통과해야 정상)",
            f'x = "{prefix}{b64(unknown_small)}"',
            False,
        ),
        ("1x1 픽셀 크기 아이콘 (통과)", f'x = "{prefix}{b64(tiny_icon)}"', False),
        (
            "자산이 아닌 긴 base64 (통과)",
            'x = "' + b64(b"not an asset " * 200) + '"',
            False,
        ),
        (
            "wrap 된 자산 아닌 긴 base64 (통과)",
            'x = "' + wrap(b64(b"not an asset " * 200), 76) + '"',
            False,
        ),
        # 정규식의 `{16,}` 는 공백까지 센다 — 공백을 뺀 실제 글자 수로 재지 않으면 여기가 뚫린다.
        (
            "공백이 대부분인 짧은 payload (통과)",
            f'x = "{prefix}{wrap("QUJDRUZHSUo", 1)}"',
            False,
        ),
        # ─ ①-g 페이로드를 컨테이너 경계까지 넓힌 자리의 양면 (PR #409 4라운드) ─
        #
        # 앞면 — **하한을 다시 넣으면 여기가 빨간불이다.** 퍼센트로 접은 SVG 는 10글자로도
        # 성립하는데, 종전의 16자 하한은 「첫 리터럴 공백이 16자 안에 오느냐」라는 표기의
        # 우연이 탐지를 가르던 두 번째 자리였다 (첫 자리는 페이로드 문자군 열거).
        (
            "퍼센트로 접은 짧은 SVG (하한을 넣으면 놓친다)",
            f'x = url("data:image/svg+xml,{PCT_SVG_TINY}")',
            True,
        ),
        # 뒷면 — **컨테이너 안에 콤마가 있어야 한다.** 문서·주석의 인라인 코드 조각
        # (백틱으로 감싼 `data:`)이 한참 뒤의 무관한 콤마와 짝지어지면, 그 사이 산문이 통째로
        # 페이로드가 되어 산문 속 `<svg` 가 벡터로 잡힌다 (이 조건이 없을 때 실제 트리에서
        # 오탐 위반 1건이 났다 — 이 파일 자신이었다).
        # 백스톱 — 여는 따옴표가 없는데 **공백은 담는** 자리(YAML·TOML 평문 스칼라 등)는
        # 컨테이너를 알아볼 수 없어 보수적 문자군으로 끊긴다. 원문 `<svg` 앵커가 그 자리를 받는다.
        # (마커를 `%3c` 로 적으면 이 자리는 여전히 뚫린다 — 검사기 「못 막는 것」에 적었다.)
        (
            "따옴표 없는 자리의 원문 SVG (백스톱)",
            "logo: data:image/svg+xml," + svg_art,
            True,
        ),
        (
            "백틱 코드 조각 `data:` + 뒤쪽 무관한 콤마 (통과)",
            "# `data:` URI 를 설명하는 주석이다. 아래는 예시 마크업,\n"
            "# <svg xmlns='http://www.w3.org/2000/svg'><path d='M0 0h9v9z'/></svg> `끝`\n",
            False,
        ),
    ]


# 아래 케이스는 **규칙 A(정확 해시)로** 잡혀야 한다. 「잡히기만 하면 통과」로 두면, 공백을
# 안 벗겨 바이트가 어긋난 채 규칙 B(미등록 자산)로 걸리는 상태를 초록으로 읽는다 — 그러면
# 「아는 제거 대상은 크기 무관으로 잡는다」는 규칙 A 의 보장이 죽은 것을 그물이 못 본다.
BY_DENYLIST = frozenset(
    {
        ".css 의 data: URI",
        ".ts 의 문자열 상수",
        ".json 의 값",
        ".md 의 이미지 문법",
        "mime 을 text/plain 으로 위장",
        "data: 감싸개 없는 base64 런",
        "대소문자 뒤섞기",
        "MIME 76컬럼 LF wrap",
        "PEM 64컬럼 CRLF wrap",
        "임의 위치 개행 (앵커 한가운데 포함)",
        "탭 삽입",
        "스페이스 삽입",
        "폼피드 삽입",
        "TS 백틱 템플릿 리터럴 안의 개행",
        "마임과 ;base64 사이의 개행",
        "마임 뒤 스페이스",
        "base64 낱말 한가운데 개행",
        "payload 안의 %0A",
        "payload 안의 %20",
        "감싸개 없는 base64 런 + 76컬럼 wrap",
        "감싸개 없는 런 + 앵커 한가운데 개행",
        "감싸개 없는 런 + 임의 위치 개행",
    }
)
DENYLIST_MARKER = "제거 대상 blob 이 인라인으로 재유입"


def run_inline_cases() -> list[str]:
    failures: list[str] = []
    if gate.INLINE_ASSET_MIN_BYTES != EXPECTED_MIN_BYTES:
        failures.append(
            f"① 문턱이 {gate.INLINE_ASSET_MIN_BYTES}B 로 바뀌었다 (기대 {EXPECTED_MIN_BYTES}B) — "
            "근거를 적고 고른 값이다. 바꿀 이유가 있으면 검사기 독스트링의 근거와 이 상수를 "
            "같이 갱신하라"
        )
    for label, actual, expected in (
        ("base64", gate.B64_STRIP_CHARS, EXPECTED_B64_STRIP),
        ("퍼센트 인코딩", gate.URL_STRIP_CHARS, EXPECTED_URL_STRIP),
    ):
        if actual != expected:
            failures.append(
                f"① {label} 공백 집합이 {actual!r} 로 바뀌었다 (기대 {expected!r}) — "
                "WHATWG 가 벗기는 것과 글자 단위로 맞춘 값이다. `\\s` 로 갈아 끼우면 "
                "유니코드 공백까지 먹어 브라우저 동작과 어긋난다"
            )
    if gate.has_size_threshold(gate.SVG_ASSET_KIND):
        failures.append(
            "① 벡터에 바이트 문턱이 되살아났다 — 문턱 근거는 래스터 한정이다 "
            "(511 B 상표 로고가 통과한 자리, PR #409 리뷰 ②)"
        )

    # 줄 번호는 개행 위치 색인으로 계산한다 (후보가 늘면 `count("\n", 0, …)` 가 2차가 되므로).
    # 색인의 경계가 어긋나면 위반이 **엉뚱한 줄**로 보고되고, 그건 위반 유무로는 안 보인다.
    probe = f'\n\nx = url("data:image/svg+xml,{PCT_SVG_TINY}")\n'
    reported = gate.check_inline_assets(FakeEntry("probe"), probe)
    if len(reported) != 1 or not reported[0].startswith("probe:3:"):
        failures.append(f"① 줄 번호 보고가 어긋났다 — 기대 «probe:3:» 1건 · 실제 {reported}")

    cases = inline_cases()
    if len(cases) < MIN_INLINE_CASES:
        return [f"① 케이스 {len(cases)}건 — 하한 {MIN_INLINE_CASES} 미만 (수집이 깨졌다)"]
    names = {name for name, _text, _catch in cases}
    missing = BY_DENYLIST - names
    if missing:  # fail-closed — 케이스 이름을 바꾸면 해시 검증이 조용히 사라진다
        failures.append(f"① BY_DENYLIST 의 이름이 케이스에 없다: {sorted(missing)}")

    banned_sha = gate.blob_sha(png(4096))
    saved = dict(gate.DENYLIST_BLOBS)
    gate.DENYLIST_BLOBS[banned_sha] = "테스트 픽스처 — 제거 대상 자산 대역"
    denylist_checked = 0
    try:
        for name, text, should_catch in cases:
            found = gate.check_inline_assets(FakeEntry("probe"), text)
            caught = bool(found)
            if caught != should_catch:
                want = "잡힘" if should_catch else "통과"
                got = "잡힘" if caught else "통과"
                failures.append(f"① {name}: 기대 {want} · 실제 {got}")
                continue
            if name in BY_DENYLIST:
                denylist_checked += 1
                if not any(DENYLIST_MARKER in v for v in found):
                    failures.append(
                        f"① {name}: 규칙 A(정확 해시)로 안 잡혔다 — 디코드 결과가 원본 "
                        f"바이트와 어긋났다는 뜻이다. 실제 위반: {found[0]}"
                    )
    finally:
        gate.DENYLIST_BLOBS.clear()
        gate.DENYLIST_BLOBS.update(saved)
    if denylist_checked != len(BY_DENYLIST):
        failures.append(
            f"① 규칙 A 해시 검증 {denylist_checked}건 — 기대 {len(BY_DENYLIST)}건 "
            "(케이스가 앞에서 실패해 검증이 건너뛰어졌다)"
        )
    print(
        f"  ① 인라인 자산 {len(cases)}건 검사 "
        f"(문턱 {gate.INLINE_ASSET_MIN_BYTES}B · 벡터 면제 · 규칙 A 해시 {denylist_checked}건)"
    )
    return failures


# ── ①-e 선두 바이트 — 「자산의 시작점을 알아맞히지 않는가」 (PR #409 3라운드) ─────────────
# SVG 판정은 두 번 고쳐졌고 **두 번 다 시작점을 알아맞히는 방식이라** 뚫렸다: 선두 512 B 창은
# 루트 앞 주석 한 덩어리로 넘어갔고, 그 처방인 프롤로그 건너뛰기는 계산한 오프셋에서 `<` 를
# **요구**해서 **선두 바이트 하나로 통째로 죽었다** (진입점이 `data.lstrip()` — 파이썬 기본
# ASCII 공백만 벗긴다). UTF-8 BOM·NUL·NEL·NBSP·글자 `x` 하나가 전부 같은 결과를 냈다.
#
# 그래서 여기서는 한 형태를 못박지 않고 **범위로 판다** — C0 제어문자 전 범위 + BOM 3종 +
# 유니코드 공백류. 「무엇을 벗길지 열거하는」 수정이 다시 들어오면 이 표의 어딘가가 반드시
# 빨간불이 난다 (한 종류만 막으면 나머지가 남는다).
#
# 루트 요소를 **창 밖으로 밀어내는** 프롤로그 — 이게 없으면 선두 512 B 창이 받아 버려서
# 선두 바이트 회귀가 관측되지 않는다 (실측: 창 안이면 BOM 이 붙어도 잡힌다).
XML_PROLOGUE = "<!--" + "p" * 600 + "-->"

# 「창을 되돌리는(또는 상수만 키우는) 수정」을 잡는 패딩 크기. 창 방식의 성질은 **얼마로
# 잡든 그만큼 패딩하면 넘어간다**는 것이라, 테스트가 한 크기만 보면 상수를 키우는 수정에
# 조용히 통과를 내준다. 흔한 창 후보(512·4096·65536)를 전부 넘기는 값을 포함시킨다.
PROLOGUE_PADDINGS = [600, 5_000, 70_000, 200_000]

LEADING_BYTES: list[tuple[str, bytes]] = [
    ("UTF-8 BOM", b"\xef\xbb\xbf"),
    ("UTF-16LE BOM", b"\xff\xfe"),
    ("UTF-16BE BOM", b"\xfe\xff"),
    ("UTF-32LE BOM", b"\xff\xfe\x00\x00"),
    ("UTF-32BE BOM", b"\x00\x00\xfe\xff"),
    ("NEL U+0085", "".encode()),
    ("NBSP U+00A0", " ".encode()),
    ("ZWSP U+200B", "​".encode()),
    ("줄구분자 U+2028", " ".encode()),
    ("이데오그래픽 스페이스 U+3000", "　".encode()),
    ("BOM + 개행", b"\xef\xbb\xbf\n"),
    ("자산과 무관한 글자 x", b"x"),
    *[(f"C0 제어문자 \\x{code:02x}", bytes([code])) for code in range(0x20)],
]


def encoding_cases() -> list[tuple[str, bytes, bool]]:
    """(이름, 인라인될 바이트, 잡혀야 하나).

    **전부 문턱(1 KiB) 아래**다 — 그래서 여기서 잡히려면 「벡터에는 문턱이 없다」가 실제로
    걸려야 하고, 그 면제는 `sniff_asset()` 이 벡터로 **알아봤을 때만** 걸린다. 68 B 아이콘을
    UTF-16 으로 인코딩하면 138 B 인데 UTF-8 로 안 읽혀 「바이너리(매직 미상)」로 떨어졌고,
    래스터 문턱이 되살아나 통과했다 (PR #409 3라운드 실측). 이 표가 그 결합을 못박는다.
    """
    icon = SVG_ICON
    return [
        ("UTF-8 (대조군)", icon.encode("utf-8"), True),
        ("UTF-8 + BOM", icon.encode("utf-8-sig"), True),
        ("UTF-16 (BOM 포함)", icon.encode("utf-16"), True),
        ("UTF-16LE (BOM 없음)", icon.encode("utf-16-le"), True),
        ("UTF-16BE (BOM 없음)", icon.encode("utf-16-be"), True),
        ("UTF-32 (BOM 포함)", icon.encode("utf-32"), True),
        ("UTF-32BE (BOM 없음)", icon.encode("utf-32-be"), True),
        # ─ 여기부터는 **못 알아보는 것**을 못박는다 (기대값 = 통과). 검사기 독스트링
        #   「못 막는 것」의 해당 항목과 짝이다 — 잡히게 되면 좋은 변화이니 문서를 같이 고쳐라.
        #   브라우저가 이 둘을 되살리는지는 검증하지 않았다(환경 없음) — 되살린다면 진짜
        #   우회이므로 그때는 기대값을 뒤집고 문서를 함께 고친다.
        ("EBCDIC(cp037) — 못 알아본다 (통과)", icon.encode("cp037"), False),
        (
            "UTF-7 `+ADw-` 표기 — 못 알아본다 (통과)",
            icon.replace("<", "+ADw-").encode("ascii"),
            False,
        ),
        # ASCII 로 남는 UTF-7 표기는 마커가 살아 있어 잡힌다 — 위 항목과 헷갈리지 않게 못박는다.
        ("UTF-7 (ASCII 그대로) — 잡힌다", icon.encode("utf-7"), True),
    ]


def _inline_forms(payload: bytes) -> list[tuple[str, str]]:
    """같은 바이트를 D1 의 두 경로에 각각 실어 준다 — 둘 다 같은 스니핑을 거친다."""
    return [
        ("base64", 'x = "data:image/svg+xml;base64,' + b64(payload) + '"'),
        (
            "퍼센트",
            'x = "data:image/svg+xml,' + urllib.parse.quote_from_bytes(payload) + '"',
        ),
    ]


def run_leading_byte_cases() -> list[str]:
    failures: list[str] = []
    if len(LEADING_BYTES) < MIN_LEAD_CASES:
        return [f"① 선두 바이트 {len(LEADING_BYTES)}건 — 하한 {MIN_LEAD_CASES} 미만 (표가 깎였다)"]
    body = (XML_PROLOGUE + SVG_ART).encode()
    checked = 0
    for name, lead in LEADING_BYTES:
        for form, text in _inline_forms(lead + body):
            checked += 1
            if not gate.check_inline_assets(FakeEntry("probe"), text):
                failures.append(
                    f"① 선두 «{name}» ({form}): 안 잡혔다 — 선두 바이트 하나로 SVG 스니핑이 "
                    "죽는 자리가 되살아났다 (판정이 자산의 시작점을 알아맞히려 하고 있다)"
                )

    for padding in PROLOGUE_PADDINGS:
        payload = ("<!--" + "p" * padding + "-->" + SVG_ART).encode()
        for form, text in _inline_forms(payload):
            checked += 1
            if not gate.check_inline_assets(FakeEntry("probe"), text):
                failures.append(
                    f"① 프롤로그 패딩 {padding}B ({form}): 안 잡혔다 — 마커를 **창** 안에서만 "
                    "찾는 방식이 되살아났다. 창은 얼마로 잡든 그만큼 패딩하면 넘어간다"
                )

    encodings = encoding_cases()
    if len(encodings) < MIN_ENCODING_CASES:
        failures.append(f"① 인코딩 {len(encodings)}건 — 하한 {MIN_ENCODING_CASES} 미만")
    for name, payload, should_catch in encodings:
        if len(payload) >= gate.INLINE_ASSET_MIN_BYTES:
            failures.append(
                f"① 인코딩 «{name}»: 픽스처가 {len(payload)}B 로 문턱 위다 — 문턱 면제를 "
                "안 거치므로 이 케이스가 재는 것이 사라진다"
            )
            continue
        for form, text in _inline_forms(payload):
            checked += 1
            caught = bool(gate.check_inline_assets(FakeEntry("probe"), text))
            if caught != should_catch:
                want = "잡힘" if should_catch else "통과"
                failures.append(f"① 인코딩 «{name}» ({form}): 기대 {want} · 실제 {'잡힘' if caught else '통과'}")
    print(
        f"  ① 선두 바이트 {len(LEADING_BYTES)}종 · 프롤로그 패딩 {len(PROLOGUE_PADDINGS)}종"
        f"(최대 {max(PROLOGUE_PADDINGS):,}B) · 인코딩 {len(encodings)}종 을 "
        f"D1 두 경로(base64·퍼센트)에 실어 {checked}건 검사"
    )
    return failures


# ── ①-f 표기 전수 — 「어느 표기로 적었느냐」가 탐지를 가르지 않는가 (PR #409 4라운드) ──────
# 앞 세 라운드는 매번 **벗길 것·볼 것을 열거**하는 방식으로 고쳤고, 매번 열거 밖이 남았다.
# 4라운드가 뚫린 자리가 그 전형이다 — CSS 가 SVG 를 인라인하는 표준 관용구(여는 태그만
# `%3c` + `svg` 로 적고 이어지는 `xmlns='…'` 의 공백·작은따옴표는 리터럴로 두는 표기)가
# 세 갈래 어디에도 안 들어왔다. 탐지 여부를 가른 것은 **첫 리터럴 공백이 16자 안에 오느냐**
# 라는 표기의 우연이었다. (실물 예시는 적지 않는다 — 이 파일도 인라인 스캔 대상이다.)
#
# 그래서 이 절은 케이스를 손으로 적지 않고 **축의 곱**으로 만든다. 축을 하나 지우면 건수가
# 하한 아래로 떨어져 그물이 먼저 운다:
#
#   컨테이너 9 × 마커·페이로드 인코딩 7 × 공백 표기 5  (컨테이너가 물리적으로 못 담는 조합 제외)
#
# **판정 기준은 「브라우저가 되살리는가」다** — 이 게이트가 스스로 그은 선(모듈 독스트링
# 「㉯ base64·퍼센트 인코딩만 본다」)이 그것이기 때문이다. 되살리는데 안 잡히면 실패,
# 못 살리는데 잡히는 것은 **릴리스를 멈추는 방향**이라 실패로 치지 않는다.
MIN_NOTATION_CASES = 200

# 구조 공백 자리표시 — 인코딩을 적용한 **뒤** 실제 공백 표기로 바꾼다 (인코더가 자리표시를
# 건드리지 않아야 「마커만 퍼센트, 공백은 리터럴」 같은 혼합 표기를 정확히 만들 수 있다).
NOTATION_WS = "\x01"


def notation_body(quote: str) -> str:
    """로고급 벡터 (디코드 ~200 B) — 속성 따옴표를 컨테이너에 맞춰 바꾼다."""
    return (
        f"<svg{NOTATION_WS}xmlns={quote}http://www.w3.org/2000/svg{quote}"
        f"{NOTATION_WS}viewBox={quote}0{NOTATION_WS}0{NOTATION_WS}32{NOTATION_WS}32{quote}>"
        f"<path{NOTATION_WS}d={quote}M16{NOTATION_WS}2{NOTATION_WS}L30{NOTATION_WS}30"
        f"{NOTATION_WS}L2{NOTATION_WS}30{NOTATION_WS}Z{NOTATION_WS}M8{NOTATION_WS}20"
        f"{NOTATION_WS}h16{quote}{NOTATION_WS}fill={quote}none{quote}"
        f"{NOTATION_WS}stroke={quote}#123456{quote}/></svg>"
    )


# (이름, 인코더, 마임에 붙는 표시, 리드 결정으로 열어 둔 언어 층인가)
NOTATION_ENCODINGS: list[tuple[str, object, str, bool]] = [
    ("리터럴 <svg", lambda b: b, "", False),
    (
        "%3csvg (마커만 퍼센트)",
        lambda b: b.replace("<", "%3c").replace(">", "%3e"),
        "",
        False,
    ),
    ("%3Csvg (대문자)", lambda b: b.replace("<", "%3C").replace(">", "%3E"), "", False),
    ("전부 퍼센트", lambda b: urllib.parse.quote(b, safe=NOTATION_WS), "", False),
    (
        "%3c%73vg (마커 내부까지 퍼센트)",
        lambda b: b.replace("<svg", "%3c%73vg").replace("</svg", "%3c%2f%73vg").replace("<", "%3c").replace(">", "%3e"),
        "",
        False,
    ),
    ("base64", lambda b: b64(b.replace(NOTATION_WS, " ").encode()), ";base64", False),
    # ㉮-1 언어 층 — HTML 파서가 푸는 엔티티다. 리드 결정으로 **열어 둔** 계층이라 기대값이
    # 「안 잡힘」이다 (③ 절과 같은 방향). 누가 막으면 여기가 빨간불이 나고, 그때 독스트링과
    # 릴리스 문서의 「못 막는 것」을 같이 갱신하게 된다.
    (
        "&lt;svg (HTML 엔티티)",
        lambda b: b.replace("<", "&lt;").replace(">", "&gt;"),
        "",
        True,
    ),
]

# (이름, 공백 표기, URL 파서가 지워서 마크업이 깨지는가)
NOTATION_WHITESPACE: list[tuple[str, str, bool]] = [
    ("리터럴 SPACE", " ", False),
    ("%20", "%20", False),
    ("개행 LF", "\n", True),
    ("탭 TAB", "\t", True),
    ("복귀 CR", "\r", True),
]

# (이름, 앞 조각, 뒤 조각, 페이로드가 담을 수 없는 글자, 공백을 담을 수 있는가, HTML 파서가 있는가)
NOTATION_CONTAINERS: list[tuple[str, str, str, str, bool, bool]] = [
    (
        'CSS url("…")',
        '.a{{background:url("data:image/svg+xml{m},',
        '")}}',
        '"',
        True,
        False,
    ),
    (
        "CSS url('…')",
        ".a{{background:url('data:image/svg+xml{m},",
        "')}}",
        "'",
        True,
        False,
    ),
    # 여는 따옴표와 `data:` 사이의 공백 — URL 파서가 입력의 앞뒤 C0·SPACE 를 벗기므로
    # 브라우저는 정상으로 읽는다. 이 한 줄이 `_CONTAINER_GAP_CHARS` 를 못박는다
    # (비우면 여는 글자를 못 알아보고 공백에서 끊긴다).
    (
        'CSS url("␣␣…")',
        '.a{{background:url("  data:image/svg+xml{m},',
        '")}}',
        '"',
        True,
        False,
    ),
    (
        "CSS url(…) 따옴표 없음",
        ".a{{background:url(data:image/svg+xml{m},",
        ")}}",
        "'\" ()\t\n\r",
        False,
        False,
    ),
    ('JS "…"', 'const L = "data:image/svg+xml{m},', '";', '"', True, False),
    ("JS '…'", "const L = 'data:image/svg+xml{m},", "';", "'", True, False),
    ("JS 템플릿 `…`", "const L = `data:image/svg+xml{m},", "`;", "`", True, False),
    ('JSX 속성 src="…"', '<img src="data:image/svg+xml{m},', '" />', '"', True, True),
    (
        'JSX 식 src={{"…"}}',
        '<img src={{"data:image/svg+xml{m},',
        '"}} />',
        '"',
        True,
        True,
    ),
    # 컨테이너가 없으면 URL 토큰 자체가 성립하지 않는다 (따옴표 없는 URL·HTML 속성은
    # 공백에서 끝난다) — 브라우저가 못 되살리므로 「잡혀야 한다」의 대상이 아니다.
    (
        "컨테이너 없음(산문)",
        "예시: data:image/svg+xml{m},",
        " 끝",
        "'\" \t\n\r",
        False,
        False,
    ),
]


def notation_cases() -> list[tuple[str, str, bool, bool]]:
    """(이름, 파일 내용, 브라우저가 되살리는가, 리드 결정으로 열어 둔 층인가)."""
    cases: list[tuple[str, str, bool, bool]] = []
    for (
        c_name,
        prefix,
        suffix,
        forbidden,
        holds_space,
        html_parser,
    ) in NOTATION_CONTAINERS:
        for e_name, encode, marker, language_layer in NOTATION_ENCODINGS:
            for w_name, ws_text, url_parser_eats in NOTATION_WHITESPACE:
                quote = "'" if "'" not in forbidden else '"'
                payload = encode(notation_body(quote)).replace(NOTATION_WS, ws_text)
                if any(ch in payload for ch in forbidden):
                    continue  # 그 컨테이너가 물리적으로 못 담는 조합
                text = prefix.format(m=marker) + payload + suffix
                # 브라우저가 되살리는가 — 근거는 세 가지뿐이고 전부 표기의 물리다.
                restorable = True
                if not holds_space and ws_text in (" ", "\n", "\t", "\r"):
                    restorable = False  # 따옴표 없는 URL 토큰은 공백을 담지 못한다
                elif marker != ";base64" and url_parser_eats:
                    # URL 파서가 URL 전체에서 tab·LF·CR 를 지운다 → `<svgxmlns=…` 가 된다.
                    # base64 본문은 공백이 무의미해 해당 없다.
                    restorable = False
                elif ws_text in ("\n", "\r") and "템플릿" not in c_name:
                    restorable = False  # CSS·JS 문자열은 이스케이프 없는 실제 개행을 못 담는다
                elif language_layer and not html_parser:
                    restorable = False  # 엔티티는 HTML 파서가 있는 자리에서만 풀린다
                cases.append(
                    (
                        f"{c_name} · {e_name} · {w_name}",
                        text,
                        restorable,
                        language_layer,
                    )
                )
    return cases


def run_notation_cases() -> list[str]:
    failures: list[str] = []
    cases = notation_cases()
    if len(cases) < MIN_NOTATION_CASES:
        return [
            f"①-f 표기 케이스 {len(cases)}건 — 하한 {MIN_NOTATION_CASES} 미만 "
            "(축이 지워졌다: 컨테이너·인코딩·공백 표 중 하나)"
        ]
    must_catch = open_layer = overreach = 0
    for name, text, restorable, language_layer in cases:
        caught = bool(gate.check_inline_assets(FakeEntry("probe"), text))
        if restorable and not language_layer:
            must_catch += 1
            if not caught:
                failures.append(
                    f"①-f «{name}»: 브라우저가 되살리는 표기인데 게이트가 못 잡는다 — 탐지가 표기의 우연에 걸린 자리다"
                )
        elif language_layer and restorable:
            open_layer += 1
            if caught:
                failures.append(
                    f"①-f «{name}»: 리드 결정으로 **열어 둔** 언어 층(㉮-1)이 잡혔다 — "
                    "막은 것 자체는 좋을 수 있지만, 검사기 독스트링 「못 막는 것」과 "
                    ".docs/6-도구/공개배포-릴리스.md 를 같이 갱신해야 한다"
                )
        elif caught:
            overreach += 1
    print(
        f"  ①-f 표기 전수 {len(cases)}건 검사 "
        f"(컨테이너 {len(NOTATION_CONTAINERS)} × 인코딩 {len(NOTATION_ENCODINGS)} × "
        f"공백 {len(NOTATION_WHITESPACE)}) — 복원 가능 {must_catch}건 전부 잡힘 · "
        f"열어 둔 언어 층 {open_layer}건 그대로 통과 · 과검출 {overreach}건(릴리스를 멈추는 방향)"
    )
    return failures


def decode_cases() -> list[tuple[str, str, bytes | None]]:
    """(이름, payload 표기, 기대 디코드 결과). `None` 은 「받지 않아야 한다」.

    위반 판정보다 한 층 아래를 직접 못박는다 — **공백을 벗긴 뒤 디코드한 결과가 원본과
    바이트 단위로 같아야** 규칙 A(정확 해시)가 성립하기 때문이다. 하한 검사처럼 위반 층에서는
    관측되지 않는(= 오탐만 늘리는) 동작도 여기서만 고정할 수 있다.
    """
    raw = png(300)
    payload = b64(raw)
    return [
        ("공백 없음", payload, raw),
        ("76컬럼 LF wrap", wrap(payload, 76), raw),
        ("64컬럼 CRLF wrap", wrap(payload, 64, "\r\n"), raw),
        ("임의 위치 개행", wrap_random(payload, RANDOM_WRAP_SEED), raw),
        ("탭 삽입", wrap(payload, 40, "\t"), raw),
        ("스페이스 삽입", wrap(payload, 40, " "), raw),
        ("폼피드 삽입", wrap(payload, 40, "\x0c"), raw),
        ("모든 글자 사이 개행", wrap(payload, 1), raw),
        # 퍼센트 디코딩을 base64 디코딩보다 먼저 하지 않으면 여기가 깨진다 (브라우저 순서).
        ("퍼센트로 적은 개행 %0A", payload[:40] + "%0A" + payload[40:], raw),
        ("퍼센트로 적은 스페이스 %20", payload[:40] + "%20" + payload[40:], raw),
        # 통째로 `%` 를 허용하면 이것까지 삼켜 디코드가 깨진다 — `%XX` 형태만 받는다.
        ("`%XX` 가 아닌 `%` 는 안 받는다", payload[:40] + "%ZZ" + payload[40:], None),
        # 공백을 뺀 실제 글자 수로 하한을 재지 않으면 여기가 통과한다 (정규식의 `{16,}` 는
        # 공백까지 센다). 위반 층에서는 관측되지 않는 자리라 여기서 못박는다.
        ("공백 뺀 글자 수가 하한 미만", wrap("QUJDRUZHSUo", 1), None),
        # `\s` 로 갈아 끼우면 이것도 벗겨져 디코드에 성공한다 — 브라우저는 안 벗긴다.
        (
            "유니코드 공백 U+00A0 은 안 벗긴다",
            payload[:20] + "\u00a0" + payload[20:],
            None,
        ),
        (
            "유니코드 줄구분자 U+2028 은 안 벗긴다",
            payload[:20] + "\u2028" + payload[20:],
            None,
        ),
    ]


def run_decode_cases() -> list[str]:
    failures: list[str] = []
    cases = decode_cases()
    if len(cases) < MIN_DECODE_CASES:
        return [f"① 디코드 케이스 {len(cases)}건 — 하한 {MIN_DECODE_CASES} 미만 (수집이 깨졌다)"]
    for name, payload, expected in cases:
        got = gate._decode_b64(payload)
        if got != expected:
            want = "거절" if expected is None else f"원본 {len(expected)}B 와 일치"
            actual = "거절" if got is None else f"{len(got)}B (원본과 {'일치' if got == expected else '불일치'})"
            failures.append(f"① 디코드 «{name}»: 기대 {want} · 실제 {actual}")
    print(f"  ① 공백 제거 후 디코드 {len(cases)}건 검사 (바이트 단위 일치)")
    return failures


# ── ③ 문서화된 우회 — 「지금은 뚫린다」를 고정한다 (PR #409 교차 검증, 리드 결정 ㉡) ────────
# **이 케이스들의 기대값은 「게이트 통과」다. 그게 정답이라서가 아니라, 지금 상태가 그래서다.**
#
# 언어 층 이스케이프(`\n`·`&#10;` 등)로 접은 payload 는 게이트가 못 잡는다 — 소스에는 실제
# 공백이 없지만 런타임에는 생겨서 브라우저가 원본을 복원한다. 리드 결정은 **막지 않고 정직하게
# 적는 것**이었다 (근거: 언어별 이스케이프 문법을 흉내내는 싸움은 끝이 없고, 흉내가 어긋난
# 자리는 조용한 미탐이 되어 지금보다 나쁘다). 정본 서술은 `verify_public_release_tree.py`
# 독스트링 「못 막는 것」의 **뿌리 ㉮ / 항목 ㉮-1** 이다.
#
# **이 테스트의 목적은 그 상태가 조용히 바뀌지 않게 하는 것이다.** 누군가 이 층을 막으면
# 여기가 빨간불이 나고, 실패 메시지가 「문서를 갱신하라」로 이어진다. 잡히는 것은 **좋은
# 변화**이므로 케이스를 지우지 말고 기대값을 뒤집으면서 문서를 같이 고쳐라.
#
# 복원 검증은 **stdlib 만** 쓴다 (CI 에 node 를 요구하지 않으려고):
#   · 역슬래시 이스케이프 → `ast.literal_eval` (파이썬 문자열 리터럴 규칙 — `\n`·`\x0A`·줄 이음은
#     JS/TS·JSON 과 의미가 같다. JS 전용 표기 `\u{A}` 는 여기서 다루지 않는다)
#   · HTML 문자 참조 → `html.unescape` (HTML5 문자 참조 해석)
# 조사 단계에서는 node 와 css-tree 로 JS/TS·CSS 판까지 복원을 확인했다 (결과는 독스트링에).
MIN_KNOWN_BYPASS_CASES = 4
KNOWN_BYPASS_DOC = "verify_public_release_tree.py 독스트링 「못 막는 것」 ㉮-1 · .docs/6-도구/공개배포-릴리스.md"


def known_bypass_cases() -> list[tuple[str, str, str]]:
    """(이름, 게이트에 먹일 소스 텍스트, 런타임 층). payload 는 실행 시점에 만든다."""
    payload = b64(png(4096))
    prefix = "data:image/png;base64,"
    backslash = chr(92)
    return [
        (
            "JS/TS·JSON 문자열 이스케이프 \\n",
            f'const LOGO = "{prefix}{wrap(payload, 76, backslash + "n")}";',
            "backslash",
        ),
        (
            "JS/TS 16진 이스케이프 \\x0A",
            f'const LOGO = "{prefix}{wrap(payload, 76, backslash + "x0A")}";',
            "backslash",
        ),
        (
            "줄 이음 — 역슬래시 + 실제 개행",
            f'const LOGO = "{prefix}{wrap(payload, 76, backslash + chr(10))}";',
            "backslash",
        ),
        (
            "HTML/JSX 문자 참조 &#10;",
            f'<img src="{prefix}{wrap(payload, 76, "&#10;")}" />',
            "charref",
        ),
        (
            "HTML/JSX 문자 참조 &#x0A;",
            f'<img src="{prefix}{wrap(payload, 76, "&#x0A;")}" />',
            "charref",
        ),
        (
            "HTML/JSX 명명 참조 &NewLine;",
            f'<img src="{prefix}{wrap(payload, 76, "&NewLine;")}" />',
            "charref",
        ),
    ]


def _restore(text: str, layer: str) -> str:
    """소스 표기를 그 층이 처리한 뒤의 런타임 문자열로 되돌린다.

    먼저 **따옴표 안**만 떼어낸다 — 문자열 리터럴이든 HTML 속성값이든 층이 처리하는 범위는
    거기까지다. 전체 줄을 넘기면 뒤따르는 `" />` 가 payload 에 섞여 복원이 깨진다.
    """
    quoted = text[text.index('"') : text.rindex('"') + 1]
    if layer == "backslash":
        return ast.literal_eval(quoted)
    return html.unescape(quoted[1:-1])


def run_known_bypass_cases() -> list[str]:
    failures: list[str] = []
    cases = known_bypass_cases()
    if len(cases) < MIN_KNOWN_BYPASS_CASES:
        return [f"③ 케이스 {len(cases)}건 — 하한 {MIN_KNOWN_BYPASS_CASES} 미만 (수집이 깨졌다)"]

    banned = png(4096)
    saved = dict(gate.DENYLIST_BLOBS)
    gate.DENYLIST_BLOBS[gate.blob_sha(banned)] = "테스트 픽스처 — 제거 대상 자산 대역"
    restored = 0
    try:
        for name, text, layer in cases:
            # (가) 런타임 층이 **정말로** 원본을 복원하는가 — 아니면 픽스처가 죽은 것이라
            #      「게이트가 통과시킨다」는 관측에 아무 의미가 없다.
            runtime = _restore(text, layer)
            stripped = "".join(ch for ch in runtime.split(",", 1)[-1] if ch not in gate.B64_STRIP_CHARS)
            revived = gate._decode_b64(stripped, minimum=0)
            if revived != banned:
                failures.append(
                    f"③ {name}: 런타임 복원이 원본과 다르다 — 이 케이스는 더 이상 우회를 "
                    "재현하지 못한다 (픽스처가 죽었다). 고치거나 지워라"
                )
                continue
            restored += 1
            # (나) 그런데 게이트는 못 잡는다 — 그게 지금 상태이고, 문서가 그렇게 적혀 있다.
            if gate.check_inline_assets(FakeEntry("probe"), text):
                failures.append(
                    f"③ {name}: **이제 잡힌다.** 좋은 변화다 — 다만 문서가 아직 「못 막는다」로 "
                    f"남아 있다. {KNOWN_BYPASS_DOC} 를 갱신하고 이 케이스를 ① 로 옮겨라"
                )
    finally:
        gate.DENYLIST_BLOBS.clear()
        gate.DENYLIST_BLOBS.update(saved)
    if restored != len(cases) and not failures:
        failures.append(f"③ 런타임 복원 확인 {restored}건 — 기대 {len(cases)}건")
    print(
        f"  ③ 문서화된 우회 {len(cases)}건 검사 (런타임 복원 확인 {restored}건 · 전부 게이트 "
        "통과 = 현재 상태. 잡히면 빨간불 → 문서 갱신 신호)"
    )
    return failures


def remote_cases(repo: Path, origin: str) -> list[tuple[str, str, bool]]:
    """(이름, --remote 값, 거부돼야 하나). origin 은 개발 레포에 심어 둔 원격 URL."""
    base = origin.removesuffix(".git")
    host_path = base.split("://", 1)[1]
    host, path = host_path.split("/", 1)
    owner, name = path.split("/", 1)
    return [
        ("origin 그대로", origin, True),
        (".git 없는 표기", base, True),
        ("후행 슬래시", base + "/", True),
        (".git 뒤 후행 슬래시", origin + "/", True),
        ("scp 형식", f"git@{host}:{path}.git", True),
        ("scp 형식 · .git 없음", f"git@{host}:{path}", True),
        ("ssh:// 형식", f"ssh://git@{host}/{path}.git", True),
        ("git:// 형식", f"git://{host}/{path}.git", True),
        ("대문자 뒤섞기", f"https://{host.upper()}/{path.upper()}.git", True),
        # ─ PR #409 리뷰 ③ + 그 전수 조사에서 나온 표기 변형 ─
        # 후행 점은 FQDN 루트 라벨이라 DNS 가 같은 곳으로 푼다 (읽기 전용 ls-remote 로 실측:
        # `https://github.com./…` 이 점 없는 표기와 같은 SHA 를 돌려준다).
        ("FQDN 후행 점", f"https://{host}./{path}.git", True),
        ("FQDN 후행 점 · scp", f"git@{host}.:{path}.git", True),
        ("FQDN 후행 점 · ssh://", f"ssh://git@{host}./{path}.git", True),
        (".GIT 대문자 접미", f"https://{host}/{path}.GIT", True),
        (
            "퍼센트 인코딩 경로",
            f"https://{host}/{owner}/{urllib.parse.quote(name, safe='')}.git",
            True,
        ),
        (
            "퍼센트 인코딩 하이픈",
            f"https://{host}/{owner}/{name.replace('-', '%2D')}.git",
            True,
        ),
        # ─ PR #409 kimi CI 리뷰 뒤 지휘자 실측에서 나온 자리 (둘 다 가드 B 가 상쇄하지만,
        #   그 사실이 가드 A 의 서술을 참으로 만들지는 않는다) ─
        # 경로에만 넣었던 퍼센트 디코딩이 호스트에 빠져 있던 비대칭. 실측(읽기 전용):
        # `git ls-remote https://github%2Ecom/Danwoo/fintech-ai-platform.git HEAD` 가 같은 SHA.
        (
            "호스트 퍼센트 인코딩",
            f"https://{host.replace('.', '%2E')}/{path}.git",
            True,
        ),
        (
            "호스트 퍼센트 인코딩 + 후행 점",
            f"https://{host.replace('.', '%2E')}./{path}.git",
            True,
        ),
        # 닷 세그먼트는 HTTP 클라이언트가 RFC 3986 §5.2.4 대로 지우고 보낸다. 실측(읽기 전용):
        # `git ls-remote https://github.com/x/../Danwoo/fintech-ai-platform.git HEAD` 가 같은 SHA.
        ("닷 세그먼트 `..`", f"https://{host}/x/../{path}.git", True),
        ("닷 세그먼트 중첩", f"https://{host}/a/b/../../{path}.git", True),
        ("닷 세그먼트 `.`", f"https://{host}/./{path}.git", True),
        # **선두** 닷 세그먼트는 상대 경로로 해소하던 탓에 `..` 가 그대로 남아 빠져나갔다
        # (PR #409 3라운드). RFC 3986 §5.2.4 는 버퍼가 빈 상태의 `..` 를 **버린다**.
        ("선두 닷 세그먼트", f"https://{host}/../{path}.git", True),
        ("선두 닷 세그먼트 중첩", f"https://{host}/../../{path}.git", True),
        ("선두 닷 세그먼트 퍼센트 인코딩", f"https://{host}/%2e%2e/{path}.git", True),
        ("선두 닷 세그먼트 · scp 형식", f"git@{host}:../{path}.git", True),
        # `.git` 접미 **뒤**의 닷 세그먼트 — 접미 제거를 해소보다 먼저 하면 제거가 실패하고
        # `.git` 이 남은 값이 되어 빠져나갔다 (PR #409 4라운드 리뷰 비차단 1). 읽기 전용 실측:
        # `git ls-remote "https://github.com/Danwoo/fintech-ai-platform.git/." HEAD` 가 같은 SHA.
        (".git 뒤 닷 세그먼트 `.`", f"https://{host}/{path}.git/.", True),
        (".git 뒤 닷 세그먼트 `..`", f"https://{host}/{path}.git/x/..", True),
        (".git 뒤 퍼센트 인코딩 `%2e`", f"https://{host}/{path}.git/%2e", True),
        (".git 뒤 닷 세그먼트 · 대문자 .GIT", f"https://{host}/{path}.GIT/.", True),
        (".git 뒤 닷 세그먼트 · scp 형식", f"git@{host}:{path}.git/.", True),
        # 읽을 수 없는 표기는 **깔끔한 거부**로 끝나야 한다 (종전엔 traceback 이 샜다).
        ("깨진 IPv6 (정규화 불가 → 거부)", "https://[::1", True),
        ("전각 슬래시 (NFKC 검사 위반 → 거부)", f"https://{host}／{path}", True),
        ("기본 포트 명시 :443", f"https://{host}:443/{path}.git", True),
        ("기본 포트 명시 :22", f"ssh://git@{host}:22/{path}.git", True),
        ("유저인포 포함", f"https://user:token@{host}/{path}.git", True),
        ("이중 슬래시", f"https://{host}//{path}.git", True),
        ("쿼리 붙임", origin + "?x=1", True),
        ("앞뒤 공백", f"  {origin}  ", True),
        ("개발 레포 로컬 경로", str(repo), True),
        ("개발 레포 .git", str(repo / ".git"), True),
        (
            "`..` 를 낀 경로",
            str(repo.parent / ".." / repo.parent.name / repo.name),
            True,
        ),
        ("file:// 경로", "file://" + str(repo), True),
        # ─ 정상 원격은 통과해야 한다 ─
        ("다른 소유자의 같은 이름", f"https://{host}/other-owner/{name}", False),
        ("같은 소유자의 다른 레포", f"https://{host}/{owner}/trading-lab", False),
        ("다른 호스트", f"https://gitlab.example.com/{path}.git", False),
        ("한 글자 다른 호스트", f"https://{host}x/{path}.git", False),
        ("무관한 로컬 경로", str(repo.parent / "some-public-repo.git"), False),
        # 닷 세그먼트를 **풀고 나면 다른 곳**인 표기는 통과해야 한다 — 해소가 「무조건 거부」로
        # 뭉개지지 않는지 본다 (거부 방향으로만 넓히면 정상 릴리스가 막힌다).
        (
            "닷 세그먼트로 다른 레포에 도달",
            f"https://{host}/{owner}/x/../../other/{name}",
            False,
        ),
        ("선두 닷 세그먼트 뒤가 다른 레포", f"https://{host}/../other/{name}", False),
    ]


def run_remote_cases() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="release-gate-test-") as tmp:
        repo = Path(tmp) / "devrepo"
        repo.mkdir()
        origin = "https://github.com/example-owner/example-repo.git"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
        cases = remote_cases(repo, origin)
        if len(cases) < MIN_REMOTE_CASES:
            return [f"② 케이스 {len(cases)}건 — 하한 {MIN_REMOTE_CASES} 미만 (수집이 깨졌다)"]
        for name, remote, should_reject in cases:
            compared, reason = rp.check_remote_not_self(remote, repo)
            if compared == 0:
                failures.append(f"② {name}: 대조 대상 0건 — 검사가 존재하지 않는다")
                continue
            rejected = reason is not None
            if rejected != should_reject:
                want = "거부" if should_reject else "통과"
                got = "거부" if rejected else "통과"
                failures.append(f"② {name} ({remote}): 기대 {want} · 실제 {got}")
        print(f"  ② 원격 자기 지정 {len(cases)}건 검사")
    return failures


# ── ④ 목적지 브랜치 — 「매니페스트가 무엇과 비교하고 어디에 미는가」 (#410) ──────────────
# 릴리스 브랜치가 `main` 으로 박혀 있으면 공개 레포의 기본 브랜치가 다른 이름일 때 둘이 함께
# 어긋난다: 릴리스가 아무도 안 보는 브랜치에 쌓이고, 매니페스트의 「직전 릴리스 대비」가
# 엉뚱한 브랜치와의 비교가 된다. 한 줄(`checkout -B main` 의 시작점)만 되돌리면 다시 열리는
# 종류라 실행되는 케이스로 못박는다.
#
# 여기서는 `--remote` 를 **로컬 bare 레포**로만 준다 — 네트워크도, 공개 레포 생성도 없다.

MIN_BRANCH_CASES = 12


def _fixture_git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_destination(root: Path, label: str, default: str, seeded: dict[str, str]) -> Path:
    """bare 공개 레포 픽스처. `seeded` 는 브랜치명 → 그 브랜치에 담을 표식."""
    bare = root / f"{label}.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", default, str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    if not seeded:
        return bare
    work = root / f"{label}-seed"
    first = next(iter(seeded))
    subprocess.run(
        ["git", "init", "-q", "-b", first, str(work)],
        check=True,
        capture_output=True,
        text=True,
    )
    _fixture_git("config", "user.email", "fixture@example.com", cwd=work)
    _fixture_git("config", "user.name", "fixture", cwd=work)
    for index, (branch, marker) in enumerate(seeded.items()):
        if index:
            _fixture_git("checkout", "-q", "--orphan", branch, cwd=work)
            subprocess.run(
                ["git", "rm", "-rqf", "."],
                cwd=work,
                check=False,
                capture_output=True,
                text=True,
            )
        (work / "content.txt").write_text(marker, encoding="utf-8")
        _fixture_git("add", "-A", cwd=work)
        _fixture_git("commit", "-qm", f"{branch}: {marker}", cwd=work)
        _fixture_git("push", "-q", str(bare), f"HEAD:refs/heads/{branch}", cwd=work)
    return bare


# (이름, 기본 브랜치, 심을 브랜치들, --branch, 기대 브랜치 또는 None=거부, 기존 릴리스 있음)
BranchCase = tuple[str, str, dict[str, str], str | None, str | None, bool]


def branch_cases() -> list[BranchCase]:
    prev = "직전 릴리스"
    other = "무관한 내용"
    return [
        # 정상 — 기본 브랜치가 곧 릴리스 이력이다 (이름이 무엇이든)
        ("기본 main", "main", {"main": prev}, None, "main", True),
        ("기본 trunk", "trunk", {"trunk": prev}, None, "trunk", True),
        ("기본 master", "master", {"master": prev}, None, "master", True),
        # 이슈 #410 재현 — 기본 브랜치가 main 이 아니고 main 이 따로 있다.
        # 옛 코드는 `checkout -B main` 으로 로컬 main 을 trunk 위로 옮겨 비교 기준을 잃었다.
        (
            "기본 trunk + main 도 있음",
            "trunk",
            {"trunk": prev, "main": other},
            None,
            "trunk",
            True,
        ),
        # 새 입력 — 기본 브랜치 이름이 main·trunk·master 셋 중 어느 것도 아니다
        (
            "기본 release-line",
            "release-line",
            {"release-line": prev, "main": other},
            None,
            "release-line",
            True,
        ),
        # 새 입력 — 0커밋 초기 릴리스. 기본 브랜치 이름을 목적지가 정한다
        ("빈 레포 · 기본 trunk", "trunk", {}, None, "trunk", False),
        ("빈 레포 · 기본 main", "main", {}, None, "main", False),
        ("빈 레포 · 기본 이름이 특이", "publish", {}, None, "publish", False),
        # --branch 명시가 가장 세다 (원격 기본 브랜치와 달라도 사람이 적은 것을 따른다)
        (
            "--branch 로 비기본 브랜치 지정",
            "trunk",
            {"trunk": other, "main": prev},
            "main",
            "main",
            True,
        ),
        (
            "--branch 가 기본 브랜치와 같음",
            "trunk",
            {"trunk": prev},
            "trunk",
            "trunk",
            True,
        ),
        ("--branch · 빈 레포", "trunk", {}, "release", "release", False),
        # 거부 — 추측하면 조용히 틀린 숫자가 나온다
        ("--branch 가 목적지에 없음", "trunk", {"trunk": prev}, "nope", None, False),
    ]


def run_branch_cases() -> list[str]:
    failures: list[str] = []
    cases = branch_cases()
    if len(cases) < MIN_BRANCH_CASES:
        return [f"④ 케이스 {len(cases)}건 — 하한 {MIN_BRANCH_CASES} 미만 (수집이 깨졌다)"]

    with tempfile.TemporaryDirectory(prefix="release-branch-test-") as tmp:
        root = Path(tmp)
        for index, (
            name,
            default,
            seeded,
            override,
            expected,
            expect_existing,
        ) in enumerate(cases):
            bare = make_destination(root, f"case{index}", default, seeded)
            workdir = root / f"work{index}"
            workdir.mkdir()
            try:
                clone, branch, has_commits, _why = rp.prepare_destination(str(bare), workdir, override)
            except RuntimeError as error:
                if expected is not None:
                    failures.append(f"④ {name}: 기대 브랜치 {expected} · 실제 거부 ({error})")
                continue
            except subprocess.CalledProcessError as error:
                # 판정한 브랜치가 목적지에 없으면 체크아웃이 죽는다 — 「기존 릴리스 있음」과
                # 「그 브랜치가 실재함」이 어긋난 것이라 거부가 아니라 결함이다.
                failures.append(f"④ {name}: git 이 죽었다 ({' '.join(error.cmd)})")
                continue
            if expected is None:
                failures.append(f"④ {name}: 기대 거부 · 실제 브랜치 {branch}")
                continue
            if branch != expected:
                failures.append(f"④ {name}: 기대 브랜치 {expected} · 실제 {branch}")
            if has_commits != expect_existing:
                failures.append(f"④ {name}: 기존 릴리스 판정이 {has_commits} — 기대 {expect_existing}")
            if not has_commits:
                continue
            # 핵심 회귀 — 비교 기준이 **원격의 그 브랜치**여야 한다. 옛 코드처럼 로컬 브랜치를
            # 현재 HEAD 위로 옮기면 여기서 어긋난다 (그때 매니페스트가 엉뚱한 비교가 됐다).
            head = rp.git("rev-parse", "HEAD", cwd=clone).stdout.strip()
            want = rp.git("rev-parse", f"refs/remotes/origin/{branch}", cwd=clone, check=False).stdout.strip()
            if head != want:
                failures.append(
                    f"④ {name}: HEAD({head[:8]}) 가 origin/{branch}({want[:8]}) 와 다르다 — "
                    "비교 기준이 엉뚱한 브랜치로 옮겨졌다 (#410)"
                )

        # 원격 HEAD 가 실재하지 않는 브랜치를 가리키는 목적지 — 클론이 아무것도 체크아웃하지
        # 못한다. 옛 코드는 그것을 「커밋 없음 = 첫 릴리스」로 읽어, 릴리스 이력이 있는데도
        # 매니페스트가 「초기 커밋」이라 적고 push 는 non-fast-forward 로 깨졌다.
        dangling = make_destination(root, "dangling", "trunk", {"main": "직전 릴리스"})
        _fixture_git("symbolic-ref", "HEAD", "refs/heads/does-not-exist", cwd=dangling)
        workdir = root / "work-dangling"
        workdir.mkdir()
        try:
            _clone, branch, has_commits, _why = rp.prepare_destination(str(dangling), workdir)
        except RuntimeError:
            pass
        else:
            failures.append(
                f"④ 원격 HEAD 가 없는 브랜치를 지시: 기대 거부 · 실제 {branch}"
                f"(기존 릴리스 {has_commits}) — 추측하면 매니페스트가 거짓이 된다 (#410)"
            )

    print(f"  ④ 목적지 브랜치 {len(cases) + 1}건 검사 (bare 레포 픽스처 — 네트워크 없음)")
    return failures


def main() -> int:
    print("공개 배포 게이트 회귀 그물 (#406 · PR #409 리뷰 · #410):")
    failures = (
        run_decode_cases()
        + run_inline_cases()
        + run_notation_cases()
        + run_leading_byte_cases()
        + run_known_bypass_cases()
        + run_remote_cases()
        + run_branch_cases()
    )
    if failures:
        print(f"\n실패 {len(failures)}건:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    # 「전부 막혔다」로 읽히면 안 된다 — ③ 은 **열려 있는 것을 고정**한 결과다.
    print(
        "통과 — 닫은 우회는 닫힌 채로, 안 닫은 우회(③ 언어 층 이스케이프)는 열린 채로 그대로다\n"
        "  ③ 이 열려 있다는 서술의 정본: verify_public_release_tree.py 독스트링 "
        "「못 막는 것」 뿌리 ㉮"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
