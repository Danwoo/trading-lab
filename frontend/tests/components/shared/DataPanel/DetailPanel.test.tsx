// @vitest-environment jsdom
//
// #356 회귀 그물 — 삭제 확인 창이 대상·연쇄를 말하기 전엔 삭제 API 를 부르지 않는다.
//
// 증명한다: `deleteConfirm` 을 준 화면은 확인 창에 옛 문구("정말 삭제하시겠습니까?") 대신
// 대상 이름과 연쇄 건수가 뜨고, 그 확인을 누르기 전엔 `apiService.delete` 가 호출되지 않는다.
// 증명하지 못한다: 각 Container(코드·권한·메뉴·포트폴리오·스케줄러)가 실제 API 로 정확한
// 건수를 세는지 — 그건 각 서비스 함수의 계약(스키마 `total_count`/배열 길이)에 있다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DetailPanel } from "@/components/shared/DataPanel/DetailPanel";
import { MessagePopup } from "@/components/shared/Feedback/MessagePopup";
import { useMessageStore } from "@/stores/shared/messageStore";

// 실제 Radix Popup 은 jsdom 에 없는 레이아웃·애니메이션에 기대므로, 여기서도 `MessagePopup.
// test.tsx` 와 같은 스텁을 쓴다 — 이 파일이 보는 축은 "소비자가 팝업에 무엇을 넘기는지"다.
vi.mock("@/components/shared/ui/Popup", () => ({
  Popup: ({ visible, title, children }: { visible: boolean; title?: string; children?: React.ReactNode }) =>
    visible ? (
      <div data-testid="popup">
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

const ViewStub = ({ data, onDelete }: { data: { name: string }; onDelete?: () => void }) => (
  <div>
    <span>{data.name}</span>
    <button onClick={onDelete}>행삭제</button>
  </div>
);

beforeEach(() => {
  useMessageStore.setState({ messages: [], currentMessage: null });
});

afterEach(() => {
  cleanup();
  useMessageStore.setState({ messages: [], currentMessage: null });
});

describe("DetailPanel — 삭제 확인이 대상·연쇄를 말한다 (#356)", () => {
  it("deleteConfirm 이 준 대상·연쇄가 뜨고, 확인 전엔 delete 를 부르지 않는다", async () => {
    const user = userEvent.setup();
    const deleteSpy = vi.fn().mockResolvedValue({ message: "삭제가 완료되었습니다." });

    render(
      <>
        <DetailPanel
          title="테스트"
          data={{ id: "9903", name: "9903 취미" }}
          initialMode="view"
          ViewComponent={ViewStub}
          apiService={{ select: vi.fn(), delete: deleteSpy }}
          deleteConfirm={() => ({
            target: "9903 취미",
            cascadeLines: ["하위 코드 4건이 함께 삭제됩니다."],
          })}
        />
        <MessagePopup />
      </>,
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "행삭제" }));
    });

    await screen.findByText("삭제 대상: 9903 취미");
    expect(screen.getByText("하위 코드 4건이 함께 삭제됩니다.")).toBeTruthy();
    // 옛 일괄 문구는 더 이상 뜨지 않는다.
    expect(screen.queryByText("정말 삭제하시겠습니까?")).toBeNull();
    expect(deleteSpy).not.toHaveBeenCalled();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "삭제" }));
    });

    expect(deleteSpy).toHaveBeenCalledTimes(1);
  });

  it("deleteConfirm 을 안 주면 옛 일괄 문구로 물러난다 (하위호환)", async () => {
    const user = userEvent.setup();
    const deleteSpy = vi.fn().mockResolvedValue({ message: "삭제가 완료되었습니다." });

    render(
      <>
        <DetailPanel
          title="테스트"
          data={{ id: "1", name: "이름없는화면" }}
          initialMode="view"
          ViewComponent={ViewStub}
          apiService={{ select: vi.fn(), delete: deleteSpy }}
        />
        <MessagePopup />
      </>,
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "행삭제" }));
    });

    await screen.findByText("정말 삭제하시겠습니까?");
    expect(deleteSpy).not.toHaveBeenCalled();
  });
});
