import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * 실제 API 라우트 핸들러를 import 해서 도는 회귀 테스트 전용 설정 — `vitest.config.ts` 와
 * 분리한 이유는 `npm test`(기본 설정, CI frontend-unit 잡)가 `npm ci --ignore-scripts` 로
 * 생성된 Prisma 클라이언트 없이 항상 돌 수 있게 유지하기 위해서다(vitest.config.ts 의 exclude
 * 주석 참고). 라우트 핸들러(`app/api` 아래 route.ts 파일들)는 `withAuth` → `utils/common/api/responses`
 * → `@/prisma/generated/client` 로 이어지는 체인을 갖고 있어, 이 파일을 import 하는 테스트는
 * 생성된 클라이언트가 있어야 한다 — `vitest.db.config.ts`(dbtest)와 달리 실제 DB 접속은
 * 필요 없고 `prisma generate` 만 있으면 된다(#337 CI 결함 — CI 는 `test:api-regressions` 를
 * 도는 잡에서만 `npx prisma generate` 를 돌린다, `.github/workflows/ci.yml` 참고).
 *
 * `npm run test:api-regressions` 로 돈다. 기본 `npm test` 의 exclude 에 이 include 대상이 이미
 * 빠져 있으므로 같은 테스트가 두 번 돌거나 빠지는 일이 없다.
 */
/**
 * 이 목록이 **유일한 출처**다 — `vitest.config.ts` 가 이것을 그대로 exclude 로 쓴다.
 * 두 곳에 손으로 적으면 새 파일이 한쪽에만 들어가 기본 `npm test` 에서도 같이 돌고
 * (Prisma 클라이언트가 없어) 깨진다. 실제로 #231 에서 그렇게 깨졌다.
 */
export const API_REGRESSION_TESTS = [
  "tests/regressions/337-path-traversal.test.ts",
  "tests/regressions/389-filter-fail-closed.test.ts",
  "tests/regressions/388-signup-boundary.test.ts",
  "tests/regressions/400-put-full-representation.test.ts",
  "tests/regressions/238-email-immutability.test.ts",
  "tests/regressions/251-personal-workspace-menu.test.tsx",
  "tests/regressions/231-console-otp-dev-only.test.ts",
  "tests/regressions/342-email-failure-reason.test.ts",
  "tests/regressions/343-signup-requires-verification.test.ts",
  "tests/regressions/341-signup-grants-operator.test.ts",
  "tests/regressions/354-stale-authorization.test.ts",
  "tests/regressions/423-stream-failure-reason.test.ts",
];

export default defineConfig({
  resolve: {
    alias: { "@": rootDir },
  },
  test: {
    // 병렬 상한 — 기본값은 CPU 코어 수(이 기계 22)만큼 프로세스를 띄워 한 번의 npm test 가 3GB 를 넘겼다.
    // 워커·self-hosted 러너가 같은 16GB VM 을 나눠 쓰므로 4 로 고정한다 (2026-08-28 실측: 18 프로세스 3,201MB).
    maxWorkers: 4,
    include: API_REGRESSION_TESTS,
    environment: "node",
    // 검사 대상이 0건이면 실패한다 — vitest.config.ts 와 같은 원칙(#252). include 를 파일
    // 하나로 좁혀뒀으므로, 이 파일 경로가 바뀌거나 지워지면 여기서 바로 드러난다.
    passWithNoTests: false,
  },
});
