import { describe, expect, it } from "vitest";

import { buildGridQuery } from "@/hooks/shared/gridQuery";
import { convertFilterToPrismaWhere } from "@/lib/grid/filters";
import type { GridSort } from "@/types/grid";

// useServerTable 자체는 React 훅이라 렌더 없이 호출할 수 없다(O0 는 jsdom·컴포넌트 렌더
// 테스트를 아직 도입하지 않았다 — vitest.config.ts, environment: "node"). 그래서 훅이 내부적으로
// 쓰는 순수 함수 buildGridQuery(hooks/shared/gridQuery.ts, useServerTable.ts 가 그대로 재사용)를
// 직접 검증한다 — 페이지/정렬/필터 상태 → 서버로 나가는 GridQuery 로의 변환이 이 오더의 실제 계약이다.
// (#381 이전엔 useServerTable.ts 의 showToast import 가 DevExtreme Toast 배럴을 거쳐 env.ts 의
// zod 검증까지 물어, node 환경에서 훅 렌더 없이도 import 만으로 던지는 두 번째 이유가 있었다.
// #381 로 useServerTable.ts 가 toastQueue.ts(순수 모듈)를 직접 import 하도록 바뀌어 그 경로는
// 해소됐다 — 지금은 위 첫 번째 이유(훅은 렌더 없이 호출 불가)만으로 이 분리가 유효하다.)
describe("buildGridQuery — ① 페이지 이동 → skip/take", () => {
  it("pageIndex·pageSize 를 skip/take 로 변환한다", () => {
    expect(buildGridQuery({ pageIndex: 0, pageSize: 20 })).toMatchObject({ skip: 0, take: 20 });
    expect(buildGridQuery({ pageIndex: 2, pageSize: 20 })).toMatchObject({ skip: 40, take: 20 });
    expect(buildGridQuery({ pageIndex: 3, pageSize: 15 })).toMatchObject({ skip: 45, take: 15 });
  });

  it("take 는 항상 채워진다 — skip 만 보내면 리포지토리가 skip 을 무시한다 (watchlist_repository.py)", () => {
    const query = buildGridQuery({ pageIndex: 5, pageSize: 10 });
    expect(query.take).toBe(10);
    expect(query.skip).toBe(50);
  });
});

describe("buildGridQuery — ② 정렬 변경 → sort: [{selector, desc}]", () => {
  it("정렬 항목을 selector·desc 형태 그대로 전달한다", () => {
    const sort: GridSort[] = [{ selector: "ticker", desc: true }];
    expect(buildGridQuery({ pageIndex: 0, pageSize: 20, sort })).toMatchObject({
      sort: [{ selector: "ticker", desc: true }],
    });
  });

  it("keyField(rn)로의 정렬은 제거된다 — 바깥 ROW_NUMBER() 별칭이라 안쪽 ORDER BY 가 못 가리킨다", () => {
    const sort: GridSort[] = [{ selector: "rn", desc: false }];
    expect(buildGridQuery({ pageIndex: 0, pageSize: 20, sort }).sort).toBeUndefined();
  });

  it("rn 과 다른 컬럼이 섞이면 rn 만 제거하고 나머지는 유지한다", () => {
    const sort: GridSort[] = [
      { selector: "rn", desc: false },
      { selector: "priority", desc: true },
    ];
    expect(buildGridQuery({ pageIndex: 0, pageSize: 20, sort }).sort).toEqual([{ selector: "priority", desc: true }]);
  });

  it("정렬 없음은 undefined 로 전달된다", () => {
    expect(buildGridQuery({ pageIndex: 0, pageSize: 20 }).sort).toBeUndefined();
  });
});

describe("buildGridQuery — ③ 필터가 배열 문법 그대로 전달된다", () => {
  it("단일 조건 배열을 변형 없이 그대로 전달한다", () => {
    const filter = ["ticker", "=", "005930"];
    const query = buildGridQuery({ pageIndex: 0, pageSize: 20, filter });
    expect(query.filter).toBe(filter);
    expect(query.filter).toEqual(["ticker", "=", "005930"]);
  });

  it("and/or 그룹 배열도 변형 없이 그대로 전달한다", () => {
    const filter = [["market", "=", "KOSPI"], "and", ["target_price", ">=", 10000]];
    expect(buildGridQuery({ pageIndex: 0, pageSize: 20, filter }).filter).toEqual(filter);
  });
});

// ④ 왕복 검증 — 이 오더의 핵심 증명. buildGridQuery 가 만든 filter 배열을
// convertFilterToPrismaWhere 에 그대로 넣었을 때 기대한 Prisma where 가 나와야
// "백엔드 0줄 변경" 주장이 성립한다.
describe("buildGridQuery — ④ 왕복 검증: filter 배열 → convertFilterToPrismaWhere", () => {
  it('단일 조건: ["ticker","=","005930"] → { ticker: { equals: "005930" } }', () => {
    const query = buildGridQuery({ pageIndex: 0, pageSize: 20, filter: ["ticker", "=", "005930"] });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({ ticker: { equals: "005930" } });
  });

  it('contains: ["issuer_nm","contains","삼성"] → { issuer_nm: { contains: "삼성", mode: "insensitive" } }', () => {
    const query = buildGridQuery({ pageIndex: 0, pageSize: 20, filter: ["issuer_nm", "contains", "삼성"] });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({
      issuer_nm: { contains: "삼성", mode: "insensitive" },
    });
  });

  it("AND 그룹: market=KOSPI and target_price>=10000 → { AND: [...] }", () => {
    const query = buildGridQuery({
      pageIndex: 0,
      pageSize: 20,
      filter: [["market", "=", "KOSPI"], "and", ["target_price", ">=", 10000]],
    });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({
      AND: [{ market: { equals: "KOSPI" } }, { target_price: { gte: 10000 } }],
    });
  });

  it("OR 그룹: sector=IT or sector=반도체 → { OR: [...] }", () => {
    const query = buildGridQuery({
      pageIndex: 0,
      pageSize: 20,
      filter: [["sector", "=", "IT"], "or", ["sector", "=", "반도체"]],
    });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({
      OR: [{ sector: { equals: "IT" } }, { sector: { equals: "반도체" } }],
    });
  });

  // 헤더필터 "제외"가 이 형태로 회선에 오른다(["!", expr]) — 과거 이 부정을 잃고 반대 행을
  // 보여주던 결함(#293)이 있었다. buildGridQuery 가 배열을 손대지 않아야 재발하지 않는다.
  it('부정: ["!", ["priority","=",1]] → { NOT: { priority: { equals: 1 } } }', () => {
    const query = buildGridQuery({ pageIndex: 0, pageSize: 20, filter: ["!", ["priority", "=", 1]] });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({ NOT: { priority: { equals: 1 } } });
  });

  it("필터 없음은 빈 where {} 로 왕복된다", () => {
    const query = buildGridQuery({ pageIndex: 0, pageSize: 20 });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({});
  });

  it("페이지·정렬이 섞여도 filter 왕복 결과는 그대로다 — 필드 간 간섭이 없다", () => {
    const query = buildGridQuery({
      pageIndex: 2,
      pageSize: 15,
      sort: [{ selector: "priority", desc: true }],
      filter: ["use_at", "=", "Y"],
    });
    expect(query).toEqual({
      skip: 30,
      take: 15,
      filter: ["use_at", "=", "Y"],
      sort: [{ selector: "priority", desc: true }],
    });
    expect(convertFilterToPrismaWhere(query.filter)).toEqual({ use_at: { equals: "Y" } });
  });
});
