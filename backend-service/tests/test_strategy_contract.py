"""#150 B0 — 전략 규약이 폼을 만든다는 계약을 검증한다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_strategy_contract.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식 — **완료 조건은 첫 두 개다** (#150 B0 "전략을 하나 더 추가해도 화면 코드를
안 고친다는 것을 테스트로 보인다"):

- **새 전략 파일을 놓기만 하면 목록에 뜬다** — 등록부·레지스트리를 고치지 않는다.
- **폼 스키마가 내는 control 은 화면이 이미 아는 세 종뿐이다** — 그래서 화면이 안 바뀐다.
  이 단언이 깨지는 유일한 경우가 규약에 새 파라미터 타입을 더할 때이고, 그때는 화면도
  같이 고쳐야 한다는 것을 이 테스트가 잡는다 (규약 §3.4).
- 폼 스키마에 `type` 이 새지 않는다 — 화면이 type 을 알면 타입이 늘 때마다 화면이 따라 바뀐다.
- 잘못된 선언은 **이유와 함께** 목록에서 빠지고, 깨진 파일 하나가 나머지를 죽이지 않는다.
- 저장 시 값 검증이 선언한 범위·타입·선택지를 실제로 막는다.
- 레포에 실제로 들어 있는 전략 파일이 규약을 통과한다.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# import 사슬이 core.config(settings)까지 닿지 않도록 app 만 경로에 올린다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("APP_ENV", "test")

from services.bot.strategy_loader import (  # noqa: E402
    StrategySpec,
    default_strategies_dir,
    load_strategies,
    to_form_schema,
    validate_param_values,
)

# 화면이 그릴 줄 아는 컨트롤 — 이 집합이 늘면 프론트도 같이 고쳐야 한다.
KNOWN_CONTROLS = {"number", "select", "toggle"}

_NEW_STRATEGY = '''\
"""테스트용 새 전략 — 파일을 놓기만 한다."""

STRATEGY = {
    "key": "brand_new",
    "name": "새로 놓은 전략",
    "timeframe": "1w",
    "params": [
        {"name": "window", "label": "관찰 기간", "type": "int",
         "default": 4, "min": 1, "max": 52, "step": 1, "unit": "주"},
        {"name": "mode", "label": "모드", "type": "choice", "default": "a",
         "choices": [{"value": "a", "label": "가"}, {"value": "b", "label": "나"}]},
        {"name": "strict", "label": "엄격", "type": "bool", "default": False},
    ],
}


def indicators(bars, params):
    return {}


def entry(ctx):
    return False


def exit(ctx):
    return False
'''

_BROKEN_STRATEGY = """\
STRATEGY = {
    "key": "broken",
    "name": "범위 밖 기본값",
    "timeframe": "1d",
    "params": [
        {"name": "n", "label": "N", "type": "int",
         "default": 999, "min": 1, "max": 10, "step": 1},
    ],
}


def indicators(bars, params):
    return {}


def entry(ctx):
    return False


def exit(ctx):
    return False
"""

_NO_CALLABLES = """\
STRATEGY = {"key": "no_fn", "name": "함수 없음", "timeframe": "1d", "params": []}
"""


def _write(directory: Path, name: str, source: str) -> None:
    (directory / name).write_text(source, encoding="utf-8")


def test_new_strategy_file_needs_no_registration() -> None:
    """파일을 놓기만 하면 목록에 뜬다 — 등록부를 고치지 않는다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        result = load_strategies(directory)
        assert result.valid == [], "빈 디렉터리인데 전략이 잡혔다"

        _write(directory, "brand_new.py", _NEW_STRATEGY)
        result = load_strategies(directory)

        assert [spec.key for spec in result.valid] == ["brand_new"], result.errors
        assert result.errors == []


def test_form_schema_uses_only_known_controls() -> None:
    """폼이 내는 control 이 화면이 아는 세 종뿐이라, 전략이 늘어도 화면이 안 바뀐다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "brand_new.py", _NEW_STRATEGY)
        schema = to_form_schema(load_strategies(directory).valid[0])

    controls = {field["control"] for field in schema["fields"]}
    assert controls <= KNOWN_CONTROLS, f"화면이 모르는 control 이 생겼다: {controls - KNOWN_CONTROLS}"
    assert controls == {"number", "select", "toggle"}, "세 종을 다 덮는 시나리오여야 한다"

    by_name = {field["name"]: field for field in schema["fields"]}
    assert by_name["window"]["unit"] == "주"
    assert by_name["mode"]["options"] == [
        {"value": "a", "label": "가"},
        {"value": "b", "label": "나"},
    ]
    assert by_name["strict"]["default"] is False
    assert schema["timeframe"] == "1w"


def test_form_schema_does_not_leak_type() -> None:
    """`type` 이 화면에 안 나간다 — 나가면 화면이 타입 목록에 결합된다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "brand_new.py", _NEW_STRATEGY)
        schema = to_form_schema(load_strategies(directory).valid[0])

    for field in schema["fields"]:
        assert "type" not in field, f"{field['name']} 에 type 이 샜다"


def test_percent_gets_default_unit() -> None:
    """percent 는 unit 을 안 적어도 % 가 붙는다."""
    spec = StrategySpec.model_validate(
        {
            "key": "pct_only",
            "name": "퍼센트",
            "timeframe": "1d",
            "params": [
                {"name": "p", "label": "비율", "type": "percent", "default": 3.0, "min": 0.5, "max": 15.0, "step": 0.5}
            ],
        }
    )
    assert to_form_schema(spec)["fields"][0]["unit"] == "%"


def test_broken_file_is_reported_and_isolated() -> None:
    """깨진 전략 하나가 나머지를 죽이지 않고, 이유가 남는다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "brand_new.py", _NEW_STRATEGY)
        _write(directory, "broken.py", _BROKEN_STRATEGY)
        _write(directory, "no_fn.py", _NO_CALLABLES)
        result = load_strategies(directory)

    assert [spec.key for spec in result.valid] == ["brand_new"]
    reasons = {error.source: error.message for error in result.errors}
    assert set(reasons) == {"broken.py", "no_fn.py"}
    assert "범위" in reasons["broken.py"], reasons["broken.py"]
    assert "indicators" in reasons["no_fn.py"], reasons["no_fn.py"]


def test_duplicate_key_is_rejected() -> None:
    """같은 key 를 두 파일이 쓰면 뒤엣것이 빠진다 — 저장된 봇이 어느 쪽을 가리키는지 모호해진다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "a_first.py", _NEW_STRATEGY)
        _write(directory, "b_second.py", _NEW_STRATEGY)
        result = load_strategies(directory)

    assert [spec.key for spec in result.valid] == ["brand_new"]
    assert len(result.errors) == 1
    assert "a_first.py" in result.errors[0].message


def test_underscore_files_are_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "_helper.py", _NEW_STRATEGY)
        result = load_strategies(directory)
    assert result.valid == [] and result.errors == []


def test_value_validation_guards_declared_range() -> None:
    """저장할 값이 선언 밖이면 막는다 — 빠진 값은 default 로 채운다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "brand_new.py", _NEW_STRATEGY)
        spec = load_strategies(directory).valid[0]

    assert validate_param_values(spec, {}) == {"window": 4, "mode": "a", "strict": False}
    assert validate_param_values(spec, {"window": 10})["window"] == 10

    for values, expected in [
        ({"window": 99}, "1~52"),
        ({"window": 1.5}, "정수"),
        ({"window": "4"}, "숫자"),
        ({"mode": "z"}, "a, b"),
        ({"strict": "yes"}, "true/false"),
        ({"unknown": 1}, "선언하지 않은"),
    ]:
        try:
            validate_param_values(spec, values)
        except ValueError as error:
            assert expected in str(error), f"{values} → {error}"
        else:
            raise AssertionError(f"{values} 가 통과했다")


def test_unknown_timeframe_is_rejected() -> None:
    """적재가 모르는 주기를 전략이 요구하지 못하게 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "odd.py", _NEW_STRATEGY.replace('"timeframe": "1w"', '"timeframe": "3d"'))
        result = load_strategies(directory)
    assert result.valid == []
    assert "timeframe" in result.errors[0].message


def test_repo_strategies_satisfy_the_contract() -> None:
    """레포에 실제로 들어 있는 전략 파일이 규약을 통과한다 — 0건이면 실패다."""
    result = load_strategies()
    assert result.errors == [], f"규약을 못 지킨 전략이 있다: {result.errors}"
    assert len(result.valid) >= 2, f"검사한 전략이 {len(result.valid)}건이다 ({default_strategies_dir()})"

    for spec in result.valid:
        schema = to_form_schema(spec)
        controls = {field["control"] for field in schema["fields"]}
        assert controls <= KNOWN_CONTROLS, f"{spec.key}: 화면이 모르는 control {controls - KNOWN_CONTROLS}"
        # 선언한 default 만으로 저장이 성립해야 한다 — 폼을 열자마자 오류인 전략은 없다.
        validate_param_values(spec, {})


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests)}건 검사 · 실패 {failures}건")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
