// @vitest-environment jsdom
//
// #453 F1 — 봇 저장 실패가 **1.6초 만에 사라지고**, 어느 칸인지도 안 짚었다.
//
//   +400ms   토스트 "⚠️ 봇 이름을 적어주세요."   aria-invalid 칸 0개
//   +2000ms  토스트 없음                          aria-invalid 칸 0개
//
// 문구 자체는 정확했다. 문제는 **수명과 잔류물**이다 — 64줄짜리 폼에서 스크롤을 내려 저장을
// 눌렀다면 위로 올라가 이름 칸을 찾아야 하는데 그때는 문구가 이미 없다. 같은 셸의 격자 폼은
// 폼 안에 남긴다. 두 폼이 실패를 다르게 다루던 것을 맞춘다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { BotForm } from "@/components/features/Bot/BotForm";
import { NEW_BOT_DRAFT } from "@/components/features/Bot/botFormModel";

afterEach(cleanup);

function renderForm(extra: { fieldErrors?: Record<string, string>; formError?: string | null }) {
  return render(
    <BotForm
      draft={NEW_BOT_DRAFT}
      onDraftChange={vi.fn()}
      strategy={null}
      strategyForms={[]}
      catalogErrors={[]}
      onStrategyChange={vi.fn()}
      onParamChange={vi.fn()}
      {...extra}
    />,
  );
}

describe("실패는 폼 안에 남는다", () => {
  it("칸을 짚을 수 있으면 그 칸에 남는다 — 이름 칸이 무효로 표시된다", () => {
    renderForm({ fieldErrors: { bot_nm: "봇 이름을 적어주세요." } });
    const name = screen.getByLabelText("이름");
    expect(name.getAttribute("aria-invalid")).toBe("true");
  });

  it("그 칸이 문구를 들고 있다 — 토스트가 사라져도 무엇이 잘못됐는지 읽힌다", () => {
    renderForm({ fieldErrors: { bot_nm: "봇 이름을 적어주세요." } });
    const name = screen.getByLabelText("이름");
    const described = (name.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ");
    expect(described).toContain("봇 이름을 적어주세요.");
  });

  it("칸을 짚을 수 없는 실패는 폼 머리에 남는다", () => {
    renderForm({ formError: "전략을 하나 고르면 저장할 수 있습니다." });
    const alerts = screen.getAllByRole("alert").map((node) => node.textContent ?? "");
    expect(alerts.some((text) => text.includes("전략을 하나 고르면"))).toBe(true);
  });

  it("실패가 없으면 아무것도 얹지 않는다 — 빈 경고 자리를 남기지 않는다", () => {
    const { container } = renderForm({});
    expect(container.querySelectorAll('[role="alert"]').length).toBe(0);
    expect(screen.getByLabelText("이름").getAttribute("aria-invalid")).toBeNull();
  });
});
