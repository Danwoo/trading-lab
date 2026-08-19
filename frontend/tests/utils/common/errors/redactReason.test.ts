// @vitest-environment node
//
// 실패 사유가 **화면에 나가기 직전** URL·쿼리를 잃는가 (#274).
//
// 저장 시점 방어(#251)는 소급되지 않는다 — 이미 저장된 행이 실제로 화면에 URL 을 내보내고
// 있었다. data.go.kr 은 인증키를 쿼리로 받으므로, 그 자리에 키가 있을 수 있다.
import { describe, expect, it } from "vitest";

import { redactReason } from "@/utils/common/errors/redactReason";

const KEY = "dummy-service-key-CANARY-a+b/c==";

describe("실패 사유는 화면에 URL 을 내보내지 않는다", () => {
  it("실제로 저장돼 있던 사유에서 주소가 걷힌다", () => {
    const stored =
      "HTTPStatusError: Client error '403 Forbidden' for url 'https://openapi.tossinvest.com/oauth2/token' " +
      "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403";

    const shown = redactReason(stored);

    expect(shown).not.toContain("://");
    expect(shown).not.toContain("tossinvest.com");
    // 사유 자체는 남는다 — 통째로 지우면 원인이 사라진다
    expect(shown).toContain("403 Forbidden");
    expect(shown).toContain("[주소 생략]");
  });

  it("쿼리에 실린 키가 걷힌다 — data.go.kr 은 인증키를 쿼리로 받는다", () => {
    const stored = `요청 실패: https://apis.data.go.kr/service?serviceKey=${KEY}&type=json`;

    const shown = redactReason(stored);

    expect(shown).not.toContain(KEY);
    expect(shown).not.toContain("://");
  });

  it("URL 없이 쿼리만 옮겨 적힌 경우도 걷힌다", () => {
    expect(redactReason(`파라미터 ?serviceKey=${KEY} 가 거절됐습니다`)).not.toContain(KEY);
  });

  it("우리가 쓴 한국어 사유는 그대로 남는다", () => {
    const ours =
      "toss: 소스가 이 서버의 접근을 막았습니다 (HTTP 403). 발급처 앱 설정에서 이 서버의 IP 를 허용 목록에 등록하세요.";

    expect(redactReason(ours)).toBe(ours);
  });

  it("빈 사유는 null 이다 — 「사유 없음」과 「빈 문자열」을 뭉개지 않는다", () => {
    expect(redactReason(null)).toBeNull();
    expect(redactReason("")).toBeNull();
    expect(redactReason("   ")).toBeNull();
  });
});
