# [가이드 5/8] routers/<도메인>/ — tool 표면. operation_id=tool 이름, docstring=설명, In/Out=스키마, 라우트 추가=tool 추가.
# 복사 후 prefix·라우트를 새 도메인으로. operation_id 는 소비 쪽이 이 문자열로 바인딩하니 바뀌면 lockstep.
# docstring 에 도구 선택 단서(용도·형제 구분·0건), few_shot 에 호출 예시. router 는 로직 없이 위임만.

from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.example.example_schema import EchoIn, EchoOut
from services.example.example_service import ExampleService
from utils.common.few_shot import few_shot

router = APIRouter(prefix="/example", dependencies=[Depends(verify_access_token)])


@router.post(
    "/echo",
    operation_id="example_echo",
    openapi_extra=few_shot(
        [
            {"질문": "hello 를 그대로 돌려줘", "호출": {"text": "hello"}},
            {"질문": "안녕하세요 echo 해줘", "호출": {"text": "안녕하세요"}},
        ]
    ),
)
@inject
async def echo(
    body: EchoIn,
    example_service: ExampleService = Depends(Provide[Container.example_service]),
) -> EchoOut:
    """입력 텍스트를 그대로 돌려주는 최소 예시 tool (외부 의존 0). 복사 후 이 자리에 실제 조회/검색 tool 을
    작성한다 — docstring 에 용도·반환 필드·형제 tool 구분·입력 팁·0건 해석을 적어 소비 에이전트의 도구
    선택을 돕는다 (도구 선택 규칙의 SoT 는 이 docstring 이다)."""
    return await example_service.echo(body)
