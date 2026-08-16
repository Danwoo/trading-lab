import type { BotDetailOut, StrategyForm } from "@/schemas/bot/bot";
import { defaultParams } from "@/services/bot/botService";

/** 봇 하나가 싣는 전략 하나의 편집 상태. */
export interface StrategyDraft {
  strategyKey: string;
  params: Record<string, unknown>;
  /** 설정별 출처 — 실험대 스펙 §8.6.3 「출처가 남는다」. 손대지 않은 값은 여기 없다(선언 기본값). */
  paramSources: Record<string, "USER" | "AI_SUGGESTED">;
}

export interface BotDraft {
  bot_nm: string;
  bot_desc: string;
  universe_kind: "POOL" | "WATCHLIST" | "LIST";
  combine_rule: "AND" | "OR" | "SCORE";
  bot_role: "READONLY" | "PROPOSE" | "EXECUTE";
  alloc_per_symbol: number | null;
  max_positions: number | null;
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  max_trades_per_day: number | null;
}

/**
 * 새 봇의 출발 상태. **역할은 `READONLY` 로 시작한다** — 실주문은 마일스톤 2 의 no-go 이고,
 * 기본값이 판정·주문 쪽이면 사용자가 켠 적 없는 권한을 봇이 갖게 된다.
 */
export const NEW_BOT_DRAFT: BotDraft = {
  bot_nm: "",
  bot_desc: "",
  universe_kind: "WATCHLIST",
  combine_rule: "AND",
  bot_role: "READONLY",
  alloc_per_symbol: null,
  max_positions: null,
  stop_loss_pct: null,
  take_profit_pct: null,
  max_trades_per_day: null,
};

export const UNIVERSE_KIND_ITEMS = [
  { value: "WATCHLIST", label: "관심종목" },
  { value: "POOL", label: "종목군" },
  { value: "LIST", label: "직접 고른 목록" },
];

export const COMBINE_RULE_ITEMS = [
  { value: "AND", label: "모두 만족(AND)" },
  { value: "OR", label: "하나라도 만족(OR)" },
  { value: "SCORE", label: "점수 합산(SCORE)" },
];

/**
 * 봇이 할 수 있는 것. `EXECUTE`(실주문)는 목록에 두지 않는다 — 저장 자체는 백엔드가 허용하지만
 * 주문을 낼 엔진이 없어 **켜도 아무 일이 일어나지 않는다.** 고를 수 있게 두면 「켰으니 돈다」로
 * 읽힌다.
 */
export const BOT_ROLE_ITEMS = [
  { value: "READONLY", label: "보기만 한다" },
  { value: "PROPOSE", label: "제안까지 한다" },
];

/** 저장된 봇 → 편집 상태. 다시 열었을 때 저장한 조건이 그대로 보여야 한다(M2 완료 조건). */
export function toDraft(bot: BotDetailOut): BotDraft {
  return {
    bot_nm: bot.bot_nm,
    bot_desc: bot.bot_desc ?? "",
    universe_kind: bot.universe_kind,
    combine_rule: bot.combine_rule,
    bot_role: bot.bot_role,
    alloc_per_symbol: bot.alloc_per_symbol ?? null,
    max_positions: bot.max_positions ?? null,
    stop_loss_pct: bot.stop_loss_pct ?? null,
    take_profit_pct: bot.take_profit_pct ?? null,
    max_trades_per_day: bot.max_trades_per_day ?? null,
  };
}

/** 전략 선언의 기본값으로 채운 새 전략 한 줄. */
export function newStrategyDraft(form: StrategyForm): StrategyDraft {
  return { strategyKey: form.key, params: defaultParams(form), paramSources: {} };
}

/**
 * 저장 요청 본문. 빈 문자열은 **보내지 않는다** — `""` 를 그대로 실으면 "설명을 지웠다"와
 * "설명을 안 적었다"가 같아진다.
 */
export function toCreatePayload(draft: BotDraft, strategies: StrategyDraft[]) {
  return {
    ...draft,
    bot_desc: draft.bot_desc.trim() === "" ? undefined : draft.bot_desc.trim(),
    use_at: "Y" as const,
    param_sources: {},
    strategies: strategies.map((strategy) => ({
      strategy_key: strategy.strategyKey,
      params: strategy.params,
      param_sources: strategy.paramSources,
      weight: undefined,
    })),
  };
}
