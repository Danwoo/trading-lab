/// <reference types="vite/client" />
// #434 — 화면의 숫자 칸에 **천장이 있는가** (클래스 전수).
//
// 「종목당 비중」 하나를 고쳤더니 같은 파일에 형제가 넷 더 있었고, 프론트만 보면 여섯 더
// 있었다(`weight`·`avg_price`·`target_price`·`alert_price`·`quantity`·`sort_ordr`). 인스턴스를
// 하나씩 고치면 다음 칸에서 같은 구멍이 다시 난다.
//
// 저장 컬럼에는 **항상** 천장이 있다. 화면이 그 선을 안 그으면 폼은 통과시키고 저장에서
// 422 가 나 사용자가 두 번 왕복한다. 백엔드 `tests/test_numeric_inputs_are_bounded.py` 가
// 같은 규칙을 요청 스키마 전수로 보고, 이 그물은 그 짝을 화면 쪽에서 본다.
import { describe, expect, it } from "vitest";
import { z } from "zod";

/**
 * 래퍼를 벗겨 실제 타입 스키마를 꺼낸다.
 *
 * `innerType` 만 따라가면 `Optional(...)` 이 안 벗겨진다 — 그 헬퍼는 `z.preprocess` 로 만든
 * 파이프라, 속을 `def.out` 에 둔다. 처음 이 그물을 그렇게 짰다가 **선택 입력 숫자 칸을
 * 통째로 못 보고** 초록이었다(`alloc_per_symbol`·`target_price`·`weight`·`bot_id` …).
 */
const unwrap = (schema: unknown): any => {
  let current: any = schema;
  for (let depth = 0; depth < 10; depth++) {
    const next = current?.def?.innerType ?? current?.def?.out;
    if (!next || next === current) break;
    current = next;
  }
  return current;
};

/** 저장 컬럼을 거치지 않는 칸 — 사유를 적고 면제한다. */
const EXEMPT: Record<string, string> = {};

const modules = import.meta.glob("../../schemas/**/*.ts", { eager: true }) as Record<string, Record<string, unknown>>;

type NumberField = { key: string; schema: z.ZodType };

const numberFields = (): NumberField[] => {
  const found: NumberField[] = [];
  for (const [path, module] of Object.entries(modules)) {
    const file = path.replace("../../", "");
    for (const [exportName, exported] of Object.entries(module)) {
      const shape = (exported as any)?.shape;
      if (!shape || typeof shape !== "object") continue;
      for (const [fieldName, fieldSchema] of Object.entries(shape)) {
        if (unwrap(fieldSchema)?.def?.type !== "number") continue;
        found.push({ key: `${file} ${exportName}.${fieldName}`, schema: fieldSchema as z.ZodType });
      }
    }
  }
  return found;
};

describe("저장 컬럼에 천장이 있는 칸은 화면이 먼저 거부한다 (전수)", () => {
  const fields = numberFields();

  it("스키마를 실제로 읽었다 — 0건이면 통과가 아니다", () => {
    expect(Object.keys(modules).length).toBeGreaterThan(10);
    expect(fields.length).toBeGreaterThan(10);
  });

  // 판독이 조용히 좁아지면 이 그물은 초록인 채로 죽는다. 선택 입력·필수 입력·정수·실수를
  // 하나씩 이름으로 박아, 무엇을 못 읽게 됐는지 그 자리에서 드러나게 한다.
  it("선택 입력 숫자 칸까지 읽는다", () => {
    const seen = new Set(fields.map(({ key }) => key));
    for (const key of [
      "schemas/bot/bot.ts BotSchema.alloc_per_symbol",
      "schemas/bot/bot.ts BotStrategyInSchema.weight",
      "schemas/watchlist/watchlist.ts WatchlistSchema.target_price",
      "schemas/backtest/backtest.ts BacktestRunInSchema.bot_id",
      "schemas/portfolio/portfolio.ts HoldingSchema.quantity",
    ]) {
      expect(seen).toContain(key);
    }
  });

  it("모든 숫자 칸이 말도 안 되는 큰 값을 거부한다", () => {
    const unbounded = fields
      .filter(({ key }) => !(key in EXEMPT))
      .filter(({ schema }) => schema.safeParse(1e18).success)
      .map(({ key }) => key);
    expect(unbounded).toEqual([]);
  });

  it("경계 안쪽 값은 그대로 통과한다 — 상한을 건다고 정상 입력을 막지 않는다", () => {
    const rejected = fields.filter(({ schema }) => !schema.safeParse(1).success).map(({ key }) => key);
    expect(rejected).toEqual([]);
  });
});
