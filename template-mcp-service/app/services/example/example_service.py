# [가이드 4/8] services/<도메인>/ — 도메인 로직. router 는 위임만.
# 복사 후 echo 를 실제 로직으로. 외부 API·DB 는 client·repository 를 주입받아 호출 (container 에 provider 추가).

from schemas.example.example_schema import EchoIn, EchoOut


class ExampleService:
    """입력을 그대로 돌려주는 최소 예시 (외부 의존 없음)."""

    async def echo(self, body: EchoIn) -> EchoOut:
        return EchoOut(echo=body.text, length=len(body.text))
