// @vitest-environment jsdom
//
// #446 F33 — 아무 칸도 건드리지 않고 「변경하기」를 눌러도 요청이 나가고
// 「마이페이지 정보가 변경되었습니다.」가 떴다.
//
// 「변경되었습니다」는 **무언가 달라졌다**는 말이다. 아무것도 안 달라졌는데 그 말을 하면,
// 진짜로 바뀌었을 때의 같은 문장이 신호로서의 값을 잃는다 — 이 레포가 #424 에서 세운 기준
// (「화면이 실제 상태와 다른 말을 하지 않는다」)의 작은 사례다.
//
// 덤으로 쓸데없는 쓰기 요청도 안 나간다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const ME = { email: "operator@example.com", name: "운영자", dept: "리서치", workspace_nm: "내 워크스페이스" };

vi.mock("@/services/common/mypageService", () => ({
  fetchMyInfo: vi.fn(async () => ME),
  updateMyInfo: vi.fn(async () => ({ result: true })),
  deleteMyAccount: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
// 문구는 스토어를 거쳐 팝업이 그린다 — 팝업을 띄우지 않고 그 호출을 직접 본다.
vi.mock("@/stores/shared/messageStore", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/stores/shared/messageStore")>();
  return { ...actual, showMessage: vi.fn() };
});

const { updateMyInfo } = await import("@/services/common/mypageService");
const { showMessage } = await import("@/stores/shared/messageStore");
const { Mypage } = await import("@/components/features/Common/Mypage/Mypage");

async function open() {
  render(<Mypage />);
  await screen.findByDisplayValue(ME.name);
}

const submit = async () => {
  await userEvent.setup().click(screen.getByRole("button", { name: /변경/ }));
};

describe("안 바뀐 저장이 「변경됨」이라고 하지 않는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("아무것도 안 고치고 누르면 쓰기 요청이 안 나간다", async () => {
    await open();
    await submit();

    await waitFor(() => expect(vi.mocked(updateMyInfo)).not.toHaveBeenCalled());
  });

  it("아무것도 안 고치고 누르면 「변경되었습니다」라고 하지 않는다", async () => {
    await open();
    await submit();

    await waitFor(() => expect(vi.mocked(showMessage)).toHaveBeenCalled());
    const said = vi
      .mocked(showMessage)
      .mock.calls.map((c) => JSON.stringify(c[1]))
      .join(" ");
    expect(said).not.toContain("정보가 변경되었습니다");
  });

  it("바뀐 것이 없다는 사실을 말한다 — 눌렀는데 아무 일도 안 일어나는 것은 아니다", async () => {
    await open();
    await submit();

    await waitFor(() => expect(vi.mocked(showMessage)).toHaveBeenCalled());
    const said = vi
      .mocked(showMessage)
      .mock.calls.map((c) => JSON.stringify(c[1]))
      .join(" ");
    expect(said).toContain("바뀐 것이 없습니다");
  });

  it("한 칸이라도 고치면 종전대로 저장한다 — 막는 범위가 넓어지지 않았다", async () => {
    await open();
    const user = userEvent.setup();
    const dept = screen.getByDisplayValue(ME.dept);
    await user.clear(dept);
    await user.type(dept, "실험대");
    await submit();

    await waitFor(() => expect(vi.mocked(updateMyInfo)).toHaveBeenCalledTimes(1));
  });
});
