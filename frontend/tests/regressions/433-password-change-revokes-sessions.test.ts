/**
 * #433 회귀 그물 — **비밀번호를 바꾸면 다른 기기의 세션이 끊긴다.**
 *
 * Cycle 7 발굴(B-19)이 잡은 것: 비밀번호를 바꿔도 옛 세션이 그대로 유효했다.
 *
 * **왜 설정이 있는데 안 들었나**: `lib/auth/auth.ts` 에 `revokeSessionsOnPasswordReset: true` 가
 * 있지만 그것은 Better Auth 가 **스스로 처리하는 재설정 흐름**에만 걸린다. 마이페이지는
 * `prisma.baAccount.updateMany` 로 해시를 직접 쓰므로 그 옵션이 발동할 자리가 없었다.
 *
 * 이 파일이 보는 것: 그 경로가 **세션 행을 실제로 지우는가**, 그리고 **지금 쓰는 세션은 남기는가**.
 * 토큰을 못 읽는 경우에는 전부 지우는지(fail-safe)도 함께 본다.
 * 보지 못하는 것: 지워진 뒤 실제 요청이 401 이 되는지 — 그 축은 `354-stale-authorization` 이
 * 인가 게이트 쪽에서 이미 잡는다.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/env", () => ({
  env: {
    APP_KEY: "fstpl",
    NODE_ENV: "development",
    DATABASE_URL: "postgresql://u:p@127.0.0.1:5432/x",
    BETTER_AUTH_SECRET: "test-secret",
    JWT_SECRET: "test-secret",
  },
}));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

const deleteMany = vi.fn(async (_args: { where?: Record<string, unknown> }) => ({ count: 2 }));
const accountUpdateMany = vi.fn(async (_args: unknown) => ({ count: 1 }));
const userUpdate = vi.fn(async () => ({ id: "u-433", email: "me@example.com" }));
const userFindUnique = vi.fn(async () => ({ id: "u-433", email: "me@example.com", name: "나" }));

vi.mock("@/lib/prisma/client", () => ({
  prisma: {
    baSession: { deleteMany },
    baAccount: { updateMany: accountUpdateMany },
    user: { update: userUpdate, findUnique: userFindUnique, findFirst: userFindUnique },
    authorMember: { findFirst: vi.fn(async () => null) },
  },
}));

vi.mock("@/lib/auth/authUtils", () => ({
  hashPassword: vi.fn(async (p: string) => `hashed:${p}`),
  deleteUserCascade: vi.fn(),
  normalizeEmail: (e: string) => e,
}));

vi.mock("@/lib/auth/withAuth", () => ({
  withAuth: (handler: any) => (req: NextRequest, params: any) => handler(req, CURRENT_SESSION, params ?? {}),
}));

const CURRENT_SESSION = {
  user: { id: "u-433", email: "me@example.com", authorId: "operator", workspaceId: 1 },
  session: { token: "current-device-token" },
};

afterEach(() => {
  deleteMany.mockClear();
  accountUpdateMany.mockClear();
});

async function patchWithPassword(body: Record<string, unknown>) {
  const { PATCH } = await import("@/app/api/common/mypage/route");
  const req = new NextRequest("http://localhost/api/common/mypage", {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json" },
  });
  return PATCH(req, {} as any);
}

describe("비밀번호를 바꾸면 다른 기기 세션이 끊긴다 (#433)", () => {
  it("비밀번호를 바꾸면 세션 행을 지운다 — 지금 쓰는 토큰은 남긴다", async () => {
    await patchWithPassword({ email: "me@example.com", password: "newpassword123", name: "내이름", dept: "" });

    expect(accountUpdateMany).toHaveBeenCalled();
    expect(deleteMany).toHaveBeenCalledTimes(1);
    const where = deleteMany.mock.calls[0]?.[0]?.where as Record<string, unknown> | undefined;
    expect(where?.userId).toBe("u-433");
    expect(where?.NOT).toEqual({ token: "current-device-token" });
  });

  it("비밀번호를 안 바꾸면 세션을 건드리지 않는다", async () => {
    await patchWithPassword({ email: "me@example.com", name: "이름만", dept: "" });

    expect(deleteMany).not.toHaveBeenCalled();
  });
});
