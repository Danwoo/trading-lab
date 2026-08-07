// @vitest-environment jsdom
//
// 이슈 #322 — `realtimeStore.ts` 는 지연 로드 모듈이다(capability 게이트 뒤에서만 마운트되는
// 패널이 처음 import 할 때 평가된다). "부팅 시점엔 문맥 스토어·중재자가 둘 다 idle/null 이라
// 동기화가 필요 없다"던 원래 가정은 즉시평가 전제였다 — 실제로는 세션 최초 종목 선택이 이
// 모듈의 평가보다 먼저 일어날 수 있고, 그러면 `subscribeSymbolChange`(등록 이후 변경만 반응)가
// 그 선택을 영영 놓친다. `vi.resetModules()` 로 매 테스트마다 "새 세션"을 흉내 내고, 두 모듈을
// import 하는 순서로 그 경쟁을 재현한다 — 디버그 훅 없이, 실제 모듈 그래프 순서로.
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.resetModules();
});

describe("realtimeStore — 지연 로드 race (#322)", () => {
  it("모듈이 평가되기 전에 이미 종목이 선택돼 있었으면, 평가 시점에 그 종목으로 즉시 동기화한다", async () => {
    const { setSymbol } = await import("@/stores/terminal/contextActions");
    // 지연 로드 패널이 아직 마운트되지 않은 시점에 세션 최초 종목 선택이 먼저 일어난다.
    setSymbol({ ticker: "005930", market: "KOSPI", name: "삼성전자" });

    // 이제서야 지연 로드 패널이 마운트되며 이 모듈이 처음 평가된다.
    const { useRealtimeState } = await import("@/stores/terminal/realtimeStore");
    const { result } = renderHook(() => useRealtimeState());

    // idle 에 고착되면 안 된다 — NullTransport 가 동기적으로 응답하므로 최소 "unavailable"(또는
    // 그 이상)이어야 하고, symbol 은 이미 선택된 종목을 그대로 반영해야 한다.
    expect(result.current.status).not.toBe("idle");
    expect(result.current.symbol).toEqual({ ticker: "005930", market: "KOSPI", name: "삼성전자" });
  });

  it("모듈 평가 시점에 아직 종목이 없으면(정상 부팅 순서) idle 로 남는다 — 회귀 없음", async () => {
    const { useRealtimeState } = await import("@/stores/terminal/realtimeStore");
    const { result } = renderHook(() => useRealtimeState());

    expect(result.current.status).toBe("idle");
    expect(result.current.symbol).toBeNull();
  });

  it("모듈 평가 이후의 종목 변경은 기존대로 구독이 반영한다 — 회귀 없음", async () => {
    const { setSymbol } = await import("@/stores/terminal/contextActions");
    const { useRealtimeState } = await import("@/stores/terminal/realtimeStore");
    const { result } = renderHook(() => useRealtimeState());
    expect(result.current.status).toBe("idle");

    act(() => {
      setSymbol({ ticker: "000660", market: "KOSPI", name: "SK하이닉스" });
    });

    expect(result.current.status).not.toBe("idle");
    expect(result.current.symbol).toEqual({ ticker: "000660", market: "KOSPI", name: "SK하이닉스" });
  });
});
