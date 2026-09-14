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
    // 이 스위트는 **직렬**이다. dbtest 6개 파일이 Postgres 하나를 나눠 쓰며 같은 author_id 를 upsert/create 로 심는다
    // (`tests/regressions/*.dbtest.ts`) — 파일이 동시에 돌면 유니크 위반이 난다. 22코어 병렬로 통과하던 것은 스케줄 운이었고,
    // 상한 4 로 스케줄이 바뀌자 #362 테스트가 `Unique constraint failed on (author_id)` 로 드러났다 (2026-08-28, run 33145733926).
    fileParallelism: false,
    maxWorkers: 1,
    include: ["tests/**/*.dbtest.?(c|m)[jt]s?(x)"],
    environment: "node",
    // 검사 대상이 0건이면 실패한다 — vitest.config.ts 와 같은 원칙(#252).
    passWithNoTests: false,
  },
});
