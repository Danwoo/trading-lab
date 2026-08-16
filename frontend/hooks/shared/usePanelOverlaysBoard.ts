"use client";

import { useSyncExternalStore } from "react";
import { VIEWPORT_COMPACT_MIN_PX } from "@/constants/shell";

/** Tailwind `lg:` 와 같은 질의여야 한다 — 그래야 CSS 가 겹으로 바꾸는 폭과 여기 답이 같다. */
const SIDE_BY_SIDE_QUERY = `(min-width: ${VIEWPORT_COMPACT_MIN_PX}px)`;

function subscribe(onChange: () => void): () => void {
  const list = window.matchMedia(SIDE_BY_SIDE_QUERY);
  list.addEventListener("change", onChange);
  return () => list.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  return !window.matchMedia(SIDE_BY_SIDE_QUERY).matches;
}

/**
 * 열린 패널이 보드를 **덮는** 폭인가 (§21.6 의 1024 미만).
 *
 * **폭·배분은 여기서 나오지 않는다** — 그건 CSS 가 정한다(`--shell-*` + `lg:`·`xl:`).
 * JS 에 남은 것은 이 한 줄뿐인데, 덮을 때는 패널이 「옆에 붙는 형제」에서 「보드를 덮는 겹」으로
 * **DOM 의 뜻이 바뀌어** 보드가 `inert` 가 되어야 하고, 그건 클래스로 켜고 끌 수 없기 때문이다.
 *
 * 서버 스냅샷은 `false`(덮지 않음)다. 이 값이 첫 페인트를 좌우하지 않는다 — 덮을 것이 있으려면
 * 패널이 열려 있어야 하고 패널은 레일을 눌러야 열리므로, 첫 페인트에는 열린 패널이 없다.
 * 폭을 JS 로 가르던 때와 다른 점이 여기다: 그때는 서버가 세 구간 중 하나를 찍어야 했다.
 */
export function usePanelOverlaysBoard(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
