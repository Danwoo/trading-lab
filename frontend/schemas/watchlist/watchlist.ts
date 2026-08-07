// schemas/watchlist/watchlist.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { StrRange, Field, Optional, PositiveFloat, enums, object, files } from "@/lib/zod/helpers";

// 백엔드 계약: backend-service/app/schemas/watchlist/watchlist_schema.py
//   Watchlist{issuer_nm?(200), market?(20), sector?(100), currency?(5),
//             target_price?(float ge0), alert_price?(float ge0), priority?(5),
//             use_at?(1, 기본 Y), memo?(1300), atch_file_id?(20)}
//   WatchlistCreateIn = Watchlist + ticker(20, 필수), WatchlistUpdateIn = Watchlist(ticker 없음)
export const WatchlistSchema = object({
  ticker: StrRange(1, 20),
  issuer_nm: Optional(Field({ max_length: 200 }).str()),
  market: Optional(Field({ max_length: 20 }).str()),
  sector: Optional(Field({ max_length: 100 }).str()),
  currency: Optional(Field({ max_length: 5 }).str()),
  target_price: Optional(PositiveFloat()),
  alert_price: Optional(PositiveFloat()),
  priority: Optional(Field({ max_length: 5 }).str()),
  use_at: enums(["Y", "N"]),
  memo: Optional(Field({ max_length: 1300 }).str()),
  atch_file_id: Optional(Field({ max_length: 20 }).str()),
});

// CRUD 스키마 — ticker 는 PK 라 생성 시에만 입력, 수정 시 URL 경로로 전달
// researchFiles: 폼 업로더가 선택한 리서치 문서(업로드 후 atch_file_id 로 치환). z.object 가
//   미지 키를 제거하므로 파일 배열이 검증을 통과하려면 스키마에 명시해야 한다(옛 todo 패턴).
export const WatchlistCreateInSchema = WatchlistSchema.extend({
  researchFiles: Optional(files()),
});
export const WatchlistUpdateInSchema = WatchlistSchema.omit({ ticker: true }).extend({
  researchFiles: Optional(files()),
});

// 타입 정의
export type Watchlist = z.infer<typeof WatchlistSchema>;
export type WatchlistOut = Watchlist & CommonEntity;
export interface WatchlistsOut {
  items: WatchlistOut[];
  total_count: number;
}
