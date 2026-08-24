/**
 * #354 런타임 그물 — **인가 게이트가 「지금의 DB」로 판정하는가.**
 *
 * 재현했던 것(로컬 스택, 시계와 함께): 권한을 회수하고 세션 행이 0이 된 뒤에도 운영자 전용
 * API 가 +203초까지 200 이었고, 관리자가 세션을 강제 종료한 뒤에도 +213초까지, 계정을
 * 비활성으로 바꾼 뒤에도 +276초까지 200 이었다. 셋 다 로그인 시각 + 300초에 끊겼다 —
 * 쿠키 캐시(`maxAge: 5 * 60`)의 수명 그대로다.
 *
 * 여기서는 그 시간축 대신 **판정의 입력**을 잡는다: 세션 행이 담은 스냅샷(로그인 시점의
 * authorId/workspaceId)이 아니라 `resolveAccountContext` 가 낸 현재 값으로 판정하는지,
 * 그리고 둘이 어긋나면 통과시키지 않는지.
 *
 * `resolveAccountContext` 자체(DB 를 읽어 권한·워크스페이스·차단 사유를 내는 부분)는
 * `354-account-context.dbtest.ts` 가 실제 Postgres 로 검사한다 — 여기서 대역을 세우는 이유는
 * 이 파일이 보는 것이 "게이트가 그 값을 어떻게 쓰는가"이기 때문이다.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest, NextResponse } from "next/server";

vi.mock("@/env", () => ({ env: { APP_KEY: "fstpl", NODE_ENV: "development" } }));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));

const getSession = vi.fn();
vi.mock("@/lib/auth/auth", () => ({ auth: { api: { getSession } } }));

const resolveAccountContext = vi.fn();
vi.mock("@/lib/auth/accountContext", () => ({ resolveAccountContext }));

// withAuth 가 정적 import 하는 prisma 연쇄를 막는다 — 이 파일이 보는 축이 아니다.
vi.mock("@/lib/auth/authUtils", () => ({
  assertSameWorkspaceOrSysAdmin: vi.fn(async () => null),
  assertTargetNotSysAdmin: vi.fn(async () => null),
  normalizeEmail: (e: string) => e,
}));

const { withAuth } = await import("@/lib/auth/withAuth");

/** 로그인 시점의 스냅샷 — 운영자, 워크스페이스 1. */
const SNAPSHOT = {
  user: { id: "u-354", email: "victim@example.com" },
  session: { authorId: "operator", workspaceId: 1 },
};

const handled = vi.fn();
const call = (opts = {}) => {
  const route = withAuth(async () => {
    handled();
    return NextResponse.json({ ok: true });
  }, opts);
  return route(new NextRequest("http://localhost/api/common/system/adminuser"), {});
};

afterEach(() => {
  getSession.mockReset();
  resolveAccountContext.mockReset();
  handled.mockReset();
});

function sessionPresent() {
  getSession.mockResolvedValue({ response: SNAPSHOT, headers: new Headers() });
}

describe("#354 인가 게이트", () => {
  it("세션을 읽을 때 쿠키 캐시를 우회한다 (이 한 줄이 결함의 원인이었다)", async () => {
    sessionPresent();
    resolveAccountContext.mockResolvedValue({ block: null, authorId: "operator", workspaceId: 1 });
    await call({ requireOperatorOrAdmin: true });

    expect(getSession).toHaveBeenCalledTimes(1);
    expect(getSession.mock.calls[0][0]?.query?.disableCookieCache).toBe(true);
  });

  it("세션 행이 사라졌으면 401 — 쿠키 캐시가 남아 있어도 핸들러에 못 닿는다", async () => {
    getSession.mockResolvedValue(null);
    const res = await call({ requireOperatorOrAdmin: true });
    expect(res.status).toBe(401);
    expect(handled).not.toHaveBeenCalled();
  });

  it("권한을 회수하면 스냅샷이 operator 라도 401", async () => {
    sessionPresent();
    resolveAccountContext.mockResolvedValue({ block: null, authorId: null, workspaceId: 1 });
    const res = await call({ requireOperatorOrAdmin: true });
    expect(res.status).toBe(401);
    expect(handled).not.toHaveBeenCalled();
  });

  it("계정이 비활성이면 401 — 로그인 시점 1회 검사로는 안 잡히던 자리", async () => {
    sessionPresent();
    resolveAccountContext.mockResolvedValue({ block: "InactiveUser", authorId: null, workspaceId: null });
    const res = await call();
    expect(res.status).toBe(401);
    expect(handled).not.toHaveBeenCalled();
  });

  it("워크스페이스가 옮겨졌으면 401 — 스냅샷으로 서명된 JWT 가 옛 테넌트를 가리키기 때문", async () => {
    sessionPresent();
    resolveAccountContext.mockResolvedValue({ block: null, authorId: "operator", workspaceId: 2 });
    const res = await call();
    expect(res.status).toBe(401);
    expect(handled).not.toHaveBeenCalled();
  });

  it("401 응답은 쿠키 캐시도 버린다 — 화면이 5분간 로그인된 척하지 않게", async () => {
    getSession.mockResolvedValue(null);
    const res = (await call()) as NextResponse;
    const cleared = res.cookies.getAll().filter((c: { name: string }) => c.name.startsWith("fstpl.session_data"));
    expect(cleared.length).toBeGreaterThan(0);
    expect(cleared.every((c: { value: string; maxAge?: number }) => c.value === "" && c.maxAge === 0)).toBe(true);
  });

  it("현재 권한이 스냅샷과 같으면 그대로 통과한다 (정상 경로가 막히지 않는다)", async () => {
    sessionPresent();
    resolveAccountContext.mockResolvedValue({ block: null, authorId: "operator", workspaceId: 1 });
    const res = await call({ requireOperatorOrAdmin: true });
    expect(res.status).toBe(200);
    expect(handled).toHaveBeenCalledTimes(1);
  });
});
