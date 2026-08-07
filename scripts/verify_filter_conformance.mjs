/**
 * #295·#306 — frontend/lib/grid/filters.ts 가 두 언어 공유 입력 세트에서 기대한
 * 방향으로 반응하는지 검증.
 *
 *     node scripts/verify_filter_conformance.mjs
 *
 * 입력 세트는 scripts/fixtures/filter_conformance_cases.json 하나를 backend-service 쪽
 * tests/test_filter_conformance.py 와 **같이** 읽는다. 파서 산출물이 언어마다 다른 모양
 * (SQL 문자열 vs Prisma where 객체)이라 문자 그대로 비교할 수 없으므로, "결과가 같다"를
 * 그 JSON 이 못박은 행동 분류(expect: reject|false|accept)로 조작화했다 — 자세한 근거는
 * 그 파일의 _comment 를 본다. 둘 다 같은 제3의 값(이 JSON)과 일치하면 서로도 일치한다.
 *
 * 검사 대상이 0건이거나 fixture 의 M-2~M-7·#306 커버리지가 줄면 실패한다(fail-closed) —
 * 리드 결정의 필수 조건이다.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { convertFilterToPrismaWhere } from "../frontend/lib/grid/filters.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = path.join(__dirname, "fixtures", "filter_conformance_cases.json");

const MIN_CASES = 36;
// 이슈 #295 가 못박은 발산 목록(M-2~M-7)·#306(두 파서가 같은 방향으로 틀린 빈 부정)·
// #389(형식 오류 축, 기대값의 근거는 scripts/verify_filter_negation.mjs 의 DevExtreme 심판)·
// #401(재귀 깊이 상한 — 두 파서가 같은 상한을 쓰는지) — fixture 의 ref 에서 하나씩은 나와야 한다.
const REQUIRED_REFS = ["M-2", "M-3", "M-4", "M-5", "M-6", "M-7", "#306", "#389", "#401"];

function loadCases() {
  const raw = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));
  const cases = raw.cases;
  if (!Array.isArray(cases) || cases.length < MIN_CASES) {
    console.log(`FAIL 검사 대상이 ${cases?.length ?? 0}건 — 최소 ${MIN_CASES}건 필요 (fail-closed)`);
    process.exit(2);
  }
  const refs = new Set(cases.map((c) => c.ref));
  const missing = REQUIRED_REFS.filter((req) => ![...refs].some((ref) => ref.startsWith(req)));
  if (missing.length > 0) {
    console.log(`FAIL 필수 발산 항목이 fixture 에서 빠졌다: ${missing.join(", ")}`);
    process.exit(2);
  }
  return cases;
}

function checkConformanceCases() {
  const cases = loadCases();
  const failures = [];
  const counts = { reject: 0, false: 0, accept: 0 };

  for (const testCase of cases) {
    const { id, name, input, expect } = testCase;
    counts[expect] = (counts[expect] ?? 0) + 1;
    const label = `[${id}] ${name}`;

    if (expect === "reject") {
      try {
        const where = convertFilterToPrismaWhere(input);
        failures.push(`${label}: 거절돼야 하는데 통과했다 — ${JSON.stringify(where)}`);
      } catch {
        // 기대한 결과 — 계속
      }
      continue;
    }

    if (expect === "false") {
      try {
        const where = convertFilterToPrismaWhere(input);
        if (JSON.stringify(where) !== JSON.stringify({ OR: [] })) {
          failures.push(`${label}: 항상 거짓이 아니다 — ${JSON.stringify(where)}`);
        }
      } catch (err) {
        failures.push(`${label}: 항상 거짓을 내야 하는데 거절됐다 — ${err.message ?? err}`);
      }
      continue;
    }

    if (expect === "accept") {
      try {
        const where = convertFilterToPrismaWhere(input);
        if (Object.keys(where).length === 0) {
          failures.push(`${label}: 정상 입력인데 빈(무제약) where 가 나왔다`);
        }
      } catch (err) {
        failures.push(`${label}: 정상 입력인데 거절됐다 — ${err.message ?? err}`);
      }
      continue;
    }

    failures.push(`${label}: fixture 의 expect 값을 모른다 — ${expect}`);
  }

  console.log(
    `     (검사 ${cases.length}건 — reject ${counts.reject ?? 0} · false ${counts.false ?? 0} · ` +
      `accept ${counts.accept ?? 0})`,
  );

  if (failures.length > 0) {
    console.log(`FAIL conformance_cases\n${failures.map((f) => `     ${f}`).join("\n")}`);
    return false;
  }
  console.log("PASS conformance_cases");
  return true;
}

/**
 * M-6 — TS 는 "전체가 날짜꼴"인 값만 Date 로 바꾸고, 부분 일치(regex 에 앵커가 없던 시절의
 * 오탐)는 문자열로 남겨야 한다. dateShape 케이스로 이 불변식을 고정해 앵커가 조용히
 * 빠지는 회귀를 잡는다.
 */
function checkDateCoercionShape() {
  const cases = loadCases().filter((c) => "dateShape" in c);
  if (cases.length < 2) {
    console.log(`FAIL M-6 dateShape 케이스가 ${cases.length}건 — 목록이 줄었다`);
    return false;
  }

  const failures = [];
  for (const testCase of cases) {
    const { id, input, dateShape } = testCase;
    const where = convertFilterToPrismaWhere(input);
    const field = input[0];
    const actual = where[field]?.equals;
    const isDate = actual instanceof Date;
    const wantDate = dateShape === "date";
    if (isDate !== wantDate) {
      failures.push(
        `[${id}] 기대 ${wantDate ? "Date" : "string"} / 실제 ${isDate ? "Date" : typeof actual} (${JSON.stringify(where)})`,
      );
    }
  }

  if (failures.length > 0) {
    console.log(`FAIL date_coercion_shape\n${failures.map((f) => `     ${f}`).join("\n")}`);
    return false;
  }
  console.log(`PASS date_coercion_shape (${cases.length} 케이스)`);
  return true;
}

const results = [checkConformanceCases(), checkDateCoercionShape()];
const passed = results.every(Boolean);

console.log(`\n${results.filter(Boolean).length}/${results.length} 검사 통과`);
process.exit(passed ? 0 : 1);
