/**
 * #293 — frontend/lib/grid/filters.ts 가 필터 문법을 DevExtreme 과 같은 뜻으로 읽는지 검증.
 *
 *     node scripts/verify_filter_negation.mjs
 *
 * 심판은 **DevExtreme 자신의 평가기**(`devextreme/cjs/data/query.js`)가 낸 답이다. 기대 행
 * 집합을 손으로 적으면 "내가 생각한 뜻"을 검증하는 것이지 "회선에 오르는 문법의 뜻"을 검증하는
 * 게 아니다. 같은 filter JSON 을 두 경로에 먹여 나온 행 집합을 대조한다:
 *
 *     DevExtreme 평가기의 답 (정답)  ─┐
 *                                    ├─ 같은 행 집합이어야 한다
 *     convertFilterToPrismaWhere → evalPrismaWhere
 *
 * **#341 이후 — 평가기를 부르지 않고 얼린 답을 읽는다.** devextreme 이 레포에서 제거되면서
 * (package.json·node_modules 둘 다) 그 평가기를 런타임에 부를 수 없게 됐다. 제거 **직전에**
 * 실제 라이브러리(24.2.15)를 돌려 받은 답을 `fixtures/devextreme_filter_oracle.json` 에 얼렸고,
 * 이 스크립트는 그 표를 읽는다. 여전히 손으로 적은 값이 아니다 — 다만 "정답이 라이브러리와 함께
 * 자동으로 갱신되지는 않는다"는 경계가 새로 생겼다(케이스를 추가하면 표에도 답을 넣어야 하고,
 * 표에 없는 케이스를 만나면 이 스크립트는 조용히 넘어가지 않고 실패한다).
 *
 * 검증 경계 — 두 번째 경로는 **실제 Prisma 가 아니다**. Prisma 클라이언트를 돌리려면 살아 있는
 * PostgreSQL 이 필요한데 없으므로, `filters.ts` 가 내는 where 객체를 아래 evalPrismaWhere 가
 * 해석해 행을 고른다. where 형태 자체는 EXPECTED_SHAPES 에 문자열로 고정해 눈으로 읽게 한다.
 * SQL 의 NULL 3값 논리는 이 해석기로 재현되지 않는다 — NULL_BOUNDARY 주석 참조.
 *
 * 이 파일이 frontend/ 밖에 있는 이유: frontend 의 tsconfig 가 모든 .ts 를 include 하고 eslint
 * 설정도 앱 코드를 전제로 잡혀 있어, 러너 없는 standalone 스크립트를 그 안에 두면 빌드·린트
 * 게이트와 싸운다. 레포 루트 `scripts/verify_*` 가족과 같은 자리에 둔다.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { convertFilterToPrismaWhere } from "../frontend/lib/grid/filters.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = path.join(__dirname, "fixtures", "filter_conformance_cases.json");
const ORACLE_PATH = path.join(__dirname, "fixtures", "devextreme_filter_oracle.json");

/** DevExtreme 평가기가 고른 행 — 제거 직전에 얼린 정답표(위 헤더 주석 참조). */
const ORACLE = JSON.parse(readFileSync(ORACLE_PATH, "utf8"));

/**
 * 정답표에서 케이스의 답을 읽는다. **표에 없으면 실패시킨다** — 케이스를 추가하고 답을 안
 * 넣으면 그 케이스가 조용히 검사에서 빠지기 때문이다(검사 0건 = 통과 금지).
 */
function judgedTickers(label) {
  const answer = ORACLE.cases[label];
  if (answer === undefined) {
    console.error(
      `\n[verify_filter_negation] 정답표에 없는 케이스: "${label}"\n` +
        `  fixtures/devextreme_filter_oracle.json 의 cases 에 이 케이스의 답을 넣으세요.\n` +
        `  답은 손으로 적지 말고 DevExtreme 평가기를 한 번 돌려 받으세요(그 표의 "//" 주석 참조).\n`,
    );
    process.exit(1);
  }
  return answer;
}

/**
 * `filters.ts` 가 내는 Prisma where 형태를 해석해 행을 고른다.
 *
 * 지원 범위는 `createFieldCondition` 이 실제로 만드는 것뿐이다 — 모르는 키를 만나면 조용히
 * 넘기지 않고 던진다. 넘기면 "조건이 사라진 결과"를 "일치"로 읽어버린다.
 */
function evalPrismaWhere(row, where) {
  if (where === null || typeof where !== "object") {
    throw new Error(`where 가 객체가 아니다: ${JSON.stringify(where)}`);
  }

  return Object.entries(where).every(([key, value]) => {
    if (key === "AND") return value.every((child) => evalPrismaWhere(row, child));
    if (key === "OR") return value.some((child) => evalPrismaWhere(row, child));
    if (key === "NOT") return !evalPrismaWhere(row, value);
    return matchesFieldFilter(row[key], value);
  });
}

function matchesFieldFilter(actual, filter) {
  if (filter === null) return actual === null || actual === undefined;
  if (typeof filter !== "object") return actual === filter;

  const { mode, ...operators } = filter;
  const insensitive = mode === "insensitive";

  return Object.entries(operators).every(([operator, operand]) => {
    switch (operator) {
      case "equals":
        return operand === null ? actual === null || actual === undefined : compare(actual, operand) === 0;
      case "not":
        if (operand === null) return actual !== null && actual !== undefined;
        if (typeof operand === "object") return !matchesFieldFilter(actual, { ...operand, mode });
        return compare(actual, operand) !== 0;
      case "gt":
        return compare(actual, operand) > 0;
      case "gte":
        return compare(actual, operand) >= 0;
      case "lt":
        return compare(actual, operand) < 0;
      case "lte":
        return compare(actual, operand) <= 0;
      case "in":
        return operand.some((candidate) => compare(actual, candidate) === 0);
      case "notIn":
        return !operand.some((candidate) => compare(actual, candidate) === 0);
      case "contains":
        return like(actual, operand, insensitive, "contains");
      case "startsWith":
        return like(actual, operand, insensitive, "startsWith");
      case "endsWith":
        return like(actual, operand, insensitive, "endsWith");
      default:
        throw new Error(`해석기가 모르는 Prisma 연산자: ${operator}`);
    }
  });
}

function compare(actual, expected) {
  if (actual === null || actual === undefined) return Number.NaN;
  if (actual instanceof Date && expected instanceof Date) return actual.getTime() - expected.getTime();
  if (actual === expected) return 0;
  if (typeof actual === "number" && typeof expected === "number") return actual - expected;
  const left = String(actual);
  const right = String(expected);
  if (left === right) return 0;
  return left < right ? -1 : 1;
}

/** `escapeLikeValue` 가 이스케이프한 `\%`·`\_`·`\\` 를 되돌려 문자 그대로 비교한다. */
function like(actual, pattern, insensitive, kind) {
  if (actual === null || actual === undefined) return false;
  const unescaped = String(pattern).replace(/\\([\\%_])/g, "$1");
  const haystack = insensitive ? String(actual).toLowerCase() : String(actual);
  const needle = insensitive ? unescaped.toLowerCase() : unescaped;
  if (kind === "startsWith") return haystack.startsWith(needle);
  if (kind === "endsWith") return haystack.endsWith(needle);
  return haystack.includes(needle);
}

function prismaRows(rows, expression) {
  const where = convertFilterToPrismaWhere(expression);
  return rows.filter((row) => evalPrismaWhere(row, where));
}

// ── 대조에 쓰는 표 ────────────────────────────────────────────────────────────

const KEY = "ticker";

const ROWS = [
  { ticker: "AAPL", market: "NASDAQ", price: 190, memo: "" },
  { ticker: "005930", market: "KOSPI", price: 71000, memo: "반도체" },
  { ticker: "035720", market: "KOSPI", price: 52000, memo: "플랫폼" },
];

/**
 * DevExtreme 헤더 필터가 "제외"(exclude)에서 회선에 올리는 형태.
 * `devextreme/cjs/__internal/grids/grid_core/header_filter/m_header_filter.js` 가
 * `["!", filterValues]` 로 만든다.
 */
const HEADER_FILTER_EXCLUDE = ["!", [[KEY, "=", "005930"], "or", [KEY, "=", "035720"]]];

// DevExtreme 평가기가 받아들이는 연산자만 쓴다 — `in`·`between`·`isblank` 등은 평가기가
// E4003 으로 거절해서 심판을 세울 수 없다 (그 갈림은 #295 의 몫).
const CASES = [
  ["헤더필터 제외 (C24)", HEADER_FILTER_EXCLUDE],
  ["헤더필터 포함", [[KEY, "=", "005930"], "or", [KEY, "=", "035720"]]],
  ["부정 · 단일 조건", ["!", [KEY, "=", "AAPL"]]],
  ["부정 · 단일 조건 (숫자)", ["!", ["price", ">", 60000]]],
  ["부정 · contains", ["!", ["market", "contains", "KOS"]]],
  ["부정 · and 그룹", ["!", [["market", "=", "KOSPI"], "and", ["price", ">", 60000]]]],
  ["부정의 부정", ["!", ["!", [KEY, "=", "AAPL"]]]],
  ["부정을 품은 and 그룹", [["!", [KEY, "=", "AAPL"]], "and", ["price", ">", 60000]]],
  ["부정을 품은 or 그룹", [["!", ["market", "=", "KOSPI"]], "or", ["price", "<", 60000]]],
  ["부정이 오른쪽에", [["market", "=", "KOSPI"], "and", ["!", [KEY, "=", "005930"]]]],
  ["부정 · 중첩 그룹 안", [[["!", ["market", "=", "NASDAQ"]], "or", ["price", "<", 100]], "and", ["price", ">", 0]]],
  ["부정 · 3단 중첩", ["!", [[["market", "=", "KOSPI"], "and", ["price", ">", 60000]], "or", [KEY, "=", "AAPL"]]]],
  ["단일 조건", [KEY, "=", "AAPL"]],
  ["and 그룹", [["market", "=", "KOSPI"], "and", ["price", ">", 60000]]],
  ["or 그룹", [["market", "=", "NASDAQ"], "or", ["price", "<", 60000]]],
  ["contains", ["market", "contains", "kos"]],
  ["notcontains", ["market", "notcontains", "kos"]],
  ["startswith", ["market", "startswith", "NAS"]],
  ["endswith", ["market", "endswith", "PI"]],
  ["<>", ["market", "<>", "KOSPI"]],
  [">=", ["price", ">=", 71000]],
  ["<=", ["price", "<=", 52000]],
];

/** where 형태를 눈으로 읽게 고정한다 — 해석기와는 다른 눈으로 보는 대조. */
const EXPECTED_SHAPES = [
  [HEADER_FILTER_EXCLUDE, '{"NOT":{"OR":[{"ticker":{"equals":"005930"}},{"ticker":{"equals":"035720"}}]}}'],
  [["!", [KEY, "=", "AAPL"]], '{"NOT":{"ticker":{"equals":"AAPL"}}}'],
  [["!", ["price", ">", 60000]], '{"NOT":{"price":{"gt":60000}}}'],
  [["!", ["!", [KEY, "=", "AAPL"]]], '{"NOT":{"NOT":{"ticker":{"equals":"AAPL"}}}}'],
  [
    [["!", [KEY, "=", "AAPL"]], "and", ["price", ">", 60000]],
    '{"AND":[{"NOT":{"ticker":{"equals":"AAPL"}}},{"price":{"gt":60000}}]}',
  ],
  // `[]` 는 "필터 없음"이 아니라 "항상 거짓"이다(#306) — 그 부정은 "항상 참"이어야 하므로
  // `["!", []]` 는 더 이상 빈 no-op({})이 아니라 NOT(거짓 조건)이 나간다.
  [["!", []], '{"NOT":{"OR":[]}}'],
];

/**
 * 이 대조기가 **못 잡는 것**을 못 잡는 채로 붙잡아 두는 자리.
 *
 * NULL 컬럼에 부정을 걸면 JS 는 행을 남기고(`!(null == "AAPL")` → true), 실제 SQL 은 3값 논리라
 * `NOT (ticker = 'AAPL')` 이 NULL 이 되어 행을 버린다. 위 evalPrismaWhere 는 JS 의미라서
 * DevExtreme 평가기와 **일치해 버린다** — 즉 이 대조로는 그 갈림을 볼 수 없다. 파이썬 파서도
 * `NOT (…)` 를 내므로 두 파서끼리는 일치하며, 문법이 아니라 SQL 의 성질이다.
 * 아래 검사는 그 전제(해석기는 JS 의미)가 유지되는지 지키는 트립와이어다.
 */
const NULL_BOUNDARY = ["부정 · NULL 컬럼", ["!", [KEY, "=", "AAPL"]]];
const NULL_ROWS = [{ ticker: null }];

// ── #389 형식 오류 축 — 심판이 fixture 의 기대값을 근거지운다 ──────────────────
//
// #389 의 두 번째 결함은 두 파서가 **같은 방향으로** 틀린 경우다(둘 다 형식 오류를 "필터
// 없음"으로 삼켜 전건 반환). 적합성 대조(서로 비교)는 이런 결함을 구조적으로 못 잡는다 —
// 그래서 #306 이 그랬듯 DevExtreme 자신의 평가기를 제3의 심판으로 세운다.
//
// 이 검사가 못박는 것은 두 가지다:
//   ① 심판은 이 입력들에서 **전건을 내지 않는다**(0건이거나 예외) — 그러므로 "필터 없음"은
//      두 파서의 합의가 아니라 **오답**이다. fixture 의 judge 필드가 그 실측을 적어둔 것이고,
//      이 검사가 매 실행마다 다시 확인한다(값이 틀리면 실패 — 주석이 아니라 검사다).
//   ② 우리 파서는 그 입력들을 **거절한다** — 심판보다 좁은 쪽(fail-closed)이라 안전하고,
//      #295 리드 결정("잘못된 입력은 양쪽 다 거절")과 같은 방향이다.
//
// 필드 `a`·`b` 가 실제로 있는 행을 쓴다 — 없는 필드로 검사하면 "0건"이 문법 판정 때문인지
// 필드가 없어서인지 구분되지 않아 심판이 공회전한다(아래 SANITY 가 그 구분을 고정한다).
const MALFORMED_ROWS = [
  { a: 1, b: 2 },
  { a: 2, b: 2 },
  { a: 3, b: 5 },
];
// 심판이 살아 있음을 보이는 대조 — 정상 필터는 부분집합, "필터 없음"은 전건.
const MALFORMED_SANITY = { wellFormed: ["a", "=", 1], wellFormedRows: 1, noFilterRows: MALFORMED_ROWS.length };
const MIN_MALFORMED_CASES = 12;

// ── 검증 ──────────────────────────────────────────────────────────────────────

const failures = [];

function check(name, ok, detail) {
  if (ok) {
    console.log(`PASS ${name}`);
  } else {
    failures.push(name);
    console.log(`FAIL ${name}\n     ${detail}`);
  }
}

function tickersOf(rows) {
  return rows.map((row) => String(row[KEY])).join(",") || "(없음)";
}

function checkHeaderFilterExcludeIsNotInverted() {
  const judged = ORACLE.headerFilterExclude;
  const prisma = tickersOf(prismaRows(ROWS, HEADER_FILTER_EXCLUDE));
  check(
    "header_filter_exclude_is_not_inverted (C24)",
    judged === "AAPL" && prisma === "AAPL",
    `제외한 것만 보인다 — DevExtreme ${judged} / Prisma ${prisma}`,
  );
}

function checkJudgeAgreement() {
  const mismatched = [];
  for (const [label, expression] of CASES) {
    const judged = judgedTickers(label);
    const prisma = tickersOf(prismaRows(ROWS, expression));
    if (judged !== prisma) mismatched.push(`  ${label}\n    DevExtreme ${judged}\n    Prisma     ${prisma}`);
  }
  check(
    `devextreme_judge_agreement (${CASES.length} 케이스)`,
    mismatched.length === 0,
    `두 경로가 다른 행을 낸다:\n${mismatched.join("\n")}`,
  );
}

function checkWhereShapes() {
  const wrong = [];
  for (const [expression, expected] of EXPECTED_SHAPES) {
    const actual = JSON.stringify(convertFilterToPrismaWhere(expression));
    if (actual !== expected) {
      wrong.push(`  ${JSON.stringify(expression)}\n    기대 ${expected}\n    실제 ${actual}`);
    }
  }
  check(
    `prisma_where_shapes (${EXPECTED_SHAPES.length} 형태)`,
    wrong.length === 0,
    `where 형태가 다르다:\n${wrong.join("\n")}`,
  );
}

function checkNullBoundaryIsJsSemanticsNotSql() {
  const [label, expression] = NULL_BOUNDARY;
  const judged = ORACLE.nullBoundaryRowCount;
  const prisma = prismaRows(NULL_ROWS, expression).length;
  check(
    `null_boundary_is_js_semantics_not_sql (${label})`,
    judged === 1 && prisma === 1,
    `해석기가 JS 의미를 벗어났다 — 검증 경계 설명을 다시 써야 한다 (judge ${judged} / prisma ${prisma})`,
  );
}

function checkEvaluatorRejectsUnknownOperator() {
  let threw = false;
  try {
    evalPrismaWhere({ a: 1 }, { a: { someUnknownPrismaOperator: 1 } });
  } catch {
    threw = true;
  }
  check(
    "evaluator_rejects_unknown_operator",
    threw,
    "해석기가 모르는 연산자를 조용히 넘긴다 — 조건이 사라진 결과를 일치로 읽는다",
  );
}

function loadMalformedCases() {
  const raw = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));
  return (raw.cases ?? []).filter((c) => c.ref === "#389");
}

/** 심판이 실제로 행을 가르는지 — 이 대조가 깨지면 아래 "전건 아님" 판정은 공회전이다. */
function checkMalformedJudgeSanity() {
  const wellFormed = ORACLE.malformedSanityWellFormedRows;
  check(
    "malformed_judge_sanity",
    wellFormed === MALFORMED_SANITY.wellFormedRows && MALFORMED_ROWS.length === MALFORMED_SANITY.noFilterRows,
    `심판이 정상 필터에서 ${wellFormed}건 — 기대 ${MALFORMED_SANITY.wellFormedRows}건 ` +
      `(전건은 ${MALFORMED_ROWS.length}건). 심판이 행을 안 가르면 '전건 아님' 판정에 뜻이 없다`,
  );
}

/**
 * #389 — 형식 오류 입력에서 ① 심판이 전건을 내지 않고 ② 우리 파서가 거절하는지.
 * fixture 의 judge 필드(rows-not-all|throws)가 심판의 실측과 맞는지도 함께 본다.
 */
function checkMalformedNeverReturnsAllRows() {
  const cases = loadMalformedCases();
  if (cases.length < MIN_MALFORMED_CASES) {
    console.log(`FAIL #389 형식 오류 케이스가 ${cases.length}건 — 최소 ${MIN_MALFORMED_CASES}건 필요 (fail-closed)`);
    process.exit(2);
  }

  const problems = [];
  for (const testCase of cases) {
    const { id, input, expect: expected, judge } = testCase;
    const label = `[${id}]`;

    if (expected !== "reject") {
      problems.push(`${label} #389 축은 전부 reject 여야 한다 — expect=${expected}`);
      continue;
    }

    // ① 심판 — 전건을 내면 안 된다. (얼린 정답표의 실측값, 위 헤더 주석 참조)
    const judged = ORACLE.malformedJudge[id];
    if (judged === undefined) {
      problems.push(`${label} 정답표(devextreme_filter_oracle.json)의 malformedJudge 에 이 id 의 실측값이 없다`);
      continue;
    }
    if (judged === "throws") {
      if (judge !== "throws") problems.push(`${label} fixture 의 judge=${judge} 인데 심판은 예외를 던졌다`);
    } else {
      if (judge !== "rows-not-all") problems.push(`${label} fixture 의 judge=${judge} 인데 심판은 ${judged}건을 냈다`);
      if (judged === MALFORMED_ROWS.length) {
        problems.push(`${label} 심판이 전건(${judged}건)을 냈다 — 이 입력은 이 축의 근거가 될 수 없다`);
      }
    }

    // ② 우리 파서 — 거절해야 한다. 통과하면 최소한 "제약 없음"은 아니어야 하는데,
    //    #389 의 결함이 정확히 "제약 없음"이었으므로 통과 자체를 실패로 본다.
    try {
      const where = convertFilterToPrismaWhere(input);
      const kind = Object.keys(where).length === 0 ? "제약 없음(= 전건)" : JSON.stringify(where);
      problems.push(`${label} 파서가 거절하지 않았다 — ${kind}`);
    } catch {
      // 기대한 결과
    }
  }

  check(
    `malformed_never_returns_all_rows (${cases.length} 케이스)`,
    problems.length === 0,
    `형식 오류 축이 깨졌다:\n${problems.map((p) => `  ${p}`).join("\n")}`,
  );
  return cases.length;
}

// 검사 대상이 0건이면 통과가 아니다.
if (CASES.length < 20 || EXPECTED_SHAPES.length < 5) {
  console.log(`FAIL 케이스 목록이 줄었다 — CASES ${CASES.length} / EXPECTED_SHAPES ${EXPECTED_SHAPES.length}`);
  process.exit(2);
}

checkHeaderFilterExcludeIsNotInverted();
checkJudgeAgreement();
checkWhereShapes();
checkNullBoundaryIsJsSemanticsNotSql();
checkEvaluatorRejectsUnknownOperator();
checkMalformedJudgeSanity();
const malformedCount = checkMalformedNeverReturnsAllRows();

console.log(
  `\n${CASES.length} 케이스 · ${EXPECTED_SHAPES.length} 형태 · #389 형식 오류 ${malformedCount} 케이스 검사 — ` +
    `${failures.length === 0 ? "모두 통과" : `${failures.length} 건 실패: ${failures.join(", ")}`}`,
);
process.exit(failures.length === 0 ? 0 : 1);
