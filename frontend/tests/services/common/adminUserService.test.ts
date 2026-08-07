// #400 — 서버 경계와 **같은 스키마**로 먼저 검증하는 클라이언트 쪽 그물.
//
// PR #413 리뷰가 지적한 축: 「클라이언트가 명시적 null 을 보낼 수단이 없다」는 참이지만
// 「손상된 값을 보낼 수단이 없다」는 성립하지 않는다. `Optional()` 이 변환 실패를 `undefined`
// 로 접던 시절엔 `workspace_id: "garbage"` 가 여기서 조용히 사라져, 서버엔 workspace_id 키가
// 없는 정상 PUT 으로 보였다 — 그리고 전체표현 계약이 그걸 명시적 null(배정 해제)로 읽었다.
//
// **검증 경계** — apiCall 은 mock 이다. 보는 것은 「검증을 통과했는가 / 통과했다면 어떤 본문이
// 나가는가」이고, 서버가 그 본문을 어떻게 다루는지는 tests/regressions/400-… 의 몫이다.

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiCall = vi.fn(async () => ({ message: "ok" }));
vi.mock("@/utils/common/api/client", () => ({ apiCall: (...args: any[]) => apiCall(...(args as [])) }));

import { updateAdminUser } from "@/services/common/adminUserService";

const BASE = { email: "target@example.com", name: "이름", use_at: "Y", appr_at: "Y" };

beforeEach(() => {
  apiCall.mockClear();
});

describe("updateAdminUser — 손상된 workspace_id 는 회선에 오르지 못한다", () => {
  it.each([
    ["숫자로 안 읽히는 문자열", "garbage"],
    ["지수 표기(→300)", "3e2"],
    ["16진수 표기(→16)", "0x10"],
    ["빈 배열", []],
  ])("%s 은 검증에서 막히고 apiCall 을 부르지 않는다", async (_label, workspace_id) => {
    // 결함이 있을 때: 검증 통과 + workspace_id 키가 사라진 본문이 PUT 으로 나갔다.
    await expect(updateAdminUser({ ...BASE, workspace_id })).rejects.toMatchObject({
      response: { status: 422 },
    });
    expect(apiCall).not.toHaveBeenCalled();
  });

  // 거절이 정상 경로를 갉아먹지 않는지 — 화면이 실제로 보내는 형태다. SelectBox 는
  // `valueExpr="id"`(WorkspaceOptionOut.id: number)를, clear 버튼은 null 을 낸다.
  it.each([
    ["숫자 (SelectBox 선택)", 7, 7],
    ["null (clear 버튼)", null, undefined],
  ])("workspace_id 가 %s 이면 그대로 나간다", async (_label, workspace_id, expected) => {
    await updateAdminUser({ ...BASE, workspace_id });

    expect(apiCall).toHaveBeenCalledTimes(1);
    const [, options] = apiCall.mock.calls[0] as any[];
    expect(options.method).toBe("PUT");
    expect(options.data.workspace_id).toBe(expected);
  });
});
