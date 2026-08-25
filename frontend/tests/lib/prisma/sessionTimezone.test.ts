import { describe, expect, it } from "vitest";

import {
  SESSION_TIMEZONE,
  SessionTimezoneError,
  ensureSessionTimezoneUtc,
  mergeUtcTimezoneOption,
  poolConfigWithUtcTimezone,
} from "@/lib/prisma/sessionTimezone";

/** `$queryRaw\`SHOW timezone\`` 만 흉내내는 최소 대역. */
function clientReporting(timezone: string) {
  return { $queryRaw: async () => [{ TimeZone: timezone }] };
}

describe("mergeUtcTimezoneOption", () => {
  it("빈 옵션에는 timezone 지정만 넣는다", () => {
    expect(mergeUtcTimezoneOption("")).toBe("-c timezone=UTC");
  });

  it("이미 있는 timezone 지정을 UTC 로 갈아끼운다", () => {
    expect(mergeUtcTimezoneOption("-c timezone=Asia/Seoul")).toBe("-c timezone=UTC");
  });

  it("붙여 쓴 -ctimezone= 꼴도 잡는다", () => {
    expect(mergeUtcTimezoneOption("-ctimezone=Asia/Seoul")).toBe("-c timezone=UTC");
  });

  it("timezone 이 아닌 옵션은 순서대로 보존한다", () => {
    expect(mergeUtcTimezoneOption("-c search_path=frontend -c timezone=Asia/Seoul")).toBe(
      "-c search_path=frontend -c timezone=UTC",
    );
  });
});

describe("poolConfigWithUtcTimezone", () => {
  it("URL 에 옵션이 없으면 timezone 만 붙인다", () => {
    const config = poolConfigWithUtcTimezone("postgresql://u@h:5432/db?schema=frontend");
    expect(config.options).toBe("-c timezone=UTC");
    expect(config.connectionString).toContain("schema=frontend");
  });

  it("URL 의 options 를 떼어내 코드가 이기게 한다 — pg 는 URL 쪽을 우선하기 때문", () => {
    const config = poolConfigWithUtcTimezone(
      "postgresql://u@h:5432/db?schema=frontend&options=-c%20timezone%3DAsia%2FSeoul",
    );
    expect(config.options).toBe("-c timezone=UTC");
    expect(config.connectionString).not.toContain("options=");
  });

  it("URL 의 다른 옵션은 코드 쪽 options 로 옮겨 살린다", () => {
    const config = poolConfigWithUtcTimezone(
      "postgresql://u@h:5432/db?options=-c%20search_path%3Dfrontend%20-c%20timezone%3DAsia%2FSeoul",
    );
    expect(config.options).toBe("-c search_path=frontend -c timezone=UTC");
  });
});

describe("ensureSessionTimezoneUtc", () => {
  it("UTC 면 통과한다", async () => {
    await expect(ensureSessionTimezoneUtc(clientReporting(SESSION_TIMEZONE))).resolves.toBeUndefined();
  });

  it("UTC 가 아니면 던진다 — 우회 스위치가 없다", async () => {
    await expect(ensureSessionTimezoneUtc(clientReporting("Asia/Seoul"))).rejects.toBeInstanceOf(SessionTimezoneError);
  });

  it("실제 값을 메시지에 담는다 — 무엇이 왔는지 로그로 알 수 있어야 한다", async () => {
    await expect(ensureSessionTimezoneUtc(clientReporting("Asia/Seoul"))).rejects.toThrow("Asia/Seoul");
  });
});
