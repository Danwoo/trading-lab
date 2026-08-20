// utils/common/errors/redactReason.ts
//
// 실패 사유를 **화면에 그리기 직전에** 한 번 더 거른다.
//
// 저장 시점 방어(#251)는 「앞으로」만 덮는다 — 이미 저장된 행·다른 경로로 들어온 행·다른
// 서비스가 쓴 행은 그대로 나간다. 실제로 그런 행이 DB 에 있었고, 화면에 이렇게 보였다:
//
//     HTTPStatusError: Client error '403 Forbidden' for url 'https://openapi.tossinvest.com/oauth2/token'
//
// **data.go.kr 은 인증키를 쿼리 파라미터로 받는다.** 그 소스의 실패였다면 그 자리에 키가 있다.
// 화면은 어디서 왔든 그리는 자리라, 마지막 관문이 여기다.

/** `scheme://…` 토막. 공백·따옴표·닫는 괄호에서 끊는다 — 뒤 문장을 삼키지 않게. */
const URL_LIKE = /[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^\s'"()<>]+/g;

/** URL 없이 `?a=b&c=d` 만 있는 토막 (쿼리만 옮겨 적힌 경우). */
const BARE_QUERY = /\?[A-Za-z0-9_%+.-]+=[^\s'"()<>]*/g;

/**
 * `?` 없이 `키=값` 만 옮겨 적힌 모양 — `serviceKey=…`·`api_key=…`·`access_token=…`.
 *
 * 새 행은 저장 시점 가림이 덮지만, **이 관문이 겨냥하는 옛 행에는 여기뿐이다.** 키처럼 보이는
 * 이름에 한정한다 — 아무 `a=b` 나 지우면 사유 문장이 부서진다.
 */
//: 스킴 낱말은 `Bearer` 하나가 아니다 — `Basic`·`Digest` 도 같은 자리에 온다. 낱말을 고정하면
//: 그 낱말이 아닐 때 값 클래스가 스킴에서 끊겨 매치 자체가 실패한다(`Basic <base64>` 가 그대로 나갔다).
const KEY_ASSIGNMENT =
  /\b(?:authorization|[A-Za-z0-9_-]*(?:key|token|secret|password|passwd|pwd))['"]?\s*[=:]\s*['"]?(?:[A-Za-z]+\s+)?[A-Za-z0-9_%+./=-]{6,}['"]?/gi;

/**
 * 사유에서 URL·쿼리를 걷는다. **사유 자체는 남긴다** — 통째로 지우면 원인이 사라진다.
 *
 * 지운 자리에 표식을 남기는 이유: 「원래 없었다」와 「우리가 지웠다」를 읽는 사람이 구분해야
 * 한다. 지운 사실을 감추면 사유가 왜 어색한지 알 수 없다.
 */
export function redactReason(reason: string | null | undefined): string | null {
  if (!reason) return null;
  const cleaned = reason
    .replace(URL_LIKE, "[주소 생략]")
    .replace(BARE_QUERY, "[질의 생략]")
    .replace(KEY_ASSIGNMENT, "[값 생략]");
  return cleaned.trim() || null;
}
