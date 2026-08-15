"use client";

import { useOnDemand } from "@/hooks/terminal/useOnDemand";
import { selectBotList } from "@/services/bot/botService";
import type { BotOut } from "@/schemas/bot/bot";
import type { PanelData } from "@/types/terminal/provenance";

/** 보드의 「내 봇」 자리가 한 번에 보여주는 수. 목록 화면이 아니라 **있는지 없는지**를 보는 자리다. */
const ROSTER_PAGE_SIZE = 20;

/**
 * 보드가 「봇이 0개인가」를 **물어봐서** 안다 — 화면 결정 §21.4 의 빈 상태는 지어낸 것이 아니라
 * 실제로 0건일 때만 떠야 한다.
 *
 * `selectBotList` 는 서버가 실패를 알리면 `null` 을 준다(정상 응답이면 `{items, total_count}`).
 * 그래서 **「0개」와 「못 읽었다」가 값으로 갈린다** — 못 읽은 것을 0개로 그리면 화면이
 * 「봇을 만드세요」라고 말하는데 실제로는 이미 만든 봇이 안 보이는 것일 수 있다.
 */
export function useBotRoster(): PanelData<BotOut[]> {
  return useOnDemand<BotOut[]>({
    group: "bench-bot-roster",
    enabled: true,
    source: "내 봇",
    fetcher: async () => {
      const result = await selectBotList({ skip: 0, take: ROSTER_PAGE_SIZE });
      if (result === null) throw new Error("봇 목록을 불러오지 못했습니다");
      // 목록은 조회 시점 계산이라 서버가 기준 시각을 주지 않는다 — 없는 값을 지어내지 않는다.
      return { items: result.items, asOf: null };
    },
  });
}
