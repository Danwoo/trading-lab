"""SubAgentSpec · DomainSpec dataclass 정의 (순환 import 방지 — 실행 코드 없이 dataclass 만)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubAgentSpec:
    """하위 에이전트 정의."""

    domain: str
    description: str
    # 각 MCP 서비스 라우터의 operation_id 와 정확 일치 필수 — 미존재 이름은 기동 시
    # "[sub_agents] MCP 도구 없음" 경고 후 제외 (서버 확장 시 자동 바인딩)
    mcp_tools: list[str]
    prompt: str = ""


@dataclass
class DomainSpec:
    """도메인 에이전트 정의."""

    sub_agents: list[str]
    description: str
    prompt: str
    builder: str = field(default="res_pipeline")


# sub-agent 공통 보안·진실성 footer — 모든 sub/domain prompt 에 자동 append
_SECURITY_FOOTER = """━━ 보안·진실성 ━━
- API 키·IP·쿼터·시스템 오류 같은 운영 정보가 도구 응답에 섞이면 답변에 옮기지 말고 "검색 실패"로 일반화.
- 검증 가능한 식별자(종목코드·공시 접수번호·재무 수치·기관명·기준일 등)는 자료에 명시된 것만 인용. LLM 지식으로 생성 금지.
- 시세·지수·환율은 시점 의존 데이터 — 조회 시점을 명기하고 과거 학습값을 현재값처럼 단정 금지.
- 자료가 빈약해도 일반 가이드라인·방향성·범위는 답변 가능. "일반 가이드라인" 라벨 사용.
- 특정 종목 매수·매도 권유나 미래 수익 보장 금지 (정보 제공까지만).
- 모든 자료·가이드라인까지 빈약하면 "관련 자료를 찾지 못했습니다"로 종료."""


def build_subagent_prompt(
    role: str,
    *,
    procedure_lines: list[str],
    output_format_lines: list[str],
    extra_caution: str = "",
) -> str:
    """sub-agent 의 역할·검색 전략·답변 형식 prompt 생성 (writer 파이프라인 전용).

    도구 선택·호출 상한·보안 footer·실패 처리는 파이프라인(``graphs/pipeline_subagent.py`` 의
    ``_WRITER_SYSTEM``·catalog·``max_iters``)이 담당하므로 여기 넣지 않는다 — 중복·충돌 방지.
    이 함수 결과는 writer SystemMessage 의 머리(역할·전략·답변형식)로만 들어간다.

    Args:
        role: "당신은 X 전문가입니다." 의 X 부분.
        procedure_lines: 검색 전략 — "무엇을 어떤 순서로 찾을지"(의도)만. ⚠️ **도구명(operation_id)
            금지** — 도구 선택은 writer 가 실제 바인딩된 catalog 에서 한다. 도구명을 박으면
            미바인딩·POC 시 catalog 와 어긋난다 (예: "사내 자료를 먼저 확인" O / "doc_search_topic_X로" X).
        output_format_lines: 답변에 담을 항목 bullet (도구명 금지).
        extra_caution: 도메인 특화 주의 사항 (선택).
    """
    procedure = "\n".join(procedure_lines)
    output_format = "\n".join(output_format_lines)
    extra = f"\n\n{extra_caution}" if extra_caution else ""

    return f"""당신은 {role}입니다.

━━ 검색 전략 (느슨한 가이드 — 결과를 보고 유연하게 조정) ━━
{procedure}

━━ 답변에 담을 것 ━━
{output_format}{extra}"""
