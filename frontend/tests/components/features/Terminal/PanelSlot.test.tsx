// @vitest-environment jsdom
//
// 이슈 #326 — `needsSymbol` 게이트(FR-007 브리핑)가 가용성 매트릭스보다 먼저 걸리는지, 그리고
// `needsSymbol: false` 패널에는 새지 않는지 검증한다. O2 가 `needsSymbol` 필드를 선언만 해두고
// 아무도 읽지 않던 것을 이 오더가 처음 소비한다.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { PanelSlot } from "@/components/features/Terminal/PanelSlot";
import { setSymbol } from "@/stores/terminal/contextActions";
import { useContextStore } from "@/stores/terminal/contextStore";
import type { PanelDefinition, PanelProps } from "@/types/terminal/panel";
import type { PanelInstance } from "@/types/terminal/layout";

const INSTANCE: PanelInstance = { instanceId: "chart-1", type: "chart", collapsed: false, settings: {} };

function definitionOf(overrides: Partial<PanelDefinition>): PanelDefinition {
  return {
    type: "chart",
    title: "차트",
    capability: "candles",
    needsSymbol: true,
    load: () =>
      Promise.resolve({
        default: (_props: PanelProps) => <div data-testid="panel-body">패널 본문</div>,
      }),
    ...overrides,
  };
}

const NOOP = {
  onToggleCollapse: () => {},
  onClose: () => {},
  onSettingsChange: () => {},
};

afterEach(() => {
  cleanup();
  useContextStore.setState({ symbol: null, interval: "1d", range: null, selectedBotId: null });
});

describe("PanelSlot — needsSymbol 게이트(FR-007)", () => {
  it("needsSymbol 패널 + 종목 미선택 → 브리핑 이유가 뜨고 패널 본문은 마운트되지 않는다", async () => {
    const definition = definitionOf({ capability: "candles" }); // KR 에서 원래는 가용
    render(<PanelSlot instance={INSTANCE} definition={definition} region="KR" {...NOOP} />);

    expect(
      await screen.findByText(
        "브리핑 — 아직 선택된 종목이 없습니다. 사이드바에서 관심종목·보유·스크리너 중 하나를 골라보세요.",
      ),
    ).toBeTruthy();
    expect(screen.queryByTestId("panel-body")).toBeNull();
    // 시장 판정 문구(가용성 매트릭스)로 오인시키지 않는다 — 아직 종목이 없을 뿐 시장을 모르는 게 아니다.
    expect(screen.queryByText("시장 정보를 알 수 없는 종목입니다")).toBeNull();
  });

  it("needsSymbol 패널 + 종목 선택 → 가용성 매트릭스 판정으로 넘어가 패널이 마운트된다", async () => {
    setSymbol({ ticker: "005930", market: "KOSPI", name: "삼성전자" });
    const definition = definitionOf({ capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="KR" {...NOOP} />);

    expect(await screen.findByTestId("panel-body")).toBeTruthy();
  });

  it("needsSymbol: false 패널은 종목 미선택이어도 브리핑 게이트를 타지 않는다 — 가용성 매트릭스만 본다", async () => {
    const definition = definitionOf({ needsSymbol: false, capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="KR" {...NOOP} />);

    // 종목이 없어도 needsSymbol:false 라 region=KR·candles 판정 그대로 마운트된다.
    await waitFor(() => expect(screen.getByTestId("panel-body")).toBeTruthy());
    expect(screen.queryByText(/브리핑/)).toBeNull();
  });

  it("needsSymbol: false 패널이 시장에서 불가하면 여전히 가용성 매트릭스 이유가 뜬다(회귀 방지)", async () => {
    const definition = definitionOf({ needsSymbol: false, capability: "orderbook" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="US" {...NOOP} />);

    expect(await screen.findByText("미국 심층 호가는 확보된 소스가 없습니다")).toBeTruthy();
  });
});

describe("PanelSlot — market 결측(출처 불문)과 진짜 시장 불명을 구분한다(#326 교차 리뷰 지적)", () => {
  it("market 이 빈 문자열 → 출처를 주장하지 않는 결측 문구가 뜨고, '시장 정보를 알 수 없는 종목입니다' 는 아니다", async () => {
    // 이 문구는 관심종목(시장을 비워 등록)·보유(market 컬럼 자체가 없음, 이슈 #328) 두 경로
    // 모두에서 나올 수 있다 — SymbolRef 가 출처를 안 실으므로 어느 쪽에서 왔다고 단정하지 않는다.
    setSymbol({ ticker: "005930", market: "", name: "삼성전자" });
    const definition = definitionOf({ capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    expect(
      await screen.findByText("이 종목에 등록된 시장 값이 비어 있습니다 — 시장을 채우면 이 패널이 열립니다."),
    ).toBeTruthy();
    expect(screen.queryByText("시장 정보를 알 수 없는 종목입니다")).toBeNull();
  });

  it("market 이 있지만 매핑에 없는 진짜 미지원 시장 → 기존 '시장 정보를 알 수 없는 종목입니다' 문구를 그대로 쓴다", async () => {
    setSymbol({ ticker: "XXXX", market: "OTC", name: "장외종목" });
    const definition = definitionOf({ capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    expect(await screen.findByText("시장 정보를 알 수 없는 종목입니다")).toBeTruthy();
    expect(screen.queryByText(/등록된 시장 값이 비어 있습니다/)).toBeNull();
  });

  it("needsSymbol: false 패널은 market 결측이어도 게이트를 타지 않는다 — 가용성 매트릭스만 본다", async () => {
    // 브리핑 게이트와 대칭인 회귀 방지 — 결측 게이트도 needsSymbol 스코프 밖으로 새면 안 된다.
    // positions·bot-state 등 시장이 필요 없는 후속 패널(레지스트리 주석 예고)이 이 조합이다.
    setSymbol({ ticker: "005930", market: "", name: "삼성전자" });
    const definition = definitionOf({ needsSymbol: false, capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    // needsSymbol:false 라 market 결측 판정을 건너뛰고 resolveCapability(region=UNKNOWN) 로
    // 판정한다 — 그 결과는 가용성 매트릭스의 UNKNOWN 문구다(결측 문구가 아니다).
    expect(await screen.findByText("시장 정보를 알 수 없는 종목입니다")).toBeTruthy();
    expect(screen.queryByText(/등록된 시장 값이 비어 있습니다/)).toBeNull();
    expect(screen.queryByTestId("panel-body")).toBeNull();
  });
});
