# strategies — 전략 파일

전략 하나가 파일 하나입니다. 여기에 `.py` 를 하나 더 놓으면 봇 만들기 화면의 전략 목록에 바로 뜹니다 — **화면 코드를 고칠 필요가 없습니다.**

규약 정본은 [`.docs/specs/2026-08-15-strategy-contract.md`](../.docs/specs/2026-08-15-strategy-contract.md) 입니다. 여기서는 쓰는 법만 적습니다.

## 파일 하나가 갖춰야 하는 것

```python
STRATEGY = {           # ← 이 선언이 폼을 만든다
    "key": "...",      # 저장된 봇이 이 전략을 가리키는 이름. 한 번 정하면 안 바꾼다
    "name": "...",     # 화면에 보이는 이름
    "timeframe": "1d", # 이 전략이 보는 캔들 주기
    "params": [...],   # 조절할 수 있는 값들
}

def indicators(bars, params): ...   # 이 전략이 보는 값
def entry(ctx): ...                 # 산다고 판정하면 True
def exit(ctx): ...                  # 판다고 판정하면 True
```

전략 파일은 **아무것도 import 하지 않습니다.** `STRATEGY` 는 순수 데이터이고, 로더가 스키마로 검증해 어디가 왜 틀렸는지 알려 줍니다.

## 파라미터 타입

| `type` | 폼 | 같이 적어야 하는 것 |
|---|---|---|
| `int` · `float` · `percent` | 숫자 입력 | `min` · `max` · `step` |
| `choice` | 선택 | `choices` (2개 이상) |
| `bool` | 켜기/끄기 | — |

새 타입이 필요해 보이면 먼저 이 다섯으로 표현되는지 보십시오. **타입을 늘리면 화면도 같이 고쳐야 합니다** (규약 §3.4).

## 캔들 주기

`1m` `5m` `15m` `30m` `1h` `1d` `1w` `1M` — 목록 밖은 거부됩니다.

전략마다 따로 선언하므로, 월봉 필터와 일봉 진입을 한 봇에 실으면 멀티 타임프레임이 그대로 성립합니다.

## 지금 도는 것과 안 도는 것

`STRATEGY` 선언은 **검증되고 폼이 됩니다.** `indicators`·`entry`·`exit` 는 **있는지만 검사하고 호출하지 않습니다** — 실행할 백테스트 엔진이 아직 없습니다. 규약을 지켜 미리 적어 두면 엔진이 생길 때 그대로 돕니다.

## 확인

```bash
cd backend-service/app && APP_ENV=development uv run python -c "
from services.bot.strategy_loader import load_strategies
for s in load_strategies().valid: print(s.key, '·', s.name, '·', len(s.params), '개 파라미터')
for e in load_strategies().errors: print('실패:', e.source, '—', e.message)
"
```
