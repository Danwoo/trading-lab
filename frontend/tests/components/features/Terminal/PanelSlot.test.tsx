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

  // #284 — 배지 「제공 안 됨」은 「사용자가 할 수 있는 것이 없다」는 뜻이다. 바로 아래 사유가
  // 「채우면 열립니다」라고 말하는 자리에 그 배지를 붙이면 한 자리가 두 말을 한다.
  it("배지가 「제공 안 됨」이라 부르지 않는다 — 채우면 열리는 자리다", async () => {
    setSymbol({ ticker: "005930", market: "", name: "삼성전자" });
    const definition = definitionOf({ capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    await screen.findByText("이 종목에 등록된 시장 값이 비어 있습니다 — 시장을 채우면 이 패널이 열립니다.");
    expect(screen.queryByText("제공 안 됨")).toBeNull();
    expect(screen.getByText("고르면 채워집니다")).toBeTruthy();
  });

  it("market 이 있지만 매핑에 없는 진짜 미지원 시장 → 기존 '시장 정보를 알 수 없는 종목입니다' 문구를 그대로 쓴다", async () => {
    setSymbol({ ticker: "XXXX", market: "OTC", name: "장외종목" });
    const definition = definitionOf({ capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    expect(await screen.findByText("시장 정보를 알 수 없는 종목입니다")).toBeTruthy();
    expect(screen.queryByText(/등록된 시장 값이 비어 있습니다/)).toBeNull();
  });

  it("needsSymbol: false 패널은 market 결측 게이트를 타지 않는다", async () => {
    // 브리핑 게이트와 대칭인 회귀 방지 — 결측 게이트도 needsSymbol 스코프 밖으로 새면 안 된다.
    setSymbol({ ticker: "005930", market: "", name: "삼성전자" });
    const definition = definitionOf({ needsSymbol: false, capability: "candles" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    expect(screen.queryByText(/등록된 시장 값이 비어 있습니다/)).toBeNull();
  });

  // 이 자리는 종전에 「시장 정보를 알 수 없는 종목입니다」를 기대했다. 그 기대가 실제 화면에서
  // 틀렸음이 드러났다 — 종목을 안 고른 채 /terminal 을 열면 「봇 상태」가 봇과 아무 상관 없는
  // 그 문구로 가려졌다(브라우저로 재현). 종목에 안 매인 자리에 시장을 묻는 것이 잘못이다.
  it("시장을 몰라도 종목에 안 매인 자리는 열린다 — 시장이 변수가 아닌 자료일 때", async () => {
    setSymbol(null);
    const definition = definitionOf({ needsSymbol: false, capability: "botState" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    expect(await screen.findByTestId("panel-body")).toBeTruthy();
    expect(screen.queryByText("시장 정보를 알 수 없는 종목입니다")).toBeNull();
  });

  it("그래도 시장마다 답이 갈리는 자료면 모르는 채로 열어 주지 않는다 (fail-closed)", async () => {
    setSymbol(null);
    const definition = definitionOf({ needsSymbol: false, capability: "orderbook" });
    render(<PanelSlot instance={INSTANCE} definition={definition} region="UNKNOWN" {...NOOP} />);

    expect(await screen.findByText("시장 정보를 알 수 없는 종목입니다")).toBeTruthy();
    expect(screen.queryByTestId("panel-body")).toBeNull();
  });
});
