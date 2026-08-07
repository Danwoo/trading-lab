import { describe, expect, it } from "vitest";

import { getKSTTime, getKSTTimestamp, toEndOfDay } from "@/utils/common/timeUtils";

describe("toEndOfDay", () => {
  it("날짜 문자열에 그날 마지막 시각을 붙인다", () => {
    expect(toEndOfDay("2026-03-05")).toBe("2026-03-05 23:59:59");
  });
});

// KST 는 DST 가 없어 UTC+9 고정이다. 타임존 라이브러리로 바꾸더라도 이 결과는 같아야 한다.
describe("getKSTTime / getKSTTimestamp", () => {
  const base = new Date("2026-03-05T00:00:00.000Z");

  it("기준 시각에 9시간을 더한다", () => {
    expect(getKSTTime(base).toISOString()).toBe("2026-03-05T09:00:00.000Z");
  });

  it("타임스탬프는 +9시간의 초 단위 (밀리초 절사)", () => {
    expect(getKSTTimestamp(new Date("2026-03-05T00:00:00.999Z"))).toBe(Date.UTC(2026, 2, 5, 9, 0, 0) / 1000);
  });

  it("인자로 받은 Date 를 변형하지 않는다", () => {
    const input = new Date("2026-03-05T00:00:00.000Z");
    getKSTTime(input);
    getKSTTimestamp(input);
    expect(input.toISOString()).toBe("2026-03-05T00:00:00.000Z");
  });
});
