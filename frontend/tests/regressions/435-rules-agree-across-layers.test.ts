// @vitest-environment node
//
// #435 (B-29·B-28) — 한 칸의 규칙을 세 층이 다르게 말하면, 문구를 따른 사용자가 다시 막힌다.
//
// `최대 보유 종목`·`하루 최대 매매` 는 세 층이 이렇게 어긋나 있었다:
//
//   화면      `min={1}`
//   zod       `PositiveInt()` = `gte: 0`   ← 0 을 통과시킨다
//   백엔드    `Field(gt=0)`                 ← 0 을 422 로 거절한다
//
// 그래서 `-2` 를 넣으면 「0 이상 값을 입력해주세요」가 뜨고, 시키는 대로 `0` 을 넣으면 서버가
// 거절한다. **문구를 따르면 다시 막힌다.** 이름도 거들었다 — `PositiveInt` 라 적혀 있지만
// 규칙은 「양수」가 아니라 「음수 아님」이었다.
//
// zod 스키마 머리의 주석은 처음부터 `max_positions?(gt0)` 라고 **옳게** 적어 두었다.
// 이 그물은 그 주석과 코드가 다시 갈라지는 것을 잡는다.
import { describe, expect, it } from "vitest";

import { BotCreateInSchema } from "@/schemas/bot/bot";

const BASE = {
  bot_nm: "규칙 대조용 봇",
  combine_rule: "AND",
  universe_kind: "POOL",
  bot_role: "READONLY",
  use_at: "Y",
  param_sources: {},
  strategies: [{ strategy_key: "pullback", params: { period: 20 }, param_sources: { period: "USER" } }],
};

const parse = (over: Record<string, unknown>) => BotCreateInSchema.safeParse({ ...BASE, ...over });

describe("한 칸의 규칙을 세 층이 같게 말한다", () => {
  // 백엔드는 `gt=0` 이다 (`bot_schema.py`). 화면도 `min={1}` 이다. zod 만 달랐다.
  for (const field of ["max_positions", "max_trades_per_day"] as const) {
    it(`${field}: 0 은 거절한다 — 서버가 거절하는 값을 클라이언트가 통과시키지 않는다`, () => {
      expect(parse({ [field]: 0 }).success).toBe(false);
    });

    it(`${field}: 음수도 거절한다`, () => {
      expect(parse({ [field]: -2 }).success).toBe(false);
    });

    it(`${field}: 1 은 통과한다 — 막는 범위가 넓어지지 않았다`, () => {
      expect(parse({ [field]: 1 }).success).toBe(true);
    });

    it(`${field}: 비워도 통과한다 — 「제한하지 않음」은 그대로다`, () => {
      expect(parse({}).success).toBe(true);
    });
  }

  // 0 이 뜻이 있는 칸은 종전대로 0 을 받는다 — 규칙을 한 방향으로 몰지 않았는지 본다.
  it("손절·익절·비중은 0 을 그대로 받는다", () => {
    expect(parse({ stop_loss_pct: 0, take_profit_pct: 0, alloc_per_symbol: 0 }).success).toBe(true);
  });
});
