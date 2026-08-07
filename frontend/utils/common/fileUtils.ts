// utils/common/fileUtils.ts
export const formatFileSize = (bytes: number): string => {
  // 음수·NaN·Infinity 방어 — 사용처(FileUploader 등)가 값 없음을 `|| 0`으로
  // 처리하는 관례에 맞춰, 유효하지 않은 크기도 "0 B"로 표시한다 (#264)
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";

  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB", "EB"];

  // 0 < bytes < 1 은 B 단위로, EB 초과는 마지막 단위로 클램프 — sizes[i] 가
  // undefined 가 되지 않게 한다 (#264)
  const i = Math.min(Math.max(Math.floor(Math.log(bytes) / Math.log(k)), 0), sizes.length - 1);

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};
