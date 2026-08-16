import { beforeEach, describe, expect, it } from "vitest";

import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";

beforeEach(() => {
  useBenchSelectionStore.setState({ selection: null });
});

/**
 * 화면 결정 §20.2 「이동 규칙」의 뒤 두 줄. 값은 **하나**이고 `origin` 이 방금 누가 움직였는지만
 * 말한다 — 보드용·패널용으로 두 벌을 두면 둘이 어긋나는 순간 양방향 선택이 깨진다.
 */
describe("benchSelectionStore — 보드와 패널이 나누는 하나의 선택", () => {
  it("보드에서 고르면 origin 이 board 다 — 패널이 「좁힘」으로 반응할 근거", () => {
    useBenchSelectionStore.getState().select({ kind: "grid-point", id: "g-42", label: "칸 42", origin: "board" });

    expect(useBenchSelectionStore.getState().selection).toEqual({
      kind: "grid-point",
      id: "g-42",
      label: "칸 42",
      origin: "board",
    });
  });

  it("패널에서 고르면 같은 자리에 origin 만 panel 로 들어간다 — 보드가 「표시」로 반응한다", () => {
    useBenchSelectionStore.getState().select({ kind: "bot", id: "bot-1", label: "봇 알파", origin: "panel" });

    expect(useBenchSelectionStore.getState().selection?.origin).toBe("panel");
    expect(useBenchSelectionStore.getState().selection?.id).toBe("bot-1");
  });

  it("보드에서 고른 것을 패널에서 다시 고르면 값 하나가 갱신될 뿐 두 벌이 생기지 않는다", () => {
    useBenchSelectionStore.getState().select({ kind: "grid-point", id: "g-42", label: "칸 42", origin: "board" });
    useBenchSelectionStore.getState().select({ kind: "curve-point", id: "c-7", label: "3월 2주", origin: "panel" });

    expect(useBenchSelectionStore.getState().selection).toEqual({
      kind: "curve-point",
      id: "c-7",
      label: "3월 2주",
      origin: "panel",
    });
  });

  it("같은 지점을 다시 고르면 선택이 풀린다 — 보드에서도 좁힘을 되돌릴 수 있어야 한다", () => {
    const pick = { kind: "grid-point", id: "g-42", label: "칸 42", origin: "board" } as const;

    useBenchSelectionStore.getState().select({ ...pick });
    useBenchSelectionStore.getState().select({ ...pick });

    expect(useBenchSelectionStore.getState().selection).toBeNull();
  });

  it("같은 id 라도 종류가 다르면 다른 지점이다 — 풀리지 않고 갈아탄다", () => {
    useBenchSelectionStore.getState().select({ kind: "grid-point", id: "42", label: "칸 42", origin: "board" });
    useBenchSelectionStore.getState().select({ kind: "bot", id: "42", label: "봇 42", origin: "board" });

    expect(useBenchSelectionStore.getState().selection?.kind).toBe("bot");
  });

  it("clear 는 선택을 비운다", () => {
    useBenchSelectionStore.getState().select({ kind: "bot", id: "bot-1", label: "봇 알파", origin: "board" });
    useBenchSelectionStore.getState().clear();

    expect(useBenchSelectionStore.getState().selection).toBeNull();
  });
});
