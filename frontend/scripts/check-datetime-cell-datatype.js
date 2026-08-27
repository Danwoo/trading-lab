#!/usr/bin/env node
// 시각 필드를 그리는 `TableCell` 이 `dataType="datetime"` 을 빠뜨리지 않았는지 본다.
//
// ── 왜 ──────────────────────────────────────────────────────────────────────
// `TableCell` 의 `dataType` 기본값은 `"string"` 이고, 그 갈래는 값을 `String(value)` 로
// 그대로 그린다. 백엔드가 내는 감사 시각은 오프셋이 붙은 인스턴트 문자열이라
// (`2026-08-23T02:24:09+00:00`), `dataType` 이 없으면 화면에 그 자릿수가 **날것으로** 나온다.
// 같은 값을 그리드는 `formatDate()` 로 사용자 타임존에 맞춰 그리므로, 한 화면 안에서 목록과
// 상세가 9시간 갈린다 — 이슈 359 가 없애려는 바로 그 모양이다.
//
// 이 결함은 타입 검사를 통과한다(`dataType` 이 선택 prop 이다). 그래서 정적으로 센다.
//
// ── fail-closed ─────────────────────────────────────────────────────────────
//   · 스캔한 `.tsx` 가 `MIN_FILES` 미만이면 실패한다 — 경로가 옮겨져 「위반 0건」이 되는
//     상태를 통과로 치지 않는다.
//   · 시각 필드에 걸린 셀을 한 건도 못 찾으면 실패한다 — 정규식이 현실과 어긋난 것이다.
//
// 실행: `cd frontend && node scripts/check-datetime-cell-datatype.js`

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOTS = ["components", "app"];
const MIN_FILES = 100;
const MIN_TIME_CELLS = 7;

// 감사·운영 시각 필드. 시장 시각(`ts`·`entry_ts`·`exit_ts`·`nav_dt`)은 뜻이 벽시계라 뺀다 —
// 그쪽은 인스턴트가 아니므로 사용자 타임존으로 옮기면 축이 밀린다.
const TIME_FIELDS = [
  "reg_dt",
  "mod_dt",
  "started_dt",
  "finished_dt",
  "ingested_at",
  "createdAt",
  "updatedAt",
  "expiresAt",
];

const CELL = /<TableCell\b([^>]*)>\s*\{([^}]*)\}/g;

function collect(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "node_modules" || entry === ".next") continue;
      collect(full, out);
    } else if (entry.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

const files = ROOTS.flatMap((root) => {
  const dir = path.join(frontendDir, root);
  try {
    return collect(dir);
  } catch {
    return [];
  }
});

let timeCells = 0;
const violations = [];

for (const file of files) {
  const source = readFileSync(file, "utf8");
  const lineOf = (index) => source.slice(0, index).split("\n").length;
  for (const match of source.matchAll(CELL)) {
    const [, attrs, expression] = match;
    const field = TIME_FIELDS.find((name) => new RegExp(`\\b${name}\\b`).test(expression));
    if (!field) continue;
    timeCells += 1;
    if (!/dataType\s*=\s*["']datetime["']/.test(attrs)) {
      violations.push(`${path.relative(frontendDir, file)}:${lineOf(match.index)} — ${field}`);
    }
  }
}

console.log(`.tsx ${files.length}건 검사 · 시각 필드를 그리는 TableCell ${timeCells}건 (하한 ${MIN_TIME_CELLS})`);

if (files.length < MIN_FILES) {
  console.error(`::error::스캔한 .tsx 가 ${files.length}건뿐이다 (하한 ${MIN_FILES}) — 경로가 어긋났는지 보라`);
  process.exit(1);
}
if (timeCells < MIN_TIME_CELLS) {
  console.error(
    `::error::시각 필드를 그리는 TableCell 을 ${timeCells}건 찾았다 (하한 ${MIN_TIME_CELLS}) — ` +
      "정규식이 현실과 어긋났다(fail-closed)",
  );
  process.exit(1);
}
if (violations.length) {
  console.error(`::error::dataType="datetime" 이 빠진 시각 셀 ${violations.length}건:`);
  for (const line of violations) console.error(`::error::  · ${line}`);
  console.error(
    "::error::없으면 TableCell 이 기본값 string 으로 떨어져 오프셋 문자열을 날것으로 그린다 — " +
      "같은 행이 목록과 상세에서 갈린다 (이슈 359).",
  );
  process.exit(1);
}

console.log('판정: 시각 필드를 그리는 셀이 전부 dataType="datetime" 을 갖는다');
