// 칸 클릭 → 갱신 시간 한 줄 (F12) — 예산을 넘겼을 때 숫자만 적고 끝나지 않는다.
import { describe, expect, it } from "vitest";

import { REPORT_BUDGET_MS, reportTimingLine } from "@/lib/bench/reportTiming";

describe("reportTimingLine", () => {
  it("예산 안이면 시간과 예산만 적는다", () => {
    expect(reportTimingLine(83)).toBe("칸 클릭 → 갱신 83ms — 예산 500ms (스펙 §5)");
  });

  it("캐시(0ms)는 그렇게 말한다", () => {
    expect(reportTimingLine(0)).toContain("0ms (캐시)");
  });

  it("예산을 넘기면 무슨 뜻인지·다음엔 어떻게 되는지를 말한다 — 초과를 적기만 하지 않는다", () => {
    const line = reportTimingLine(1287);
    expect(line).toContain("1287ms");
    expect(line).toContain("넘겼습니다");
    expect(line).toContain("다시 누르면 캐시로 바로 뜹니다");
  });

  it("경계값 — 예산과 같으면 넘긴 것이 아니다", () => {
    expect(reportTimingLine(REPORT_BUDGET_MS)).not.toContain("넘겼습니다");
    expect(reportTimingLine(REPORT_BUDGET_MS + 1)).toContain("넘겼습니다");
  });
});
