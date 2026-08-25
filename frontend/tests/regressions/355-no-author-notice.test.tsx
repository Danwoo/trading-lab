// @vitest-environment jsdom
//
// #355 — 권한이 0건인 계정을 화면이 **그 상태와 함께** 보여주는가.
//
// 목록의 권한 칸과 상세의 「소속 권한」 격자는 권한이 없으면 예전엔 그냥 비어 있었다 — 빈 칸은
// 「아직 안 줬다」와 「줄 수 없다」를 가르지 못한다. 이 파일은 그 두 자리를 렌더해 ① 0건이면 문구가
// 서고 ② 승인 전 계정은 이유(승인이 붙여 준다)를 말하며 ③ 권한이 있으면 문구가 없는지 확인한다.
// 읽기 전에는 말하지 않는 것도 본다 — 모르는 것을 단정하면 전 계정에서 깜빡인다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";

// `Feedback` 배럴 → `MessagePopup` → ui 배럴 → `env.ts`(t3-oss) 까지 끌려온다 (#341 화면 테스트와 같은 관례).
vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

/** 서버가 돌려주는 「소속 권한」 — 케이스마다 바꾼다. */
let assigned: Array<{ author_id: string; author_nm: string }> = [];
/** 응답을 붙들어 두는 손잡이 — `null` 이면 즉시 응답한다. */
let hold: { release: () => void } | null = null;
/** 「소속 권한」 응답이 화면에 도착한 횟수 — 부정 단정(문구가 없다)을 읽기 뒤에 하려고 센다. */
let delivered = 0;
vi.mock("@/services/common/adminUserService", () => ({
  selectUserAuthors: vi.fn(
    () =>
      new Promise<{ items: typeof assigned; total_count: number }>((resolve) => {
        const finish = () => {
          delivered++;
          resolve({ items: assigned, total_count: assigned.length });
        };
        if (hold === null) finish();
        else hold.release = finish;
      }),
  ),
  addUserAuthor: vi.fn(),
  removeUserAuthor: vi.fn(),
}));
vi.mock("@/services/common/authorService", () => ({
  selectAuthorOptions: vi.fn(async () => ({ items: [{ author_id: "user", author_nm: "일반사용자" }], total_count: 1 })),
}));

const { default: AdminUserAuthorGrid } =
  await import("@/components/features/Common/System/AdminUser/AdminUserAuthorGrid");
const { renderAuthorCell } = await import("@/components/features/Common/System/AdminUser/authorCell");
const { NO_AUTHOR_HOW_EDIT, NO_AUTHOR_HOW_VIEW, NO_AUTHOR_PENDING, NO_AUTHOR_TITLE, NO_AUTHOR_LABEL } =
  await import("@/constants/accountAuthor");

// 이 설정은 자동 정리(globals)가 없다 — 안 지우면 앞 테스트의 DOM 이 남아 다음 단정이 중복으로 죽는다.
afterEach(() => {
  cleanup();
  assigned = [];
  hold = null;
  delivered = 0;
});

/** 머리줄이 서 있는 안내 상자의 전체 문구. 격자 자신도 `role="status"` 를 여럿 쓰므로 머리줄로 찾는다. */
async function noticeText(): Promise<string> {
  const title = await screen.findByText(NO_AUTHOR_TITLE);
  const box = title.closest('[role="status"]');
  expect(box, "안내가 role=status 상자 안에 있지 않다 — 보조기술이 상태 변화를 못 듣는다").not.toBeNull();
  return box!.textContent ?? "";
}

describe("#355 상세 「소속 권한」 — 0건이면 상태를 말한다", () => {
  it("승인된 계정에 권한이 없으면 머리줄과 가는 길(읽기 모드)을 낸다", async () => {
    render(<AdminUserAuthorGrid email="a@example.com" apprAt="Y" editable={false} />);
    const text = await noticeText();
    expect(text).toContain(NO_AUTHOR_HOW_VIEW);
    expect(text).not.toContain(NO_AUTHOR_PENDING);
  });

  it("수정 모드에서는 바로 그 자리(+)를 가리킨다", async () => {
    render(<AdminUserAuthorGrid email="a@example.com" apprAt="Y" editable={true} />);
    const text = await noticeText();
    expect(text).toContain(NO_AUTHOR_HOW_EDIT);
    expect(text).not.toContain(NO_AUTHOR_HOW_VIEW);
  });

  it("승인 전 계정은 「승인이 붙여 준다」를 말한다 — 없는 것이 정상인 상태", async () => {
    render(<AdminUserAuthorGrid email="a@example.com" apprAt="N" editable={false} />);
    const text = await noticeText();
    expect(text).toContain(NO_AUTHOR_PENDING);
    expect(text).not.toContain(NO_AUTHOR_HOW_VIEW);
  });

  it("권한이 있으면 문구가 서지 않는다", async () => {
    assigned = [{ author_id: "user", author_nm: "일반사용자" }];
    render(<AdminUserAuthorGrid email="a@example.com" apprAt="Y" editable={false} />);
    await waitFor(() => expect(delivered, "「소속 권한」 응답이 아직 도착하지 않았다").toBeGreaterThan(0));
    await act(async () => {});
    expect(screen.queryByText(NO_AUTHOR_TITLE)).toBeNull();
  });

  it("아직 못 읽었으면 말하지 않는다 — 읽기 전 0건은 0건이 아니다", async () => {
    hold = { release: () => undefined };
    render(<AdminUserAuthorGrid email="a@example.com" apprAt="Y" editable={false} />);
    await act(async () => {});
    expect(screen.queryByText(NO_AUTHOR_TITLE), "읽기 전에 「권한 없음」이 떴다 — 전 계정에서 깜빡인다").toBeNull();
    await act(async () => hold!.release());
    await noticeText();
  });
});

describe("#355 목록의 권한 칸 — 빈 칸 대신 「권한 없음」", () => {
  it("author_nm 이 비면 「권한 없음」을 그리고, 승인 전이면 흐리게 낸다", () => {
    const { container: approved } = render(<>{renderAuthorCell({ data: { appr_at: "Y" }, value: "" })}</>);
    expect(approved.textContent).toContain(NO_AUTHOR_LABEL);
    expect(approved.querySelector(".text-caution"), "승인된 계정의 권한 없음이 주의색이 아니다").not.toBeNull();
    cleanup();

    const { container: pending } = render(<>{renderAuthorCell({ data: { appr_at: "N" }, value: "" })}</>);
    expect(pending.textContent).toContain(NO_AUTHOR_LABEL);
    expect(
      pending.querySelector(".text-caution"),
      "승인 전 계정까지 주의색으로 냈다 — 정상 상태가 오류처럼 읽힌다",
    ).toBeNull();
    cleanup();

    const { container: has } = render(<>{renderAuthorCell({ data: { appr_at: "Y" }, value: "일반사용자" })}</>);
    expect(has.textContent).toBe("일반사용자");
  });

  it("컨테이너의 권한 컬럼이 그 렌더러를 쓴다", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(
      path.join(process.cwd(), "components/features/Common/System/AdminUser/AdminUserContainer.tsx"),
      "utf8",
    );
    // 컬럼 정의가 컴포넌트 안에 있어 import 로 못 꺼낸다 — 배선은 소스로 잠근다.
    expect(src).toMatch(/dataField:\s*"author_nm"[\s\S]{0,400}cellRender:\s*renderAuthorCell/);
  });
});
