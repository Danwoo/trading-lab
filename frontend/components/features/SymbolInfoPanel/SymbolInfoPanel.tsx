"use client";

import { useEffect } from "react";
import { usePanelProvenance } from "@/components/features/Terminal/panelProvenanceBridge";
import { useRealtimeQuote } from "@/hooks/terminal/useRealtimeQuote";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import { formatNumber } from "@/utils/common/formatters/number";
import type { Quote } from "@/lib/terminal/realtimeArbiter";
import type { Provenance } from "@/types/terminal/provenance";
import type { PanelProps } from "@/types/terminal/panel";

/**
 * 임시 시세 — `provenance.kind === "placeholder"` 일 때만 쓴다. 실시간 계약이 없는 동안
 * (`NullTransport`, #242 O4) 화면에 무엇이 뜨는지 증명하기 위한 값이지 API 계약이 아니다.
 * 캔들 패널의 임시 캔들 데이터와 같은 성격이지만, 이 값은 이 파일 밖으로 내보내지 않는다 —
 * 공유 계약처럼 보이면 다른 곳에서 실데이터로 오인해 import 할 위험이 있다.
 */
const PLACEHOLDER_QUOTE: Quote = {
  price: 74200,
  change: 1200,
  changeRate: 1.64,
  volume: 8_423_190,
  at: new Date().toISOString(),
};

/**
 * 종목 정보 패널(#242 O6, FR-019). 실시간 시세 한 갈래(`useRealtimeQuote`)만 읽는다.
 *
 * `useRealtimeQuote` 의 "idle"(구독 중재자가 아직 이 종목으로 전환되지 않음, `error === null`)도
 * 이 패널 안에서는 placeholder 로 다룬다 — 그대로 `unavailable` 을 올리면 `PanelFrame` 이 이
 * 컴포넌트를 통째로 언마운트하는데(§`PanelFrame.tsx` 의 `isUnavailable` 분기), 언마운트되면
 * `useSyncExternalStore` 구독도 함께 끊겨 **어떤 이후 종목 전환도 다시 이 패널을 되살리지
 * 못하는 죽은 상태**가 된다(실측 — 최초 종목 선택 시 구독 중재자 모듈이 지연 로드돼 그 선택
 * 이벤트를 놓치는 경쟁 상태가 실제로 발생한다). ChartPanel 의 동일 패턴과 같은 이유.
 * **진짜 에러**(`error !== null`)는 그대로 올려 NFR-001 을 지킨다.
 *
 * #322 후속 — 지연 로드 race 의 근본 원인은 `realtimeStore.ts` 에서 모듈 평가 시점에 현재
 * 문맥 종목으로 동기화하도록 고쳤다(그 파일 코멘트 참고). 그런데 **이 방어는 그 뒤에도 그대로
 * 남긴다** — 언마운트가 위험한 진짜 이유는 race 자체가 아니라 `PanelSlot`→`PanelFrame` 의
 * 구조다: `provenance` 를 갱신할 수 있는 것은 **마운트된 이 컴포넌트 자신뿐**인데(`reportProvenance`
 * 호출), `PanelFrame` 은 그 `provenance` 가 "unavailable"이면 `children`(이 컴포넌트)을 트리에서
 * 뺀다 — 한 번 unavailable 을 올리면 그것을 되돌릴 유일한 주체가 사라지는 구조적 교착이다.
 * 이 교착은 race 가 사라져도 남는다(예: 이 패널이 마운트된 채로 문맥 종목이 null 로 바뀌는
 * 경로가 미래에 생기면 다시 idle 을 보고할 수 있다). 그래서 걷어내지 않는다.
 */
export default function SymbolInfoPanel({ instanceId }: PanelProps) {
  const symbol = useTerminalSymbol();
  const quoteState = useRealtimeQuote();
  const reportProvenance = usePanelProvenance(instanceId);

  const isBenignGap = quoteState.provenance.kind === "unavailable" && quoteState.error === null;
  const isPlaceholder = quoteState.provenance.kind === "placeholder" || isBenignGap;

  useEffect(() => {
    // 실려 온 사유는 `hint` 로 그대로 넘긴다 — 떨어뜨리면 왜 임시인지가 화면에서 사라진다.
    const effective: Provenance = isPlaceholder
      ? {
          kind: "placeholder",
          source: "임시 데이터",
          note: symbol?.ticker,
          hint: quoteState.provenance.kind === "placeholder" ? quoteState.provenance.hint : undefined,
        }
      : quoteState.provenance;
    reportProvenance(effective);
    // quoteState.provenance 는 매 렌더 새 객체 리터럴이다(useRealtimeQuote 가 switch 로 매번
    // 새로 만든다) — 원본을 deps 에 넣으면 report→bridge 갱신→재렌더→새 객체→다시 report 로
    // 무한 루프가 된다(실측: "Maximum update depth exceeded"). 내용 기준 키(JSON)로 비교한다.
  }, [isPlaceholder, JSON.stringify(quoteState.provenance), symbol?.ticker, reportProvenance]);

  const quote = quoteState.data ?? (isPlaceholder ? PLACEHOLDER_QUOTE : null);

  if (!quote) {
    return (
      <div role="status" className="flex h-full items-center justify-center px-6 text-center text-sm text-ink-muted">
        시세 정보를 아직 받지 못했습니다.
      </div>
    );
  }

  const isUp = quote.change >= 0;
  const directionClassName = isUp ? "text-market-up" : "text-market-down";

  return (
    <div className="flex h-full flex-col gap-4 p-3 font-mono text-xs">
      <div>
        <p className="text-sm text-ink">{symbol?.name ?? symbol?.ticker ?? "종목 미선택"}</p>
        <p className="text-ink-muted">{symbol ? `${symbol.ticker} · ${symbol.market}` : "—"}</p>
      </div>

      <div className={directionClassName}>
        <p className="text-lg">{formatNumber(quote.price, "number")}</p>
        {/* 색만으로 방향을 표시하지 않는다 — 부호(▲/▼)를 항상 함께 그린다 (#242 O3 착수 코멘트). */}
        <p>
          {isUp ? "▲" : "▼"} {formatNumber(Math.abs(quote.change), "number")} (
          {formatNumber(Math.abs(quote.changeRate), "decimal", { decimals: 2 })}%)
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-ink-muted">
        <dt>거래량</dt>
        <dd className="text-right text-ink">{formatNumber(quote.volume, "number")}</dd>
      </dl>
    </div>
  );
}
