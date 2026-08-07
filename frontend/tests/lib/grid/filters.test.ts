import { describe, expect, it } from "vitest";

import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";

// escapeLikeValue 는 export 되지 않는다 — 공개 API 인 convertFilterToPrismaWhere 를 통해 검증한다.
describe("convertFilterToPrismaWhere — LIKE 와일드카드 이스케이프", () => {
  it("contains 값의 % _ \\ 를 백슬래시로 이스케이프한다", () => {
    expect(convertFilterToPrismaWhere(["name", "contains", "a%b_c\\d"])).toEqual({
      name: { contains: "a\\%b\\_c\\\\d", mode: "insensitive" },
    });
  });

  it.each([
    ["startswith", "startsWith"],
    ["endswith", "endsWith"],
  ])("%s 도 같은 이스케이프를 적용한다", (operator, prismaKey) => {
    expect(convertFilterToPrismaWhere(["name", operator, "50%"])).toEqual({
      name: { [prismaKey]: "50\\%", mode: "insensitive" },
    });
  });

  // 중첩 not(NestedStringFilter)엔 mode 필드가 없어 바깥에 둔다 (소스 주석의 계약).
  it("notcontains 는 중첩 not 안의 값을 이스케이프하고 mode 는 바깥에 둔다", () => {
    expect(convertFilterToPrismaWhere(["name", "notcontains", "100%"])).toEqual({
      name: { not: { contains: "100\\%" }, mode: "insensitive" },
    });
  });

  // 이스케이프가 텍스트 연산자 밖으로 번지면 `=`·`in` 이 찾지 못하는 값이 된다.
  it("비-LIKE 연산자의 값은 이스케이프하지 않는다", () => {
    expect(convertFilterToPrismaWhere(["code", "=", "100%"])).toEqual({ code: { equals: "100%" } });
    expect(convertFilterToPrismaWhere(["code", "<>", "50_"])).toEqual({ code: { not: "50_" } });
    expect(convertFilterToPrismaWhere(["tag", "in", ["a%", "b_"]])).toEqual({ tag: { in: ["a%", "b_"] } });
    expect(convertFilterToPrismaWhere(["tag", "notin", ["a%"]])).toEqual({ tag: { notIn: ["a%"] } });
  });

  it("문자열이 아닌 값은 이스케이프 없이 통과시킨다", () => {
    expect(convertFilterToPrismaWhere(["cnt", "contains", 100])).toEqual({
      cnt: { contains: 100, mode: "insensitive" },
    });
  });
});

describe("convertFilterToPrismaWhere — 대소문자 무관(mode: insensitive) 적용 범위", () => {
  it.each(["contains", "notcontains", "startswith", "endswith"])("%s 에는 mode: insensitive 가 붙는다", (operator) => {
    const where = convertFilterToPrismaWhere(["name", operator, "x"]) as Record<string, Record<string, unknown>>;
    expect(where.name.mode).toBe("insensitive");
  });

  // 파이썬 서비스도 비-LIKE 연산자는 대소문자를 가린다 — 여기만 무관하게 만들면 두 소비자가 갈린다.
  it.each([
    [">", 1],
    [">=", 1],
    ["<", 1],
    ["<=", 1],
    ["=", "x"],
    ["<>", "x"],
    ["in", ["x"]],
    ["notin", ["x"]],
  ])("%s 에는 mode 가 붙지 않는다", (operator, value) => {
    const where = convertFilterToPrismaWhere(["f", operator, value]) as Record<string, unknown>;
    expect(where.f).not.toHaveProperty("mode");
  });
});

describe("convertFilterToPrismaWhere — 비교·범위·공백 연산자", () => {
  it.each([
    [">", "gt"],
    [">=", "gte"],
    ["<", "lt"],
    ["<=", "lte"],
  ])("%s → %s", (operator, prismaKey) => {
    expect(convertFilterToPrismaWhere(["age", operator, 30])).toEqual({ age: { [prismaKey]: 30 } });
  });

  it("between 은 gte·lte 로 펼쳐진다", () => {
    expect(convertFilterToPrismaWhere(["age", "between", [10, 20]])).toEqual({ age: { gte: 10, lte: 20 } });
  });

  // #295 M-5 — 예전엔 2개짜리 배열이 아니면 조건을 조용히 버렸다({} 를 반환). 그러면
  // backend-service(미해결 바인드 → 500)와 갈린다 — 조용한 통과 대신 거절로 모았다.
  it("between 값이 2개짜리 배열이 아니면 거절한다", () => {
    expect(() => convertFilterToPrismaWhere(["age", "between", [10]])).toThrow();
    expect(() => convertFilterToPrismaWhere(["age", "between", [10, 20, 30]])).toThrow();
    expect(() => convertFilterToPrismaWhere(["age", "between", 10])).toThrow();
  });

  // 날짜는 UTC 로 강제 해석한다 (슬래시→하이픈, 공백→T, Z 부착). 로컬 타임존 해석으로
  // 되돌리면 서버·클라이언트 타임존에 따라 조회 범위가 달라진다.
  it("날짜 문자열은 UTC 로 강제 해석된 Date 가 된다", () => {
    expect(convertFilterToPrismaWhere(["reg_dt", ">=", "2026-01-01"])).toEqual({
      reg_dt: { gte: new Date("2026-01-01T00:00:00.000Z") },
    });
    expect(convertFilterToPrismaWhere(["reg_dt", "<=", "2026/03/05 08:00:00"])).toEqual({
      reg_dt: { lte: new Date("2026-03-05T08:00:00.000Z") },
    });
  });

  it("날짜로 안 보이는 문자열은 그대로 둔다", () => {
    expect(convertFilterToPrismaWhere(["name", "=", "2026년"])).toEqual({ name: { equals: "2026년" } });
  });

  // #295 M-6 — 예전 정규식엔 앵커가 없어 날짜꼴을 부분 포함하기만 하는 문자열도 Date 로
  // 강제 변환됐다(예: 메모의 "12024-01-011"). 전체 일치일 때만 coercion 한다.
  it("날짜꼴을 부분 포함할 뿐인 문자열은 Date 로 강제 변환하지 않는다", () => {
    expect(convertFilterToPrismaWhere(["memo", "=", "12024-01-011"])).toEqual({ memo: { equals: "12024-01-011" } });
    expect(convertFilterToPrismaWhere(["memo", "=", "id-2026-01-01-suffix"])).toEqual({
      memo: { equals: "id-2026-01-01-suffix" },
    });
  });

  it("null 은 Prisma null 문법으로 변환된다", () => {
    expect(convertFilterToPrismaWhere(["memo", "=", null])).toEqual({ memo: null });
    expect(convertFilterToPrismaWhere(["memo", "<>", null])).toEqual({ memo: { not: null } });
  });

  it("isblank / isnotblank 는 null 과 빈 문자열을 함께 다룬다", () => {
    expect(convertFilterToPrismaWhere(["memo", "isblank", null])).toEqual({
      OR: [{ memo: null }, { memo: { equals: "" } }],
    });
    expect(convertFilterToPrismaWhere(["memo", "isnotblank", null])).toEqual({
      AND: [{ memo: { not: null } }, { memo: { not: "" } }],
    });
  });

  // #295 M-3 — 예전엔 `=` 로 조용히 강등됐다. backend-service 는 이미 같은 입력을 400 으로
  // 거절해 왔다 — 조용한 통과 대신 거절로 모았다.
  it("모르는 연산자는 거절한다", () => {
    expect(() => convertFilterToPrismaWhere(["f", "wat", "v"])).toThrow();
  });
});

describe("convertFilterToPrismaWhere — in 계열 값 검증(#295 M-7)", () => {
  // 예전엔 조건을 조용히 버렸다({} 반환) — backend-service 는 스칼라를 [값] 으로
  // 조용히 감쌌다. 같은 입력, 다른 결과 집합이라 어느 쪽도 조용한 통과가 아니게 모았다.
  it.each(["in", "anyof", "notin", "noneof"])("%s 값이 배열이 아니면 거절한다", (operator) => {
    expect(() => convertFilterToPrismaWhere(["tag", operator, "x"])).toThrow();
  });

  it("빈 배열 값은 거절 대상이 아니다 — in/anyof 는 무매칭, notin/noneof 는 전체매칭", () => {
    expect(convertFilterToPrismaWhere(["tag", "in", []])).toEqual({ tag: { in: [] } });
    expect(convertFilterToPrismaWhere(["tag", "noneof", []])).toEqual({ tag: { notIn: [] } });
  });
});

describe("convertFilterToPrismaWhere — 필드명 검증(#295 M-4)", () => {
  // backend-service 의 _SAFE_IDENTIFIER_RE 와 같은 규칙. 예전엔 검증이 없어 이상한
  // 필드명이 예측 불가능한 Prisma 런타임 오류로 떨어졌다.
  it("SQL 인젝션 모양·숫자로 시작하는 필드명을 거절한다", () => {
    expect(() => convertFilterToPrismaWhere(["a; DROP TABLE t", "=", 1])).toThrow();
    expect(() => convertFilterToPrismaWhere(["1bad", "=", 1])).toThrow();
  });

  it("정상 필드명은 그대로 통과한다", () => {
    expect(convertFilterToPrismaWhere(["valid_field_1", "=", 1])).toEqual({ valid_field_1: { equals: 1 } });
  });
});

describe("convertFilterToPrismaWhere — 빈 배열·항 없는 부정(#306)", () => {
  // DevExtreme 이 검색 패널에서 "아무것도 안 맞음" 뜻으로 실제로 회선에 올리는 형태다.
  // 예전엔 "필터 없음"(전건)으로 읽혔다 — 정반대다.
  it("빈 배열은 항상 거짓 조건을 낸다", () => {
    expect(convertFilterToPrismaWhere([])).toEqual({ OR: [] });
  });

  it('항 없는 부정 ["!"] 은 항상 거짓 조건을 낸다', () => {
    expect(convertFilterToPrismaWhere(["!"])).toEqual({ OR: [] });
  });

  it("빈 배열의 부정은 항상 참(무제약이 아니라 빈 AND/OR 도 아닌 빈 객체)", () => {
    expect(convertFilterToPrismaWhere(["!", []])).toEqual({ NOT: { OR: [] } });
  });
});

describe("convertFilterToPrismaWhere — 그룹 안 and/or 혼용 거절(#295 M-2)", () => {
  // DevExtreme 자신의 필터 컴파일러(grid_core/m_utils.js compileGroup)도 같은 입력에
  // E4019 를 던진다 — 평면 배열 안에서 and/or 를 섞는 문법은 없다. 예전엔 마지막에 본
  // 연산자가 전부를 덮어써 `[A,"and",B,"or",C]` 가 `A OR B OR C` 가 됐다.
  it("한 그룹 안에서 and 와 or 가 섞이면 거절한다", () => {
    expect(() => convertFilterToPrismaWhere([["a", "=", 1], "and", ["b", "=", 2], "or", ["c", "=", 3]])).toThrow();
  });

  it("균일한 연산자는 그대로 통과한다", () => {
    expect(convertFilterToPrismaWhere([["a", "=", 1], "and", ["b", "=", 2], "and", ["c", "=", 3]])).toEqual({
      AND: [{ a: { equals: 1 } }, { b: { equals: 2 } }, { c: { equals: 3 } }],
    });
  });
});

describe("convertFilterToPrismaWhere — 복합 조건", () => {
  it("and 로 묶인 조건은 AND 배열", () => {
    expect(convertFilterToPrismaWhere([["a", "contains", "x"], "and", ["b", "=", "y"]])).toEqual({
      AND: [{ a: { contains: "x", mode: "insensitive" } }, { b: { equals: "y" } }],
    });
  });

  it("or 로 묶인 조건은 OR 배열", () => {
    expect(convertFilterToPrismaWhere([["a", "=", "x"], "or", ["b", "=", "y"]])).toEqual({
      OR: [{ a: { equals: "x" } }, { b: { equals: "y" } }],
    });
  });

  it("논리 연산자가 없으면 AND 로 묶는다", () => {
    expect(
      convertFilterToPrismaWhere([
        ["a", "=", "x"],
        ["b", "=", "y"],
      ]),
    ).toEqual({ AND: [{ a: { equals: "x" } }, { b: { equals: "y" } }] });
  });

  it("조건이 하나면 배열로 감싸지 않는다", () => {
    expect(convertFilterToPrismaWhere([["a", "=", "x"]])).toEqual({ a: { equals: "x" } });
  });

  it("중첩 그룹을 재귀 처리한다", () => {
    expect(convertFilterToPrismaWhere([[["a", "=", "1"], "or", ["b", "=", "2"]], "and", ["c", "=", "3"]])).toEqual({
      AND: [{ OR: [{ a: { equals: "1" } }, { b: { equals: "2" } }] }, { c: { equals: "3" } }],
    });
  });
});

describe("convertFilterToPrismaWhere — 입력 형태", () => {
  it("JSON 문자열도 받는다 (그리드가 쿼리스트링으로 넘기는 형태)", () => {
    expect(convertFilterToPrismaWhere('["name","contains","%"]')).toEqual({
      name: { contains: "\\%", mode: "insensitive" },
    });
  });

  // "필터가 안 왔다"와 "필터가 왔는데 형식이 깨졌다"는 다르다 — `searchParams.get("filter")` 는
  // `string | null` 이라 아래 둘이 "안 왔다"의 전부다.
  it.each([
    ["filter 파라미터 부재(null)", null],
    ["빈 문자열", ""],
  ])("%s 은 빈 조건 {} 을 준다 (제약 없음이 맞는 경우)", (_label, input) => {
    expect(convertFilterToPrismaWhere(input)).toEqual({});
  });

  // #389 — 예전엔 이 셋도 `{}` 였다. 형식 오류를 "필터 없음"으로 삼키면 사용자는 필터가
  // 걸렸다고 믿는데 전건이 나간다. DevExtreme 평가기는 같은 입력에 0건 또는 예외를 낸다
  // (scripts/verify_filter_negation.mjs 의 malformed_never_returns_all_rows 가 실측을 고정).
  it.each([
    ["잘못된 JSON", "{not json"],
    ["배열이 아닌 JSON", '{"a":1}'],
    ["배열이 아닌 값", 42],
  ])("%s 은 거절한다 (전건 반환 방지)", (_label, input) => {
    expect(() => convertFilterToPrismaWhere(input)).toThrow();
  });
});

// #389 — 두 파서가 **같은 방향으로** 틀려서(둘 다 "필터 없음"으로 읽어 전건 반환) 적합성
// 대조로는 구조적으로 못 잡던 모양들. 공유 fixture(scripts/fixtures/filter_conformance_cases.json)
// 의 ref "#389" 축과 같은 목록이고, 기대값의 근거는 DevExtreme 평가기다.
describe("convertFilterToPrismaWhere — 형식 오류는 거절한다(#389)", () => {
  const MALFORMED: [string, unknown][] = [
    ["연산자 자리에 리스트", ["a", ["="], 1]],
    ["연산자 자리에 null", ["a", null, 1]],
    ["연산자 자리에 숫자", ["a", 5, 1]],
    ["연산자 토큰만", ["and"]],
    ["값이 빠진 단일 조건", ["a", "="]],
    ["필드 자리에 숫자", [1, "=", 1]],
    ["평면 5항", ["a", "=", 1, "and", 2]],
    ["부정 피연산자가 배열이 아님", ["!", "x"]],
    ["조건 없이 연산자로 끝남", ["a", "=", 1, "and"]],
    ["좌항 없는 연산자", ["and", ["a", "=", 1]]],
  ];

  it.each(MALFORMED)("%s 은 거절한다", (_label, input) => {
    expect(() => convertFilterToPrismaWhere(input)).toThrow();
  });

  it("거절은 500 이 아니라 400 으로 매핑되는 모양이다 — Error 를 상속하지 않는다", () => {
    // createErrorResponse 는 `instanceof Error` 가 아닌 `{ message }` 객체만 400 으로 옮긴다.
    // 진짜 Error 를 던지면 같은 입력이 backend-service(400)와 갈려 500 이 된다.
    expect.assertions(MALFORMED.length * 2);
    for (const [, input] of MALFORMED) {
      try {
        convertFilterToPrismaWhere(input);
      } catch (thrown) {
        expect(thrown).not.toBeInstanceOf(Error);
        expect(thrown).toHaveProperty("message");
      }
    }
  });

  it("목록이 줄지 않았다 (fail-closed)", () => {
    expect(MALFORMED.length).toBe(10);
  });
});

describe("convertSortToPrismaOrderBy", () => {
  it("selector·desc 를 Prisma orderBy 배열로 옮긴다", () => {
    expect(convertSortToPrismaOrderBy([{ selector: "name", desc: true }, { selector: "age" }])).toEqual([
      { name: "desc" },
      { age: "asc" },
    ]);
  });

  it("JSON 문자열도 받는다", () => {
    expect(convertSortToPrismaOrderBy('[{"selector":"reg_dt","desc":true}]')).toEqual([{ reg_dt: "desc" }]);
  });

  it("selector 없는 항목은 건너뛴다", () => {
    expect(convertSortToPrismaOrderBy([{ desc: true }, { selector: "age" }])).toEqual([{ age: "asc" }]);
  });

  it.each([
    ["falsy", null],
    ["빈 배열", []],
    ["잘못된 JSON", "{not json"],
    ["배열이 아닌 JSON", '{"a":1}'],
    ["selector 가 하나도 없는 배열", [{ desc: true }]],
  ])("%s 은 undefined (orderBy 미지정)", (_label, input) => {
    expect(convertSortToPrismaOrderBy(input)).toBeUndefined();
  });
});

describe("convertSortToPrismaOrderBy — selector 식별자 검증(#401 ①)", () => {
  // filter 축은 #295 M-4 로 두 파서가 같은 정규식을 쓰는데 sort 축은 TS 만 무검증이었다 —
  // 같은 입력이 두 경로에서 다른 판정을 받는 것이 #295 가 없앤 클래스다.
  it.each([["a; DROP TABLE t"], ["1bad"], ["with space"], ["a.b"]])(
    "유효하지 않은 selector(%s)는 거절한다",
    (selector) => {
      expect(() => convertSortToPrismaOrderBy([{ selector }])).toThrow();
    },
  );

  it("거절 신호는 진짜 Error 가 아니라 `{message}` 다 — 그래야 400 이 된다(#389 매핑)", () => {
    let thrown: any = null;
    try {
      convertSortToPrismaOrderBy([{ selector: "a; DROP TABLE t" }]);
    } catch (error) {
      thrown = error;
    }
    expect(thrown).not.toBeNull();
    expect(thrown instanceof Error).toBe(false);
    expect(typeof thrown.message).toBe("string");
  });

  it.each([[[null]], [["name"]], [[1]]])("객체가 아닌 정렬 항목(%j)은 거절한다 (예전엔 TypeError → 500)", (input) => {
    expect(() => convertSortToPrismaOrderBy(input)).toThrow();
  });

  it("정상 selector 는 그대로 통과한다 (거절이 정상 경로를 갉아먹지 않는다)", () => {
    expect(convertSortToPrismaOrderBy([{ selector: "reg_dt", desc: true }])).toEqual([{ reg_dt: "desc" }]);
  });
});

describe("convertFilterToPrismaWhere — 재귀 깊이 상한(#401 ②)", () => {
  // 상한 값(32)의 근거는 lib/devextreme/filters.ts 의 MAX_FILTER_DEPTH 주석 — 레포가 실제로
  // 만들거나 회귀 그물이 못박은 필터의 최대 깊이 4, 화면이 만드는 최대 2 의 8배 여유다.
  const nested = (depth: number): unknown => {
    let node: unknown = ["a", "=", 1];
    for (let i = 1; i < depth; i++) node = ["!", node];
    return node;
  };

  it("상한과 같은 깊이(32)는 통과한다", () => {
    expect(() => convertFilterToPrismaWhere(nested(32))).not.toThrow();
  });

  it("상한을 한 단 넘긴 깊이(33)는 거절한다 (예전엔 스택이 무너질 때까지 내려가 RangeError → 500)", () => {
    expect(() => convertFilterToPrismaWhere(nested(33))).toThrow();
  });

  it("거절 신호는 진짜 Error 가 아니라 `{message}` 다 — 그래야 400 이 된다", () => {
    let thrown: any = null;
    try {
      convertFilterToPrismaWhere(nested(33));
    } catch (error) {
      thrown = error;
    }
    expect(thrown).not.toBeNull();
    expect(thrown instanceof Error).toBe(false);
    expect(thrown.message).toContain("32");
  });

  it("그룹 중첩도 같은 상한을 쓴다 (부정 체인만이 아니다)", () => {
    const group = (depth: number): unknown => {
      let node: unknown = ["a", "=", 1];
      for (let i = 1; i < depth; i++) node = [node, "and", ["b", "=", 2]];
      return node;
    };
    expect(() => convertFilterToPrismaWhere(group(32))).not.toThrow();
    expect(() => convertFilterToPrismaWhere(group(33))).toThrow();
  });
});
