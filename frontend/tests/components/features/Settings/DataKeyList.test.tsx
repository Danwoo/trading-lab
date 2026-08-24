// @vitest-environment jsdom
//
// 이슈 #344 — 목록이 **세션의 세 상태**를 가른다. 「읽는 중」은 기다리고, 「못 읽음」은 그렇다고
// 말하며, 「읽었는데 시스템관리자가 아님」만 「시스템관리자만 넣을 수 있다」고 말한다.
// 세션이 끝내 안 오는 경우를 로딩으로 두면 화면이 「불러오는 중」에 영영 머물며 이유를 안 말한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { DataKeyList } from "@/components/features/Settings/DataKeyList";
import type { DataKeyStatus } from "@/services/dataKey/dataKeyService";

vi.mock("@/hooks/shared/useSessionContext", () => ({ useSessionContext: vi.fn() }));
vi.mock("@/services/dataKey/dataKeyService", () => ({ selectDataKeyStatus: vi.fn() }));

const { useSessionContext } = await import("@/hooks/shared/useSessionContext");
const { selectDataKeyStatus } = await import("@/services/dataKey/dataKeyService");

// 실제 설정 이름을 적지 않는다 — `DataKeyRow.test.tsx` 와 같은 이유다.
const ROWS: DataKeyStatus[] = [
  { source: "fixture-source", setting: "FIXTURE_SETTING_NOT_A_REAL_KEY", filled: false, secret: true, guidance: null },
];

type Session = ReturnType<typeof useSessionContext>;

function session(over: Partial<Session>): Session {
  return { authorId: null, workspaceId: null, isSysAdmin: false, isLoaded: false, isPending: false, ...over };
}

const UNREADABLE = "로그인 정보를 읽지 못해";
const ADMIN_ONLY = "시스템관리자";

describe("DataKeyList — 세션 「읽는 중」·「못 읽음」·「권한 없음」을 가른다 (#344)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("세션을 읽는 중이면 상태 표도 안내도 아직 그리지 않는다 — 관리자에게 「할 수 없습니다」가 스치지 않는다", async () => {
    vi.mocked(useSessionContext).mockReturnValue(session({ isPending: true }));
    vi.mocked(selectDataKeyStatus).mockResolvedValue({ items: ROWS, total_count: ROWS.length });

    render(<DataKeyList />);
    await vi.waitFor(() => expect(selectDataKeyStatus).toHaveBeenCalled());

    expect(screen.getByText("불러오는 중입니다…")).toBeTruthy();
    expect(screen.queryByText(ROWS[0].setting)).toBeNull();
    expect(screen.queryByText(ADMIN_ONLY, { exact: false })).toBeNull();
  });

  it("세션이 끝내 안 오면 로딩에 머물지 않고 「못 읽었다」고 말한다 — 「권한 없음」이라 하지 않는다", async () => {
    vi.mocked(useSessionContext).mockReturnValue(session({ isPending: false, isLoaded: false }));
    vi.mocked(selectDataKeyStatus).mockResolvedValue({ items: ROWS, total_count: ROWS.length });

    render(<DataKeyList />);

    expect(await screen.findByText(ROWS[0].setting)).toBeTruthy();
    expect(screen.queryByText("불러오는 중입니다…")).toBeNull();
    expect(screen.getByText(UNREADABLE, { exact: false })).toBeTruthy();
    expect(screen.queryByText(ADMIN_ONLY, { exact: false })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("세션을 읽었는데 시스템관리자가 아니면 누가 넣을 수 있는지 말하고 입력칸은 내린다", async () => {
    vi.mocked(useSessionContext).mockReturnValue(session({ isLoaded: true, isSysAdmin: false }));
    vi.mocked(selectDataKeyStatus).mockResolvedValue({ items: ROWS, total_count: ROWS.length });

    render(<DataKeyList />);

    expect(await screen.findByText(ROWS[0].setting)).toBeTruthy();
    expect(screen.getByText(ADMIN_ONLY, { exact: false })).toBeTruthy();
    expect(screen.queryByText(UNREADABLE, { exact: false })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("시스템관리자면 안내 없이 넣는 자리가 있다", async () => {
    vi.mocked(useSessionContext).mockReturnValue(session({ isLoaded: true, isSysAdmin: true }));
    vi.mocked(selectDataKeyStatus).mockResolvedValue({ items: ROWS, total_count: ROWS.length });

    render(<DataKeyList />);

    expect(await screen.findByLabelText(`${ROWS[0].source} ${ROWS[0].setting}`)).toBeTruthy();
    expect(screen.queryByText(ADMIN_ONLY, { exact: false })).toBeNull();
    expect(screen.queryByText(UNREADABLE, { exact: false })).toBeNull();
  });
});
