import path from "node:path";
import { fileURLToPath } from "node:url";
import { configDefaults, defineConfig } from "vitest/config";

import { API_REGRESSION_TESTS } from "./vitest.api-regressions.config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  // tsconfig.json 의 paths(`@/*` → `./*`) 와 같은 매핑. 두 곳이 어긋나면 타입은 통과하는데
  // 테스트만 모듈을 못 찾는 상태가 된다.
  resolve: {
    alias: { "@": rootDir },
  },
  test: {
    // 병렬 상한 — 기본값은 CPU 코어 수(이 기계 22)만큼 프로세스를 띄워 한 번의 npm test 가 3GB 를 넘겼다.
    // 워커·self-hosted 러너가 같은 16GB VM 을 나눠 쓰므로 4 로 고정한다 (2026-08-28 실측: 18 프로세스 3,201MB).
    maxWorkers: 4,
    // include 는 vitest 기본값(`**/*.{test,spec}.?(c|m)[jt]s?(x)`)을 그대로 쓴다.
    // `tests/` 로 좁히면 그 밖에 놓인 테스트가 조용히 수집에서 빠진다 — 안 도는 테스트는
    // 없는 테스트보다 나쁘다. 배치 규약(tests/ 아래 소스 경로 미러링)은 CLAUDE.md 가 안내한다.
    // 기본 exclude 는 node_modules·.git 뿐이라 빌드 산출물·생성 코드를 더한다.
    // tests/regressions/337-path-traversal.test.ts 는 실제 라우트 핸들러를 import 하는데,
    // 그 체인(withAuth → utils/common/api/responses → @/prisma/generated/client)이 생성된
    // Prisma 클라이언트를 요구한다 — 이 기본 설정(`npm test`, CI 의 frontend-unit 잡)은
    // `npm ci --ignore-scripts`(postinstall=prisma generate 도 건너뜀)로 도는 게 전제라
    // 클라이언트가 없다(#337 CI 결함 — 로컬은 클라이언트가 하드링크로 이미 있어 통과했는데
    // CI 에서만 `ERR_MODULE_NOT_FOUND` 로 빨강이었다). 그 파일은
    // `vitest.api-regressions.config.ts`(별도 CI 잡, prisma generate 를 먼저 돌림)로 옮겼다 —
    // delete-user-cascade 잡과 같은 격리 패턴(무거운 전제를 지는 테스트는 별도 잡).
    exclude: [
      ...configDefaults.exclude,
      "**/.next/**",
      "prisma/generated/**",
        ...API_REGRESSION_TESTS,
    ],
    // better-auth 세션 아톰이 테스트 파일보다 오래 사는 타이머를 남겨, 환경이 걷힌 뒤
    // `window` 를 만지다 Unhandled Error 를 낸다 — 이유와 대역 값은 그 파일의 주석에.
    setupFiles: ["./tests/support/auth-client-mock.ts"],
    // 기본은 node(빠름) — 순수 유틸 대다수가 여기 해당. DOM 이 필요한 파일(컴포넌트 렌더
    // 테스트)만 파일 최상단 `// @vitest-environment jsdom` 주석으로 opt-in 한다.
    // 경로 글롭(environmentMatchGlobs/test.projects) 대신 파일 단위 주석을 고른 이유:
    // - 위 include 주석과 같은 이유로 경로 기반 설정을 늘리지 않는다 — 글롭과 실제 배치가
    //   갈리면(디렉터리 리팩터 등) 조용히 어긋난다.
    // - 주석을 빠뜨려도 조용히 통과하지 않는다: @testing-library/react 의 render() 가 node
    //   환경에서 즉시 `ReferenceError: document is not defined` 로 죽는다(실측 확인) — 글롭
    //   기반이었어도 결과는 같지만, 파일 단위가 설정 파일 대조 없이 테스트 파일만 보고도
    //   이유를 알 수 있어 더 명시적이다.
    environment: "node",
    // #342 의 DevExtreme 테마 타이머 억제(`tests/setup.ts`)는 #341 로 사라졌다 — jsdom 테스트가
    // DevExtreme 위젯을 하나도 마운트하지 않게 되어(그 파일이 스스로 적어 둔 삭제 조건) 억제할
    // 대상이 없다.
    // 수집된 테스트가 0건이면 실패한다. vitest 기본값과 같지만 명시해서 잠근다 —
    // 검사 대상이 0건인데 초록인 상태는 이 레포에서 실제로 사고를 냈다 (#252).
    // `--passWithNoTests` 플래그도 같은 이유로 쓰지 않는다.
    passWithNoTests: false,
  },
});
