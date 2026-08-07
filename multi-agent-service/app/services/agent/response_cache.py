"""응답 캐시 — 정확한 쿼리 문자열 단위 간이 LRU (TTL + 최대 엔트리 수).

멀티 에이전트 응답은 비결정적이고 시점 의존(시장 트렌드 등)이라 프로덕션은 disabled 권장.
멀티턴 대화 맥락은 캐시 대상 아님 — 1턴 단일 쿼리만 캐싱.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from collections.abc import Iterable


def make_cache_key(email: str, gid: int, enabled_mcps: Iterable[str], question: str) -> str:
    """(email, gid, enabled_mcps, question) 결정론적 캐시 키.

    bare question 만으로 키를 잡으면 다른 사용자·세션·도구조합의 답변이 섞여 PII 교차 유출 위험이 있다.
    사용자·세션·활성 MCP 집합·질문을 모두 키에 포함해 격리한다 (native·example-ai 공통).
    """
    mcps = sorted(frozenset(enabled_mcps or ()))
    return json.dumps([email or "", int(gid or 0), mcps, question or ""], ensure_ascii=False)


class ResponseCache:
    def __init__(self, config) -> None:
        self._enabled = config.MA_RESPONSE_CACHE_ENABLED
        self._max_entries = config.MA_RESPONSE_CACHE_MAX_ENTRIES
        self._ttl_s = config.MA_RESPONSE_CACHE_TTL_S
        self._store: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        if not self._enabled or self._max_entries <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if now - ts > self._ttl_s:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: str) -> None:
        if not self._enabled or self._max_entries <= 0 or not value:
            return
        now = time.monotonic()
        with self._lock:
            self._store[key] = (now, value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)
