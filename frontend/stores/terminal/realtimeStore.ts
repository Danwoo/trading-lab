"use client";

import { useSyncExternalStore } from "react";
import { subscribeSymbolChange } from "@/stores/terminal/contextActions";
import { useContextStore } from "@/stores/terminal/contextStore";
import { createArbiter, NullTransport } from "@/lib/terminal/realtimeArbiter";
import type { ArbiterState } from "@/lib/terminal/realtimeArbiter";

/**
 * 동시 1종목 구독을 실제로 소유하는 싱글턴 (설계 §3.6). **이 파일이 `switchTo` 를 호출하는
 * 유일한 곳이다.**
 *
 * #322 — 이 모듈은 즉시 평가되지 않는다. capability 게이트 뒤에서 지연 로드되는 패널
 * (`PanelSlot` → `lazy(definition.load)`)이 처음 마운트될 때에야 import 체인을 타고 평가된다.
 * "문맥 스토어 초기값과 중재자 초기 상태가 둘 다 idle/null 이라 부팅 시점 동기화가 필요 없다"
 * 던 원래 가정은 이 모듈이 앱 부팅과 함께 즉시 평가된다는 전제였다 — 실제로는 세션 최초
 * 종목 선택이 이 모듈보다 먼저 일어난다(선택이 region 을 풀어야 패널이 마운트되고, 마운트
 * 되어야 이 모듈이 평가된다). `subscribeSymbolChange` 는 등록 **이후**의 변경에만 반응하므로
 * 그 최초 선택을 영영 놓친다 — 중재자가 `{status:"idle", symbol:null}` 에 고착된다(실측:
 * SymbolInfoPanel.tsx #242 O6 의 "isBenignGap" 코멘트).
 *
 * 그래서 구독을 등록하기 전에 현재 문맥 종목으로 한 번 동기화한다. 경합은 없다 — 그 뒤로는
 * 구독이 그대로 이어받고, `switchTo` 는 이미 같은 종목이면 스스로 무시한다(`realtimeArbiter.ts`).
 */
const arbiter = createArbiter(new NullTransport());

arbiter.switchTo(useContextStore.getState().symbol);
subscribeSymbolChange((symbol) => arbiter.switchTo(symbol));

export function useRealtimeState(): ArbiterState {
  return useSyncExternalStore(arbiter.subscribe, arbiter.getState, arbiter.getState);
}
