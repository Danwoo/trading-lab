"use client";

import { Suspense, lazy, useMemo } from "react";
import { resolveCapability, resolveCapabilityWithoutRegion } from "@/lib/terminal/capabilityMatrix";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import type { CapabilityVerdict } from "@/types/terminal/capability";
import type { PanelInstance } from "@/types/terminal/layout";
import type { PanelDefinition } from "@/types/terminal/panel";
import type { Provenance } from "@/types/terminal/provenance";
import type { Region } from "@/types/terminal/context";
import { usePanelProvenanceValue } from "./panelProvenanceBridge";
import { PanelFrame } from "./PanelFrame";
import { PanelErrorBoundary } from "./PanelErrorBoundary";
import { PanelSkeleton } from "./PanelSkeleton";

export interface PanelSlotProps {
  instance: PanelInstance;
  definition: PanelDefinition;
  region: Region;
  onToggleCollapse: () => void;
  onClose: () => void;
  onSettingsChange: (next: Record<string, unknown>) => void;
}

/**
 * 종목 미선택 상태에서 `needsSymbol` 패널이 보여주는 판정 — FR-007(브리핑) 자리다. 시장 축
 * 판정(`resolveCapability`)보다 먼저 걸어, 아직 종목을 고르지 않았을 뿐인데 "시장 정보를 알 수
 * 없는 종목입니다"(가용성 매트릭스의 UNKNOWN 판정 문구)로 오인시키지 않는다. O3 의 출처 표시
 * 장치(`PanelUnavailable`)를 그대로 재사용한다(#326 이슈 지시).
 */
const NEEDS_SYMBOL_VERDICT: CapabilityVerdict = {
  available: false,
  reason: "브리핑 — 아직 선택된 종목이 없습니다. 사이드바에서 관심종목·보유·스크리너 중 하나를 골라보세요.",
  because: "not-chosen",
};

/**
 * 종목은 선택됐지만 `symbol.market` 이 빈 문자열인 경우의 판정. `SymbolRef` 는 이 값이 어느
 * 화면(관심종목·보유 등)에서 왔는지 싣지 않는다 — 그래서 이 분기는 **출처를 주장하지 않는다**.
 * 실제로 빈 시장은 최소 두 경로에서 온다: ① 관심종목 등록 폼의 「시장」이 선택 항목이라(백엔드
 * `watchlist_schema.py` `market: str | None`, 등록 폼에 `required` 없음) 시장을 비운 채 등록된
 * 관심종목 ② `Holding` 백엔드 스키마 자체에 `market` 컬럼이 없는 보유종목(이슈 #328). 두 경로
 * 모두에서 참인 문장만 쓴다 — "보유 기록에 없다"처럼 한쪽 출처를 단정하면 다른 경로(관심종목)
 * 에서는 거짓이 된다(#326 교차 리뷰 지적 — 모호한 것보다 거짓이 나쁘다).
 *
 * `resolveRegion` 은 이 빈 문자열도 정말 미지원인 시장 문자열과 똑같이 `UNKNOWN` 으로 접는다 —
 * 그 문구("시장 정보를 알 수 없는 종목입니다")를 그대로 쓰면 "종목이 이상하다"로 읽혀 사실과
 * 다르다(진실은 "이 종목 기록에 시장 값 자체가 비어 있다"). 시장 문자열이 있는데 매핑에 없는
 * 경우(진짜 미지원)는 이 분기를 타지 않고 기존 `resolveCapability` 문구를 그대로 쓴다.
 *
 * 브리핑 게이트와 같은 `needsSymbol` 스코프를 쓴다 — 시장이 필요 없는 패널(positions·bot-state
 * 등 후속)까지 이 판정을 걸면 시장과 무관한 패널을 시장 이유로 막는 오류가 된다.
 */
const MARKET_MISSING_VERDICT: CapabilityVerdict = {
  available: false,
  reason: "이 종목에 등록된 시장 값이 비어 있습니다 — 시장을 채우면 이 패널이 열립니다.",
};

/**
 * 패널 인스턴스 하나 = 출처 판정(브리핑 게이트 ∪ 시장정보 결측 게이트 ∪ 가용성 매트릭스 ∪
 * 자기 데이터 훅) + 지연 로드 + 에러 경계. 시장에 없는 데이터는 패널을 아예 로드하지 않는다 —
 * 판정이 먼저다(§3.7 가시성 게이팅과 같은 원리).
 */
export function PanelSlot({
  instance,
  definition,
  region,
  onToggleCollapse,
  onClose,
  onSettingsChange,
}: PanelSlotProps) {
  const symbol = useTerminalSymbol();
  let verdict: CapabilityVerdict;
  if (definition.needsSymbol && symbol === null) {
    verdict = NEEDS_SYMBOL_VERDICT;
  } else if (definition.needsSymbol && symbol !== null && symbol.market === "") {
    verdict = MARKET_MISSING_VERDICT;
  } else if (region === "UNKNOWN" && !definition.needsSymbol) {
    // 시장을 모르는데 그 자리가 종목에 매이지도 않았다 — 시장을 물을 이유가 없다.
    // 여기서 시장 판정을 태우면 종목을 고르기 전엔 봇 상태 패널이 늘 가려진다.
    verdict = resolveCapabilityWithoutRegion(definition.capability);
  } else {
    verdict = resolveCapability(definition.capability, { region });
  }
  const reportedProvenance = usePanelProvenanceValue(instance.instanceId);
  const provenance: Provenance | null = verdict.available
    ? reportedProvenance
    : { kind: "unavailable", reason: verdict.reason, because: verdict.because };

  const LazyPanel = useMemo(() => lazy(definition.load), [definition]);

  return (
    <PanelFrame
      instance={instance}
      definition={definition}
      provenance={provenance}
      onToggleCollapse={onToggleCollapse}
      onClose={onClose}
    >
      {verdict.available && (
        <PanelErrorBoundary panelTitle={definition.title}>
          <Suspense fallback={<PanelSkeleton />}>
            <LazyPanel
              instanceId={instance.instanceId}
              settings={instance.settings}
              onSettingsChange={onSettingsChange}
            />
          </Suspense>
        </PanelErrorBoundary>
      )}
    </PanelFrame>
  );
}
