FROM python:3.12-bookworm

RUN apt-get update && apt-get install -y \
    procps \
    htop \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV APP_HOME=/usr/app
WORKDIR $APP_HOME

# Python 의존성 설치
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-group dev

# 애플리케이션 코드 복사
COPY ./app ./app

# uvicorn 실행 위치
WORKDIR $APP_HOME/app
