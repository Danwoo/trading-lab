#!/usr/bin/env node
// #342 — anti-patterns-frontend.md 룰 4 의 Detection(`git grep -nE "from ['\"]devextreme" --
// 'frontend/components/features/Terminal/**' ...`)은 **직접 import 문자열**만 본다. 터미널/
// 패널 진입점이 shared 훅(`hooks/shared/**`)을 거쳐 devextreme 을 물면(예: useServerTable →
// showToast → Feedback 배럴 → ToastNotification.tsx → devextreme-react/toast) 그 direct grep
// 은 0 hit 인데 실제로는 devextreme 의 테마 초기화 코드(모듈 import 시점에 setInterval 을
// 건다, 24.2.15 기준 cjs/ui/themes.js)가 로드된다 — 이게 CI 에서만 간헐적으로 터진 #342 의
// 근본 원인이다(로컬은 빨라서 안 걸리고, 느린 CI 러너에서 파일 경계를 넘어 살아남는다).
//
// 이 스크립트는 rule 4 와 같은 진입점 글롭에서 시작해 **로컬 import 그래프**(`@/` 별칭·상대
// 경로)를 실제로 따라가며, 그 경로가 도달하는 파일 중 `devextreme`/`devextreme-react` 를
// import 하는 파일이 있는지 확인한다. node_modules 내부까지 들어가지 않는다 — 그 경계에서
// 멈추고 "이 지점에서 devextreme 로 나간다"만 기록한다(전체 그래프 추적이 아니라 진입점
// 스코프만 보는 이유는 anti-patterns-frontend.md 룰 4 Detection 과 동일 — 비용 대비 이 클래스
// 결함은 항상 터미널/패널 경로에서 났다, #342).
//
// #381 로 위 `useServerTable → showToast → ToastNotification.tsx → devextreme-react/toast`
// 경로는 해소됐다 — `showToast`(순수 큐 함수, toastQueue.ts)와 실제 렌더(ToastNotification.tsx,
// 이제 devextreme 미의존)를 분리해 EXPECTED_HITS 의 해당 항목을 지웠다. #383 이 나머지 한
// 통로(`lib/zod/helpers.ts -> utils/common/locale/index.ts -> devextreme/localization`)도
// zodBootstrap.ts 분리로 해소해, 진입점 42건 기준 남은 hit 은 0건이다 — EXPECTED_HITS 는 아래
// 빈 Set 이다(PR #385, 병합 결함으로 한 번 되돌아갔다가 바로잡힘).
//
// 검사 대상이 0건이면(진입점 글롭이 사라지거나 옮겨졌는데 스크립트가 그대로면) 실패한다 —
// "위반 없음"과 "아무것도 안 봤음"을 구분하기 위해서다.
//
// ── 스코프: frontend 전체 (#341 완주) ────────────────────────────────────────
// 파일 이름은 역사적이다("terminal"). 한때는 devextreme 이 살아 있는 채로 **일부 영역만**
// 지켰다 — ① 터미널·패널 신규 코드 격리(#342) ② 이관 완료 영역 되돌리기 금지(#341 ⑤)
// ③ 전역 진입점 RootLayout(#381). #341 이 devextreme 을 앱에서 통째로 걷어내면서 그 셋을
// 나눌 이유가 사라졌다: **어디서든 devextreme 을 다시 들이면 위반**이다.
// 그래서 진입점은 이제 frontend 소스 전체이고, 알려진(허용) hit 은 0건이다.
// ─────────────────────────────────────────────────────────────────────────────

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// frontend 소스 전체가 진입점이다. 아래 디렉터리만 건너뛴다:
//   node_modules(외부 코드) · .next(빌드 산출) · public(정적 자산) · prisma(스키마)
// **여기에 디렉터리를 추가하면 그만큼 사각지대가 생긴다** — 추가할 땐 이유를 옆에 적어라.
const SKIP_DIRS = new Set(["node_modules", ".next", ".git", "coverage", "public", "prisma"]);

const SCOPES = [{ label: "frontend 전체", root: ".", issue: "#341" }];

// 이 스크립트 자신은 검사 대상에서 뺀다 — 아래 `selfTestExtractImports()` 가 정규식을 두들기려고
// `import "devextreme"` 같은 **문자열 리터럴**을 일부러 담고 있어서, 자기 자신을 훑으면 그
// 픽스처가 위반으로 잡힌다. 이 파일이 devextreme 을 실제로 import 하는 일은 없다(순수 정적 스캔).
const SELF_PATH = fileURLToPath(import.meta.url);

const EXTENSIONS = [".ts", ".tsx", ".js", ".jsx"];
// import/export 문 전 형태를 커버한다 — 하나라도 빠지면 그 형태로 들어온 devextreme 의존이
// 조용히 안 잡힌다(#342 처리 중 지휘자가 부작용 전용 import 로 실측 발견). 형태별 실측은
// 커밋 메시지의 "형태별 주입→검출→복원" 표 참고.
//   from 절이 있는 모든 형태 — import x from "x" · import { a } from "x" · import * as x
//   from "x" · export { a } from "x"(배럴의 본체) · export * from "x" · export * as ns from "x".
const FROM_IMPORT_RE = /\bfrom\s+["']([^"']+)["']/g;
// from 절이 없는 순수 부작용 import — import "x"; · import 'x';. `import(` 다음 바로 괄호가
// 오는 동적 import 와는 별개 정규식(아래 DYNAMIC_IMPORT_RE)이라 여기선 걸리지 않는다(괄호는
// 이 정규식이 요구하는 "따옴표가 바로 옴"과 안 맞는다).
const SIDE_EFFECT_IMPORT_RE = /\bimport\s*["']([^"']+)["']/g;
const DYNAMIC_IMPORT_RE = /\bimport\(\s*["']([^"']+)["']\s*\)/g;
const REQUIRE_RE = /\brequire\(\s*["']([^"']+)["']\s*\)/g;

// ── 차단 대상 판별 ────────────────────────────────────────────────────────────
// #341 이 걷어낸 것은 6종이다 — 직접 의존 둘(`devextreme`·`devextreme-react`)과 그 둘이
// 끌고 오던 전이 넷(`devexpress-diagram`·`devexpress-gantt`·`@devexpress/utils`·
// `@devextreme/runtime`). 종전 정규식 `/^devextreme(-react)?(\/|$)/` 은 앞의 둘만 봤고,
// 나머지 넷은 이 그물을 조용히 통과했다(PR #417 독립 리뷰가 주입으로 실증).
//
// 이름을 6개 열거하는 대신 **계열 전체**를 막는다. 열거는 새 상용 패키지
// (`devextreme-angular`·`devexpress-richedit` 등)를 놓치는데, "그물의 선언된 범위와 실제
// 범위가 갈리는 것"이 정확히 이 레포가 반복해 데어 온 클래스다. 계열로 막으면 목록을
// 관리할 필요가 없고, 예외는 아래 허용 목록 한 자리에서만 생긴다.
const DEVEXTREME_FAMILY_RE = /^(@devextreme\/|@devexpress\/|devextreme|devexpress-)/;

// 계열 이름을 닮았지만 상용 DevExtreme 배포판이 **아닌** 것. 항목을 더하려면 라이선스 근거를
// 옆에 적어라 — 이 목록이 그물에 뚫는 유일한 구멍이다.
//   devextreme-exceljs-fork: 이름과 달리 MIT `exceljs` 포크(순수 xlsx 라이터).
//     `useExcelExport`·`useTableExport` 가 워크북 생성에 쓴다 (anti-patterns-frontend.md 룰 4).
const ALLOWED_PACKAGES = new Set(["devextreme-exceljs-fork"]);

// import 지정자에서 패키지 이름만 떼어낸다 — `devextreme/dist/css/dx.light.css` → `devextreme`,
// `@devexpress/utils/lib/utils` → `@devexpress/utils`. 서브경로를 붙인 채로 정규식을 돌리면
// 허용 목록이 정확 매칭을 못 한다.
function packageNameOf(specifier) {
  const parts = specifier.split("/");
  return specifier.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
}

// 로컬 경로(`@/...`·상대 경로)는 여기 오기 전에 걸러지지 않으므로 스스로 배제한다 —
// `@/lib/devextreme/...` 같은 우리 코드 경로를 패키지로 오인하면 안 된다.
function isBannedDevExtremePackage(specifier) {
  if (specifier.startsWith(".") || specifier.startsWith("@/")) return false;
  const pkg = packageNameOf(specifier);
  if (ALLOWED_PACKAGES.has(pkg)) return false;
  return DEVEXTREME_FAMILY_RE.test(pkg);
}

// 알려진·허용 hit — **비어 있다.** #341 로 devextreme 은 앱에서 완전히 사라졌고
// package.json 에서도 빠졌다. 여기에 무언가를 되살리는 것은 되돌리기이므로, 항목을 추가하려면
// 이슈 참조와 함께 그 이유를 옆에 적어라.
//
// 비어 있으면 "알려진 hit 이 다시 잡히는가"(missingKnown) 축이 자명하게 통과해 **순회가 통째로
// 죽어도 초록**이 될 수 있다(PR #385 독립 리뷰가 남긴 지적). 그 리브니스는 아래
// `assertGraphWalkAlive()` 가 대신 지킨다 — devextreme 이 아닌 **실재하는 로컬 체인**을 매번
// 다시 따라가, 별칭 해석·CSS 해석·그래프 순회가 살아 있는지 확인한다.
const EXPECTED_HITS = new Set([]);

// 순회 리브니스 픽스처 — "app/layout.tsx 에서 styles/globals.css 에 닿는다". `@/` 별칭 해석 ·
// 확장자 없는 경로 해석 · CSS 파일까지 따라가기 · BFS 자체가 전부 동작해야만 성립하는 체인이다.
// devextreme 과 무관한 체인이라 위반 목록이 비어도 이 축은 계속 살아 있다.
const LIVENESS_ENTRY = "app/layout.tsx";
const LIVENESS_TARGET = "styles/globals.css";

function collectEntryFiles(root) {
  const abs = path.join(frontendDir, root);
  if (!existsSync(abs)) {
    console.error(
      `[check-terminal-devextreme-transitive] 진입점 루트가 없습니다: ${root} — ` +
        `디렉터리를 옮겼다면 이 스크립트도 함께 고치세요.`,
    );
    process.exit(1);
  }
  const files = [];
  walk(abs, files);
  return files;
}

function walk(dir, out) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const abs = path.join(dir, name);
    const st = statSync(abs);
    if (st.isDirectory()) {
      walk(abs, out);
    } else if (EXTENSIONS.includes(path.extname(name)) && abs !== SELF_PATH) {
      // 테스트 파일도 본다 — 테스트가 devextreme 을 되살리면 package.json 에서 지운 의존성이
      // 다시 필요해지고, 그건 앱 코드가 되살린 것과 같은 되돌리기다(#341 이전에는 제외했다).
      out.push(abs);
    }
  }
}

function resolveLocal(specifier, fromFile) {
  let base;
  if (specifier.startsWith("@/")) {
    base = path.join(frontendDir, specifier.slice(2));
  } else if (specifier.startsWith(".")) {
    base = path.join(path.dirname(fromFile), specifier);
  } else {
    return null; // bare specifier(node_modules) — 별도 처리
  }
  if (existsSync(base) && statSync(base).isFile()) return base;
  for (const ext of EXTENSIONS) {
    if (existsSync(base + ext)) return base + ext;
  }
  for (const ext of EXTENSIONS) {
    const indexPath = path.join(base, `index${ext}`);
    if (existsSync(indexPath)) return indexPath;
  }
  return null; // 타입 전용 경로(.d.ts)·별칭 미매칭 등 — 조용히 건너뛴다
}

// 정규식 로직을 파일 I/O 에서 떼어낸 순수 함수 — 아래 selfTest() 가 합성 스니펫으로 직접
// 두들겨본다(파일을 실제로 쓰고 지우지 않고도 각 import/export 형태가 잡히는지 확인).
function extractSpecifiersFromSource(src) {
  const specifiers = [];
  for (const re of [FROM_IMPORT_RE, SIDE_EFFECT_IMPORT_RE, DYNAMIC_IMPORT_RE, REQUIRE_RE]) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(src))) specifiers.push(m[1]);
  }
  return specifiers;
}

function extractImports(filePath) {
  return extractSpecifiersFromSource(readFileSync(filePath, "utf8"));
}

// 검사 자신을 위한 그물 — import/export 형태 중 하나라도 정규식이 못 읽게 되면(회귀) 여기서
// 바로 실패한다. 파일 그래프를 따라가는 본검사와 달리 이건 순수 문자열 스니펫이라 항상,
// 실제 소스 트리 상태와 무관하게 돈다 — "검사가 조용히 죽었는지" 매 실행마다 스스로 확인.
function selfTestExtractImports() {
  const cases = [
    ['import "devextreme";', "부작용 전용(쌍따옴표)"],
    ["import 'devextreme';", "부작용 전용(홑따옴표)"],
    ['import devextreme from "devextreme";', "default import"],
    ['import { Toast } from "devextreme";', "named import"],
    ['import * as devextreme from "devextreme";', "namespace import"],
    ['export { Toast } from "devextreme";', "재수출(named) — 배럴의 본체"],
    ['export * from "devextreme";', "전체 재수출"],
    ['export * as ns from "devextreme";', "네임스페이스 재수출"],
    ['await import("devextreme");', "동적 import"],
    ['require("devextreme");', "CJS require"],
  ];
  const failed = [];
  for (const [snippet, label] of cases) {
    const found = extractSpecifiersFromSource(snippet);
    if (!found.includes("devextreme")) failed.push(label);
  }
  if (failed.length > 0) {
    console.error(
      `[check-terminal-devextreme-transitive] 자체 그물 실패 — 아래 import/export 형태를 정규식이 못 읽습니다:\n` +
        failed.map((l) => `  - ${l}`).join("\n"),
    );
    process.exit(1);
  }
  console.log(`[check-terminal-devextreme-transitive] 자체 그물 — import/export 형태 ${cases.length}종 전부 확인.`);
}

// 두 번째 자체 그물 — **어떤 패키지를 막는가**. 위 selfTestExtractImports() 가 "import 문을
// 읽는가"를 지킨다면 이쪽은 "읽은 이름을 차단 대상으로 판정하는가"를 지킨다. 종전에는 이 축의
// 그물이 아예 없어서, 걷어낸 6종 중 4종을 못 잡는 정규식이 아무 경고 없이 초록이었다.
// 서브경로·스코프·허용 포크·우리 로컬 경로를 한 번에 두들긴다.
function selfTestPackageMatcher() {
  const banned = [
    ["devextreme", "직접 의존 ①"],
    ["devextreme/dist/css/dx.light.css", "직접 의존 ① — 서브경로"],
    ["devextreme-react", "직접 의존 ②"],
    ["devextreme-react/data-grid", "직접 의존 ② — 서브경로"],
    ["devexpress-diagram", "전이 의존 ③"],
    ["devexpress-gantt", "전이 의존 ④"],
    ["@devexpress/utils", "전이 의존 ⑤ — 스코프"],
    ["@devexpress/utils/lib/utils/debounce", "전이 의존 ⑤ — 스코프 서브경로"],
    ["@devextreme/runtime", "전이 의존 ⑥ — 스코프"],
    ["@devextreme/runtime/common", "전이 의존 ⑥ — 스코프 서브경로"],
    ["devextreme-angular", "계열 신규(열거 아닌 계열 차단인지)"],
  ];
  const allowed = [
    ["devextreme-exceljs-fork", "MIT exceljs 포크 — 허용 목록"],
    ["@/components/shared/DataTable", "우리 별칭 경로"],
    ["./legacyColumns", "상대 경로"],
    ["@tanstack/react-table", "무관한 스코프 패키지"],
    ["exceljs", "무관한 패키지"],
  ];

  const failed = [];
  for (const [specifier, label] of banned) {
    if (!isBannedDevExtremePackage(specifier)) failed.push(`차단 실패 — ${label}: ${specifier}`);
  }
  for (const [specifier, label] of allowed) {
    if (isBannedDevExtremePackage(specifier)) failed.push(`오탐 — ${label}: ${specifier}`);
  }
  if (failed.length > 0) {
    console.error(
      `[check-terminal-devextreme-transitive] 자체 그물 실패 — 패키지 판정이 어긋났습니다:\n` +
        failed.map((l) => `  - ${l}`).join("\n"),
    );
    process.exit(1);
  }
  console.log(
    `[check-terminal-devextreme-transitive] 자체 그물 — 패키지 판정 ${banned.length}건 차단 / ` +
      `${allowed.length}건 허용 전부 확인(#341 대상 6종 포함).`,
  );
}

selfTestExtractImports();
selfTestPackageMatcher();

// 진입점 1개에서 BFS — devextreme 에 처음 닿는 경로(체인)를 기록한다.
function traceFromEntry(entryFile) {
  const rel = path.relative(frontendDir, entryFile);
  const visited = new Set([entryFile]);
  const queue = [[entryFile, [rel]]];
  const hits = [];
  let visitedCount = 0;

  while (queue.length > 0) {
    const [file, chain] = queue.shift();
    visitedCount += 1;
    for (const specifier of extractImports(file)) {
      if (isBannedDevExtremePackage(specifier)) {
        hits.push({ chain: [...chain, specifier].join(" -> ") });
        continue;
      }
      const resolved = resolveLocal(specifier, file);
      if (!resolved || visited.has(resolved)) continue;
      visited.add(resolved);
      queue.push([resolved, [...chain, path.relative(frontendDir, resolved)]]);
    }
  }
  return { hits, visitedCount };
}

// 순회 리브니스 — EXPECTED_HITS 가 비어 있어도 "그래프 순회가 실제로 도는지"를 매 실행 확인한다.
// devextreme 과 무관한 실재 체인(app/layout.tsx → styles/globals.css)을 따라가므로, 위반이
// 0건이라는 통과가 "아무것도 안 봤음"인지 "정말 없음"인지 구분된다.
function assertGraphWalkAlive() {
  const entry = path.join(frontendDir, LIVENESS_ENTRY);
  const target = path.join(frontendDir, LIVENESS_TARGET);
  if (!existsSync(entry) || !existsSync(target)) {
    console.error(
      `[check-terminal-devextreme-transitive] 리브니스 픽스처 파일이 없습니다 — ` +
        `${LIVENESS_ENTRY} 또는 ${LIVENESS_TARGET} 를 옮겼다면 이 스크립트의 상수도 고치세요.`,
    );
    process.exit(1);
  }

  const visited = new Set([entry]);
  const queue = [entry];
  while (queue.length > 0) {
    const file = queue.shift();
    if (file === target) {
      console.log(
        `[check-terminal-devextreme-transitive] 순회 리브니스 — ${LIVENESS_ENTRY} → ${LIVENESS_TARGET} 도달 확인.`,
      );
      return;
    }
    for (const specifier of extractImports(file)) {
      const resolved = resolveLocal(specifier, file);
      if (!resolved || visited.has(resolved)) continue;
      visited.add(resolved);
      queue.push(resolved);
    }
  }

  console.error(
    `[check-terminal-devextreme-transitive] 순회 리브니스 실패 — ${LIVENESS_ENTRY} 에서 ` +
      `${LIVENESS_TARGET} 에 닿지 못했습니다(방문 ${visited.size}건). 별칭·확장자 해석이나 그래프 ` +
      `순회가 죽었을 수 있습니다. 두 파일의 실제 import 관계가 끊긴 것이라면 위 상수를 바꾸세요.`,
  );
  process.exit(1);
}

assertGraphWalkAlive();

let totalEntryFiles = 0;
let totalVisited = 0;
const unexpected = [];
const expectedSeen = new Set();

for (const scope of SCOPES) {
  const entryFiles = collectEntryFiles(scope.root);
  // fail-closed — 진입점이 0건이면 "위반 없음"이 아니라 "아무것도 안 봤음"이다.
  if (entryFiles.length === 0) {
    console.error(`[check-terminal-devextreme-transitive] ${scope.label} 진입점 0건 — 글롭이 어긋났습니다.`);
    process.exit(1);
  }
  let scopeVisited = 0;
  for (const entry of entryFiles) {
    const { hits, visitedCount } = traceFromEntry(entry);
    scopeVisited += visitedCount;
    for (const hit of hits) {
      const parts = hit.chain.split(" -> ");
      const key = `${parts[parts.length - 2]} -> ${parts[parts.length - 1]}`;
      if (EXPECTED_HITS.has(key)) {
        expectedSeen.add(key);
      } else {
        unexpected.push(`  - [${scope.issue}] ${path.relative(frontendDir, entry)}: ${hit.chain}`);
      }
    }
  }
  totalEntryFiles += entryFiles.length;
  totalVisited += scopeVisited;
  console.log(
    `[check-terminal-devextreme-transitive] ${scope.label}: 진입점 ${entryFiles.length}건, ` +
      `그래프 노드 방문 ${scopeVisited}건(진입점별 합산, 중복 포함) 검사.`,
  );
}

console.log(`[check-terminal-devextreme-transitive] 합계 진입점 ${totalEntryFiles}건 / 노드 방문 ${totalVisited}건.`);
console.log(`  알려진(허용) hit ${expectedSeen.size}/${EXPECTED_HITS.size}건 확인.`);

const missingKnown = [...EXPECTED_HITS].filter((key) => !expectedSeen.has(key));
if (missingKnown.length > 0) {
  console.error(
    `\n[check-terminal-devextreme-transitive] 알려진 hit ${missingKnown.length}건이 이번엔 안 잡혔습니다 — ` +
      `코드를 고쳐 실제로 해소했다면 EXPECTED_HITS 에서 그 항목을 지우세요.\n`,
  );
  console.error(missingKnown.map((k) => `  - ${k}`).join("\n"));
  process.exit(1);
}

if (unexpected.length > 0) {
  console.error(
    `\n[check-terminal-devextreme-transitive] devextreme 의존 ${unexpected.length}건 발견 — ` +
      `#341 로 앱에서 완전히 걷어낸 라이브러리입니다(package.json 에도 없습니다).\n`,
  );
  console.error([...new Set(unexpected)].join("\n"));
  console.error(
    "\n  대체 수단은 레포에 이미 있습니다 — 폼/오버레이는 radix-ui(components/shared/ui/primitives),",
    "그리드는 @tanstack/react-table(components/shared/DataTable). 정말 되살려야 한다면 이슈를 열고",
    "이 스크립트의 EXPECTED_HITS 에 근거와 함께 등록하세요.\n",
  );
  process.exit(1);
}

console.log("[check-terminal-devextreme-transitive] 새로운 전이 devextreme 의존 0건 — 통과.");
