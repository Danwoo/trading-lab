/**
 * 동적 라우트 세그먼트([xxx])의 안전선 — **탈출만 막는다, 식별자 폭은 줄이지 않는다.**
 *
 * `app/api/external/*` 라우트는 이 값을 그대로 백엔드 URL 템플릿에 꽂는다
 * (`proxyApiRequest`, `${BACKEND_URL}/${params.portfolio_id}/holding` 류). 그 조립 지점은
 * `encodeURIComponent` 로 값을 이스케이프하지만, **그것만으로는 세그먼트 경계를 보장하지 못한다**
 * (정정 — 4차 교차 리뷰 실측, PR #337). `encodeURIComponent("core/holding")` 는 `core%2Fholding`
 * 을 만들고, 이 문자열은 Next 라우트 매칭까지는 한 세그먼트로 남는다. 그런데 실제 백엔드
 * (FastAPI/Starlette)는 **라우트 매칭 전에 요청 경로를 퍼센트 디코딩**하므로, 와이어에 실린
 * `%2F` 는 그쪽에서 다시 `/` 로 풀려 `/portfolio/core/holding` 처럼 **다른 라우트에 매치된다** —
 * `%2F`·`%2f`·`%23`(`#`) 등 인코딩된 구분자는 "opaque 바이트열"이 아니라 **수신자가 디코딩하면
 * 그대로 살아나는 구분자**다. 그래서 세그먼트 경계는 인코딩이 아니라 **값 자체에 원문 `/` 가
 * 없다는 것**으로 지켜야 한다 — 아래 `isSafeSegmentValue` 가 이 값을 명시적으로 거부한다.
 *
 * 원문 `/` 를 막아도 여전히 남는 것은 **`.`(하나) 와 `..`(둘) 이 세그먼트 전체인 경우**뿐이다 —
 * 이 두 값은 인코딩해도 예약되지 않은 문자(unreserved, RFC 3986)라 그대로 남고, URL 정규화
 * (`remove_dot_segments`)가 "현재/상위 디렉터리"로 특별 취급해 접어버린다(`%2e` 단일 인코딩만으로도
 * 성립 — 1차 교차 리뷰가 재현). 부분 문자열로 포함된 점(`BRK.B`·`a..b`)은 세그먼트 "전체"가 아니므로
 * 이 정규화 대상이 아니다 — 여기서 막을 이유가 없다.
 *
 * ## 왜 문자 종류를 넓게 열어두면서 `/` 와 이 두 값만 막나 (4차 재작업 — 교차 리뷰가 재현)
 *
 * 1차는 denylist(`/`·".." 리터럴만) 였다가 `%2e`·`PF1%3F`·`%252e%252e` 에 뚫렸고, 2차는 그 반작용으로
 * allowlist(영숫자·`-`·`_`·라벨 사이 단일 점)로 좁혔다가 이번엔 **이 앱 자신의 생성 계약보다 좁아져서**
 * 정상 값이 400 이 됐다 — `portfolio_id`/`ticker`/`scheduler_id` 는 길이만 제한(`StrRange`),
 * `code`/`author_id`/`menu_id` 는 공백만 금지(`NO_WHITESPACE`), 이메일 파라미터는 `z.email()` 이
 * 정하는 폭이 있는데, 그 어느 것도 "영숫자만" 이 아니다. 한글 포트폴리오명("성장주")·한글 코드값
 * ("남")처럼 이 레포(한국어 제품)에서 흔한 값이 그 좁은 규칙에 걸렸다. 3차는 문자 종류를 전혀
 * 안 보는 대신 `encodeURIComponent` 가 구분자를 전부 막아준다고 가정했는데, 그 전제가 위처럼
 * 백엔드 디코딩 순서 때문에 거짓이었다(4차 재현, `/` 만은 뚫림).
 *
 * 그래서 "허용할 문자 집합"을 정의하는 방식은 계속 버려둔다 — 생성 계약이 바뀔 때마다 이 파일도
 * 따라가야 하는 동기화 문제가 반복된다. 대신 **탈출에 실제로 쓰이는 값(원문 `/`, 그리고 세그먼트
 * 전체가 `.`·`..`인 경우)만 배타적으로 막는다.** 생성 계약이 앞으로 얼마나 넓어지든(이모지·기호 등)
 * 이 규칙은 여전히 안전하다 — 세그먼트 구분자로 쓰일 수 있는 문자는 오직 `/` 뿐이고, 그 문자만
 * 원천에서 차단하면 인코딩 겹수·유사문자 여부와 무관하게 경계가 지켜진다.
 *
 * **정밀화 — 이 경계를 지키는 주체가 항상 이 가드인 것은 아니다(5차 교차 리뷰, 프로덕션
 * `nginx.conf` 를 그대로 마운트한 실측).** 이 문단이 말하는 "지켜진다"는 **이 값이 Next.js 라우트
 * 핸들러까지 그대로 도달했을 때** 이 가드가 최종 방어선이라는 뜻이다. 이 레포의 배포 토폴로지에는
 * 앞단에 nginx 가 있고(`platform/nginx/config/nginx.conf`), nginx 는 `proxy_pass` 이전에 `%2F`
 * 를 실제 `/` 로 풀고 경로를 정규화한다 — 즉 nginx 뒤에서는 B1 페이로드가 애초에 이 가드가 보는
 * 한 세그먼트 값으로 도착하지 않고, nginx 가 이미 다른(클라이언트가 평문으로도 직접 부를 수 있는)
 * 라우트로 해석해 넘긴다. 그 경로에서는 **경계를 지키는 주체가 이 가드가 아니라 nginx** 다. 이
 * 가드는 ① nginx 를 거치지 않는 직접 접근(로컬 개발, 오배포, 향후 토폴로지 변경)과 ② nginx 구성이
 * 달라져도 무너지지 않는 심층 방어를 위해 여전히 필요하지만, "nginx 유무와 무관하게 경계가
 * 지켜진다"는 뜻은 아니다.
 *
 * ## email 전용 규칙을 없앤 이유
 *
 * 2차는 `key === "email"` 로, 3차 직전 수정은 라우트 명시 선언(`emailParams`)으로 이메일 값에 별도
 * 허용집합(`@` 포함)을 열어줬다. 그런데 이메일이 꽂히는 라우트(`adminuser/[email]`,
 * `author/[author_id]/user/[user_id]`)는 전부 **Prisma 직접 라우트라 URL 조립 자체가 없다** —
 * 애초에 이 가드가 막아야 할 위협(경로 탈출)이 없는 자리다. 값 형태·key 이름으로 판정을 나누는
 * 매 단계가 "그 판정이 틀리면 정상 값이 막힌다"는 같은 함정을 반복해서 냈으므로(F1·F2 모두 이
 * 클래스), 이제 이메일이든 아니든 **같은 값들(빈 문자열·원문 `/`·점 세그먼트)만** 본다. 생성 계약(`z.email()`)
 * 이 허용하는 `_admin@example.com`·`o'brien@example.com` 도 그대로 통과한다.
 *
 * 이 파일은 의도적으로 다른 모듈을 import 하지 않는다 — `normalizeEmail.ts` 와 같은 이유
 * (그 파일 상단 주석 참조): 순수 로직만 있어야 vitest 가 실 환경변수 없이 가볍게 테스트한다.
 */

// 세그먼트 전체가 "." 또는 ".." 인 경우만 매치 — URL 정규화가 특별 취급하는 정확히 그 두 값.
const DOT_SEGMENT = /^\.{1,2}$/;

function isSafeSegmentValue(value: string): boolean {
  if (value.length === 0) return false;
  // 원문(디코딩된) '/' — 유일한 세그먼트 구분자. 백엔드(Starlette)가 라우트 매칭 전에 퍼센트
  // 디코딩하므로 `encodeURIComponent` 로 만든 `%2F` 도 여기서는 못 막는다(위 파일 상단 주석,
  // PR #337 B1). 값 자체에 이 문자가 없다는 것만이 경계를 보장한다.
  if (value.includes("/")) return false;
  return !DOT_SEGMENT.test(value);
}

/**
 * 허용 집합 밖의 첫 세그먼트 key 를 돌려준다. 전부 안전하면 null.
 *
 * 문자열이 아닌 값(배열·숫자 등)은 검사하지 않고 통과시킨다 — 오늘 `withAuth` 를 타는 라우트 중
 * catch-all(`[...slug]`, params 값이 배열) 은 0건이라 실 구멍은 없다(전 라우트 스캔 확인,
 * `app/api/auth/[...all]` 유일한 catch-all 은 better-auth 핸들러라 `withAuth` 를 타지 않는다).
 * 이 전제가 깨지면(향후 `app/api/external/**` 에 catch-all 라우트 추가) 이 함수는 그 세그먼트를
 * 조용히 건너뛴다 — 배열 param 이 생기면 원소별 검사를 추가할 것.
 */
export function findUnsafePathSegment(params: Record<string, unknown>): string | null {
  for (const [key, value] of Object.entries(params)) {
    if (typeof value !== "string") continue;
    if (!isSafeSegmentValue(value)) return key;
  }
  return null;
}
