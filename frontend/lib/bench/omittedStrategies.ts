import type { BotDetailOut, BotStrategyOut } from "@/schemas/bot/bot";

/** 사람이 읽는 전략 이름 — 전략 파일을 못 읽었으면 키라도 말한다. */
export function strategyName(strategy: BotStrategyOut): string {
  return strategy.form?.name ?? strategy.strategy_key;
}

/**
 * 검증이 **빼고 도는** 전략들 — 격자는 첫 전략 하나만 훑는다.
 *
 * 백엔드 `BacktestGridIn` 이 `strategy_key` 하나만 받으므로 계약상 다전략 봇을 표현할 수
 * 없다. 다전략 검증을 여기서 만들지는 않는다 — **못 한다는 말을 안 하는 것**이 결함이다.
 */
export function omittedStrategies(bot: BotDetailOut | null): BotStrategyOut[] {
  return bot === null ? [] : bot.strategies.slice(1);
}

/** 빠진 전략이 결과를 어떻게 흔드는지 — 합치는 방법마다 다르다. */
function consequenceOf(combineRule: BotDetailOut["combine_rule"]): string {
  if (combineRule === "OR") return "하나만 만족해도 사는 봇이라, 빠진 전략이 내던 신호가 결과에 없습니다.";
  if (combineRule === "SCORE") return "가중합으로 판정하는 봇이라, 빠진 전략의 몫만큼 점수가 달라집니다.";
  return "조건을 다 만족해야 사는 봇이라, 빠진 전략이 걸러 내던 자리까지 사고 든 결과입니다.";
}

/**
 * 「이 봇을 검증했다」가 참이 아닐 때 화면이 할 말 — 참이면 `null`.
 *
 * 같은 제품의 저장 경로는 이미 이 사실을 정확히 말하고 막는다(「전략이 2개 실려 있는데 이
 * 화면은 하나만 다룹니다」). 데이터가 지워지는 쪽에는 그물이 있고 판정이 틀리는 쪽에는
 * 없었다 — 같은 수준으로 말하게 한다.
 */
export function omittedStrategyNotice(bot: BotDetailOut | null): string | null {
  const omitted = omittedStrategies(bot);
  if (bot === null || omitted.length === 0) return null;
  const ran = strategyName(bot.strategies[0]);
  const names = omitted.map(strategyName).join(" · ");
  return (
    `이 봇에는 전략이 ${bot.strategies.length}개 실려 있는데 검증은 「${ran}」 하나만 돌립니다 — ` +
    `${names}은(는) 빠집니다. ${consequenceOf(bot.combine_rule)}`
  );
}
