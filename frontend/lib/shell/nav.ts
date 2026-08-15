/**
 * DB 메뉴(`tn_menu`)에서 온 네비게이션 트리를 두 셸이 나눠 쓰기 위한 순수 함수 모음.
 *
 * 셸이 둘이라 같은 트리를 두 가지로 읽는다 — 제품 셸(`app/(product)/layout.tsx`)은 **접근
 * 가능한 경로 목록**만 필요하고(레일은 정적이다), 관리 셸(`app/(main)/admin/layout.tsx`)은
 * **자기 화면만 걸러낸 트리**가 필요하다. 둘이 같은 파일에서 나오지 않으면 한쪽만 고쳐져
 * 메뉴가 조용히 어긋난다.
 */

export interface NavItem {
  id: string;
  text: string;
  icon?: string;
  path?: string;
  items?: NavItem[];
}

/** 관리 셸이 소유하는 경로 접두어. 이 밖의 메뉴는 제품 셸의 레일이 소유한다. */
export const ADMIN_PATH_PREFIX = "/admin";

/**
 * 경로 매칭 — 정확히 같거나 슬래시 경계로 시작.
 * (`/admin/foo` 가 `/admin/foobar` 를 잘못 매칭하는 over-match 방지)
 */
export const matchesPath = (pathname: string, allowed: string): boolean =>
  pathname === allowed || pathname.startsWith(allowed + "/");

/** 트리에 있는 모든 `path` 를 평평하게. 접근 가능 경로 판정의 단일 출처다. */
export const collectNavPaths = (items: NavItem[]): string[] =>
  items.flatMap((item) => [...(item.path ? [item.path] : []), ...(item.items ? collectNavPaths(item.items) : [])]);

/** 그 경로에 해당하는 잎 노드. 탭 제목을 메뉴에서 가져올 때 쓴다. */
export function findNavByPath(items: NavItem[], path: string): NavItem | null {
  for (const item of items) {
    if (item.path === path) return item;
    if (item.items) {
      const found = findNavByPath(item.items, path);
      if (found) return found;
    }
  }
  return null;
}

/** 트리를 앞에서부터 훑어 처음 만나는 경로. 착지점 폴백에 쓴다. */
export function findFirstNavPath(items: NavItem[]): string | null {
  for (const item of items) {
    if (item.path) return item.path;
    if (item.items) {
      const found = findFirstNavPath(item.items);
      if (found) return found;
    }
  }
  return null;
}

/**
 * 관리 셸(MDI 탭)이 보여줄 메뉴만 남긴다 — `/admin` 아래 경로를 가진 잎과 그 부모.
 *
 * 탭 콘텐츠는 iframe 이라, 제품 경로(`/bench`·`/terminal`)가 이 목록에 남아 있으면 제품 화면이
 * 관리 셸 안의 iframe 으로 열린다. 제품 경로는 레일이 목적지로 소유하므로 여기서 잘라낸다.
 * 잎이 하나도 안 남은 대분류는 함께 사라진다(빈 폴더를 그리지 않는다).
 */
export function selectAdminNavItems(items: NavItem[]): NavItem[] {
  const isAdminLeaf = (item: NavItem) => !!item.path && matchesPath(item.path, ADMIN_PATH_PREFIX);

  return items.flatMap((item) => {
    if (!item.items) return isAdminLeaf(item) ? [item] : [];
    const children = selectAdminNavItems(item.items);
    if (children.length === 0) return [];
    return [{ ...item, items: children }];
  });
}
