"""데이터 소스 키 **상태** 조회 스키마 — 「어디에 무엇을 넣어야 하나」를 화면이 답하게 (#225).

**값을 담는 필드가 없다.** 이 응답은 API 로 나가므로, 키도 그 앞자리도 싣지 않는다 —
일부만으로도 전체를 좁히는 단서가 된다. 화면이 알아야 할 것은 「채워졌는가」뿐이다.
"""

from pydantic import BaseModel


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
