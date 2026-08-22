/**
 * 셸이 아는 경로 상수.
 *
 * 「로그인 후 착지」와 「권한 없음 튕김」은 예전에 같은 값(`/`)으로 읽혔다 — 로그인 화면이
 * 곧 홈이었기 때문이다. 실험대가 홈이 되면서 둘은 다른 것이 됐다(#73 S2, 화면 결정 §20.2):
 * 착지는 **제품 안**으로 들어가는 것이고, 튕김은 **제품 밖**으로 나가는 것이다.
 * 두 상수를 갈라 두지 않으면 한쪽을 바꿀 때 다른 쪽이 조용히 따라간다.
 */

/** 실험대 — 제품의 홈(화면 결정 §20.2 「㉮ 실험대가 홈」). */
export const BENCH_PATH = "/bench";

/** 시세 — 전체 폭 목적지(§20.3). 기본 진입점은 아니다. */
export const MARKET_PATH = "/terminal";

/**
 * 관리 화면 — MDI 탭 섀시의 진입점(§20.2 「화면 전환은 「시세」와 `/admin` 둘뿐」).
 *
 * 이 경로에 페이지가 실재해야 레일의 「설정」이 열린다 — `app/admin/layout.tsx` 만 있고
 * `page.tsx` 가 없으면 `/admin/*` 는 열려도 `/admin` 자체는 404 다.
 */
export const ADMIN_PATH = "/admin";

/**
 * 설정 — 데이터 소스 키처럼 **이 설치에 매인 값**을 다루는 자리 (#225).
 *
 * `/admin` 아래 두지 않는 이유: 그쪽 화면은 `tn_menu` 행으로 열리고 그 행은 시드에만 있어,
 * **이미 설치한 사람은 재시드(계정 초기화) 전까지 못 본다.** 키 설정은 새 설치가 가장 먼저
 * 필요한 것이라 메뉴 게이트 뒤에 두면 필요한 사람에게 안 닿는다 (리드 결정 2026-08-19).
 */
export const SETTINGS_PATH = "/settings";

/**
 * 로그인 후 착지점.
 *
 * **메뉴 게이트가 fail-closed 라 무조건 여기로 보내면 안 된다** — 이 경로가 사용자의
 * `tn_menu` 권한에 없으면 제품 셸이 곧바로 `UNAUTHORIZED_FALLBACK_PATH` 로 되돌려
 * 로그인 화면과 왕복한다. 그래서 `Login.tsx` 는 네비게이션에 이 경로가 **있을 때만**
 * 여기로 보내고, 없으면 접근 가능한 첫 메뉴로 내려간다.
 */
export const POST_LOGIN_PATH = BENCH_PATH;

/**
 * 권한 없는 경로 접근 시 되돌릴 자리 — 로그인 화면.
 *
 * URL 직접 입력 같은 비정상 흐름에서만 도달한다(정상 사용자는 레일·사이드바를 거친다).
 */
export const UNAUTHORIZED_FALLBACK_PATH = "/";

/**
 * 되돌린 이유를 도착지에 실어 보내는 쿼리 파라미터.
 *
 * `UNAUTHORIZED_FALLBACK_PATH` 는 로그인 화면이라, 사유 없이 도착하면 **로그인이 풀린 것으로
 * 읽힌다.** 세션은 멀쩡한데 로그인하라는 화면을 보는 것이 #333 이 적은 결함이고, 사유를
 * 실어야 도착지가 그것을 부정할 수 있다.
 */
export const RETURN_REASON_PARAM = "reason";

/**
 * 되돌린 사유 — **계정 상태 이야기만 여기 온다.** 「메뉴를 못 읽었다」는 되돌리지 않고
 * 제품 셸 안에서 사유 화면으로 선다 — 못 읽은 것은 로그아웃 상태가 아니다.
 *
 * `session-expired` 는 그 반대편이다: 쿠키는 남았는데 서버가 세션을 거부한(401) 상태라
 * **정말로 로그아웃됐다.** 제품 셸에는 로그아웃 수단이 없어(`signOut` 은 관리 섀시의
 * `Header` 하나뿐이다) 여기서 되돌리지 않으면 나갈 길이 없다.
 */
export type ReturnReason = "forbidden" | "no-menu" | "session-expired";

/** 되돌릴 자리 + 사유. 도착지(로그인 화면)가 이 값을 읽어 왜 왔는지 말한다. */
export const fallbackPathWithReason = (reason: ReturnReason): string =>
  `${UNAUTHORIZED_FALLBACK_PATH}?${RETURN_REASON_PARAM}=${reason}`;
