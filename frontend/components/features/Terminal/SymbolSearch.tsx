"use client";

import { useEffect, useRef, useState } from "react";
import { createWatchlist } from "@/services/watchlist/watchlistService";
import { selectInstrumentList } from "@/services/terminal/instrumentService";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { INSTRUMENT_MASTER_SIGNAL_KEY, useIngestRevision } from "@/stores/terminal/ingestSignalStore";
import type { InstrumentOut } from "@/schemas/terminal/instrument";
import type { SymbolRef } from "@/types/terminal/context";

export interface SymbolSearchProps {
  /** 관심종목에 담고 문맥까지 그 종목으로 옮긴다. 담긴 뒤 목록을 다시 읽는 것은 부모의 몫이다. */
  onAdded: (symbol: SymbolRef) => void;
  /** 관심종목이 이미 있을 때만 준다 — 0건이면 돌아갈 목록이 없어 닫는 자리를 두지 않는다. */
  onClose?: () => void;
}

/** 타이핑이 멎기를 기다리는 시간. 한 글자마다 4,303행을 훑게 하지 않는다. */
const DEBOUNCE_MS = 250;

/** 사이드바에 한 번에 그리는 검색 결과 수. 좁히는 것은 검색어의 일이다. */
const RESULT_TAKE = 20;

type SearchState =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "loaded"; items: InstrumentOut[]; totalCount: number; unavailableReason: string | null };

/**
 * 종목 마스터 검색 (#318) — 터미널을 안 떠나고 첫 종목을 담는 자리.
 *
 * 여기 오기 전에는 `/admin/watchlist` 로 나가 **티커를 외워서 쳐야** 했다. 마스터 4,303행이
 * 이미 DB 에 있는데도 그랬다 — 아는 것을 안 쓴 것이다.
 *
 * 세 가지를 가려 말한다(FR-021): **못 읽음**(서버 실패) · **아직 안 받음**(마스터가 빔, 서버가
 * 내려 준 사유를 그대로 보여 준다) · **없음**(마스터는 찼는데 그 이름이 없다). 셋을 「결과
 * 없음」 하나로 뭉개면 사용자가 자기가 친 종목명을 의심한다.
 */
export function SymbolSearch({ onAdded, onClose }: SymbolSearchProps) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ kind: "loading" });
  const [addingTicker, setAddingTicker] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const requestToken = useRef(0);
  // 「종목 목록 받기」가 마스터를 채우면 다시 훑는다 — 안 그러면 방금 받은 4,303행을 두고
  // 「아직 안 받았습니다」가 그대로 남는다(#350 과 같은 계통).
  const masterRevision = useIngestRevision(INSTRUMENT_MASTER_SIGNAL_KEY);

  useEffect(() => {
    const token = ++requestToken.current;
    setState({ kind: "loading" });

    const timer = setTimeout(() => {
      selectInstrumentList({ q: query.trim(), take: RESULT_TAKE })
        .then((result) => {
          if (token !== requestToken.current) return;
          setState({
            kind: "loaded",
            items: result?.items ?? [],
            totalCount: result?.total_count ?? 0,
            unavailableReason: result?.unavailable_reason ?? null,
          });
        })
        .catch(() => {
          if (token !== requestToken.current) return;
          setState({ kind: "failed" });
        });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [query, masterRevision]);

  const add = async (instrument: InstrumentOut) => {
    setAddingTicker(instrument.symbol);
    setAddError(null);
    const symbol: SymbolRef = {
      ticker: instrument.symbol,
      market: instrument.market,
      name: instrument.issuer_nm,
    };
    try {
      await createWatchlist({
        ticker: instrument.symbol,
        issuer_nm: instrument.issuer_nm,
        market: instrument.market,
        currency: instrument.currency,
        use_at: "Y",
      });
      onAdded(symbol);
    } catch (error: any) {
      // 이미 담긴 종목은 실패가 아니다 — 사용자가 원한 결과(그 종목이 관심종목에 있다)가
      // 이미 참이므로 그대로 고른다.
      if (error?.response?.status === 409) {
        onAdded(symbol);
        return;
      }
      setAddError(getApiErrorMessage(error));
    } finally {
      setAddingTicker(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-shrink-0 items-center gap-1.5 border-b border-line px-2 py-1">
        <input
          type="search"
          aria-label="종목 검색"
          placeholder="종목명 또는 코드"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-h-touch-min min-w-0 flex-1 rounded-control border border-line bg-bg-base px-2 py-1 text-ink placeholder:text-ink-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        />
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex-shrink-0 rounded-control border border-line px-2 py-1 text-2xs text-ink hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            닫기
          </button>
        )}
      </div>

      {addError && (
        <p role="alert" className="flex-shrink-0 border-b border-line px-2 py-1 text-2xs text-danger">
          {addError}
        </p>
      )}

      <SearchBody state={state} addingTicker={addingTicker} onPick={add} />
    </div>
  );
}

function SearchBody({
  state,
  addingTicker,
  onPick,
}: {
  state: SearchState;
  addingTicker: string | null;
  onPick: (instrument: InstrumentOut) => void;
}) {
  if (state.kind === "loading") {
    return (
      <p role="status" className="px-2 py-2 text-ink-muted">
        종목을 찾고 있습니다…
      </p>
    );
  }

  if (state.kind === "failed") {
    return (
      <p role="status" className="px-2 py-2 text-danger">
        종목 목록을 불러오지 못했습니다 — 잠시 후 다시 시도하세요.
      </p>
    );
  }

  if (state.items.length === 0) {
    // 마스터가 비어 있으면 서버가 사유와 다음 걸음을 내려 준다 — 프론트가 문구를 지어내면
    // 서버가 아는 사실과 갈린다(적재 콘솔의 사유 표시와 같은 규율).
    return (
      <p role="status" className="px-2 py-2 text-ink-muted">
        {state.unavailableReason ?? "찾는 종목이 없습니다 — 종목명 일부나 코드로 다시 찾아보세요."}
      </p>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ul className="min-h-0 flex-1 overflow-auto">
        {state.items.map((instrument) => (
          <li key={`${instrument.market}:${instrument.symbol}`}>
            <button
              type="button"
              disabled={addingTicker !== null}
              onClick={() => onPick(instrument)}
              className="flex w-full items-center justify-between gap-2 border-l-2 border-transparent px-2 py-1.5 text-left hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted disabled:opacity-50"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-ink">{instrument.issuer_nm}</span>
                <span className="block text-ink-muted">
                  {instrument.market} · {instrument.symbol}
                </span>
              </span>
              <span className="flex-shrink-0 text-2xs text-ink-muted">
                {addingTicker === instrument.symbol ? "담는 중…" : "담기"}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {state.totalCount > state.items.length && (
        <p role="status" className="flex-shrink-0 border-t border-line px-2 py-1 text-ink-muted">
          {state.totalCount}건 중 {state.items.length}건 표시 — 검색어를 좁히세요
        </p>
      )}
    </div>
  );
}
