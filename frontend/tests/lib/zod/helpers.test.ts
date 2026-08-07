// #382 — `Optional()` 이 주석으로 약속한 "문자열 타입 자동변환"에 그물이 없어 조용히 깨졌다.
// (`getType()` 이 Zod v3 내부 shape `_def.typeName` 을 읽는데 이 레포는 zod v4다.)
//
// HTML `<input>` 의 value 는 **항상 문자열**이다. 숫자·불리언 필드를 그 값으로 그대로 제출하면
// 자동변환이 없는 한 검증이 실패한다 — 그래서 이 동작은 "있으면 좋은 것"이 아니라 폼이 도는
// 전제다. 아래 표는 그 전제를 케이스로 고정한다.
//
// **검증 경계** — 여기서 보는 것은 스키마의 파싱 결과뿐이다. 실제 폼(react-hook-form)이 어떤
// 값을 넘기는지, 브라우저에서 어떻게 보이는지는 이 층에서 안 보인다. 마지막 describe 가
// 실제 스키마(watchlist·adminUser)를 직접 파싱해 그 간극을 한 칸 좁힌다.

import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Field, files, int, Optional, PositiveFloat, str } from "@/lib/zod/helpers";

describe("Optional() — 숫자 문자열 자동변환(#382)", () => {
  const NUMBER_CASES: [string, z.ZodTypeAny][] = [
    ["z.number()", z.number()],
    ["int()", int()],
    ["PositiveFloat()", PositiveFloat()],
    ["Field({ ge: 0 }).float()", Field({ ge: 0 }).float()],
  ];

  it.each(NUMBER_CASES)("Optional(%s) 는 숫자 문자열을 숫자로 바꾼다", (_label, schema) => {
    const result = Optional(schema).safeParse("42");
    expect(result.success).toBe(true);
    expect(result.success && result.data).toBe(42);
  });

  it("소수 문자열도 바꾼다", () => {
    expect(Optional(PositiveFloat()).safeParse("1500.5")).toMatchObject({ success: true, data: 1500.5 });
  });

  it("숫자로 읽을 수 없는 문자열은 거절이다 — '값 없음'으로 접지 않는다", () => {
    // 예전엔 `{ success: true, data: undefined }` 였다. 그 결과를 `?? null` 로 받는 PUT
    // 전체표현 계약(#400)에서 **손상된 요청이 필드를 지우는 정상 요청으로 둔갑**했다.
    expect(Optional(z.number()).safeParse("abc").success).toBe(false);
  });

  it("이미 숫자인 값은 그대로 통과한다", () => {
    expect(Optional(z.number()).safeParse(42)).toMatchObject({ success: true, data: 42 });
  });

  it("스키마의 제약은 변환 뒤에도 살아 있다 — 음수는 PositiveFloat 을 통과하지 못한다", () => {
    expect(Optional(PositiveFloat()).safeParse("-1").success).toBe(false);
  });

  it("목록이 줄지 않았다 (fail-closed)", () => {
    expect(NUMBER_CASES.length).toBe(4);
  });
});

// 「숫자로 읽히지만 사람이 안 쓴 표기」 전수 — `Number()` 가 받아주는 표기와 폼이 실제로 만드는
// 표기의 간극이다. 가장 비싼 것이 `"3e2"`→300 이었다: 배정 해제가 아니라 **존재하지도 않을 300번
// 워크스페이스로 조용히 배정**되고, 정수 가드(`z.number().int()`)는 300 도 정수라 못 잡았다.
// 선은 「정수인가」가 아니라 **「사람이 읽는 값과 같은가」**에 긋는다 — 십진수 표기만 받는다.
describe("Optional(int()) — 숫자 표기 전수(사람이 읽는 값과 같은 것만 받는다)", () => {
  const ACCEPTED: [string, number][] = [
    ["1", 1],
    [" 1 ", 1], // 앞뒤 공백 — str() 도 trim 한다
    ["\n2\t", 2],
    ["+1", 1],
    ["-1", -1],
    ["007", 7], // 0 채움은 십진수다 (0o/0x 접두어와 다르다)
  ];

  const REJECTED: string[] = [
    "3e2", // → 300. Number() 가 지수 표기를 받는다
    "3E2",
    "0x10", // → 16
    "0X10",
    "0b101", // → 5
    "0o17", // → 15
    "1e400", // → Infinity
    "Infinity",
    "-Infinity",
    "1_000", // Number() 는 NaN — 예전엔 조용히 undefined
    "1n", // 예전엔 조용히 undefined
    "garbage",
    "3.7", // 십진수지만 정수가 아니다 — 안쪽 int() 가 잡는다
  ];

  it.each(ACCEPTED)("%s 는 %i 로 받는다", (input, expected) => {
    expect(Optional(int()).safeParse(input)).toMatchObject({ success: true, data: expected });
  });

  it.each(REJECTED)("%s 는 거절한다 — undefined 로 접히면 필드가 지워진다", (input) => {
    expect(Optional(int()).safeParse(input).success).toBe(false);
  });

  it("십진수라도 자릿수가 넘쳐 Infinity 가 되면 거절한다", () => {
    const overflowing = "1".repeat(400);
    expect(Number(overflowing)).toBe(Infinity);
    expect(Optional(int()).safeParse(overflowing).success).toBe(false);
  });

  it("표가 줄지 않았다 (fail-closed)", () => {
    expect(ACCEPTED.length).toBe(6);
    expect(REJECTED.length).toBe(13);
  });
});

describe("Optional() — 불리언 문자열 자동변환(#382)", () => {
  it.each([
    ["true", true],
    ["TRUE", true],
    ["false", false],
    ["False", false],
  ])("Optional(z.boolean()) 는 %s 를 %s 로 바꾼다", (input, expected) => {
    expect(Optional(z.boolean()).safeParse(input)).toMatchObject({ success: true, data: expected });
  });

  it("불리언으로 읽을 수 없는 문자열은 거절이다 — 숫자 축과 같은 이유", () => {
    expect(Optional(z.boolean()).safeParse("yes").success).toBe(false);
  });

  it("이미 불리언인 값은 그대로 통과한다", () => {
    expect(Optional(z.boolean()).safeParse(false)).toMatchObject({ success: true, data: false });
  });
});

describe("Optional() — 빈값 처리(자동변환과 무관하게 유지돼야 하는 기존 계약)", () => {
  it.each([
    ["null", null],
    ["undefined", undefined],
    ["빈 문자열", ""],
    ["공백만 있는 문자열", "   "],
  ])("%s 는 undefined 로 접힌다", (_label, input) => {
    expect(Optional(str()).safeParse(input)).toMatchObject({ success: true, data: undefined });
  });

  it("빈 배열은 배열 스키마에서만 '선택 없음'이다", () => {
    // 업로더가 파일을 하나도 안 고른 상태 — 여기선 접히는 게 맞다.
    expect(Optional(files()).safeParse([])).toMatchObject({ success: true, data: undefined });
  });

  it.each([
    ["문자열 스키마", str()],
    ["숫자 스키마", int()],
  ])("배열이 아닌 %s 에 온 빈 배열은 손상값이라 거절한다", (_label, schema) => {
    // 예전엔 여기서도 undefined 로 접혀, `workspace_id: []` 가 200 + 배정 해제였다.
    expect(Optional(schema).safeParse([]).success).toBe(false);
  });

  it("문자열 스키마는 문자열을 그대로 통과시킨다 (변환이 문자열 경로를 갉아먹지 않는다)", () => {
    expect(Optional(Field({ max_length: 20 }).str()).safeParse("KOSPI")).toMatchObject({
      success: true,
      data: "KOSPI",
    });
  });

  it("문자열 스키마의 제약은 그대로다", () => {
    expect(Optional(Field({ max_length: 3 }).str()).safeParse("KOSPI").success).toBe(false);
  });
});

// 자동변환이 없으면 곧바로 깨지는 실제 스키마 필드 — "쓰는 데가 없어서 안 드러난 것"이
// 아님을 고정한다. 새 숫자/불리언 Optional 필드가 늘면 이 표도 늘려야 한다.
describe("Optional() 을 숫자 타입에 쓰는 실제 스키마(#382)", () => {
  it("watchlist 의 가격 필드는 문자열 입력을 받아들인다", async () => {
    const { WatchlistCreateInSchema } = await import("@/schemas/watchlist/watchlist");
    const parsed = WatchlistCreateInSchema.safeParse({
      ticker: "005930",
      issuer_nm: "삼성전자",
      use_at: "Y",
      target_price: "71000",
      alert_price: "70000.5",
    });
    expect(parsed.success, parsed.success ? "" : JSON.stringify(parsed.error.issues)).toBe(true);
    expect(parsed.success && parsed.data.target_price).toBe(71000);
    expect(parsed.success && parsed.data.alert_price).toBe(70000.5);
  });

  it("adminUser 의 workspace_id 는 문자열 입력을 받아들인다 (select 의 value 는 문자열이다)", async () => {
    const { AdminUserUpdateInSchema } = await import("@/schemas/common/adminUser");
    const parsed = AdminUserUpdateInSchema.safeParse({ workspace_id: "3", use_at: "Y", appr_at: "Y" });
    expect(parsed.success, parsed.success ? "" : JSON.stringify(parsed.error.issues)).toBe(true);
    expect(parsed.success && parsed.data.workspace_id).toBe(3);
  });
});
