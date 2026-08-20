// @vitest-environment jsdom
//
// 사유가 떠 있어도 **패널 자신은 트리에 남는다**는 불변식.
//
// 언마운트하면 그 사유를 갱신할 수 있는 유일한 주체가 사라져, 한 번 `unavailable` 을 올린
// 패널은 문맥이 바뀌어도 영영 그 사유에 갇힌다(구조적 교착 — `SymbolInfoPanel` 의 긴 주석이
// 그 교착을 우회하려고 남아 있다). 호가처럼 **정상 상태가 「사유 있음」인 패널**은 이 불변식이
// 없으면 종목을 바꿔도 옛 사유를 계속 보여준다.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { PanelFrame } from "@/components/features/Terminal/PanelFrame";
import type { PanelDefinition } from "@/types/terminal/panel";
import type { PanelInstance } from "@/types/terminal/layout";

const INSTANCE: PanelInstance = { instanceId: "orderbook-1", type: "orderbook", collapsed: false, settings: {} };
const DEFINITION = {
  type: "orderbook",
  title: "호가",
  capability: "orderbook",
  needsSymbol: true,
  load: async () => ({ default: () => null }),
} as unknown as PanelDefinition;

function renderFrame(reason: string | null) {
  return render(
    <PanelFrame
      instance={INSTANCE}
      definition={DEFINITION}
      provenance={
        reason === null
          ? { kind: "loaded", source: "적재본", asOf: null }
          : { kind: "unavailable", reason, because: "no-source" }
      }
      onToggleCollapse={() => {}}
      onClose={() => {}}
    >
      <p data-testid="panel-body">패널 본문</p>
    </PanelFrame>,
  );
}

describe("PanelFrame — 사유가 떠도 자식은 살아 있다", () => {
  afterEach(cleanup);

  it("unavailable 이어도 자식이 트리에 남는다 (숨겨질 뿐)", () => {
    renderFrame("소스가 없습니다");
    expect(screen.getByText("소스가 없습니다")).toBeTruthy();
    const body = screen.getByTestId("panel-body");
    expect(body, "자식이 언마운트되면 사유를 갱신할 주체가 사라진다").toBeTruthy();
    expect(body.closest("div")?.className).toContain("hidden");
  });

  it("사유가 없을 때는 자식이 보인다", () => {
    renderFrame(null);
    expect(screen.queryByText("소스가 없습니다")).toBeNull();
    expect(screen.getByTestId("panel-body").closest("div")?.className).toContain("contents");
  });

  it("접힌 패널에서는 자식을 렌더하지 않는다 — 접힘은 사용자가 스스로 끈 것이다", () => {
    render(
      <PanelFrame
        instance={{ ...INSTANCE, collapsed: true }}
        definition={DEFINITION}
        provenance={{ kind: "unavailable", reason: "소스가 없습니다", because: "no-source" }}
        onToggleCollapse={() => {}}
        onClose={() => {}}
      >
        <p data-testid="panel-body">패널 본문</p>
      </PanelFrame>,
    );
    expect(screen.queryByTestId("panel-body")).toBeNull();
  });
});
