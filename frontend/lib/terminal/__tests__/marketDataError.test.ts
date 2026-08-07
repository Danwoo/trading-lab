import { describe, expect, it } from "vitest";
import { classifyMarketDataError } from "@/lib/terminal/marketDataError";
import { EndpointNotReadyError } from "@/lib/terminal/errors";

describe("classifyMarketDataError", () => {
  it("EndpointNotReadyError 는 placeholder 로 흡수한다", () => {
    const outcome = classifyMarketDataError(new EndpointNotReadyError("market.candles"));
    expect(outcome).toEqual({ kind: "placeholder" });
  });

  it("다른 Error 는 흡수하지 않고 error 로 낸다", () => {
    const original = new Error("네트워크 끊김");
    const outcome = classifyMarketDataError(original);
    expect(outcome.kind).toBe("error");
    expect(outcome.kind === "error" && outcome.error).toBe(original);
  });

  it("Error 가 아닌 값도 Error 로 감싸 흡수하지 않는다", () => {
    const outcome = classifyMarketDataError("문자열로 던져진 예외");
    expect(outcome.kind).toBe("error");
    expect(outcome.kind === "error" && outcome.error).toBeInstanceOf(Error);
  });
});
