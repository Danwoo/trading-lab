"""Redis 연결 (외부타입 redis.Redis) — BM25 sparse 모델 pickle 저장소. 실제 접속은 첫 명령 시점(lazy)."""

import redis


def get_redis_client(config) -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_DB_HOST,
        port=config.REDIS_DB_PORT,
        password=config.REDIS_DB_PASSWORD or None,
        decode_responses=False,
    )
