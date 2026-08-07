import { describe, expect, it } from "vitest";

import { formatDate } from "@/utils/common/formatters/date";

// 2026-03-05T15:30:45Z — 타임존에 따라 날짜가 갈리는 경계 (UTC 3/5 저녁 · KST 3/6 자정 직후).
const NEAR_MIDNIGHT = "2026-03-05T15:30:45Z";

// 표시 타임존 정책: 세 모드 모두 `timeZone` 이 없으면 **사용자(런타임 기본) 타임존**을 쓴다
// (결정 2026-07-30, 이슈 #263). 그래서 값을 고정하려면 `timeZone` 을 명시해야 한다 —
// 명시 없이 기대값을 박으면 실행 환경(로컬 KST / CI UTC)에 따라 깨진다.
// 기본 동작은 "런타임 기본과 일치하는가" 로 검증한다 (환경 무관).
const runtimeTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

describe("formatDate — 표시 타임존 정책", () => {
  it("timeZone 미지정이면 사용자(런타임 기본) 타임존을 쓴다", () => {
    expect(formatDate(NEAR_MIDNIGHT, "datetime")).toBe(formatDate(NEAR_MIDNIGHT, "datetime", { timeZone: runtimeTz }));
  });

  it("세 모드가 같은 타임존을 쓴다 (date·time 이 datetime 과 어긋나지 않는다)", () => {
    const datetime = formatDate(NEAR_MIDNIGHT, "datetime")!;
    expect(formatDate(NEAR_MIDNIGHT, "date")).toBe(datetime.slice(0, 10));
    expect(formatDate(NEAR_MIDNIGHT, "time")).toBe(datetime.slice(11));
  });
});

describe("formatDate — date", () => {
  it("timeZone 을 명시하면 그 타임존의 날짜를 준다", () => {
    expect(formatDate(NEAR_MIDNIGHT, "date", { timeZone: "UTC" })).toBe("2026-03-05");
    expect(formatDate(NEAR_MIDNIGHT, "date", { timeZone: "Asia/Seoul" })).toBe("2026-03-06");
  });

  it("Date 객체도 받는다", () => {
    expect(formatDate(new Date(NEAR_MIDNIGHT), "date", { timeZone: "Asia/Seoul" })).toBe("2026-03-06");
  });
});

describe("formatDate — datetime", () => {
  it("timeZone 을 명시하면 그 타임존의 YYYY-MM-DD HH:mm:ss 를 준다", () => {
    expect(formatDate(NEAR_MIDNIGHT, "datetime", { timeZone: "UTC" })).toBe("2026-03-05 15:30:45");
    expect(formatDate(NEAR_MIDNIGHT, "datetime", { timeZone: "Asia/Seoul" })).toBe("2026-03-06 00:30:45");
  });
});

describe("formatDate — time", () => {
  it("timeZone 을 명시하면 그 타임존의 HH:mm:ss 를 준다", () => {
    expect(formatDate(NEAR_MIDNIGHT, "time", { timeZone: "UTC" })).toBe("15:30:45");
    expect(formatDate(NEAR_MIDNIGHT, "time", { timeZone: "Asia/Seoul" })).toBe("00:30:45");
  });

  it("자정을 00:00:00 으로 준다 (24:00:00 여지 없음)", () => {
    expect(formatDate("2026-03-05T15:00:00Z", "time", { timeZone: "Asia/Seoul" })).toBe("00:00:00");
  });
});

describe("formatDate — 빈 값·잘못된 값", () => {
  it.each([
    ["null", null],
    ["undefined", undefined],
    ["빈 문자열", ""],
    ["0", 0],
  ])("%s 은 null 을 준다 (표시할 값 없음)", (_label, input) => {
    expect(formatDate(input, "date")).toBeNull();
  });

  it("파싱 불가한 문자열도 null 을 준다 (Invalid Date 를 그대로 내보내지 않는다)", () => {
    expect(formatDate("날짜아님", "datetime")).toBeNull();
  });
});
