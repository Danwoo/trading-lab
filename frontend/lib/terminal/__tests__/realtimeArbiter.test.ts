import { describe, expect, it } from "vitest";
import { createArbiter } from "@/lib/terminal/realtimeArbiter";
import type { Quote, RealtimeTransport } from "@/lib/terminal/realtimeArbiter";
import type { SymbolRef } from "@/types/terminal/context";

const SYMBOL_A: SymbolRef = { ticker: "005930", market: "KOSPI" };
const SYMBOL_B: SymbolRef = { ticker: "AAPL", market: "NASDAQ" };

/** 구독/해제 호출을 순서대로 기록한다 — "구독이 1개다"만으로는 못 잡는 순서 역전을 잡기 위함. */
class FakeTransport implements RealtimeTransport {
  calls: string[] = [];
  private handlers = new Map<string, { onTick: (q: Quote) => void; onError: (e: Error) => void }>();

  private key(symbol: SymbolRef): string {
    return `${symbol.ticker}:${symbol.market}`;
  }

  subscribe(symbol: SymbolRef, onTick: (quote: Quote) => void, onError: (e: Error) => void): () => void {
    const key = this.key(symbol);
    this.calls.push(`subscribe:${key}`);
    this.handlers.set(key, { onTick, onError });
    return () => {
      this.calls.push(`unsubscribe:${key}`);
      this.handlers.delete(key);
    };
  }

  emitTick(symbol: SymbolRef, quote: Quote): void {
    this.handlers.get(this.key(symbol))?.onTick(quote);
  }

  emitError(symbol: SymbolRef, error: Error): void {
    this.handlers.get(this.key(symbol))?.onError(error);
  }

  activeCount(): number {
    return this.handlers.size;
  }
}

const QUOTE_A: Quote = { price: 70000, change: 100, changeRate: 0.14, volume: 1000, at: "2026-08-02T00:00:00Z" };

describe("realtimeArbiter", () => {
  it("① switchTo(A) → subscribed", () => {
    const transport = new FakeTransport();
    const arbiter = createArbiter(transport);

    arbiter.switchTo(SYMBOL_A);
    transport.emitTick(SYMBOL_A, QUOTE_A);

    expect(arbiter.getState().status).toBe("subscribed");
    expect(arbiter.getState().symbol).toEqual(SYMBOL_A);
    expect(arbiter.getState().quote).toEqual(QUOTE_A);
  });

  it("② switchTo(B) 시 A 의 해제가 B 구독보다 먼저 호출된다", () => {
    const transport = new FakeTransport();
    const arbiter = createArbiter(transport);

    arbiter.switchTo(SYMBOL_A);
    arbiter.switchTo(SYMBOL_B);

    expect(transport.calls).toEqual(["subscribe:005930:KOSPI", "unsubscribe:005930:KOSPI", "subscribe:AAPL:NASDAQ"]);
  });

  it("③ 같은 종목으로 switchTo 하면 재구독하지 않는다", () => {
    const transport = new FakeTransport();
    const arbiter = createArbiter(transport);

    arbiter.switchTo(SYMBOL_A);
    arbiter.switchTo({ ...SYMBOL_A }); // 새 객체지만 같은 종목

    expect(transport.calls).toEqual(["subscribe:005930:KOSPI"]);
  });

  it("④ switchTo(null) 이면 구독 0", () => {
    const transport = new FakeTransport();
    const arbiter = createArbiter(transport);

    arbiter.switchTo(SYMBOL_A);
    expect(transport.activeCount()).toBe(1);

    arbiter.switchTo(null);

    expect(transport.activeCount()).toBe(0);
    expect(arbiter.getState().status).toBe("idle");
    expect(arbiter.getState().symbol).toBeNull();
  });

  it("⑤ 전송 오류가 error 상태로 반영된다", () => {
    const transport = new FakeTransport();
    const arbiter = createArbiter(transport);
    const error = new Error("연결이 끊겼습니다");

    arbiter.switchTo(SYMBOL_A);
    transport.emitError(SYMBOL_A, error);

    expect(arbiter.getState().status).toBe("error");
    expect(arbiter.getState().error).toBe(error);
  });

  it("⑥ dispose 후 살아 있는 구독이 0이다", () => {
    const transport = new FakeTransport();
    const arbiter = createArbiter(transport);

    arbiter.switchTo(SYMBOL_A);
    expect(transport.activeCount()).toBe(1);

    arbiter.dispose();

    expect(transport.activeCount()).toBe(0);
  });
});
