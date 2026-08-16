"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";

/**
 * 레일 항목 id → 그 패널이 그리는 것.
 *
 * 여기 없는 항목은 `ProductPanel` 이 `item.pending` 을 대신 보여준다 — 그래서 **레지스트리에
 * 있음 = 패널이 실재함**이고, `pending` 은 「아직 없음」의 유일한 표식이다. 둘이 어긋나면
 * (배선했는데 pending 이 남았거나, pending 을 지웠는데 배선이 없거나) 화면이 거짓말을 하므로
 * `railPanelContent.test.tsx` 가 그 어긋남을 막는다.
 *
 * 동적 import 인 이유 — 제품 셸은 모든 화면이 지나가는 자리다. 여기서 정적으로 끌어오면
 * 봇을 안 쓰는 화면도 봇 코드를 받는다.
 */
const BotWorkbenchPanel = dynamic(() => import("@/components/features/Bot/BotWorkbench").then((m) => m.BotWorkbench), {
  ssr: false,
  loading: () => <p className="text-sm text-ink-muted">불러오는 중입니다…</p>,
});

export const RAIL_PANEL_CONTENT: Record<string, ComponentType> = {
  bot: () => <BotWorkbenchPanel inPanel />,
};
