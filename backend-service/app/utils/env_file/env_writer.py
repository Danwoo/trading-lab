"""`.env` 한 줄을 갈아 끼운다 — **최소한만 건드린다** (#225).

## 왜 이 방식인가

키를 저장할 자리는 각 서비스의 `.env` 다 (결정 로그 2026-08-19 — DB 에 두면 DB 없는 MCP
서비스에 닿지 않는다). 그리고 **백업 파일을 남기지 않는다**(같은 날 판정 — `.env.*` 는
gitignore 라 옛 키가 평문으로 쌓인다).

되돌릴 사본이 없다는 것이 이 모듈의 경계를 정한다: **바꾸는 것이 최소여야 한다.**

  · 이름이 같은 줄 **하나만** 갈고, 없으면 끝에 한 줄 더한다
  · 주석·빈 줄·다른 변수·줄 순서·따옴표 스타일을 보존한다
  · 같은 이름이 두 번 나오면 **쓰지 않고 거부한다** — 어느 쪽이 유효한지는 우리가 정할 것이
    아니고, 잘못 고르면 사용자가 되돌릴 사본이 없다
  · 파일이 없으면 거부한다 — 만드는 것은 `bootstrap_local_env.py` 의 일이다

## 값을 검증하는 이유

`.env` 는 한 줄 = 한 변수다. 값에 줄바꿈이 있으면 **그 뒤가 다음 변수로 읽힌다** — 키 하나를
넣었는데 다른 설정이 조용히 바뀐다. `#` 로 시작하는 값은 주석으로 읽힐 수 있다. 그래서
줄바꿈·널문자를 담은 값은 거부한다.

**값은 예외 메시지에 담지 않는다** — 이 예외는 API 응답이 된다.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class EnvWriteRejected(Exception):
    """쓰지 않고 거부했다. 메시지는 **값을 담지 않는다** — API 로 나간다."""


#: 값에 들어오면 다음 줄을 오염시키는 것들. 공백·탭은 허용한다(따옴표 없이도 안전하다).
_FORBIDDEN_IN_VALUE = ("\n", "\r", "\0")


def _rendered(name: str, value: str) -> str:
    """`.env` 한 줄. 값을 늘 겹따옴표로 감싼다 — 공백이 든 값도 한 줄로 남는다."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{name}="{escaped}"'


def _assignment_index(lines: list[str], name: str) -> int | None:
    """`name=` 대입이 있는 줄 번호. 주석은 대입이 아니다. 둘 이상이면 거부한다."""
    prefix = f"{name}="
    found = [i for i, line in enumerate(lines) if line.lstrip().startswith(prefix)]
    if len(found) > 1:
        raise EnvWriteRejected(
            f"{name} 이 이 파일에 {len(found)}번 나옵니다 — 어느 것이 유효한지 정할 수 없어 쓰지 않았습니다"
        )
    return found[0] if found else None


def set_env_value(path: Path, name: str, value: str) -> str:
    """`path` 의 `name` 을 `value` 로 만든다. 무엇을 했는지(`replaced`/`appended`)를 돌려준다.

    호출자가 `name` 을 **서버 소유 표에서** 꺼내 넘기는 것이 전제다 — 이 함수는 이름을
    검증하지 않는다(요청이 이름을 정하지 못하게 하는 것은 라우터의 몫이다).
    """
    if any(bad in value for bad in _FORBIDDEN_IN_VALUE):
        raise EnvWriteRejected("값에 줄바꿈이 들어 있습니다 — 그대로 쓰면 다음 줄이 다른 설정으로 읽힙니다")
    if not path.is_file():
        raise EnvWriteRejected(f"{path.name} 이 없습니다 — 먼저 bootstrap_local_env.py 로 만드세요")

    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    # 파일 끝 개행은 split 이 빈 문자열로 남긴다 — 그것을 그대로 두어 개행 유무를 보존한다.
    trailing_blank = lines and lines[-1] == ""
    body = lines[:-1] if trailing_blank else lines

    index = _assignment_index(body, name)
    if index is None:
        body = [*body, _rendered(name, value)]
        action = "appended"
    else:
        body[index] = _rendered(name, value)
        action = "replaced"

    rebuilt = "\n".join([*body, ""] if trailing_blank else body)
    _atomic_write(path, rebuilt)
    return action


def _atomic_write(path: Path, content: str) -> None:
    """임시 파일에 쓰고 `os.replace` 로 갈아 끼운다 — 도중에 죽어도 반쪽 파일이 남지 않는다.

    같은 디렉터리에 만드는 이유: `os.replace` 는 같은 파일시스템 안에서만 원자적이다.
    권한도 옮긴다 — `.env` 가 600 이면 새 파일도 600 이어야 한다.
    """
    mode = path.stat().st_mode & 0o777
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
