"""전략 파일을 읽어 검증하고, 화면이 먹는 폼 스키마로 옮긴다.

규약 정본은 `.docs/specs/2026-08-15-strategy-contract.md` 다. 전략 파일은 우리 패키지를
import 하지 않는 순수 데이터 선언(`STRATEGY` 딕셔너리)이므로, 여기의 스키마가 **어디가 왜
틀렸는지**를 말해 주는 유일한 자리다.

판정 함수 셋(`indicators`·`entry`·`exit`)은 **존재만 확인하고 호출하지 않는다** — 실행할
백테스트 엔진이 아직 없다.
"""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# 규약 §3.3 — 목록 밖의 주기는 거부한다. 열어 두면 적재가 모르는 주기를 전략이 요구하게 되고
# 그 실패가 백테스트 시점까지 미뤄진다.
TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "1d", "1w", "1M")

# 규약 §3.4 — 타입에서 폼 컨트롤로. 화면은 control 세 종만 그린다.
_CONTROL_BY_TYPE = {
    "int": "number",
    "float": "number",
    "percent": "number",
    "choice": "select",
    "bool": "toggle",
}
_NUMERIC_TYPES = ("int", "float", "percent")

# 전략 파일이 갖춰야 하는 판정 함수 (규약 §2)
REQUIRED_CALLABLES = ("indicators", "entry", "exit")

_KEY_PATTERN = r"^[a-z][a-z0-9_]{1,39}$"
_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"


class StrategyChoice(BaseModel):
    value: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)


class StrategyParam(BaseModel):
    """파라미터 선언 하나 — 폼 필드 하나가 된다."""

    model_config = {"extra": "forbid"}

    name: str = Field(pattern=_NAME_PATTERN)
    label: str = Field(min_length=1, max_length=60)
    type: Literal["int", "float", "percent", "choice", "bool"]
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[StrategyChoice] | None = None
    unit: str | None = Field(default=None, max_length=10)
    help: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_by_type(self) -> "StrategyParam":
        if self.type in _NUMERIC_TYPES:
            self._check_numeric()
        elif self.type == "choice":
            self._check_choice()
        elif self.type == "bool" and not isinstance(self.default, bool):
            raise ValueError(f"'{self.name}': bool 파라미터의 default 는 true/false 여야 합니다")
        return self

    def _check_numeric(self) -> None:
        missing = [key for key in ("min", "max", "step") if getattr(self, key) is None]
        if missing:
            raise ValueError(f"'{self.name}': {self.type} 파라미터는 {', '.join(missing)} 를 함께 선언해야 합니다")
        if self.min >= self.max:
            raise ValueError(f"'{self.name}': min({self.min}) 이 max({self.max}) 보다 작아야 합니다")
        if self.step <= 0:
            raise ValueError(f"'{self.name}': step 은 0 보다 커야 합니다")
        if isinstance(self.default, bool) or not isinstance(self.default, (int, float)):
            raise ValueError(f"'{self.name}': {self.type} 파라미터의 default 는 숫자여야 합니다")
        if self.type == "int" and not float(self.default).is_integer():
            raise ValueError(f"'{self.name}': int 파라미터의 default 는 정수여야 합니다")
        if not self.min <= self.default <= self.max:
            raise ValueError(f"'{self.name}': default({self.default}) 가 선언한 범위 {self.min}~{self.max} 밖입니다")

    def _check_choice(self) -> None:
        if not self.choices or len(self.choices) < 2:
            raise ValueError(f"'{self.name}': choice 파라미터는 choices 를 2개 이상 선언해야 합니다")
        values = [choice.value for choice in self.choices]
        if len(set(values)) != len(values):
            raise ValueError(f"'{self.name}': choices 의 value 가 중복됩니다")
        if self.default not in values:
            raise ValueError(f"'{self.name}': default({self.default!r}) 가 choices 에 없습니다")


class StrategySpec(BaseModel):
    """전략 파일이 선언한 것 — 검증을 통과한 모양."""

    model_config = {"extra": "forbid"}

    key: str = Field(pattern=_KEY_PATTERN)
    name: str = Field(min_length=1, max_length=60)
    timeframe: Literal[TIMEFRAMES]  # type: ignore[valid-type]
    params: list[StrategyParam] = Field(max_length=30)
    summary: str | None = Field(default=None, max_length=200)

    @field_validator("params")
    @classmethod
    def _unique_names(cls, params: list[StrategyParam]) -> list[StrategyParam]:
        names = [param.name for param in params]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise ValueError(f"파라미터 이름이 중복됩니다: {', '.join(duplicated)}")
        return params


class StrategyLoadError(BaseModel):
    """읽지 못한 전략 하나 — 목록에서 빠지되 이유는 남는다."""

    source: str
    message: str


class StrategyLoadResult(BaseModel):
    """깨진 전략 하나가 목록 전체를 죽이지 않는다 (규약 §4)."""

    valid: list[StrategySpec]
    errors: list[StrategyLoadError]

    def by_key(self, key: str) -> StrategySpec | None:
        return next((spec for spec in self.valid if spec.key == key), None)


def default_strategies_dir() -> Path:
    """레포 루트의 `strategies/`. 전략은 사용자가 git 에 커밋하는 자기 자산이라 서비스 밖에 산다."""
    return Path(__file__).resolve().parents[4] / "strategies"


def load_strategies(directory: Path | str | None = None) -> StrategyLoadResult:
    """디렉터리의 전략 파일을 전부 읽는다. `_` 로 시작하는 파일은 건너뛴다."""
    root = Path(directory) if directory else default_strategies_dir()
    if not root.is_dir():
        return StrategyLoadResult(
            valid=[],
            errors=[StrategyLoadError(source=str(root), message="전략 디렉터리가 없습니다")],
        )

    valid: list[StrategySpec] = []
    errors: list[StrategyLoadError] = []
    seen_keys: dict[str, str] = {}

    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = _load_one(path)
        except _StrategyFileError as error:
            errors.append(StrategyLoadError(source=path.name, message=str(error)))
            continue

        if spec.key in seen_keys:
            errors.append(
                StrategyLoadError(
                    source=path.name,
                    message=f"key '{spec.key}' 가 {seen_keys[spec.key]} 와 겹칩니다",
                )
            )
            continue
        seen_keys[spec.key] = path.name
        valid.append(spec)

    return StrategyLoadResult(valid=valid, errors=errors)


def to_form_schema(spec: StrategySpec) -> dict[str, Any]:
    """화면이 먹는 모양으로 옮긴다 (규약 §5).

    `type` 은 내보내지 않는다 — 화면이 type 을 알면 타입이 늘 때마다 화면이 따라 바뀐다.
    """
    return {
        "key": spec.key,
        "name": spec.name,
        "summary": spec.summary,
        "timeframe": spec.timeframe,
        "fields": [_to_field(param) for param in spec.params],
    }


def validate_param_values(spec: StrategySpec, values: dict[str, Any]) -> dict[str, Any]:
    """사용자가 채운 값이 선언한 범위 안인지 본다. 빠진 값은 default 로 채운다.

    선언에 없는 이름이 오면 거부한다 — 전략이 안 보는 값을 저장해 두면 나중에 「왜 이렇게
    샀지」를 되짚을 때 없는 설정이 근거로 보인다.
    """
    unknown = sorted(set(values) - {param.name for param in spec.params})
    if unknown:
        raise ValueError(f"'{spec.key}' 가 선언하지 않은 파라미터입니다: {', '.join(unknown)}")

    resolved: dict[str, Any] = {}
    for param in spec.params:
        if param.name not in values:
            resolved[param.name] = param.default
            continue
        resolved[param.name] = _coerce(param, values[param.name])
    return resolved


class _StrategyFileError(Exception):
    """전략 파일 하나를 못 읽은 이유 — 사람이 읽을 문장으로만 쓴다."""


def _to_field(param: StrategyParam) -> dict[str, Any]:
    field: dict[str, Any] = {
        "name": param.name,
        "label": param.label,
        "control": _CONTROL_BY_TYPE[param.type],
        "default": param.default,
    }
    if param.type in _NUMERIC_TYPES:
        field["min"] = _as_declared(param, param.min)
        field["max"] = _as_declared(param, param.max)
        field["step"] = _as_declared(param, param.step)
        unit = param.unit or ("%" if param.type == "percent" else None)
        if unit:
            field["unit"] = unit
    elif param.type == "choice":
        field["options"] = [choice.model_dump() for choice in param.choices or []]
    if param.help:
        field["help"] = param.help
    return field


def _as_declared(param: StrategyParam, value: float | None) -> float | int | None:
    """int 파라미터의 경계는 정수로 내보낸다 — 폼과 오류 메시지에 `1.0~52.0` 이 보이면 안 된다."""
    if value is None:
        return None
    return int(value) if param.type == "int" else value


def _coerce(param: StrategyParam, value: Any) -> Any:
    if param.type == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"'{param.name}': true/false 여야 합니다 (받은 값 {value!r})")
        return value
    if param.type == "choice":
        allowed = [choice.value for choice in param.choices or []]
        if value not in allowed:
            raise ValueError(f"'{param.name}': {', '.join(allowed)} 중 하나여야 합니다 (받은 값 {value!r})")
        return value

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{param.name}': 숫자여야 합니다 (받은 값 {value!r})")
    if param.type == "int":
        if not float(value).is_integer():
            raise ValueError(f"'{param.name}': 정수여야 합니다 (받은 값 {value!r})")
        value = int(value)
    if not param.min <= value <= param.max:
        low, high = _as_declared(param, param.min), _as_declared(param, param.max)
        raise ValueError(f"'{param.name}': {low}~{high} 범위여야 합니다 (받은 값 {value!r})")
    return value


def _load_one(path: Path) -> StrategySpec:
    module = _import_module(path)

    declaration = getattr(module, "STRATEGY", None)
    if declaration is None:
        raise _StrategyFileError("STRATEGY 선언이 없습니다")
    if not isinstance(declaration, dict):
        raise _StrategyFileError(f"STRATEGY 는 딕셔너리여야 합니다 (받은 것 {type(declaration).__name__})")

    missing = [name for name in REQUIRED_CALLABLES if not isinstance(getattr(module, name, None), Callable)]
    if missing:
        raise _StrategyFileError(f"판정 함수가 없습니다: {', '.join(missing)}")

    try:
        return StrategySpec.model_validate(declaration)
    except ValidationError as error:
        raise _StrategyFileError(_readable(error)) from error


def _import_module(path: Path) -> ModuleType:
    """전략 파일을 import 한다 — 임의 코드 실행이다 (규약 §4, 로컬 전용 전제)."""
    module_name = f"_strategy_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise _StrategyFileError("파이썬 모듈로 읽을 수 없습니다")
    module = importlib.util.module_from_spec(spec)
    # 전략 파일끼리 이름이 겹쳐도 서로를 덮지 않게, import 가 끝나면 sys.modules 에서 뺀다.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001 — 남의 파일이라 무엇이 터질지 모른다
        raise _StrategyFileError(f"파일을 읽다 실패했습니다: {error}") from error
    finally:
        sys.modules.pop(module_name, None)
    return module


def _readable(error: ValidationError) -> str:
    """pydantic 오류를 전략 작성자가 읽을 한 문장으로 줄인다."""
    messages = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "STRATEGY"
        messages.append(f"{location}: {detail['msg']}")
    return " / ".join(messages)
