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
 * 도는 잡에서만 `npx prisma generate` 를 돌린다, `.github/workflows/frontend-ci.yml` 참고).
 *
 * `npm run test:api-regressions` 로 돈다. 기본 `npm test` 의 exclude 에 이 include 대상이 이미
 * 빠져 있으므로 같은 테스트가 두 번 돌거나 빠지는 일이 없다.
 */
export default defineConfig({
  resolve: {
    alias: { "@": rootDir },
  },
  test: {
    include: [
      "tests/regressions/337-path-traversal.test.ts",
      "tests/regressions/389-filter-fail-closed.test.ts",
      "tests/regressions/388-signup-boundary.test.ts",
      "tests/regressions/400-put-full-representation.test.ts",
      "tests/regressions/238-email-immutability.test.ts",
      "tests/regressions/251-personal-workspace-menu.test.tsx",
      "tests/regressions/231-console-otp-dev-only.test.ts",
    ],
    environment: "node",
    // 검사 대상이 0건이면 실패한다 — vitest.config.ts 와 같은 원칙(#252). include 를 파일
    // 하나로 좁혀뒀으므로, 이 파일 경로가 바뀌거나 지워지면 여기서 바로 드러난다.
    passWithNoTests: false,
  },
});
