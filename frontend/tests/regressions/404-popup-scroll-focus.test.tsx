// @vitest-environment jsdom
//
// #404 회귀 그물 — `Popup` 본문 스크롤 영역이 **포커스를 받을 수 있는가**.
//
// 결함(수정 전): 스크롤 영역(`min-h-0 flex-1 overflow-auto`)에 `tabIndex` 가 없었다.
// 본문을 마우스로 클릭하면 브라우저가 가장 가까운 포커스 가능 조상을 잡는데 그게 Radix 가
// `tabindex="-1"` 을 붙인 `DialogContent`(= `overflow-hidden`)라, 그 뒤로 PageDown·ArrowDown
// 이 스크롤할 대상을 못 찾았다. 마우스 휠은 멀쩡해서 마우스 사용자에게는 안 보였다.
//
// ## 이 파일이 증명하는 것 / 못 하는 것 (경계)
//
// - **증명한다(동작)**: 본문을 클릭했을 때 **포커스가 어디로 가는가**. `user-event` 의 포인터
//   구현은 실브라우저처럼 "가장 가까운 포커스 가능 조상"으로 포커스를 옮기므로, 결함의 원인
//   그 자체(포커스가 스크롤되지 않는 바깥 노드로 샌다)가 여기서 그대로 재현된다.
//   열릴 때의 초기 포커스 위치도 같은 층이다.
// - **못 증명한다(스크롤)**: PageDown 이 실제로 `scrollTop` 을 움직이는지. jsdom 에는 레이아웃도
//   스크롤도 없어 `scrollTop` 은 언제나 0 이다 — 그 축은 실브라우저 측정이 담당한다
//   (이 브랜치의 Playwright 재현: 클릭 후 PageDown 이 0→570).
//   `dialogPrimitive.test.tsx` 헤더의 같은 경계 선언 참고 — **초록을 스크롤의 증거로 읽지 마라.**
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Popup } from "@/components/shared/ui/Popup";

// `FormModal` 은 `@/components/shared/ui` 배럴을 거쳐 fileService → env.ts 까지 끌고 온다
// (배럴 fan-out — PolicyPopup.tsx 주석 참고). 테스트 프로세스에는 서버 env 가 없으므로 막는다.
vi.mock("@/env", () => ({ env: { NODE_ENV: "test", FILE_SERVICE_URL: "http://file.test" } }));

const { FormModal } = await import("@/components/shared/Layout/FormModal");

afterEach(cleanup);

/** Radix 는 문서 리스너·초기 포커스를 매크로태스크로 미룬다 — 한 번 비운다. */
async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/** 본문 스크롤 영역 — 소비자가 넘긴 children 을 담는 그 노드. */
function getScrollArea(): HTMLElement {
  const dialog = screen.getByRole("dialog");
  const region = dialog.querySelector<HTMLElement>('[role="region"]');
  expect(region, "본문 스크롤 영역(role=region)을 찾지 못했다").not.toBeNull();
  return region as HTMLElement;
}

describe("Popup 본문 스크롤 영역 — 포커스 (#404)", () => {
  it("본문(포커스 가능한 요소가 없는 지점)을 클릭하면 포커스가 스크롤 영역에 머문다", async () => {
    const user = userEvent.setup();
    render(
      <Popup visible title="이용약관">
        <p>제1조 목적</p>
      </Popup>,
    );
    await flush();

    const scrollArea = getScrollArea();
    await user.click(screen.getByText("제1조 목적"));

    // 결함 시절엔 여기서 `div[role=dialog]`(스크롤되지 않는 바깥 노드)가 잡혔다.
    expect(document.activeElement).toBe(scrollArea);
    expect(scrollArea.getAttribute("tabindex")).toBe("0");
  });

  it("스크롤 영역은 이름 있는 region 이다 — 제목이 없으면 기본 이름을 쓴다", async () => {
    render(
      <Popup visible title="이용약관">
        <p>본문</p>
      </Popup>,
    );
    await flush();
    expect(getScrollArea().getAttribute("aria-label")).toBe("이용약관");
    cleanup();

    render(
      <Popup visible showTitle={false}>
        <p>본문</p>
      </Popup>,
    );
    await flush();
    // 이름 없는 region 은 보조기술에 노출되지 않는다 — 빈 이름으로 두지 않는다.
    expect(getScrollArea().getAttribute("aria-label")).toBe("팝업");
  });

  it("열릴 때 초기 포커스는 본문 안 첫 조작 요소다 — 스크롤 영역이 가로채지 않는다", async () => {
    render(
      <Popup visible title="삭제 확인">
        <button type="button">확인</button>
        <button type="button">취소</button>
      </Popup>,
    );
    await flush();

    // 스크롤 영역이 DOM 상 먼저이므로, 그냥 두면 Radix 기본 동작이 그것을 첫 tabbable 로 잡아
    // 알림 팝업을 Enter 로 바로 확인하던 경로가 죽는다.
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "확인" }));
  });

  it("FormModal 처럼 자기 스크롤러를 겹쳐 둔 소비자의 초기 포커스가 그대로다", async () => {
    // `FormModal` 은 Popup 본문 안에 `tabIndex={0}` 스크롤러를 한 겹 더 둔다. Popup 쪽 영역이
    // 초기 포커스를 가로채면 이 화면들의 조작 순서가 통째로 한 칸씩 밀린다.
    render(
      <FormModal visible title="사용자 등록" onClose={() => {}} onSave={() => {}}>
        <input aria-label="이름" />
      </FormModal>,
    );
    await flush();

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "저장" }));
  });

  it("본문에 조작 요소가 없으면 초기 포커스가 스크롤 영역에 온다 (읽기 전용 팝업)", async () => {
    render(
      <Popup visible title="이용약관">
        <p>읽기 전용 본문</p>
      </Popup>,
    );
    await flush();
    expect(document.activeElement).toBe(getScrollArea());
  });
});
