#!/usr/bin/env node
/**
 * `frontend/prisma/init/tables.sql` 재현 대조 — 커밋된 생성물 == 생성기 출력 (fail-closed).
 *
 * ## 왜 있나
 *
 * `tables.sql` 은 `schema.prisma` 의 `generator table_sql` 이 `prisma generate` 때 덮어쓰는
 * **커밋된 생성물**이다. 이 레포는 다른 두 생성물(브랜드 자산·THIRD-PARTY-NOTICES)에는
 * 「생성기 출력 == 커밋본」 대조를 붙여 왔는데 여기만 없었다.
 *
 * 없으면 무슨 일이 나나: 두 CI 잡이 **서로 다른 스키마를 검증한다.**
 *   · `test: frontend-db` 는 `prisma generate` 뒤에 `tables.sql` 을 적용한다 → 방금 다시 만든 것
 *   · `test: backend-db` 는 generate 를 안 돌린다 → **커밋된 것**
 * `schema.prisma` 만 고치고 재생성을 잊으면 그 둘이 갈리고 아무도 말하지 않는다 (#331).
 *
 * ## 대조 기준은 커밋본(HEAD)이다
 *
 * 작업 트리 파일이 아니라 HEAD 의 blob 을 기준으로 잡는다 — 이 잡의 다른 스텝이 이미
 * `prisma generate` 를 돌렸더라도 판정이 흔들리지 않는다(작업 트리 파일을 기준으로 삼으면
 * 스텝 순서가 바뀌는 순간 「생성물끼리 비교」가 되어 늘 통과한다).
 * 대조 뒤 작업 트리는 실행 전 바이트로 되돌린다.
 *
 * 실행: `node scripts/check-tables-sql-reproducible.js` (cwd=frontend)
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = path.resolve(FRONTEND_DIR, "..");
const TABLES_SQL = path.join(FRONTEND_DIR, "prisma", "init", "tables.sql");
const TRACKED_PATH = "frontend/prisma/init/tables.sql";
const GENERATOR = "table_sql";

function fail(message) {
  console.error(`::error::[tables-sql] ${message}`);
  process.exit(1);
}

if (!fs.existsSync(TABLES_SQL)) {
  fail(`대조 대상이 없습니다: ${TABLES_SQL} — 경로가 바뀌었으면 이 스크립트도 함께 고치세요.`);
}

let committed;
try {
  committed = execFileSync("git", ["show", `HEAD:${TRACKED_PATH}`], {
    cwd: REPO_ROOT,
    maxBuffer: 64 * 1024 * 1024,
  });
} catch (error) {
  fail(`커밋본을 읽지 못했습니다 (HEAD:${TRACKED_PATH}): ${error.message}`);
}
if (committed.length === 0) {
  fail(`커밋본이 0바이트입니다 — 대조할 것이 없습니다 (${TRACKED_PATH}).`);
}

const beforeRun = fs.readFileSync(TABLES_SQL);

let generated;
try {
  execFileSync("npx", ["prisma", "generate", "--generator", GENERATOR], {
    cwd: FRONTEND_DIR,
    stdio: "inherit",
  });
  generated = fs.readFileSync(TABLES_SQL);
} finally {
  fs.writeFileSync(TABLES_SQL, beforeRun);
}

if (generated.length === 0) {
  fail(`생성기 출력이 0바이트입니다 — 생성기가 헛돌았습니다 (generator ${GENERATOR}).`);
}

console.log(`[tables-sql] 대조 1건 — 커밋본 ${committed.length}B · 생성기 출력 ${generated.length}B`);

if (!committed.equals(generated)) {
  fail(
    `${TRACKED_PATH} 이 schema.prisma 에서 다시 나오지 않습니다. ` +
      "`cd frontend && npx prisma generate` 로 다시 만들어 커밋하세요.",
  );
}

console.log("[tables-sql] 커밋본과 생성기 출력이 바이트 동일합니다.");
