import { beforeEach, describe, expect, it } from "vitest";
import {
  setInterval as setTerminalInterval,
  setRange,
  setSelectedBot,
  setSymbol,
  subscribeSymbolChange,
} from "@/stores/terminal/contextActions";
import { useContextStore } from "@/stores/terminal/contextStore";
import type { SymbolRef } from "@/types/terminal/context";

const SAMSUNG: SymbolRef = { ticker: "005930", market: "KOSPI", name: "삼성전자" };
const SK_HYNIX: SymbolRef = { ticker: "000660", market: "KOSPI", name: "SK하이닉스" };

beforeEach(() => {
  useContextStore.setState({ symbol: null, interval: "1d", range: null, selectedBotId: null });
});

describe("contextActions", () => {
  it("종목을 바꾸면 스토어를 구독하는 쪽 전체가 새 값을 받는다 (FR-003)", () => {
    const seenByA: (SymbolRef | null)[] = [];
    const seenByB: (SymbolRef | null)[] = [];
    const unsubA = useContextStore.subscribe((state) => seenByA.push(state.symbol));
    const unsubB = useContextStore.subscribe((state) => seenByB.push(state.symbol));

    setSymbol(SAMSUNG);
    setSymbol(SK_HYNIX);

    expect(seenByA).toEqual([SAMSUNG, SK_HYNIX]);
    expect(seenByB).toEqual([SAMSUNG, SK_HYNIX]);

    unsubA();
    unsubB();
  });

  it("subscribeSymbolChange 는 종목이 실제로 바뀐 전이에서만 알린다 — O4 중재자가 쓰는 통로", () => {
    const changes: (SymbolRef | null)[] = [];
    const unsubscribe = subscribeSymbolChange((symbol) => changes.push(symbol));

    setSymbol(SAMSUNG);
    setTerminalInterval("1m"); // 종목과 무관한 필드 변경 — 알림이 오면 안 된다
    setSymbol(SK_HYNIX);
    setSymbol(null);

    expect(changes).toEqual([SAMSUNG, SK_HYNIX, null]);
    unsubscribe();
  });

  it("unsubscribe 이후에는 더 이상 알림을 받지 않는다", () => {
    const changes: (SymbolRef | null)[] = [];
    const unsubscribe = subscribeSymbolChange((symbol) => changes.push(symbol));

    setSymbol(SAMSUNG);
    unsubscribe();
    setSymbol(SK_HYNIX);

    expect(changes).toEqual([SAMSUNG]);
  });

  it("setInterval·setRange·setSelectedBot 은 각자의 필드만 갱신한다", () => {
    setTerminalInterval("5m");
    setRange({ from: "2026-01-01", to: "2026-01-31" });
    setSelectedBot("bot-1");

    expect(useContextStore.getState()).toMatchObject({
      symbol: null,
      interval: "5m",
      range: { from: "2026-01-01", to: "2026-01-31" },
      selectedBotId: "bot-1",
    });
  });
});
