// #400 — 리포트 머리가 요청 구간을 적으면서, 엔진이 실제로 훑은 구간은 안 적었다.
//
// 실측: 3년(`2023-08-26 ~ 2026-08-25`)을 요청한 실행이 적재본 때문에 242봉(361일)만 훑았는데
// 머리줄은 3년을 말했다. 「3년을 검증했다」로 읽으면 표본 길이를 세 배로 착각한다.
import { describe, expect, it } from "vitest";

import { coversRequest, scannedRange } from "@/lib/bench/scannedRange";
import type { EquityPointOut } from "@/schemas/backtest/backtest";

const point = (dt: string): EquityPointOut => ({
  dt,
  equity: 1_000_000,
  cash: 0,
  position_count: 0,
  gross_exposure: 0,
});

describe("실제로 훑은 구간", () => {
  it("자산곡선의 첫 날·마지막 날·점 수를 읽는다", () => {
    expect(scannedRange([point("2025-08-25"), point("2026-08-20"), point("2026-08-21")])).toEqual({
      from: "2025-08-25",
      to: "2026-08-21",
      bars: 3,
    });
  });

  it("순서가 뒤섞여 와도 양 끝을 맞게 읽는다", () => {
    expect(scannedRange([point("2026-08-21"), point("2025-08-25")])?.from).toBe("2025-08-25");
  });

  it("`dt` 가 시각까지 실어 와도 날짜만 읽는다", () => {
    expect(scannedRange([point("2025-08-25T00:00:00+09:00")])?.from).toBe("2025-08-25");
  });

  it("곡선이 비면 지어내지 않는다", () => {
    expect(scannedRange([])).toBeNull();
  });

  it("점 하나면 시작과 끝이 같은 하루다", () => {
    expect(scannedRange([point("2026-08-21")])).toEqual({ from: "2026-08-21", to: "2026-08-21", bars: 1 });
  });
});

describe("요청 구간을 다 훑었나", () => {
  const scanned = { from: "2025-08-25", to: "2026-08-21", bars: 242 };

  it("적재본이 짧으면 거짓이다 — 이 실행이 바로 그 경우다", () => {
    expect(coversRequest(scanned, "2023-08-26", "2026-08-25")).toBe(false);
  });

  it("두 끝이 같을 때만 참이다", () => {
    expect(coversRequest(scanned, "2025-08-25", "2026-08-21")).toBe(true);
    expect(coversRequest(scanned, "2025-08-25", "2026-08-25")).toBe(false);
    expect(coversRequest(scanned, "2023-08-26", "2026-08-21")).toBe(false);
  });

  it("훑은 것이 없으면 덮었다고 하지 않는다", () => {
    expect(coversRequest(null, "2023-08-26", "2026-08-25")).toBe(false);
  });
});
