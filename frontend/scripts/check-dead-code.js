#!/usr/bin/env node
// 죽은 코드(아무도 안 부르는 파일·export·의존성)가 **늘어나지 않게** 상한으로 잠근다.
//
// knip 이 내는 목록을 그대로 지우면 CI 가 깨진다 — 이 레포의 소비자 상당수가 TypeScript
// import 그래프 밖에 있기 때문이다(워크플로가 `node` 로 실행하는 스크립트, 파이썬 그물이
// 경로로 열어 정규식으로 파싱하는 상수, prisma 가 문자열로 지정하는 생성기). 그 사실 선언은
// `frontend/knip.jsonc` 에 이유와 함께 적혀 있고, 여기서는 **선언 뒤에 남은 수**만 센다.
//
// ── 상한은 정확히 일치해야 한다 (≤ 가 아니라 =) ─────────────────────────────
// 죽은 코드를 실제로 걷어낸 PR 은 `CEILINGS` 도 함께 내려야 통과한다. 「줄었으니 통과」로
// 두면 상한이 현실보다 위에 떠 있게 되고, 그만큼의 새 죽은 코드가 조용히 들어올 자리가 생긴다.
// 남긴다고 판정한 항목은 목록에 그대로 보인다 — 설정으로 감추지 않는 것이 의도다.
//
// ── fail-closed ────────────────────────────────────────────────────────────
//   · knip 실행이 실패하거나 출력이 JSON 이 아니면 실패한다 (「안 돌았다」는 「위반 없다」가 아니다).
//   · 스캔 대상 소스 파일이 `MIN_SOURCE_FILES` 미만이면 실패한다 — 경로가 옮겨져 knip 이
//     빈 프로젝트를 보고 「미사용 0건」을 내는 상태를 통과시키지 않는다.
//   · knip 출력의 축(카테고리) 이름이 아래 목록과 어긋나면 실패한다 — 버전이 올라 축이
//     사라지면 그 축의 위반이 통째로 안 보인다.
//   · 자체 그물: 합계 함수를 합성 payload 로 두들겨, 세는 자리가 실제로 세는지 매번 확인한다.
//
// 실행: `cd frontend && node scripts/check-dead-code.js`

import { spawnSync } from "node:child_process";
import { readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// 버전을 박는다 — knip 은 마이너 사이에도 판정이 달라질 수 있어, 고정하지 않으면 같은 커밋이
// 날마다 다른 수를 낸다. 올릴 때는 이 상수와 knip.jsonc 의 `$schema` 를 같이 올린다.
const KNIP_VERSION = "5.88.1";

// 축별 상한 — **현재 실측치**다. 값의 근거(항목별 판정)는 이 파일을 들인 PR 본문의 판정표.
const CEILINGS = {
  // utils/common/locale/index.ts — 어느 TS 모듈도 import 하지 않는다(전수 grep). 지우려면
  // frontend/CLAUDE.md 의 「순수 유틸」 규칙 문장과 세 곳의 주석을 함께 옮겨야 해 이번엔 남겼다.
  files: 1,
  dependencies: 0,
  // patch-package — frontend/patches/ 가 없고 postinstall 도 `prisma generate` 하나뿐이라
  // 아무도 안 부른다. 그런데 이것을 지우면 npm 이 `yaml@2.8.3` 을 트리에서 함께 걷어내고,
  // 그 패키지는 THIRD-PARTY-NOTICES.md 의 **프로덕션** 목록에 올라 있다 — 고지 문서를 다시
  // 만들어야 하는 변경이라 이번 범위 밖으로 뒀다.
  devDependencies: 1,
  optionalPeerDependencies: 0,
  unlisted: 0,
  binaries: 0,
  unresolved: 0,
  // 공용 UI 프리미티브·서비스 CRUD·zod 헬퍼 — 신규 엔티티 스캐폴드가 쓰는 어휘라 남겼다.
  exports: 27,
  types: 10,
  enumMembers: 0,
  // 스키마 배럴의 의도적 별칭(`XCreateInSchema = XSchema`)과 `export default` 재노출.
  duplicates: 7,
};

// knip JSON 의 축 이름. 이 목록과 실제 출력이 어긋나면 실패한다 (버전 상승으로 축이 사라져도
// 조용히 0건이 되지 않게).
const PER_FILE_AXES = [
  "dependencies",
  "devDependencies",
  "optionalPeerDependencies",
  "unlisted",
  "binaries",
  "unresolved",
  "exports",
  "types",
  "enumMembers",
  "duplicates",
];

const SKIP_DIRS = new Set(["node_modules", ".next", ".git", "coverage", "generated"]);
const SOURCE_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"];
// 실측 503개. 크게 밑돌면 스캔 루트가 어긋난 것으로 본다.
const MIN_SOURCE_FILES = 400;

function fail(message) {
  console.error(`\n[check-dead-code] ${message}`);
  process.exit(1);
}

function countSourceFiles(dir) {
  let total = 0;
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) total += countSourceFiles(full);
    else if (SOURCE_EXTENSIONS.includes(path.extname(entry))) total += 1;
  }
  return total;
}

/** knip JSON 리포트를 축별 건수로 접는다. 알 수 없는 축이 있으면 예외를 던진다. */
function countIssues(report) {
  if (!Array.isArray(report?.files) || !Array.isArray(report?.issues)) {
    throw new Error("knip 출력에 files/issues 배열이 없습니다");
  }
  const counts = { files: report.files.length };
  for (const axis of PER_FILE_AXES) counts[axis] = 0;

  for (const issue of report.issues) {
    for (const axis of PER_FILE_AXES) {
      const value = issue[axis];
      if (value === undefined) throw new Error(`knip 출력에 축 '${axis}' 가 없습니다 (버전이 바뀌었습니까?)`);
      // enumMembers 는 `{ 열거형이름: [멤버...] }` 모양, 나머지는 배열.
      counts[axis] += Array.isArray(value)
        ? value.length
        : Object.values(value).reduce((sum, members) => sum + members.length, 0);
    }
  }
  return counts;
}

/** 세는 자리가 실제로 세는지 매번 확인한다 — 통과가 「0건」인지 「안 셌다」인지 가른다. */
function selfTest() {
  const probe = {
    files: ["a.ts", "b.ts"],
    issues: [
      {
        file: "package.json",
        dependencies: [{ name: "x" }],
        devDependencies: [],
        optionalPeerDependencies: [],
        unlisted: [],
        binaries: [],
        unresolved: [],
        exports: [{ name: "e1" }, { name: "e2" }],
        types: [{ name: "T" }],
        enumMembers: { Color: [{ name: "RED" }, { name: "BLUE" }] },
        duplicates: [[{ name: "a" }, { name: "default" }]],
      },
    ],
  };
  const got = countIssues(probe);
  const expected = {
    files: 2,
    dependencies: 1,
    devDependencies: 0,
    optionalPeerDependencies: 0,
    unlisted: 0,
    binaries: 0,
    unresolved: 0,
    exports: 2,
    types: 1,
    enumMembers: 2,
    duplicates: 1,
  };
  for (const [axis, value] of Object.entries(expected)) {
    if (got[axis] !== value) {
      fail(`자체 그물 실패 — 축 '${axis}' 를 ${got[axis]} 로 셌습니다 (기대 ${value}).`);
    }
  }
  console.log(`[check-dead-code] 자체 그물 — 축 ${Object.keys(expected).length}종 집계 확인.`);
}

selfTest();

const sourceFiles = countSourceFiles(frontendDir);
if (sourceFiles < MIN_SOURCE_FILES) {
  fail(
    `스캔 대상 소스 파일이 ${sourceFiles}개입니다 (하한 ${MIN_SOURCE_FILES}) — ` +
      "경로가 옮겨졌거나 확장자 필터가 어긋났습니다. 대상이 없는 상태로 통과시키지 않습니다.",
  );
}

const result = spawnSync("npx", ["--yes", `knip@${KNIP_VERSION}`, "--no-config-hints", "--reporter", "json"], {
  cwd: frontendDir,
  encoding: "utf8",
  maxBuffer: 64 * 1024 * 1024,
});

if (result.error) fail(`knip 을 실행하지 못했습니다: ${result.error.message}`);
// knip 은 위반이 있으면 exit 1, 실행 자체가 실패하면 2 이상을 낸다.
if (result.status !== 0 && result.status !== 1) {
  fail(`knip 이 exit ${result.status} 로 끝났습니다:\n${(result.stderr || result.stdout || "").slice(0, 2000)}`);
}

let report;
try {
  report = JSON.parse(result.stdout);
} catch (error) {
  fail(`knip 출력이 JSON 이 아닙니다 (${error.message}):\n${(result.stdout || result.stderr || "").slice(0, 2000)}`);
}

let counts;
try {
  counts = countIssues(report);
} catch (error) {
  fail(`${error.message} — 축이 사라지면 그 축의 위반이 통째로 안 보입니다.`);
}

console.log(`[check-dead-code] knip@${KNIP_VERSION} · 소스 파일 ${sourceFiles}개 스캔`);
for (const axis of Object.keys(CEILINGS)) {
  console.log(`  · ${axis}: ${counts[axis]}건 (상한 ${CEILINGS[axis]})`);
}

const over = [];
const under = [];
for (const [axis, ceiling] of Object.entries(CEILINGS)) {
  if (counts[axis] > ceiling) over.push(`${axis}: ${counts[axis]} > ${ceiling}`);
  else if (counts[axis] < ceiling) under.push(`${axis}: ${counts[axis]} < ${ceiling}`);
}

if (over.length > 0) {
  console.error("\n[check-dead-code] 죽은 코드가 상한을 넘었습니다:");
  for (const line of over) console.error(`  · ${line}`);
  console.error(
    "\n  목록을 보려면: cd frontend && npx --yes knip@" +
      KNIP_VERSION +
      " --no-config-hints --reporter compact\n" +
      "  TS 밖에 소비자가 있는 것이면 knip.jsonc 에 **이유와 함께** 선언하세요 (지우면 CI 가 깨집니다).\n",
  );
  process.exit(1);
}

if (under.length > 0) {
  console.error("\n[check-dead-code] 죽은 코드가 상한보다 줄었습니다 — CEILINGS 도 함께 내리세요:");
  for (const line of under) console.error(`  · ${line}`);
  console.error("\n  상한이 현실보다 위에 떠 있으면 그만큼 새 죽은 코드가 조용히 들어옵니다.\n");
  process.exit(1);
}

console.log("[check-dead-code] 모든 축이 상한과 같습니다 — 통과.");
