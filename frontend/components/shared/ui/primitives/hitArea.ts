// components/shared/ui/primitives/hitArea.ts
//
// 아이콘 조작부의 최소 표적 — WCAG 2.5.8 (AA) 은 조작부의 표적을 24×24 CSS px 이상으로 요구한다.
// 아이콘만 있는 버튼은 글리프 크기가 곧 상자 크기라, 손가락으로 누르면 옆 칸이 눌린다.
//
// **상자만 세우고 글리프는 안 키운다** — `min-w`/`min-h` 로 상자를 24 로 밀어 올리고 글리프는
// 가운데 정렬로 둔다. 보이는 크기는 그대로다.
//
// 예외는 하나다: 본문 문장 안에 놓인 인라인 링크(2.5.8 의 "Inline" 예외). 그 자리에는 붙이지
// 않는다 — 줄 높이를 벌려 문단이 깨진다.

/** 크기·정렬만. `display` 를 구간별로 갈라야 하는 자리(`hidden xl:inline-flex`)가 쓴다. */
export const ICON_HIT_AREA_BOX = "min-h-6 min-w-6 items-center justify-center";

/** 아이콘 전용 버튼의 기본형 — 이것을 쓰면 상자가 항상 24×24 이상이다. */
export const ICON_HIT_AREA = `inline-flex ${ICON_HIT_AREA_BOX}`;
