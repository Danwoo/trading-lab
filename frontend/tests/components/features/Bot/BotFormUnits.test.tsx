// @vitest-environment jsdom
//
// 봇의 「굴리는 규칙」 다섯 칸이 **단위를 보이는가** (#316).
//
// 종전에는 손절에 `5` 를 치고 저장한 뒤 다시 열어도 화면에 남는 글자가 `5` 뿐이었다 —
// 5%인지 5원인지 화면에 근거가 없었다. 단위 선언(`format="#,##0.##%"`)은 있었지만
// `NumberBox` 가 그것을 **읽기 전용일 때만** 그려서 편집 가능한 칸에서는 한 번도 안 돌았다.
//
// 그물은 이슈가 잰 것과 같은 것을 잰다 — 「그 칸 옆에 단위 글자가 있나」. 다섯 칸을 **세고**,
// 기대 개수와 다르면 실패한다(칸이 사라져도 초록인 상태를 막는다). 값이 빈 폼과 채운 폼
// 양쪽에서 본다 — 단위는 값이 들어와야 나타나는 것이 아니다.
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BotForm } from "@/components/features/Bot/BotForm";
import { NEW_BOT_DRAFT, type BotDraft } from "@/components/features/Bot/botFormModel";

/** 라벨 → 그 칸이 보여야 하는 단위. 정본은 백엔드 `schemas/bot/bot_schema.py` 의 `Bot` 이다. */
const UNITS: Record<string, string> = {
  손절: "%", // stop_loss_pct — 손절선 (%, 0~100)
  익절: "%", // take_profit_pct — 익절선 (%, 0 이상)
  "종목당 비중": "%", // alloc_per_symbol — 종목당 비중 (%, 0 이상)
  "최대 보유 종목": "종목", // max_positions — 동시에 들고 갈 최대 종목 수 (1 이상)
  "하루 최대 매매": "회", // max_trades_per_day — 하루 최대 매매 횟수 (1 이상)
};

const FILLED_DRAFT: BotDraft = {
  ...NEW_BOT_DRAFT,
  bot_nm: "테스트 봇",
  stop_loss_pct: 4.25,
  take_profit_pct: 10,
  alloc_per_symbol: 5,
  max_positions: 8,
  max_trades_per_day: 3,
};

function renderForm(draft: BotDraft, onDraftChange = vi.fn()) {
  return render(
    <BotForm
      draft={draft}
      onDraftChange={onDraftChange}
      strategy={null}
      strategyForms={[]}
      catalogErrors={[]}
      onStrategyChange={vi.fn()}
      onParamChange={vi.fn()}
    />,
  );
}

/** 봇 작업대와 같은 배선 — 친 글자가 상태로 돌아와 다시 값이 된다(제어 컴포넌트). */
function StatefulForm() {
  const [draft, setDraft] = useState<BotDraft>(NEW_BOT_DRAFT);
  return (
    <>
      <span data-draft>{draft.stop_loss_pct === null ? "" : String(draft.stop_loss_pct)}</span>
      <BotForm
        draft={draft}
        onDraftChange={(field, value) => setDraft((prev) => ({ ...prev, [field]: value }))}
        strategy={null}
        strategyForms={[]}
        catalogErrors={[]}
        onStrategyChange={vi.fn()}
        onParamChange={vi.fn()}
      />
    </>
  );
}

function inputOf(container: HTMLElement, label: string): HTMLInputElement {
  const element = [...container.querySelectorAll("label")].find((node) => node.textContent?.trim() === label);
  if (!element) throw new Error(`라벨을 못 찾았다: ${label}`);
  const input = container.querySelector<HTMLInputElement>(`#${CSS.escape(element.htmlFor)}`);
  if (!input) throw new Error(`라벨이 가리키는 칸이 없다: ${label}`);
  return input;
}

/**
 * 칸 옆에 실제로 그려진 단위 글자. `aria-describedby` 가 가리키는 것 중 **단위 하나만 담은**
 * 요소를 찾는다 — 도움말 문단에도 `%` 라는 글자가 들어 있어서, 행 전체를 문자열로 훑으면
 * 단위 표기가 사라져도 초록이 된다.
 */
function unitBadgeOf(input: HTMLInputElement, unit: string): HTMLElement | null {
  const ids = (input.getAttribute("aria-describedby") ?? "").split(/\s+/).filter(Boolean);
  const found = ids
    .map((id) => document.getElementById(id))
    .find((node) => node !== null && node.textContent?.trim() === unit);
  return found ?? null;
}

describe("봇 폼의 다섯 칸은 단위를 보인다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it.each([
    ["빈 폼", NEW_BOT_DRAFT],
    ["채운 폼", FILLED_DRAFT],
  ])("%s — 다섯 칸 모두 단위 글자를 옆에 둔다", (_name, draft) => {
    const { container } = renderForm(draft);

    const missing: string[] = [];
    let checked = 0;
    for (const [label, unit] of Object.entries(UNITS)) {
      const input = inputOf(container, label);
      const badge = unitBadgeOf(input, unit);
      checked += 1;
      // 단위는 값 옆에 그려져야 한다 — 다른 자리에 있는 같은 글자를 세지 않는다.
      if (badge === null || input.parentElement?.contains(badge) !== true) missing.push(`${label}(${unit})`);
    }

    expect({ 검사한칸: checked, 단위없는칸: missing }).toEqual({ 검사한칸: Object.keys(UNITS).length, 단위없는칸: [] });
  });

  it("단위 글자가 입력을 방해하지 않는다 — 친 대로 값이 올라가고 화면에 남는다", async () => {
    const user = userEvent.setup();
    const { container } = render(<StatefulForm />);

    const input = inputOf(container, "손절");
    await user.type(input, "4.25");

    // 한 글자씩 다시 그려도 커서가 튀거나 값이 씹히지 않는다 — 단위 글자가 값에 섞이면 깨진다.
    expect(input.value).toBe("4.25");
    expect(container.querySelector("[data-draft]")?.textContent).toBe("4.25");
    expect(unitBadgeOf(input, "%")).not.toBeNull();
  });
});
