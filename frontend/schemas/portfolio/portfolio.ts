// schemas/portfolio/portfolio.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { StrRange, Field, Optional, PositiveInt, PositiveFloat, int, enums, object } from "@/lib/zod/helpers";

// ── Portfolio (master) ─────────────────────────────────────────────────
export const PortfolioSchema = object({
  portfolio_id: StrRange(1, 20),
  portfolio_nm: StrRange(1, 200),
  sort_ordr: PositiveInt(),
  use_at: enums(["Y", "N"]),
  description: Optional(Field({ max_length: 1000 }).str()),
});

export const PortfolioCreateInSchema = PortfolioSchema;
export const PortfolioUpdateInSchema = PortfolioSchema.omit({ portfolio_id: true });

export type Portfolio = z.infer<typeof PortfolioSchema>;
export type PortfolioOut = Portfolio & CommonEntity;
export interface PortfoliosOut {
  items: PortfolioOut[];
  total_count: number;
}

// ── Holding (detail) ───────────────────────────────────────────────────
export const HoldingSchema = object({
  portfolio_id: StrRange(1, 20),
  ticker: StrRange(1, 20),
  holding_nm: StrRange(1, 200),
  quantity: int(),
  avg_price: PositiveFloat(),
  // Watchlist.market 과 대칭(#328) — 기존 행은 백필하지 않아 비어 있을 수 있다.
  market: Optional(Field({ max_length: 20 }).str()),
  use_at: enums(["Y", "N"]),
  description: Optional(Field({ max_length: 1000 }).str()),
});

export const HoldingCreateInSchema = HoldingSchema.omit({ portfolio_id: true });
export const HoldingUpdateInSchema = HoldingSchema.omit({ portfolio_id: true, ticker: true });

export type Holding = z.infer<typeof HoldingSchema>;
export type HoldingOut = Holding & CommonEntity & { portfolio_nm?: string };
export interface HoldingsOut {
  items: HoldingOut[];
  total_count: number;
}
