// @vitest-environment jsdom
//
// F25 — 「조건 결합」 칸이 이 화면에서는 도달할 수 없는 설정을 고르게 했다. 도움말은 「전략을
// 여럿 실으면」이라 했는데 「고른 전략」은 단일 선택 하나라 여럿을 실을 길이 없다(실측).
// 값은 저장되므로 칸을 감추지 않고, 지금은 쓰이지 않는다는 사실을 도움말이 말한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { BotForm } from "@/components/features/Bot/BotForm";
import { NEW_BOT_DRAFT } from "@/components/features/Bot/botFormModel";

afterEach(cleanup);

/** 브라우저가 읽어 주는 순서대로 — 컨트롤의 `aria-describedby` 가 가리키는 문장들. */
function describedText(control: Element): string {
  return (control.getAttribute("aria-describedby") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
}

describe("F25 「조건 결합」 도움말", () => {
  it("전략이 하나뿐인 화면이라 지금은 쓰이지 않는다고 말한다 — 도달할 수 없는 설정을 고르게 하지 않는다", () => {
    render(
      <BotForm
        draft={NEW_BOT_DRAFT}
        onDraftChange={vi.fn()}
        strategy={null}
        strategyForms={[]}
        catalogErrors={[]}
        onStrategyChange={vi.fn()}
        onParamChange={vi.fn()}
      />,
    );

    const help = describedText(screen.getByLabelText("조건 결합"));
    expect(help).toContain("전략을 하나만 실으므로 지금은 쓰이지 않습니다");
  });
});
