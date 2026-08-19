"""데이터 소스 키 **상태** 조회 스키마 — 「어디에 무엇을 넣어야 하나」를 화면이 답하게 (#225).

**값을 담는 필드가 없다.** 이 응답은 API 로 나가므로, 키도 그 앞자리도 싣지 않는다 —
일부만으로도 전체를 좁히는 단서가 된다. 화면이 알아야 할 것은 「채워졌는가」뿐이다.
"""

from pydantic import BaseModel, Field


class DataKeyStatusOut(BaseModel):
    #: 소스 id — 어댑터 선택이 아니라 화면 표시·요청 식별용이다.
    source: str
    #: `.env` 의 변수 이름. 사용자가 파일을 직접 고칠 때 찾을 이름이라 그대로 보인다.
    setting: str
    #: 지금 채워져 있는가. **불리언이다** — 값도 앞자리도 아니다.
    filled: bool
    #: 비밀값인가. 연락처처럼 「우리가 누구인지」인 항목은 감출 것이 아니다.
    secret: bool
    #: 없을 때 어디서 받는지. 서버가 정본이다 — 화면이 다시 쓰면 항목명과 갈린다.
    guidance: str | None = None


class DataKeyStatusListOut(BaseModel):
    items: list[DataKeyStatusOut]
    total_count: int


class DataKeySaveIn(BaseModel):
    """키 저장 요청 — **소스 id 와 값만** 받는다.

    파일 경로도 변수 이름도 요청이 정하지 못한다. 서버가 소스 id 로 표를 조회해 꺼내므로,
    경로 조작이나 임의 변수 덮어쓰기가 도달할 수 없다 (#225).
    """

    source: str = Field(..., max_length=40)
    value: str = Field(..., max_length=500)


class DataKeySaveOut(BaseModel):
    source: str
    setting: str
    #: `replaced` 또는 `appended` — 무엇을 했는지 화면이 말할 수 있게.
    action: str
    #: 설정은 기동 시 읽는다 — 감수한 것을 감추지 않는다 (결정 로그 2026-08-19).
    restart_required: bool


class DataKeyProbeOut(BaseModel):
    #: 키가 통했는가.
    ok: bool
    #: 실제로 물어봤는가. 확인 호출이 없는 소스는 `False` 다 — 「실패」와 다르다.
    checked: bool
    #: 사람이 읽을 사유. **값을 담지 않는다.**
    detail: str
