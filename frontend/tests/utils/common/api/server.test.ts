import { describe, expect, it } from "vitest";

import { proxyApiRequest } from "@/utils/common/api/server";

// #298 — `mode: "external"`(사용자 입력 URL 을 검증 없이 그대로 fetch 하는, 호출자 0명이던 SSRF
// 잠복 표면)을 제거했다. 타입에서는 이미 지워졌지만, 런타임에서도 그 값이 다시 조용히 살아나지
// 않는지(예: 어딘가 `as any` 로 우회해 재도입) 잠그는 회귀 테스트 — exhaustive switch 의 default
// 분기가 알 수 없는 mode 를 던지는 동작에 기댄다.
describe("proxyApiRequest — 제거된 external mode 가 되살아나지 않는다", () => {
  it("'external' 모드는 더 이상 유효하지 않다 — 알 수 없는 mode 로 취급되어 던진다", async () => {
    await expect(proxyApiRequest("http://localhost:8000/whatever", {}, "external" as any)).rejects.toThrow(
      /Unknown proxy mode/,
    );
  });
});
