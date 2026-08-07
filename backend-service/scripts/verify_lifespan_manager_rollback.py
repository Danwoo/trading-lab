"""lifespan 매니저 기동 실패 시 롤백 검증 — 시도된 매니저 전부의 stop 이 호출되는지 (#270).

계약 (app/main.py `lifespan`):
  (1) 모든 매니저가 정상 기동하면 순서대로 start 되고, yield 이후 역순으로 stop 된다 (기존 동작).
  (2) N 번째 매니저의 start 가 실패하면, **시도된 1..N 번 매니저 전부**(실패한 N 번째 포함)의 stop
      이 역순으로 호출된 뒤 원래 예외가 다시 올라간다. start() 가 예외를 던지기 전에 이미 부작용을
      냈을 수 있으므로("시작 실패 = 부작용 없음"이 아니다 — 예: `scheduler_manager.start()` 는
      `self.scheduler.start()` 로 내부 스케줄러를 띄운 **뒤** DB 조회를 하는데, 그 조회가 기동 시
      DB 불가로 실패할 수 있다) 실패한 매니저 자신도 정리 대상이다. N+1 번째 이후(시도조차 안 된)
      매니저는 stop 을 받지 않는다.
  (3) 첫 번째 매니저부터 실패해도 그 매니저 자신의 stop 은 호출된다(시도됐으므로) — 그 뒤 매니저는
      시도되지 않았으니 stop 도 없다.
  (4) 정리 중 **stop() 자신이 던져도** 나머지 매니저는 계속 정리되고, 밖으로 올라가는 예외는
      기동 실패의 **원인 예외**다 (#375). 정리 실패는 삼켜지지 않고 로그에 남는다 — 운영자에게
      "m2 stop 실패"만 보이고 진짜 원인인 "m3 start 실패"가 사라지면 안 된다.
  (5) 커넥션 풀 회수(`dispose()`)는 정상 종료 경로뿐 아니라 **기동 실패 롤백 경로에서도** 호출된다
      (#375). 기동에 실패했다고 풀을 남겨 두지 않는다.
  (6) 정상 종료 중 stop() 이 던져도 나머지 매니저 정리와 dispose() 는 계속되고, 예외는 밖으로
      나가지 않는다 (종료 경로에서 던져 봐야 셧다운만 지저분해진다).

이 계약이 성립하려면 **각 매니저의 stop() 이 start() 실패 후에도 안전(idempotent 가드)** 해야 한다
— `modules.BackgroundManager` 프로토콜이 이를 명시한다. 기존 3종(message_consumer·nav_producer·
scheduler)은 전부 `self.task`/`self.scheduler.running` 등 자체 상태를 보고 정리하므로 이 전제를
충족한다.

main.py 는 core.container 를 import 하므로 필수 env 를 더미로 주입한 뒤 로드한다.
`uv run python scripts/verify_lifespan_manager_rollback.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_DUMMY_ENV = {
    "APP_ENV": "production",
    "BACKEND_SQL_DB_DRIVER": "x",
    "BACKEND_SQL_DB_ODBC_DRIVER": "x",
    "BACKEND_SQL_DB_HOST": "x",
    "BACKEND_SQL_DB_PORT": "1433",
    "BACKEND_SQL_DB_NAME": "x",
    "BACKEND_SQL_DB_USER": "x",
    "BACKEND_SQL_DB_PASSWORD": "x",
    "SFTP_HOST": "x",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "x",
    "SFTP_PASSWORD": "x",
    "JWT_SECRET": "x",
}
for _k, _v in _DUMMY_ENV.items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import main as main_module  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


class _FakeManager:
    """`fail_after_side_effect=True` 는 scheduler_manager 의 실제 패턴을 재현한다 — start() 가
    부작용(예: 내부 스케줄러 기동)을 먼저 낸 뒤, 그 다음 단계(예: DB 조회)에서 예외를 던진다."""

    def __init__(
        self,
        name: str,
        fail: bool = False,
        fail_after_side_effect: bool = False,
        fail_stop: bool = False,
    ) -> None:
        self.name = name
        self.fail = fail
        self.fail_after_side_effect = fail_after_side_effect
        self.fail_stop = fail_stop
        self.started = False
        self.stopped = False
        self.side_effect_active = False  # 예: scheduler.running

    async def start(self) -> None:
        if self.fail_after_side_effect:
            self.side_effect_active = True  # self.scheduler.start() 에 해당 — 실패 전에 이미 일어남
        if self.fail:
            raise RuntimeError(f"{self.name} 기동 실패")
        self.started = True

    async def stop(self) -> None:
        # 실제 매니저와 동형: 자기 상태를 보고서만 정리한다(idempotent 가드) — start() 가 어디까지
        # 진행됐든 안전하게 호출 가능해야 한다는 계약을 그대로 재현.
        # `fail_stop=True` 는 정리 자체가 실패하는 매니저 (#375) — 예: 종료 중 외부 연결이 끊겨
        # 던지는 경우. 이때도 나머지 매니저는 정리돼야 하고 원인 예외가 가려지면 안 된다.
        if self.fail_stop:
            raise RuntimeError(f"{self.name} 정리 실패")
        if self.side_effect_active:
            self.side_effect_active = False
        self.stopped = True


def _fake_app(disposed: list[str] | None = None) -> MagicMock:
    def _dispose() -> None:
        if disposed is not None:
            disposed.append("dispose")

    app = MagicMock()
    app.container.backend_sql_client.return_value = MagicMock(dispose=_dispose)
    return app


async def _run_lifespan_expect_failure(managers: list[_FakeManager], app: MagicMock | None = None) -> Exception:
    with patch.object(main_module, "load_managers", return_value=managers):
        try:
            async with main_module.lifespan(app or _fake_app()):
                _fail("기동 실패에도 lifespan 이 yield 까지 진행됨")
        except RuntimeError as e:
            return e
    raise AssertionError("도달 불가")


def check_middle_failure_rolls_back_all_attempted_managers() -> None:
    """(2) 3번째 매니저 실패(부작용 없음) → 1·2·3번 전부 stop 됨(역순), 4번째(미시도)는 손대지 않음."""
    m1, m2, m3, m4 = (
        _FakeManager("m1"),
        _FakeManager("m2"),
        _FakeManager("m3", fail=True),
        _FakeManager("m4"),
    )
    asyncio.run(_run_lifespan_expect_failure([m1, m2, m3, m4]))

    if not (m1.started and m1.stopped):
        _fail(f"먼저 시작한 m1 의 stop 이 호출되지 않음 (started={m1.started}, stopped={m1.stopped})")
    if not (m2.started and m2.stopped):
        _fail(f"먼저 시작한 m2 의 stop 이 호출되지 않음 (started={m2.started}, stopped={m2.stopped})")
    if not m3.stopped:
        _fail(f"기동 실패한 m3 자신의 stop 이 호출되지 않음 (stopped={m3.stopped})")
    if m4.started or m4.stopped:
        _fail(f"시도조차 안 된 m4 가 start/stop 되었다고 기록됨 (started={m4.started}, stopped={m4.stopped})")
    print("  ✓ 롤백: 시도된 m1·m2·m3 전부 stop 됨(m3 자신 포함), 시도 안 된 m4 는 그대로")


def check_partial_side_effect_before_failure_is_cleaned_up() -> None:
    """(2) 핵심 시나리오 — scheduler_manager 패턴: start() 가 부작용을 낸 뒤 실패해도 그 부작용이
    stop() 으로 정리된다(예전 계약은 "실패한 매니저는 시작한 게 없다"고 가정해 이걸 놓쳤다)."""
    m1 = _FakeManager("m1")
    m_scheduler_like = _FakeManager("scheduler-like", fail=True, fail_after_side_effect=True)
    asyncio.run(_run_lifespan_expect_failure([m1, m_scheduler_like]))

    if not m_scheduler_like.stopped:
        _fail("부작용을 낸 뒤 실패한 매니저의 stop 이 호출되지 않음 — scheduler 스레드가 떠 있게 됨")
    if m_scheduler_like.side_effect_active:
        _fail("stop() 은 호출됐지만 부작용(side_effect_active)이 정리되지 않음")
    print("  ✓ 부작용 후 실패(scheduler_manager 패턴): stop() 이 호출되어 부작용까지 정리됨")


def check_first_failure_still_stops_itself() -> None:
    """(3) 첫 매니저부터 실패해도 그 매니저 자신은 stop 됨(시도됐으므로), 그 뒤는 미시도라 그대로."""
    m1 = _FakeManager("m1", fail=True)
    m2 = _FakeManager("m2")
    asyncio.run(_run_lifespan_expect_failure([m1, m2]))

    if not m1.stopped:
        _fail(f"첫 매니저 자신의 stop 이 호출되지 않음 (stopped={m1.stopped})")
    if m2.started or m2.stopped:
        _fail(f"시도되지 않은 m2 가 start/stop 되었다고 기록됨 (started={m2.started}, stopped={m2.stopped})")
    print("  ✓ 첫 매니저 실패: 그 매니저 자신은 stop 됨, 시도되지 않은 뒤 매니저는 그대로")


def check_all_success_normal_shutdown_unaffected() -> None:
    """(1) 전부 정상 기동하면 기존 동작(정상 yield, 역순 stop)이 그대로 유지된다."""
    m1, m2, m3 = _FakeManager("m1"), _FakeManager("m2"), _FakeManager("m3")
    stop_order: list[str] = []

    async def _tracked_stop(mgr: _FakeManager) -> None:
        stop_order.append(mgr.name)
        mgr.stopped = True

    m1.stop = lambda: _tracked_stop(m1)  # type: ignore[method-assign]
    m2.stop = lambda: _tracked_stop(m2)  # type: ignore[method-assign]
    m3.stop = lambda: _tracked_stop(m3)  # type: ignore[method-assign]

    async def _run() -> None:
        with patch.object(main_module, "load_managers", return_value=[m1, m2, m3]):
            async with main_module.lifespan(_fake_app()):
                pass

    asyncio.run(_run())

    if not (m1.started and m2.started and m3.started):
        _fail("정상 케이스에서 매니저 일부가 시작되지 않음")
    if stop_order != ["m3", "m2", "m1"]:
        _fail(f"정상 종료 순서가 역순이 아님: {stop_order}")
    print("  ✓ 정상 기동: 전부 start 되고, 종료 시 역순(m3→m2→m1)으로 stop — 기존 동작 무손상")


def check_stop_failure_neither_hides_cause_nor_blocks_cleanup() -> None:
    """(4) 롤백 중 stop() 이 던져도 나머지가 정리되고, 올라가는 예외는 원인(start 실패)이며,
    정리 실패는 삼켜지지 않고 로그에 남는다."""
    m1 = _FakeManager("m1")
    m2 = _FakeManager("m2", fail_stop=True)
    m3 = _FakeManager("m3", fail=True)
    logged: list[str] = []

    def _record_error(msg: object, *args: object, **kwargs: object) -> None:
        logged.append(str(msg))

    with patch.object(main_module.logger, "error", _record_error):
        raised = asyncio.run(_run_lifespan_expect_failure([m1, m2, m3]))

    if "m3 기동 실패" not in str(raised):
        _fail(f"올라온 예외가 원인(m3 기동 실패)이 아니라 정리 실패에 가려짐: {raised!r}")
    if not m3.stopped:
        _fail("기동 실패한 m3 자신의 stop 이 호출되지 않음")
    if not m1.stopped:
        _fail("m2 의 정리 실패 뒤 m1 이 정리되지 않음 — 한 매니저의 실패가 나머지 정리를 막았다")
    if not any("m2 정리 실패" in line for line in logged):
        _fail(f"정리 실패가 로그에 남지 않음(삼켜짐): {logged}")
    print("  ✓ 정리 실패: 원인 예외가 그대로 올라오고, 나머지도 정리되며, 실패는 로그에 남음")


def check_rollback_disposes_sql_client() -> None:
    """(5) 기동 실패로 롤백해도 커넥션 풀이 회수된다."""
    disposed: list[str] = []
    asyncio.run(
        _run_lifespan_expect_failure([_FakeManager("m1"), _FakeManager("m2", fail=True)], app=_fake_app(disposed))
    )
    if not disposed:
        _fail("기동 실패 롤백 경로에서 dispose() 가 호출되지 않음 — 커넥션 풀이 남는다")
    print("  ✓ 롤백 경로에서도 dispose() 호출 — 기동 실패해도 커넥션 풀 회수")


def check_shutdown_stop_failure_continues_cleanup() -> None:
    """(6) 정상 종료 중 stop() 이 던져도 나머지 정리·dispose 가 계속되고 예외는 밖으로 안 나간다."""
    disposed: list[str] = []
    m1 = _FakeManager("m1")
    m2 = _FakeManager("m2", fail_stop=True)
    m3 = _FakeManager("m3")

    async def _run() -> None:
        with patch.object(main_module, "load_managers", return_value=[m1, m2, m3]):
            async with main_module.lifespan(_fake_app(disposed)):
                pass

    with patch.object(main_module.logger, "error", lambda *a, **kw: None):
        try:
            asyncio.run(_run())
        except RuntimeError as e:
            _fail(f"정상 종료 경로의 stop() 실패가 밖으로 새어 나감: {e}")

    if not (m3.stopped and m1.stopped):
        _fail(f"종료 중 stop 실패 뒤 나머지가 정리되지 않음 (m3={m3.stopped}, m1={m1.stopped})")
    if not disposed:
        _fail("종료 중 stop 실패로 dispose() 까지 건너뛰어짐 — 커넥션 풀이 남는다")
    print("  ✓ 정상 종료 중 정리 실패: 나머지 매니저 정리·dispose 계속, 예외는 밖으로 안 나감")


def main() -> None:
    print("lifespan 매니저 롤백 검증")
    check_middle_failure_rolls_back_all_attempted_managers()
    check_partial_side_effect_before_failure_is_cleaned_up()
    check_first_failure_still_stops_itself()
    check_all_success_normal_shutdown_unaffected()
    check_stop_failure_neither_hides_cause_nor_blocks_cleanup()
    check_rollback_disposes_sql_client()
    check_shutdown_stop_failure_continues_cleanup()
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
