/**
 * 시스템관리자 권한 ID
 *
 * 일반 권한과의 차이:
 * - 네비게이션: 메뉴 권한 배정 없이 모든 메뉴에 접근 가능
 * - 권한관리: 시스템관리자 권한은 목록에서 숨김 처리되어 비시스템관리자는 조회/수정/사용자 배정 불가
 * - 사용자관리: 시스템관리자 소속 사용자는 시스템관리자만 수정/삭제 가능
 */
export const SYS_ADMIN_AUTHOR_ID = "admin";

/** 일반관리자 권한 ID — 워크스페이스별 사용자 관리 권한 */
export const GENERAL_ADMIN_AUTHOR_ID = "operator";

/** 일반사용자 권한 ID — 도메인 매핑된 가입자에게 자동 부여되는 디폴트 권한 */
export const DEFAULT_USER_AUTHOR_ID = "user";

/** 여러 권한 보유 시 세션 대표 권한 선택 우선순위 (숫자 정렬 비의존 — 자유 권한은 후순위 fallback) */
export const AUTHOR_PRIORITY = [SYS_ADMIN_AUTHOR_ID, GENERAL_ADMIN_AUTHOR_ID, DEFAULT_USER_AUTHOR_ID];

/** 삭제 불가 권한 — admin/operator/user 시스템 권한은 백엔드가 의존하므로 삭제 차단 (버튼도 미노출) */
export const PROTECTED_AUTHOR_IDS = [SYS_ADMIN_AUTHOR_ID, GENERAL_ADMIN_AUTHOR_ID, DEFAULT_USER_AUTHOR_ID];

/** 삭제할 수 없는 메뉴 ID 접두사 목록 — 이 접두사로 시작하는 메뉴는 삭제와 미사용 처리가 차단된다 */
export const PROTECTED_MENU_PREFIXES = ["msys"];

/**
 * 권한별 자동 시스템 메뉴 매핑 — TN_AuthorMenu 부여 없이도 권한 자체로 시스템 메뉴 접근.
 * - admin 시스템관리자: 모든 시스템 메뉴 (isSysAdmin 분기로 자동 — 이 매핑은 사실상 무관)
 * - operator 일반관리자: 사용자관리(msys1005), 메일발송로그(msys1006).
 *   권한관리(msys1003)는 전역(워크스페이스 무관) 권한을 변경 → 모든 워크스페이스에 영향이라 시스템관리자 전용. 운영자 제외.
 * - user 일반사용자: 시스템 메뉴 없음
 */
export const AUTO_SYSTEM_MENUS_BY_AUTHOR: Record<string, string[]> = {
  [GENERAL_ADMIN_AUTHOR_ID]: ["msys1005", "msys1006"],
};

/**
 * 개인 워크스페이스가 만들어질 때 함께 부여되는 기본 업무 메뉴 (`tn_workspace_menu`).
 *
 * 네비게이션은 일반 사용자에게 **권한 메뉴 ∩ 워크스페이스 메뉴** 만 노출한다
 * (`app/api/common/system/menu/navigation/route.ts` 의 `isVisible`). 개인 워크스페이스에는
 * 그 교집합의 한쪽인 `tn_workspace_menu` 행이 하나도 없어서, SaaS 가입자가 로그인하면
 * 메뉴 API 가 `{"items":[]}` 를 반환하고 **사이드바가 빈 채로 떴다** (#251).
 *
 * **무엇을 넣는가 (판단 근거)**: 리드 결정(#242)은 "대시보드가 메인, 터미널은 여는 것"이고
 * 대시보드 화면은 아직 없다(#2 — 시세 적재 뒤). 그래서 **지금 존재하고 개인이 혼자 쓸 수
 * 있는 화면만** 넣는다 — 터미널(mbiz1008)과 관심종목(mbiz1001). 이 목록에 있어도 DB 에 없거나
 * `use_at='N'` 인 메뉴는 건너뛴다(운영자가 끈 메뉴를 되살리지 않는다).
 *
 * 실험대(mbiz1009)가 여기 있는 이유는 다르다 — **로그인 후 착지점**(`constants/routes.ts` 의
 * `POST_LOGIN_PATH`)이라, 가입자에게 이 메뉴가 없으면 착지가 fail-closed 게이트에 막혀
 * 종전처럼 첫 메뉴로 되돌아간다(#73 S2, 화면 결정 §20.2).
 *
 * 교집합의 다른 한쪽(권한)은 `prisma/init/seed.sql` 의 `tn_author_menu` 가 정한다 — 기본
 * 권한(`DEFAULT_USER_AUTHOR_ID`)이 이 목록을 전부 갖지 않으면 여기 넣어도 안 보인다.
 * 두 곳이 어긋나면 사이드바가 다시 조용히 비므로
 * `tests/regressions/251-personal-workspace-menu.test.ts` 가 둘을 대조한다.
 */
export const PERSONAL_WORKSPACE_DEFAULT_MENU_IDS = ["mbiz1009", "mbiz1008", "mbiz1001"];

/**
 * 공용/개인 이메일 도메인 블랙리스트.
 * - 워크스페이스 도메인으로 등록할 수 없다 (등록하면 해당 도메인을 쓰는 전 세계 사용자가 그 워크스페이스로 빨려들어옴).
 * - 가입 시점에 도메인 매핑 후보에서 자동 제외된다 (DB 에 등록 자체가 안 되니 매핑 시도되지 않음).
 */
export const PUBLIC_EMAIL_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "naver.com",
  "daum.net",
  "hanmail.net",
  "kakao.com",
  "nate.com",
  "yahoo.com",
  "yahoo.co.kr",
  "hotmail.com",
  "outlook.com",
  "live.com",
  "icloud.com",
  "me.com",
  "protonmail.com",
  "proton.me",
  "aol.com",
  "gmx.com",
  "gmx.net",
  "gmx.de",
]);

export const isSysAdminAuthor = (author_id: string) => author_id === SYS_ADMIN_AUTHOR_ID;
export const isProtectedAuthor = (author_id: string) => PROTECTED_AUTHOR_IDS.includes(author_id);
export const isProtectedMenu = (menu_id: string) =>
  PROTECTED_MENU_PREFIXES.some((prefix) => menu_id.startsWith(prefix));
export const isPublicEmailDomain = (domain: string) => PUBLIC_EMAIL_DOMAINS.has(domain.toLowerCase().trim());
