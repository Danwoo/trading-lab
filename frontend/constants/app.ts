/** MDI 탭 최대 개수 — 초과 시 LRU로 가장 오래된 탭 자동 close */
export const MAX_TABS = 20;

/** 그리드 기본 페이지 사이즈 — 그리드 종류별 디폴트 (프로젝트에 따라 조정) */
export const PAGE_SIZE = {
  MASTER: 20, // 마스터 목록 그리드
  DETAIL: 15, // 디테일 내부 그리드
  SELECT: 15, // 팝업 선택 그리드
  LOOKUP: 20, // 룩업(검색형 드롭다운)
} as const;

/** 페이저에서 선택 가능한 페이지 사이즈 옵션 */
export const ALLOWED_PAGE_SIZES = [10, 15, 20, 50, 100];
