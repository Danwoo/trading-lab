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
from services.data_key.data_key_service import SOURCE_KEY_SETTINGS, DataKeyService  # noqa: E402

SOURCE = "data_go_kr"
SETTING = SOURCE_KEY_SETTINGS[SOURCE]
STORED = "STORED-KEY-DO-NOT-USE"

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
    finally:
        os.chdir(origin)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    print("판정: 저장된 키도 확인할 수 있고, 친 값이 있으면 그쪽이 이긴다")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
