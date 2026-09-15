"""#445 (B-16·F30) — 저장된 키가 실제로 통하는지 확인할 수 있는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    uv run python tests/test_probe_uses_stored_key.py

**「설정됨」과 「유효함」은 다르다.** 저장된 키는 비밀이라 화면에 안 남고, 그래서 다시 칠 수
없다. 종전의 `probe_key` 는 빈 값을 그냥 거절해서(「확인할 값이 없습니다」), 이미 저장된 키가
통하는지 **아무도 답하지 못했다.** Cycle 6 의 봇 서비스와 같은 병이다.

빈 값은 이제 「저장된 것으로 확인해 달라」는 뜻이다. 여기서 보는 것은 값이 어디서 오는지까지다 —
외부 호출은 이 그물의 범위 밖이라, 저장된 값이 실제로 실려 나가는지는 provider 를 가로채 본다.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))


def _seed_env_from_example() -> int:
    """`app/.env.example` 로 필수 환경변수를 채운다 — **import 전에** 불러야 한다.

    `core.config` 는 모듈을 읽는 순간 `settings = Settings()` 를 만들고, 그 값은 cwd 의
    `.env.{APP_ENV}` 에서 온다. 그 파일은 gitignore 라 워크트리·CI 에 없다.
    """
    os.environ.setdefault("APP_ENV", "development")
    example = BACKEND / "app/.env.example"
    assert example.is_file(), f"{example} 가 없다 — 이 테스트의 전제가 사라졌다"
    seeded = 0
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")
            seeded += 1
    assert seeded > 0, ".env.example 에서 채운 키가 0건이다 — 형식이 바뀌었다면 이 그물을 고쳐라"
    return seeded


_SEEDED = _seed_env_from_example()

from core.exceptions import BadRequestError  # noqa: E402
from services.data_key import data_key_service as mod  # noqa: E402
from services.data_key.data_key_service import (  # noqa: E402
    COMPOSITE_KEY_SETTINGS,
    SOURCE_KEY_SETTINGS,
    DataKeyService,
)

SOURCE = "data_go_kr"
SETTING = SOURCE_KEY_SETTINGS[SOURCE]
STORED = "STORED-KEY-DO-NOT-USE"

# 합성 자격 소스 — 설정 이름은 **코드에서 읽는다**. 여기에 실제 키 이름을 적으면
# `verify_data_key_env_boundary.py` 가 막고, 소스가 바뀌면 그물이 낡는다.
COMPOSITE_SOURCE = next(iter(COMPOSITE_KEY_SETTINGS))
COMPOSITE_SETTINGS = COMPOSITE_KEY_SETTINGS[COMPOSITE_SOURCE]

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class Config:
    def __init__(self, **values: str) -> None:
        self.APP_ENV = "development"
        for setting in SOURCE_KEY_SETTINGS.values():
            setattr(self, setting, "")
        for pair in COMPOSITE_KEY_SETTINGS.values():
            for setting in pair:
                setattr(self, setting, "")
        for key, value in values.items():
            setattr(self, key, value)


def _service(**values: str) -> DataKeyService:
    tmp = Path(tempfile.mkdtemp(prefix="probe-stored."))
    (tmp / ".env.development").write_text("# 비어 있음\n", encoding="utf-8")
    os.chdir(tmp)
    return DataKeyService(Config(**values))


def main() -> int:
    import asyncio

    origin = Path.cwd()
    try:
        # ① 저장된 키도 없으면 무엇이 없는지 말한다 — 「확인할 값이 없습니다」로 끝내지 않는다.
        svc = _service()
        try:
            asyncio.run(svc.probe_key(SOURCE, "", SETTING))
            FAILURES.append("저장된 키가 없는데 확인이 통과했다")
            globals()["CHECKED"] += 1
        except BadRequestError as e:
            check("빈 값 + 저장 없음 → 사유가 저장 없음을 말한다", "저장된 키도 없습니다" in str(e), True)

        # ② 저장된 키가 있으면 그 값으로 물어본다. provider 를 가로채 실린 값을 본다.
        svc = _service(**{SETTING: STORED})
        seen: list[str] = []

        def fake_get_provider(source: str, credential: str):
            seen.append(credential)
            raise RuntimeError("여기서 멈춘다 — 외부 호출은 이 그물의 범위 밖이다")

        original = mod.get_provider
        mod.get_provider = fake_get_provider  # type: ignore[assignment]
        try:
            asyncio.run(svc.probe_key(SOURCE, "", SETTING))
        except RuntimeError:
            pass
        finally:
            mod.get_provider = original  # type: ignore[assignment]

        check("저장된 키가 provider 로 실린다", seen, [STORED])

        # ③ 값을 치면 그 값이 이긴다 — 저장 전 확인은 종전 그대로.
        svc = _service(**{SETTING: STORED})
        svc._last_probe_at.clear()
        seen2: list[str] = []

        def fake2(source: str, credential: str):
            seen2.append(credential)
            raise RuntimeError("stop")

        mod.get_provider = fake2  # type: ignore[assignment]
        try:
            asyncio.run(svc.probe_key(SOURCE, "TYPED-KEY", SETTING))
        except RuntimeError:
            pass
        finally:
            mod.get_provider = original  # type: ignore[assignment]

        check("친 값이 저장된 값을 이긴다", seen2, ["TYPED-KEY"])

        # ④ **합성 자격**: 한쪽만 저장돼 있으면 화면은 그 행을 「설정됨」이라고 말한다.
        #    그 상태에서 「저장된 키 확인」을 누르면 「저장된 키도 없습니다」가 아니라
        #    **무엇이 비었는지**를 말해야 한다 — 아니면 화면과 정반대인 사유가 뜬다.
        first, second = COMPOSITE_SETTINGS
        svc = _service(**{first: STORED})
        svc._last_probe_at.clear()
        try:
            result = asyncio.run(svc.probe_key(COMPOSITE_SOURCE, "", first))
        except BadRequestError as e:
            # 이것이 이 그물이 막는 회귀다 — 화면은 그 행을 「설정됨」이라고 말하는데
            # 확인은 「저장된 키도 없습니다」라고 답한다.
            result = {"checked": None, "detail": f"예외로 끝났다: {e}", "ok": None}
        check("합성 자격의 한쪽만 있으면 예외가 아니라 사유를 낸다", result.get("checked"), False)
        check("비어 있는 쪽의 이름을 말한다", second in (result.get("detail") or ""), True)
        check("통했다고 하지 않는다", result.get("ok"), False)

        # ⑤ 둘 다 저장돼 있으면 이어 붙인 한 줄이 실린다 — 다시 잇지 않는다.
        svc = _service(**{first: "A-PART", second: "B-PART"})
        svc._last_probe_at.clear()
        seen3: list[str] = []

        def fake3(source: str, credential: str):
            seen3.append(credential)
            raise RuntimeError("stop")

        mod.get_provider = fake3  # type: ignore[assignment]
        try:
            asyncio.run(svc.probe_key(COMPOSITE_SOURCE, "", first))
        except RuntimeError:
            pass
        finally:
            mod.get_provider = original  # type: ignore[assignment]

        check("둘 다 저장돼 있으면 이어 붙인 한 줄이 실린다", seen3, ["A-PART:B-PART"])

        # ⑥ 정말 아무것도 없으면 종전대로 거절한다 — 그 말은 사실이다.
        svc = _service()
        svc._last_probe_at.clear()
        try:
            asyncio.run(svc.probe_key(COMPOSITE_SOURCE, "", first))
            FAILURES.append("합성 자격이 통째로 비었는데 확인이 통과했다")
            globals()["CHECKED"] += 1
        except BadRequestError as e:
            check("통째로 비면 저장된 키가 없다고 말한다", "저장된 키도 없습니다" in str(e), True)
    finally:
        os.chdir(origin)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    # 실패한 판에 성공 문구를 찍으면 로그를 읽는 사람이 정반대 사실을 읽는다 —
    # 종료 코드만 맞는 것으로는 부족하다.
    if FAILURES:
        print("판정: 저장된 키 확인이 깨졌다 — 위 FAIL 을 보라")
        return 1
    print("판정: 저장된 키도 확인할 수 있고, 친 값이 있으면 그쪽이 이긴다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
