// components/shared/Feedback/Loading.tsx
"use client";

// 간단한 위치 프리셋 타입
type PositionPreset = "center" | "top" | "bottom";

// Loading 기본값 상수
const DEFAULT_LOADING_WIDTH = 200;
const DEFAULT_LOADING_HEIGHT = 90;

interface Props {
  visible: boolean;
  message?: string;
  showIndicator?: boolean;
  showPane?: boolean;
  shading?: boolean;
  shadingColor?: string;
  width?: number | string;
  height?: number | string;
  position?: PositionPreset;
}

/** 프리셋 → 오버레이 안에서의 정렬. `of`(특정 요소에 붙이기)는 소비자가 없어 옮기지 않았다. */
const POSITION_CLASSES: Record<PositionPreset, string> = {
  center: "items-center justify-center",
  top: "items-start justify-center pt-12",
  bottom: "items-end justify-center pb-12",
};

/**
 * Loading 컴포넌트 (#341 — DevExtreme `LoadPanel` 이관)
 *
 * 데이터 로딩 중 표시하는 스피너 및 오버레이입니다.
 *
 * 오버레이는 **부모 요소를 기준**으로 덮는다(`absolute inset-0`) — 화면 전체를 덮고 싶으면
 * 호출부가 `relative` 인 조상 없이 두면 된다. 이관 전 `position.of` 로 대상 요소를 지정하던
 * 방식은 소비자가 없어 옮기지 않았다(`DetailPanel`·`TreeGridPanel` 둘 다 프리셋만 쓴다).
 *
 * 회전 애니메이션은 `prefers-reduced-motion` 에서 꺼진다(`motion-safe:`) — 정지한 원이라도
 * `role="status"` + 메시지로 상태는 그대로 전달된다.
 *
 * @example
 * <Loading visible={isLoading} message="데이터를 불러오는 중..." />
 */
export function Loading({
  visible,
  message = "Loading...",
  showIndicator = true,
  showPane = true,
  shading = true,
  shadingColor = "rgba(0,0,0,0)",
  width = DEFAULT_LOADING_WIDTH,
  height = DEFAULT_LOADING_HEIGHT,
  position = "center",
}: Props) {
  if (!visible) return null;

  return (
    <div
      className={`absolute inset-0 z-[1000] flex ${POSITION_CLASSES[position]}`}
      style={{ backgroundColor: shading ? shadingColor : "transparent" }}
    >
      <div
        role="status"
        aria-live="polite"
        style={{ width, height }}
        className={
          showPane
            ? "flex flex-col items-center justify-center gap-2 rounded border border-gray-200 bg-white shadow-lg"
            : "flex flex-col items-center justify-center gap-2"
        }
      >
        {showIndicator && (
          <span
            aria-hidden="true"
            className="h-6 w-6 rounded-full border-2 border-gray-300 border-t-blue-500 motion-safe:animate-spin"
          />
        )}
        <span className="text-sm text-gray-700">{message}</span>
      </div>
    </div>
  );
}
