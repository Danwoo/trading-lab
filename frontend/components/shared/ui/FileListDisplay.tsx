// components/shared/ui/FileListDisplay.tsx
"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { FileDetail } from "@/schemas/common/file";
import { Button } from "@/components/shared/ui/Button";
import { selectFileDownloadUrl, selectFilePreviewUrl } from "@/services/common/fileService";
import { useFileGroups } from "@/hooks/shared/useFileGroups";
import { formatFileSize } from "@/utils/common/fileUtils";
import { showToast } from "@/components/shared/Feedback";
import { FileTypeIcon } from "@/components/shared/ui/primitives/FileTypeIcon";
import { Icon } from "@/components/shared/ui/primitives/icons";

interface Props {
  atchFileId?: string;
  fileSn?: number;
  compact?: boolean;
}

/**
 * 이미지 미리보기 컴포넌트
 */
const ImagePreview: React.FC<{ file: FileDetail; atchFileId: string }> = ({ file, atchFileId }) => {
  const isPdf = file.file_extsn?.toLowerCase() === "pdf" || file.orignl_file_nm?.toLowerCase().endsWith(".pdf");

  const [imageUrl, setImageUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    // PDF는 미리보기 로직 실행 안함
    if (isPdf) {
      setIsLoading(false);
      setError(true);
      return;
    }

    const loadImageUrl = async () => {
      try {
        setIsLoading(true);
        setError(false);
        const url = await selectFilePreviewUrl(atchFileId, file.file_sn);
        setImageUrl(url);
      } catch (err) {
        console.error("이미지 URL 로드 실패:", err);
        setError(true);
      } finally {
        setIsLoading(false);
      }
    };

    loadImageUrl();
  }, [atchFileId, file.file_sn, isPdf]);

  const handleImageClick = async () => {
    try {
      const url = await selectFilePreviewUrl(atchFileId, file.file_sn);
      window.open(url, "_blank");
    } catch (error) {
      console.error("이미지 미리보기 실패:", error);
    }
  };

  if (isLoading) {
    return (
      <div className="relative w-full h-32 rounded border overflow-hidden bg-gray-100 flex items-center justify-center">
        <div className="text-gray-400 text-sm">로딩 중...</div>
      </div>
    );
  }

  // PDF 또는 에러시 문서 아이콘 표시
  if (error || !imageUrl || isPdf) {
    return (
      <div className="relative w-full h-32 rounded border overflow-hidden bg-gray-100 flex items-center justify-center">
        <div className="flex flex-col items-center gap-1">
          <FileTypeIcon extension={file.file_extsn || ""} fileName={file.orignl_file_nm || ""} />
          <span className="text-xs text-gray-500 text-center truncate w-full px-2">{file.orignl_file_nm}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="cursor-pointer" onClick={handleImageClick}>
      <div className="relative group">
        <div className="relative w-full h-32 rounded border overflow-hidden">
          <Image
            src={imageUrl}
            alt={file.orignl_file_nm}
            fill
            unoptimized={true}
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            className="object-contain hover:opacity-80 transition-opacity"
            onError={() => console.error("이미지 로드 실패:", file.orignl_file_nm)}
          />
        </div>
        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 rounded transition-all duration-200 flex items-center justify-center">
          <Icon name="find" size={28} className="text-white opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      </div>
    </div>
  );
};

/**
 * 파일 목록 표시 컴포넌트
 */
export const FileListDisplay: React.FC<Props> = ({ atchFileId, compact = false, fileSn }) => {
  const [isDownloading, setIsDownloading] = useState(false);

  // 파일 목록 조회
  const fileGroups = useFileGroups(atchFileId ? [{ key: "files", fileId: atchFileId }] : []);
  let files = fileGroups.files?.files || [];
  // 「없다」와 「못 읽었다」를 가른다 — 조회 실패를 「없음」으로 그리면 사용자는 첨부가 유실됐다고
  // 믿고 다시 올리려 든다 (#440·B-10).
  const loadFailed = fileGroups.files?.error === true;

  if (fileSn !== undefined) {
    files = files.filter((file) => file.file_sn === fileSn);
  }

  // 단일 파일 다운로드
  const handleDownload = async (file: FileDetail) => {
    try {
      const url = await selectFileDownloadUrl(atchFileId!, file.file_sn);
      window.open(url, "_blank");
    } catch (error) {
      console.error("파일 다운로드 실패:", error);
    }
  };

  // 전체 파일 다운로드
  const handleDownloadAll = async () => {
    if (!atchFileId || files.length === 0) return;

    try {
      setIsDownloading(true);

      // 각 파일을 순차적으로 다운로드
      for (const file of files) {
        try {
          const url = await selectFileDownloadUrl(atchFileId, file.file_sn);

          // iframe을 사용한 다운로드 (브라우저 팝업 차단 우회)
          const iframe = document.createElement("iframe");
          iframe.style.display = "none";
          iframe.src = url;
          document.body.appendChild(iframe);

          // iframe 정리
          setTimeout(() => {
            document.body.removeChild(iframe);
          }, 1000);

          // 다음 파일 다운로드 전 대기
          await new Promise((resolve) => setTimeout(resolve, 300));
        } catch (error) {
          console.error(`파일 다운로드 실패: ${file.orignl_file_nm}`, error);
        }
      }
    } catch (error) {
      console.error("전체 다운로드 실패:", error);
      showToast("파일 다운로드 중 오류가 발생했습니다.", "error");
    } finally {
      setIsDownloading(false);
    }
  };

  // compact 모드
  if (compact) {
    if (!atchFileId?.trim() || files.length === 0) {
      return null;
    }

    return (
      <Button
        text="다운로드"
        onClick={handleDownloadAll}
        stylingMode="outlined"
        type="default"
        width="auto"
        height={28}
        disabled={isDownloading}
      />
    );
  }

  // 일반 모드
  if (!atchFileId?.trim()) {
    return <div className="text-gray-400">첨부된 파일이 없습니다.</div>;
  }

  if (loadFailed) {
    return (
      <div className="text-amber-700" role="status">
        첨부 목록을 불러오지 못했습니다 — 파일이 없다는 뜻은 아닙니다. 잠시 후 화면을 다시 열어 주세요.
      </div>
    );
  }

  if (files.length === 0) {
    return <div className="text-gray-400">첨부된 파일이 없습니다.</div>;
  }

  const imageFiles = files.filter(
    (file) => file.file_ty === "IMAGE" && file.file_extsn?.toLowerCase().match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i),
  );

  const documentFiles = files.filter(
    (file) => !(file.file_ty === "IMAGE" && file.file_extsn?.toLowerCase().match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i)),
  );

  return (
    <div className="space-y-4">
      {/* 이미지 그리드 - 동적 컬럼 */}
      {imageFiles.length > 0 && (
        <div
          className="grid gap-2"
          style={{
            gridTemplateColumns: `repeat(${Math.min(imageFiles.length, 5)}, 1fr)`,
          }}
        >
          {imageFiles.map((file) => (
            <ImagePreview key={file.file_sn} file={file} atchFileId={atchFileId} />
          ))}
        </div>
      )}

      {/* 문서 리스트 */}
      {documentFiles.length > 0 && (
        <div className="space-y-2">
          {documentFiles.map((file) => (
            <div key={file.file_sn} className="flex items-center justify-between p-2 bg-gray-50 rounded border">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className="flex-shrink-0">
                  <FileTypeIcon extension={file.file_extsn || ""} fileName={file.orignl_file_nm || ""} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">{file.orignl_file_nm}</div>
                  <div className="text-xs text-gray-500">{formatFileSize(file.file_mg || 0)}</div>
                </div>
              </div>

              <div className="flex gap-2 ml-1">
                <Button
                  text="다운로드"
                  onClick={() => handleDownload(file)}
                  stylingMode="outlined"
                  type="default"
                  width="auto"
                  height={28}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
