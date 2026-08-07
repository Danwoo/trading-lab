import type { SymbolRef } from "@/types/terminal/context";

export type RealtimeStatus = "idle" | "connecting" | "subscribed" | "unavailable" | "error";

export interface Quote {
  price: number;
  change: number;
  changeRate: number;
  volume: number;
  at: string;
}

export interface RealtimeTransport {
  subscribe(symbol: SymbolRef, onTick: (quote: Quote) => void, onError: (e: Error) => void): () => void;
}

export interface ArbiterState {
  status: RealtimeStatus;
  symbol: SymbolRef | null;
  quote: Quote | null;
  error: Error | null;
}

export interface Arbiter {
  getState(): ArbiterState;
  switchTo(symbol: SymbolRef | null): void;
  subscribe(listener: (s: ArbiterState) => void): () => void;
  dispose(): void;
}

function sameSymbol(a: SymbolRef, b: SymbolRef): boolean {
  return a.ticker === b.ticker && a.market === b.market;
}

/** `NullTransport` 가 onError 에 넘기는 표식 — 진짜 전송 오류(`error`)와 "아직 연결 안 됨"(`unavailable`)을 구분한다. */
class TransportUnavailableError extends Error {
  constructor() {
    super("실시간 전송이 아직 연결되지 않았습니다");
    this.name = "TransportUnavailableError";
  }
}

const INITIAL_STATE: ArbiterState = { status: "idle", symbol: null, quote: null, error: null };

/**
 * 동시 1종목 구독을 보장하는 중재자 (§3.6). **불변식**: `switchTo` 는 이전 구독의 해제 함수를
 * 반드시 호출한 뒤 새 구독을 건다 — 어느 시점에도 살아 있는 구독은 0 또는 1개다.
 */
export function createArbiter(transport: RealtimeTransport): Arbiter {
  let state: ArbiterState = INITIAL_STATE;
  let unsubscribeCurrent: (() => void) | null = null;
  const listeners = new Set<(s: ArbiterState) => void>();

  function setState(patch: Partial<ArbiterState>): void {
    state = { ...state, ...patch };
    listeners.forEach((listener) => listener(state));
  }

  function releaseSubscription(): void {
    if (unsubscribeCurrent) {
      const unsubscribe = unsubscribeCurrent;
      unsubscribeCurrent = null;
      unsubscribe();
    }
  }

  return {
    getState(): ArbiterState {
      return state;
    },

    switchTo(symbol: SymbolRef | null): void {
      if (symbol === null) {
        releaseSubscription();
        setState({ status: "idle", symbol: null, quote: null, error: null });
        return;
      }

      // 이미 이 종목을 구독(또는 시도) 중이면 재구독하지 않는다.
      if (unsubscribeCurrent !== null && state.symbol !== null && sameSymbol(state.symbol, symbol)) {
        return;
      }

      // 불변식의 핵심: 새 구독을 걸기 전에 이전 구독을 먼저 해제한다.
      releaseSubscription();
      setState({ status: "connecting", symbol, quote: null, error: null });

      unsubscribeCurrent = transport.subscribe(
        symbol,
        (quote) => setState({ status: "subscribed", quote, error: null }),
        (error) => {
          if (error instanceof TransportUnavailableError) {
            setState({ status: "unavailable", quote: null, error: null });
          } else {
            setState({ status: "error", quote: null, error });
          }
        },
      );
    },

    subscribe(listener: (s: ArbiterState) => void): () => void {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    dispose(): void {
      releaseSubscription();
      listeners.clear();
      state = INITIAL_STATE;
    },
  };
}

/** M2 기본 전송 — 실제 웹소켓 계약이 확정되기 전까지 항상 `unavailable` 을 보고한다 (FE-AD-13). */
export class NullTransport implements RealtimeTransport {
  subscribe(_symbol: SymbolRef, _onTick: (quote: Quote) => void, onError: (e: Error) => void): () => void {
    onError(new TransportUnavailableError());
    return () => {};
  }
}
