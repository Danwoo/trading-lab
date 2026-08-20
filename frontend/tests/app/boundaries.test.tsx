// @vitest-environment jsdom
//
// 없는 주소와 그리다 만 화면 — 두 자리 다 **한국어로, 갈 곳과 함께** 답해야 한다.
// 이 파일이 없으면 자리를 지웠을 때 Next.js 기본 화면(영문)으로 조용히 되돌아간다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NotFound from "@/app/not-found";
import ErrorBoundary from "@/app/error";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("없는 주소", () => {
  it("한국어로 답하고 돌아갈 길을 준다", () => {
    render(<NotFound />);

    expect(document.body.textContent).toContain("이 주소에 해당하는 화면이 없습니다");
    expect(screen.getByRole("link", { name: "실험대로 가기" }).getAttribute("href")).toBe("/bench");
  });
});

describe("화면이 멈췄을 때", () => {
  it("무엇이 멈췄고 무엇이 남아 있는지 말한다", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary error={new Error("boom")} reset={() => {}} />);

    expect(screen.getByRole("alert").textContent).toContain("이 화면이 멈췄습니다");
    expect(document.body.textContent).toContain("저장된 것은 그대로 있습니다");
  });

  it("다시 그리기가 실제로 reset 을 부른다 — 죽은 버튼이 아니다", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const reset = vi.fn();
    render(<ErrorBoundary error={new Error("boom")} reset={reset} />);

    await userEvent.click(screen.getByRole("button", { name: "다시 그리기" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("예외 원문을 화면에 싣지 않는다 — 사유에 URL·키가 실려 온 전례가 있다", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary error={new Error("https://apis.data.go.kr/svc?serviceKey=SECRETKEY123")} reset={() => {}} />);

    expect(document.body.textContent).not.toContain("serviceKey");
    expect(document.body.textContent).not.toContain("data.go.kr");
  });
});
