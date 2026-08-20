// 숫자 표기의 로케일을 브라우저에 맡기지 않는다 — 맡기면 같은 값이 기계마다 `1.000,5`·`1,000.5`
// 로 갈린다(#282 의 날짜판과 같은 결함).
//
// 결과 문자열로는 못 잡는다: ko-KR 과 CI 기본 로케일(en-US)의 표기가 이 값들에서 같아, 로케일을
// 안 정해도 초록이 된다. 그래서 **무엇을 넘겼는가**를 잡는다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { formatNumber } from "@/utils/common/formatters/number";

const RealNumberFormat = Intl.NumberFormat;

/** `Intl.NumberFormat` 이 받은 로케일 인자를 모은다. */
function recordLocales(): string[] {
  const seen: string[] = [];
  // `new` 로 불리므로 생성 가능한 함수여야 한다 — 화살표 함수는 생성자가 될 수 없다.
  function Recording(locale?: unknown, options?: unknown) {
    seen.push(locale === undefined ? "<브라우저 기본>" : String(locale));
    return new RealNumberFormat(locale as string | undefined, options as Intl.NumberFormatOptions);
  }
  vi.spyOn(Intl, "NumberFormat").mockImplementation(Recording as unknown as typeof Intl.NumberFormat);
  return seen;
}

afterEach(() => vi.restoreAllMocks());

describe("formatNumber", () => {
  it.each(["number", "currency", "percent", "decimal"] as const)("%s 표기의 로케일을 못 박는다", (type) => {
    const seen = recordLocales();

    formatNumber(1234.5, type);

    expect(seen).toEqual(["ko-KR"]);
  });

  it("숫자가 아닌 것은 빈 문자열이다", () => {
    expect(formatNumber(null)).toBe("");
    expect(formatNumber("숫자아님")).toBe("");
  });
});
