// schemas/common/file.ts
import { CommonEntity } from "@/schemas/common/types";

// ==================== 파일 (File) 기본 타입 ====================

export interface File {
  atch_file_id: string; // PK
}

export interface FileOut extends File, CommonEntity {}

export interface FileListOut {
  items: FileOut[];
  total_count: number;
}

// ==================== 파일 상세 (FileDetail) 기본 타입 ====================

export interface FileDetail {
  atch_file_id: string;
  file_sn: number;
  file_stre_cours?: string;
  stre_file_nm?: string;
  orignl_file_nm: string;
  file_extsn?: string;
  file_mg?: number;
  file_ty?: string;
}

export interface FileDetailOut extends FileDetail, CommonEntity {
  id?: string;
  name?: string;
  size?: number;
  url?: string;
}

export interface FileDetailListOut {
  items: FileDetailOut[];
  total_count: number;
}

export interface FilePreviewQuery {
  size?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
}
