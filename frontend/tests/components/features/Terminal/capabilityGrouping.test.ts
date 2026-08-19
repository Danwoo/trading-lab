// #227 — **막힌 소스를 사유로 묶는다.**
//
// 조합은 소스 × 시장 × 데이터종류라 같은 사유가 수십 번 되풀이된다. 실측(로컬 기동, 로그인
// 후 `/api/external/backend/market-capability`)으로 **막힘 46건이 서로 다른 사유 9종**이었고,
// 그 46줄이 그대로 첫 화면을 덮어 제품이 고장 난 것처럼 보였다.
//
// 키가 없어 막힌 것은 사용자가 오늘 풀 수 있는 유일한 것이라 앞에 세운다.
//
// **검증 경계** — 묶는 함수만 본다. 화면 렌더는 보지 않는다.

import { describe, expect, it } from "vitest";
import { groupBlockedByReason } from "@/components/features/Terminal/IngestConsole";
import { CREDENTIAL_MISSING_CODE } from "@/lib/terminal/marketDataError";
import type { MarketCapability } from "@/services/terminal/marketService";

function blocked(source: string, market: string, dataKind: string, reason: string, code: string | null = null) {
  return { source, market, dataKind, available: false, reason, code } satisfies MarketCapability;
}

const NO_KEY = "Alpaca API 키가 등록되지 않았습니다";
const NO_PRICE = "SEC 는 가격 데이터를 제공하지 않습니다";

describe("#227 막힌 소스를 사유로 묶는다", () => {
  it("같은 사유는 한 줄로 접히고 대상이 모인다", () => {
    const groups = groupBlockedByReason([
      blocked("alpaca", "NASDAQ", "daily_bar", NO_KEY, CREDENTIAL_MISSING_CODE),
      blocked("alpaca", "NYSE", "daily_bar", NO_KEY, CREDENTIAL_MISSING_CODE),
      blocked("alpaca", "AMEX", "quote", NO_KEY, CREDENTIAL_MISSING_CODE),
    ]);

    expect(groups).toHaveLength(1);
    expect(groups[0].targets).toHaveLength(3);
    expect(groups[0].targets[0]).toBe("alpaca · NASDAQ · 일봉");
  });

  it("키를 넣으면 풀리는 것이 앞에 선다 — 건수가 적어도", () => {
    const groups = groupBlockedByReason([
      blocked("sec", "NASDAQ", "daily_bar", NO_PRICE),
      blocked("sec", "NYSE", "daily_bar", NO_PRICE),
      blocked("sec", "AMEX", "daily_bar", NO_PRICE),
      blocked("alpaca", "NASDAQ", "quote", NO_KEY, CREDENTIAL_MISSING_CODE),
    ]);

    expect(groups[0].reason).toBe(NO_KEY);
    expect(groups[0].fixable).toBe(true);
    expect(groups[1].fixable).toBe(false);
  });

  it("같은 고칠 수 있음끼리는 건수가 많은 쪽이 앞에 선다", () => {
    const groups = groupBlockedByReason([
      blocked("a", "M", "quote", "적게 막힘"),
      blocked("b", "M", "quote", "많이 막힘"),
      blocked("b", "N", "quote", "많이 막힘"),
    ]);

    expect(groups[0].reason).toBe("많이 막힘");
  });

  it("사유가 없어도 버리지 않는다 — 빈 화면보다 「사유 없음」이 낫다", () => {
    const groups = groupBlockedByReason([{ ...blocked("x", "M", "quote", ""), reason: null }]);

    expect(groups[0].reason).toBe("사유가 기록되지 않았습니다");
  });

  it("막힌 자리의 종류도 사람 말로 적는다 — 같은 패널 위쪽과 같은 어휘로", () => {
    const groups = groupBlockedByReason([
      blocked("alpaca", "NASDAQ", "daily_bar", NO_KEY, CREDENTIAL_MISSING_CODE),
      blocked("alpaca", "NASDAQ", "instrument_master", NO_KEY, CREDENTIAL_MISSING_CODE),
    ]);

    expect(groups[0].targets).toEqual(["alpaca · NASDAQ · 일봉", "alpaca · NASDAQ · 종목목록"]);
  });

  it("모르는 종류는 버리지 않고 원문으로 남긴다", () => {
    const groups = groupBlockedByReason([blocked("x", "M", "future_kind", "막힘")]);

    expect(groups[0].targets).toEqual(["x · M · future_kind"]);
  });

  it("막힌 것이 없으면 묶을 것도 없다", () => {
    expect(groupBlockedByReason([])).toEqual([]);
  });
});
