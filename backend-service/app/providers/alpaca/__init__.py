"""Alpaca 어댑터 — 미국 일봉·분봉·시세. **키 필요** (구현설계 §8 Q9 확정 소스).

키는 ID·시크릿 **쌍**이라 이 레포의 `api_key: str | None` 한 자리에 `"<KEY_ID>:<SECRET>"` 로
담는다. 분리 규칙은 `client.py` 가 소유한다 — 형식이 소스 밖으로 새지 않게.
"""

SOURCE = "alpaca"
