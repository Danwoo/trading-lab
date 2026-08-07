import { describe, expect, it } from "vitest";

import { findUnsafePathSegment } from "@/lib/auth/safePathSegment";

// `withAuth` 가 모든 동적 라우트 세그먼트에 통과시키는 안전선. 네 차례 교차 리뷰가 실결함을
// 재현했다:
//   1차(denylist `/[/\\]|\.\./`) → allowlist(영숫자+"-"+"_"+단일 점)로 재작성 — `%2e`(단일 점)·
//     `PF1%3F`(물음표)·`%252e%252e`(이중 인코딩)이 뚫렸었다.
//   2차(allowlist 가 key==="email" 일 때만 "@" 허용) → `author/[author_id]/user/[user_id]` 의
//     `user_id` 는 이름과 달리 **실제 값이 이메일**이라 정상 값이 400 으로 막히는 결함이 났다.
//   3차(라우트 명시 선언 `emailParams` 로 이메일 값에 별도 허용집합) → 여전히 "영숫자만" 규칙이
//     생성 계약(포트폴리오·코드·권한·메뉴는 한글 허용)보다 좁아 **정상 생성된 레코드가 조회·수정·
//     삭제 400** 이 되는 결함이 났다(F1). 값 형태로 판정을 나누는 시도 자체가 매번 같은 함정
//     ("그 판정이 틀리면 정상 값이 막힌다")을 반복했다.
//   4차(문자 종류를 전혀 안 보고 "."·".."·빈 문자열만 차단, 구분자는 조립 지점의
//     `encodeURIComponent` 가 지킨다고 가정) → **그 전제가 거짓이었다(B1, PR #337 4차 교차
//     리뷰).** 백엔드(Starlette)가 라우트 매칭 전에 퍼센트 디코딩을 하므로 `%2F` 도 결국 `/` 로
//     풀려 세그먼트 경계를 넘는다 — `core%2Fholding` 이 `/portfolio/core/holding` 에 매치되고,
//     실제로 DELETE 로 다른 리소스(보유종목)를 지우는 것까지 재현됐다.
//
// 그래서 5차는 4차의 넓은 정책(문자 종류를 안 본다)은 유지하되, **원문(디코딩된) `/` 를 명시적으로
// 차단**한다 — 세그먼트 구분자가 될 수 있는 문자는 이것 하나뿐이고, 인코딩 겹수·수신자의 디코딩
// 시점과 무관하게 값 자체에 없으면 경계를 넘을 수 없다.
describe("findUnsafePathSegment — 탈출 값만 차단, 폭은 생성 계약과 같거나 넓게", () => {
  describe("1~4차 리뷰가 재현한 결함 케이스 — 여전히 올바른 판정인지", () => {
    it("1. 정상 값은 통과 (research_doc_id 류)", () => {
      expect(findUnsafePathSegment({ research_doc_id: "1" })).toBeNull();
    });

    it("2. ../../admin — 세그먼트 전체는 '..' 가 아니지만 원문 '/' 를 포함해 5차부터 차단(B1)", () => {
      expect(findUnsafePathSegment({ portfolio_id: "../../admin" })).toBe("portfolio_id");
    });

    it("3. %2e(단일 점) → 디코딩된 '.' — 세그먼트 전체가 '.' 라 차단", () => {
      expect(findUnsafePathSegment({ portfolio_id: "." })).toBe("portfolio_id");
    });

    it("4. PF1%3F(물음표) → 디코딩된 'PF1?' — '.'도 '..'도 아니라 통과(구분은 encodeURIComponent 가 처리)", () => {
      expect(findUnsafePathSegment({ portfolio_id: "PF1?" })).toBeNull();
    });

    it("5. %252e%252e(이중 인코딩) → Next 1회 디코딩 후 '%2e%2e' — 그대로도 '..'가 아니라 통과", () => {
      expect(findUnsafePathSegment({ portfolio_id: "%2e%2e" })).toBeNull();
    });

    it("6. .. 자체(세그먼트 전체) — 차단(remove_dot_segments 가 특별 취급하는 그 값)", () => {
      expect(findUnsafePathSegment({ portfolio_id: ".." })).toBe("portfolio_id");
    });
  });

  // F1 재현 — 이 앱의 생성 계약(schemas/**)이 실제로 허용하는 값들. 전부 통과해야 한다.
  describe("F1 재현 — 생성 계약이 허용하는 값이 가드도 통과하는지", () => {
    it.each([
      ["portfolio_id", "성장주", "한글 포트폴리오명 — schemas/portfolio.ts StrRange(1,20), 길이만 제한"],
      ["portfolio_id", "pf(1)", "괄호 — 길이만 제한"],
      ["ticker", "삼성전자", "한글 종목명 입력 — StrRange(1,20)"],
      ["ticker", "BRK.B", "클래스 주식 표기 — 라벨 사이 단일 점"],
      ["scheduler_id", "일간수집", "한글 스케줄러명 — StrRange(1,20)"],
      ["code", "남", "한글 코드값 — NO_WHITESPACE(공백 외 전부)"],
      ["group_code", "성별", "한글 코드그룹값 — NO_WHITESPACE"],
      ["author_id", "관리자", "한글 권한명 — NO_WHITESPACE"],
      ["menu_id", "메뉴1", "한글 메뉴명 — NO_WHITESPACE"],
    ])("%s = %s  (%s)", (key, value) => {
      expect(findUnsafePathSegment({ [key]: value })).toBeNull();
    });
  });

  // F2 재현 — z.email() 이 허용하는데 이전 EMAIL_PATH_SEGMENT 는 거부했던 값들.
  describe("F2 재현 — z.email() 이 허용하는 이메일이 가드도 통과하는지 (email/user_id 구분 없이)", () => {
    it.each([
      ["email", "operator@example.com", "기본"],
      ["user_id", "operator@example.com", "author/[author_id]/user/[user_id] — 이름은 일반 식별자 같지만 값은 이메일"],
      ["email", "_admin@example.com", "z.email() 이 허용 — local-part 선행 '_' "],
      ["email", "o'brien@example.com", "z.email() 이 허용 — 어퍼스트로피"],
      ["email", "user_@example.com", "z.email() 이 허용 — local-part 후행 '_' "],
      ["email", "user+tag@example.com", "plus-tag — 흔한 이메일 별칭 관례"],
    ])("%s = %s  (%s)", (key, value) => {
      expect(findUnsafePathSegment({ [key]: value })).toBeNull();
    });
  });

  describe("여전히 차단해야 하는 것 — 세그먼트 전체가 '.'·'..'·빈 문자열인 경우", () => {
    it.each([
      [".", "단일 점 — 현재 디렉터리"],
      ["..", "이중 점 — 상위 디렉터리"],
    ])("%s (%s) — 차단", (payload) => {
      expect(findUnsafePathSegment({ portfolio_id: payload })).toBe("portfolio_id");
    });

    it("빈 문자열은 차단 (길이 0)", () => {
      expect(findUnsafePathSegment({ portfolio_id: "" })).toBe("portfolio_id");
    });
  });

  describe("부분 문자열의 점은 특별 취급 대상이 아니다 — 차단하지 않는다", () => {
    it.each([
      [".hidden", "선행 점 — 세그먼트 전체가 '.'이 아니므로 통과"],
      ["hidden.", "후행 점 — 통과"],
      ["a..b", "중간 연속 점 — 통과"],
      ["a.b.c", "라벨 다중 — 통과"],
    ])("%s (%s)", (payload) => {
      expect(findUnsafePathSegment({ portfolio_id: payload })).toBeNull();
    });
  });

  // 원문 '/' 는 아래 별도 describe 에서 차단을 검증한다(B1) — 나머지는 그 문자를 만들지 않는
  // 한 encodeURIComponent 조립이 지켜주므로 여기서는 통과가 맞다.
  describe("구분자·인코딩 류 — 값 자체에 원문 '/' 가 없는 한 encodeURIComponent 조립이 지키는 값들", () => {
    it.each([
      ["#", "fragment 문자"],
      [";", "세미콜론"],
      ["a\\b", "백슬래시"],
      ["％％etc", "유니코드 전각 퍼센트(U+FF05)"],
      ["／／etc", "유니코드 전각 슬래시(U+FF0F) — ASCII '/'과 다른 문자라 차단 대상 아님"],
      ["a。。b", "유니코드 표의 마침표(U+3002)로 흉내낸 이중 점 — ASCII '.'과 다른 문자라 특별 취급 아님"],
      ["a b", "공백"],
      ["%00", "널바이트가 디코딩 안 되고 리터럴 %00으로 남는 경우"],
    ])("%s (%s) — 가드 통과(조립 지점의 encodeURIComponent 가 구분자를 escape)", (payload) => {
      expect(findUnsafePathSegment({ portfolio_id: payload })).toBeNull();
    });
  });

  // B1 — PR #337 4차 교차 리뷰 재현. 아래 값들은 공격자가 보내는 원문 URL 이 아니라, Next 라우터가
  // 그 URL 을 **디코딩한 뒤** 이 함수에 실제로 전달하는 params 값이다(withAuth.ts:87 `props.params`).
  // 즉 `GET core%2Fholding` 요청은 이 함수에 `"core/holding"` 으로 도착한다 — 여기서 막지 않으면
  // encodeURIComponent 가 그 값을 %2F 로 되돌려 백엔드에 보내고, Starlette 이 그걸 다시 '/'로 풀어
  // 다른 라우트(보유종목 삭제 등)에 매치시킨다(파일 상단 주석·PR 코멘트 재현 참고).
  describe("B1 — 원문 '/' 를 포함한 디코딩 값은 차단한다 (encodeURIComponent 단독 방어의 실패를 여기서 막음)", () => {
    it.each([
      ["core/holding", "리뷰어 재현 C — GET, portfolio 단건 라우트가 holding 목록에 매치되던 값"],
      ["zzrev337/holding/삼성전자", "리뷰어 재현 — DELETE, 포트폴리오 삭제가 보유종목 삭제로 착지하던 값"],
      ["/admin", "리뷰어 재현 #10 — 선행 슬래시"],
      ["a/b", "가장 단순한 형태"],
    ])("%s (%s) — 차단", (payload) => {
      expect(findUnsafePathSegment({ portfolio_id: payload })).toBe("portfolio_id");
    });
  });

  describe("여러 key 동시 검사", () => {
    it("문자열이 아닌 값은 검사 대상에서 제외", () => {
      expect(findUnsafePathSegment({ workspace_id: 5 as unknown as string })).toBeNull();
    });

    it("여러 key 중 안전하지 않은 것 하나라도 있으면 그 key 를 돌려준다", () => {
      expect(findUnsafePathSegment({ portfolio_id: "PF001", ticker: ".." })).toBe("ticker");
    });

    it("빈 params 는 안전하다", () => {
      expect(findUnsafePathSegment({})).toBeNull();
    });
  });
});
