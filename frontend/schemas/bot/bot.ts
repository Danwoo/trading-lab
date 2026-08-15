// schemas/bot/bot.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import {
  Field,
  FloatRange,
  Optional,
  PositiveFloat,
  PositiveInt,
  StrRange,
  array,
  enums,
  object,
  record,
} from "@/lib/zod/helpers";

// 백엔드 계약: backend-service/app/schemas/bot/bot_schema.py
//   Bot{bot_desc?(500), combine_rule(AND|OR|SCORE), universe_kind(POOL|WATCHLIST|LIST),
//       universe_ref?, alloc_per_symbol?(ge0), max_positions?(gt0), stop_loss_pct?(0~100),
//       take_profit_pct?(ge0), max_trades_per_day?(gt0), bot_role(READONLY|PROPOSE|EXECUTE),
//       use_at(1), param_sources}
//   BotCreateIn = Bot + bot_nm(1~100) + strategies[]
// 어휘 셋(combine_rule·universe_kind·bot_role)은 alembic 0014 의 CHECK 제약과 같아야 한다 —
// 한쪽만 늘리면 저장이 500 으로 터진다 (backend tests/test_bot_schema_sql_consistency.py 가 대조).

export const COMBINE_RULES = ["AND", "OR", "SCORE"] as const;
export const UNIVERSE_KINDS = ["POOL", "WATCHLIST", "LIST"] as const;
export const BOT_ROLES = ["READONLY", "PROPOSE", "EXECUTE"] as const;
/** 설정 하나가 어디서 왔나 — 실험대 스펙 §8.6.3 「출처가 남는다」 */
export const PARAM_SOURCES = ["USER", "AI_SUGGESTED"] as const;

const ParamSourceMap = record(enums(PARAM_SOURCES));

export const BotStrategyInSchema = object({
  strategy_key: StrRange(1, 40),
  // 값의 타입·범위는 전략 선언이 정하므로 여기서 좁히지 않는다 — 백엔드가 선언에 대해 검증한다.
  params: record(z.any()),
  param_sources: ParamSourceMap,
  weight: Optional(PositiveFloat()),
});

export const BotSchema = object({
  bot_nm: StrRange(1, 100),
  bot_desc: Optional(Field({ max_length: 500 }).str()),
  combine_rule: enums(COMBINE_RULES),
  universe_kind: enums(UNIVERSE_KINDS),
  universe_ref: Optional(record(z.any())),
  alloc_per_symbol: Optional(PositiveFloat()),
  max_positions: Optional(PositiveInt()),
  stop_loss_pct: Optional(FloatRange(0, 100)),
  take_profit_pct: Optional(PositiveFloat()),
  max_trades_per_day: Optional(PositiveInt()),
  bot_role: enums(BOT_ROLES),
  use_at: enums(["Y", "N"]),
  param_sources: ParamSourceMap,
});

// 전략 없는 봇은 아무 판정도 못 한다 — 백엔드도 빈 목록을 거부한다.
export const BotCreateInSchema = BotSchema.extend({
  strategies: array(BotStrategyInSchema).min(1),
});
// 전략 목록을 안 보내면 건드리지 않는다. 보내면 통째로 갈아 끼운다.
export const BotUpdateInSchema = BotSchema.extend({
  strategies: Optional(array(BotStrategyInSchema).min(1)),
});

export type Bot = z.infer<typeof BotSchema>;
export type BotStrategyIn = z.infer<typeof BotStrategyInSchema>;
export type BotOut = Bot & CommonEntity & { bot_id: number };

/** 폼 필드 하나 — `control` 로 그리고 나머지는 그대로 흘려 넣는다 (전략 규약 §5). */
export interface StrategyField {
  name: string;
  label: string;
  control: "number" | "select" | "toggle";
  default: unknown;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  options?: { value: string; label: string }[];
  help?: string;
}

/** 전략 파일이 선언한 것에서 만들어진 폼. 새 전략이 늘어도 이 모양은 안 바뀐다. */
export interface StrategyForm {
  key: string;
  name: string;
  summary?: string | null;
  timeframe: string;
  fields: StrategyField[];
}

export interface BotStrategyOut {
  bot_strategy_id: number;
  strategy_key: string;
  params: Record<string, unknown>;
  param_sources: Record<string, string>;
  weight: number | null;
  sort_order: number;
  /** 전략 파일이 사라졌으면 null 이고 `missing_reason` 이 온다 — 빈 폼을 조용히 보여주지 않는다. */
  form: StrategyForm | null;
  missing_reason: string | null;
}

export type BotDetailOut = BotOut & { strategies: BotStrategyOut[] };

export interface BotsOut {
  items: BotOut[];
  total_count: number;
}

/**
 * 전략 목록. `errors` 가 비어 있지 않으면 **못 읽은 전략이 있다는 뜻**이라 화면이 이유를 보여준다 —
 * 「전략이 없다」와 「전략을 못 읽었다」는 다르다.
 */
export interface StrategyCatalogOut {
  items: StrategyForm[];
  errors: { source: string; message: string }[];
}
