"""#435 — 실패 문구가 **사용자가 실제로 할 수 있는 일**을 말하고, 같은 사건에 같은 말을 하는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    uv run python tests/test_failure_message_prescriptions.py

Cycle 6 이 「스트리밍이 실패 원인을 「잠시 후 다시 시도」로 덮는다」(#423)를 닫았는데, Cycle 7 에서
같은 병이 더 나쁜 형태로 나왔다 — **틀린 처방을 확신 있게 말한다.** 「잠시 후 다시 시도」는 아무것도
안 하게 만들지만, 틀린 처방은 **엉뚱한 곳을 고치게 만든다.**

여기서 보는 것은 셋이다:

  (F31·B-15) 403 은 「키 틀림」과 「IP 막힘」을 **소스가 안 가른다.** 그런데 문구는 IP 만 단정해
      사용자를 방화벽으로 보냈다 — 명백한 가짜 키를 넣었을 때도 그랬다. 모호하면 **모호한 채로**
      말하되, 사용자가 먼저 확인할 수 있는 것(키)을 앞에 둔다.
  (F39) 「전략 파일이 있는지 확인하십시오」 — 이 제품의 사용자는 개인 투자자다. 전략 파일은 서버의
      소스 파일이고 볼 수도 고칠 수도 없다. **할 수 없는 처방은 처방이 아니다.**
  (F34) 같은 「중복」에 문구가 둘이었다 — 순차 경로는 「이미 존재하는 데이터입니다」, 동시 경로(DB
      유니크 위반)는 「이미 등록된 값입니다」. 사용자에게는 같은 사건이므로 같은 말이어야 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

import re  # noqa: E402

import httpx  # noqa: E402
from providers.failure import describe_provider_failure  # noqa: E402

# 서비스 모듈은 import 하지 않는다 — `core.config` 를 끌어와 env 없는 자리(CI)에서 죽는다.
# 문구가 그 파일에 있는지는 소스를 읽어 확인한다.

DUPLICATE_MESSAGE = "이미 존재하는 데이터입니다."


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://source.example/api?serviceKey=SECRET")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def test_403_은_키를_먼저_말한다() -> str:
    msg = describe_provider_failure(_status_error(403), "data_go_kr")
    assert "키" in msg, f"키를 아예 안 말한다: {msg}"
    key_at, ip_at = msg.index("키"), msg.find("IP")
    assert ip_at == -1 or key_at < ip_at, f"IP 를 키보다 먼저 말한다: {msg}"
    return "403 은 키를 먼저 말한다"


def test_403_이_IP_만_단정하지_않는다() -> str:
    msg = describe_provider_failure(_status_error(403), "data_go_kr")
    # 소스가 두 원인을 안 가르므로 「IP 를 등록하세요」로 끝내면 오진이다.
    assert not msg.rstrip(".").endswith("막힙니다"), f"IP 처방으로 끝난다: {msg}"
    return "403 이 IP 만 단정하지 않는다"


def test_403_문구가_원문과_자격을_안_담는다() -> str:
    msg = describe_provider_failure(_status_error(403), "data_go_kr")
    for leak in ("serviceKey", "SECRET", "https://", "HTTPStatusError"):
        assert leak not in msg, f"{leak!r} 가 화면 문구에 실렸다: {msg}"
    return "403 문구가 원문과 자격을 안 담는다"


def test_모르는_상태_코드는_아는_척하지_않는다() -> str:
    msg = describe_provider_failure(_status_error(451), "data_go_kr")
    assert "451" in msg and "종목" not in msg, f"모르는 코드에 400 의 조언을 빌려 준다: {msg}"
    return "모르는 상태 코드는 아는 척하지 않는다"


def test_전략을_못_찾은_처방이_사용자가_할_수_있는_일이다() -> str:
    source = (BACKEND / "app/services/bot/bot_service.py").read_text(encoding="utf-8")
    assert "전략 파일이 있는지 확인" not in source, "개인 투자자가 볼 수도 고칠 수도 없는 처방이 남아 있다"
    return "전략을 못 찾은 처방이 사용자가 할 수 있는 일이다"


def test_중복은_어느_경로로_와도_같은_말을_한다() -> str:
    # `core.exception_handler` 는 `core.logger`→`core.config` 를 끌어와 env 없는 자리에서
    # import 가 죽는다. 그래서 매핑 표를 소스에서 읽는다.
    handler = (BACKEND / "app/core/exception_handler.py").read_text(encoding="utf-8")
    row = re.search(r'"23505":\s*ConflictError\("([^"]+)"\)', handler)
    assert row, "23505(unique_violation) 매핑을 못 찾았다 — 표의 형태가 바뀌었다면 이 그물을 고쳐라"
    assert row.group(1) == DUPLICATE_MESSAGE, f"DB 유니크 위반 경로만 다른 말을 한다: {row.group(1)}"
    # 순차 경로(서비스가 먼저 조회해 걸러내는 쪽)의 문구가 정본이다.
    service_source = (BACKEND / "app/services/watchlist/watchlist_service.py").read_text(encoding="utf-8")
    assert DUPLICATE_MESSAGE in service_source, "정본으로 삼은 문구가 서비스에서 사라졌다"
    return "중복은 어느 경로로 와도 같은 말을 한다"


def _main() -> int:
    tests = [
        test_403_은_키를_먼저_말한다,
        test_403_이_IP_만_단정하지_않는다,
        test_403_문구가_원문과_자격을_안_담는다,
        test_모르는_상태_코드는_아는_척하지_않는다,
        test_전략을_못_찾은_처방이_사용자가_할_수_있는_일이다,
        test_중복은_어느_경로로_와도_같은_말을_한다,
    ]
    passed = 0
    for tc in tests:
        try:
            name = tc()
        except AssertionError as e:
            print(f"FAIL {tc.__name__}: {e}")
            continue
        print(f"PASS {name}")
        passed += 1
    print(f"\n검사한 단언 {len(tests)}건 중 {passed}건 통과")
    print("판정: 실패 문구가 할 수 있는 일을 말하고, 같은 사건에 같은 말을 한다")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
