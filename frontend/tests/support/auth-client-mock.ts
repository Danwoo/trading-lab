import { vi } from "vitest";

/**
 * `@/lib/auth/auth-client` 를 전 단위 테스트에서 대역으로 세운다 (`vitest.config.ts` 의 `setupFiles`).
 *
 * **왜 전역인가** — better-auth 의 `useSession` 은 nanostores 아톰을 구독하고, 마지막 구독이
 * 끊긴 **1초 뒤** 정리 타이머가 돈다(`session-refresh.mjs` → `broadcast-channel.mjs`). 그 사이
 * 테스트 파일이 끝나 jsdom 이 걷히면 타이머가 `window` 를 만지다 죽어
 * `ReferenceError: window is not defined` 가 vitest 의 Unhandled Error 로 뜬다 — 실측:
 * `useWriteAccess`(#341)가 관심종목·포트폴리오·실험대·시세 화면에 들어간 뒤 전체 실행에서
 * `WatchlistContainer.test.tsx` 가 이것을 냈다. 파일 하나를 따로 돌리면 안 나므로 **어느 파일이
 * 낼지는 실행 순서가 정한다** — 그래서 파일마다 막지 않고 한 자리에서 끊는다.
 *
 * **화면이 달라지지 않게** 로그아웃 상태(`data: null`)를 돌려준다 — 대역이 없을 때 이 환경이
 * 내던 값과 같다. 세션 있는 상태를 봐야 하는 테스트는 파일에서 `vi.mock` 으로 덮으면 된다
 * (파일 단위 mock 이 setup 의 것을 이긴다).
 */
vi.mock("@/lib/auth/auth-client", () => ({
  authClient: {},
  signIn: vi.fn(),
  signOut: vi.fn(),
  getSession: vi.fn(async () => null),
  useSession: () => ({ data: null, isPending: false, error: null, refetch: vi.fn() }),
}));
