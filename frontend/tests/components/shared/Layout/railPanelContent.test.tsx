// @vitest-environment jsdom
//
// 「패널이 실재하는가」는 두 곳에 적혀 있다 — 레지스트리에 항목이 있는가(`RAIL_PANEL_CONTENT`)와
// 레일 항목에 `pending` 이 남아 있는가(`RAIL_ITEMS`). 둘이 어긋나면 화면이 거짓말을 한다:
//
//   - 배선했는데 `pending` 이 남으면 → 보드의 CTA 가 "준비 중"이라 말하는데 패널은 실제로 열린다.
//   - `pending` 을 지웠는데 배선이 없으면 → 패널이 빈 채로 뜨고 왜 비었는지 아무 말도 없다.
//
// 이 그물은 그 어긋남을 막는다. **검사 대상 수를 세어 0이면 실패한다** — 레일 항목이 사라지거나
// 이름이 바뀌어 "대상 없음 = 위반 없음"으로 조용히 초록이 되는 것을 막기 위해서다.
import { describe, expect, it } from "vitest";

import { RAIL_ITEMS } from "@/constants/shell";
import { RAIL_PANEL_CONTENT } from "@/components/shared/Layout/railPanelContent";

const PANEL_ITEMS = RAIL_ITEMS.filter((item) => item.kind === "panel");

describe("레일 패널 — 배선과 「준비 중」 표식이 어긋나지 않는다", () => {
  it("검사 대상이 0건이 아니다", () => {
    expect(PANEL_ITEMS.length).toBeGreaterThan(0);
  });

  it("배선된 패널에는 pending 이 없다", () => {
    const wired = PANEL_ITEMS.filter((item) => RAIL_PANEL_CONTENT[item.id] !== undefined);
    expect(wired.length).toBeGreaterThan(0);
    expect(wired.filter((item) => item.pending !== undefined).map((item) => item.id)).toEqual([]);
  });

  it("배선되지 않은 패널은 왜 비었는지 말한다 (pending 이 있다)", () => {
    const unwired = PANEL_ITEMS.filter((item) => RAIL_PANEL_CONTENT[item.id] === undefined);
    expect(unwired.filter((item) => item.pending === undefined).map((item) => item.id)).toEqual([]);
  });

  it("레지스트리에 레일에 없는 id 가 들어 있지 않다", () => {
    const railIds = new Set(RAIL_ITEMS.map((item) => item.id));
    expect(Object.keys(RAIL_PANEL_CONTENT).filter((id) => !railIds.has(id))).toEqual([]);
  });

  it("봇 패널은 배선되어 있다 — 보드의 1차 진입점이다", () => {
    expect(RAIL_PANEL_CONTENT.bot).toBeDefined();
    expect(PANEL_ITEMS.find((item) => item.id === "bot")?.pending).toBeUndefined();
  });
});
