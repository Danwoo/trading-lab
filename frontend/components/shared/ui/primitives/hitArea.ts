// components/shared/ui/primitives/hitArea.ts
//
// 아이콘 조작부의 최소 표적 — WCAG 2.5.8 (AA) 은 조작부의 표적을 24×24 CSS px 이상으로 요구한다.
// 아이콘만 있는 버튼은 글리프 크기가 곧 상자 크기라, 손가락으로 누르면 옆 칸이 눌린다.
//
// **상자만 세우고 글리프는 안 키운다** — `min-w`/`min-h` 로 상자를 밀어 올리고 글리프는
// 가운데 정렬로 둔다. 보이는 글리프 크기는 어느 갈래에서도 그대로다.
//
// 예외는 하나다: 본문 문장 안에 놓인 인라인 링크(2.5.8 의 "Inline" 예외). 그 자리에는 붙이지
// 않는다 — 줄 높이를 벌려 문단이 깨진다.
//
// ## 표적이 입력 장치에 따라 갈린다 (#289 리드 결정 2026-08-21 ②)
//
// 마우스 24px · 손가락 44px 이고, 갈래는 **CSS 한 곳**(`styles/globals.css` 의
// `--touch-icon-target`, `@media (pointer: coarse)` 에서 44px)이 정한다. 폭이 아니라 포인터로
// 가르는 이유는 셸 토큰(`--touch-*`)과 같다 — 터치 노트북은 넓어도 손가락으로 누른다.
//
// 갈래를 클래스가 아니라 토큰에 둔 이유: 이 클래스를 쓰는 자리가 14곳이라 `pointer-coarse:`
// 변형을 자리마다 붙이면 SoT 가 14개로 흩어진다. 토큰 하나면 값도 미디어 쿼리도 한 줄이다.
// 셸의 `--touch-min`(26px · coarse 44px)과는 여전히 층이 다르다 — 그쪽은 촘촘한 목록·탭의
// **줄 높이** 하한이고 여기는 아이콘 **표적**의 하한이다. 둘이 24 아래로 못 내려가는 것은
// `tests/styles/shellTokens.test.ts` 가 잠근다.
//
// **남는 것**: 손가락 기기에서는 줄 높이가 정해진 자리(패널 머리·탭 줄)가 상자만큼 벌어진다.
// 그 값은 PR #289 본문의 「보이는 것이 안 변했다」 표에 두 갈래 다 적혀 있다.

/** 크기·정렬만. `display` 를 구간별로 갈라야 하는 자리(`hidden xl:inline-flex`)가 쓴다. */
export const ICON_HIT_AREA_BOX = "min-h-touch-icon min-w-touch-icon items-center justify-center";

/** 아이콘 전용 버튼의 기본형 — 이것을 쓰면 상자가 마우스 24×24 · 손가락 44×44 이상이다. */
export const ICON_HIT_AREA = `inline-flex ${ICON_HIT_AREA_BOX}`;
