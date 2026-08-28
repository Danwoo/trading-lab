import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * 실제 Postgres 를 상대로 도는 통합 테스트(`*.dbtest.ts`) 전용 설정 — `vitest.config.ts` 와
 * 분리한 이유는 `npm test`(기본 설정)를 DB 없는 환경에서도 항상 돌게 유지하기 위해서다. 이
 * 설정으로만 수집되는 파일은 `DATABASE_URL` 이 가리키는 스키마가 준비돼 있어야 통과한다
 * (배치·실행 방법은 `tests/lib/auth/deleteUserCascade.dbtest.ts` 상단 주석 참고).
 *
 * `npm run test:db` 로 돈다. 기본 `npm test` 의 include 글롭(`*.{test,spec}.*`)과 이 설정의
 * include(`*.dbtest.*`)는 겹치지 않으므로 같은 테스트가 두 번 돌거나 빠지는 일이 없다.
 */
export default defineConfig({
  resolve: {
    alias: { "@": rootDir },
  },
  test: {
    // 병렬 상한 — 기본값은 CPU 코어 수(이 기계 22)만큼 프로세스를 띄워 한 번의 npm test 가 3GB 를 넘겼다.
    // 워커·self-hosted 러너가 같은 16GB VM 을 나눠 쓰므로 4 로 고정한다 (2026-08-28 실측: 18 프로세스 3,201MB).
    maxWorkers: 4,
    minWorkers: 1,
    include: ["tests/**/*.dbtest.?(c|m)[jt]s?(x)"],
    environment: "node",
    // 검사 대상이 0건이면 실패한다 — vitest.config.ts 와 같은 원칙(#252).
    passWithNoTests: false,
  },
});
