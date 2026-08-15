"use client";

import { useSyncExternalStore } from "react";
import { VIEWPORT_COMPACT_MIN_PX, VIEWPORT_WIDE_MIN_PX } from "@/constants/shell";

/** §21.6 의 폭 구간. 이름의 뜻은 `constants/shell.ts` 의 상수 주석에 있다. */
export type ViewportBand = "wide" | "compact" | "overlay";

const WIDE_QUERY = `(min-width: ${VIEWPORT_WIDE_MIN_PX}px)`;
const COMPACT_QUERY = `(min-width: ${VIEWPORT_COMPACT_MIN_PX}px)`;

function subscribe(onChange: () => void): () => void {
  const lists = [window.matchMedia(WIDE_QUERY), window.matchMedia(COMPACT_QUERY)];
  lists.forEach((list) => list.addEventListener("change", onChange));
  return () => lists.forEach((list) => list.removeEventListener("change", onChange));
}

function getSnapshot(): ViewportBand {
  if (window.matchMedia(WIDE_QUERY).matches) return "wide";
  if (window.matchMedia(COMPACT_QUERY).matches) return "compact";
  return "overlay";
}

/**
 * 지금 화면 폭이 §21.6 의 어느 구간인가.
 *
 * 폭을 **CSS 만으로** 가르지 않는 이유는, 구간에 따라 패널이 「옆에 붙는 형제」에서 「보드를
 * 덮는 겹」으로 **DOM 의 뜻 자체가 바뀌기** 때문이다 — 덮을 때는 Escape 로 닫히고 보드가
 * `inert` 가 되어야 하는데, 그건 클래스로 켜고 끌 수 있는 것이 아니다.
 *
 * 서버 렌더 스냅샷은 `wide` 다 — 첫 페인트를 넓은 화면 기준으로 그린 뒤 마운트에서 실제 폭으로
 * 정정한다(`useSyncExternalStore` 가 하이드레이션 불일치 없이 이 두 벌을 다룬다). 좁은 화면
 * 사용자는 한 프레임 넓게 봤다 좁아지지만, 반대로 두면 넓은 화면 사용자 전부가 그 값을 치른다.
 */
export function useViewportBand(): ViewportBand {
  return useSyncExternalStore(subscribe, getSnapshot, () => "wide");
}
