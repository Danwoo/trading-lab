// @vitest-environment jsdom
//
// #341 — 역할이 막은 쓰기를 화면이 **누르기 전에** 말하는가.
//
// `scripts/verify_write_gate_coverage.py` 는 「화면이 게이트 표식을 참조하는가」까지만 본다
// (grep 이라 참조가 실제로 조작부에 닿는지는 못 본다). 이 파일은 그 한 칸을 메운다 —
// 판정 훅과, `/admin` 의 관심종목·포트폴리오·스케줄러가 게이트를 **위임하는** 공용 패널이
// 실제로 조작부를 세우지 않고 사유를 내는지 렌더해서 확인한다.
//
// 브라우저로 못 덮는 자리라 여기서 잡는다: `/admin/watchlist` 는 관리자 계정으로도 빈 탭만
// 열려(로컬 스택 실측, 이 변경과 무관한 선행 결함) 그 화면의 게이트를 눈으로 볼 수 없다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, renderHook, screen } from "@testing-library/react";

// `Feedback` 배럴 → `MessagePopup` → ui 배럴 → `env.ts`(t3-oss) 까지 끌려온다. 이 파일의
// 관심사가 아니고 `.env.test` 도 없어 그대로 두면 무관한 이유로 죽는다 (기존 테스트와 같은 관례).
vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

const sessionState = { authorId: null as string | null, isLoaded: false };
vi.mock("@/hooks/shared/useSessionContext", () => ({
  useSessionContext: () => ({
    authorId: sessionState.authorId,
    workspaceId: 1,
    isSysAdmin: sessionState.authorId === "admin",
    isLoaded: sessionState.isLoaded,
  }),
}));

const { useWriteAccess } = await import("@/hooks/shared/useWriteAccess");
const { DetailPanel } = await import("@/components/shared/DataPanel/DetailPanel");
const { GENERAL_ADMIN_AUTHOR_ID, GUEST_AUTHOR_ID, SYS_ADMIN_AUTHOR_ID } = await import("@/constants/protected");
const { WRITE_DENIED_TITLE } = await import("@/constants/writeAccess");

// 이 설정은 자동 정리(globals)가 없다 — 안 지우면 앞 테스트의 DOM 이 남아 다음 단정이 중복으로 죽는다.
afterEach(cleanup);

function setSession(authorId: string | null, isLoaded = true) {
  sessionState.authorId = authorId;
  sessionState.isLoaded = isLoaded;
}

describe("#341 판정 훅 — 누구에게 벽을 말하나", () => {
  it.each([
    [GUEST_AUTHOR_ID, true],
    [GENERAL_ADMIN_AUTHOR_ID, false],
    [SYS_ADMIN_AUTHOR_ID, false],
  ])("역할 %s → 막힘 %s", (authorId, denied) => {
    setSession(authorId);
    const { result } = renderHook(() => useWriteAccess());
    expect(result.current.isDenied, `${authorId} 의 판정이 뒤집혔다`).toBe(denied);
    expect(result.current.canWrite).toBe(!denied);
    expect(Boolean(result.current.deniedHint)).toBe(denied);
  });

  it("세션을 아직 못 읽었으면 막혔다고 말하지 않는다 — 모르는 것을 단정하면 전 계정이 깜빡인다", () => {
    setSession(null, false);
    const { result } = renderHook(() => useWriteAccess());
    expect(result.current.isDenied).toBe(false);
    expect(result.current.deniedHint).toBeUndefined();
  });
});

/** 상세 패널이 세우는 조작부. 게이트가 걸리면 이 버튼들이 서면 안 된다. */
function ViewStub({ onEdit, onDelete }: { onEdit?: () => void; onDelete?: () => void }) {
  return (
    <div>
      {onEdit && <button type="button">수정</button>}
      {onDelete && <button type="button">삭제</button>}
    </div>
  );
}

function FormStub() {
  return <div data-testid="form" />;
}

const panel = (writeGated?: { halted: string[] }, initialMode: "view" | "create" = "view") => (
  <DetailPanel
    title="관심종목 정보"
    data={{ ticker: "005930" }}
    initialMode={initialMode}
    ViewComponent={ViewStub}
    FormComponent={FormStub}
    writeGated={writeGated}
    apiService={{ select: async () => ({ ticker: "005930" }), create: async () => ({}), update: async () => ({}) }}
  />
);

describe("#341 공용 상세 패널 — 게이트를 위임받은 자리", () => {
  it("막히지 않은 계정에는 수정·삭제가 서고 사유는 안 뜬다", () => {
    render(panel(undefined));
    expect(screen.getByRole("button", { name: "수정" })).toBeTruthy();
    expect(screen.queryByText(WRITE_DENIED_TITLE)).toBeNull();
  });

  it("막힌 계정에는 조작부가 아예 안 서고 사유가 먼저 뜬다", () => {
    render(panel({ halted: ["관심종목 등록", "수정", "삭제"] }));
    expect(screen.queryByRole("button", { name: "수정" }), "막혔는데 「수정」이 서 있다").toBeNull();
    expect(screen.queryByRole("button", { name: "삭제" }), "막혔는데 「삭제」가 서 있다").toBeNull();
    expect(screen.getByText(WRITE_DENIED_TITLE)).toBeTruthy();
    // 막히는 동작 이름이 화면마다 다르므로 부르는 쪽이 준 값이 그대로 보여야 한다.
    expect(screen.getByText(/관심종목 등록/)).toBeTruthy();
  });

  it("막힌 계정에는 등록 폼이 아예 안 선다 — 다 채운 뒤 403 을 만나는 것이 이 이슈의 증상이다", () => {
    render(panel({ halted: ["관심종목 등록"] }, "create"));
    expect(screen.queryByTestId("form"), "막혔는데 등록 폼이 섰다").toBeNull();
    expect(screen.getByText(WRITE_DENIED_TITLE)).toBeTruthy();
  });

  it("같은 패널이 게이트 없이는 등록 폼을 그대로 세운다 (위 단정이 늘 참이 아님을 보인다)", () => {
    render(panel(undefined, "create"));
    expect(screen.getByTestId("form")).toBeTruthy();
  });
});
