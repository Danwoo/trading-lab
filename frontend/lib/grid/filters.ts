// lib/grid/filters.ts

// 필터 문법이 통제를 벗어난 입력임을 알리는 신호. 일부러 `Error` 를 상속하지 않는다 —
// utils/common/api/responses.ts 의 createErrorResponse 는 `instanceof Error` 가 아닌
// `{ message }` 평범한 객체만 400 으로 매핑하고(4번 분기), 진짜 Error 인스턴스는 5번
// fallback(500)으로 떨어진다. 여기서 Error 를 던지면 "잘못된 필터"가 500 이 되어
// backend-service(BadRequestError → 400)와 갈린다(#295).
function invalidFilter(message: string): never {
  throw { message };
}

// SQL 식별자 검증과 같은 규칙 — backend-service/app/utils/common/devextreme_utils.py 의
// _SAFE_IDENTIFIER_RE 와 동일한 정규식이어야 같은 필드명을 같은 방향으로 판정한다(#295 M-4).
// 이전엔 이 검증이 없어 이상한 필드명이 Prisma 런타임 오류(형태를 예측할 수 없음)로 떨어졌다.
const _SAFE_IDENTIFIER_RE = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

function validateIdentifier(field: any): string {
  if (typeof field !== "string" || !_SAFE_IDENTIFIER_RE.test(field)) {
    invalidFilter(`유효하지 않은 필드명입니다: ${field}`);
  }
  return field;
}

// 중첩 그룹 재귀의 깊이 상한 — backend-service/app/utils/common/devextreme_utils.py 의
// `_MAX_FILTER_DEPTH` 와 **같은 값**이어야 한다. 두 파서가 다른 상한을 쓰면 같은 필터가 한쪽만
// 통과해 #295 가 없앤 발산이 되살아난다.
//
// 상한이 없으면 클라이언트가 보낸 값 하나가 서버 오류가 된다: TS 는 `RangeError`(스택 초과)로,
// 파이썬은 `RecursionError`(→ `RuntimeError` 서브클래스라 500)로 떨어졌다 — 8KB 안팎 요청 하나로
// 넘어간다(#401 실측). 문법 오류를 400 으로 접는 #389 의 설계가 이 축에서만 뚫려 있었다.
//
// 값의 근거(실측) — 레포가 실제로 만들거나 회귀 그물이 못박은 필터의 최대 깊이는 **4**다
// (`scripts/verify_filter_negation.mjs` 의 "부정 · 중첩 그룹 안"·"부정 · 3단 중첩").
// 화면이 만들어 내는 필터는 최대 **2**다 (`components/shared/DataTable/DataTableFilterRow.tsx`
// 의 buildFilter — 조건 1개면 1, 여러 개면 `[[조건],"and",[조건],…]` 로 2). 32는 실측 최대의
// 8배 여유이고, 실제로 스택이 무너지는 지점(파이썬 1000단대, TS 3700단대 — #401 실측)보다
// 두 자릿수 아래다.
const MAX_FILTER_DEPTH = 32;

// 항상 거짓인 조건 — Prisma 는 `OR: []` 를 빈 논리합(= 거짓)으로 컴파일한다(`AND: []` 는
// 반대로 참이므로 쓸 수 없다). 특정 필드(예: id)를 골라 `{ id: { in: [] } }` 로 쓰면 그
// 필드가 모델마다 달라 일반화가 안 된다 — 이 형태는 필드 이름 없이 어떤 모델에도 쓴다.
const FALSE_CONDITION = { OR: [] as any[] };

// 필터가 아예 오지 않은 것(쿼리 파라미터 부재)과 "필터가 왔는데 형식이 깨졌다"는 다르다.
// 앞은 제약 없음(전건)이 맞고, 뒤는 거절해야 한다 — 형식 오류를 "필터 없음"으로 삼키면
// 사용자는 필터가 걸렸다고 믿는데 전건이 나간다(#389). `searchParams.get("filter")` 는
// `string | null` 이라 이 셋이 "필터 없음"의 전부다.
function isFilterAbsent(filter: any): boolean {
  return filter === null || filter === undefined || filter === "";
}

export function convertFilterToPrismaWhere(filter: any): any {
  if (isFilterAbsent(filter)) return {};

  if (typeof filter === "string") {
    try {
      filter = JSON.parse(filter);
    } catch {
      // 예전엔 `{}`(제약 없음)를 돌려줘 깨진 JSON 이 전건을 불렀다(#389).
      invalidFilter("필터 형식이 올바르지 않습니다: JSON 을 읽을 수 없습니다.");
    }
  }

  if (!Array.isArray(filter)) {
    invalidFilter(`필터는 배열이어야 합니다: ${JSON.stringify(filter)}`);
  }

  return parseFilterArray(filter, 1);
}

function parseFilterArray(filter: any[], depth: number): any {
  // 깊이 검사는 다른 어떤 처리보다 먼저다 — 아래 분기들이 재귀를 부르기 때문이다.
  if (depth > MAX_FILTER_DEPTH) {
    invalidFilter(`필터 중첩이 너무 깊습니다 (최대 ${MAX_FILTER_DEPTH}단).`);
  }

  // 빈 배열 `[]`, 항 없는 부정 `["!"]` — DevExtreme 이 "아무것도 안 맞음" 뜻으로 검색
  // 패널에서 실제로 회선에 올리는 형태다(grid_core/search/m_search.js, combineFilters 의
  // and 단축 — #306). 아래 그룹 처리로 흘려보내면 조건이 하나도 안 쌓여 `{}`(필터 없음 =
  // 전건)가 나가는데, 정반대다.
  if (filter.length === 0 || (filter.length === 1 && filter[0] === "!")) {
    return FALSE_CONDITION;
  }

  // 부정: ["!", 표현식]
  //
  // 헤더 필터의 "제외"(exclude)가 이 형태로 회선에 오른다 — DevExtreme 이
  // `["!", filterValues]` 로 감싼다 (devextreme/cjs/__internal/grids/grid_core/header_filter).
  // 아래 그룹 처리로 흘려보내면 "!" 는 and/or 가 아닌 문자열이라 그냥 버려지고,
  // 남은 or 그룹이 그대로 나가 **제외하려던 행만** 조회된다.
  if (filter.length === 2 && filter[0] === "!") {
    // 피연산자가 배열이 아니면 거절한다 — 예전엔 이 분기를 비껴가 아래 그룹 처리에서 두 항이
    // 다 버려지고 `{}`(전건)가 나갔다(#389, `["!", "x"]`). 부정이 통째로 사라진 정반대 결과다.
    if (!Array.isArray(filter[1])) {
      invalidFilter("부정(!) 의 피연산자는 조건 배열이어야 합니다.");
    }
    return { NOT: parseFilterArray(filter[1], depth + 1) };
  }

  // 항이 더 붙은 `!` 는 문법에 없다 — backend-service 와 같은 방향으로 거절한다(M-10 계열).
  if (filter.length > 2 && filter[0] === "!") {
    invalidFilter("잘못된 부정 조건 형식입니다.");
  }

  if (filter.length === 3 && typeof filter[0] === "string") {
    // 단일 조건: ["field", "operator", value]
    const [field, operator, value] = filter;
    return createFieldCondition(field, operator, value);
  }

  // 복합 조건 처리.
  //
  // 한 그룹 안에서 and 와 or 를 섞으면 거절한다(#295 M-2) — DevExtreme 자신의 필터
  // 컴파일러(grid_core/m_utils.js compileGroup)도 `[A,"and",B,"or",C]` 같은 평면 배열에
  // E4019 를 던진다. 예전엔 마지막에 본 연산자가 전부를 덮어써 `[A,"and",B,"or",C]` 가
  // `A OR B OR C` 가 됐다(파이썬은 SQL 의 AND-우선 규칙에 기대 다른 뜻을 냈다) — 같은 입력이
  // 경로에 따라 다른 뜻이 되던 것을, 문법에 없는 입력이니 양쪽 다 거절하는 쪽으로 모은다.
  //
  // 연산자는 **소비된 피연산자 사이**에서만 센다(devextreme_utils.py 의 pending_operator 와
  // 같은 규칙) — 그냥 등장한 문자열을 전부 세면 `[A,"and","or",B]`(피연산자 2개, 연산자
  // 토큰만 2개) 같은 경우까지 과다 거절한다. DevExtreme 은 이 경우 마지막 토큰("or")만
  // 유효하다고 본다(다음 피연산자가 소비할 때까지 갱신되는 하나의 "다음 연산자" 슬롯).
  const conditions: any[] = [];
  const operators: string[] = [];
  let pendingOperator: string | null = null;

  for (let i = 0; i < filter.length; i++) {
    const item = filter[i];

    if (Array.isArray(item)) {
      const condition = parseFilterArray(item, depth + 1);
      if (conditions.length > 0) {
        operators.push(pendingOperator ?? "AND");
      }
      conditions.push(condition);
      pendingOperator = null;
    } else if (typeof item === "string" && (item.toLowerCase() === "and" || item.toLowerCase() === "or")) {
      // 좌항 없는 연산자는 문법 오류다 — DevExtreme 평가기도 `["and", A]` 에 0건을 낸다(실측).
      // 예전엔 이 토큰을 그냥 삼켜 A 만 남았다: 심판보다 넓은 결과다.
      if (conditions.length === 0) {
        invalidFilter(`연산자 앞에 조건이 없습니다: ${item}`);
      }
      pendingOperator = item.toUpperCase();
    }
    // and/or 도 배열도 아닌 항은 버린다(M-9) — DevExtreme 평가기도 `[A, 5, B]`·`[A, "junk"]`
    // 에서 그 항을 무시하고 나머지를 결합한다(실측). 여기서 조건이 하나도 안 쌓이는 경우는
    // 아래에서 거절한다.
  }

  if (operators.length >= 2 && new Set(operators).size > 1) {
    invalidFilter("같은 그룹 안에서 and 와 or 를 섞어 쓸 수 없습니다. 괄호로 묶어 중첩하세요.");
  }

  // 조건이 하나도 안 쌓였다 = 필터가 왔는데 형식이 문법에 없다. 예전엔 `{}`(제약 없음)를
  // 돌려줘 `["and"]`·`["a","="]`·`[1,"=",1]`·`["a","=",1,"and",2]` 가 전부 전건을 냈다(#389).
  // DevExtreme 평가기는 같은 입력에 0건 또는 예외를 낸다 — 전건은 어느 쪽도 아니다.
  if (conditions.length === 0) {
    invalidFilter(`필터에서 읽을 수 있는 조건이 없습니다: ${JSON.stringify(filter)}`);
  }
  if (conditions.length === 1) return conditions[0];

  const logicalOperator = operators[0] ?? "AND";
  return logicalOperator === "OR" ? { OR: conditions } : { AND: conditions };
}

// 날짜꼴 문자열인지 판정 — 전체 문자열이 날짜(+ 선택적 시각)와 정확히 일치해야 한다.
// 앵커(^...$) 없이 쓰면 "부분 일치"가 되어 날짜를 포함하기만 하는 아무 문자열(예: 메모
// 필드의 "12024-01-011")도 Date 로 강제 변환된다(#295 M-6 — 파이썬은 같은 값을 문자열
// 그대로 둔다). 앵커를 붙여 "전체가 날짜꼴"일 때만 판정하도록 좁힌다.
const _DATE_LIKE_RE = /^\d{4}[-/]\d{2}[-/]\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$/;

function coerceValue(value: any): any {
  if (typeof value !== "string") return value;
  if (_DATE_LIKE_RE.test(value)) {
    // 슬래시를 하이픈으로, 공백을 T 로 바꾸고 `Z` 를 붙인다.
    //
    // 이 함수의 본체는 **문자열을 Date 로 바꾸는 것**이다 — 그래야 Prisma 가 datetime 비교로
    // 바인딩한다. `Z` 는 그 과정에서 "이 자릿수를 어느 인스턴트로 읽을까"를 정하는 부분이고,
    // 감사 컬럼이 `timestamptz` 로 옮겨진 뒤에도 **그대로 둔다** (#359): 어댑터는 Date 를 UTC
    // 자릿수 문자열로 보내고 세션 tz 는 UTC 로 고정돼 있으므로, `Z` 는 "UTC 로 강제"가 아니라
    // 사실을 그대로 적은 표식이 됐다. 떼면 브라우저 로컬 tz 로 읽혀 필터 경계가 사용자마다
    // 달라진다.
    const normalized = value.replace(/\//g, "-").replace(" ", "T") + "Z";
    const d = new Date(normalized);
    if (!isNaN(d.getTime())) return d;
  }
  return value;
}

// LIKE 와일드카드 이스케이프 — 텍스트 연산자(contains/startswith/endswith)의 값 전용.
//
// Prisma 의 contains/startsWith/endsWith 는 값을 그대로 LIKE 패턴에 이어붙인다
// (`... LIKE ('%' || $1 || '%')` — 실측). 그래서 사용자가 그리드 검색창에 `%` 나 `_` 를
// 넣으면 와일드카드로 해석돼 전건이 걸린다. 그리드 검색은 문자 그대로 찾는 의미이므로
// 값 쪽에서 막는다.
//
// PostgreSQL 의 LIKE 는 ESCAPE 절이 없으면 백슬래시가 기본 이스케이프 문자다
// (datasource = postgresql, schema.prisma). Prisma 는 ESCAPE 절을 붙일 수단을 주지 않으므로
// 기본 이스케이프 문자에 기댄다 — 다른 방언으로 옮기면 여기부터 다시 확인해야 한다.
//
// 이스케이프 계층은 SQL 을 조립하는 쪽이다. 브라우저에서 값을 미리 이스케이프하면
// 같은 filter JSON 을 받는 다른 소비자(파이썬 서비스의 like_pattern)와 이중 이스케이프가 되고,
// `=`·`in` 같은 비-LIKE 연산자의 값까지 오염된다.
function escapeLikeValue(value: any): any {
  if (typeof value !== "string") return value;
  return value.replace(/[\\%_]/g, "\\$&");
}

function createFieldCondition(field: string, operator: string, value: any): any {
  validateIdentifier(field);

  switch (operator) {
    // 텍스트 연산자만 대소문자 무관 — 같은 filter JSON 을 먹는 파이썬 서비스가 ILIKE 를 쓴다
    // (devextreme_utils.filter_condition). 비-LIKE 연산자(`=`·`in` 등)는 그쪽도 가리므로 그대로 둔다.
    // notcontains 의 mode 는 바깥에 둔다 — 중첩 not(NestedStringFilter)엔 mode 필드가 없고,
    // 바깥 mode 가 그 안까지 적용된다 (`NOT ILIKE` 로 나가는 것을 실측).
    case "contains":
      return { [field]: { contains: escapeLikeValue(value), mode: "insensitive" } };

    case "notcontains":
      return { [field]: { not: { contains: escapeLikeValue(value) }, mode: "insensitive" } };

    case "startswith":
      return { [field]: { startsWith: escapeLikeValue(value), mode: "insensitive" } };

    case "endswith":
      return { [field]: { endsWith: escapeLikeValue(value), mode: "insensitive" } };

    case "=":
      return value === null ? { [field]: null } : { [field]: { equals: coerceValue(value) } };

    case "<>":
    case "!=":
      return value === null ? { [field]: { not: null } } : { [field]: { not: coerceValue(value) } };

    case ">":
      return { [field]: { gt: coerceValue(value) } };

    case ">=":
      return { [field]: { gte: coerceValue(value) } };

    case "<":
      return { [field]: { lt: coerceValue(value) } };

    case "<=":
      return { [field]: { lte: coerceValue(value) } };

    case "between":
      // 값이 [시작, 끝] 2원소 배열이 아니면 거절한다(#295 M-5) — 예전엔 조건을 조용히
      // 버렸는데(where 에서 빠지면 그 필드에 제약이 없어진 것과 같다), backend-service 는
      // 같은 입력에서 미해결 바인드로 500 이 났다. 어느 쪽도 조용한 통과가 아니게 모은다.
      if (!(Array.isArray(value) && value.length === 2)) {
        invalidFilter(`between 연산자는 값이 [시작, 끝] 2개인 배열이어야 합니다: ${field}`);
      }
      return { [field]: { gte: coerceValue(value[0]), lte: coerceValue(value[1]) } };

    case "in":
    case "anyof":
    case "notin":
    case "noneof":
      // 값이 배열이 아니면 거절한다(#295 M-7) — 예전엔 조건을 조용히 버렸는데,
      // backend-service 는 스칼라를 [값] 으로 조용히 감쌌다(같은 입력, 다른 결과 집합).
      // 두 파서 다 "값이 배열이어야 한다"는 계약을 어긴 입력은 거절하는 쪽으로 모은다.
      if (!Array.isArray(value)) {
        invalidFilter(`${operator} 연산자는 값이 배열이어야 합니다: ${field}`);
      }
      return operator === "notin" || operator === "noneof" ? { [field]: { notIn: value } } : { [field]: { in: value } };

    case "isblank":
      return {
        OR: [{ [field]: null }, { [field]: { equals: "" } }],
      };

    case "isnotblank":
      return {
        AND: [{ [field]: { not: null } }, { [field]: { not: "" } }],
      };

    default:
      // 모르는 연산자는 거절한다(#295 M-3) — 예전엔 `=` 로 조용히 강등됐다
      // (backend-service 는 이미 같은 입력을 400 으로 거절해 왔다).
      invalidFilter(`지원하지 않는 연산자: ${operator}`);
  }
}

export function convertSortToPrismaOrderBy(sort: any): any[] | undefined {
  if (!sort) return undefined;

  if (typeof sort === "string") {
    try {
      sort = JSON.parse(sort);
    } catch {
      return undefined;
    }
  }

  if (!Array.isArray(sort) || sort.length === 0) return undefined;

  const orderBy: any[] = [];

  for (const sortItem of sort) {
    // 항이 객체가 아니면 거절한다 — `[null]` 은 `sortItem.selector` 에서 TypeError 를 내고,
    // 그건 진짜 Error 라 400 이 아니라 500 으로 샜다(파이썬 `parse_sort` 도 같은 입력에
    // AttributeError 를 냈다). 클라이언트가 보낸 값이 서버 오류가 되지 않게 400 으로 접는다.
    //
    // `Array.isArray` 를 따로 보는 이유 — JS 에서 배열의 `typeof` 는 `"object"` 다. 그래서
    // `[["a"]]` 는 이 검사를 통과한 뒤 `sortItem.selector` 가 undefined 라 조용히 건너뛰어져
    // 기본 정렬로 폴백했고(200), 파이썬 `parse_sort` 는 `isinstance(s, dict)` 로 같은 입력을
    // 400 으로 거절했다 — #295·#401 이 없앤 "같은 입력, 두 경로, 다른 판정" 클래스가 이 좁은
    // 모양에서만 남아 있었다.
    if (sortItem === null || typeof sortItem !== "object" || Array.isArray(sortItem)) {
      invalidFilter(`정렬 항목은 객체여야 합니다: ${JSON.stringify(sortItem)}`);
    }
    if (sortItem.selector) {
      // filter 축과 같은 식별자 검증 — #295 M-4 가 두 파서를 맞춘 건 filter 축뿐이라
      // sort 축은 TS 만 무검증으로 남아 있었다(파이썬 `parse_sort` 는 `_validate_identifier`
      // 를 부른다). 같은 입력이 두 경로에서 다른 판정을 받는 것이 #295 가 없앤 클래스다(#401).
      validateIdentifier(sortItem.selector);
      orderBy.push({
        [sortItem.selector]: sortItem.desc ? "desc" : "asc",
      });
    }
  }

  return orderBy.length > 0 ? orderBy : undefined;
}
