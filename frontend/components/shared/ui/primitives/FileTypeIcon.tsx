// components/shared/ui/primitives/FileTypeIcon.tsx
//
// 확장자별 파일 아이콘 (#341 — DevExtreme 아이콘 폰트 대체 과정에서 중복 제거).
// `FileListDisplay.tsx` 와 `FileUploader.tsx` 가 **같은 매핑 표를 각자 복사해** 갖고 있었다 —
// 아이콘 세트를 옮기며 한쪽만 고치면 두 화면의 아이콘이 갈리므로 여기로 합친다.
"use client";

import { Icon } from "./icons";

/** 확장자 → (아이콘 이름, 색 클래스). 확장자는 소문자·점 없는 형태로 조회한다. */
const EXTENSION_ICONS: Record<string, { name: string; color: string }> = {
  pdf: { name: "pdffile", color: "text-red-500" },
  doc: { name: "doc", color: "text-blue-600" },
  docx: { name: "doc", color: "text-blue-600" },
  xls: { name: "xlsfile", color: "text-green-600" },
  xlsx: { name: "xlsfile", color: "text-green-600" },
  csv: { name: "xlsfile", color: "text-green-600" },
  parquet: { name: "xlsfile", color: "text-indigo-600" },
  ppt: { name: "file", color: "text-orange-500" },
  pptx: { name: "file", color: "text-orange-500" },
  txt: { name: "doc", color: "text-gray-600" },
  rtf: { name: "doc", color: "text-gray-600" },
  zip: { name: "folder", color: "text-purple-600" },
  rar: { name: "folder", color: "text-purple-600" },
  "7z": { name: "folder", color: "text-purple-600" },
  tar: { name: "folder", color: "text-purple-600" },
  gz: { name: "folder", color: "text-purple-600" },
  jpg: { name: "image", color: "text-blue-500" },
  jpeg: { name: "image", color: "text-blue-500" },
  png: { name: "image", color: "text-blue-500" },
  gif: { name: "image", color: "text-blue-500" },
  bmp: { name: "image", color: "text-blue-500" },
  webp: { name: "image", color: "text-blue-500" },
};

/** 확장자 필드가 비어 있으면 파일명 끝에서 뽑는다(업로드 직후엔 확장자 필드가 없다). */
function resolveExtension(extension: string, fileName: string): string {
  let ext = extension?.toLowerCase() ?? "";
  if (!ext && fileName) {
    const lastDot = fileName.lastIndexOf(".");
    if (lastDot > 0) ext = fileName.slice(lastDot + 1).toLowerCase();
  }
  return ext.replace(".", "");
}

/**
 * 파일 종류 아이콘. 파일명이 항상 옆에 함께 표시되므로 장식으로 둔다(접근명 없음) —
 * 스크린리더는 파일명을 읽으면 되고, 아이콘까지 읽으면 같은 정보가 두 번 나온다.
 */
export function FileTypeIcon({ extension, fileName }: { extension: string; fileName: string }) {
  // 확장자는 파일명에서 뽑는 자유 문자열이다 — `Object.hasOwn` 없이 조회하면
  // `report.constructor` 같은 이름이 상속 멤버를 물어온다(icons.tsx `resolveIconComponent` 주석).
  const key = resolveExtension(extension, fileName);
  const entry = Object.hasOwn(EXTENSION_ICONS, key) ? EXTENSION_ICONS[key] : undefined;
  return <Icon name={entry?.name ?? "file"} size={20} className={entry?.color ?? "text-gray-400"} />;
}
