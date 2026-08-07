# [가이드 6/8] core/container.py — DI 등록 (config→service→wiring).
# 복사 후 service provider·wiring 모듈을 새 도메인으로. 외부 연결은 client=Singleton, repository=Factory 추가.
# 새 라우터는 wiring modules 에 넣어야 @inject 가 동작. 상세: CLAUDE.md "DI 등록".

from core.config import settings
from dependency_injector import containers, providers
from services.example.example_service import ExampleService


class Container(containers.DeclarativeContainer):
    # Config (유일 settings 경계)
    config = providers.Object(settings)

    # Service (외부 의존 0 인 echo 예시 — 실제 도메인은 여기에 client/repository 를 주입)
    example_service = providers.Factory(ExampleService)

    wiring_config = containers.WiringConfiguration(modules=["routers.example.example_router"])
