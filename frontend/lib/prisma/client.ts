import { env } from "@/env";
import { PrismaClient } from "@/prisma/generated/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { poolConfigWithUtcTimezone } from "./sessionTimezone";

const globalForPrisma = global as unknown as { prisma: PrismaClient };

function createPrismaClient() {
  const url = env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  // Prisma 소유 테이블은 frontend 스키마에 산다 (DB 는 fintech 하나 — 소유만 스키마로 갈랐다.
  // .docs/5-인프라셋팅/로컬-postgres.md). `?schema=` 는 Prisma CLI(db push)만 읽고 pg 드라이버는
  // 무시하므로, 런타임 어댑터에는 스키마를 따로 넘겨야 쿼리가 스키마 수식된다 — 안 넘기면
  // search_path 기본값(public, 파이썬 서비스 소유)으로 떨어져 테이블을 찾지 못한다.
  const schema = new URL(url).searchParams.get("schema") ?? undefined;
  // 세션 타임존은 코드가 못박는다 (#359) — 사용자 `.env` 의 DATABASE_URL 에 기대지 않는다.
  // 어댑터는 오프셋 없는 UTC 자릿수 문자열을 보내므로(formatDateTime), `timestamptz` 컬럼에서는
  // 서버가 그 자릿수를 **세션 tz 로** 해석한다 — 세션이 UTC 가 아니면 저장 인스턴트가 어긋난다.
  // 어댑터 생성자는 pg.PoolConfig 를 그대로 받는다(@prisma/adapter-pg 7.9.1 index.d.ts).
  const adapter = new PrismaPg(poolConfigWithUtcTimezone(url), schema ? { schema } : undefined);
  return new PrismaClient({ adapter });
}

export const prisma = globalForPrisma.prisma || createPrismaClient();

if (env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
