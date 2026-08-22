import { POST_LOGIN_PATH, fallbackPathWithReason } from "@/constants/routes";
import type { NavFailure } from "@/stores/shared/navStore";

interface NavNode {
  path?: string;
  items?: NavNode[];
}

/**
 * 메뉴를 읽은 결과 — 셋을 가른다. `failure` 가 「못 읽음/로그아웃됨」이고, `failure === null`
 * 인데 `items` 가 빈 것이 「0건」이다. 하나로 뭉치면 어느 한쪽에는 거짓을 말하게 된다.
 */
export interface NavSnapshot {
  items: NavNode[];
  failure: NavFailure | null;
}

/**
 * 로그인 직후 어디로 보내고 무엇을 말할 것인가.
 *
 * **「못 읽음」과 「0건」을 가른다** (#333). 종전에는 `items` 만 보고 둘 다 「접근 가능한 메뉴가
 * 없습니다 / 관리자에게 문의해 주세요」로 끝냈다 — 못 읽었을 때 그것은 사실이 아닌 진단이고,
 * 로컬 배포판에서 문의할 관리자는 그 화면을 보는 사람 자신이다.
 */
export type PostLoginDestination =
  /** 메뉴에 열린 화면이 있다 — 제품 안으로 들어간다 */
  | { kind: "landing"; path: string; title?: undefined; lines?: undefined }
  /** 메뉴를 못 읽었다 — 세션은 끊기지 않았으므로 제품 안으로 들여보내고, 셸이 사유 화면을 세운다 */
  | { kind: "menu-unreadable"; path: string; title: string; lines: string[] }
  /** 방금 로그인했는데 서버가 세션을 거부했다(401) — 제품 안으로 들여보내면 안 된다 */
  | { kind: "session-expired"; path: string; title: string; lines: string[] }
  /** 메뉴를 읽었고 0건이다 — 계정 상태 이야기라 제품 밖으로 되돌리되 도착지가 사유를 안다 */
  | { kind: "no-menu"; path: string; title: string; lines: string[] };

const findFirstPath = (items: NavNode[]): string | null => {
  for (const item of items) {
    if (item.path) return item.path;
    if (item.items) {
      const found = findFirstPath(item.items);
      if (found) return found;
    }
  }
  return null;
};

const hasPath = (items: NavNode[], target: string): boolean =>
  items.some((item) => item.path === target || (item.items ? hasPath(item.items, target) : false));

/**
 * 착지점.
 *
 * 예전에는 「접근 가능한 첫 메뉴」였다 — 메뉴 정렬 순서가 곧 홈이라, 메뉴 하나를 위로 올리면
 * 홈이 조용히 바뀌었다. 실험대가 홈이 되면서(화면 결정 §20.2) 착지점을 상수로 못박는다. 다만
 * **메뉴 게이트가 fail-closed** 라 그 경로 권한이 없는 사용자를 그리로 보내면 셸이 곧바로
 * 되돌려 왕복한다 — 그래서 네비게이션에 있을 때만 쓰고, 없으면 종전대로 첫 메뉴로 내려간다.
 */
const resolveLandingPath = (items: NavNode[]): string | null =>
  hasPath(items, POST_LOGIN_PATH) ? POST_LOGIN_PATH : findFirstPath(items);

export function resolvePostLoginDestination(nav: NavSnapshot): PostLoginDestination {
  // 로그인 직후의 401 은 드물지만(방금 세션을 받았다) 표현 가능한 상태다 — 세션 비밀키가
  // 교체됐거나 그 사이 세션이 폐기되면 온다. 여기서 안 가르면 `items` 가 비었다는 이유로
  // 「이 계정에 열려 있는 화면이 없습니다」라는 **사실이 아닌 진단**으로 새어 나간다.
  if (nav.failure === "unauthenticated") {
    return {
      kind: "session-expired",
      path: fallbackPathWithReason("session-expired"),
      title: "알림",
      lines: ["로그인은 됐지만 서버가 그 세션을 받지 않았습니다.", "다시 로그인해 주세요."],
    };
  }

  if (nav.failure === "unreadable") {
    return {
      kind: "menu-unreadable",
      // 못 읽었다고 로그인 화면에 세워 두지 않는다 — 셸이 사유와 다시 시도를 그대로 들고 있다.
      path: POST_LOGIN_PATH,
      title: "알림",
      lines: ["메뉴를 읽지 못했습니다.", "데이터베이스와 백엔드가 떠 있는지 확인해 주세요."],
    };
  }

  const landingPath = resolveLandingPath(nav.items);
  if (landingPath) return { kind: "landing", path: landingPath };

  return {
    kind: "no-menu",
    path: fallbackPathWithReason("no-menu"),
    title: "알림",
    lines: ["이 계정에 열려 있는 화면이 없습니다.", "관리 화면(/admin)의 메뉴·권한에서 이 계정에 화면을 열어 주세요."],
  };
}
