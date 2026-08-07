// hooks/shared/gridQuery.ts
//
// useServerTable 이 쓰는 순수 로직 — React 훅·`showToast`(레거시 토스트 컴포넌트 경유) 등
// 부수효과 있는 모듈을 import 하지 않는다. 이 파일만 따로 두는 이유는 테스트 때문이다:
// vitest.config.ts 는 jsdom 없이 "node" 환경만 쓰므로(O0, #262), 이 파일을 import 하는
// 테스트가 우연히 React 컴포넌트/토스트 배럴을 함께 끌고 오면(그 배럴이 내부에서
// env.ts 를 검증하는 코드까지 물고 있어) 테스트 자체가 깨진다. 순수 로직을 분리해두면
// `useServerTable.query.test.ts` 가 훅을 렌더하지 않고도 이 파일만 안전하게 import 할 수 있다.

import type { GridQuery, GridSort } from "@/types/grid";

// 리포지토리가 `ROW_NUMBER() OVER (ORDER BY ...)` 로 바깥에서 만드는 컬럼이라
// 안쪽 ORDER BY 는 이 필드를 가리킬 수 없다 (기존 useMasterGridData·useDetailGridData·
// useSelectGridData 세 훅이 모두 하는 처리를 이어받는다).
const ROW_NUMBER_FIELD = "rn";

function stripKeyFieldSort(sort: GridSort[] | undefined): GridSort[] | undefined {
  if (!sort || sort.length === 0) return undefined;
  const filtered = sort.filter((item) => item.selector !== ROW_NUMBER_FIELD);
  return filtered.length > 0 ? filtered : undefined;
}

/**
 * 페이지·정렬·필터 상태를 서버가 받는 {@link GridQuery} 로 변환한다.
 * 훅 없이 호출 가능한 순수 함수 — `useServerTable.query.test.ts` 가 직접 검증한다.
 */
export function buildGridQuery(state: {
  pageIndex: number;
  pageSize: number;
  sort?: GridSort[];
  filter?: unknown[];
}): GridQuery {
  return {
    skip: state.pageIndex * state.pageSize,
    take: state.pageSize,
    filter: state.filter,
    sort: stripKeyFieldSort(state.sort),
  };
}

function getFieldValue(row: unknown, field: string): unknown {
  if (row === null || typeof row !== "object") return undefined;
  return (row as Record<string, unknown>)[field];
}

// clientSide 모드 전용 — 서버로 절대 나가지 않는다. 문법은 필터 파서(lib/ 아래 레거시
// parseFilterArray)와 같은 DSL(조건 [field,operator,value] · 부정 ["!",expr] · 그룹
// [expr,"and"|"or",expr,...])을 그대로 인터프리트한다. TanStack 의 filterFn 은 쓰지 않는다
// — 직렬화 불가능한 상태를 만들지 않기 위해서다 (이슈 #242 O1 스파이크 제약).
function evaluateClientFilter(row: unknown, expr: unknown): boolean {
  if (!Array.isArray(expr)) return true;

  if (expr.length === 2 && expr[0] === "!" && Array.isArray(expr[1])) {
    return !evaluateClientFilter(row, expr[1]);
  }

  if (expr.length === 3 && typeof expr[0] === "string") {
    const [field, operator, value] = expr as [string, string, unknown];
    return evaluateCondition(getFieldValue(row, field), operator, value);
  }

  let result: boolean | undefined;
  let logicalOperator: "AND" | "OR" = "AND";

  for (const item of expr) {
    if (Array.isArray(item)) {
      const value = evaluateClientFilter(row, item);
      result = result === undefined ? value : logicalOperator === "OR" ? result || value : result && value;
    } else if (typeof item === "string" && (item.toLowerCase() === "and" || item.toLowerCase() === "or")) {
      logicalOperator = item.toUpperCase() as "AND" | "OR";
    }
  }

  return result ?? true;
}

function evaluateCondition(fieldValue: unknown, operator: string, value: unknown): boolean {
  const text = fieldValue === null || fieldValue === undefined ? "" : String(fieldValue).toLowerCase();
  const target = typeof value === "string" ? value.toLowerCase() : value;

  switch (operator) {
    case "=":
      return fieldValue === value;
    case "<>":
    case "!=":
      return fieldValue !== value;
    case ">":
      return (fieldValue as never) > (value as never);
    case ">=":
      return (fieldValue as never) >= (value as never);
    case "<":
      return (fieldValue as never) < (value as never);
    case "<=":
      return (fieldValue as never) <= (value as never);
    case "contains":
      return typeof target === "string" && text.includes(target);
    case "notcontains":
      return !(typeof target === "string" && text.includes(target));
    case "startswith":
      return typeof target === "string" && text.startsWith(target);
    case "endswith":
      return typeof target === "string" && text.endsWith(target);
    case "between":
      return (
        Array.isArray(value) &&
        value.length === 2 &&
        (fieldValue as never) >= (value[0] as never) &&
        (fieldValue as never) <= (value[1] as never)
      );
    case "in":
    case "anyof":
      return Array.isArray(value) && value.includes(fieldValue);
    case "notin":
    case "noneof":
      return Array.isArray(value) && !value.includes(fieldValue);
    case "isblank":
      return fieldValue === null || fieldValue === undefined || fieldValue === "";
    case "isnotblank":
      return !(fieldValue === null || fieldValue === undefined || fieldValue === "");
    default:
      return fieldValue === value;
  }
}

function compareClientValues(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined) return -1;
  if (b === null || b === undefined) return 1;
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

/** clientSide 모드 — 이미 전체를 받아둔 rows 에 query(filter·sort·skip/take)를 로컬로 적용한다. */
export function applyClientQuery<T>(allRows: T[], query: GridQuery): { rows: T[]; totalCount: number } {
  const filtered = query.filter ? allRows.filter((row) => evaluateClientFilter(row, query.filter)) : allRows.slice();

  const sort = query.sort;
  if (sort && sort.length > 0) {
    filtered.sort((rowA, rowB) => {
      for (const item of sort) {
        const cmp = compareClientValues(getFieldValue(rowA, item.selector), getFieldValue(rowB, item.selector));
        if (cmp !== 0) return item.desc ? -cmp : cmp;
      }
      return 0;
    });
  }

  const take = query.take ?? filtered.length;
  const rows = filtered.slice(query.skip, query.skip + take);
  return { rows, totalCount: filtered.length };
}
