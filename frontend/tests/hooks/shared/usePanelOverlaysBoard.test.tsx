// @vitest-environment jsdom
//
// 이 훅이 내는 한 줄(「패널이 보드를 덮는가」)이 `<main>` 의 `inert` 를 켜고 끈다. 틀리면
// 보드가 덮이지 않았는데 죽거나, 덮였는데 키보드로 조작된다 — 둘 다 접근성 결함이다.
//
// **jsdom 은 `matchMedia` 를 구현하지 않아** 이 훅은 그동안 테스트가 불가능했다(#191).
// `installViewport` 가 브라우저와 같은 모양의 `matchMedia` 를 세워 폭을 정할 수 있게 한다.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, act } from "@testing-library/react";

import { usePanelOverlaysBoard } from "@/hooks/shared/usePanelOverlaysBoard";
import { VIEWPORT_COMPACT_MIN_PX } from "@/constants/shell";
import { installViewport, type Viewport } from "@/tests/utils/viewport";

let viewport: Viewport | null = null;

function Probe() {
  return <span data-testid="v">{usePanelOverlaysBoard() ? "덮는다" : "안 덮는다"}</span>;
}

function read(): string | null {
  return screen.getByTestId("v").textContent;
}

describe("usePanelOverlaysBoard — 폭 구간이 덮는지를 가른다 (§21.6)", () => {
  afterEach(() => {
    cleanup();
    viewport?.restore();
    viewport = null;
  });

  it("경계 이상에서는 덮지 않는다 — 패널이 옆에 붙는다", () => {
    viewport = installViewport(VIEWPORT_COMPACT_MIN_PX);
    render(<Probe />);

    expect(read()).toBe("안 덮는다");
  });

  it("경계 미만에서는 덮는다", () => {
    viewport = installViewport(VIEWPORT_COMPACT_MIN_PX - 1);
    render(<Probe />);

    expect(read()).toBe("덮는다");
  });

  it("경계가 CSS 와 같은 값이다 — 한 픽셀이 갈린다", () => {
    // 이 훅의 질의가 Tailwind `lg:` 와 다른 값이면, CSS 는 나란히 그리는데 JS 는 덮는다고
    // 말하는 구간이 생긴다. 그 폭에서 보드가 이유 없이 죽는다.
    viewport = installViewport(VIEWPORT_COMPACT_MIN_PX);
    render(<Probe />);
    expect(read()).toBe("안 덮는다");

    act(() => viewport!.resize(VIEWPORT_COMPACT_MIN_PX - 1));
    expect(read()).toBe("덮는다");
  });

  it("폭이 바뀌면 따라간다 — 구독이 살아 있다", () => {
    viewport = installViewport(1440);
    render(<Probe />);
    expect(read()).toBe("안 덮는다");

    act(() => viewport!.resize(900));
    expect(read()).toBe("덮는다");

    act(() => viewport!.resize(1280));
    expect(read()).toBe("안 덮는다");
  });
});
